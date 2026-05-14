from datetime import UTC, datetime
from typing import Any

from app.db import get_connection


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def create_job(job_id: str, url: str, title: str | None, format_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO download_jobs (id, url, title, format_id, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (job_id, url, title, format_id, _now_iso()),
        )


def update_job_status(
    job_id: str,
    *,
    status: str,
    file_path: str | None = None,
    error_message: str | None = None,
) -> None:
    with get_connection() as conn:
        if status in ("completed", "failed"):
            conn.execute(
                """
                UPDATE download_jobs
                SET status = ?, file_path = ?, error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, file_path, error_message, _now_iso(), job_id),
            )
            return
        conn.execute(
            """
            UPDATE download_jobs
            SET status = ?, file_path = ?, error_message = ?
            WHERE id = ?
            """,
            (status, file_path, error_message, job_id),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM download_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)
