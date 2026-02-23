from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    app.state.mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    app.state.mongo_db = app.state.mongo_client[settings.mongo_db]
    app.state.mongo_collection = app.state.mongo_db[settings.mongo_collection]

    # (опционально) индекс, чтобы выборка "pending" была быстрой
    # await app.state.mongo_collection.create_index([("file.status", 1), ("created_at", 1)])
    # await app.state.mongo_collection.create_index([("file.local_path", 1)])

    yield

    app.state.mongo_client.close()
