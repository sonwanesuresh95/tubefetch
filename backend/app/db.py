import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                format_id TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection():
    conn = _connect(settings.database_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
