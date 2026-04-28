from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@dataclass
class InsertOneResult:
    inserted_id: Any


@dataclass
class UpdateResult:
    matched_count: int


@dataclass
class DeleteResult:
    deleted_count: int


class FakeCollection:
    def __init__(self, *, unique_fields: Iterable[str] | None = None):
        self._docs: list[dict[str, Any]] = []
        self._unique_fields = set(unique_fields or [])

    @property
    def docs(self) -> list[dict[str, Any]]:
        return self._docs

    class _Cursor:
        def __init__(self, docs: list[dict[str, Any]], query: dict[str, Any], projection, matcher):
            self._docs = docs
            self._query = query
            self._projection = projection
            self._matcher = matcher
            self._sort_key = None
            self._sort_dir = 1

        def sort(self, key: str, direction: int):
            self._sort_key = key
            self._sort_dir = direction
            return self

        async def to_list(self, length: int | None = None):
            items = [doc for doc in self._docs if self._matcher(doc, self._query)]
            if self._sort_key:
                reverse = self._sort_dir < 0
                items.sort(key=lambda item: item.get(self._sort_key), reverse=reverse)
            if length is not None:
                items = items[:length]
            if self._projection:
                return [
                    FakeCollection._apply_projection_static(item, self._projection)
                    for item in items
                ]
            return [dict(item) for item in items]

    @staticmethod
    def _apply_projection_static(doc: dict[str, Any], projection: dict[str, int]):
        if all(value == 0 for value in projection.values()):
            return {key: value for key, value in doc.items() if key not in projection}
        return {key: value for key, value in doc.items() if projection.get(key) == 1}

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, value in query.items():
            if isinstance(value, dict):
                if "$gt" in value:
                    candidate = doc.get(key)
                    if candidate is None or candidate <= value["$gt"]:
                        return False
                    continue
            if doc.get(key) != value:
                return False
        return True

    def _apply_projection(self, doc: dict[str, Any], projection: dict[str, int] | None) -> dict[str, Any]:
        if not projection:
            return dict(doc)
        if all(value == 0 for value in projection.values()):
            return {key: value for key, value in doc.items() if key not in projection}
        return {key: value for key, value in doc.items() if projection.get(key) == 1}

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        return FakeCollection._Cursor(self._docs, query, projection, self._matches)

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        for doc in self._docs:
            if self._matches(doc, query):
                return self._apply_projection(doc, projection)
        return None

    async def insert_one(self, doc: dict[str, Any]):
        for field in self._unique_fields:
            if field in doc and any(existing.get(field) == doc[field] for existing in self._docs):
                raise DuplicateKeyError(f"duplicate key: {field}")
        stored = dict(doc)
        stored.setdefault("_id", ObjectId())
        self._docs.append(stored)
        return InsertOneResult(stored["_id"])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False):
        for doc in self._docs:
            if not self._matches(doc, query):
                continue
            if "$set" in update:
                doc.update(update["$set"])
            return UpdateResult(matched_count=1)
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            new_doc.setdefault("_id", ObjectId())
            self._docs.append(new_doc)
            return UpdateResult(matched_count=1)
        return UpdateResult(matched_count=0)

    async def delete_one(self, query: dict[str, Any]):
        for index, doc in enumerate(self._docs):
            if self._matches(doc, query):
                del self._docs[index]
                return DeleteResult(deleted_count=1)
        return DeleteResult(deleted_count=0)

    async def delete_many(self, query: dict[str, Any]):
        remaining = []
        deleted = 0
        for doc in self._docs:
            if self._matches(doc, query):
                deleted += 1
                continue
            remaining.append(doc)
        self._docs = remaining
        return DeleteResult(deleted_count=deleted)


class DummyMongoDb:
    async def command(self, *_args, **_kwargs):
        return {"ok": 1}


def make_test_settings():
    from config import Settings

    return Settings(
        mongo_uri="mongodb://test",
        mongo_db="test_db",
        users_collection="users",
        registrations_collection="registrations",
        maintenance_collection="maintenance",
        email_tasks_collection="email_tasks",
        password_reset_tokens_collection="password_reset_tokens",
        sessions_collection="sessions",
        session_cookie_name="test_session",
        session_ttl_hours=1,
        password_reset_ttl_minutes=30,
        checker_api_url="http://checker",
        checker_api_timeout_sec=5,
        admin_emails=frozenset(),
    )
