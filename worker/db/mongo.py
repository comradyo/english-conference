from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

from core.config import Settings
from utils.serializers import bson_safe


class MongoRepo:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncIOMotorClient(settings.mongo_uri)
        self.col = self.client[settings.mongo_db][settings.mongo_collection]

    async def ensure_indexes(self) -> None:
        await self.col.create_index(
            [("locked_at", 1), ("created_at", 1)],
            name="idx_pending_by_lock_created",
            partialFilterExpression={"result": None},
        )

        await self.col.create_index(
            [("locked_at", 1), ("created_at", 1)],
            name="idx_error_by_lock_created",
            partialFilterExpression={"result.status": "error"},
        )

        await self.col.create_index(
            [("publication_file_url", 1)],
            name="idx_publication_file_url",
        )

    async def close(self) -> None:
        self.client.close()

    async def acquire_job(self) -> Optional[Dict[str, Any]]:
        now_dt = datetime.now(timezone.utc)
        lock_expired_before = now_dt - timedelta(seconds=self.settings.lock_timeout_sec)

        return await self.col.find_one_and_update(
            filter={
                "$and": [
                    {
                        "$or": [
                            {"result": None},
                            {"result.status": "error"},  # <-- повторяем только ошибки
                        ]
                    },
                    {
                        "$or": [
                            {"locked_at": None},
                            {"locked_at": {"$lt": lock_expired_before}},
                        ]
                    },
                    {"publication_file_url": {"$type": "string"}},
                ]
            },
            update={
                "$set": {
                    "locked_at": now_dt,
                    "lock_owner": self.settings.worker_id,
                    "updated_at": now_dt,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    async def mark_done(
            self,
            doc_id,
            result_value: Any,
            file_local_path: Optional[str] = None,
    ) -> None:
        now_dt = datetime.now(timezone.utc)
        update: Dict[str, Any] = {
            "$set": {
                "result": bson_safe(result_value),
                "processed_at": now_dt,
                "updated_at": now_dt,
            },
            "$unset": {
                "locked_at": "",
                "lock_owner": "",
                "last_error": "",
            },
        }
        if file_local_path is not None:
            update["$set"]["file_local_path"] = file_local_path

        await self.col.update_one(
            {"_id": doc_id, "lock_owner": self.settings.worker_id},
            update,
        )

    async def mark_failed(self, doc: Dict[str, Any], error_text: str) -> None:
        """
        Требуемое поведение:
        - result становится "ошибочным" (status=error)
        - повторная попытка будет только после LOCK_TIMEOUT_SEC:
          оставляем locked_at=datetime.now() и снимаем lock_owner
        """
        now_dt = datetime.now(timezone.utc)
        attempts = int(doc.get("attempts") or 0)

        if attempts >= self.settings.max_attempts:
            # Финальная неудача (как и было раньше) — дальше не ретраим автоматически
            await self.col.update_one(
                {"_id": doc["_id"], "lock_owner": self.settings.worker_id},
                {
                    "$set": {
                        "result": {"status": "failed", "error": error_text, "attempts": attempts, "at": now_dt},
                        "failed_at": now_dt,
                        "updated_at": now_dt,
                        "last_error": error_text,
                    },
                    "$unset": {"locked_at": "", "lock_owner": ""},
                },
            )
        else:
            # Ошибка с cooldown: result=error и locked_at=now_dt (datetime!)
            await self.col.update_one(
                {"_id": doc["_id"], "lock_owner": self.settings.worker_id},
                {
                    "$set": {
                        "result": {"status": "error", "error": error_text, "attempts": attempts, "at": now_dt},
                        "last_error": error_text,
                        "updated_at": now_dt,
                        "locked_at": now_dt,  # <-- ключевой момент: удерживаем lock для cooldown
                    },
                    "$unset": {"lock_owner": ""},  # <-- освобождаем "владение", но lock по времени остаётся
                },
            )
