"""FastAPI entrypoint. Locally: `uv run uvicorn app.main:app --reload` (from backend/)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import funds, imports, portfolio, reference
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
app.include_router(funds.router)
app.include_router(reference.router)
app.include_router(imports.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "env": settings.app_env}
