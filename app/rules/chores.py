"""Tugas mingguan tanpa streak: setrika & refill makanan hewan."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from app.rules.clock import Window, at, until, week_start
from app.rules.ruleset import RuleSet


@dataclass(frozen=True)
class ChoreRule:
    key: str
    label: str
    opens_weekday: int   # jendela dibuka pukul 00.00 pada hari ini (Senin = 0)
    closes_weekday: int  # jendela ditutup pukul 23.59 pada hari ini


CHORES = {
    r.key: r
    for r in (
        ChoreRule("setrika", "Setrika", opens_weekday=4, closes_weekday=6),               # Jumat 00.00 - Minggu 23.59
        ChoreRule("pakan_hewan", "Refill makanan hewan", opens_weekday=2, closes_weekday=6),  # Rabu 00.00 - Minggu 23.59
    )
}


def window(rule: ChoreRule, d: date, tz: tzinfo) -> Window:
    """Jendela check-in pada pekan (Senin-Minggu) yang memuat tanggal d."""
    monday = week_start(d)
    start = at(monday + timedelta(days=rule.opens_weekday), time(0, 0), tz)
    end = until(monday + timedelta(days=rule.closes_weekday), time(23, 59), tz)
    return Window(start, end)


def state(rule: ChoreRule, d: date, now: datetime, done: bool, tz: tzinfo) -> str:
    """done | not_open | open | missed"""
    if done:
        return "done"
    w = window(rule, d, tz)
    if now < w.start:
        return "not_open"
    return "open" if now < w.end else "missed"


def photo_cutoff(now: datetime, rs: RuleSet) -> datetime:
    """Check-in foto yang lebih lama dari ini dihapus otomatis (baris + file)."""
    return now - timedelta(days=rs.history_days)
