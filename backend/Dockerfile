# syntax=docker/dockerfile:1

########################
# Stage 1: builder
########################
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps for compiling wheels (psycopg2 etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels once so the runtime stage installs fast and stays slim.
RUN pip wheel --wheel-dir /wheels -r requirements.txt


########################
# Stage 2: runtime
########################
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MEDIA_ROOT=/app/media

WORKDIR /app

# Runtime system deps:
#   ffmpeg    - video/audio pipeline (Module 4 render)
#   libpq5    - psycopg2 runtime
#   ca-certs  - outbound HTTPS (Anthropic, Pexels, yt-dlp)
# yt-dlp itself is a Python package from requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Application code
COPY . .

# Non-root user; owns the app dir + media mount point
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p "$MEDIA_ROOT" \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
