import os
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    mongo_collection: str

    poll_interval_sec: float
    lock_timeout_sec: int
    max_attempts: int

    download_dir: Path
    worker_id: str

    yandex_aip_url: str
    yandex_api_token: str
    yandex_disk_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        yandex_api_token = os.getenv("YANDEX_API_TOKEN")
        if yandex_api_token is None:
            raise AttributeError("YANDEX_API_TOKEN is not set")
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            mongo_collection=os.getenv("MONGO_COLLECTION", "submissions"),

            poll_interval_sec=float(os.getenv("POLL_INTERVAL_SEC", "2")),
            lock_timeout_sec=int(os.getenv("LOCK_TIMEOUT_SEC", "300")),
            max_attempts=int(os.getenv("MAX_ATTEMPTS", "5")),

            download_dir=Path(os.getenv("DOWNLOAD_DIR", "/data/downloads")),
            worker_id=os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}"),

            yandex_aip_url=os.getenv("YANDEX_API_URL", "https://cloud-api.yandex.net/v1/disk/resources/download/"),
            yandex_api_token=yandex_api_token,
            yandex_disk_path=os.getenv("YANDEX_DISK_PATH", "Приложения/Tilda Publishing and Disk/English_test/")
        )
