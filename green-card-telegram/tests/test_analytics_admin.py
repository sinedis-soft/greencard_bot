import os

from fastapi.testclient import TestClient

from app.main import app
from app.services.analytics_service import AnalyticsService


def test_event_created_and_bound_request_id():
    svc = AnalyticsService()
    svc.track("application_submitted", request_id="req-1", telegram_user_id=1, payload={"a": 1})
    events = svc.get_events("req-1")
    assert events
    assert events[-1].request_id == "req-1"


def test_admin_endpoint_requires_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret")
    client = TestClient(app)
    r = client.get("/api/admin/applications/req-1/events")
    assert r.status_code == 403


def test_admin_endpoint_with_token(monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret")
    client = TestClient(app)
    r = client.get("/api/admin/applications/req-1/events", headers={"x-admin-token": "secret"})
    assert r.status_code == 200
    assert "events" in r.json()
