import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import pytest

from online.api import create_app
from online.config import Settings
from online.models import rectangle
from online.store import Store
from online.worker import public_source_error


AUTH = {"Authorization": "Bearer " + "a" * 40, "Idempotency-Key": "diagnostic-submit-001"}
OTHER = {"Authorization": "Bearer " + "b" * 40}


def custom(modules=None):
    return dict(mode="custom", name="Bhubaneswar test", modules=modules or ["flood"],
        boundary=rectangle([85.75,20.15,85.95,20.35]),
        config=dict(schema="nbs-local-job/v1", name="Bhubaneswar test", modules=["flood"], boundarySha256="0"*64,
            groundwater=dict(baseline=[2003,2013],monitoring=[2014,2023]),
            drought=dict(reference=[2001,2023],minimumYears=15,compare=[2013,2023],seasons=[dict(name="Growing season",start=6,end=10)]),
            climate=dict(baseline=[1991,2020],future=[2041,2070],models=["ACCESS-CM2"],scenarios=["ssp245"],metrics=["hot","warm","frost","temperature","rain","dry"],thresholds=dict(hot=35,warm=25,rain=20,dry=1)),
            flood=dict(returnPeriods=[10,100,500]),landMask="all-land",maxDownloadGB=10))


@pytest.fixture
def service(tmp_path,monkeypatch):
    monkeypatch.delenv("NBS_EARTHDATA_VERIFIED",raising=False)
    monkeypatch.delenv("NBS_GLDAS_VERIFIED",raising=False)
    monkeypatch.delenv("NBS_MODIS_VERIFIED",raising=False)
    settings=Settings(data=tmp_path,keys={"alice":"a"*40,"bob":"b"*40},min_free_bytes=0)
    app=create_app(settings)
    (tmp_path/"diagnostics/sample-ready.json").write_text("{}")
    return TestClient(app),app.state.diagnostics_store,settings


def test_auth_queue_idempotency_isolation_and_cancel(service):
    c,s,_=service
    assert c.get("/api/diagnostics/jobs").status_code==401
    r=c.post("/api/diagnostics/jobs",json={},headers=AUTH)
    assert r.status_code==202,r.text
    job=r.json()["id"]
    assert c.post("/api/diagnostics/jobs",json={},headers=AUTH).json()["id"]==job
    assert c.post("/api/diagnostics/jobs",json={"modules":["flood"]},headers=AUTH).status_code==409
    assert c.get("/api/diagnostics/jobs",headers=OTHER).json()==[]
    for suffix in ("","/result","/assets/results.zip"):
        assert c.get(f"/api/diagnostics/jobs/{job}{suffix}",headers=OTHER).status_code==404
    assert c.post(f"/api/diagnostics/jobs/{job}/cancel",headers=OTHER).status_code==404
    assert c.post(f"/api/diagnostics/jobs/{job}/cancel",headers=AUTH).json()["status"]=="cancelled"
    assert s.claim() is None
    assert c.get("/api/jobs",headers=AUTH).json()==[]


def test_nasa_gate_does_not_block_public_sources(service,monkeypatch):
    c,_,_=service
    caps=c.get("/api/diagnostics/capabilities",headers=AUTH).json()
    assert sum(m["custom_enabled"] for m in caps["modules"])==5
    for module in ("groundwater","drought"):
        assert c.post("/api/diagnostics/jobs",json=custom([module]),headers=AUTH).status_code==503
    assert c.post("/api/diagnostics/jobs",json=custom(["lulc","fragmentation","flood","degradation","climate"]),headers=AUTH).status_code==202
    monkeypatch.setenv("NBS_EARTHDATA_VERIFIED","true")
    assert not next(m for m in c.get("/api/diagnostics/capabilities",headers=AUTH).json()["modules"] if m["id"]=="groundwater")["custom_enabled"]


def test_verified_modis_does_not_unlock_unverified_gldas(service,monkeypatch):
    c,_,_=service
    monkeypatch.setenv("NBS_NASA_USERNAME","test-account")
    monkeypatch.setenv("NBS_NASA_PASSWORD","test-fixture")
    monkeypatch.setenv("NBS_MODIS_VERIFIED","true")
    monkeypatch.setenv("NBS_GLDAS_VERIFIED","false")
    caps={m["id"]:m for m in c.get("/api/diagnostics/capabilities",headers=AUTH).json()["modules"]}
    assert caps["drought"]["custom_enabled"] is True
    assert caps["groundwater"]["custom_enabled"] is False
    assert c.post("/api/diagnostics/jobs",json=custom(["drought"]),headers=AUTH).status_code==202
    assert c.post("/api/diagnostics/jobs",json=custom(["drought","groundwater"]),headers=AUTH).status_code==503
    monkeypatch.setenv("NBS_GLDAS_VERIFIED","true")
    caps={m["id"]:m for m in c.get("/api/diagnostics/capabilities",headers=AUTH).json()["modules"]}
    assert caps["groundwater"]["custom_enabled"] is True
    assert c.post("/api/diagnostics/jobs",json=custom(["groundwater"]),headers={**AUTH,"Idempotency-Key":"verified-groundwater-001"}).status_code==202
    monkeypatch.delenv("NBS_NASA_PASSWORD")
    assert c.post("/api/diagnostics/jobs",json=custom(["drought"]),headers=AUTH).status_code==503


