# syntax=docker/dockerfile:1

# --- Étape 1 : interface compilée -------------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Étape 2 : dépendances Python (lockfile figé) ---------------------------------------------
FROM python:3.12-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Étape 3 : image d'exécution --------------------------------------------------------------
FROM python:3.12-slim
LABEL org.opencontainers.image.title="Finance" \
      org.opencontainers.image.description="Suivi de patrimoine auto-hébergé" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/fsa64320/finance"

# Utilisateur sans privilèges ; /data est le seul endroit où l'application écrit.
RUN groupadd --gid 10001 finance \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin finance \
 && mkdir /data \
 && chown finance:finance /data

WORKDIR /app/backend
COPY --from=backend /app/backend/.venv /app/backend/.venv
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/src ./src
COPY --from=frontend /build/dist /app/static

ENV PATH="/app/backend/.venv/bin:${PATH}" \
    PYTHONPATH="/app/backend/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FINANCE_DATA_DIR=/data \
    FINANCE_STATIC_DIR=/app/static \
    FINANCE_HOST=0.0.0.0 \
    FINANCE_PORT=8000 \
    XDG_CACHE_HOME=/tmp/cache

USER finance
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/auth/status', timeout=3)"]

# Un seul processus : la base chiffrée et les sessions vivent en mémoire de ce processus.
CMD ["python", "-m", "finance"]
