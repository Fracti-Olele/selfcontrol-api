"""Tes alur HTTP end-to-end (jam server dipalsukan lewat fixture `at`).
Kalender 2026: 16 Nov = Senin, 17 = Selasa, 18 = Rabu, 19 = Kamis, 20 = Jumat, 21 = Sabtu, 22 = Minggu. 1 Des = Selasa."""
import os

API = "/api/v1"


def photo() -> bytes:
    """Byte acak berawalan header JPEG: lolos cek format dan selalu unik."""
    return b"\xff\xd8\xff\xe0" + os.urandom(64)


def send(client, path: str, data: bytes | None = None):
    return client.post(f"{API}{path}", files={"photo": ("bukti.jpg", data or photo(), "image/jpeg")})


def violation_codes(client, query: str = "") -> list[str]:
    return [v["code"] for v in client.get(f"{API}/violations?limit=200{query}").json()]


# ====================== bangun tidur ======================
def test_wake_deadline_and_study_penalty(client, at):
    at("2026-11-16 06:30")  # Senin
    r = send(client, "/wake/checkin")
    assert r.status_code == 201 and r.json()["on_time"] is True
    assert client.get(f"{API}/study/status").json()["required_seconds"] == 40 * 60
    assert send(client, "/wake/checkin").status_code == 409  # sekali per hari

    at("2026-11-17 07:30")  # Selasa: lewat 07.00 -> terlambat
    r = send(client, "/wake/checkin")
    assert r.status_code == 201 and r.json()["on_time"] is False
    assert client.get(f"{API}/study/status").json()["required_seconds"] == 60 * 60  # +20 menit
    assert "WAKE_LATE" in violation_codes(client, "&category=wake")


def test_missing_wake_checkin_is_logged_on_the_next_day(client, at):
    at("2026-11-16 06:00")
    client.get(f"{API}/status")  # sistem mulai Senin
    at("2026-11-17 06:00")
    logs = {v["code"]: v for v in client.get(f"{API}/violations").json()}
    assert {"WAKE_MISSED", "STUDY_TARGET_MISSED"} <= set(logs)
    assert "0 dari 60 menit" in logs["STUDY_TARGET_MISSED"]["message"]  # bangun gagal -> target 60 menit


def test_days_without_any_request_are_caught_up_later(client, at):
    at("2026-11-16 06:00")
    client.get(f"{API}/status")
    at("2026-11-20 06:00")  # server "mati" 4 hari
    logs = client.get(f"{API}/violations?limit=200").json()
    expected = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]
    assert sorted(v["local_date"] for v in logs if v["code"] == "WAKE_MISSED") == expected
    assert sorted(v["local_date"] for v in logs if v["code"] == "STUDY_TARGET_MISSED") == expected  # Jumat = libur


# ====================== belajar ======================
def test_study_sessions_accumulate_until_target(client, at):
    at("2026-11-16 06:30")
    send(client, "/wake/checkin")
    at("2026-11-16 08:00")
    assert send(client, "/study/start").status_code == 201
    assert send(client, "/study/start").status_code == 409  # sesi masih berjalan
    at("2026-11-16 08:20")
    r = send(client, "/study/end")
    assert r.status_code == 200
    st = r.json()["status"]
    assert (st["studied_seconds"], st["target_met"]) == (1200, False)  # 20 menit < 40
    assert send(client, "/study/end").status_code == 409  # tidak ada sesi aktif

    at("2026-11-16 09:00")  # boleh upload lagi di hari yang sama
    send(client, "/study/start")
    at("2026-11-16 09:25")
    st = send(client, "/study/end").json()["status"]
    assert (st["studied_seconds"], st["target_met"]) == (2700, True)  # 20 + 25 menit >= 40


def test_unclosed_session_expires_at_midnight_and_is_not_counted(client, at):
    at("2026-11-16 06:30")
    send(client, "/wake/checkin")
    at("2026-11-16 23:30")
    send(client, "/study/start")
    at("2026-11-17 00:10")
    st = client.get(f"{API}/study/status").json()
    assert st["open_session"] is None and st["studied_seconds"] == 0
    assert client.get(f"{API}/study/sessions?local_date=2026-11-16").json()[0]["status"] == "expired"
    assert send(client, "/study/end").status_code == 409


