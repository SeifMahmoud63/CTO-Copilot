# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install minimal runtime system dependencies (curl for container healthcheck)
# Clean apt caches and lists immediately to avoid bloating the layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install python dependencies with BuildKit pip cache mount:
# - Reuses downloaded wheels across builds from host cache (drastically speeding up rebuilds)
# - Cache directory is never saved into the final image layer (zero bloat in production)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && rm -rf /tmp/* /var/tmp/*

# Copy only runtime code, web UI, Alembic migrations, and bucket init script
COPY app/ ./app/
COPY web/ ./web/
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/
COPY scripts/ensure_buckets.py ./scripts/ensure_buckets.py

# Expose default port
EXPOSE 8000

# Start FastAPI server serving both API and Web UI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

