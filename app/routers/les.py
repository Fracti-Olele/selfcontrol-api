from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_board
from app.schemas import (
    ChangeRequestOut,
    ExcuseIn,
    ExtraOut,
    FinalizeIn,
    LesChanges,
    LesCheckInOut,
    LesHistoryItem,
    LesScheduleIn,
    LesScheduleOut,
    LesTodayOut,
    ReasonIn,
)
from app.services import les as les_service
from app.services.scoreboard import Scoreboard
from app.timeutils import get_now

# Semua endpoint bergantung pada `board` (get_board) agar sapuan bolos dijalankan lebih dulu.
router = APIRouter()


# ---------- jadwal ----------
@router.get("/schedules", response_model=list[LesScheduleOut], summary="Daftar jadwal les + jendela berikutnya")
def list_schedules(db: Session = Depends(get_db), now: datetime = Depends(get_now), board: Scoreboard = Depends(get_board)):
    return les_service.list_schedules(db, now)


@router.post("/schedules", response_model=LesScheduleOut, status_code=201, summary="Tambah jadwal les (hari + jam)")
def create_schedule(
    payload: LesScheduleIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.create_schedule(db, payload, now)


# ---------- ubah jadwal: verifikasi 2 langkah ----------
@router.post(
    "/schedules/{schedule_id}/changes",
    response_model=ChangeRequestOut,
    status_code=201,
    summary="Ajukan perubahan jadwal (langkah 1)",
)
def request_change(
    schedule_id: int,
    payload: LesChanges,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.request_change(db, schedule_id, payload, now)


@router.post("/changes/{request_id}/confirm", response_model=ChangeRequestOut, summary="Konfirmasi perubahan (ulangi beberapa kali)")
def confirm_change(
    request_id: int,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.confirm_change(db, request_id, now)


@router.post("/changes/{request_id}/finalize", response_model=LesScheduleOut, summary="Ketik teks verifikasi persis -> terapkan")
def finalize_change(
    request_id: int,
    payload: FinalizeIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.finalize_change(db, request_id, payload.phrase, now)


# ---------- check-in, izin, les tambahan ----------
@router.post("/checkin", response_model=LesCheckInOut, status_code=201, summary="Upload foto di lingkungan les")
def checkin(
    photo: UploadFile = File(..., description="Foto di lokasi les"),
    schedule_id: int | None = Form(None, description="Hanya perlu bila dua les terbuka bersamaan"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.checkin(db, photo, now, schedule_id)


@router.post("/excuses", response_model=LesHistoryItem, status_code=201, summary="Ajukan izin (ketik alasan)")
def excuse(
    payload: ExcuseIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.excuse(db, payload, now)


@router.post("/extras", response_model=ExtraOut, status_code=201, summary="Les tambahan di luar jadwal: upload foto dulu")
def extra_upload(
    photo: UploadFile = File(..., description="Foto di lokasi les tambahan"),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.extra_upload(db, photo, now)


@router.put("/extras/{extra_id}/reason", response_model=ExtraOut, summary="Les tambahan: isi alasan (sekali)")
def extra_reason(
    extra_id: int,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    board: Scoreboard = Depends(get_board),
):
    return les_service.extra_reason(db, extra_id, payload.reason, now)


# ---------- histori & hari ini ----------
@router.get("/history", response_model=list[LesHistoryItem], summary="Histori les: hadir, bolos, izin, les tambahan")
def history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    board: Scoreboard = Depends(get_board),
):
    return les_service.history(db, limit)


@router.get("/today", response_model=list[LesTodayOut], summary="Les hari ini + status jendelanya")
def today(db: Session = Depends(get_db), now: datetime = Depends(get_now), board: Scoreboard = Depends(get_board)):
    return les_service.today(db, now)
