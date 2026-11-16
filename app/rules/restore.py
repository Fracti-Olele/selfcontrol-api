"""Kuota restorasi: belajar 5x/bulan (+ tabungan hari libur), bangun 3x/bulan."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.rules.clock import month_start
from app.rules.ruleset import RuleSet
from app.rules.streaks import DayView


@dataclass(frozen=True)
class Balance:
    quota: float      # jatah bulan ini
    used: int         # restorasi yang sudah dipakai bulan ini
    remaining: float  # sisa; satu restorasi butuh sisa >= 1


def holiday_credit_dates(days: Iterable[DayView], today: date) -> list:
    """Hari libur yang dipakai belajar sampai target hari itu tercapai -> +0.5 tabungan (sekali per hari)."""
    return [
        v.date
        for v in days
        if v.holiday and v.date < today and v.study_done_seconds >= v.study_required_seconds
    ]


def savings(credit_dates: Iterable[date], month: date, rs: RuleSet) -> float:
    """Tabungan yang berlaku di awal `month` (tanggal 1 bulan itu)."""
    dates = list(credit_dates)
    if rs.savings_mode == "monthly":
        previous = month_start(month - timedelta(days=1))
        count = sum(1 for d in dates if previous <= d < month)
    else:
        count = sum(1 for d in dates if d < month)
    return count * rs.holiday_study_saving


def balance(kind: str, month: date, credit_dates: Iterable[date], used: int, rs: RuleSet) -> Balance:
    if kind == "study":
        quota = rs.study_restores_per_month + savings(credit_dates, month, rs)
    elif kind == "wake":
        quota = float(rs.wake_restores_per_month)
    else:
        raise ValueError(f"kind tidak dikenal: {kind}")
    return Balance(quota, used, quota - used)
