"""Menu Reset Seluruh Data Aplikasi (CLI Reset Menu).

Modul ini menyediakan fitur penghapusan permanen seluruh data operasional
yang tersimpan di folder `data/`, termasuk profil sekolah, data siswa,
berkas cadangan (.bak).

Penjelasan Sederhana untuk Orang Awam:
    Bayangkan tombol ini seperti "Format Ulang" pada komputer:
    - Semua data sekolah (nama, akreditasi, jurusan) akan dihapus.
    - Semua data siswa (nilai rapor, status TKA) akan dihapus.
    - Semua berkas cadangan otomatis (.bak) juga ikut dihapus.
    - Berkas konfigurasi sistem (config.json) TIDAK dihapus karena berisi
      aturan resmi SNBP yang bukan data pengguna.

    ⚠️ PERINGATAN: Proses ini TIDAK BISA DIBATALKAN (irreversible).
    Setelah data dihapus, tidak ada cara untuk mengembalikannya kecuali
    Anda memiliki salinan cadangan manual di tempat lain.

Kepatuhan Standar Rekayasa:
    - Arsitektur: Lapisan Presentasi (CLI Presentation Component).
    - C1: Menggunakan perenderan Rich Panel dan Confirm berwarna.
    - Keamanan: Konfirmasi ganda (double confirmation) sebelum penghapusan
      untuk mencegah penghapusan tidak disengaja.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt


def _count_data_files(data_dir: Path) -> dict[str, int]:
    """Menghitung jumlah berkas data yang akan dihapus per kategori.

    Fungsi pembantu ini memindai seluruh isi folder `data/` dan mengelompokkan
    berkas-berkas yang ditemukan ke dalam kategori yang mudah dipahami operator.

    Args:
        data_dir: Jalur absolut ke direktori data (biasanya `data/`).

    Returns:
        Dictionary berisi jumlah berkas per kategori:
        - "profil_sekolah": Jumlah berkas school.json dan cadangannya.
        - "data_siswa": Jumlah berkas students.json dan cadangannya.
        - "berkas_cadangan": Jumlah berkas .bak dan .tmp.
        - "template_impor": Jumlah berkas di folder import/.
        - "total": Total seluruh berkas yang akan dihapus.
    """
    counts: dict[str, int] = {
        "profil_sekolah": 0,
        "data_siswa": 0,
        "berkas_cadangan": 0,
        "template_impor": 0,
        "total": 0,
    }

    if not data_dir.exists():
        return counts

    # Hitung berkas profil sekolah (school.json)
    if (data_dir / "school.json").exists():
        counts["profil_sekolah"] += 1
    if (data_dir / "school.json.bak").exists():
        counts["profil_sekolah"] += 1

    # Hitung berkas data siswa (students.json)
    if (data_dir / "students.json").exists():
        counts["data_siswa"] += 1
    if (data_dir / "students.json.bak").exists():
        counts["data_siswa"] += 1

    # Hitung berkas cadangan dan temporer lainnya (.bak, .tmp)
    for bak_file in data_dir.glob("*.bak"):
        # Sudah dihitung di atas, jadi lewati school.json.bak dan students.json.bak
        if bak_file.name not in ("school.json.bak", "students.json.bak"):
            counts["berkas_cadangan"] += 1
    for _tmp_file in data_dir.glob("*.tmp"):
        counts["berkas_cadangan"] += 1

    # Hitung berkas template impor di folder import/
    import_dir = data_dir / "import"
    if import_dir.exists():
        for import_file in import_dir.iterdir():
            if import_file.is_file():
                counts["template_impor"] += 1

    # Hitung total keseluruhan
    counts["total"] = sum(counts.values())

    return counts


def _perform_reset(data_dir: Path) -> dict[str, int]:
    """Melaksanakan penghapusan permanen seluruh berkas data.

    Fungsi ini menghapus semua berkas operasional di folder `data/` KECUALI
    berkas `config.json` yang berisi konfigurasi aturan resmi SNBP.

    Berkas yang dihapus:
    - school.json, school.json.bak (profil sekolah)
    - students.json, students.json.bak (data siswa)
    - Semua berkas .bak dan .tmp lainnya (cadangan otomatis)
    - Seluruh isi folder import/ (template impor CSV)

    Berkas yang TIDAK dihapus:
    - config.json (konfigurasi aturan resmi SNBP, bukan data pengguna)

    Args:
        data_dir: Jalur absolut ke direktori data (biasanya `data/`).

    Returns:
        Dictionary berisi jumlah berkas yang berhasil dihapus per kategori.
    """
    deleted: dict[str, int] = {
        "profil_sekolah": 0,
        "data_siswa": 0,
        "berkas_cadangan": 0,
        "template_impor": 0,
        "total": 0,
    }

    if not data_dir.exists():
        return deleted

    # ── 1. Hapus berkas profil sekolah ──────────────────────────────────
    for school_file in ("school.json", "school.json.bak"):
        target = data_dir / school_file
        if target.exists():
            target.unlink()
            deleted["profil_sekolah"] += 1

    # ── 2. Hapus berkas data siswa ─────────────────────────────────────
    for student_file in ("students.json", "students.json.bak"):
        target = data_dir / student_file
        if target.exists():
            target.unlink()
            deleted["data_siswa"] += 1

    # ── 3. Hapus berkas cadangan dan temporer (.bak, .tmp) ─────────────
    for pattern in ("*.bak", "*.tmp"):
        for leftover in data_dir.glob(pattern):
            if leftover.is_file():
                leftover.unlink()
                deleted["berkas_cadangan"] += 1

    # ── 5. Hapus seluruh isi folder import/ ────────────────────────────
    import_dir = data_dir / "import"
    if import_dir.exists():
        for import_file in import_dir.iterdir():
            if import_file.is_file():
                import_file.unlink()
                deleted["template_impor"] += 1

    # Hitung total keseluruhan
    deleted["total"] = sum(deleted.values())

    return deleted


def display_reset_menu(console: Console, data_dir: str = "data") -> None:
    """Menampilkan alur menu reset data dengan konfirmasi ganda.

    Alur interaksi yang dilalui operator:
    1. Sistem menghitung dan menampilkan rincian berkas yang akan dihapus.
    2. Jika tidak ada berkas data, tampilkan pesan "sudah bersih" dan kembali.
    3. Operator diminta konfirmasi pertama (Ya/Tidak).
    4. Jika Ya, operator diminta mengetikkan kata "HAPUS" sebagai konfirmasi kedua.
    5. Jika konfirmasi kedua cocok, penghapusan dilaksanakan dan hasilnya ditampilkan.

    Args:
        console: Objek Rich Console untuk perenderan visual.
        data_dir: Jalur relatif ke direktori data (default: "data").
    """
    data_path = Path(data_dir)

    # ── Langkah 1: Hitung berkas yang ada ──────────────────────────────
    counts = _count_data_files(data_path)

    if counts["total"] == 0:
        console.print(
            Panel(
                "[bold green]✅ Tidak ada data yang perlu dihapus.[/bold green]\n"
                "[white]Folder data sudah dalam keadaan bersih.[/white]",
                title="[bold green]🧹 DATA SUDAH BERSIH[/bold green]",
                border_style="green",
            )
        )
        return

    # ── Langkah 2: Tampilkan rincian berkas yang akan dihapus ──────────
    detail_lines: list[str] = []

    if counts["profil_sekolah"] > 0:
        detail_lines.append(
            f"  [bold white]🏫 Profil Sekolah & Kurikulum:[/bold white]  "
            f"[yellow]{counts['profil_sekolah']} berkas[/yellow]"
        )
    if counts["data_siswa"] > 0:
        detail_lines.append(
            f"  [bold white]👨‍🎓 Data Siswa & Nilai Rapor:[/bold white]    "
            f"[yellow]{counts['data_siswa']} berkas[/yellow]"
        )
    if counts["berkas_cadangan"] > 0:
        detail_lines.append(
            f"  [bold white]💾 Berkas Cadangan (.bak/.tmp):[/bold white] "
            f"[yellow]{counts['berkas_cadangan']} berkas[/yellow]"
        )
    if counts["template_impor"] > 0:
        detail_lines.append(
            f"  [bold white]📥 Template Impor CSV:[/bold white]          "
            f"[yellow]{counts['template_impor']} berkas[/yellow]"
        )

    detail_text = "\n".join(detail_lines)

    console.print(
        Panel(
            f"[bold red]⚠️  PERINGATAN: TINDAKAN INI TIDAK BISA DIBATALKAN!  ⚠️[/bold red]\n\n"
            f"Berkas-berkas berikut akan [bold red]DIHAPUS PERMANEN[/bold red]:\n\n"
            f"{detail_text}\n\n"
            f"[bold white]Total: {counts['total']} berkas akan dihapus.[/bold white]\n\n"
            f"[dim]Catatan: Berkas config.json (aturan resmi SNBP) TIDAK akan dihapus.[/dim]",
            title="[bold red]🗑️  RESET SELURUH DATA APLIKASI[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )

    # ── Langkah 3: Konfirmasi pertama ──────────────────────────────────
    confirm_first = Confirm.ask(
        "[bold yellow]Apakah Anda yakin ingin menghapus semua data di atas?[/bold yellow]",
        default=False,
        console=console,
    )

    if not confirm_first:
        console.print("\n[green]Penghapusan dibatalkan. Data Anda tetap aman.[/green]\n")
        return

    # ── Langkah 4: Konfirmasi kedua (ketik "HAPUS") ────────────────────
    console.print(
        "\n[bold red]Untuk benar-benar menghapus, ketikkan kata:[/bold red] "
        "[bold white on red] HAPUS [/bold white on red]\n"
    )
    confirm_word = Prompt.ask(
        "[bold red]Ketik di sini untuk konfirmasi[/bold red]",
        console=console,
    )

    if confirm_word.strip().upper() != "HAPUS":
        console.print("\n[green]Konfirmasi tidak cocok. Penghapusan dibatalkan. Data Anda tetap aman.[/green]\n")
        return

    # ── Langkah 5: Laksanakan penghapusan ──────────────────────────────
    deleted = _perform_reset(data_path)

    # Tampilkan hasil penghapusan
    result_lines: list[str] = []
    if deleted["profil_sekolah"] > 0:
        result_lines.append(f"  ✓ Profil sekolah: {deleted['profil_sekolah']} berkas dihapus")
    if deleted["data_siswa"] > 0:
        result_lines.append(f"  ✓ Data siswa: {deleted['data_siswa']} berkas dihapus")
    if deleted["berkas_cadangan"] > 0:
        result_lines.append(f"  ✓ Berkas cadangan: {deleted['berkas_cadangan']} berkas dihapus")
    if deleted["template_impor"] > 0:
        result_lines.append(f"  ✓ Template impor: {deleted['template_impor']} berkas dihapus")

    result_text = "\n".join(result_lines)

    console.print(
        Panel(
            f"[bold green]Penghapusan berhasil dilaksanakan.[/bold green]\n\n"
            f"{result_text}\n\n"
            f"[bold white]Total: {deleted['total']} berkas telah dihapus permanen.[/bold white]\n\n"
            f"[dim]Sistem siap digunakan kembali dari awal. Silakan mulai dengan\n"
            f"mengatur profil sekolah melalui Menu 1.[/dim]",
            title="[bold green]✅ RESET DATA SELESAI[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
