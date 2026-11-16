"""Penilaian harian dan penghitungan streak (murni).

Streak TIDAK disimpan sebagai counter: ia dihitung ulang dari fakta harian + daftar restorasi,
sehingga memulihkan hari yang gagal otomatis memperbaiki hitungannya.
"""
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, tzinfo
from enum import StrEnum

from app.rules import study, wake
from app.rules.clock import ONE_DAY, local_date
from app.rules.ruleset import RuleSet


class Verdict(StrEnum):
    COUNTED = "counted"  # syarat terpenuhi -> streak +1
    BRIDGED = "bridged"  # gagal tetapi diselamatkan restorasi -> streak tidak putus, tidak bertambah
    NEUTRAL = "neutral"  # tidak dinilai (libur belajar) -> streak stagnan
    PENDING = "pending"  # hari ini, belum selesai
    MISSED = "missed"    # gagal -> streak putus (kecuali dipulihkan dalam jendela restorasi)


@dataclass(frozen=True)
class DayFacts:
    """Fakta mentah satu hari (disimpan permanen di tabel day_records)."""

    wake_checkin_at: datetime | None = None
    study_seconds: int = 0
    reflection_done: bool = False


@dataclass(frozen=True)
class DayView:
    date: date
    holiday: bool
    wake_state: str  # on_time | late | pending | overdue
    wake_checkin_at: datetime | None
    wake: Verdict
    study_required_seconds: int
    study_done_seconds: int
    study: Verdict
    reflection: str  # done | pending | missed
    main: Verdict


@dataclass(frozen=True)
class StreakView:
    current: int
    best: int
    restorable: tuple  # tanggal gagal yang masih bisa dipulihkan
    current_if_restored: int


def main_verdict(w: Verdict, s: Verdict, reflection: str) -> Verdict:
    """Streak utama: bangun tepat waktu + belajar memenuhi target + refleksi terjawab."""
    if w is Verdict.MISSED or s is Verdict.MISSED or reflection == "missed":
        return Verdict.MISSED
    if w is Verdict.PENDING or s is Verdict.PENDING or reflection == "pending":
        return Verdict.PENDING
    if w is Verdict.BRIDGED or s is Verdict.BRIDGED:
        return Verdict.BRIDGED
    return Verdict.COUNTED  # bangun COUNTED; belajar COUNTED atau NEUTRAL (libur); refleksi done


def evaluate_day(
    d: date,
    facts: DayFacts,
    now: datetime,
    restored_wake: bool,
    restored_study: bool,
    rs: RuleSet,
    tz: tzinfo,
) -> DayView:
    today = local_date(now, tz)

    w_state = wake.state(d, facts.wake_checkin_at, now, rs, tz)
    if w_state == "on_time":
        w = Verdict.COUNTED
    elif w_state == "pending":
        w = Verdict.PENDING
    else:
        w = Verdict.BRIDGED if restored_wake else Verdict.MISSED

    required = study.required_seconds(wake.penalized(w_state), rs)
    holiday = study.is_holiday(d, rs)
    if holiday:
        s = Verdict.NEUTRAL
    elif facts.study_seconds >= required:
        s = Verdict.COUNTED
    elif d >= today:
        s = Verdict.PENDING
    else:
        s = Verdict.BRIDGED if restored_study else Verdict.MISSED

    reflection = "done" if facts.reflection_done else ("pending" if d >= today else "missed")
    return DayView(
        d, holiday, w_state, facts.wake_checkin_at, w, required, facts.study_seconds, s, reflection,
        main_verdict(w, s, reflection),
    )


def evaluate_days(
    facts: Mapping[date, DayFacts],
    restored: Mapping[str, Collection[date]],
    first: date,
    now: datetime,
    rs: RuleSet,
    tz: tzinfo,
) -> list:
    """Nilai setiap hari dari `first` sampai hari ini."""
    today = local_date(now, tz)
    views, d = [], first
    while d <= today:
        views.append(
            evaluate_day(
                d,
                facts.get(d, DayFacts()),
                now,
                d in restored.get("wake", ()),
                d in restored.get("study", ()),
                rs,
                tz,
            )
        )
        d += ONE_DAY
    return views


# ---------------- streak ----------------
def _run(verdicts: Iterable[Verdict]) -> tuple:
    current = best = 0
    for v in verdicts:
        if v is Verdict.COUNTED:
            current += 1
            best = max(best, current)
        elif v is Verdict.MISSED:
            current = 0
    return current, best


def _bridge(v: Verdict, d: date, today: date, rs: RuleSet) -> Verdict:
    """Andaikan hari gagal yang masih dalam jendela restorasi dipulihkan."""
    return Verdict.BRIDGED if v is Verdict.MISSED and (today - d).days <= rs.restore_window_days else v


def _view(days: Sequence[DayView], actual: Sequence[Verdict], hypo: Sequence[Verdict], today: date, rs: RuleSet) -> StreakView:
    current, best = _run(actual)
    current_if_restored, _ = _run(hypo)
    restorable = tuple(
        v.date
        for v, a, h in zip(days, actual, hypo)
        if a is Verdict.MISSED and h is not Verdict.MISSED and (today - v.date).days <= rs.restore_window_days
    )
    return StreakView(current, best, restorable, current_if_restored)


def sub_streak(days: Sequence[DayView], kind: str, today: date, rs: RuleSet) -> StreakView:
    """Streak 'wake' atau 'study' dari hari-hari yang sudah dinilai (urut tanggal)."""
    actual = [getattr(v, kind) for v in days]
    hypo = [_bridge(a, v.date, today, rs) for a, v in zip(actual, days)]
    return _view(days, actual, hypo, today, rs)


def main_streak(days: Sequence[DayView], today: date, rs: RuleSet) -> StreakView:
    """Streak utama. Hanya bisa diselamatkan lewat restorasi bangun/belajar; refleksi yang terlewat tidak bisa dipulihkan."""
    actual = [v.main for v in days]
    hypo = [
        main_verdict(_bridge(v.wake, v.date, today, rs), _bridge(v.study, v.date, today, rs), v.reflection)
        for v in days
    ]
    return _view(days, actual, hypo, today, rs)
