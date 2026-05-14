import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL

_YOUTUBE_HOST = re.compile(
    r"^(https?://)?((www|m)\.)?(youtube\.com|youtu\.be)(/|$)",
    re.IGNORECASE,
)

_YOUTUBE_CANONICAL_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)


def prepare_youtube_url(raw: str) -> str:
    """Strip whitespace and drop playlist / radio / extra query params so a single video is resolved."""
    url = raw.strip()
    if not url:
        return url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_CANONICAL_HOSTS and not host.endswith(".youtube.com"):
        return url

    if host == "youtu.be" or host == "www.youtu.be":
        video_id = (parsed.path or "").strip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url

    path = (parsed.path or "").rstrip("/") or "/"
    if path == "/watch":
        params = parse_qs(parsed.query, keep_blank_values=False)
        values = params.get("v")
        if values and values[0]:
            return f"https://www.youtube.com/watch?v={values[0]}"
        return url
    if path.startswith("/embed/"):
        video_id = path.removeprefix("/embed/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url
    if path.startswith("/shorts/"):
        video_id = path.removeprefix("/shorts/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url
    if path.startswith("/live/"):
        video_id = path.removeprefix("/live/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return url

    return url


def is_allowed_youtube_url(url: str) -> bool:
    prepared = prepare_youtube_url(url)
    return bool(prepared and _YOUTUBE_HOST.match(prepared))


def _human_size(num: int | None) -> str | None:
    if num is None or num <= 0:
        return None
    size = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _format_entry(f: dict[str, Any]) -> dict[str, Any] | None:
    fid = f.get("format_id")
    if not fid:
        return None
    vcodec = f.get("vcodec") or "none"
    acodec = f.get("acodec") or "none"
    has_video = vcodec not in ("none", None)
    has_audio = acodec not in ("none", None)
    height = f.get("height")
    abr = f.get("abr") or f.get("tbr")
    ext = f.get("ext") or "unknown"
    filesize = f.get("filesize") or f.get("filesize_approx")

    if has_video and has_audio:
        kind = "video"
        res = f.get("resolution") or (f"{height}p" if height else "unknown")
        label = f"{res} · {ext.upper()}"
        if filesize:
            sz = _human_size(int(filesize))
            if sz:
                label += f" · ~{sz}"
    elif has_video and not has_audio:
        kind = "video"
        res = f.get("resolution") or (f"{height}p" if height else "unknown")
        label = f"{res} · {ext.upper()} · video only"
        if filesize:
            sz = _human_size(int(filesize))
            if sz:
                label += f" · ~{sz}"
    elif has_audio and not has_video:
        kind = "audio"
        abr_val = float(abr) if abr is not None else None
        br = f"{int(abr_val)} kbps" if abr_val else "audio"
        label = f"{br} · {ext.upper()}"
        if filesize:
            sz = _human_size(int(filesize))
            if sz:
                label += f" · ~{sz}"
    else:
        return None

    note_parts: list[str] = []
    if f.get("format_note"):
        note_parts.append(str(f["format_note"]))
    if has_video and not has_audio:
        note_parts.append("No audio in this file; player may be silent unless merged by yt-dlp.")
    note = " · ".join(note_parts) if note_parts else None

    return {
        "format_id": str(fid),
        "ext": str(ext),
        "label": label.strip(),
        "kind": kind,
        "height": int(height) if height else None,
        "abr": float(abr) if abr is not None else None,
        "filesize_approx": int(filesize) if filesize else None,
        "vcodec": None if vcodec == "none" else str(vcodec),
        "acodec": None if acodec == "none" else str(acodec),
        "note": note,
        "_sort_height": int(height) if height and kind == "video" else 0,
        "_sort_abr": float(abr) if abr is not None and kind == "audio" else 0.0,
    }


def extract_video_info(url: str) -> dict[str, Any]:
    url = prepare_youtube_url(url)
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "nocheckcertificate": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not isinstance(info, dict):
        msg = "Could not read video metadata."
        raise ValueError(msg)

    formats_raw = info.get("formats") or []
    parsed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for fr in formats_raw:
        entry = _format_entry(fr)
        if not entry:
            continue
        if entry["format_id"] in seen_ids:
            continue
        seen_ids.add(entry["format_id"])
        parsed.append(entry)

    video_formats = sorted(
        [p for p in parsed if p["kind"] == "video"],
        key=lambda x: (x["_sort_height"], x.get("filesize_approx") or 0),
        reverse=True,
    )
    audio_formats = sorted(
        [p for p in parsed if p["kind"] == "audio"],
        key=lambda x: (x["_sort_abr"], x.get("filesize_approx") or 0),
        reverse=True,
    )

    for p in video_formats + audio_formats:
        p.pop("_sort_height", None)
        p.pop("_sort_abr", None)

    duration = info.get("duration")
    raw_views = info.get("view_count")
    view_count: int | None = None
    if raw_views is not None:
        try:
            view_count = int(raw_views)
        except (TypeError, ValueError):
            view_count = None
    return {
        "video_id": str(info.get("id") or ""),
        "title": str(info.get("title") or "Untitled"),
        "thumbnail": info.get("thumbnail"),
        "duration_seconds": int(duration) if duration else None,
        "view_count": view_count,
        "uploader": info.get("uploader"),
        "video_formats": video_formats,
        "audio_formats": audio_formats,
    }


def download_file(url: str, format_id: str, output_dir: Path, basename: str) -> Path:
    url = prepare_youtube_url(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / f"{basename}.%(ext)s")
    opts: dict[str, Any] = {
        "format": format_id,
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "nocheckcertificate": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    if not isinstance(info, dict):
        msg = "Download failed."
        raise RuntimeError(msg)

    requested = info.get("requested_downloads")
    if isinstance(requested, list) and requested:
        path = requested[-1].get("filepath")
        if path:
            return Path(path)

    ext = info.get("ext")
    if ext:
        candidate = output_dir / f"{basename}.{ext}"
        if candidate.is_file():
            return candidate

    matches = sorted(output_dir.glob(f"{basename}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]

    msg = "Download finished but file path was not found."
    raise RuntimeError(msg)
