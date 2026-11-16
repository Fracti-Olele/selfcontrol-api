from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import HistoryDayOut, ReflectionOut, StarIn
from app.services import reflection as reflection_service
from app.services.scoreboard import Scoreboard

router = APIRouter()


@router.get("", response_model=list[HistoryDayOut], summary="Histori harian: 7 hari terakhir + yang berbintang")
def daily_history(db: Session = Depends(get_db), board: Scoreboard = Depends(get_board)):
    return reflection_service.history(db, board)


@router.put("/{local_date}/star", response_model=ReflectionOut, summary="Beri/cabut bintang agar tidak terhapus otomatis")
def star_entry(
    local_date: date,
    payload: StarIn,
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return reflection_service.set_star(db, local_date, payload.starred)
