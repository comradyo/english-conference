from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from pymongo import MongoClient


OPTIONAL_PUBLICATION_PARTICIPATIONS = (
    "Выступление с презентацией без публикации",
    "Гость",
)
TARGET_REVIEW_STATUS = "На рассмотрении"


@dataclass(frozen=True)
class Settings:
    mongo_uri: str
    mongo_db: str
    registrations_collection: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=os.getenv("MONGO_DB", "eng_conference"),
            registrations_collection=os.getenv(
                "WEB_REGISTRATIONS_COLLECTION",
                "conference_registrations",
            ),
        )


def build_filter() -> dict[str, object]:
    return {
        "participation": {"$in": list(OPTIONAL_PUBLICATION_PARTICIPATIONS)},
        "review_status": {"$ne": TARGET_REVIEW_STATUS},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sets review_status='На рассмотрении' for applications that do not require a publication file."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print how many documents would be updated.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    client = MongoClient(settings.mongo_uri)
    try:
        collection = client[settings.mongo_db][settings.registrations_collection]
        filter_doc = build_filter()
        matched_count = collection.count_documents(filter_doc)

        print(f"Mongo DB: {settings.mongo_db}")
        print(f"Collection: {settings.registrations_collection}")
        print(f"Matched optional-publication applications: {matched_count}")

        if args.dry_run:
            print("Dry run only. No documents were modified.")
            return 0

        result = collection.update_many(
            filter_doc,
            {
                "$set": {
                    "review_status": TARGET_REVIEW_STATUS,
                }
            },
        )
        print(f"Modified documents: {result.modified_count}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
