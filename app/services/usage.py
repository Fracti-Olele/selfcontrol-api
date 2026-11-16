"""Logika pemakaian aplikasi: bandingkan durasi hari ini dengan batas harian."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppLimit, UsageDaily
from app.schemas import UsageItem, UsageResult


def evaluate(limit: AppLimit | None, package_name: str, used_seconds: int) -> UsageResult:
    """Aplikasi tanpa batas aktif selalu 'allowed'. Mencapai batas (>=) berarti 'blocked'."""
    if limit is None or not limit.is_active:
        return UsageResult(
            package_name=package_name,
            status="allowed",
            used_seconds=used_seconds,
            limit_seconds=None,
            remaining_seconds=None,
        )
    limit_seconds = limit.daily_limit_minutes * 60
    return UsageResult(
        package_name=package_name,
        status="blocked" if used_seconds >= limit_seconds else "allowed",
        used_seconds=used_seconds,
        limit_seconds=limit_seconds,
        remaining_seconds=max(limit_seconds - used_seconds, 0),
    )


def record(db: Session, usage_date: date, items: list[UsageItem], now: datetime) -> list[UsageResult]:
    """Simpan total pemakaian (hanya boleh naik) lalu hitung status tiap aplikasi."""
    totals: dict[str, int] = {}
    for it in items:  # gabungkan duplikat dalam satu laporan
        totals[it.package_name] = max(totals.get(it.package_name, 0), it.total_seconds)

    limits = {lim.package_name: lim for lim in db.scalars(select(AppLimit))}
    results = []
    for package, seconds in totals.items():
        row = db.scalar(
            select(UsageDaily).where(UsageDaily.package_name == package, UsageDaily.usage_date == usage_date)
        )
        if row is None:
            row = UsageDaily(package_name=package, usage_date=usage_date, duration_seconds=seconds)
            db.add(row)
        else:
            row.duration_seconds = max(row.duration_seconds, seconds)  # tidak bisa "diturunkan"
        row.updated_at = now
        results.append(evaluate(limits.get(package), package, row.duration_seconds))
    db.commit()
    return results


def blocked_packages(db: Session, usage_date: date) -> list[str]:
    """Semua aplikasi yang hari itu sudah mencapai/melewati batasnya."""
    stmt = (
        select(AppLimit.package_name)
        .select_from(AppLimit)
        .join(
            UsageDaily,
            (UsageDaily.package_name == AppLimit.package_name) & (UsageDaily.usage_date == usage_date),
        )
        .where(AppLimit.is_active.is_(True), UsageDaily.duration_seconds >= AppLimit.daily_limit_minutes * 60)
        .order_by(AppLimit.package_name)
    )
    return list(db.scalars(stmt))
