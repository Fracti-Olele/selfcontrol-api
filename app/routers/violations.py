from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import ViolationOut
from app.services import violations
from app.services.scoreboard import Scoreboard

router = APIRouter()


@router.get("", response_model=list[ViolationOut], summary="Log pelanggaran semua subsistem")
def all_violations(
    category: Literal["wake", "study", "les"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return violations.recent(db, category, limit)
