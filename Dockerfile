# API image (specs/021). Portable: Render, Fly.io, Cloud Run, or any container host.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock CLAUDE.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY config ./config
COPY api ./api
COPY pipeline ./pipeline
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

# Migrations are idempotent, so running them on start keeps a single-instance deploy simple.
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
