# --- Frontend (Vite + React) ---
FROM node:20-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- API + static SPA ---
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY --from=frontend /build/dist /app/static

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV YTDL_STATIC_DIR=/app/static

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
