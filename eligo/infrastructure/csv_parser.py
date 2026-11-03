"""Modul Pembaca & Pengurai Berkas CSV Nilai Siswa (Robust CSV Parser).

Modul ini bertanggung jawab membaca dan memeriksa keabsahan berkas CSV (Comma-Separated Values)
yang berisi daftar nilai rapor siswa per semester untuk satu jurusan tertentu.

Penjelasan Sederhana untuk Orang Awam (Konsep Non-Teknis):
    Ketika pihak sekolah mengunggah nilai siswa menggunakan Microsoft Excel atau Google Sheets,
    file tersebut sering disimpan dalam bentuk CSV. Namun, format CSV di dunia nyata seringkali
    memiliki banyak variasi yang membingungkan komputer:
    1. Masalah Tanda Pemisah (Delimiter):
       Di komputer dengan pengaturan wilayah Indonesia, Excel biasanya memisahkan kolom dengan
       titik koma (`;`). Sedangkan di komputer standar internasional, Excel menggunakan koma (`,`).
       Sistem ini secara pintar mendeteksi otomatis tanda pemisah mana yang digunakan!
    2. Masalah Karakter Rahasia Windows (UTF-8 BOM):
       Excel di Windows sering menempelkan 3 bita tak terlihat di awal file (disebut Byte Order Mark / BOM).
       Jika tidak dibersihkan, huruf pertama dari judul kolom bisa menjadi aneh dan rusak.
       Modul ini secara otomatis membersihkan karakter rahasia tersebut.
    3. Prinsip Kumpulkan Semua Kesalahan (Collect-All Errors):
       Jika ada 100 siswa di berkas, dan terdapat 5 siswa yang nilainya salah (misalnya nilainya 150 atau kosong),
       sistem TIDAK LANGSUNG BERHENTI di kesalahan pertama. Sistem akan memeriksa seluruh 100 baris,
       mencatat semua kesalahan ke dalam sebuah daftar rapi, sehingga guru/operator sekolah bisa
       memperbaiki seluruh kesalahan tersebut sekaligus tanpa harus mengulang-ulang proses berkali-kali.

Kepatuhan Standar Rekayasa:
    - Arsitektur: Lapisan Infrastruktur (I/O berkas dan konversi format luar ke entitas domain).
    - Batasan C1: Hanya menggunakan modul standar Python (`csv`, `pathlib`) tanpa pustaka eksternal.
    - Batasan REQ-04 & REQ-05: Penanganan variasi format dan pengumpulan seluruh kesalahan per baris.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from eligo.domain.exceptions import CsvImportError, ErrorCode, RowError
from eligo.domain.models import Major, TkaStatus
from eligo.domain.normalizer import (
    normalize_class_name,
    normalize_header,
    normalize_name,
    normalize_tka_status,
)


@dataclass(frozen=True)
class ParsedStudentRow:
    """Objek Nilai yang menyimpan hasil penguraian satu baris siswa yang telah lolos validasi dasar.

    Objek ini merepresentasikan baris siswa yang bersih dan siap diproses lebih lanjut
    oleh layanan aplikasi (Application Service) untuk disimpan ke database sekolah.

    Atribut:
        row_number: Nomor baris fisik di dalam berkas CSV (1-indexed, baris 1 adalah judul kolom).
        name: Nama siswa yang telah dibersihkan dan diformat Title Case (misal: "Ahmad Fauzi").
        class_name: Nama kelas siswa berhuruf kapital (misal: "XII-MIPA-1").
        major_code: Kode jurusan siswa (misal: "MIPA").
        tka_status: Status keikutsertaan Tes Kemampuan Akademik (TkaStatus.IKUT atau TIDAK_IKUT).
        grades: Tuple berisi 5 kamus nilai (satu kamus per semester, index 0 = Semester 1).
                Format tiap semester: {"MTK": 90, "BIN": 85, "ING": 88}.
        raw_data: Data teks mentah asli dari CSV untuk keperluan audit dan pencatatan riwayat.
    """

    row_number: int
    name: str
    class_name: str
    major_code: str
    tka_status: TkaStatus
    grades: tuple[dict[str, int], ...]
    raw_data: dict[str, str]


def detect_encoding_and_delimiter(file_path: Path | str) -> tuple[str, str]:
    """Mendeteksi pengkodean karakter (encoding) dan tanda pemisah kolom (delimiter) dari berkas CSV.

    Fungsi ini melakukan pemeriksaan awal terhadap bita fisik berkas:
    1. Membaca 4 bita pertama untuk mendeteksi tanda khusus Windows UTF-8 BOM (\\xef\\xbb\\xbf).
       Jika ada, gunakan 'utf-8-sig' agar tanda tersebut otomatis dibersihkan saat dibaca.
       Jika tidak ada, gunakan 'utf-8' standar.
    2. Membaca baris pertama (judul kolom) untuk menghitung frekuensi tanda titik koma (;)
       dibandingkan koma (,). Tanda dengan kemunculan terbanyak akan dipilih sebagai pemisah resmi.

    Args:
        file_path: Lokasi berkas CSV di dalam media penyimpanan komputer.

    Returns:
        Tuple berupa (nama_encoding, tanda_pemisah), contoh: ("utf-8-sig", ";") atau ("utf-8", ",").

    Raises:
        CsvImportError: Jika berkas tidak ditemukan di lokasi yang ditentukan.
    """
    path = Path(file_path)
    if not path.exists():
        raise CsvImportError(
            message=f"Berkas CSV tidak ditemukan di lokasi: {path}",
            code=ErrorCode.FILE_NOT_FOUND,
            details={"file_path": str(path)},
        )

    # Langkah 1: Deteksi BOM (Byte Order Mark) pada bita awal
    try:
        with path.open("rb") as f:
            raw_bytes = f.read(4)
    except OSError as err:
        raise CsvImportError(
            message=f"Gagal membaca berkas CSV: {err}",
            code=ErrorCode.CSV_PARSE_ERROR,
            details={"os_error": str(err)},
        ) from err

    encoding = "utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8"

    # Langkah 2: Deteksi Delimiter (koma vs titik koma) pada baris pertama teks
    delimiter = ","
    try:
        with path.open("r", encoding=encoding, errors="replace") as f:
            first_line = f.readline()
            if first_line:
                semicolon_count = first_line.count(";")
                comma_count = first_line.count(",")
                # Jika titik koma lebih dominan, gunakan titik koma (standar Excel Indonesia)
                if semicolon_count > comma_count:
                    delimiter = ";"
                else:
                    delimiter = ","
    except OSError as err:
        raise CsvImportError(
            message=f"Gagal memeriksa baris judul CSV: {err}",
            code=ErrorCode.CSV_PARSE_ERROR,
            details={"os_error": str(err)},
        ) from err

    return encoding, delimiter


def parse_student_csv(
    file_path: Path | str,
    major: Major,
    synonyms: dict[str, str],
) -> tuple[list[ParsedStudentRow], list[RowError]]:
    """Membaca dan memvalidasi berkas CSV nilai rapor siswa berdasarkan kurikulum jurusan.

    Alur Kerja Rinci:
        1. Deteksi encoding dan pemisah kolom (delimiter) secara otomatis.
        2. Buka berkas dan baca baris judul (header).
        3. Normalisasi nama-nama kolom header (huruf kecil, hapus spasi berlebih).
        4. Periksa apakah semua kolom wajib (nama, kelas, tka, serta mata pelajaran 5 semester)
           tersedia dalam berkas CSV. Jika kolom wajib hilang, proses langsung dihentikan
           dengan melempar `CsvImportError(code='HEADER_MISMATCH')`.
        5. Memeriksa setiap baris data siswa satu per satu:
           - Mengabaikan baris kosong.
           - Memeriksa nama siswa (tidak boleh kosong).
           - Memeriksa nama kelas siswa (tidak boleh kosong).
           - Memeriksa kesesuaian kode jurusan (jika kolom jurusan ada).
           - Memeriksa status TKA terhadap daftar sinonim yang diakui.
           - Memeriksa setiap nilai mata pelajaran untuk Semester 1 sampai Semester 5:
             * Apakah selnya kosong? (GRADE_EMPTY)
             * Apakah bukan angka bulat? (GRADE_NOT_INT)
             * Apakah nilainya di luar rentang sah 0 sampai 100? (GRADE_OUT_OF_RANGE)
        6. Mengumpulkan baris yang valid ke `valid_rows` dan baris bermasalah ke `error_rows`.

    Args:
        file_path: Path berkas CSV yang diunggah oleh operator.
        major: Objek Major kurikulum jurusan yang dipilih (memuat daftar mapel semester 1-5).
        synonyms: Kamus variasi penulisan status TKA (misal {"ikut": "IKUT", "ya": "IKUT"}).

    Returns:
        Tuple berisi (daftar_baris_valid, daftar_kesalahan_per_baris).
        - daftar_baris_valid: Kumpulan objek `ParsedStudentRow` yang siap diimpor.
        - daftar_kesalahan_per_baris: Kumpulan objek `RowError` untuk dilaporkan kepada operator.

    Raises:
        CsvImportError: Jika berkas kosong atau format header tidak sesuai dengan kurikulum jurusan.
    """
    path = Path(file_path)
    encoding, delimiter = detect_encoding_and_delimiter(path)

    # 1. Bangun daftar kolom yang diharapkan sesuai kurikulum jurusan
    # Semester 1 sampai 5 (index 0..4 pada major.subjects)
    expected_grade_columns: dict[tuple[int, str], str] = {}
    for sem_idx, semester_subjects in enumerate(major.subjects):
        sem_num = sem_idx + 1
        for subject in semester_subjects:
            key_name = f"sem{sem_num}_{subject.code.lower()}"
            expected_grade_columns[(sem_idx, subject.code)] = key_name

    try:
        with path.open("r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                raw_headers = next(reader)
            except StopIteration:
                raise CsvImportError(
                    message="Berkas CSV kosong, tidak memuat data sama sekali.",
                    code=ErrorCode.CSV_PARSE_ERROR,
                    details={"file_path": str(path)},
                ) from None

            # Normalisasi header
            headers = [normalize_header(h) for h in raw_headers]
            header_map: dict[str, int] = {h: idx for idx, h in enumerate(headers) if h}

            # Validasi keberadaan kolom wajib
            missing_headers: list[str] = []
            if "nama" not in header_map:
                missing_headers.append("nama")
            if "kelas" not in header_map:
                missing_headers.append("kelas")

            # Periksa kolom TKA (toleransi nama kolom: 'tka' atau 'tka_status')
            tka_col_name = "tka_status" if "tka_status" in header_map else "tka"
            if tka_col_name not in header_map:
                missing_headers.append("tka_status / tka")

            # Periksa kelengkapan seluruh mata pelajaran 5 semester
            for (_sem_idx, _subj_code), expected_col in expected_grade_columns.items():
                if expected_col not in header_map:
                    missing_headers.append(expected_col)

            if missing_headers:
                missing_str = ", ".join(missing_headers)
                raise CsvImportError(
                    message=(
                        f"Format kolom CSV tidak sesuai dengan kurikulum jurusan '{major.name}'. "
                        f"Kolom yang belum ada atau salah nama: [{missing_str}]."
                    ),
                    code=ErrorCode.HEADER_MISMATCH,
                    details={
                        "major_code": major.code,
                        "missing_columns": missing_headers,
                        "detected_headers": headers,
                    },
                )

            valid_rows: list[ParsedStudentRow] = []
            error_rows: list[RowError] = []

            # 2. Proses baris data (baris ke-2 dst)
            for row_idx, row in enumerate(reader, start=2):
                # Abaikan baris yang sepenuhnya kosong
                if not row or not any(cell.strip() for cell in row):
                    continue

                row_dict: dict[str, str] = {}
                for h_name, col_idx in header_map.items():
                    if col_idx < len(row):
                        row_dict[h_name] = row[col_idx].strip()
                    else:
                        row_dict[h_name] = ""

                current_row_errors: list[RowError] = []

                # Validasi Kolom Nama
                raw_name = row_dict.get("nama", "")
                norm_name = normalize_name(raw_name)
                if not norm_name:
                    current_row_errors.append(
                        RowError(
                            row_number=row_idx,
                            column_name="nama",
                            raw_value=raw_name,
                            error_code=ErrorCode.NAME_EMPTY,
                            message="Nama siswa tidak boleh kosong.",
                        )
                    )

                # Validasi Kolom Kelas
                raw_class = row_dict.get("kelas", "")
                norm_class = normalize_class_name(raw_class)
                if not norm_class:
                    current_row_errors.append(
                        RowError(
                            row_number=row_idx,
                            column_name="kelas",
                            raw_value=raw_class,
                            error_code=ErrorCode.NAME_EMPTY,
                            message="Nama kelas siswa tidak boleh kosong.",
                        )
                    )

                # Validasi Kolom Jurusan (jika dicantumkan di CSV)
                if "jurusan" in header_map:
                    raw_major = row_dict.get("jurusan", "")
                    if raw_major and raw_major.upper() != major.code.upper():
                        current_row_errors.append(
                            RowError(
                                row_number=row_idx,
                                column_name="jurusan",
                                raw_value=raw_major,
                                error_code=ErrorCode.MAJOR_NOT_FOUND,
                                message=(
                                    f"Jurusan '{raw_major}' tidak cocok dengan "
                                    f"jurusan impor saat ini ('{major.code}')."
                                ),
                            )
                        )

                # Validasi Status TKA
                raw_tka = row_dict.get(tka_col_name, "")
                tka_enum = normalize_tka_status(raw_tka, synonyms, raise_on_unknown=False)
                if tka_enum is None:
                    valid_opts = ", ".join(sorted(synonyms.keys()))
                    current_row_errors.append(
                        RowError(
                            row_number=row_idx,
                            column_name=tka_col_name,
                            raw_value=raw_tka,
                            error_code=ErrorCode.TKA_SYNONYM_UNKNOWN,
                            message=(
                                f"Status TKA '{raw_tka}' tidak dikenal. "
                                f"Gunakan salah satu dari: {valid_opts}."
                            ),
                        )
                    )

                # Validasi Nilai Rapor Semester 1 sampai 5
                # Struktur semester_grades: 5 kamus nilai (index 0 = Sem 1)
                parsed_semesters: list[dict[str, int]] = [{} for _ in range(5)]
                for (sem_idx, subj_code), expected_col in expected_grade_columns.items():
                    raw_val = row_dict.get(expected_col, "")
                    if not raw_val:
                        current_row_errors.append(
                            RowError(
                                row_number=row_idx,
                                column_name=expected_col,
                                raw_value=raw_val,
                                error_code=ErrorCode.GRADE_EMPTY,
                                message=f"Nilai {subj_code} Semester {sem_idx + 1} kosong.",
                            )
                        )
                        continue

                    # Periksa apakah nilai adalah integer yang sah
                    if "." in raw_val or "," in raw_val:
                        current_row_errors.append(
                            RowError(
                                row_number=row_idx,
                                column_name=expected_col,
                                raw_value=raw_val,
                                error_code=ErrorCode.GRADE_NOT_INT,
                                message=(
                                    f"Nilai {subj_code} Semester {sem_idx + 1} "
                                    f"harus bilangan bulat utuh, ditemukan '{raw_val}'."
                                ),
                            )
                        )
                        continue

                    try:
                        int_val = int(raw_val)
                    except ValueError:
                        current_row_errors.append(
                            RowError(
                                row_number=row_idx,
                                column_name=expected_col,
                                raw_value=raw_val,
                                error_code=ErrorCode.GRADE_NOT_INT,
                                message=(
                                    f"Nilai {subj_code} Semester {sem_idx + 1} "
                                    f"harus angka, ditemukan '{raw_val}'."
                                ),
                            )
                        )
                        continue

                    # Periksa rentang 0 sampai 100
                    if int_val < 0 or int_val > 100:
                        current_row_errors.append(
                            RowError(
                                row_number=row_idx,
                                column_name=expected_col,
                                raw_value=raw_val,
                                error_code=ErrorCode.GRADE_OUT_OF_RANGE,
                                message=(
                                    f"Nilai {subj_code} Semester {sem_idx + 1} ({int_val}) "
                                    "di luar batas sah 0-100."
                                ),
                            )
                        )
                        continue

                    parsed_semesters[sem_idx][subj_code] = int_val

                # Evaluasi hasil baris: jika ada error, kumpulkan ke error_rows
                if current_row_errors:
                    error_rows.extend(current_row_errors)
                else:
                    # Baris bersih sempurna: buat objek ParsedStudentRow
                    assert tka_enum is not None
                    parsed_row = ParsedStudentRow(
                        row_number=row_idx,
                        name=norm_name,
                        class_name=norm_class,
                        major_code=major.code,
                        tka_status=tka_enum,
                        grades=tuple(parsed_semesters),
                        raw_data=row_dict,
                    )
                    valid_rows.append(parsed_row)

    except OSError as err:
        raise CsvImportError(
            message=f"Kesalahan sistem saat membaca berkas CSV: {err}",
            code=ErrorCode.CSV_PARSE_ERROR,
            details={"os_error": str(err)},
        ) from err

    return valid_rows, error_rows


def generate_csv_template(major: Major) -> str:
    """Membuat teks template berkas CSV standar berdasarkan kurikulum jurusan.

    Template ini dapat diunduh atau diekspor oleh operator sekolah sehingga guru
    memiliki panduan kolom yang pasti saat mengisi nilai rapor siswa.

    Args:
        major: Objek Major kurikulum jurusan.

    Returns:
        String isi berkas CSV lengkap dengan baris header dan 1 baris contoh data fiktif.
    """
    headers = ["nama", "kelas", "jurusan"]
    example_row = ["Ahmad Fauzi", "XII-MIPA-1", major.code]

    for sem_idx, semester_subjects in enumerate(major.subjects):
        sem_num = sem_idx + 1
        for subject in semester_subjects:
            headers.append(f"sem{sem_num}_{subject.code.lower()}")
            example_row.append("85")

    headers.append("tka_status")
    example_row.append("ikut")

    return ",".join(headers) + "\n" + ",".join(example_row) + "\n"
