from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    client = AsyncIOMotorClient(settings.mongo_uri)
    database = client[settings.mongo_db]

    app.state.settings = settings
    app.state.mongo_client = client
    app.state.mongo_db = database
    app.state.users_collection = database[settings.users_collection]
    app.state.registrations_collection = database[settings.registrations_collection]
    app.state.email_tasks_collection = database[settings.email_tasks_collection]
    app.state.password_reset_tokens_collection = database[settings.password_reset_tokens_collection]
    app.state.sessions_collection = database[settings.sessions_collection]

    await app.state.users_collection.create_index("email", unique=True, name="uq_web_user_email")
    await app.state.sessions_collection.create_index("token", unique=True, name="uq_web_session_token")
    await app.state.sessions_collection.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="ttl_web_sessions",
    )
    await app.state.registrations_collection.create_index(
        [("owner_user_id", 1), ("created_at", -1)],
        name="idx_owner_registrations",
    )
    await app.state.registrations_collection.create_index(
        [("email", 1), ("created_at", -1)],
        name="idx_registration_email",
    )
    await app.state.email_tasks_collection.create_index(
        [("status", 1), ("available_at", 1), ("created_at", 1)],
        name="idx_email_tasks_status_available",
    )
    await app.state.password_reset_tokens_collection.create_index(
        "token",
        unique=True,
        name="uq_password_reset_token",
    )
    await app.state.password_reset_tokens_collection.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="ttl_password_reset_tokens",
    )
    await app.state.password_reset_tokens_collection.create_index(
        [("user_id", 1), ("created_at", -1)],
        name="idx_password_reset_tokens_user",
    )

    yield

    client.close()