def test_geometry_climate_and_land_limits(service):
    c,_,_=service
    bad=[]
    req=custom(["lulc"]);req["boundary"]=rectangle([84,19,86,21]);bad.append(req)
    req=custom();req["boundary"]=rectangle([80,10,95,25]);bad.append(req)
    req=custom(["climate"]);req["config"]["climate"]["models"].append("MIROC6");bad.append(req)
    req=custom();req["config"]["maxDownloadGB"]=20;bad.append(req)
    req=custom(["fragmentation"]);req["land_cover"]={"resolution":100,"edge_width_m":50};bad.append(req)
    req=custom();req["boundary"]["features"][0]["geometry"]["coordinates"]=[[[0,0],[1,1],[0,1],[1,0],[0,0]]];bad.append(req)
    bad.extend([{"modules":["flood","flood"]},{"mode":"ganjam","boundary":rectangle([85,20,86,21])}])
    for request in bad:
        response=c.post("/api/diagnostics/jobs",json=request,headers=AUTH)
        assert response.status_code==422,response.text
    assert c.post("/api/diagnostics/jobs",json=custom(["lulc","fragmentation"]),headers=AUTH).status_code==202


def test_partial_results_allowlist_and_expiry(service):
    c,s,settings=service
    job=c.post("/api/diagnostics/jobs",json={},headers=AUTH).json()["id"]
    s.claim()
    out=settings.data/"diagnostics/jobs"/job/"results";out.mkdir(parents=True)
    (out/"result.json").write_text(json.dumps({"complete":False,"assets":[{"file":"statistics.csv","media_type":"text/csv"}]}))
    (out/"statistics.csv").write_text("module,mean\nflood,1\n")
    (out/"private-worker.log").write_text("private")
    s.finish(job,"partial")
    assert c.get(f"/api/diagnostics/jobs/{job}/result",headers=AUTH).json()["complete"] is False
    assert c.get(f"/api/diagnostics/jobs/{job}/assets/statistics.csv",headers=AUTH).status_code==200
    assert c.get(f"/api/diagnostics/jobs/{job}/assets/private-worker.log",headers=AUTH).status_code==404
    s.expire(time.time()+1)
    assert c.get(f"/api/diagnostics/jobs/{job}/result",headers=AUTH).status_code==410


def test_worker_waits_for_shared_compute_slot(tmp_path):
    settings=Settings(data=tmp_path,min_free_bytes=0)
    store=Store(tmp_path)
    job=store.create("alice","shared-slot-test",{},settings)
    lock_path=tmp_path/"shared-compute.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        env={**os.environ,"NBS_DATA_DIR":str(tmp_path),"NBS_COMPUTE_LOCK":str(lock_path),"NBS_ACCESS_KEYS":"{}"}
        process=subprocess.Popen([sys.executable,"-m","online.worker"],cwd=Path(__file__).resolve().parents[1],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            until=time.monotonic()+10
            while not (tmp_path/"worker-heartbeat").exists() and time.monotonic()<until:
                assert process.poll() is None
                time.sleep(.05)
            assert (tmp_path/"worker-heartbeat").exists()
            assert store.get(job["id"])["status"]=="queued"
            assert store.cancel(job["id"],"alice")["status"]=="cancelled"
        finally:
            process.terminate();process.wait(timeout=5)
        assert process.returncode==0


def test_provider_error_details_are_never_published(tmp_path):
    path=tmp_path/"source-error.json"
    assert public_source_error(tmp_path) is None
    path.write_text(json.dumps({"code":"unknown", "message":"private-signed-url"}))
    assert public_source_error(tmp_path) is None
    path.write_text(json.dumps({"code":"modis_download_budget", "message":"private-signed-url"}))
    message=public_source_error(tmp_path)
    assert "15 reference years" in message
    assert "private-signed-url" not in message
    path.write_text(json.dumps({"code":"gldas_download_budget", "message":"private-signed-url"}))
    message=public_source_error(tmp_path)
    assert "GLDAS regional" in message
    assert "private-signed-url" not in message
