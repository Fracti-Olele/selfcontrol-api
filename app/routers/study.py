from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import RestoreIn, RestoreOut, StudyActionOut, StudySessionOut, StudyStatusOut, ViolationOut
from app.services import restore as restore_service
from app.services import study as study_service
from app.services import violations
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

router = APIRouter()


@router.get("/status", response_model=StudyStatusOut, summary="Progres belajar hari ini + streak belajar")
def study_status(db: Session = Depends(get_db), board: Scoreboard = Depends(get_board)):
    return study_service.status(db, board)


@router.post("/start", response_model=StudyActionOut, status_code=201, summary="Upload foto MULAI belajar")
def study_start(
    photo: UploadFile = File(..., description="Foto saat mulai belajar"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return study_service.start(db, photo, now, board)


@router.post("/end", response_model=StudyActionOut, summary="Upload foto SETELAH belajar (menutup sesi)")
def study_end(
    photo: UploadFile = File(..., description="Foto setelah belajar"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return study_service.end(db, photo, now)


@router.get("/sessions", response_model=list[StudySessionOut], summary="Daftar sesi belajar")
def study_sessions(
    local_date: date | None = Query(None, description="Filter satu tanggal lokal"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return study_service.sessions(db, local_date, limit)


@router.post("/restore", response_model=RestoreOut, summary="Pakai restorasi untuk menyelamatkan streak belajar")
def study_restore(
    payload: RestoreIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return restore_service.use(db, "study", payload.target_date, now, board)


@router.get("/violations", response_model=list[ViolationOut], summary="Log pelanggaran belajar")
def study_violations(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return violations.recent(db, "study", limit)
