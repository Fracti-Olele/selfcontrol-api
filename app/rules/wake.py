"""Aturan bangun tidur."""
from datetime import date, datetime, timedelta, tzinfo

from app.rules.clock import local_date, until
from app.rules.ruleset import RuleSet


def deadline(d: date, rs: RuleSet, tz: tzinfo) -> datetime:
    """Batas eksklusif check-in bangun untuk tanggal lokal d: 07.00 hari biasa, 09.00 Sabtu & Minggu."""
    limit = rs.wake_deadline_weekend if d.weekday() in rs.weekend_weekdays else rs.wake_deadline_weekday
    return until(d, limit, tz)


def is_on_time(ts: datetime, rs: RuleSet, tz: tzinfo) -> bool:
    return ts < deadline(local_date(ts, tz), rs, tz)


def state(d: date, checkin_at: datetime | None, now: datetime, rs: RuleSet, tz: tzinfo) -> str:
    """on_time | late | pending (belum check-in, batas belum lewat) | overdue (belum check-in, batas sudah lewat)."""
    limit = deadline(d, rs, tz)
    if checkin_at is not None:
        return "on_time" if checkin_at < limit else "late"
    return "pending" if now < limit else "overdue"


def penalized(wake_state: str) -> bool:
    """Terlambat atau gagal -> target belajar hari itu bertambah."""
    return wake_state in ("late", "overdue")


def initial_start_date(now: datetime, rs: RuleSet, tz: tzinfo) -> date:
    """Hari pertama yang dinilai: hari ini bila batas bangunnya belum lewat; jika sudah lewat, mulai besok."""
    today = local_date(now, tz)
    return today if now < deadline(today, rs, tz) else today + timedelta(days=1)
