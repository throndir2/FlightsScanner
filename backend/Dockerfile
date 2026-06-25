# FlightsScanner backend image — serves the FastAPI API and runs Celery worker/beat
# (same image, different commands; see docker-compose.yml).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# Run as a non-root user (security hardening — see docs/auth-and-security.md §6).
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command runs the API; compose overrides this for worker/beat.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
