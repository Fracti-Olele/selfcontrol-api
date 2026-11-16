"""Semua waktu disimpan sebagai UTC; jadwal dan "hari" dihitung memakai zona waktu lokal (TIMEZONE)."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings

TZ = ZoneInfo(settings.timezone)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_now() -> datetime:
    """Dependency FastAPI. Sengaja dipisah supaya waktu bisa dipalsukan saat testing."""
    return now_utc()


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(TZ)


def local_today(now: datetime) -> date:
    return to_local(now).date()

