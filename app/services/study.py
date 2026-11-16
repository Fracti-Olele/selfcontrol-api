"""Sesi belajar: foto 'mulai' lalu foto 'setelah'. Durasi semua sesi pada hari yang sama dijumlahkan."""
from datetime import date, datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudySession
from app.rules import study as study_rules
from app.schemas import StudyActionOut, StudySessionOut, StudyStatusOut
from app.services import photos, scoreboard
from app.services.scoreboard import Scoreboard


def _open_session(db: Session) -> StudySession | None:
    stmt = select(StudySession).where(StudySession.status == "open").order_by(StudySession.started_at.desc())
    return db.scalar(stmt)


def expire_stale(db: Session, today: date) -> None:
    """Sesi yang foto 'setelah'-nya tidak diupload sampai tengah malam kedaluwarsa dan TIDAK dihitung."""
    stale = db.scalars(select(StudySession).where(StudySession.status == "open", StudySession.local_date < today))
    for s in stale:
        s.status = "expired"


def status(db: Session, board: Scoreboard) -> StudyStatusOut:
    v = board.today_view
    done, required = v.study_done_seconds, v.study_required_seconds
    open_session = _open_session(db)
    return StudyStatusOut(
        local_date=v.date,
        is_holiday=v.holiday,
        required_seconds=required,
        studied_seconds=done,
        remaining_seconds=max(0, required - done),
        target_met=done >= required,
        holiday_credit_earned=v.holiday and done >= required,
        open_session=StudySessionOut.model_validate(open_session) if open_session is not None else None,
        streak=scoreboard.streak_out(board.study),
        restore=scoreboard.balance_out(board.balances["study"]),
    )


def start(db: Session, upload: UploadFile, now: datetime, board: Scoreboard) -> StudyActionOut:
    if _open_session(db) is not None:
        raise HTTPException(409, "Sesi belajar masih berjalan. Upload foto 'setelah belajar' dulu.")
    data, ext = photos.read_photo(upload)
    photo = photos.store_photo(db, data, ext, now, "study")
    session = StudySession(
        local_date=board.today,
        started_at=now,
        start_photo_id=photo.id,
        duration_seconds=0,
        status="open",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return StudyActionOut(
        session=StudySessionOut.model_validate(session),
        message="Sesi belajar dimulai. Upload foto 'setelah belajar' sebelum pukul 23:59 agar durasinya terhitung.",
        status=status(db, scoreboard.load(db, now)),
    )


def end(db: Session, upload: UploadFile, now: datetime) -> StudyActionOut:
    session = _open_session(db)
    if session is None:
        raise HTTPException(409, "Tidak ada sesi belajar yang berjalan. Upload foto 'mulai belajar' dulu.")
    data, ext = photos.read_photo(upload)
    photo = photos.store_photo(db, data, ext, now, "study")

    seconds = study_rules.session_seconds(session.started_at, now)
    session.ended_at = now
    session.end_photo_id = photo.id
    session.duration_seconds = seconds
    session.status = "completed"
    scoreboard.get_day(db, session.local_date).study_seconds += seconds
    db.commit()
    db.refresh(session)

    st = status(db, scoreboard.load(db, now))
    if st.target_met:
        message = "Target belajar hari ini tercapai."
        if st.is_holiday:
            message += " Hari libur: +0.5 tabungan restorasi."
    else:
        message = (
            f"Baru {st.studied_seconds // 60} dari {st.required_seconds // 60} menit. "
            "Kamu bisa mulai sesi lagi hari ini sampai total durasinya mencapai target."
        )
    return StudyActionOut(session=StudySessionOut.model_validate(session), message=message, status=st)


def sessions(db: Session, local_date: date | None, limit: int) -> list:
    stmt = select(StudySession).order_by(StudySession.started_at.desc()).limit(limit)
    if local_date is not None:
        stmt = stmt.where(StudySession.local_date == local_date)
    return list(db.scalars(stmt))
