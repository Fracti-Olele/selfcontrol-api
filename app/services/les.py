"""Les: jadwal mandiri, check-in foto, bolos, izin, les tambahan, dan perubahan jadwal berverifikasi."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LesAttendance, LesChangeRequest, LesExtra, LesSchedule
from app.rules import les
from app.rules.clock import DAY_NAMES, ONE_DAY, Window, last_minute, local_date
from app.rules.ruleset import DEFAULT_RULES as RS
from app.schemas import (
    ChangeRequestOut,
    ExcuseIn,
    LesChanges,
    LesCheckInOut,
    LesHistoryItem,
    LesScheduleIn,
    LesScheduleOut,
    LesTodayOut,
    LesWindowOut,
)
from app.services import meta, photos, violations
from app.timeutils import TZ


@dataclass(frozen=True)
class Occurrence:
    """Satu kemunculan jadwal mingguan pada satu tanggal, lengkap dengan jendela check-in-nya."""

    schedule: LesSchedule
    local_date: date
    window: Window


# ---------------- util internal ----------------
def _occurrences(schedule: LesSchedule, first: date, last: date) -> list:
    out, d = [], first
    while d <= last:
        if d.weekday() == schedule.weekday:
            window = les.checkin_window(d, schedule.start_time, schedule.travel_minutes, RS, TZ)
            if les.applies(window, schedule.effective_from):
                out.append(Occurrence(schedule, d, window))
        d += ONE_DAY
    return out


def _active(db: Session, schedule_id: int | None = None) -> list:
    stmt = select(LesSchedule).where(LesSchedule.is_active.is_(True)).order_by(LesSchedule.start_time)
    if schedule_id is not None:
        stmt = stmt.where(LesSchedule.id == schedule_id)
    return list(db.scalars(stmt))


def _attendance(db: Session, first: date, last: date) -> dict:
    rows = db.scalars(select(LesAttendance).where(LesAttendance.local_date >= first, LesAttendance.local_date <= last))
    return {(r.schedule_id, r.local_date): r for r in rows}


def _window_out(d: date, window: Window) -> LesWindowOut:
    return LesWindowOut(local_date=d, departure_at=window.start, deadline_at=last_minute(window.end))


# ---------------- jadwal ----------------
def schedule_out(sch: LesSchedule, now: datetime) -> LesScheduleOut:
    nxt = None
    if sch.is_active:
        nxt = les.next_occurrence(sch.weekday, sch.start_time, sch.travel_minutes, sch.effective_from, now, RS, TZ)
    return LesScheduleOut(
        id=sch.id,
        title=sch.title,
        weekday=sch.weekday,
        start_time=sch.start_time,
        travel_minutes=sch.travel_minutes,
        is_active=sch.is_active,
        next_occurrence=_window_out(nxt[0], nxt[1]) if nxt is not None else None,
    )


def create_schedule(db: Session, payload: LesScheduleIn, now: datetime) -> LesScheduleOut:
    """Menambah jadwal bebas (tanpa verifikasi). Mengubah/menghentikan jadwal yang ada WAJIB lewat verifikasi."""
    travel = payload.travel_minutes if payload.travel_minutes is not None else RS.les_default_travel_minutes
    sch = LesSchedule(
        title=payload.title,
        weekday=payload.weekday,
        start_time=payload.start_time,
        travel_minutes=travel,
        is_active=True,
        effective_from=now,
        created_at=now,
    )
    db.add(sch)
    db.commit()
    db.refresh(sch)
    return schedule_out(sch, now)


def list_schedules(db: Session, now: datetime) -> list:
    rows = db.scalars(select(LesSchedule).order_by(LesSchedule.weekday, LesSchedule.start_time))
    return [schedule_out(s, now) for s in rows]


# ---------------- bolos (dipanggil oleh sweep) ----------------
def mark_absences(db: Session, now: datetime) -> None:
    """Kemunculan jadwal yang jendelanya sudah berakhir tanpa check-in/izin -> bolos + log pelanggaran."""
    today = local_date(now, TZ)
    last_seen = meta.get_date(db, "last_les_date")
    first = (min(last_seen, today) if last_seen is not None else today) - ONE_DAY  # -1 hari: jendela bisa lewat tengah malam
    handled = _attendance(db, first, today)
    for sch in _active(db):
        for occ in _occurrences(sch, first, today):
            if occ.window.end > now or (sch.id, occ.local_date) in handled:
                continue
            db.add(
                LesAttendance(
                    schedule_id=sch.id,
                    local_date=occ.local_date,
                    window_start=occ.window.start,
                    window_end=occ.window.end,
                    status="absent",
                    created_at=now,
                )
            )
            violations.add_once(
                db,
                category="les",
                code="LES_ABSENT",
                local_date=occ.local_date,
                occurred_at=occ.window.end,
                message=(
                    f"Bolos les {sch.title} pada {occ.local_date:%d-%m-%Y}: "
                    f"tidak ada foto check-in sampai {last_minute(occ.window.end):%H:%M}."
                ),
                dedupe_key=f"les_absent:{sch.id}:{occ.local_date}",
            )
    meta.put_date(db, "last_les_date", today)


# ---------------- check-in ----------------
def _next_window_hint(schedules: list, now: datetime) -> str:
    today = local_date(now, TZ)
    upcoming = [o for s in schedules for o in _occurrences(s, today, today + timedelta(days=8)) if o.window.start > now]
    if not upcoming:
        return ""
    nxt = min(upcoming, key=lambda o: o.window.start)
    return (
        f" Jendela berikutnya: {nxt.schedule.title}, {DAY_NAMES[nxt.local_date.weekday()]} "
        f"{nxt.local_date:%d-%m} pukul {nxt.window.start:%H:%M}."
    )


def checkin(db: Session, upload: UploadFile, now: datetime, schedule_id: int | None) -> LesCheckInOut:
    today = local_date(now, TZ)
    schedules = _active(db, schedule_id)
    if schedule_id is not None and not schedules:
        raise HTTPException(404, "Jadwal les tidak ditemukan atau tidak aktif.")

    handled = _attendance(db, today - ONE_DAY, today + ONE_DAY)
    open_now = [
        occ
        for sch in schedules
        for occ in _occurrences(sch, today - ONE_DAY, today + ONE_DAY)
        if occ.window.contains(now) and (sch.id, occ.local_date) not in handled
    ]
    if not open_now:
        raise HTTPException(409, "Tidak ada les yang jendela check-in-nya sedang terbuka." + _next_window_hint(schedules, now))
    if len(open_now) > 1:
        raise HTTPException(409, "Lebih dari satu les sedang terbuka. Sertakan schedule_id.")
    occ = open_now[0]

    data, ext = photos.read_photo(upload)
    photo = photos.store_photo(db, data, ext, now, "les")
    att = LesAttendance(
        schedule_id=occ.schedule.id,
        local_date=occ.local_date,
        window_start=occ.window.start,
        window_end=occ.window.end,
        status="present",
        photo_id=photo.id,
        checked_in_at=now,
        created_at=now,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return LesCheckInOut(
        attendance_id=att.id,
        schedule_id=occ.schedule.id,
        title=occ.schedule.title,
        local_date=occ.local_date,
        checked_in_at=now,
        message=f"Check-in les {occ.schedule.title} tercatat.",
    )


# ---------------- izin ----------------
def excuse(db: Session, payload: ExcuseIn, now: datetime) -> LesHistoryItem:
    sch = db.get(LesSchedule, payload.schedule_id)
    if sch is None or not sch.is_active:
        raise HTTPException(404, "Jadwal les tidak ditemukan atau tidak aktif.")
    if payload.local_date.weekday() != sch.weekday:
        raise HTTPException(422, f"Tanggal itu bukan hari les ({DAY_NAMES[sch.weekday]}).")
    window = les.checkin_window(payload.local_date, sch.start_time, sch.travel_minutes, RS, TZ)
    if not les.applies(window, sch.effective_from):
        raise HTTPException(422, "Les pada tanggal itu tidak termasuk jadwal yang berlaku.")
    if now >= window.end:
        raise HTTPException(409, "Waktu les itu sudah lewat. Izin hanya bisa diajukan sebelum jendela check-in berakhir.")
    exists = db.scalar(
        select(LesAttendance.id).where(
            LesAttendance.schedule_id == sch.id, LesAttendance.local_date == payload.local_date
        )
    )
    if exists is not None:
        raise HTTPException(409, "Les pada tanggal itu sudah tercatat (hadir atau izin).")

    att = LesAttendance(
        schedule_id=sch.id,
        local_date=payload.local_date,
        window_start=window.start,
        window_end=window.end,
        status="excused",
        reason=payload.reason,
        created_at=now,
    )
    db.add(att)
    db.commit()
    return LesHistoryItem(
        kind="excused", at=window.start, title=sch.title, local_date=payload.local_date, reason=payload.reason
    )


# ---------------- les tambahan (makeup class) ----------------
def extra_upload(db: Session, upload: UploadFile, now: datetime) -> LesExtra:
    data, ext = photos.read_photo(upload)
    photo = photos.store_photo(db, data, ext, now, "les")
    extra = LesExtra(photo_id=photo.id, uploaded_at=now)
    db.add(extra)
    db.commit()
    db.refresh(extra)
    return extra


def extra_reason(db: Session, extra_id: int, reason: str, now: datetime) -> LesExtra:
    extra = db.get(LesExtra, extra_id)
    if extra is None:
        raise HTTPException(404, "Les tambahan tidak ditemukan.")
    if extra.reason is not None:
        raise HTTPException(409, "Alasan sudah diisi dan tidak bisa diubah.")
    extra.reason, extra.reason_at = reason, now
    db.commit()
    db.refresh(extra)
    return extra


# ---------------- histori & hari ini ----------------
def history(db: Session, limit: int) -> list:
    rows = db.scalars(select(LesAttendance).order_by(LesAttendance.window_start.desc()).limit(limit))
    extras = db.scalars(select(LesExtra).order_by(LesExtra.uploaded_at.desc()).limit(limit))
    items = [
        LesHistoryItem(kind=r.status, at=r.window_start, title=r.title, local_date=r.local_date, reason=r.reason)
        for r in rows
    ]
    items += [LesHistoryItem(kind="extra", at=e.uploaded_at, title=None, local_date=None, reason=e.reason) for e in extras]
    items.sort(key=lambda i: i.at, reverse=True)
    return items[:limit]


def today(db: Session, now: datetime) -> list:
    d = local_date(now, TZ)
    handled = _attendance(db, d, d)
    out = []
    for sch in _active(db):
        for occ in _occurrences(sch, d, d):
            att = handled.get((sch.id, d))
            state = les.status(
                occ.window, now, att is not None and att.status == "present", att is not None and att.status == "excused"
            )
            out.append(
                LesTodayOut(
                    schedule_id=sch.id,
                    title=sch.title,
                    local_date=d,
                    departure_at=occ.window.start,
                    deadline_at=last_minute(occ.window.end),
                    state=state,
                )
            )
    out.sort(key=lambda x: x.departure_at)
    return out


# ---------------- perubahan jadwal: konfirmasi berulang + teks persis ----------------
def _current_values(sch: LesSchedule) -> dict:
    return {
        "weekday": sch.weekday,
        "start_time": sch.start_time.isoformat(),
        "travel_minutes": sch.travel_minutes,
        "is_active": sch.is_active,
    }


def _request_out(req: LesChangeRequest) -> ChangeRequestOut:
    if req.status == "applied":
        step = "done"
    elif req.confirmations < req.required_confirmations:
        step = "confirm"
    else:
        step = "type_phrase"
    return ChangeRequestOut(
        id=req.id,
        schedule_id=req.schedule_id,
        changes=req.changes,
        confirmations=req.confirmations,
        required_confirmations=req.required_confirmations,
        status=req.status,
        expires_at=req.expires_at,
        next_step=step,
    )


def _pending(db: Session, request_id: int, now: datetime) -> LesChangeRequest:
    req = db.get(LesChangeRequest, request_id)
    if req is None:
        raise HTTPException(404, "Permintaan perubahan tidak ditemukan.")
    if req.status != "pending":
        raise HTTPException(409, f"Permintaan ini sudah berstatus {req.status}.")
    if now >= req.expires_at:
        req.status = "expired"
        db.commit()
        raise HTTPException(409, "Permintaan kedaluwarsa. Ajukan perubahan dari awal.")
    return req


def request_change(db: Session, schedule_id: int, payload: LesChanges, now: datetime) -> ChangeRequestOut:
    """Langkah 1: ajukan perubahan. Permintaan pending lama untuk jadwal yang sama dibatalkan."""
    sch = db.get(LesSchedule, schedule_id)
    if sch is None:
        raise HTTPException(404, "Jadwal les tidak ditemukan.")
    current = _current_values(sch)
    changes = {k: v for k, v in payload.model_dump(mode="json", exclude_none=True).items() if current[k] != v}
    if not changes:
        raise HTTPException(422, "Tidak ada perbedaan dengan jadwal yang sekarang.")
    for old in db.scalars(
        select(LesChangeRequest).where(LesChangeRequest.schedule_id == sch.id, LesChangeRequest.status == "pending")
    ):
        old.status = "cancelled"
    req = LesChangeRequest(
        schedule_id=sch.id,
        changes=changes,
        confirmations=0,
        required_confirmations=RS.change_confirmations,
        status="pending",
        created_at=now,
        expires_at=now + timedelta(minutes=RS.change_request_ttl_minutes),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _request_out(req)


def confirm_change(db: Session, request_id: int, now: datetime) -> ChangeRequestOut:
    """Langkah 2: konfirmasi (diulang sebanyak change_confirmations kali)."""
    req = _pending(db, request_id, now)
    if req.confirmations >= req.required_confirmations:
        raise HTTPException(409, "Konfirmasi sudah cukup. Lanjutkan dengan mengetik teks verifikasi.")
    req.confirmations += 1
    db.commit()
    return _request_out(req)


def finalize_change(db: Session, request_id: int, phrase: str, now: datetime) -> LesScheduleOut:
    """Langkah 3: ketik teks persis -> perubahan diterapkan, berlaku sejak sekarang."""
    req = _pending(db, request_id, now)
    if req.confirmations < req.required_confirmations:
        raise HTTPException(409, f"Konfirmasi baru {req.confirmations}/{req.required_confirmations}.")
    if not les.phrase_ok(phrase, RS):
        raise HTTPException(422, "Teks verifikasi tidak sama persis.")

    sch = db.get(LesSchedule, req.schedule_id)
    ch = req.changes
    if "weekday" in ch:
        sch.weekday = ch["weekday"]
    if "start_time" in ch:
        sch.start_time = time.fromisoformat(ch["start_time"])
    if "travel_minutes" in ch:
        sch.travel_minutes = ch["travel_minutes"]
    if "is_active" in ch:
        sch.is_active = ch["is_active"]
    sch.effective_from = now  # kemunculan versi lama sudah disapu (bolos dicatat) sebelum request ini diproses
    req.status, req.applied_at = "applied", now
    db.commit()
    db.refresh(sch)
    return schedule_out(sch, now)
