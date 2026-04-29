from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPOSITORY_ROOT / "web"

for import_path in (REPOSITORY_ROOT, WEB_DIR):
    import_path_value = str(import_path)
    if import_path_value not in sys.path:
        sys.path.insert(0, import_path_value)

import web.main as main
from web.tests.fixtures import DummyMongoDb, FakeCollection, make_test_settings


@asynccontextmanager
async def _no_lifespan(_app):
    yield


def _configure_test_state(app):
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
def app():
    return _configure_test_state(main.app)


@pytest.fixture
def state(app):
    return app.state


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
