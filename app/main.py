from fastapi import FastAPI

from api.v1.routes.tilda_webhook import router as tilda_router
from core.lifespan import lifespan
from core.logging import setup_logging

setup_logging()

app = FastAPI(lifespan=lifespan)
app.include_router(tilda_router)
