from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UsageReport, UsageReportOut
from app.services import usage as usage_service
from app.timeutils import get_now, local_today

router = APIRouter()


@router.post("", response_model=UsageReportOut, summary="HP melaporkan durasi pemakaian aplikasi")
def report_usage(payload: UsageReport, db: Session = Depends(get_db), now: datetime = Depends(get_now)):
    today = local_today(now)
    usage_date = payload.usage_date or today
    if usage_date > today:
        raise HTTPException(422, "usage_date tidak boleh di masa depan")

    results = usage_service.record(db, usage_date, payload.items, now)
    return UsageReportOut(
        usage_date=usage_date,
        results=results,
        blocked_packages=usage_service.blocked_packages(db, usage_date),
    )
