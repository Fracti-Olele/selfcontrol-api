"""Pengaturan aplikasi, dibaca dari environment variable atau file .env."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "default-key"
    timezone: str = "Asia/Jakarta"
    database_url: str = "sqlite:///./selfcontrol.db"
    upload_dir: Path = Path("uploads")
    max_upload_mb: int = 8
    reject_duplicate_photos: bool = True


settings = Settings()