def test_holiday_study_adds_savings_for_next_month(client, at):
    at("2026-11-20 06:30")  # Jumat = libur belajar
    send(client, "/wake/checkin")
    at("2026-11-20 08:00")
    send(client, "/study/start")
    at("2026-11-20 08:45")
    send(client, "/study/end")
    st = client.get(f"{API}/study/status").json()
    assert st["is_holiday"] and st["holiday_credit_earned"]

    at("2026-12-01 10:00")  # awal bulan: restorasi = 5 + tabungan
    assert client.get(f"{API}/study/status").json()["restore"]["quota"] == 5.5
    assert client.get(f"{API}/wake/status").json()["restore"]["quota"] == 3


def test_same_photo_cannot_be_reused_across_features(client, at):
    at("2026-11-16 06:30")
    shared = photo()
    assert send(client, "/wake/checkin", shared).status_code == 201
    at("2026-11-16 08:00")
    assert send(client, "/study/start", shared).status_code == 409
    assert send(client, "/study/start", b"bukan foto").status_code == 415


# ====================== streak & restorasi ======================
def test_main_streak_counts_only_when_all_three_conditions_done(client, at):
    at("2026-11-16 06:30")
    send(client, "/wake/checkin")
    at("2026-11-16 08:00")
    send(client, "/study/start")
    at("2026-11-16 08:45")
    send(client, "/study/end")  # 45 menit
    at("2026-11-16 11:00")
    r = client.put(f"{API}/reflection/today", json={"happy": True, "text": "Lumayan"})
    assert r.status_code == 409  # jendela refleksi baru dibuka 12.00
    assert client.get(f"{API}/streaks/main").json()["verdict"] == "pending"

    at("2026-11-16 13:00")
    assert client.put(f"{API}/reflection/today", json={"happy": True, "text": "Hari yang baik"}).status_code == 200
    main = client.get(f"{API}/streaks/main").json()
    assert main["verdict"] == "counted" and main["streak"]["current"] == 1


def test_missed_day_can_be_restored_once_within_the_window(client, at):
    at("2026-11-16 06:30")
    send(client, "/wake/checkin")
    at("2026-11-16 08:00")
    send(client, "/study/start")
    at("2026-11-16 08:45")
    send(client, "/study/end")
    at("2026-11-17 06:30")  # Selasa: bangun tepat waktu tetapi tidak belajar
    send(client, "/wake/checkin")

    at("2026-11-18 06:00")  # Rabu pagi: Selasa masih dalam jendela restorasi
    study = client.get(f"{API}/streaks").json()["study"]
    assert study["current"] == 0 and study["restorable_dates"] == ["2026-11-17"] and study["current_if_restored"] == 1
    r = client.post(f"{API}/study/restore", json={"target_date": "2026-11-17"})
    assert r.status_code == 200
    assert r.json()["balance"]["used"] == 1 and r.json()["streak"]["current"] == 1
    assert client.post(f"{API}/study/restore", json={"target_date": "2026-11-17"}).status_code == 409  # sudah dipulihkan
    assert client.post(f"{API}/study/restore", json={"target_date": "2026-11-16"}).status_code == 409  # hari itu tidak gagal


# ====================== histori harian ======================
def test_daily_history_is_deleted_after_7_days_unless_starred(client, at):
    for day in ("16", "17"):
        at(f"2026-11-{day} 06:30")
        send(client, "/wake/checkin")
        at(f"2026-11-{day} 13:00")
        r = client.put(f"{API}/reflection/today", json={"happy": day == "16", "text": f"Catatan {day}"})
        assert r.status_code == 200
    assert client.put(f"{API}/history/2026-11-16/star", json={"starred": True}).status_code == 200

    at("2026-11-24 10:00")  # 16 Nov sudah >7 hari (berbintang), 17 Nov tepat 7 hari
    days = {h["local_date"]: h for h in client.get(f"{API}/history").json()}
    assert days["2026-11-16"]["entry"]["text"] == "Catatan 16"
    assert days["2026-11-17"]["entry"] is not None

    at("2026-11-25 10:00")
    days = {h["local_date"]: h for h in client.get(f"{API}/history").json()}
    assert days["2026-11-16"]["entry"] is not None  # berbintang: tetap ada
    assert "2026-11-17" not in days  # tidak berbintang: terhapus
    assert client.put(f"{API}/history/2026-11-17/star", json={"starred": True}).status_code == 404


