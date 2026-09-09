# Grounded backend — Render Web Service image.
# Builds the FastAPI application and runs it with uvicorn.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python requirements first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY app ./app

# Render Web Services run on $PORT (or default for local `docker run`).
EXPOSE 8000

# uvicorn binds to the incrementally-provided port.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}