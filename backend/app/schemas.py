from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class VideoInfoRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)


class FormatOption(BaseModel):
    format_id: str
    ext: str
    label: str
    kind: str  # "video" | "audio"
    height: int | None = None
    abr: float | None = None
    filesize_approx: int | None = None
    vcodec: str | None = None
    acodec: str | None = None
    note: str | None = None


class VideoInfoResponse(BaseModel):
    video_id: str
    title: str
    thumbnail: str | None = None
    duration_seconds: int | None = None
    view_count: int | None = None
    uploader: str | None = None
    video_formats: list[FormatOption]
    audio_formats: list[FormatOption]


class DownloadCreate(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)
    format_id: str = Field(..., min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=500)


class DownloadJobRead(BaseModel):
    id: str
    url: str
    title: str | None
    format_id: str
    status: JobStatus
    file_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    download_url: str | None = None
