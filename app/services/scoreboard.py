"""Papan skor: muat fakta dari database -> nilai semua hari -> streak & kuota restorasi.
Semua logika penilaian ada di app/rules (murni); file ini hanya menyambungkannya ke database."""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DayRecord, Restoration
from app.rules import restore, wake
from app.rules.clock import local_date, month_start
from app.rules.restore import Balance
from app.rules.ruleset import DEFAULT_RULES as RS
from app.rules.streaks import DayFacts, DayView, StreakView, evaluate_days, main_streak, sub_streak
from app.schemas import BalanceOut, StreakOut
from app.services import meta
from app.timeutils import TZ

KINDS = ("wake", "study")


@dataclass
class Scoreboard:
    now: datetime
    today: date
    start: date          # hari pertama yang dinilai
    days: list           # DayView dari min(start, today) sampai hari ini
    wake: StreakView
    study: StreakView
    main: StreakView
    balances: dict       # {"wake": Balance, "study": Balance}

    @property
    def today_view(self) -> DayView:
        return self.days[-1]


def ensure_started(db: Session, now: datetime) -> date:
    start = meta.get_date(db, "start_date")
    if start is None:
        start = wake.initial_start_date(now, RS, TZ)
        meta.put_date(db, "start_date", start)
    return start


def get_day(db: Session, d: date) -> DayRecord:
    """Ambil (atau buat) catatan fakta harian untuk tanggal d."""
    rec = db.get(DayRecord, d)
    if rec is None:
        rec = DayRecord(local_date=d, study_seconds=0, reflection_done=False)
        db.add(rec)
    return rec


def load(db: Session, now: datetime) -> Scoreboard:
    today = local_date(now, TZ)
    start = ensure_started(db, now)
    first = min(start, today)

    records = db.scalars(select(DayRecord).where(DayRecord.local_date >= first))
    facts = {r.local_date: DayFacts(r.wake_checkin_at, r.study_seconds, r.reflection_done) for r in records}
    restorations = list(db.scalars(select(Restoration)))
    restored = {k: {r.target_date for r in restorations if r.kind == k} for k in KINDS}

    days = evaluate_days(facts, restored, first, now, RS, TZ)
    scored = [v for v in days if v.date >= start]

    month = month_start(today)
    credits = restore.holiday_credit_dates(scored, today)
    used = {
        k: sum(1 for r in restorations if r.kind == k and month_start(local_date(r.used_at, TZ)) == month)
        for k in KINDS
    }
    balances = {k: restore.balance(k, month, credits, used[k], RS) for k in KINDS}

    return Scoreboard(
        now=now,
        today=today,
        start=start,
        days=days,
        wake=sub_streak(scored, "wake", today, RS),
        study=sub_streak(scored, "study", today, RS),
        main=main_streak(scored, today, RS),
        balances=balances,
    )


def streak_out(sv: StreakView) -> StreakOut:
    return StreakOut(
        current=sv.current,
        best=sv.best,
        current_if_restored=sv.current_if_restored,
        restorable_dates=list(sv.restorable),
    )


def balance_out(b: Balance) -> BalanceOut:
    return BalanceOut(quota=b.quota, used=b.used, remaining=b.remaining)
