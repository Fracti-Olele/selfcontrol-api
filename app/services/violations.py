"""Log pelanggaran (bangun, belajar, les). `dedupe_key` menjamin satu pelanggaran = satu baris."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ViolationLog


def add_once(
    db: Session,
    *,
    category: str,
    code: str,
    local_date: date,
    occurred_at: datetime,
    message: str,
    dedupe_key: str,
) -> bool:
    """Tambah bila belum ada. Mengembalikan True bila benar-benar baru."""
    if db.scalar(select(ViolationLog.id).where(ViolationLog.dedupe_key == dedupe_key)) is not None:
        return False
    db.add(
        ViolationLog(
            category=category,
            code=code,
            local_date=local_date,
            occurred_at=occurred_at,
            message=message,
            dedupe_key=dedupe_key,
        )
    )
    return True


def recent(db: Session, category: str | None = None, limit: int = 50) -> list:
    stmt = select(ViolationLog).order_by(ViolationLog.occurred_at.desc(), ViolationLog.id.desc()).limit(limit)
    if category is not None:
        stmt = stmt.where(ViolationLog.category == category)
    return list(db.scalars(stmt))


def since(db: Session, moment: datetime) -> list:
    stmt = select(ViolationLog).where(ViolationLog.occurred_at >= moment).order_by(ViolationLog.occurred_at)
    return list(db.scalars(stmt))
