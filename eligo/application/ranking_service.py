"""Layanan Pipeline Pemeringkatan Siswa Eligible SNBP (Application Ranking Service).

Modul ini adalah jantung utama dari sistem Eligo. Bertanggung jawab memadukan
seluruh aturan regulasi resmi SNBP Kemendikbudristek untuk memproses, menghitung nilai,
mengurutkan peringkat, mengalokasikan kuota sekolah, dan menetapkan status kelayakan siswa.

Penjelasan Sederhana untuk Orang Awam (Bagaimana Siswa Diurutkan dan Dipilih?):
    Bayangkan ada 100 siswa di jurusan MIPA sebuah SMA berakreditasi A:

    Langkah 1 - Pemisahan Siswa yang Ikut TKA (Tes Kemampuan Akademik):
        Hanya siswa yang memilih ikut TKA yang berhak masuk ke dalam pemeringkatan kuota SNBP.
        Siswa yang tidak ikut TKA otomatis diberi label abu-abu (Non-Eligible) dan tidak memiliki peringkat.

    Langkah 2 - Perhitungan Nilai Rapor & Tambahan Prestasi:
        - Nilai rapor semester 1 sampai semester 5 dihitung rata-ratanya dengan pembulatan matematis
          2 desimal (menggunakan tipe data Decimal agar adil dan tidak ada pembulatan liar komputer).
        - Jika sekolah mengaktifkan opsi prestasi, sertifikat juara (tingkat kabupaten sampai internasional)
          diberi poin bonus (maksimal hingga 2.00 poin tambahan).
        - Nilai rapor + poin prestasi = Nilai Akhir siswa.

    Langkah 3 - Pengurutan Peringkat Berkeadilan (Merge Sort Mandiri):
        Siswa diurutkan dari nilai tertinggi ke terendah. Jika ada dua siswa yang nilainya SAMA PERSIS,
        sistem memecahkan seri (tie-breaker) secara adil berdasarkan aturan resmi pemerintah:
        1. Nilai akhir tertinggi menang.
        2. Jika masih sama, lihat nilai rapor Semester 5 yang lebih tinggi.
        3. Jika masih sama, lihat Semester 4, lalu Semester 3, 2, dan 1.
        4. Jika seluruh nilai 5 semester masih sama persis, urutkan berdasarkan abjad nama.

    Langkah 4 - Menghitung Jatah Kuota Sekolah:
        Sekolah Akreditasi A mendapat kuota 40%. Jika sekolah menggunakan e-Rapor resmi,
        pemerintah memberikan bonus kuota +5%, sehingga total kuota menjadi 45%.
        Dari 100 siswa, 45% x 100 = 45 siswa berhak mendaftar SNBP!

    Langkah 5 - Menentukan Status Warna (Lampu Lalu Lintas):
        - HIJAU (Peringkat 1 s.d. 45): Siswa ELIGIBLE (berhak mendaftar SNBP ke perguruan tinggi).
        - KUNING (Peringkat 46 s.d. 100): Siswa CADANGAN (ikut TKA namun berada di luar kuota).
        - ABU-ABU: Siswa yang dari awal tidak mengikuti TKA.

Kepatuhan Standar Rekayasa:
    - Arsitektur: Lapisan Aplikasi (Pure Orchestration tanpa operasi I/O).
    - C3: Menggunakan algoritma Merge Sort mandiri dari `domain/sorter.py`.
    - ADR-01: Aritmetika skor 100% menggunakan `decimal.Decimal` presisi tinggi.
    - REQ-06 & REQ-07: Pipeline deterministik dan pencarian nama via Binary Search O(log n).
"""

from __future__ import annotations

from decimal import Decimal

from eligo.domain.calculator import (
    compute_achievement_points,
    compute_final_score,
    compute_report_score,
    compute_semester_score,
)
from eligo.domain.models import (
    AppConfig,
    EligibilityStatus,
    RankingResult,
    SchoolProfile,
    Student,
    TkaStatus,
)
from eligo.domain.normalizer import normalize_name
from eligo.domain.quota import (
    assign_eligibility_status,
    compute_effective_percentage,
    compute_quota,
)
from eligo.domain.searcher import binary_search_by_name
from eligo.domain.sorter import build_sort_key, merge_sort


