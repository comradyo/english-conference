from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

from fixtures import DummyMongoDb, FakeCollection, make_test_settings

WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

import web.main as main


@asynccontextmanager
async def _no_lifespan(_app):
    yield


@pytest.fixture
def app():
    app = main.app
    app.router.lifespan_context = _no_lifespan
    app.state.settings = make_test_settings()
    app.state.mongo_db = DummyMongoDb()
    app.state.users_collection = FakeCollection(unique_fields={"email"})
    app.state.registrations_collection = FakeCollection()
    app.state.maintenance_collection = FakeCollection()
    app.state.email_tasks_collection = FakeCollection()
    app.state.password_reset_tokens_collection = FakeCollection(unique_fields={"token"})
    app.state.sessions_collection = FakeCollection(unique_fields={"token"})
    return app


@pytest.fixture
def state(app):
    return app.state


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
