import hmac
import json
import re
import shutil
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, custom_ready
from .models import JobRequest, SAMPLE_BBOX
from .sessions import BrowserSessions, COOKIE
from .store import Conflict, QueueFull, Store, public_job


def create_app(settings=None):
    s = (settings or Settings()).validate()
    store = Store(s.data)
    sessions = BrowserSessions(s.data, s.retention_days)
    app = FastAPI(title="NbS pyWaPOR jobs", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=s.origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"], expose_headers=["Content-Disposition"])
    auth = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def bounded_body(request: Request, call_next):
        # Limit streamed bodies too: Content-Length is not trusted.
        if request.method == "POST":
            origin = request.headers.get("origin")
            if s.public_access and ((origin is not None and origin not in s.origins) or (origin is None and request.headers.get("sec-fetch-site") == "cross-site")):
                return JSONResponse({"detail": "Submit tasks from the platform website."}, status_code=403)
            size, chunks = 0, []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 220_000:
                    return JSONResponse({"detail": "The request exceeds 220 KB. Simplify the boundary."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def legacy_owner(credentials):
        if credentials:
            for name, key in s.keys.items():
                if hmac.compare_digest(credentials.credentials.encode(), key.encode()):
                    return name
        return None

    def owner(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(auth)]):
        user = legacy_owner(credentials)
        if user:
            return user
        if s.public_access:
            user = sessions.owner(request.cookies.get(COOKIE))
            if user:
                return user
            raise HTTPException(401, "Refresh the page to restore your workspace.")
        raise HTTPException(401, "This compute service is restricted.", headers={"WWW-Authenticate": "Bearer"})

    @app.post("/api/session")
    def open_session(request: Request, response: Response, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(auth)]):
        if not s.public_access:
            raise HTTPException(403, "Automatic workspace access has not been enabled on this compute service.")
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "Use a JSON request.")
        token = sessions.open(request.cookies.get(COOKIE), legacy_owner(credentials))
        response.set_cookie(COOKIE, token, max_age=sessions.max_age, path=s.session_cookie_path, secure=s.secure_cookie, httponly=True, samesite="lax")
        return {"ready": True}

    def job_for(job_id, user):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise HTTPException(404, "Task not found.")
        row = store.get(job_id, user)
        if not row:
            raise HTTPException(404, "Task not found.")
        return row

    def result_for(job_id, user):
        row = job_for(job_id, user)
        if row["status"] == "expired":
            raise HTTPException(410, "These results have expired. Submit a new task.")
        if row["status"] != "succeeded":
            raise HTTPException(409, "Results are not ready.")
        path = s.data / "jobs" / job_id / "results" / "result.json"
        if not path.is_file():
            raise HTTPException(503, "Result storage is unavailable. Contact the administrator.")
        return json.loads(path.read_text())

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "nbs-pywapor", "version": "0.1.0"}

    @app.get("/api/capabilities")
    def capabilities(user: str = Depends(owner)):
        heartbeat = s.data / "worker-heartbeat"
        live = heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 45
        return {"analyst": user if user in s.keys else "Your workspace", "worker_online": live, "sample_ready": (s.data / "sample" / "ready.json").is_file(),
                "custom_enabled": custom_ready(s), "max_area_km2": s.max_area_km2, "max_days": s.max_days,
                "retention_days": s.retention_days,
                "sample": {"bbox": SAMPLE_BBOX, "start": "2021-07-01", "end": "2021-07-31", "name": "Fayoum public sample, Egypt"}}

    @app.post("/api/jobs", status_code=202)
    def submit(payload: JobRequest, user: str = Depends(owner), idempotency_key: Annotated[str, Header()] = ""):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", idempotency_key):
            raise HTTPException(400, "A submission key is required.")
        try:
            payload.validate_limits(s)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if payload.mode == "custom" and not custom_ready(s):
            raise HTTPException(503, "Custom regions are awaiting server data-account configuration and verification. The public sample is available.")
        if payload.mode == "sample" and not (s.data / "sample" / "ready.json").is_file():
            raise HTTPException(503, "The administrator is preparing the public sample inputs. Please try again later.")
        if shutil.disk_usage(s.data).free < s.min_free_bytes:
            raise HTTPException(503, "Result storage is nearly full. Contact the administrator.")
        try:
            return public_job(store.create(user, idempotency_key, payload.model_dump(mode="json"), s))
        except QueueFull as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "30"}) from exc
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/jobs")
    def jobs(user: str = Depends(owner)):
        return [public_job(r) for r in store.list(user)]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str, user: str = Depends(owner)):
        return public_job(job_for(job_id, user))

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str, user: str = Depends(owner)):
        job_for(job_id, user)
        return public_job(store.cancel(job_id, user))

    @app.get("/api/jobs/{job_id}/result")
    def result(job_id: str, user: str = Depends(owner)):
        return result_for(job_id, user)

    @app.get("/api/jobs/{job_id}/assets/{name}")
    def asset(job_id: str, name: str, user: str = Depends(owner)):
        manifest = result_for(job_id, user)
        entry = next((x for x in manifest["assets"] if x["file"] == name), None)
        if not entry or not re.fullmatch(r"[a-zA-Z0-9_.-]+", name) or ".." in name:
            raise HTTPException(404, "Result file not found.")
        root = (s.data / "jobs" / job_id / "results").resolve()
        path = (root / name).resolve()
        if path.parent != root or not path.is_file():
            raise HTTPException(404, "Result file not found.")
        return FileResponse(path, media_type=entry.get("media_type", "application/octet-stream"), filename=name)

    app.state.store, app.state.settings = store, s
    from diagnostics.api import install
    install(app, s, owner)
    from .analyses import install as install_analyses
    install_analyses(app, s, owner)
    return app
