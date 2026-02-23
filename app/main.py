from fastapi import FastAPI, HTTPException

from api.v1.routes.tilda_webhook import router as tilda_router
from core.lifespan import lifespan
from core.logging import setup_logging

setup_logging()

app = FastAPI(lifespan=lifespan)
app.include_router(tilda_router)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def ready():
    # проверка, что Mongo доступна
    try:
        await app.state.mongo_db.command("ping")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"mongo not ready: {e}")
    return {"status": "ok"}
