# syntax=docker/dockerfile:1.7
# Production image for the FastAPI backend.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /app/var/uploads && chown -R app:app /app/var
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini pyproject.toml ./
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"
# Migrations run explicitly (see docker-compose `migrate` service / deployment docs).
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "2"]

# Development image: includes dev tools and reloads on change.
FROM builder AS dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen
CMD ["fastapi", "dev", "--host", "0.0.0.0", "--port", "8000"]
