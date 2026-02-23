from fastapi import FastAPI

from core.lifespan import lifespan
from api.v1.routes.tilda_webhook import router as tilda_router

app = FastAPI(lifespan=lifespan)

app.include_router(tilda_router)
