"""Tes lapisan aturan murni (tanpa database/FastAPI).
Kalender 2026: 16 Nov = Senin ... 20 = Jumat, 21 = Sabtu, 22 = Minggu. 1 Des 2026 = Selasa."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.rules import chores, les, reflection, restore, study, wake
from app.rules.chores import CHORES
from app.rules.clock import until, week_start
from app.rules.restore import Balance
from app.rules.ruleset import RuleSet
from app.rules.streaks import DayFacts, Verdict, evaluate_days, main_streak, sub_streak

TZ = ZoneInfo("Asia/Jakarta")
RS = RuleSet()


def T(s: str) -> datetime:
    fmt = "%Y-%m-%d %H:%M:%S" if s.count(":") == 2 else "%Y-%m-%d %H:%M"
    return datetime.strptime(s, fmt).replace(tzinfo=TZ)


def D(s: str) -> date:
    return date.fromisoformat(s)


def facts(d: str, wake_hm: str | None, minutes: int, reflected: bool) -> DayFacts:
    return DayFacts(T(f"{d} {wake_hm}") if wake_hm else None, minutes * 60, reflected)


def streaks(days, today: str):
    t = D(today)
    return sub_streak(days, "wake", t, RS), sub_streak(days, "study", t, RS), main_streak(days, t, RS)


def mon_to_wed():
    return {D(f"2026-11-{n}"): facts(f"2026-11-{n}", "06:30", 45, True) for n in (16, 17, 18)}


def thursday(f, wake_hm="06:30", minutes=45, reflected=True):
    f[D("2026-11-19")] = facts("2026-11-19", wake_hm, minutes, reflected)
    return f


# ---------------- konvensi waktu ----------------
def test_until_means_end_of_that_minute():
    assert until(D("2026-11-16"), time(7, 0), TZ) == T("2026-11-16 07:01")
    assert until(D("2026-11-16"), time(23, 59), TZ) == T("2026-11-17 00:00")
    assert week_start(D("2026-11-22")) == D("2026-11-16")  # Minggu masih pekan yang dimulai Senin 16


# ---------------- bangun tidur ----------------
def test_wake_deadline_weekday_and_weekend():
    assert wake.is_on_time(T("2026-11-16 07:00:59"), RS, TZ)        # Senin: sampai 07.00
    assert not wake.is_on_time(T("2026-11-16 07:01:00"), RS, TZ)
    assert wake.is_on_time(T("2026-11-20 07:00:30"), RS, TZ)        # Jumat tetap 07.00
    assert not wake.is_on_time(T("2026-11-20 07:30"), RS, TZ)
    for day in ("2026-11-21", "2026-11-22"):                          # Sabtu & Minggu: 09.00
        assert wake.is_on_time(T(f"{day} 09:00:59"), RS, TZ)
        assert not wake.is_on_time(T(f"{day} 09:01:00"), RS, TZ)
    assert wake.is_on_time(T("2026-11-16 00:00:00"), RS, TZ)


def test_wake_state_and_penalty():
    d = D("2026-11-16")
    assert wake.state(d, None, T("2026-11-16 06:00"), RS, TZ) == "pending"
    assert wake.state(d, None, T("2026-11-16 07:01"), RS, TZ) == "overdue"
    assert wake.state(d, T("2026-11-16 06:50"), T("2026-11-16 08:00"), RS, TZ) == "on_time"
    assert wake.state(d, T("2026-11-16 07:45"), T("2026-11-16 08:00"), RS, TZ) == "late"
    assert wake.penalized("late") and wake.penalized("overdue")
    assert not wake.penalized("on_time") and not wake.penalized("pending")


def test_initial_start_date_skips_a_day_whose_wake_deadline_already_passed():
    assert wake.initial_start_date(T("2026-11-16 06:59"), RS, TZ) == D("2026-11-16")
    assert wake.initial_start_date(T("2026-11-16 07:01"), RS, TZ) == D("2026-11-17")
    assert wake.initial_start_date(T("2026-11-21 08:59"), RS, TZ) == D("2026-11-21")
    assert wake.initial_start_date(T("2026-11-21 09:01"), RS, TZ) == D("2026-11-22")


# ---------------- belajar ----------------
def test_study_target_and_penalty():
    assert study.required_seconds(False, RS) == 40 * 60
    assert study.required_seconds(True, RS) == 60 * 60
    assert [d for d in range(16, 23) if study.is_holiday(date(2026, 11, d), RS)] == [20, 21]  # Jumat & Sabtu


def test_session_seconds():
    assert study.session_seconds(T("2026-11-16 10:00"), T("2026-11-16 10:39:59")) == 39 * 60 + 59
    assert study.session_seconds(T("2026-11-16 10:00"), T("2026-11-16 10:40")) == 40 * 60
    assert study.session_seconds(T("2026-11-16 10:00"), T("2026-11-16 09:00")) == 0


def test_study_total_is_cumulative_and_inclusive():
    d = "2026-11-17"
    for seconds, expected in ((39 * 60 + 59, Verdict.MISSED), (40 * 60, Verdict.COUNTED)):
        day = evaluate_days({D(d): DayFacts(T(f"{d} 06:00"), seconds, True)}, {}, D(d), T("2026-11-18 01:00"), RS, TZ)[0]
        assert day.study is expected
    live = evaluate_days({D(d): DayFacts(T(f"{d} 06:00"), 600, False)}, {}, D(d), T(f"{d} 15:00"), RS, TZ)[0]
    assert live.study is Verdict.PENDING  # hari berjalan: belum cukup bukan berarti gagal


def test_late_wake_raises_study_target_to_60_minutes():
    d = "2026-11-17"
    day = evaluate_days({D(d): facts(d, "07:30", 45, True)}, {}, D(d), T("2026-11-18 10:00"), RS, TZ)[0]
    assert day.wake_state == "late" and day.study_required_seconds == 3600
    assert (day.wake, day.study, day.main) == (Verdict.MISSED, Verdict.MISSED, Verdict.MISSED)
    day = evaluate_days({D(d): facts(d, "07:30", 60, True)}, {}, D(d), T("2026-11-18 10:00"), RS, TZ)[0]
    assert day.study is Verdict.COUNTED and day.wake is Verdict.MISSED  # belajar cukup, streak bangun tetap gagal


def test_overdue_wake_today_activates_penalty_and_is_restorable_same_day():
    day = evaluate_days({}, {}, D("2026-11-17"), T("2026-11-17 08:00"), RS, TZ)
    v = day[0]
    assert v.wake_state == "overdue" and v.wake is Verdict.MISSED and v.study_required_seconds == 3600
    assert sub_streak(day, "wake", D("2026-11-17"), RS).restorable == (D("2026-11-17"),)


# ---------------- streak ----------------
def test_full_week_holidays_are_neutral_for_study_but_not_for_wake_or_main():
    f = {
        D("2026-11-16"): facts("2026-11-16", "06:30", 45, True),
        D("2026-11-17"): facts("2026-11-17", "06:30", 45, True),
        D("2026-11-18"): facts("2026-11-18", "06:30", 45, True),
        D("2026-11-19"): facts("2026-11-19", "06:30", 45, True),
        D("2026-11-20"): facts("2026-11-20", "06:30", 0, True),   # Jumat: libur belajar
        D("2026-11-21"): facts("2026-11-21", "08:30", 0, True),   # Sabtu: batas bangun 09.00
        D("2026-11-22"): facts("2026-11-22", "08:30", 45, True),
    }
    days = evaluate_days(f, {}, D("2026-11-16"), T("2026-11-22 23:30"), RS, TZ)
    wk, st, mn = streaks(days, "2026-11-22")
    assert [v.study for v in days][4:6] == [Verdict.NEUTRAL, Verdict.NEUTRAL]
    assert (wk.current, st.current, mn.current) == (7, 5, 7)  # belajar tidak bertambah/putus di hari libur


def test_pending_today_never_breaks_streak():
    f = {D("2026-11-16"): facts("2026-11-16", "06:30", 45, True)}
    days = evaluate_days(f, {}, D("2026-11-16"), T("2026-11-17 05:00"), RS, TZ)
    assert days[-1].wake is Verdict.PENDING and days[-1].study is Verdict.PENDING
    wk, st, mn = streaks(days, "2026-11-17")
    assert (wk.current, st.current, mn.current) == (1, 1, 1)


def test_missed_day_resets_and_restoration_bridges_without_adding():
    f = thursday(mon_to_wed(), wake_hm="07:30")                       # Kamis: bangun telat -> bangun & belajar gagal
    f[D("2026-11-20")] = facts("2026-11-20", "06:30", 0, False)       # Jumat pagi: sudah check-in bangun
    now, today = T("2026-11-20 10:00"), "2026-11-20"
    days = evaluate_days(f, {}, D("2026-11-16"), now, RS, TZ)
    wk, st, mn = streaks(days, today)
    kamis = D("2026-11-19")
    assert (wk.current, wk.best, wk.restorable, wk.current_if_restored) == (1, 3, (kamis,), 4)
    assert (st.current, st.restorable, st.current_if_restored) == (0, (kamis,), 3)
    assert (mn.current, mn.restorable, mn.current_if_restored) == (0, (kamis,), 3)  # perlu DUA restorasi

    restored = {"wake": {kamis}, "study": {kamis}}
    days = evaluate_days(f, restored, D("2026-11-16"), now, RS, TZ)
    wk, st, mn = streaks(days, today)
    assert (wk.current, st.current, mn.current) == (4, 3, 3)
    assert days[3].main is Verdict.BRIDGED                             # diselamatkan, tidak +1
    f[D("2026-11-20")] = facts("2026-11-20", "06:30", 0, True)         # Jumat 13.00: refleksi dijawab
    days = evaluate_days(f, restored, D("2026-11-16"), T("2026-11-20 13:00"), RS, TZ)
    assert streaks(days, today)[2].current == 4

    only_wake = evaluate_days(f, {"wake": {kamis}}, D("2026-11-16"), now, RS, TZ)
    assert only_wake[3].main is Verdict.MISSED                         # restorasi bangun saja tidak cukup


def test_restore_window_is_until_end_of_next_day():
    f = thursday(mon_to_wed(), wake_hm="07:30")
    f[D("2026-11-20")] = facts("2026-11-20", "06:30", 0, True)
    f[D("2026-11-21")] = facts("2026-11-21", "08:00", 0, True)
    for now, expected in (("2026-11-20 10:00", (D("2026-11-19"),)), ("2026-11-21 10:00", ())):
        days = evaluate_days(f, {}, D("2026-11-16"), T(now), RS, TZ)
        assert sub_streak(days, "wake", D(now[:10]), RS).restorable == expected


def test_missing_reflection_breaks_main_and_cannot_be_restored():
    f = thursday(mon_to_wed(), reflected=False)                        # Kamis: lupa refleksi
    f[D("2026-11-20")] = facts("2026-11-20", "06:30", 0, False)
    days = evaluate_days(f, {}, D("2026-11-16"), T("2026-11-20 10:00"), RS, TZ)
    wk, st, mn = streaks(days, "2026-11-20")
    assert days[3].reflection == "missed" and days[3].main is Verdict.MISSED
    assert (mn.current, mn.restorable, mn.current_if_restored) == (0, (), 0)
    assert (wk.current, st.current) == (5, 4)                          # streak bangun & belajar tidak terganggu


# ---------------- restorasi ----------------
def test_holiday_credit_requires_target_met_that_day():
    f = {
        D("2026-11-20"): facts("2026-11-20", "06:30", 45, True),   # Jumat: bangun tepat waktu, 45 >= 40 -> kredit
        D("2026-11-21"): facts("2026-11-21", "09:30", 45, True),   # Sabtu: telat -> target 60, 45 < 60 -> tidak
    }
    days = evaluate_days(f, {}, D("2026-11-20"), T("2026-11-22 10:00"), RS, TZ)
    assert restore.holiday_credit_dates(days, D("2026-11-22")) == [D("2026-11-20")]


def test_study_quota_is_5_plus_savings_and_wake_is_3():
    credits = [D("2026-11-06"), D("2026-11-07"), D("2026-11-13")]      # 3 hari libur dipakai belajar
    dec, jan = D("2026-12-01"), D("2027-01-01")
    assert restore.savings(credits, D("2026-11-01"), RS) == 0.0        # tabungan Nov baru berlaku di awal Des
    assert restore.balance("study", dec, credits, 2, RS) == Balance(6.5, 2, 4.5)
    assert restore.savings(credits + [D("2026-12-04")], jan, RS) == 2.0    # permanen: tidak berkurang
    monthly = RuleSet(savings_mode="monthly")
    assert restore.savings(credits + [D("2026-12-04")], jan, monthly) == 0.5  # hanya tabungan bulan lalu
    assert restore.balance("wake", dec, credits, 1, RS) == Balance(3.0, 1, 2.0)


# ---------------- refleksi & tugas ----------------
def test_reflection_window_12_to_2359():
    d = D("2026-11-16")
    assert reflection.state(T("2026-11-16 11:59:59"), d, RS, TZ) == "not_open"
    assert reflection.state(T("2026-11-16 12:00:00"), d, RS, TZ) == "open"
    assert reflection.state(T("2026-11-16 23:59:59"), d, RS, TZ) == "open"
    assert reflection.state(T("2026-11-17 00:00:00"), d, RS, TZ) == "closed"
    assert reflection.cutoff_date(D("2026-11-16"), RS) == D("2026-11-09")


def test_chore_windows():
    iron, food, wed = CHORES["setrika"], CHORES["pakan_hewan"], D("2026-11-18")
    w = chores.window(iron, wed, TZ)
    assert (w.start, w.end) == (T("2026-11-20 00:00"), T("2026-11-23 00:00"))        # Jumat 00.00 - Minggu 23.59
    assert chores.state(iron, wed, T("2026-11-19 23:59:59"), False, TZ) == "not_open"
    assert chores.state(iron, wed, T("2026-11-20 00:00:00"), False, TZ) == "open"
    assert chores.state(iron, wed, T("2026-11-22 23:59:59"), False, TZ) == "open"
    assert chores.state(iron, wed, T("2026-11-22 12:00"), True, TZ) == "done"
    wf = chores.window(food, wed, TZ)
    assert (wf.start, wf.end) == (T("2026-11-18 00:00"), T("2026-11-23 00:00"))      # Rabu 00.00 - Minggu 23.59
    assert chores.state(food, wed, T("2026-11-17 23:59:59"), False, TZ) == "not_open"
    assert chores.state(iron, D("2026-11-23"), T("2026-11-23 00:00"), False, TZ) == "not_open"  # pekan baru
    assert chores.photo_cutoff(T("2026-11-16 12:00"), RS) == T("2026-11-09 12:00")


# ---------------- les ----------------
def test_les_window_matches_the_example_in_the_spec():
    d = D("2026-11-17")  # les 17.00 -> berangkat 16.30 -> check-in 16.30 s.d. 17.30
    assert les.departure_at(d, time(17, 0), 30, TZ) == T("2026-11-17 16:30")
    w = les.checkin_window(d, time(17, 0), 30, RS, TZ)
    assert w.contains(T("2026-11-17 16:30:00")) and not w.contains(T("2026-11-17 16:29:59"))
    assert w.contains(T("2026-11-17 17:30:59")) and not w.contains(T("2026-11-17 17:31:00"))
    statuses = [
        les.status(w, T("2026-11-17 16:00"), False, False),
        les.status(w, T("2026-11-17 16:45"), False, False),
        les.status(w, T("2026-11-17 17:31"), False, False),
        les.status(w, T("2026-11-17 17:31"), True, False),
        les.status(w, T("2026-11-17 17:31"), False, True),
    ]
    assert statuses == ["upcoming", "open", "absent", "present", "excused"]


def test_les_schedule_created_after_its_window_is_not_truancy():
    w = les.checkin_window(D("2026-11-17"), time(17, 0), 30, RS, TZ)
    assert not les.applies(w, T("2026-11-17 17:35"))   # dibuat setelah jendela berakhir
    assert les.applies(w, T("2026-11-17 17:00"))       # dibuat di tengah jendela: masih berlaku


def test_les_next_occurrence_including_overnight_window():
    # Selasa 17.00: pada Rabu 18 Nov jendela Selasa 17 sudah berakhir -> Selasa 24
    d, w = les.next_occurrence(1, time(17, 0), 30, T("2026-11-01 00:00"), T("2026-11-18 10:00"), RS, TZ)
    assert d == D("2026-11-24") and w.start == T("2026-11-24 16:30")
    # Rabu 00.10, berangkat 23.40 hari Selasa -> pada Selasa 23.50 jendelanya sudah terbuka
    d, w = les.next_occurrence(2, time(0, 10), 30, T("2026-11-01 00:00"), T("2026-11-17 23:50"), RS, TZ)
    assert d == D("2026-11-18") and w.start == T("2026-11-17 23:40") and w.contains(T("2026-11-17 23:50"))


def test_change_phrase_must_match_exactly():
    ok = "saya tidak berbohong, memang jadwalnya berubah"
    assert les.phrase_ok(ok, RS) and les.phrase_ok("  " + ok + "\n", RS)
    for wrong in (ok.capitalize(), ok.replace(",", ""), ok + ".", ok.replace("tidak ", ""), ""):
        assert not les.phrase_ok(wrong, RS)
