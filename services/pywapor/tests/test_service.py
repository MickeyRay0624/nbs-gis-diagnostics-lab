from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from online.api import create_app
from online.config import Settings
from online.models import JobRequest, rectangle
from online.store import Store
from online.worker import stop_process


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "sample").mkdir()
    (tmp_path / "sample" / "ready.json").write_text("{}")
    settings = Settings(data=tmp_path, keys={"alice": "a" * 40, "bob": "b" * 40}, min_free_bytes=0)
    app = create_app(settings)
    return TestClient(app), app.state.store, settings


def headers(user="alice", key="submission-key-001"):
    return {"Authorization": "Bearer " + ("a" if user == "alice" else "b") * 40, "Idempotency-Key": key}


def test_auth_isolation_and_cors(setup):
    client, store, settings = setup
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/capabilities", headers={"Authorization": "Bearer wrong"}).status_code == 401
    response = client.post("/api/jobs", json={}, headers=headers())
    assert response.status_code == 202, response.text
    key = response.json()["id"]
    assert client.get(f"/api/jobs/{key}", headers=headers("bob")).status_code == 404
    assert client.post(f"/api/jobs/{key}/cancel", headers=headers("bob")).status_code == 404
    assert client.get("/api/jobs", headers=headers("bob")).json() == []
    assert client.options("/api/jobs", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"}).status_code == 400


def test_idempotency_quota_and_concurrent_claim(setup):
    client, store, settings = setup
    one = client.post("/api/jobs", json={}, headers=headers()).json()
    assert client.post("/api/jobs", json={}, headers=headers()).json()["id"] == one["id"]
    assert client.post("/api/jobs", json={"name": "Different"}, headers=headers()).status_code == 409
    assert client.post("/api/jobs", json={}, headers=headers(key="submission-key-002")).status_code == 202
    assert client.post("/api/jobs", json={}, headers=headers(key="submission-key-003")).status_code == 429
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: store.claim(), range(4)))
    ids = [row["id"] for row in claimed if row]
    assert len(ids) == len(set(ids)) == 2


def test_cancellation_and_restart_are_durable(setup):
    client, store, settings = setup
    queued = client.post("/api/jobs", json={}, headers=headers()).json()
    assert client.post(f"/api/jobs/{queued['id']}/cancel", headers=headers()).json()["status"] == "cancelled"
    assert store.claim() is None
    running = client.post("/api/jobs", json={}, headers=headers(key="submission-key-002")).json()
    store.claim()
    client.post(f"/api/jobs/{running['id']}/cancel", headers=headers())
    store.finish(running["id"], "succeeded")
    assert store.get(running["id"])["status"] == "cancelled"
    interrupted = client.post("/api/jobs", json={}, headers=headers(key="submission-key-003")).json()
    store.claim()
    new_store = Store(settings.data)
    new_store.recover()
    assert new_store.get(interrupted["id"])["status"] == "failed"
    assert "restarted" in new_store.get(interrupted["id"])["error"]


def test_geometry_dates_and_request_size(setup):
    client, store, settings = setup
    for values in ({"bbox": [31, 28, 31.2, 29.1]}, {"start": "2021-07-02"}, {"unknown": True}, {"name": "\n"}):
        assert client.post("/api/jobs", json=values, headers=headers()).status_code == 422
    custom = {"mode": "custom", "bbox": [85.75, 20.15, 85.95, 20.35]}
    assert client.post("/api/jobs", json=custom, headers=headers()).status_code == 503
    for values in ({**custom, "end": "2022-07-31"}, {**custom, "bbox": [80, 20, 90, 30]}, {**custom, "bbox": [170, 10, -170, 11]}, {**custom, "boundary": rectangle([85, 20, 86, 21])}):
        assert client.post("/api/jobs", json=values, headers=headers()).status_code == 422
    invalid = rectangle(custom["bbox"])
    invalid["features"][0]["geometry"]["coordinates"] = [[[85.75,20.15], [85.95,20.35], [85.75,20.35], [85.95,20.15], [85.75,20.15]]]
    assert client.post("/api/jobs", json={**custom, "boundary": invalid}, headers=headers()).status_code == 422
    assert client.post("/api/jobs", content=b"x" * 220_001, headers=headers()).status_code == 413


def test_result_allowlist_checks_ownership_and_expiry(setup):
    client, store, settings = setup
    job = client.post("/api/jobs", json={}, headers=headers()).json()
    key = job["id"]
    assert client.get(f"/api/jobs/{key}/result", headers=headers()).status_code == 409
    store.claim()
    folder = settings.data / "jobs" / key / "results"
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(json.dumps({"assets": [{"file": "allowed.csv", "media_type": "text/csv"}]}))
    (folder / "allowed.csv").write_text("date,et\n2021-07-01,1\n")
    (folder / "private-worker.log").write_text("do not serve")
    store.finish(key, "succeeded")
    assert client.get(f"/api/jobs/{key}/assets/allowed.csv", headers=headers()).status_code == 200
    assert client.get(f"/api/jobs/{key}/assets/allowed.csv", headers=headers("bob")).status_code == 404
    assert client.get(f"/api/jobs/{key}/assets/private-worker.log", headers=headers()).status_code == 404
    store.expire(time.time() + 1)
    assert client.get(f"/api/jobs/{key}/result", headers=headers()).status_code == 410


def test_fail_closed_configuration(tmp_path):
    with pytest.raises(ValueError):
        create_app(Settings(data=tmp_path, keys={}))
    with pytest.raises(ValueError):
        create_app(Settings(data=tmp_path, keys={"a": "x" * 40, "b": "x" * 40}))


def test_access_code_rotation_preserves_analyst_tasks(setup):
    client, store, settings = setup
    job = client.post("/api/jobs", json={}, headers=headers()).json()
    chosen_code = "demo-phrase!"
    with pytest.raises(ValueError):
        create_app(Settings(data=settings.data, keys={"alice": chosen_code}))
    replacement = Settings(data=settings.data, keys={"alice": chosen_code}, min_access_code_length=12, min_free_bytes=0)
    rotated = TestClient(create_app(replacement))
    assert rotated.get("/api/jobs", headers=headers()).status_code == 401
    response = rotated.get("/api/jobs", headers={"Authorization": "Bearer " + chosen_code})
    assert response.status_code == 200
    assert response.json()[0]["id"] == job["id"]
    assert rotated.get("/api/jobs", headers={"Authorization": "Bearer " + chosen_code[:-1]}).status_code == 401
    with pytest.raises(ValueError):
        create_app(Settings(data=settings.data, keys={"alice": chosen_code}, min_access_code_length=11))


def test_worker_terminates_job_process_group():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    stop_process(process)
    assert process.poll() is not None
    stop_process(process)  # Completion/cancellation races may call stop twice.
