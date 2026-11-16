"""Check-in foto tugas mingguan (tanpa streak): setrika dan refill makanan hewan."""
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChoreCheckIn
from app.rules import chores as chore_rules
from app.rules.chores import CHORES
from app.rules.clock import DAY_NAMES, last_minute, local_date, week_start
from app.schemas import ChoreCheckInOut, ChoreStatusOut
from app.services import photos
from app.timeutils import TZ


def status(db: Session, now: datetime) -> list:
    today = local_date(now, TZ)
    rows = db.scalars(select(ChoreCheckIn).where(ChoreCheckIn.week_start == week_start(today)))
    done = {c.task_key: c for c in rows}
    out = []
    for rule in CHORES.values():
        window = chore_rules.window(rule, today, TZ)
        check = done.get(rule.key)
        out.append(
            ChoreStatusOut(
                key=rule.key,
                label=rule.label,
                state=chore_rules.state(rule, today, now, check is not None, TZ),
                window_start=window.start,
                window_end=last_minute(window.end),
                done_at=check.uploaded_at if check is not None else None,
            )
        )
    return out


def checkin(db: Session, upload: UploadFile, key: str, now: datetime) -> ChoreCheckInOut:
    rule = CHORES.get(key)
    if rule is None:
        raise HTTPException(404, "Tugas tidak dikenal. Pilihan: " + ", ".join(CHORES))
    today = local_date(now, TZ)
    window = chore_rules.window(rule, today, TZ)
    if now < window.start:
        raise HTTPException(409, f"{rule.label} baru bisa di-check-in mulai {DAY_NAMES[rule.opens_weekday]} 00:00.")
    if now >= window.end:
        raise HTTPException(409, f"Jendela check-in {rule.label} pekan ini sudah ditutup.")
    ws = week_start(today)
    if db.scalar(select(ChoreCheckIn.id).where(ChoreCheckIn.task_key == key, ChoreCheckIn.week_start == ws)) is not None:
        raise HTTPException(409, f"{rule.label} pekan ini sudah di-check-in.")

    data, ext = photos.read_photo(upload)
    photo = photos.store_photo(db, data, ext, now, "chores")
    db.add(ChoreCheckIn(task_key=key, week_start=ws, uploaded_at=now, photo_id=photo.id))
    db.commit()
    return ChoreCheckInOut(key=key, week_start=ws, uploaded_at=now, message=f"{rule.label}: check-in tersimpan.")


def history(db: Session, limit: int) -> list:
    return list(db.scalars(select(ChoreCheckIn).order_by(ChoreCheckIn.uploaded_at.desc()).limit(limit)))
