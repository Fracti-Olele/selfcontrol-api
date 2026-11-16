"""Ringkasan satu panggilan untuk app Android (GET /status)."""
from datetime import datetime, time

from sqlalchemy.orm import Session

from app.rules.clock import at
from app.schemas import StatusOut, ViolationOut
from app.services import chores, les, reflection, streaks, study, violations, wake
from app.services import usage as usage_service
from app.services.scoreboard import Scoreboard
from app.timeutils import TZ


def build(db: Session, now: datetime, board: Scoreboard) -> StatusOut:
    midnight = at(board.today, time(0, 0), TZ)
    return StatusOut(
        server_time=now,
        local_date=board.today,
        wake=wake.status(board),
        study=study.status(db, board),
        reflection=reflection.status(db, board),
        main=streaks.main_status(board),
        chores=chores.status(db, now),
        les_today=les.today(db, now),
        violations_today=[ViolationOut.model_validate(v) for v in violations.since(db, midnight)],
        blocked_packages=usage_service.blocked_packages(db, board.today),
    )