# ====================== tugas mingguan ======================
def test_chore_windows_and_one_week_retention(client, at):
    at("2026-11-18 10:00")  # Rabu
    assert send(client, "/chores/pakan_hewan/checkin").status_code == 201
    assert send(client, "/chores/pakan_hewan/checkin").status_code == 409  # sekali per pekan
    assert send(client, "/chores/setrika/checkin").status_code == 409  # baru dibuka Jumat
    assert send(client, "/chores/tidak_ada/checkin").status_code == 404
    states = {c["key"]: c["state"] for c in client.get(f"{API}/chores").json()}
    assert states == {"setrika": "not_open", "pakan_hewan": "done"}

    at("2026-11-20 00:00")  # Jumat 00.00: setrika dibuka
    assert send(client, "/chores/setrika/checkin").status_code == 201

    at("2026-11-26 12:00")  # check-in Rabu 18 Nov sudah >7 hari -> terhapus; Jumat 20 Nov masih ada
    kept = [h["task_key"] for h in client.get(f"{API}/chores/history").json()]
    assert kept == ["setrika"]


# ====================== les ======================
def make_les(client, title: str, weekday: int, start: str = "17:00") -> int:
    r = client.post(f"{API}/les/schedules", json={"title": title, "weekday": weekday, "start_time": start})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def les_kinds(client) -> dict:
    return {h["title"]: h["kind"] for h in client.get(f"{API}/les/history").json() if h["title"]}


def test_les_checkin_window_absence_and_excuse(client, at):
    at("2026-11-16 10:00")  # Senin
    make_les(client, "Matematika", 1)  # Selasa 17.00 -> berangkat 16.30, check-in 16.30-17.30
    rabu = make_les(client, "Fisika", 2)
    kamis = make_les(client, "Kimia", 3)
    r = client.post(
        f"{API}/les/excuses", json={"schedule_id": kamis, "local_date": "2026-11-19", "reason": "Ada acara keluarga"}
    )
    assert r.status_code == 201

    at("2026-11-17 16:00")
    r = send(client, "/les/checkin")
    assert r.status_code == 409 and "16:30" in r.json()["detail"]
    at("2026-11-17 16:40")
    r = send(client, "/les/checkin")
    assert r.status_code == 201 and r.json()["title"] == "Matematika"

    at("2026-11-18 17:45")  # Rabu: 1 jam lewat tanpa kabar -> bolos
    assert les_kinds(client)["Fisika"] == "absent"
    assert violation_codes(client, "&category=les") == ["LES_ABSENT"]

    at("2026-11-19 17:45")  # Kamis: diizinkan -> bukan bolos
    assert les_kinds(client)["Kimia"] == "excused"
    assert violation_codes(client, "&category=les") == ["LES_ABSENT"]
    r = client.post(
        f"{API}/les/excuses", json={"schedule_id": rabu, "local_date": "2026-11-18", "reason": "Lupa mengabari"}
    )
    assert r.status_code == 409  # izin tidak bisa diajukan setelah waktunya lewat


