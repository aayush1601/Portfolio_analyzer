# Local/dev image for the FastAPI backend. Lambda container images come in Phase 14/15.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /repo/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/repo/backend/.venv/bin:$PATH"
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY config /repo/config
RUN useradd --create-home app && mkdir -p /repo/data && chown app /repo/data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
