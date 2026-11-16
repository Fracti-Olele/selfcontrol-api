"""Aturan refleksi harian & retensi histori."""
from datetime import date, datetime, time, timedelta, tzinfo

from app.rules.clock import Window, at, until
from app.rules.ruleset import RuleSet

QUESTION = "Apakah kamu senang dengan hari ini, apakah ada yang perlu dicurahkan?"


def window(d: date, rs: RuleSet, tz: tzinfo) -> Window:
    """Input aktif pukul 12.00 sampai 23.59 (akhir hari)."""
    return Window(at(d, rs.reflection_opens, tz), until(d, time(23, 59), tz))


def state(now: datetime, d: date, rs: RuleSet, tz: tzinfo) -> str:
    """not_open | open | closed"""
    w = window(d, rs, tz)
    if now < w.start:
        return "not_open"
    return "open" if now < w.end else "closed"


def cutoff_date(today: date, rs: RuleSet) -> date:
    """Histori harian yang tanggalnya lebih lama dari ini (dan tidak berbintang) dihapus otomatis."""
    return today - timedelta(days=rs.history_days)
