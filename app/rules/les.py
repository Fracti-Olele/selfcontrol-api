"""Aturan les: waktu berangkat, jendela check-in, bolos, dan verifikasi perubahan jadwal."""
from datetime import date, datetime, time, timedelta, tzinfo

from app.rules.clock import ONE_MINUTE, Window, at, local_date
from app.rules.ruleset import RuleSet


def departure_at(d: date, start: time, travel_minutes: int, tz: tzinfo) -> datetime:
    """Waktu berangkat = jam les dikurangi lama perjalanan (mis. les 17.00 -> berangkat 16.30)."""
    return at(d, start, tz) - timedelta(minutes=travel_minutes)


def checkin_window(d: date, start: time, travel_minutes: int, rs: RuleSet, tz: tzinfo) -> Window:
    """Upload foto boleh sejak waktu berangkat sampai 1 jam kemudian (les 17.00 -> 16.30 s.d. 17.30 / berakhir 17:30:59)."""
    dep = departure_at(d, start, travel_minutes, tz)
    return Window(dep, dep + timedelta(minutes=rs.les_window_minutes) + ONE_MINUTE)


def applies(window: Window, effective_from: datetime) -> bool:
    """Kemunculan jadwal hanya dihitung bila jendelanya belum berakhir saat versi jadwal ini mulai berlaku
    (jadwal yang baru dibuat/diubah tidak boleh langsung 'membolos' untuk waktu yang sudah lewat)."""
    return window.end > effective_from


def status(window: Window, now: datetime, attended: bool, excused: bool) -> str:
    """present | excused | upcoming | open | absent"""
    if attended:
        return "present"
    if excused:
        return "excused"
    if now < window.start:
        return "upcoming"
    return "open" if now < window.end else "absent"


def next_occurrence(
    weekday: int, start: time, travel_minutes: int, effective_from: datetime, now: datetime, rs: RuleSet, tz: tzinfo
):
    """(tanggal, jendela) kemunculan terdekat yang jendelanya belum berakhir, atau None."""
    today = local_date(now, tz)
    for k in range(-1, 9):
        d = today + timedelta(days=k)
        if d.weekday() != weekday:
            continue
        w = checkin_window(d, start, travel_minutes, rs, tz)
        if w.end > now and applies(w, effective_from):
            return d, w
    return None


def phrase_ok(text: str, rs: RuleSet) -> bool:
    """Teks verifikasi harus persis (huruf besar/kecil & tanda baca dihitung); spasi di ujung diabaikan."""
    return text.strip() == rs.change_phrase
