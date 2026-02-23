import logging
import os


def setup_logging() -> None:
    """Configure logging

    Uvicorn обычно уже настраивает handlers. Мы выравниваем уровни логирования
    для root/uvicorn/*, а если handlers ещё нет — включаем basicConfig.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root.setLevel(level)
        for h in root.handlers:
            try:
                h.setLevel(level)
            except Exception:
                pass

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).setLevel(level)


def register_log_filter() -> None:
    """
    Removes logs from healthiness/readiness endpoints so they don't spam
    and pollute application log flow
    """

    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return (
                    record.args  # type: ignore
                    and len(record.args) >= 3
                    and record.args[2] not in ["/health", "/ready"]  # type: ignore
            )

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
