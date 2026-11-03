"""Lapisan Aplikasi (Application Layer) Eligo.

Lapisan ini berfungsi sebagai orkestrator alur kerja (use cases) sistem.
Bertanggung jawab mengoordinasikan interaksi antara domain logic murni dan antarmuka
infrastruktur/repositori tanpa membocorkan detail teknis persistensi atau tampilan UI.

Tanggung Jawab Modul:
    - school_service: Manajemen profil sekolah dan kurikulum jurusan.
    - student_service: Manajemen data induk siswa dan nilai rapor.
    - ranking_service: Eksekusi pipeline pemeringkatan siswa eligible SNBP.
    - import_service: Orkestrasi impor data CSV (parse, validate, duplicate resolution).
    - config_service: Penyediaan parameter konfigurasi sistem.
"""
