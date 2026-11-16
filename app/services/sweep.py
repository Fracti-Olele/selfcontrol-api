"""Sapuan 'lazy', dijalankan di awal setiap request yang bergantung pada status.

Tanpa cron: semuanya dihitung dari jam sekarang. Hari yang terlewat (server mati / HP tidak menghubungi)
ikut disusul pada sapuan berikutnya, karena pelanggaran dihitung dari ketiadaan data, bukan dari kejadian.
"""
from datetime import datetime, time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.rules import wake
from app.rules.clock import ONE_DAY, at, last_minute
from app.rules.ruleset import DEFAULT_RULES as RS
from app.services import les as les_service
from app.services import meta, retention, scoreboard, violations
from app.services import study as study_service
from app.services.scoreboard import Scoreboard
from app.timeutils import TZ


def run(db: Session, now: datetime) -> Scoreboard:
    """Sapu lalu kembalikan papan skor terbaru."""
    try:
        board = _sweep(db, now)
        db.commit()
    except IntegrityError:  # request lain baru saja mencatat hal yang sama; ulangi sekali
        db.rollback()
        board = _sweep(db, now)
        db.commit()
    return board


def _sweep(db: Session, now: datetime) -> Scoreboard:
    board = scoreboard.load(db, now)  # sekaligus memastikan start_date tersimpan
    study_service.expire_stale(db, board.today)
    _close_days(db, board)
    les_service.mark_absences(db, now)
    retention.purge(db, now)
    return board


def _close_days(db: Session, board: Scoreboard) -> None:
    """Hari yang sudah berakhir: catat pelanggaran bangun (tidak check-in sama sekali) dan target belajar tak tercapai.
    Bangun TERLAMBAT dicatat saat fotonya diupload (lihat services/wake.py)."""
    yesterday = board.today - ONE_DAY
    last = meta.get_date(db, "last_close_date")
    first = max(board.start, last + ONE_DAY) if last is not None else board.start
    for v in board.days:
        if not (first <= v.date <= yesterday):
            continue
        if v.wake_state == "overdue":
            limit = wake.deadline(v.date, RS, TZ)
            violations.add_once(
                db,
                category="wake",
                code="WAKE_MISSED",
                local_date=v.date,
                occurred_at=limit,
                message=(
                    f"Tidak check-in bangun tidur sampai batas {last_minute(limit):%H:%M}. "
                    f"Target belajar hari itu +{RS.wake_penalty_minutes} menit."
                ),
                dedupe_key=f"wake_missed:{v.date}",
            )
        if not v.holiday and v.study_done_seconds < v.study_required_seconds:
            violations.add_once(
                db,
                category="study",
                code="STUDY_TARGET_MISSED",
                local_date=v.date,
                occurred_at=at(v.date + ONE_DAY, time(0, 0), TZ),
                message=f"Belajar {v.study_done_seconds // 60} dari {v.study_required_seconds // 60} menit.",
                dedupe_key=f"study_short:{v.date}",
            )
    meta.put_date(db, "last_close_date", yesterday)
