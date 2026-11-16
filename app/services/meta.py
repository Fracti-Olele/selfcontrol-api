"""Key-value kecil di tabel meta."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import Meta


def get(db: Session, key: str) -> str | None:
    row = db.get(Meta, key)
    return row.value if row is not None else None


def put(db: Session, key: str, value: str) -> None:
    row = db.get(Meta, key)
    if row is None:
        db.add(Meta(key=key, value=value))
    else:
        row.value = value


def get_date(db: Session, key: str) -> date | None:
    raw = get(db, key)
    return date.fromisoformat(raw) if raw else None


def put_date(db: Session, key: str, d: date) -> None:
    put(db, key, d.isoformat())
