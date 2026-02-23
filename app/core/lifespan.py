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

    # Индексы под воркер: быстрый поиск задач (pending/error) + сортировка по created_at
    await app.state.mongo_collection.create_index(
        [("locked_at", 1), ("created_at", 1)],
        name="idx_pending_by_lock_created",
        partialFilterExpression={"result": None},
    )

    await app.state.mongo_collection.create_index(
        [("locked_at", 1), ("created_at", 1)],
        name="idx_error_by_lock_created",
        partialFilterExpression={"result.status": "error"},
    )

    # Быстро находить запись по URL файла (иногда полезно для дебага/отчётов)
    await app.state.mongo_collection.create_index(
        [("publication_file_url", 1)],
        name="idx_publication_file_url",
    )

    yield

    app.state.mongo_client.close()
