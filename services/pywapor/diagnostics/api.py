from dataclasses import replace
import json
import re
import shutil
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.responses import FileResponse

from online.store import Store, Conflict, QueueFull, public_job
from .models import DiagnosticRequest, MODULES, NASA_MODULES, nasa_ready


def install(app, settings, owner):
    s = replace(settings, data=settings.data / "diagnostics")
    s.data.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(s.data)

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
            return public_job(store.create(user, idempotency_key, payload.model_dump(mode="json"), s))
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
