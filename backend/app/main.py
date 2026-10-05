"""FastAPI entrypoint. Locally: `uv run uvicorn app.main:app --reload` (from backend/)."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.api import backtests, funds, imports, portfolio, reference
from app.config import get_settings
from app.utils.log import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

app = FastAPI(title="Portfolio Intelligence API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(portfolio.router)


@app.middleware("http")
async def fresh_data(request: Request, call_next):
    """On AWS, mirror the latest S3 data into /tmp before serving (at most every 5 minutes per container)."""
    if settings.storage == "s3":
        from app.aws.storage import sync_down

        await run_in_threadpool(sync_down)
    return await call_next(request)


app.include_router(funds.router)
app.include_router(reference.router)
app.include_router(imports.router)
app.include_router(backtests.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.app_env}
