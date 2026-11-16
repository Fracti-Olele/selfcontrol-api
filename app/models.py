"""Struktur database (SQLAlchemy 2.0), dikelompokkan per subsistem.

Prinsip: tabel "fakta" (day_records, restorations, violation_logs, ...) bersifat permanen.
Hanya `reflections` (histori harian) dan `chore_checkins` (+ fotonya) yang dihapus otomatis setelah 7 hari.
"""
from datetime import date, datetime, time

from sqlalchemy import JSON, Date, ForeignKey, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime
from app.timeutils import now_utc


# ====================== umum ======================
class Meta(Base):
    """Key-value kecil: start_date, last_close_date, last_les_date, last_purge_date."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Photo(Base):
    """Semua foto bukti (bangun, belajar, tugas, les) tercatat di sini."""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(300))  # relatif terhadap UPLOAD_DIR
    sha256: Mapped[str] = mapped_column(String(64), index=True)  # mendeteksi foto yang dipakai ulang
    size_bytes: Mapped[int]
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc)


class ViolationLog(Base):
    """Log pelanggaran semua subsistem. category: wake | study | les."""

    __tablename__ = "violation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(40))  # WAKE_LATE, WAKE_MISSED, STUDY_TARGET_MISSED, LES_ABSENT
    local_date: Mapped[date] = mapped_column(Date, index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    message: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(100), unique=True)  # satu pelanggaran = satu baris, walau disapu berkali-kali


class DayRecord(Base):
    """Papan skor harian (fakta mentah). Streak dihitung dari tabel ini + restorations."""

    __tablename__ = "day_records"

    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    wake_checkin_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    study_seconds: Mapped[int]  # total durasi sesi belajar yang selesai hari itu
    reflection_done: Mapped[bool]


class Restoration(Base):
    """Satu baris = satu restorasi yang dipakai untuk menyelamatkan satu hari. kind: wake | study."""

    __tablename__ = "restorations"
    __table_args__ = (UniqueConstraint("kind", "target_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    target_date: Mapped[date] = mapped_column(Date)  # hari yang diselamatkan
    used_at: Mapped[datetime] = mapped_column(UTCDateTime)  # menentukan bulan kuota yang terpakai


# ====================== bangun tidur ======================
class WakeCheckIn(Base):
    __tablename__ = "wake_checkins"

    id: Mapped[int] = mapped_column(primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, unique=True)  # satu check-in per hari
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime)
    deadline_at: Mapped[datetime] = mapped_column(UTCDateTime)  # batas (eksklusif) yang berlaku hari itu
    on_time: Mapped[bool]
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))


# ====================== belajar ======================
class StudySession(Base):
    """Satu pasang foto: 'mulai' lalu 'setelah'. status: open | completed | expired (tidak ditutup sampai tengah malam)."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)  # tanggal lokal saat mulai
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    start_photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    end_photo_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), default=None)
    duration_seconds: Mapped[int]
    status: Mapped[str] = mapped_column(String(10), index=True)


# ====================== refleksi & histori harian ======================
class Reflection(Base):
    """Jawaban refleksi = entri histori harian. Dihapus otomatis setelah 7 hari kecuali `starred`."""

    __tablename__ = "reflections"

    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    happy: Mapped[bool]
    text: Mapped[str] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    starred: Mapped[bool]


# ====================== tugas mingguan ======================
class ChoreCheckIn(Base):
    """Check-in foto tugas (setrika, pakan_hewan). Satu per tugas per pekan. Dihapus otomatis setelah 7 hari."""

    __tablename__ = "chore_checkins"
    __table_args__ = (UniqueConstraint("task_key", "week_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_key: Mapped[str] = mapped_column(String(30))
    week_start: Mapped[date] = mapped_column(Date)  # Senin pada pekan itu
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))


# ====================== les ======================
class LesSchedule(Base):
    """Jadwal les mingguan (hari + jam). `effective_from` = kapan versi jadwal ini mulai berlaku."""

    __tablename__ = "les_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    weekday: Mapped[int]  # 0 = Senin ... 6 = Minggu
    start_time: Mapped[time] = mapped_column(Time)
    travel_minutes: Mapped[int]  # waktu berangkat = start_time - travel_minutes
    is_active: Mapped[bool]
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc)


class LesChangeRequest(Base):
    """Permintaan ubah jadwal: N kali konfirmasi + mengetik teks persis. status: pending|applied|cancelled|expired."""

    __tablename__ = "les_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("les_schedules.id"), index=True)
    changes: Mapped[dict] = mapped_column(JSON)  # hanya field yang berubah
    confirmations: Mapped[int]
    required_confirmations: Mapped[int]
    status: Mapped[str] = mapped_column(String(12), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class LesAttendance(Base):
    """Hasil satu kemunculan jadwal pada satu tanggal. status: present | absent (bolos) | excused (izin)."""

    __tablename__ = "les_attendance"
    __table_args__ = (UniqueConstraint("schedule_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("les_schedules.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)  # tanggal les
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)  # jendela dibekukan saat baris dibuat
    window_end: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(10))
    photo_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), default=None)
    checked_in_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    reason: Mapped[str | None] = mapped_column(Text, default=None)  # alasan izin
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc)

    schedule: Mapped[LesSchedule] = relationship()

    @property
    def title(self) -> str:
        return self.schedule.title


class LesExtra(Base):
    """Les tambahan di luar jadwal (makeup class): foto dulu, lalu alasan."""

    __tablename__ = "les_extras"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(ForeignKey("photos.id"))
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime)
    reason: Mapped[str | None] = mapped_column(Text, default=None)
    reason_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


# ====================== pemakaian aplikasi (tetap dari Tahap 1) ======================
class AppLimit(Base):
    """Batas pemakaian harian per aplikasi."""

    __tablename__ = "app_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_name: Mapped[str] = mapped_column(String(200), unique=True)  # mis. com.instagram.android
    label: Mapped[str] = mapped_column(String(100))
    daily_limit_minutes: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)


class UsageDaily(Base):
    """Total pemakaian per aplikasi per hari (kumulatif; nilainya hanya boleh naik)."""

    __tablename__ = "usage_daily"
    __table_args__ = (UniqueConstraint("package_name", "usage_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    package_name: Mapped[str] = mapped_column(String(200), index=True)
    usage_date: Mapped[date] = mapped_column(Date, index=True)  # tanggal lokal
    duration_seconds: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now_utc)
