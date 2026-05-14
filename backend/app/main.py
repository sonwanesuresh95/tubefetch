import asyncio
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app import jobs
from app.schemas import (
    DownloadCreate,
    DownloadJobRead,
    JobStatus,
    VideoInfoRequest,
    VideoInfoResponse,
    FormatOption,
)
from app import ytdlp_service

logger = logging.getLogger(__name__)

_WIN_RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *{f"COM{i}" for i in range(1, 10)},
        *{f"LPT{i}" for i in range(1, 10)},
    }
)


_MEDIA_EXTENSIONS = (
    ".mp4",
    ".webm",
    ".mkv",
    ".m4a",
    ".opus",
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".mov",
    ".avi",
    ".3gp",
)


def _strip_known_trailing_extension(name: str) -> str:
    lower = name.lower()
    for suf in _MEDIA_EXTENSIONS:
        if lower.endswith(suf):
            return name[: -len(suf)].rstrip(" .")
    return name


def _safe_download_basename(title: str | None, job_id: str) -> str:
    raw = (title or "").strip()
    if not raw:
        raw = f"youtube-{job_id[:12]}"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", raw)
    cleaned = cleaned.strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > 180:
        cleaned = cleaned[:180].rstrip(" .")
    cleaned = _strip_known_trailing_extension(cleaned)
    if not cleaned:
        cleaned = "download"
    if cleaned.upper() in _WIN_RESERVED_STEMS:
        return f"{cleaned}_video"
    return cleaned


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings.database_path)
    yield


def _resolve_static_root() -> Path | None:
    raw = os.environ.get("YTDL_STATIC_DIR", "").strip()
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p
    default = Path(__file__).resolve().parent.parent / "static"
    return default if default.is_dir() else None


_STATIC_ROOT = _resolve_static_root()

app = FastAPI(
    title="YouTube Downloader",
    lifespan=lifespan,
    docs_url=None if _STATIC_ROOT else "/docs",
    redoc_url=None if _STATIC_ROOT else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _job_to_read(row: dict) -> DownloadJobRead:
    status = JobStatus(row["status"])
    download_url = None
    if status == JobStatus.completed and row.get("file_path"):
        download_url = f"/api/files/{row['id']}"
    return DownloadJobRead(
        id=row["id"],
        url=row["url"],
        title=row.get("title"),
        format_id=row["format_id"],
        status=status,
        file_path=row.get("file_path"),
        error_message=row.get("error_message"),
        created_at=_parse_dt(row["created_at"]) or datetime.now(),
        completed_at=_parse_dt(row.get("completed_at")),
        download_url=download_url,
    )


def _run_download_sync(job_id: str, url: str, format_id: str) -> None:
    try:
        jobs.update_job_status(job_id, status="processing")
        path = ytdlp_service.download_file(
            url,
            format_id,
            settings.downloads_dir,
            job_id,
        )
        jobs.update_job_status(job_id, status="completed", file_path=str(path))
    except Exception as exc:
        logger.exception("Download failed for job %s", job_id)
        jobs.update_job_status(job_id, status="failed", error_message=str(exc))


async def _run_download_task(job_id: str, url: str, format_id: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_download_sync, job_id, url, format_id)


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/info", response_model=VideoInfoResponse)
async def post_video_info(body: VideoInfoRequest):
    url = ytdlp_service.prepare_youtube_url(body.url.strip())
    if not ytdlp_service.is_allowed_youtube_url(url):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported.")
    try:
        data = await asyncio.to_thread(ytdlp_service.extract_video_info, url)
    except Exception as exc:
        logger.exception("extract_info failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return VideoInfoResponse(
        video_id=data["video_id"],
        title=data["title"],
        thumbnail=data.get("thumbnail"),
        duration_seconds=data.get("duration_seconds"),
        view_count=data.get("view_count"),
        uploader=data.get("uploader"),
        video_formats=[FormatOption(**f) for f in data["video_formats"]],
        audio_formats=[FormatOption(**f) for f in data["audio_formats"]],
    )


@app.post("/api/downloads", response_model=DownloadJobRead)
async def create_download(
    body: DownloadCreate,
    background_tasks: BackgroundTasks,
):
    url = ytdlp_service.prepare_youtube_url(body.url.strip())
    if not ytdlp_service.is_allowed_youtube_url(url):
        raise HTTPException(status_code=400, detail="Only YouTube URLs are supported.")

    job_id = str(uuid.uuid4())
    title = body.title
    if title is None:
        try:
            info = await asyncio.to_thread(ytdlp_service.extract_video_info, url)
            title = info.get("title")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    jobs.create_job(job_id, url, title, body.format_id.strip())
    background_tasks.add_task(_run_download_task, job_id, url, body.format_id.strip())

    row = jobs.get_job(job_id)
    if not row:
        raise HTTPException(status_code=500, detail="Could not create job.")
    return _job_to_read(row)


@app.get("/api/downloads/{job_id}", response_model=DownloadJobRead)
async def get_download(job_id: str):
    row = jobs.get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_to_read(row)


@app.get("/api/files/{job_id}")
async def serve_file(job_id: str):
    row = jobs.get_job(job_id)
    if not row or row.get("status") != "completed":
        raise HTTPException(status_code=404, detail="File not available.")
    path_str = row.get("file_path")
    if not path_str:
        raise HTTPException(status_code=404, detail="File not available.")
    path = Path(path_str)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk.")
    ext = path.suffix.lower() or ".bin"
    base = _safe_download_basename(row.get("title"), row["id"])
    download_name = f"{base}{ext}"
    return FileResponse(
        path,
        filename=download_name,
        media_type="application/octet-stream",
    )


if _STATIC_ROOT is not None:
    app.mount("/", StaticFiles(directory=str(_STATIC_ROOT), html=True), name="spa")
