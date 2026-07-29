# -*- coding: utf-8 -*-
"""
BUAT PAKET — menyusun ZIP bersih untuk dibagikan ke pemakai.

Berkas ini untuk Anda sebagai pembuat, bukan untuk pemakai.

ZIP yang dihasilkan hanya memuat berkas aplikasi. Data pribadi Anda, alat
kerja, dan panduan internal tidak ikut — bukan karena tidak sengaja, tetapi
karena daftarnya ditulis tegas di bawah ini.

Cara pakai:
    python buat_paket.py

Hasilnya: paket/TerminalInvestasi-v1.0.0.zip
Unggah lewat GitHub → Releases → Create a new release.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

BASE = Path(__file__).parent
DIR_PAKET = BASE / "paket"

# Hanya yang tercantum di sini yang masuk ZIP. Pendekatan "daftar putih"
# dipilih dengan sengaja: kalau suatu saat ada berkas baru di folder ini,
# ia tidak akan ikut terkirim diam-diam.
ISI_PAKET = [
    "terminal_ringan.py",
    "requirements.txt",
    "MULAI.cmd",
    "MULAI.sh",
    "BACA-DULU.md",
    "README.md",
    "LICENSE",
    ".streamlit/config.toml",
    "aset/qris.png",
    "aset/paypal.png",
    "aset/CARA-PASANG-QRIS.md",
]

# Diperiksa ulang sebelum menulis. Kalau salah satu ini sampai lolos,
# ada yang keliru dan proses dihentikan.
HARAM = ["data/", "cadangan/", ".venv/", "__pycache__/", "buat_rilis.py",
         "buat_paket.py", "CARA-RILIS.md", "CARA-BAGIKAN.md",
         "LANGKAH-AWAL-GITHUB.md", "DESKRIPSI-GITHUB.md", "rilis/"]


def baca_versi() -> str:
    isi = (BASE / "terminal_ringan.py").read_text(encoding="utf-8")
    cocok = re.search(r'^VERSI\s*=\s*["\']([^"\']+)["\']', isi, re.M)
    if not cocok:
        raise SystemExit("Tidak menemukan baris VERSI di terminal_ringan.py")
    return cocok.group(1)


def main():
    versi = baca_versi()
    akar = f"TerminalInvestasi-v{versi}"

    ada, hilang = [], []
    for nama in ISI_PAKET:
        (ada if (BASE / nama).is_file() else hilang).append(nama)

    if hilang:
        print("\n  Berkas berikut tidak ditemukan dan tidak akan ikut:")
        for n in hilang:
            print(f"    - {n}")
        if "terminal_ringan.py" in hilang or "MULAI.cmd" in hilang:
            raise SystemExit("\n  Berkas inti hilang. Dibatalkan.")

    DIR_PAKET.mkdir(exist_ok=True)
    tujuan = DIR_PAKET / f"{akar}.zip"

    with zipfile.ZipFile(tujuan, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for nama in ada:
            z.write(BASE / nama, f"{akar}/{nama}")

    # Periksa ulang isi ZIP — jangan percaya pada niat, periksa hasilnya.
    with zipfile.ZipFile(tujuan) as z:
        daftar = z.namelist()
    bocor = [n for n in daftar if any(h in n for h in HARAM)]
    if bocor:
        tujuan.unlink()
        raise SystemExit(f"\n  BAHAYA — berkas terlarang ikut masuk: {bocor}\n"
                         f"  ZIP dihapus. Periksa daftar ISI_PAKET.")

    ukuran = tujuan.stat().st_size
    print(f"\n  Paket siap: {tujuan.name}  ({ukuran / 1024:.0f} KB)\n")
    for n in sorted(daftar):
        info = zipfile.ZipFile(tujuan).getinfo(n)
        print(f"    {n:<52} {info.file_size:>8,} bita")

    print(f"\n  Berkas dalam paket : {len(daftar)}")
    print(f"  Data pribadi ikut  : tidak")
    print(f"  Alat kerja ikut    : tidak")

    print(f"\n  Langkah berikutnya:")
    print(f"    1. Buka https://github.com/hariyantodipayang/terminal-investasi/releases/new")
    print(f'    2. Tag  : v{versi}')
    print(f'    3. Judul: Terminal Investasi v{versi}')
    print(f"    4. Seret {tujuan.name} ke kotak lampiran")
    print(f"    5. Publish release\n")
    print(f"  Pemakai lalu punya tombol unduh yang jelas, bukan menu Code.\n")


if __name__ == "__main__":
    main()
