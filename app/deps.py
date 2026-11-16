from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import sweep
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now


def get_board(db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> Scoreboard:
    """Jalankan sapuan lazy lalu kembalikan papan skor terbaru.
    Dipakai semua endpoint yang bergantung pada status hari ini (FastAPI meng-cache `db` dan `now` per request)."""
    return sweep.run(db, now)
