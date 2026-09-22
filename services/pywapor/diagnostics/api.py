from dataclasses import replace
import asyncio
import json
import re
import shutil
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Query
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from online.store import Store, Conflict, QueueFull, public_job
from .models import DiagnosticRequest, MODULES, NASA_MODULES, nasa_ready
from .uploads import Uploads, public_upload


def install(app, settings, owner):
    s = replace(settings, data=settings.data / "diagnostics")
    s.data.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(s.data)
    uploads = Uploads(s.data)
    inspecting = asyncio.Semaphore(1)
    app.state.uploads = uploads

    @app.post("/api/diagnostics/uploads", status_code=201)
    async def upload(request: Request, kind: str = Query(), name: str = Query(max_length=120), user: str = Depends(owner)):
        if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
            raise HTTPException(415, "Send a binary source file.")
        if shutil.disk_usage(s.data).free < s.min_free_bytes + 100_000_000:
            raise HTTPException(503, "Source storage is nearly full.")
        try: key, limit = uploads.reserve(user, kind, name)
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
        complete = False
        try:
            path = uploads.path(key)
            with path.open("xb") as out:
                path.chmod(0o600)
                size = 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit: raise HTTPException(413, "This source file exceeds the upload limit.")
                    out.write(chunk)
            if not size: raise HTTPException(422, "The file is empty.")
            async with inspecting:
                row = await run_in_threadpool(uploads.finish, key)
            complete = True
            return public_upload(row)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, "The source could not be validated. " + str(exc)) from exc
        finally:
            if not complete: uploads.discard(key, user)

    @app.post("/api/diagnostics/uploads/{upload_id}/discard")
    def discard_upload(upload_id: str, user: str = Depends(owner)):
        try: uploads.discard(upload_id, user)
        except ValueError as exc: raise HTTPException(404, "Source not found.") from exc
        return {"removed_from_draft": True}

    def get_job(job_id, user):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise HTTPException(404, "Task not found.")
        row = store.get(job_id, user)
        if not row:
            raise HTTPException(404, "Task not found.")
        return row

    def manifest(job_id, user):
        row = get_job(job_id, user)
        if row["status"] == "expired":
            raise HTTPException(410, "These results have expired. Submit again to recompute.")
        if row["status"] not in ("succeeded", "partial"):
            raise HTTPException(409, "Results are not ready.")
        path = s.data / "jobs" / job_id / "results" / "result.json"
        if not path.is_file():
            raise HTTPException(503, "Result storage is unavailable.")
        return json.loads(path.read_text())

    @app.get("/api/diagnostics/capabilities")
    def capabilities(user: str = Depends(owner)):
        heartbeat = s.data / "worker-heartbeat"
        return {"analyst":user if user in s.keys else "Your workspace", "worker_online":heartbeat.exists() and time.time()-heartbeat.stat().st_mtime < 45,
                "sample_ready":(s.data / "sample-ready.json").exists(), "retention_days":s.retention_days,
                "max_area_km2":20000, "land_cover_max_area_km2":2000, "max_climate_requests":240,
                "uploads_enabled":True, "max_raster_bytes":100_000_000, "max_vector_bytes":5_000_000,
                "modules":[{"id":k,"title":v,"custom_enabled":k not in NASA_MODULES or nasa_ready(k),
                            "reason":None if k not in NASA_MODULES or nasa_ready(k) else f"Server {'GLDAS' if k == 'groundwater' else 'MODIS'} data access is awaiting authorization and verification."} for k,v in MODULES.items()]}

    @app.post("/api/diagnostics/jobs", status_code=202)
    def submit(payload: DiagnosticRequest, user: str = Depends(owner), idempotency_key: Annotated[str, Header()] = ""):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", idempotency_key):
            raise HTTPException(400, "A submission key is required.")
        unavailable = [m for m in payload.modules if m in NASA_MODULES and not nasa_ready(m)]
        if payload.mode == "custom" and unavailable:
            raise HTTPException(503, "Server data access must be authorized and verified for: " + ", ".join(MODULES[m] for m in unavailable) + ". The Ganjam reference inputs remain available.")
        if payload.mode == "ganjam" and not (s.data / "sample-ready.json").exists():
            raise HTTPException(503, "The Ganjam reference inputs are being prepared.")
        if shutil.disk_usage(s.data).free < s.min_free_bytes:
            raise HTTPException(503, "Result storage is nearly full.")
        try:
            uploads.pin(payload.model_dump(mode="json"), user, s.retention_days)
            return public_job(store.create(user, idempotency_key, payload.model_dump(mode="json"), s))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/diagnostics/jobs")
    def jobs(user: str = Depends(owner)):
        return [public_job(row) for row in store.list(user)]

    @app.get("/api/diagnostics/jobs/{job_id}")
    def job(job_id: str, user: str = Depends(owner)):
        return public_job(get_job(job_id, user))

    @app.post("/api/diagnostics/jobs/{job_id}/cancel")
    def cancel(job_id: str, user: str = Depends(owner)):
        get_job(job_id,user)
        return public_job(store.cancel(job_id,user))

    @app.get("/api/diagnostics/jobs/{job_id}/result")
    def result(job_id: str, user: str = Depends(owner)):
        return manifest(job_id,user)

    @app.get("/api/diagnostics/jobs/{job_id}/assets/{name}")
    def asset(job_id: str, name: str, user: str = Depends(owner)):
        m = manifest(job_id,user)
        entry = next((a for a in m["assets"] if a["file"] == name),None)
        if not entry or not re.fullmatch(r"[a-zA-Z0-9_.-]+",name) or ".." in name:
            raise HTTPException(404,"Result file not found.")
        root = (s.data / "jobs" / job_id / "results").resolve()
        p = (root / name).resolve()
        if p.parent != root or not p.is_file():
            raise HTTPException(404,"Result file not found.")
        return FileResponse(p,media_type=entry["media_type"],filename=name)

    app.state.diagnostics_store = store
