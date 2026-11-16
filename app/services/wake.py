"""Check-in bangun tidur: satu foto kondisi kamar per hari."""
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WakeCheckIn
from app.rules import wake
from app.rules.clock import last_minute
from app.rules.ruleset import DEFAULT_RULES as RS
from app.schemas import WakeCheckInOut, WakeStatusOut
from app.services import photos, scoreboard, violations
from app.services.scoreboard import Scoreboard
from app.timeutils import TZ, to_local


def status(board: Scoreboard) -> WakeStatusOut:
    v = board.today_view
    return WakeStatusOut(
        local_date=v.date,
        state=v.wake_state,
        deadline_at=last_minute(wake.deadline(v.date, RS, TZ)),
        checked_in_at=v.wake_checkin_at,
        study_penalty_minutes=RS.wake_penalty_minutes if wake.penalized(v.wake_state) else 0,
        streak=scoreboard.streak_out(board.wake),
        restore=scoreboard.balance_out(board.balances["wake"]),
    )


def checkin(db: Session, upload: UploadFile, now: datetime, board: Scoreboard) -> WakeCheckInOut:
    today = board.today
    if db.scalar(select(WakeCheckIn.id).where(WakeCheckIn.local_date == today)) is not None:
        raise HTTPException(409, "Check-in bangun tidur hari ini sudah dilakukan.")

    data, ext = photos.read_photo(upload)
    limit = wake.deadline(today, RS, TZ)
    on_time = now < limit
    photo = photos.store_photo(db, data, ext, now, "wake")

    db.add(WakeCheckIn(local_date=today, uploaded_at=now, deadline_at=limit, on_time=on_time, photo_id=photo.id))
    scoreboard.get_day(db, today).wake_checkin_at = now
    if not on_time and today >= board.start:
        violations.add_once(
            db,
            category="wake",
            code="WAKE_LATE",
            local_date=today,
            occurred_at=limit,
            message=(
                f"Check-in bangun terlambat: {to_local(now):%H:%M} (batas {last_minute(limit):%H:%M}). "
                f"Target belajar hari ini +{RS.wake_penalty_minutes} menit."
            ),
            dedupe_key=f"wake_late:{today}",
        )
    db.commit()

    board = scoreboard.load(db, now)
    message = (
        "Check-in bangun tepat waktu."
        if on_time
        else f"Terlambat. Target belajar hari ini bertambah {RS.wake_penalty_minutes} menit."
    )
    return WakeCheckInOut(on_time=on_time, uploaded_at=now, message=message, status=status(board))
