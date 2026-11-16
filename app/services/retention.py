"""Penghapusan otomatis (maks. sekali per hari): histori refleksi >7 hari (kecuali berbintang) dan check-in foto tugas >7 hari."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ChoreCheckIn, Reflection
from app.rules import chores, reflection
from app.rules.clock import local_date
from app.rules.ruleset import DEFAULT_RULES as RS
from app.services import meta, photos
from app.timeutils import TZ


def purge(db: Session, now: datetime) -> None:
    today = local_date(now, TZ)
    if meta.get_date(db, "last_purge_date") == today:
        return

    cutoff = reflection.cutoff_date(today, RS)
    db.execute(delete(Reflection).where(Reflection.local_date < cutoff, Reflection.starred.is_(False)))

    old = db.scalars(select(ChoreCheckIn).where(ChoreCheckIn.uploaded_at < chores.photo_cutoff(now, RS))).all()
    for row in old:
        photos.delete_photo(db, row.photo_id)  # file + baris foto
        db.delete(row)

    meta.put_date(db, "last_purge_date", today)
