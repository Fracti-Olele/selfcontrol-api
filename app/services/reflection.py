"""Refleksi harian (histori harian) + bintang agar tidak terhapus otomatis."""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reflection
from app.rules import reflection
from app.rules.clock import last_minute
from app.rules.ruleset import DEFAULT_RULES as RS
from app.schemas import HistoryDayOut, ReflectionIn, ReflectionOut, ReflectionStatusOut
from app.services import scoreboard
from app.services.scoreboard import Scoreboard
from app.timeutils import TZ


def status(db: Session, board: Scoreboard) -> ReflectionStatusOut:
    d = board.today
    window = reflection.window(d, RS, TZ)
    entry = db.get(Reflection, d)
    return ReflectionStatusOut(
        question=reflection.QUESTION,
        local_date=d,
        state=reflection.state(board.now, d, RS, TZ),
        opens_at=window.start,
        closes_at=last_minute(window.end),
        answered=entry is not None,
        entry=ReflectionOut.model_validate(entry) if entry is not None else None,
    )


def answer(db: Session, payload: ReflectionIn, now: datetime, board: Scoreboard) -> ReflectionOut:
    d = board.today
    window = reflection.window(d, RS, TZ)
    if now < window.start:
        raise HTTPException(409, f"Refleksi baru dibuka pukul {window.start:%H:%M}.")

    entry = db.get(Reflection, d)
    if entry is None:
        entry = Reflection(
            local_date=d, happy=payload.happy, text=payload.text, answered_at=now, updated_at=now, starred=False
        )
        db.add(entry)
    else:  # boleh merevisi jawaban selama jendela masih terbuka
        entry.happy, entry.text, entry.updated_at = payload.happy, payload.text, now
    scoreboard.get_day(db, d).reflection_done = True
    db.commit()
    db.refresh(entry)
    return ReflectionOut.model_validate(entry)


def history(db: Session, board: Scoreboard) -> list:
    """7 hari terakhir + semua hari yang refleksinya berbintang (hari lain sudah dihapus otomatis)."""
    cutoff = reflection.cutoff_date(board.today, RS)
    entries = {r.local_date: r for r in db.scalars(select(Reflection))}
    out = []
    for v in sorted((v for v in board.days if v.date >= board.start), key=lambda v: v.date, reverse=True):
        if v.date < cutoff and v.date not in entries:
            continue
        entry = entries.get(v.date)
        out.append(
            HistoryDayOut(
                local_date=v.date,
                wake=v.wake.value,
                study=v.study.value,
                reflection=v.reflection,
                main=v.main.value,
                studied_seconds=v.study_done_seconds,
                entry=ReflectionOut.model_validate(entry) if entry is not None else None,
            )
        )
    return out


def set_star(db: Session, d: date, starred: bool) -> ReflectionOut:
    entry = db.get(Reflection, d)
    if entry is None:
        raise HTTPException(404, "Tidak ada entri refleksi pada tanggal itu (mungkin sudah terhapus otomatis).")
    entry.starred = starred
    db.commit()
    return ReflectionOut.model_validate(entry)
