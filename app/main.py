from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401  (supaya semua tabel terdaftar di Base.metadata)
from app.config import settings
from app.database import Base, engine
from app.routers import chores, history, les, limits, reflection, streaks, study, usage, violations, wake
from app.routers import status as status_router
from app.security import verify_api_key
from app.timeutils import now_utc, to_local


def _refuse_stage1_database() -> None:
    """Skema Tahap 1 (jadwal/check-in generik) sudah diganti total. create_all tidak mengubah tabel lama, jadi hentikan dengan pesan jelas."""
    if inspect(engine).has_table("study_schedules"):
        raise RuntimeError(
            "Database Tahap 1 terdeteksi (ada tabel study_schedules). "
            "Hentikan server, hapus selfcontrol.db (isinya hanya data uji), lalu jalankan lagi."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _refuse_stage1_database()
    Base.metadata.create_all(bind=engine)  # tahap ini cukup create_all; nanti ganti ke Alembic
    yield


app = FastAPI(title="Self-Control API", version="0.2.0", lifespan=lifespan)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Dua request kembar yang menulis baris sama (batas unik database) -> 409, bukan 500."""
    return JSONResponse(status_code=409, content={"detail": "Data bentrok (kemungkinan permintaan ganda). Coba lagi."})


API = "/api/v1"
protected = [Depends(verify_api_key)]  # semua endpoint /api/v1 wajib memakai header X-API-Key
app.include_router(status_router.router, prefix=API, tags=["Ringkasan untuk HP"], dependencies=protected)
app.include_router(wake.router, prefix=f"{API}/wake", tags=["Bangun tidur"], dependencies=protected)
app.include_router(study.router, prefix=f"{API}/study", tags=["Belajar"], dependencies=protected)
app.include_router(reflection.router, prefix=f"{API}/reflection", tags=["Refleksi harian"], dependencies=protected)
app.include_router(history.router, prefix=f"{API}/history", tags=["Histori harian"], dependencies=protected)
app.include_router(streaks.router, prefix=f"{API}/streaks", tags=["Streak"], dependencies=protected)
app.include_router(chores.router, prefix=f"{API}/chores", tags=["Tugas mingguan"], dependencies=protected)
app.include_router(les.router, prefix=f"{API}/les", tags=["Les"], dependencies=protected)
app.include_router(violations.router, prefix=f"{API}/violations", tags=["Pelanggaran"], dependencies=protected)
app.include_router(limits.router, prefix=f"{API}/limits", tags=["Batas aplikasi"], dependencies=protected)
app.include_router(usage.router, prefix=f"{API}/usage", tags=["Pemakaian aplikasi"], dependencies=protected)


@app.get("/health", tags=["Sistem"], summary="Cek server hidup (tanpa API key)")
def health():
    return {"ok": True, "server_time": to_local(now_utc()).isoformat()}