def test_les_change_needs_confirmations_and_exact_phrase(client, at):
    at("2026-11-16 10:00")
    sid = make_les(client, "Matematika", 1)
    r = client.post(f"{API}/les/schedules/{sid}/changes", json={"start_time": "18:00"})
    assert r.status_code == 201
    req = r.json()
    assert req["next_step"] == "confirm" and req["required_confirmations"] == 3
    rid = req["id"]
    phrase = "saya tidak berbohong, memang jadwalnya berubah"
    assert client.post(f"{API}/les/changes/{rid}/finalize", json={"phrase": phrase}).status_code == 409  # belum konfirmasi

    for i in (1, 2, 3):
        r = client.post(f"{API}/les/changes/{rid}/confirm")
        assert r.status_code == 200 and r.json()["confirmations"] == i
    assert r.json()["next_step"] == "type_phrase"
    assert client.post(f"{API}/les/changes/{rid}/confirm").status_code == 409  # sudah cukup

    wrong = {"phrase": "Saya tidak berbohong, memang jadwalnya berubah"}  # huruf besar di awal
    assert client.post(f"{API}/les/changes/{rid}/finalize", json=wrong).status_code == 422
    r = client.post(f"{API}/les/changes/{rid}/finalize", json={"phrase": phrase})
    assert r.status_code == 200 and r.json()["start_time"] == "18:00:00"
    assert client.post(f"{API}/les/schedules/{sid}/changes", json={"start_time": "18:00"}).status_code == 422  # tak ada beda

    rid = client.post(f"{API}/les/schedules/{sid}/changes", json={"weekday": 3}).json()["id"]
    at("2026-11-16 10:31")  # permintaan hanya berlaku 30 menit
    assert client.post(f"{API}/les/changes/{rid}/confirm").status_code == 409


def test_extra_class_needs_photo_then_reason(client, at):
    at("2026-11-16 10:00")
    r = send(client, "/les/extras")
    assert r.status_code == 201 and r.json()["reason"] is None
    eid = r.json()["id"]
    assert client.put(f"{API}/les/extras/{eid}/reason", json={"reason": "Persiapan ujian"}).status_code == 200
    assert client.put(f"{API}/les/extras/{eid}/reason", json={"reason": "Ganti alasan"}).status_code == 409
    first = client.get(f"{API}/les/history").json()[0]
    assert first["kind"] == "extra" and first["reason"] == "Persiapan ujian"


# ====================== ringkasan HP, pemakaian, keamanan ======================
def test_status_contains_everything_the_phone_needs(client, at):
    at("2026-11-16 06:30")
    body = client.get(f"{API}/status").json()
    assert set(body) >= {"wake", "study", "reflection", "main", "chores", "les_today", "violations_today", "blocked_packages"}
    assert body["wake"]["state"] == "pending" and body["study"]["required_seconds"] == 40 * 60
    assert body["reflection"]["state"] == "not_open"
    assert body["reflection"]["question"].startswith("Apakah kamu senang dengan hari ini")


def post_usage(client, instagram_seconds: int) -> dict:
    items = [
        {"package_name": "com.instagram.android", "total_seconds": instagram_seconds},
        {"package_name": "com.whatsapp", "total_seconds": 9000},
    ]
    r = client.post(f"{API}/usage", json={"items": items})
    assert r.status_code == 200, r.text
    return r.json()


def test_usage_limit_blocks_app_until_next_day(client, at):
    at("2026-11-16 10:00")
    r = client.put(f"{API}/limits/com.instagram.android", json={"label": "Instagram", "daily_limit_minutes": 60})
    assert r.status_code == 200, r.text
    out = post_usage(client, 3000)
    by_app = {x["package_name"]: x for x in out["results"]}
    assert by_app["com.instagram.android"]["status"] == "allowed" and by_app["com.whatsapp"]["status"] == "allowed"
    assert post_usage(client, 3600)["blocked_packages"] == ["com.instagram.android"]  # tepat di batas
    assert post_usage(client, 100)["blocked_packages"] == ["com.instagram.android"]  # total tidak boleh turun
    assert client.get(f"{API}/status").json()["blocked_packages"] == ["com.instagram.android"]
    at("2026-11-17 10:00")  # hari baru -> reset
    assert post_usage(client, 60)["blocked_packages"] == []


def test_api_key_required(client):
    assert client.get(f"{API}/status", headers={"X-API-Key": "salah"}).status_code == 401
