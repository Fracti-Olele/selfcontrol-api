from fastapi import APIRouter, Depends

from app.deps import get_board
from app.schemas import MainStatusOut, StreaksOut
from app.services import streaks as streaks_service
from app.services.scoreboard import Scoreboard

router = APIRouter()


@router.get("", response_model=StreaksOut, summary="Streak bangun, belajar, utama + sisa restorasi")
def streaks_overview(board: Scoreboard = Depends(get_board)):
    return streaks_service.overview(board)


@router.get("/main", response_model=MainStatusOut, summary="Streak utama: 3 syarat hari ini")
def main_status(board: Scoreboard = Depends(get_board)):
    return streaks_service.main_status(board)
