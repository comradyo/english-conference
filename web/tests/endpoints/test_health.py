from __future__ import annotations


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_unavailable(client, monkeypatch):
    async def _fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(client.app.state.mongo_db, "command", _fail)

    response = client.get("/ready")
    assert response.status_code == 503
    assert "mongo not ready" in response.json().get("detail", "")

