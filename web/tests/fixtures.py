from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def run_async(coro):
    return asyncio.run(coro)


@dataclass
class InsertOneResult:
    inserted_id: Any


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int = 0


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

        def batch_size(self, _size: int):
            return self

        def __aiter__(self):
            self._iter_items = iter(self._matching_items())
            return self

        async def __anext__(self):
            try:
                return FakeCollection._apply_projection_static(next(self._iter_items), self._projection or {})
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        def _matching_items(self) -> list[dict[str, Any]]:
            items = [doc for doc in self._docs if self._matcher(doc, self._query)]
            if self._sort_key:
                reverse = self._sort_dir < 0
                items.sort(key=lambda item: FakeCollection._get_value(item, self._sort_key), reverse=reverse)
            return items

        async def to_list(self, length: int | None = None):
            items = self._matching_items()
            if length is not None:
                items = items[:length]
            return [FakeCollection._apply_projection_static(item, self._projection) for item in items]

    class _AggregateCursor:
        def __init__(self, items: list[dict[str, Any]]):
            self._items = items

        async def to_list(self, length: int | None = None):
            if length is None:
                return [dict(item) for item in self._items]
            return [dict(item) for item in self._items[:length]]

    @staticmethod
    def _get_value(doc: dict[str, Any], dotted_key: str):
        value: Any = doc
        for key in dotted_key.split("."):
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    @staticmethod
    def _set_value(doc: dict[str, Any], dotted_key: str, value: Any) -> None:
        target = doc
        parts = dotted_key.split(".")
        for key in parts[:-1]:
            next_target = target.setdefault(key, {})
            if not isinstance(next_target, dict):
                next_target = {}
                target[key] = next_target
            target = next_target
        target[parts[-1]] = value

    @staticmethod
    def _unset_value(doc: dict[str, Any], dotted_key: str) -> None:
        target = doc
        parts = dotted_key.split(".")
        for key in parts[:-1]:
            value = target.get(key)
            if not isinstance(value, dict):
                return
            target = value
        target.pop(parts[-1], None)

    @staticmethod
    def _apply_projection_static(doc: dict[str, Any], projection: dict[str, int]):
        if not projection:
            return deepcopy(doc)
        result = deepcopy(doc)
        if all(value == 0 for value in projection.values()):
            for key in projection:
                FakeCollection._unset_value(result, key)
            return result

        result = {}
        for key, include in projection.items():
            if not include:
                continue
            value = FakeCollection._get_value(doc, key)
            if value is not None:
                FakeCollection._set_value(result, key, deepcopy(value))
        return result

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, value in query.items():
            candidate = self._get_value(doc, key)
            if isinstance(value, dict):
                for operator, expected in value.items():
                    if operator == "$exists":
                        exists = candidate is not None
                        if exists != bool(expected):
                            return False
                    elif operator == "$gt":
                        if candidate is None or candidate <= expected:
                            return False
                    elif operator == "$gte":
                        if candidate is None or candidate < expected:
                            return False
                    elif operator == "$lt":
                        if candidate is None or candidate >= expected:
                            return False
                    elif operator == "$lte":
                        if candidate is None or candidate > expected:
                            return False
                    elif operator == "$ne":
                        if candidate == expected:
                            return False
                    else:
                        return False
                continue
            if candidate != value:
                return False
        return True

    def _apply_projection(self, doc: dict[str, Any], projection: dict[str, int] | None) -> dict[str, Any]:
        return self._apply_projection_static(doc, projection or {})

    def find(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        return FakeCollection._Cursor(self._docs, query, projection, self._matches)

    async def find_one(self, query: dict[str, Any], projection: dict[str, int] | None = None):
        for doc in self._docs:
            if self._matches(doc, query):
                return self._apply_projection(doc, projection)
        return None

    async def insert_one(self, doc: dict[str, Any]):
        for field in self._unique_fields:
            value = self._get_value(doc, field)
            if value is not None and any(self._get_value(existing, field) == value for existing in self._docs):
                raise DuplicateKeyError(f"duplicate key: {field}")
        stored = deepcopy(doc)
        stored.setdefault("_id", ObjectId())
        self._docs.append(stored)
        return InsertOneResult(stored["_id"])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False):
        for doc in self._docs:
            if not self._matches(doc, query):
                continue
            self._apply_update(doc, update)
            return UpdateResult(matched_count=1, modified_count=1)
        if upsert:
            new_doc = {k: deepcopy(v) for k, v in query.items() if not isinstance(v, dict)}
            self._apply_update(new_doc, update, is_insert=True)
            new_doc.setdefault("_id", ObjectId())
            self._docs.append(new_doc)
            return UpdateResult(matched_count=1, modified_count=1)
        return UpdateResult(matched_count=0, modified_count=0)

    async def update_many(self, query: dict[str, Any], update: dict[str, Any]):
        matched_count = 0
        for doc in self._docs:
            if not self._matches(doc, query):
                continue
            matched_count += 1
            self._apply_update(doc, update)
        return UpdateResult(matched_count=matched_count, modified_count=matched_count)

    def _apply_update(self, doc: dict[str, Any], update: dict[str, Any], is_insert: bool = False) -> None:
        for key, value in update.get("$set", {}).items():
            self._set_value(doc, key, deepcopy(value))
        for key in update.get("$unset", {}):
            self._unset_value(doc, key)
        for key, value in update.get("$push", {}).items():
            items = self._get_value(doc, key)
            if not isinstance(items, list):
                items = []
                self._set_value(doc, key, items)
            items.append(deepcopy(value))
        if is_insert:
            for key, value in update.get("$setOnInsert", {}).items():
                self._set_value(doc, key, deepcopy(value))

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

    async def count_documents(self, query: dict[str, Any]):
        return sum(1 for doc in self._docs if self._matches(doc, query))

    def aggregate(self, pipeline: list[dict[str, Any]]):
        items = [deepcopy(doc) for doc in self._docs]
        for stage in pipeline:
            if "$group" not in stage:
                continue
            group_spec = stage["$group"]
            group_key = str(group_spec.get("_id", ""))
            if not group_key.startswith("$"):
                continue
            source_field = group_key[1:]
            grouped: dict[Any, dict[str, Any]] = {}
            for item in items:
                key = self._get_value(item, source_field)
                grouped.setdefault(key, {"_id": key, "count": 0})
                grouped[key]["count"] += 1
            items = list(grouped.values())
        return FakeCollection._AggregateCursor(items)


class DummyMongoDb:
    async def command(self, *_args, **_kwargs):
        return {"ok": 1}


def make_test_settings():
    from web.config import Settings

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
