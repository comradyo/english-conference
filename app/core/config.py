import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Auth
    api_key_name: str = "Authorization"
    api_key_value: str = ""

    # Mongo
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "tilda"
    mongo_collection: str = "submissions"

    # Downloads
    download_dir: Path = Path("./data/downloads")

    # HTTP
    http_timeout_total: int = 120

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key_name=os.getenv("TILDA_API_KEY_NAME", "Authorization"),
            api_key_value=os.getenv("TILDA_API_KEY_VALUE", ""),

            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "tilda"),
            mongo_collection=os.getenv("MONGO_COLLECTION", "submissions"),

            download_dir=Path(os.getenv("DOWNLOAD_DIR", "./data/downloads")),

            http_timeout_total=int(os.getenv("HTTP_TIMEOUT_TOTAL", "120")),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
