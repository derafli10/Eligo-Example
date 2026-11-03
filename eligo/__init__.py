"""Paket Utama Sistem Pemeringkatan Siswa Eligible SNBP (Eligo).

Sistem ini dirancang untuk memproses, memeringkatkan, dan menentukan status kelayakan
siswa SMA/SMK/MA untuk pendaftaran SNBP (Seleksi Nasional Berdasarkan Prestasi) sesuai
dengan ketentuan regulasi resmi Kemendikbudristek dan SNPMB.

Arsitektur Sistem:
    Mengadopsi pola Clean / Hexagonal Architecture:
    Presentation (CLI) -> Application (Services) -> Domain (Logic) <- Infrastructure.
"""

__version__ = "1.0.0"
