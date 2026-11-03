"""Lapisan Infrastruktur (Infrastructure Layer) Eligo.

Lapisan ini menangani seluruh interaksi dengan sistem luar, termasuk persistensi data
ke media penyimpanan lokal (JSON storage dengan atomic write dan cadangan otomatis .bak),
pemrosesan berkas eksternal (CSV parser dengan penanganan BOM dan deteksi separator).
"""
