"""Semua angka aturan di satu tempat. Ubah default di sini bila aturannya berubah."""
from dataclasses import dataclass
from datetime import time
from typing import Literal


@dataclass(frozen=True)
class RuleSet:
    # ---- belajar ----
    study_min_minutes: int = 40                      # total durasi minimal per hari
    study_holiday_weekdays: frozenset = frozenset({4, 5})  # Jumat, Sabtu (Senin = 0)
    holiday_study_saving: float = 0.5                # tabungan restorasi per hari libur yang dipakai belajar
    study_restores_per_month: int = 5
    # "permanent": tabungan tidak pernah berkurang -> kuota bulanan = 5 + seluruh tabungan sebelum bulan itu
    # "monthly"  : tabungan dipindah ke kuota lalu habis -> kuota bulanan = 5 + tabungan bulan lalu saja
    savings_mode: Literal["permanent", "monthly"] = "permanent"

    # ---- bangun tidur ----
    weekend_weekdays: frozenset = frozenset({5, 6})  # Sabtu, Minggu
    wake_deadline_weekday: time = time(7, 0)
    wake_deadline_weekend: time = time(9, 0)
    wake_penalty_minutes: int = 20                   # tambahan target belajar bila bangun terlambat/gagal
    wake_restores_per_month: int = 3

    # ---- refleksi harian ----
    reflection_opens: time = time(12, 0)             # ditutup 23.59

    # ---- restorasi & histori ----
    restore_window_days: int = 1                     # hari yang gagal masih bisa dipulihkan sampai akhir hari berikutnya
    history_days: int = 7

    # ---- les ----
    les_default_travel_minutes: int = 30             # berangkat 30 menit sebelum les
    les_window_minutes: int = 60                     # rentang check-in: 1 jam sejak waktu berangkat
    change_confirmations: int = 3                    # jumlah konfirmasi sebelum mengetik teks
    change_request_ttl_minutes: int = 30
    change_phrase: str = "saya tidak berbohong, memang jadwalnya berubah"


DEFAULT_RULES = RuleSet()
