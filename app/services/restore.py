"""Memakai restorasi untuk menyelamatkan satu hari yang gagal (streak bangun atau belajar)."""
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Restoration
from app.schemas import RestoreOut
from app.services import scoreboard
from app.services.scoreboard import Scoreboard

_LABEL = {"wake": "bangun tidur", "study": "belajar"}


def use(db: Session, kind: str, target: date, now: datetime, board: Scoreboard) -> RestoreOut:
    streak = board.wake if kind == "wake" else board.study
    if target not in streak.restorable:
        raise HTTPException(
            409,
            "Tanggal itu tidak bisa dipulihkan: hari itu tidak gagal, sudah dipulihkan, "
            "atau sudah lewat batas (sampai akhir hari berikutnya).",
        )
    if board.balances[kind].remaining < 1:
        raise HTTPException(409, f"Jatah restorasi {_LABEL[kind]} bulan ini sudah habis.")

    db.add(Restoration(kind=kind, target_date=target, used_at=now))
    db.commit()

    board = scoreboard.load(db, now)  # hitung ulang setelah restorasi
    updated = board.wake if kind == "wake" else board.study
    return RestoreOut(
        kind=kind,
        target_date=target,
        streak=scoreboard.streak_out(updated),
        balance=scoreboard.balance_out(board.balances[kind]),
    )
