from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import RestoreIn, RestoreOut, ViolationOut, WakeCheckInOut, WakeStatusOut
from app.services import restore as restore_service
from app.services import violations
from app.services import wake as wake_service
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

router = APIRouter()


@router.get("/status", response_model=WakeStatusOut, summary="Status bangun hari ini + streak bangun")
def wake_status(board: Scoreboard = Depends(get_board)):
    return wake_service.status(board)


@router.post("/checkin", response_model=WakeCheckInOut, status_code=201, summary="Upload foto kondisi kamar saat bangun")
def wake_checkin(
    photo: UploadFile = File(..., description="Foto kondisi kamar (JPEG/PNG/WebP)"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return wake_service.checkin(db, photo, now, board)


@router.post("/restore", response_model=RestoreOut, summary="Pakai restorasi untuk menyelamatkan streak bangun")
def wake_restore(
    payload: RestoreIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return restore_service.use(db, "wake", payload.target_date, now, board)


@router.get("/violations", response_model=list[ViolationOut], summary="Log pelanggaran bangun tidur")
def wake_violations(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return violations.recent(db, "wake", limit)