def run_ranking_pipeline(
    students: list[Student],
    profile: SchoolProfile,
    config: AppConfig,
) -> tuple[list[RankingResult], int]:
    """Menjalankan seluruh alur pipa (pipeline) pemeringkatan siswa eligible SNBP.

    Fungsi ini murni (pure function tanpa I/O) yang menerima data siswa dan profil
    sekolah, lalu mengembalikan daftar hasil pemeringkatan lengkap beserta jumlah kuota.

    Tahapan Eksekusi:
        1. Memisahkan siswa TKA (TkaStatus.IKUT) dan non-TKA (TkaStatus.TIDAK_IKUT).
        2. Menghitung skor S1..S5, rerata rapor, poin prestasi, dan skor akhir untuk siswa TKA.
        3. Mengurutkan siswa TKA menggunakan algoritma Merge Sort mandiri dan kunci komparasi
           multi-kriteria leksikografis (SortKey).
        4. Menghitung persentase efektif kuota dan jumlah kursi kuota yang dialokasikan.
        5. Menetapkan peringkat (1..N) dan status kelayakan (HIJAU untuk masuk kuota, KUNING untuk cadangan).
        6. Mengonversi siswa non-TKA menjadi hasil berstatus ABU_ABU (rank None).
        7. Menggabungkan hasil akhir: peserta TKA terurut diikuti oleh siswa non-TKA.

    Args:
        students: Daftar lengkap seluruh siswa pada angkatan/jurusan yang diproses.
        profile: Profil data sekolah (akreditasi, e-rapor aktif, dan opsi prestasi).
        config: Parameter konfigurasi bisnis dari data/config.json.

    Returns:
        Tuple berupa:
        - all_results: Daftar objek `RankingResult` untuk seluruh siswa (TKA + Non-TKA).
        - quota: Jumlah kursi siswa berstatus HIJAU yang berhak lolos kuota SNBP.
    """
    if not students:
        return [], 0

    # --------------------------------------------------------------------------
    # FASE 1: Partisi Siswa (Peserta TKA vs Non-TKA)
    # --------------------------------------------------------------------------
    tka_students: list[Student] = []
    non_tka_students: list[Student] = []

    for s in students:
        if s.tka_status == TkaStatus.IKUT:
            tka_students.append(s)
        else:
            non_tka_students.append(s)

    # --------------------------------------------------------------------------
    # FASE 2: Hitung Nilai Rapor & Prestasi untuk Peserta TKA
    # --------------------------------------------------------------------------
    partial_tka_results: list[RankingResult] = []

    for s in tka_students:
        # Hitung rata-rata nilai untuk tiap semester (1 sampai 5)
        semester_scores_list: list[Decimal] = []
        for sem_idx in range(5):
            sem_grades = s.grades[sem_idx] if sem_idx < len(s.grades) else {}
            sem_score = compute_semester_score(sem_grades)
            semester_scores_list.append(sem_score)

        sem_scores_tuple = tuple(semester_scores_list)

        # Hitung rerata rapor dari 5 semester
        report_score = compute_report_score(sem_scores_tuple)

        # Hitung bonus sertifikat prestasi jika opsi prestasi sekolah aktif
        ach_points = compute_achievement_points(
            achievements=s.achievements,
            weights=config.achievement_weights,
            max_points=config.achievement_max_points,
            achievement_enabled=profile.achievement_enabled,
        )

        # Skor Akhir = Nilai Rapor + Poin Prestasi
        final_score = compute_final_score(report_score, ach_points)

        partial_tka_results.append(
            RankingResult(
                student=s,
                semester_scores=sem_scores_tuple,
                report_score=report_score,
                achievement_points=ach_points,
                final_score=final_score,
                rank=None,  # Akan diisi di Fase 5
                status=EligibilityStatus.KUNING,  # Placeholder sementara
            )
        )

    # --------------------------------------------------------------------------
    # FASE 3: Urutkan Peserta TKA Menggunakan Merge Sort Mandiri
    # --------------------------------------------------------------------------
    # Menggunakan build_sort_key: (-final_score, -S5, -S4, -S3, -S2, -S1, nama, id)
    sorted_tka: list[RankingResult] = merge_sort(
        items=partial_tka_results,
        key_func=build_sort_key,
    )

    # --------------------------------------------------------------------------
    # FASE 4: Hitung Alokasi Kuota Kursi Sekolah
    # --------------------------------------------------------------------------
    # Ambil persentase dasar berdasarkan akreditasi sekolah (misal A = 0.40)
    accreditation_key = profile.accreditation.value
    base_pct = config.quota_percentages.get(accreditation_key, Decimal("0.00"))

    # Hitung persentase efektif (ditambah bonus e-Rapor jika aktif)
    eff_percentage = compute_effective_percentage(
        base_percentage=base_pct,
        e_rapor_bonus=config.e_rapor_bonus_percentage,
        e_rapor_active=profile.e_rapor_active,
    )

    # Hitung kuota berdasarkan TOTAL SELURUH SISWA (bukan hanya peserta TKA)
    total_batch_students = len(students)
    quota = compute_quota(
        total_students=total_batch_students,
        effective_percentage=eff_percentage,
        rounding_mode=config.quota_rounding_mode,
    )

    # --------------------------------------------------------------------------
    # FASE 5: Tetapkan Peringkat (Rank) & Status Kelayakan Siswa TKA
    # --------------------------------------------------------------------------
    # Siswa peringkat 1..kuota mendapat HIJAU, sisanya KUNING
    ranked_tka = assign_eligibility_status(
        sorted_tka_results=sorted_tka,
        quota=quota,
    )

    # --------------------------------------------------------------------------
    # FASE 6: Konversi Siswa Non-TKA (Status ABU_ABU, rank None)
    # --------------------------------------------------------------------------
    abu_abu_results: list[RankingResult] = []
    for s in non_tka_students:
        # Hitung nilai rapor informatif untuk siswa non-TKA jika datanya tersedia
        semester_scores_list = []
        for sem_idx in range(5):
            sem_grades = s.grades[sem_idx] if sem_idx < len(s.grades) else {}
            sem_score = compute_semester_score(sem_grades)
            semester_scores_list.append(sem_score)

        sem_scores_tuple = tuple(semester_scores_list)
        report_score = compute_report_score(sem_scores_tuple)

        abu_abu_results.append(
            RankingResult(
                student=s,
                semester_scores=sem_scores_tuple,
                report_score=report_score,
                achievement_points=Decimal("0.00"),  # Siswa non-TKA tidak mendapat poin prestasi
                final_score=report_score,
                rank=None,  # Siswa non-TKA tidak memiliki peringkat kuota
                status=EligibilityStatus.ABU_ABU,
            )
        )

    # --------------------------------------------------------------------------
    # FASE 7: Gabungkan Hasil Akhir
    # --------------------------------------------------------------------------
    all_results = ranked_tka + abu_abu_results
    return all_results, quota


