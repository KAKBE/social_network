import os
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import settings
from app.db import Base, engine

Base.metadata.create_all(engine)

app = FastAPI(title="По Следу — рабочий образец")


@app.middleware("http")
async def server_timing(request: Request, call_next):
    """Exposes backend processing time so the client can split latency into network and server parts."""
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
    return response


app.include_router(router)

if os.path.isdir(settings.frontend_dist):
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
