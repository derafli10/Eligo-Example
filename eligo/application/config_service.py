"""Layanan Aplikasi Konfigurasi Parameter Bisnis (Application Config Service).

Modul ini bertanggung jawab menyediakan akses terpusat ke parameter aturan SNBP
yang dimuat dari berkas konfigurasi (`data/config.json`), seperti persentase kuota akreditasi,
bonus e-Rapor, bobot poin piagam prestasi, dan kamus pemetaan kata status TKA.

Penjelasan Sederhana untuk Orang Awam:
    Setiap aturan di sistem Eligo (seperti Akreditasi A = 40%, bonus e-Rapor = +5%,
    juara provinsi = 0.50 poin) disimpan dalam berkas konfigurasi agar mudah diubah
    jika pemerintah memperbarui aturan SNBP tahun depan. Layanan ini bertugas mengambil
    aturan-aturan tersebut dan menyerahkannya ke menu atau layanan lain yang membutuhkan.

Kepatuhan Standar Rekayasa:
    - Arsitektur: Lapisan Aplikasi (Config Provider).
    - C6: Kamus sinonim TKA fleksibel dari berkas konfigurasi.
"""

from __future__ import annotations

from decimal import Decimal

from eligo.domain.models import AppConfig
from eligo.domain.repositories import ConfigRepository


def get_app_config(repo: ConfigRepository) -> AppConfig:
    """Mengambil objek konfigurasi aktif aplikasi dari repositori.

    Args:
        repo: Repositori konfigurasi sistem.

    Returns:
        Objek AppConfig yang memuat seluruh parameter bisnis sistem.
    """
    return repo.load()


def get_tka_synonyms(repo: ConfigRepository) -> dict[str, str]:
    """Mengambil kamus sinonim variasi kata untuk status keikutsertaan TKA.

    Args:
        repo: Repositori konfigurasi.

    Returns:
        Kamus pemetaan kata mentah ke nilai standar (misal {"ya": "IKUT", "ikut": "IKUT"}).
    """
    config = repo.load()
    return config.tka_synonyms


def get_quota_percentages(repo: ConfigRepository) -> dict[str, Decimal]:
    """Mengambil tabel persentase kuota dasar untuk masing-masing akreditasi sekolah.

    Args:
        repo: Repositori konfigurasi.

    Returns:
        Kamus persentase kuota, contoh: {"A": Decimal("0.40"), "B": Decimal("0.25")}.
    """
    config = repo.load()
    return config.quota_percentages
