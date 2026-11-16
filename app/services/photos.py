"""Validasi, penyimpanan, dan penghapusan foto bukti."""
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Photo
from app.timeutils import to_local


def detect_image_ext(data: bytes) -> str | None:
    """Kenali jenis gambar dari byte awal file (header Content-Type dari klien tidak dipercaya)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_photo(upload: UploadFile) -> tuple[bytes, str]:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = upload.file.read(max_bytes + 1)  # baca 1 byte lebih untuk mendeteksi kelebihan ukuran
    if len(data) > max_bytes:
        raise HTTPException(413, f"Ukuran foto maksimal {settings.max_upload_mb} MB")
    ext = detect_image_ext(data)
    if ext is None:
        raise HTTPException(415, "File harus berupa foto JPEG, PNG, atau WebP")
    return data, ext


def store_photo(db: Session, data: bytes, ext: str, now: datetime, category: str) -> Photo:
    """Simpan file ke uploads/<kategori>/TAHUN/BULAN/TANGGAL/<uuid>.<ext> dan catat di tabel photos.
    Foto yang sama (sha256) tidak boleh dipakai ulang di fitur mana pun. Nama file dibuat server (aman dari path traversal)."""
    digest = hashlib.sha256(data).hexdigest()
    if settings.reject_duplicate_photos and db.scalar(select(Photo.id).where(Photo.sha256 == digest)) is not None:
        raise HTTPException(409, "Foto ini sudah pernah dipakai. Ambil foto baru.")
    local = to_local(now)
    rel = Path(category) / f"{local:%Y}" / f"{local:%m}" / f"{local:%d}" / f"{uuid.uuid4().hex}.{ext}"
    target = settings.upload_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    photo = Photo(path=rel.as_posix(), sha256=digest, size_bytes=len(data), uploaded_at=now)
    db.add(photo)
    db.flush()  # supaya photo.id terisi
    return photo


def delete_photo(db: Session, photo_id: int | None) -> None:
    """Hapus file dan barisnya (dipakai retensi)."""
    photo = db.get(Photo, photo_id) if photo_id is not None else None
    if photo is None:
        return
    (settings.upload_dir / photo.path).unlink(missing_ok=True)
    db.delete(photo)
