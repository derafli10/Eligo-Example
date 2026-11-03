"""Modul Penulisan Berkas Atomik & Manajemen Backup Berbasis Disk.

Modul ini mengimplementasikan mekanisme penyimpanan atomik (Atomic File Write)
dan rotasi berkas cadangan (.bak) untuk menjamin integritas data sistem Eligo.

Prinsip Rekayasa Enterprise (AC-13.01, AC-13.02, ADR-04):
    1. All-or-Nothing (Atomisitas):
       Penulisan berkas dilakukan ke berkas sementara (`.tmp`) terlebih dahulu.
       Jika terjadi mati listrik, sistem crash, atau disk penuh di tengah penulisan,
       berkas utama tidak akan pernah terpotong atau korup (zero corrupted state).
    2. fsync Durability:
       Pemanggilan eksplisit `f.flush()` diikuti `os.fsync(f.fileno())` memaksa sistem
       operasi menulis seluruh buffer dari RAM langsung ke piringan disk fisik (SSD/HDD).
    3. Safe Backup Rotation:
       Sebelum berkas utama diperbarui, salinan persis dibuat ke berkas `.bak`
       menggunakan `shutil.copy2` (mempertahankan timestamp dan metadata).
    4. Atomic Replacement:
       Penggantian berkas utama menggunakan `os.replace` yang dijamin atomik
       pada sistem operasi POSIX dan Windows modern (NTFS).

Penjelasan Sederhana untuk Orang Awam:
    Bayangkan Anda sedang menulis buku rapor siswa yang sangat penting:
    1. Anda tidak menulis langsung di buku rapor asli. Anda mencoret-coret dulu di kertas buram (`.tmp`).
    2. Setelah semua tulisan di kertas buram selesai dan dipastikan benar, Anda memfotokopi
       buku rapor lama sebagai cadangan (`.bak`).
    3. Barulah Anda menukar kertas buram menjadi buku rapor resmi dalam satu detik (`os.replace`).
    Jika tiba-tiba listrik padam saat Anda sedang menulis di kertas buram, buku rapor asli
    tetap aman dan tidak pernah rusak!
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from eligo.domain.exceptions import ErrorCode, PersistenceError


def atomic_write_json(
    file_path: Path | str,
    data: Any,
    indent: int = 2,
) -> None:
    """Tulis data struktur Python ke berkas JSON dengan garansi keamanan atomik.

    Alur Teknis Penulisan:
        1. Pastikan folder direktori target sudah ada (buat jika belum ada).
        2. Tulis payload JSON ke berkas temporer `{file_path}.tmp`.
        3. Panggil `flush()` dan `os.fsync()` agar data tersimpan permanen ke media fisik.
        4. Jika berkas utama `{file_path}` sudah ada, duplikasi ke `{file_path}.bak`.
        5. Lakukan penggantian atomik: `os.replace({file_path}.tmp, {file_path})`.
        6. Jika terjadi error di tahapan manapun, bersihkan berkas `.tmp` dan
           lemparkan `PersistenceError(code="ATOMIC_WRITE_FAILED")`.

    Args:
        file_path: Lokasi Path berkas JSON target penyimpanan.
        data: Struktur data Python (dict, list, dll.) yang dapat diserialisasi ke JSON.
        indent: Jumlah spasi indentasi JSON (default: 2 spasi agar mudah dibaca manusia).

    Raises:
        PersistenceError: Jika gagal menulis ke berkas sementara, gagal membuat cadangan,
                          atau terjadi kesalahan I/O disk lainnya.

    Contoh:
        >>> from pathlib import Path
        >>> atomic_write_json(Path("data/test.json"), {"status": "ok"})
    """
    target = Path(file_path).resolve()
    tmp_path = target.with_name(f"{target.name}.tmp")
    bak_path = target.with_name(f"{target.name}.bak")

    # Langkah 1: Pastikan direktori induk target sudah ada
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        raise PersistenceError(
            message=f"Gagal membuat direktori folder untuk: {target.parent}",
            code=ErrorCode.WRITE_FAILED,
            details={"path": str(target), "error": str(err)},
        ) from err

    try:
        # Langkah 2: Tulis data JSON ke berkas sementara (.tmp)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            # Langkah 3: Paksa penulisan dari buffer OS ke perangkat penyimpanan fisik
            f.flush()
            os.fsync(f.fileno())

        # Langkah 4: Jika berkas target sudah ada dari sesi sebelumnya, buat salinan .bak
        if target.exists():
            shutil.copy2(target, bak_path)

        # Langkah 5: Ganti berkas target dengan berkas sementara secara atomik
        os.replace(tmp_path, target)

    except Exception as err:
        # Pembersihan kegagalan: hapus berkas .tmp agar tidak meninggalkan artefak kotor
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

        raise PersistenceError(
            message=f"Penyimpanan atomik gagal untuk berkas: {target.name}. {err}",
            code=ErrorCode.ATOMIC_WRITE_FAILED,
            details={"path": str(target), "error": str(err)},
        ) from err
