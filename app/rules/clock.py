"""Helper waktu. Konvensi proyek: batas "sampai pukul HH.MM" berarti sampai AKHIR menit itu (HH:MM:59)."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

ONE_MINUTE = timedelta(minutes=1)
ONE_DAY = timedelta(days=1)
DAY_NAMES = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


@dataclass(frozen=True)
class Window:
    """Rentang waktu [start, end): start inklusif, end eksklusif."""

    start: datetime
    end: datetime

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts < self.end


def at(d: date, t: time, tz: tzinfo) -> datetime:
    """Tanggal + jam dinding lokal -> datetime aware."""
    return datetime.combine(d, t, tzinfo=tz)


def until(d: date, t: time, tz: tzinfo) -> datetime:
    """Batas eksklusif untuk 'sampai pukul t': 07.00 -> 07:01:00, 23.59 -> 00:00 esok hari."""
    return at(d, t, tz) + ONE_MINUTE


def local_date(ts: datetime, tz: tzinfo) -> date:
    return ts.astimezone(tz).date()


def week_start(d: date) -> date:
    """Senin pada pekan yang memuat d."""
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return d.replace(day=1)


def last_minute(end_exclusive: datetime) -> datetime:
    """Kebalikan `until`: batas eksklusif -> jam yang ditampilkan ke pengguna (07:01:00 -> 07:00, 00:00 -> 23:59)."""
    return end_exclusive - ONE_MINUTE
