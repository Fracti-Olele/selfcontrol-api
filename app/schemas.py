"""Bentuk data masuk/keluar API (divalidasi otomatis oleh Pydantic).
Semua waktu keluar sebagai ISO 8601 zona lokal, mis. "2026-11-16T07:00:00+07:00"."""
from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from app.timeutils import to_local

LocalDT = Annotated[datetime, PlainSerializer(lambda v: to_local(v).isoformat(), return_type=str)]
PACKAGE_PATTERN = r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$"  # mis. com.instagram.android


# ====================== umum ======================
class StreakOut(BaseModel):
    current: int
    best: int
    current_if_restored: int = Field(description="Nilai streak bila semua hari yang masih bisa dipulihkan dipulihkan")
    restorable_dates: list[date]


class BalanceOut(BaseModel):
    quota: float = Field(description="Jatah restorasi bulan ini")
    used: int
    remaining: float = Field(description="Satu restorasi butuh sisa >= 1")


class RestoreIn(BaseModel):
    target_date: date = Field(description="Tanggal yang gagal dan ingin diselamatkan")


class RestoreOut(BaseModel):
    kind: Literal["wake", "study"]
    target_date: date
    streak: StreakOut
    balance: BalanceOut


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    code: str
    local_date: date
    occurred_at: LocalDT
    message: str


# ====================== bangun tidur ======================
class WakeStatusOut(BaseModel):
    local_date: date
    state: Literal["pending", "on_time", "late", "overdue"]
    deadline_at: LocalDT = Field(description="Batas akhir check-in (sampai akhir menit ini)")
    checked_in_at: LocalDT | None
    study_penalty_minutes: int = Field(description="Tambahan target belajar hari ini (20 bila terlambat/gagal)")
    streak: StreakOut
    restore: BalanceOut


class WakeCheckInOut(BaseModel):
    on_time: bool
    uploaded_at: LocalDT
    message: str
    status: WakeStatusOut


# ====================== belajar ======================
class StudySessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    local_date: date
    started_at: LocalDT
    ended_at: LocalDT | None
    duration_seconds: int
    status: Literal["open", "completed", "expired"]


class StudyStatusOut(BaseModel):
    local_date: date
    is_holiday: bool
    required_seconds: int = Field(description="Target hari ini (40 menit, +20 bila bangun terlambat/gagal)")
    studied_seconds: int
    remaining_seconds: int
    target_met: bool
    holiday_credit_earned: bool = Field(description="Hari libur yang target-nya tercapai: +0.5 tabungan restorasi")
    open_session: StudySessionOut | None
    streak: StreakOut
    restore: BalanceOut


class StudyActionOut(BaseModel):
    session: StudySessionOut
    message: str
    status: StudyStatusOut


# ====================== refleksi & histori harian ======================
class ReflectionIn(BaseModel):
    happy: bool = Field(description="Apakah kamu senang dengan hari ini?")
    text: str = Field(min_length=1, max_length=2000, description="Yang ingin dicurahkan (tulis 'tidak ada' bila memang tidak ada)")


class ReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    local_date: date
    happy: bool
    text: str
    answered_at: LocalDT
    starred: bool


class ReflectionStatusOut(BaseModel):
    question: str
    local_date: date
    state: Literal["not_open", "open", "closed"]
    opens_at: LocalDT
    closes_at: LocalDT
    answered: bool
    entry: ReflectionOut | None


class StarIn(BaseModel):
    starred: bool


class HistoryDayOut(BaseModel):
    local_date: date
    wake: str
    study: str
    reflection: str
    main: str
    studied_seconds: int
    entry: ReflectionOut | None


# ====================== streak ======================
class MainStatusOut(BaseModel):
    local_date: date
    verdict: str
    wake: str
    study: str
    reflection: str
    streak: StreakOut


class StreaksOut(BaseModel):
    wake: StreakOut
    study: StreakOut
    main: StreakOut
    wake_restore: BalanceOut
    study_restore: BalanceOut


# ====================== tugas mingguan ======================
class ChoreStatusOut(BaseModel):
    key: str
    label: str
    state: Literal["done", "not_open", "open", "missed"]
    window_start: LocalDT
    window_end: LocalDT
    done_at: LocalDT | None


class ChoreCheckInOut(BaseModel):
    key: str
    week_start: date
    uploaded_at: LocalDT
    message: str


class ChoreHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_key: str
    week_start: date
    uploaded_at: LocalDT


# ====================== les ======================
class LesScheduleIn(BaseModel):
    title: str = Field(min_length=1, max_length=100, examples=["Les Matematika"])
    weekday: int = Field(ge=0, le=6, description="0=Senin ... 6=Minggu")
    start_time: time = Field(examples=["17:00"])
    travel_minutes: int | None = Field(default=None, ge=0, le=240, description="Lama perjalanan; kosong = 30 menit")


class LesWindowOut(BaseModel):
    local_date: date
    departure_at: LocalDT
    deadline_at: LocalDT = Field(description="Batas akhir upload foto (sampai akhir menit ini)")


class LesScheduleOut(BaseModel):
    id: int
    title: str
    weekday: int
    start_time: time
    travel_minutes: int
    is_active: bool
    next_occurrence: LesWindowOut | None


class LesChanges(BaseModel):
    """Perubahan yang diajukan. Isi hanya field yang ingin diubah."""

    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    travel_minutes: int | None = Field(default=None, ge=0, le=240)
    is_active: bool | None = Field(default=None, description="false = hentikan jadwal ini")

    @model_validator(mode="after")
    def _not_empty(self):
        if all(v is None for v in (self.weekday, self.start_time, self.travel_minutes, self.is_active)):
            raise ValueError("isi minimal satu field yang ingin diubah")
        return self


class ChangeRequestOut(BaseModel):
    id: int
    schedule_id: int
    changes: dict[str, Any]
    confirmations: int
    required_confirmations: int
    status: str
    expires_at: LocalDT
    next_step: Literal["confirm", "type_phrase", "done"]


class FinalizeIn(BaseModel):
    phrase: str = Field(description="Ketik persis teks verifikasi")


class LesCheckInOut(BaseModel):
    attendance_id: int
    schedule_id: int
    title: str
    local_date: date
    checked_in_at: LocalDT
    message: str


class ExcuseIn(BaseModel):
    schedule_id: int
    local_date: date = Field(description="Tanggal les yang diizinkan")
    reason: str = Field(min_length=5, max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ExtraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: LocalDT
    reason: str | None
    reason_at: LocalDT | None


class LesHistoryItem(BaseModel):
    kind: Literal["present", "absent", "excused", "extra"]
    at: LocalDT
    title: str | None
    local_date: date | None
    reason: str | None


class LesTodayOut(BaseModel):
    schedule_id: int
    title: str
    local_date: date
    departure_at: LocalDT
    deadline_at: LocalDT
    state: Literal["upcoming", "open", "present", "excused", "absent"]


# ====================== ringkasan untuk HP ======================
class StatusOut(BaseModel):
    """Satu panggilan untuk semua yang dibutuhkan app Android."""

    server_time: LocalDT
    local_date: date
    wake: WakeStatusOut
    study: StudyStatusOut
    reflection: ReflectionStatusOut
    main: MainStatusOut
    chores: list[ChoreStatusOut]
    les_today: list[LesTodayOut]
    violations_today: list[ViolationOut]
    blocked_packages: list[str]


# ====================== batas & pemakaian aplikasi (tetap dari Tahap 1) ======================
class LimitIn(BaseModel):
    label: str = Field(min_length=1, max_length=100, examples=["Instagram"])
    daily_limit_minutes: int = Field(ge=0, le=1440, examples=[60])
    is_active: bool = True


class LimitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    package_name: str
    label: str
    daily_limit_minutes: int
    is_active: bool


class UsageItem(BaseModel):
    package_name: str = Field(max_length=200, pattern=PACKAGE_PATTERN, examples=["com.instagram.android"])
    total_seconds: int = Field(ge=0, le=86_400, description="Total pemakaian hari ini dalam detik (kumulatif)")


class UsageReport(BaseModel):
    usage_date: date | None = Field(default=None, description="Tanggal lokal laporan; kosong = hari ini")
    items: list[UsageItem] = Field(min_length=1, max_length=200)


class UsageResult(BaseModel):
    package_name: str
    status: Literal["allowed", "blocked"]
    used_seconds: int
    limit_seconds: int | None
    remaining_seconds: int | None


class UsageReportOut(BaseModel):
    usage_date: date
    results: list[UsageResult]
    blocked_packages: list[str]
