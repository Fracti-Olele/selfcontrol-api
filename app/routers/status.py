from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import StatusOut
from app.services import dashboard
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

router = APIRouter()


@router.get("/status", response_model=StatusOut, summary="Ringkasan semua sistem untuk app Android (poll berkala)")
def get_status(db: Session = Depends(get_db), now: datetime = Depends(get_now), board: Scoreboard = Depends(get_board)):
    return dashboard.build(db, now, board)