def search_student_in_results(
    results: list[RankingResult],
    target_name: str,
) -> RankingResult | None:
    """Mencari data siswa tertentu dalam hasil pemeringkatan menggunakan algoritma Binary Search.

    Agar pencarian sangat cepat (kompleksitas O(log n)), daftar hasil pemeringkatan
    disalin dan diurutkan berdasarkan abjad nama siswa (A sampai Z) terlebih dahulu,
    kemudian fungsi `binary_search_by_name` dipanggil untuk mencocokkan nama secara persis.

    Args:
        results: Daftar hasil pemeringkatan seluruh siswa.
        target_name: Nama siswa yang dicari (pencarian toleran terhadap spasi dan variasi huruf).

    Returns:
        Objek `RankingResult` jika siswa ditemukan, atau `None` jika tidak ada.
    """
    if not results or not target_name or not target_name.strip():
        return None

    # Urutkan salinan list berdasarkan abjad nama (A-Z) untuk prasyarat Binary Search
    # Penggunaan sorted() diizinkan pada lapisan Application dan Presentation
    sorted_by_name = sorted(results, key=lambda r: normalize_name(r.student.name).lower())

    idx = binary_search_by_name(sorted_by_name, target_name)
    if idx != -1:
        return sorted_by_name[idx]

    return None
