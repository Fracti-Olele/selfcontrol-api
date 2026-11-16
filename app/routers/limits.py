from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppLimit
from app.schemas import PACKAGE_PATTERN, LimitIn, LimitOut

router = APIRouter()


@router.get("", response_model=list[LimitOut], summary="Daftar batas harian aplikasi")
def list_limits(db: Session = Depends(get_db)):
    return db.scalars(select(AppLimit).order_by(AppLimit.package_name)).all()


@router.put("/{package_name}", response_model=LimitOut, summary="Buat/ubah batas harian sebuah aplikasi")
def upsert_limit(
    payload: LimitIn,
    package_name: str = Path(max_length=200, pattern=PACKAGE_PATTERN, examples=["com.instagram.android"]),
    db: Session = Depends(get_db),
):
    limit = db.scalar(select(AppLimit).where(AppLimit.package_name == package_name))
    if limit is None:
        limit = AppLimit(
            package_name=package_name,
            label=payload.label,
            daily_limit_minutes=payload.daily_limit_minutes,
            is_active=payload.is_active,
        )
        db.add(limit)
    else:
        limit.label = payload.label
        limit.daily_limit_minutes = payload.daily_limit_minutes
        limit.is_active = payload.is_active
    db.commit()
    db.refresh(limit)
    return limit
