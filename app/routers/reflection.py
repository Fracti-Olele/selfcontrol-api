from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import ReflectionIn, ReflectionOut, ReflectionStatusOut
from app.services import reflection as reflection_service
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

router = APIRouter()


@router.get("", response_model=ReflectionStatusOut, summary="Pertanyaan refleksi + apakah jendelanya terbuka")
def reflection_status(db: Session = Depends(get_db), board: Scoreboard = Depends(get_board)):
    return reflection_service.status(db, board)


@router.put("/today", response_model=ReflectionOut, summary="Jawab refleksi hari ini (aktif 12.00-23.59)")
def answer_reflection(
    payload: ReflectionIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return reflection_service.answer(db, payload, now, board)
