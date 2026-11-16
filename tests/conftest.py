"""Fixture pengujian: database sementara + jam 'sekarang' yang bisa dipalsukan."""
import os
import tempfile
from datetime import datetime
from pathlib import Path

# Env harus diset SEBELUM `app` di-import, supaya test tidak menyentuh database asli.
_tmp = Path(tempfile.mkdtemp(prefix="selfcontrol-test-"))
os.environ["API_KEY"] = "test-key"
os.environ["TIMEZONE"] = "Asia/Jakarta"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.timeutils import TZ, get_now  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app, headers={"X-API-Key": "test-key"}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def at():
    """at("2026-11-16 19:10") -> server menganggap sekarang 16 Nov 2026 pukul 19:10 WIB."""

    def set_time(text: str) -> None:
        moment = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        app.dependency_overrides[get_now] = lambda: moment

    return set_time
