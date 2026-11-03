"""Kerangka Menu Utama & Handler Gangguan Global (CLI Main Entry Point).

Modul ini adalah pusat kendali antarmuka terminal interaktif berbasis teks (Rich CLI).
Bertanggung jawab menampilkan navigasi menu utama, menghubungkan operator ke berbagai
layanan sistem, dan menangani interupsi papan tombol (Ctrl+C / KeyboardInterrupt) secara aman.

Penjelasan Sederhana untuk Orang Awam:
    Bayangkan modul ini seperti "Lobi Resepsionis" di gedung sekolah:
    1. Menu Pilihan Terpadu:
       Saat program dibuka, layar menampilkan menu rapi dengan nomor pilihan (1 sampai 5):
       - Menu 1: Profil Sekolah & Pengaturan Kuota
       - Menu 2: Buku Induk & Manajemen Data Siswa
       - Menu 3: Unggah Nilai dari Berkas Excel/CSV
       - Menu 4: Papan Peringkat & Hasil Seleksi SNBP
       - Menu 5: Reset Seluruh Data (Hapus Permanen)
       - Menu 0: Keluar dari Aplikasi
    2. Tombol Darurat yang Aman (Ctrl+C):
       Jika operator sedang mengetik lalu berubah pikiran dan menekan tombol Ctrl+C,
       program TIDAK AKAN RUSAK atau memunculkan tulisan error bahasa Inggris yang menakutkan
       (Traceback Error). Sistem menangkap tombol tersebut dengan tenang, menampilkan pesan ramah:
       "Operasi dibatalkan oleh pengguna. Kembali ke menu utama...", dan data sekolah tetap aman.

Kepatuhan Standar Rekayasa:
    - Arsitektur: Lapisan Presentasi (CLI Presentation Boundary).
    - C1: Penggunaan pustaka `rich` terisolasi murni di folder presentation/cli/.
    - REQ-14: Tangkapan KeyboardInterrupt di satu titik global tanpa dirty state.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from eligo.domain.exceptions import EligoError
from eligo.infrastructure.repositories.config_repo import JsonConfigRepository
from eligo.infrastructure.repositories.school_repo import JsonSchoolRepository
from eligo.infrastructure.repositories.student_repo import JsonStudentRepository
from eligo.presentation.cli.menu_import import display_import_menu
from eligo.presentation.cli.menu_ranking import display_ranking_menu
from eligo.presentation.cli.menu_reset import display_reset_menu
from eligo.presentation.cli.menu_school import display_school_menu
from eligo.presentation.cli.menu_student import display_student_menu


def print_welcome_banner(console: Console) -> None:
    """Mencetak spanduk selamat datang dan identitas sistem pemeringkatan Eligo."""
    banner_text = (
        "[bold cyan]SISTEM PEMERINGKATAN SISWA ELIGIBLE SNBP (ELIGO)[/bold cyan]\n"
        "[white]Aplikasi Resmi Penentuan Kuota & Peringkat Seleksi Nasional Berdasarkan Prestasi[/white]\n"
        "[dim]Sesuai Regulasi Kemendikbudristek • Algoritma Mandiri • Penyimpanan Aman[/dim]"
    )
    console.print(
        Panel(
            banner_text,
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


def print_main_menu_options(console: Console) -> None:
    """Menampilkan pilihan menu utama kepada operator."""
    menu_text = (
        "[bold green]1.[/bold green] Profil Sekolah, Akreditasi & Kurikulum Jurusan\n"
        "[bold green]2.[/bold green] Buku Induk Siswa (Lihat, Tambah, Ubah, Hapus)\n"
        "[bold green]3.[/bold green] Unggah / Impor Nilai Rapor Siswa dari Berkas CSV\n"
        "[bold green]4.[/bold green] Papan Peringkat SNBP, Filter Status & Pencarian Siswa\n"
        "[bold yellow]5.[/bold yellow] Reset Seluruh Data (Hapus Permanen)\n"
        "[bold red]0.[/bold red] Keluar dari Aplikasi"
    )
    console.print(
        Panel(
            menu_text,
            title="[bold yellow]MENU UTAMA[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def main_loop(
    console: Console,
    school_repo: JsonSchoolRepository | None = None,
    student_repo: JsonStudentRepository | None = None,
    config_repo: JsonConfigRepository | None = None,
) -> None:
    """Perulangan utama interaksi pengguna (Main Application Loop).

    Fungsi ini terus berjalan menyajikan menu hingga operator secara sadar
    memilih opsi '0' untuk keluar.

    Args:
        console: Objek Rich Console untuk perenderan visual.
        school_repo: Repositori profil sekolah (opsional, default ke data/school.json).
        student_repo: Repositori siswa (opsional, default ke data/students.json).
        config_repo: Repositori konfigurasi (opsional, default ke data/config.json).
    """
    s_repo = school_repo or JsonSchoolRepository("data/school.json")
    st_repo = student_repo or JsonStudentRepository("data/students.json")
    c_repo = config_repo or JsonConfigRepository("data/config.json")

    while True:
        try:
            print_main_menu_options(console)
            choice = Prompt.ask(
                "[bold cyan]Pilih nomor menu yang Anda inginkan[/bold cyan]",
                choices=["0", "1", "2", "3", "4", "5"],
                default="4",
                console=console,
            )

            if choice == "0":
                console.print("\n[bold green]Terima kasih telah menggunakan Sistem Eligo. Sampai jumpa![/bold green]\n")
                break
            elif choice == "1":
                display_school_menu(console, s_repo, c_repo)
            elif choice == "2":
                display_student_menu(console, st_repo, s_repo, c_repo)
            elif choice == "3":
                display_import_menu(console, st_repo, s_repo, c_repo)
            elif choice == "4":
                display_ranking_menu(console, st_repo, s_repo, c_repo)
            elif choice == "5":
                display_reset_menu(console)

        except KeyboardInterrupt:
            # Titik penangkap pembatalan lokal: operator menekan Ctrl+C saat berada di sub-menu
            console.print("\n[yellow]⚠️ Operasi dibatalkan oleh pengguna. Kembali ke menu utama...[/yellow]\n")
            continue
        except EligoError as err:
            console.print(
                Panel(
                    f"[bold red]Terjadi Kesalahan Sistem:[/bold red] {err.message}\n"
                    f"[dim]Kode Kesalahan: {err.code}[/dim]",
                    title="[bold red]❌ PEMBERITAHUAN KESALAHAN[/bold red]",
                    border_style="red",
                )
            )


def run_app() -> None:
    """Titik masuk eksekusi utama aplikasi terminal (CLI Application Runner).

    Fungsi ini adalah gerbang tunggal yang membungkus seluruh siklus hidup aplikasi
    dengan penanganan `KeyboardInterrupt` global di tingkat paling luar.
    """
    console = Console()
    print_welcome_banner(console)

    try:
        main_loop(console)
    except KeyboardInterrupt:
        # Penanganan Ctrl+C jika ditekan langsung di prompt menu paling luar
        console.print("\n[dim]Aplikasi dihentikan oleh pengguna via pintasan keyboard. Sampai jumpa![/dim]\n")
        sys.exit(0)
