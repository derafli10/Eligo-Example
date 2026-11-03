"""Repositori Profil dan Kurikulum Sekolah Berbasis Berkas JSON (JsonSchoolRepository).

Modul ini bertanggung jawab membaca dan menyimpan data profil sekolah (`data/school.json`),
termasuk akreditasi, status e-rapor, dan struktur mata pelajaran 5 semester per jurusan.

Prinsip Rekayasa Enterprise:
    1. Disaster Recovery (Pemulihan Otomatis dari .bak):
       Jika berkas `school.json` mengalami korupsi data (misal akibat crash atau terpotong),
       sistem secara otomatis mencoba membaca berkas cadangan `school.json.bak`.
       Jika cadangan valid, berkas utama langsung dipulihkan secara transparan.
       Jika kedua berkas rusak, lemparkan `CorruptBackupError(code="BACKUP_CORRUPT")`.
    2. Atomic Persistence:
       Setiap penyimpanan profil sekolah menggunakan `atomic_write_json` untuk mencegah
       kerusakan berkas jika terjadi interupsi daya.
    3. Nullable on Initial Setup:
       Jika berkas sekolah sama sekali belum dibuat (aplikasi baru pertama kali dibuka),
       metode `load()` mengembalikan `None` tanpa melempar exception agar antarmuka
       CLI dapat mengarahkan operator ke wizard penyiapan awal profil sekolah.

Penjelasan Sederhana untuk Orang Awam:
    Modul ini adalah buku arsip profil sekolah. Jika berkas data sekolah rusak (misal
    karena komputer tiba-tiba mati saat sedang menyimpan), modul ini tidak langsung panik,
    melainkan secara otomatis mencari berkas fotokopi cadangan (`.bak`) dan memperbaiki
    berkas utama kembali seperti semula!
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eligo.domain.exceptions import CorruptBackupError, ErrorCode
from eligo.domain.models import (
    Accreditation,
    Major,
    SchoolProfile,
    SchoolType,
    Subject,
)
from eligo.domain.repositories import SchoolRepository
from eligo.infrastructure.atomic_writer import atomic_write_json

logger = logging.getLogger(__name__)


class JsonSchoolRepository(SchoolRepository):
    """Implementasi SchoolRepository berbasis JSON dengan kemampuan pemulihan otomatis."""

    def __init__(self, file_path: Path | str = "data/school.json") -> None:
        """Inisialisasi repositori sekolah dengan path berkas target.

        Args:
            file_path: Lokasi berkas school.json (default: 'data/school.json').
        """
        self._path = Path(file_path).resolve()
        self._bak_path = self._path.with_name(f"{self._path.name}.bak")

    @property
    def file_path(self) -> Path:
        """Mengembalikan Path berkas utama."""
        return self._path

    def load(self) -> SchoolProfile | None:
        """Memuat profil sekolah dengan mekanisme pemulihan otomatis dari berkas .bak.

        Alur:
            1. Coba baca berkas utama `school.json`.
            2. Jika berkas utama tidak ada dan tidak ada `.bak`, kembalikan None.
            3. Jika berkas utama rusak / gagal diparse, coba baca `school.json.bak`.
            4. Jika `.bak` berhasil dibaca, pulihkan berkas utama menggunakan `atomic_write_json`.
            5. Jika berkas utama dan `.bak` keduanya rusak, lemparkan `CorruptBackupError`.

        Returns:
            Objek SchoolProfile jika data tersedia, atau None jika sistem belum diinisialisasi.

        Raises:
            CorruptBackupError: Jika berkas utama korup dan cadangan juga korup/tidak valid.
        """
        main_corrupted = False

        # Upaya 1: Baca berkas utama
        if self._path.exists():
            try:
                data = self._read_and_deserialize(self._path)
                return data
            except Exception as err:
                logger.warning(
                    f"Berkas profil sekolah utama '{self._path}' rusak: {err}. Mencoba pemulihan dari .bak..."
                )
                main_corrupted = True

        # Upaya 2: Jika berkas utama rusak atau tidak ada, cek berkas cadangan (.bak)
        if self._bak_path.exists():
            try:
                restored_profile = self._read_and_deserialize(self._bak_path)
                logger.info(f"Berhasil memulihkan profil sekolah dari: {self._bak_path}")

                # Pulihkan berkas utama secara atomik
                self.save(restored_profile)
                return restored_profile
            except Exception as bak_err:
                logger.error(f"Berkas cadangan '{self._bak_path}' juga rusak: {bak_err}")
                if main_corrupted:
                    raise CorruptBackupError(
                        message=(
                            f"Berkas profil sekolah '{self._path.name}' dan berkas cadangan "
                            f"'{self._bak_path.name}' keduanya korup atau tidak dapat dibaca."
                        ),
                        code=ErrorCode.BACKUP_CORRUPT,
                        details={
                            "main_path": str(self._path),
                            "bak_path": str(self._bak_path),
                            "bak_error": str(bak_err),
                        },
                    ) from bak_err

        # Jika berkas utama korup tapi tidak ada cadangan sama sekali
        if main_corrupted:
            raise CorruptBackupError(
                message=(
                    f"Berkas profil sekolah '{self._path.name}' rusak dan tidak ditemukan "
                    f"berkas cadangan ({self._bak_path.name}) untuk pemulihan."
                ),
                code=ErrorCode.BACKUP_CORRUPT,
                details={"main_path": str(self._path)},
            )

        # Berkas belum pernah dibuat sama sekali (inisialisasi awal)
        return None

    def save(self, profile: SchoolProfile) -> None:
        """Simpan profil sekolah ke berkas JSON menggunakan penulisan atomik.

        Args:
            profile: Objek SchoolProfile yang akan disimpan.

        Raises:
            PersistenceError: Jika penulisan ke disk fisik gagal.
        """
        payload = self._serialize_profile(profile)
        atomic_write_json(self._path, payload, indent=2)

    def get_profile(self) -> SchoolProfile | None:
        """Alias fungsional untuk metode `load()` sesuai kontrak Protocol."""
        return self.load()

    def save_profile(self, profile: SchoolProfile) -> None:
        """Alias fungsional untuk metode `save()` sesuai kontrak Protocol."""
        self.save(profile)

    # --------------------------------------------------------------------------
    # Metode Internal Serialisasi & Deserialisasi
    # --------------------------------------------------------------------------

    def _read_and_deserialize(self, path: Path) -> SchoolProfile:
        """Baca berkas JSON dari path dan konversi ke entitas domain SchoolProfile."""
        with open(path, encoding="utf-8") as f:
            payload: dict[str, Any] = json.load(f)

        schema_version = payload.get("schema_version")
        if schema_version != 1:
            raise ValueError(
                f"Versi skema tidak didukung: {schema_version} (wajib versi 1)."
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Payload 'data' harus berupa dictionary.")

        # Parsing daftar jurusan dan mapel per semester
        majors_list: list[Major] = []
        for m_raw in data.get("majors", []):
            semesters_subjects: list[tuple[Subject, ...]] = []
            for sem_raw in m_raw.get("subjects", []):
                subj_tuple = tuple(
                    Subject(code=s["code"], name=s["name"])
                    for s in sem_raw
                )
                semesters_subjects.append(subj_tuple)

            major = Major(
                code=str(m_raw["code"]),
                name=str(m_raw["name"]),
                subjects=tuple(semesters_subjects),
            )
            majors_list.append(major)

        return SchoolProfile(
            name=str(data["name"]),
            school_type=SchoolType(str(data["school_type"]).upper()),
            accreditation=Accreditation(str(data["accreditation"]).upper()),
            e_rapor_active=bool(data["e_rapor_active"]),
            achievement_enabled=bool(data["achievement_enabled"]),
            majors=tuple(majors_list),
        )

    def _serialize_profile(self, profile: SchoolProfile) -> dict[str, Any]:
        """Konversi entitas SchoolProfile ke struktur dictionary siap JSON."""
        majors_data = []
        for major in profile.majors:
            semesters_data = []
            for sem in major.subjects:
                sem_subjects = [
                    {"code": subj.code, "name": subj.name}
                    for subj in sem
                ]
                semesters_data.append(sem_subjects)

            majors_data.append(
                {
                    "code": major.code,
                    "name": major.name,
                    "subjects": semesters_data,
                }
            )

        return {
            "schema_version": 1,
            "last_updated": datetime.now(UTC).isoformat(),
            "data": {
                "name": profile.name,
                "school_type": profile.school_type.value,
                "accreditation": profile.accreditation.value,
                "e_rapor_active": profile.e_rapor_active,
                "achievement_enabled": profile.achievement_enabled,
                "majors": majors_data,
            },
        }
