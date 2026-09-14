# Multi-stage build: builder installs deps, runtime stays slim.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# System deps for building wheels (psycopg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install the package + runtime deps into a prefix we can copy over.
RUN pip install --prefix=/install --no-warn-script-location .

# ---- runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 wget \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 acp

COPY --from=builder /install /usr/local
COPY src/ /app/src/
COPY apps/ /app/apps/
COPY policies/ /app/policies/

WORKDIR /app
ENV PYTHONPATH=/app/src:/app/apps

USER acp
EXPOSE 8000

# Default command is overridden per-service in docker-compose.yml.
CMD ["uvicorn", "acp.api:app", "--host", "0.0.0.0", "--port", "8000"]
