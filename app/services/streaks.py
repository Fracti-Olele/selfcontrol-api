"""Ringkasan streak (bangun, belajar, utama)."""
from app.schemas import MainStatusOut, StreaksOut
from app.services import scoreboard
from app.services.scoreboard import Scoreboard


def main_status(board: Scoreboard) -> MainStatusOut:
    v = board.today_view
    return MainStatusOut(
        local_date=v.date,
        verdict=v.main.value,
        wake=v.wake.value,
        study=v.study.value,
        reflection=v.reflection,
        streak=scoreboard.streak_out(board.main),
    )


def overview(board: Scoreboard) -> StreaksOut:
    return StreaksOut(
        wake=scoreboard.streak_out(board.wake),
        study=scoreboard.streak_out(board.study),
        main=scoreboard.streak_out(board.main),
        wake_restore=scoreboard.balance_out(board.balances["wake"]),
        study_restore=scoreboard.balance_out(board.balances["study"]),
    )
