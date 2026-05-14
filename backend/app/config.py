from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YTDL_", extra="ignore")

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    database_filename: str = "app.db"
    # Local dev + Render default host (*.onrender.com). Override with YTDL_CORS_ALLOW_ORIGIN_REGEX if needed.
    cors_allow_origin_regex: str = (
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://[\w.-]+\.onrender\.com$"
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_filename

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"


settings = Settings()
