from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import ChoreCheckInOut, ChoreHistoryOut, ChoreStatusOut
from app.services import chores as chores_service
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

router = APIRouter()


@router.get("", response_model=list[ChoreStatusOut], summary="Status tugas minggu ini (setrika, pakan hewan)")
def chores_status(db: Session = Depends(get_db), now: datetime = Depends(get_now), board: Scoreboard = Depends(get_board)):
    return chores_service.status(db, now)


@router.get("/history", response_model=list[ChoreHistoryOut], summary="Histori check-in tugas (disimpan 7 hari)")
def chores_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return chores_service.history(db, limit)


@router.post("/{task_key}/checkin", response_model=ChoreCheckInOut, status_code=201, summary="Upload foto tugas")
def chore_checkin(
    task_key: str,
    photo: UploadFile = File(..., description="Foto bukti tugas"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return chores_service.checkin(db, photo, task_key, now)
