# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Prevents Python from writing .pyc files and buffers stdout (better logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user up front
RUN useradd -m appuser

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code, then explicitly hand ownership to appuser.
# (Using a separate RUN chown instead of `COPY --chown=...` because that
# flag can silently be a no-op on some Docker/BuildKit setups.)
COPY main.py .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Basic container-level health check hitting our /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
