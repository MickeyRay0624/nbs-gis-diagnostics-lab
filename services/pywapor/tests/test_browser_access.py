import sqlite3

from fastapi.testclient import TestClient
import pytest

from online.api import create_app
from online.config import Settings
from online.sessions import COOKIE


@pytest.fixture
def service(tmp_path):
    settings=Settings(data=tmp_path,public_access=True,keys={"owner":"a"*40},origins=["https://platform.example"],min_free_bytes=0)
    app=create_app(settings)
    (tmp_path/"sample").mkdir()
    (tmp_path/"sample/ready.json").write_text("{}")
    (tmp_path/"diagnostics/sample-ready.json").write_text("{}")
    return app,settings


def client(app):
    return TestClient(app,base_url="https://platform.example")


def test_browser_workspaces_need_no_code_and_isolate_both_queues(service):
    app,settings=service
    first,second=client(app),client(app)
    assert first.get("/api/jobs").status_code==401
    response=first.post("/api/session",json={})
    assert response.status_code==200 and response.json()=={"ready":True}
    cookie=response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie and "Path=/api" in cookie
    assert first.get("/api/capabilities").json()["analyst"]=="Your workspace"
    assert second.post("/api/session",json={}).status_code==200
    for prefix in ["/api","/api/diagnostics"]:
        created=first.post(prefix+"/jobs",json={},headers={"Idempotency-Key":"browser-submit-001"})
        assert created.status_code==202,created.text
        job=created.json()["id"]
        assert first.get(prefix+"/jobs").json()[0]["id"]==job
        assert second.get(prefix+"/jobs").json()==[]
        for suffix in ["","/result","/assets/results.zip"]:
            assert second.get(prefix+f"/jobs/{job}"+suffix).status_code==404
        assert second.post(prefix+f"/jobs/{job}/cancel").status_code==404
        assert first.post(prefix+f"/jobs/{job}/cancel").json()["status"]=="cancelled"
    forged=client(app)
    forged.cookies.set(COOKIE,"a"*64)
    assert forged.get("/api/jobs").status_code==401


def test_valid_previous_code_restores_history_and_cookie_survives_restart(service):
    app,settings=service
    previous=client(app)
    auth={"Authorization":"Bearer "+"a"*40,"Idempotency-Key":"previous-submit-001"}
    job=previous.post("/api/jobs",json={},headers=auth).json()["id"]
    assert previous.post("/api/session",json={},headers=auth).status_code==200
    assert previous.get("/api/jobs").json()[0]["id"]==job
    new_client=client(create_app(settings))
    new_client.cookies.update(previous.cookies)
    assert new_client.post("/api/session",json={}).status_code==200
    assert new_client.get("/api/jobs").json()[0]["id"]==job
    stranger=client(app)
    assert stranger.post("/api/session",json={},headers={"Authorization":"Bearer wrong"}).status_code==200
    assert stranger.get("/api/jobs").json()==[]
    with sqlite3.connect(settings.data/"browser-sessions.sqlite3") as db:
        db.execute("UPDATE sessions SET expires=0")
    assert new_client.get("/api/jobs").status_code==401
    assert new_client.post("/api/session",json={}).status_code==200
    assert new_client.get("/api/jobs").json()==[]


def test_cross_site_writes_are_blocked_and_queue_limits_still_apply(service):
    app,_=service
    c=client(app)
    assert c.post("/api/session",json={},headers={"Origin":"https://untrusted.example"}).status_code==403
    assert c.post("/api/session",data={}).status_code==415
    assert c.post("/api/session",json={},headers={"Origin":"https://platform.example"}).status_code==200
    for i,expected in enumerate([202,202,429]):
        assert c.post("/api/jobs",json={},headers={"Idempotency-Key":f"public-quota-test-{i}"}).status_code==expected
    assert c.post("/api/jobs",json={},headers={"Origin":"https://untrusted.example","Idempotency-Key":"cross-site-submit"}).status_code==403
    preflight=c.options("/api/jobs",headers={"Origin":"https://platform.example","Access-Control-Request-Method":"POST"})
    assert preflight.headers["access-control-allow-credentials"]=="true"


def test_public_mode_does_not_need_configured_access_codes(tmp_path):
    app=create_app(Settings(data=tmp_path,public_access=True,keys={}))
    assert client(app).post("/api/session",json={}).status_code==200
    protected=create_app(Settings(data=tmp_path,public_access=False,keys={"owner":"a"*40}))
    assert client(protected).post("/api/session",json={}).status_code==403
