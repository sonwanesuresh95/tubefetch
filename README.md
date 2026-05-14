# TubeFetch (YouTube downloader)

FastAPI + yt-dlp backend and a Vite React frontend. One Docker image serves the API and the built SPA.t`

## Run with Docker

From this directory (`youtube_downloader/`):

```bash
docker build -t tubefetch .
docker run --rm -p 8080:8080 -e PORT=8080 tubefetch
```

Open `http://localhost:8080`. Health check: `http://localhost:8080/api/health`.

## Run locally (without Docker)

Terminal 1 — API: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

Terminal 2 — UI: `cd frontend && npm install && npm run dev` (proxies `/api` to port 8000).

## ffmpeg

The Docker image installs **ffmpeg** for merged video+audio. Install ffmpeg on the host if you run the API without Docker.
