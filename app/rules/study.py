"""Aturan belajar."""
from datetime import date, datetime

from app.rules.ruleset import RuleSet


def is_holiday(d: date, rs: RuleSet) -> bool:
    return d.weekday() in rs.study_holiday_weekdays


def required_seconds(wake_penalized: bool, rs: RuleSet) -> int:
    """Target belajar minimal hari itu: 40 menit, ditambah 20 menit bila bangun terlambat/gagal."""
    minutes = rs.study_min_minutes + (rs.wake_penalty_minutes if wake_penalized else 0)
    return minutes * 60


def session_seconds(started_at: datetime, ended_at: datetime) -> int:
    """Durasi satu sesi = selisih waktu upload foto 'mulai' dan foto 'setelah'."""
    return max(0, int((ended_at - started_at).total_seconds()))
