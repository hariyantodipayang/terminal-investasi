# -*- coding: utf-8 -*-
"""
BUAT RILIS — alat untuk pembuat aplikasi, bukan untuk pemakai.

Berkas ini menghitung sidik jari SHA-256 tiap berkas yang akan dirilis, lalu
menyusun rilis/versi.json yang dibaca aplikasi pemakai untuk memeriksa
pembaruan.

Cara pakai:
    1. Naikkan nomor VERSI di dalam terminal_ringan.py
    2. Jalankan:  python buat_rilis.py "Keterangan perubahan singkat"
    3. Unggah ke GitHub: berkas yang berubah + rilis/versi.json
    4. Selesai. Pemakai akan melihat pemberitahuan saat membuka aplikasi.

Jangan sertakan berkas ini dalam ZIP yang Anda bagikan ke pemakai.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

# ── Yang perlu Anda sesuaikan sekali saja ─────────────────────────────
PENGGUNA_GITHUB = "hariyantodipayang"
NAMA_REPO = "terminal-investasi"
CABANG = "main"
# ──────────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent
DIR_RILIS = BASE / "rilis"

# Harus sama persis dengan BERKAS_BOLEH_DIPERBARUI di terminal_ringan.py.
# Kalau tidak, aplikasi pemakai akan menolak pembaruannya.
BERKAS_RILIS = ["terminal_ringan.py", "requirements.txt", "BACA-DULU.md"]


def sidik_jari(berkas: Path) -> str:
    return hashlib.sha256(berkas.read_bytes()).hexdigest()


def baca_versi() -> str:
    isi = (BASE / "terminal_ringan.py").read_text(encoding="utf-8")
    cocok = re.search(r'^VERSI\s*=\s*["\']([^"\']+)["\']', isi, re.M)
    if not cocok:
        raise SystemExit("Tidak menemukan baris VERSI = \"...\" di terminal_ringan.py")
    return cocok.group(1)


def url_mentah(nama: str) -> str:
    return (f"https://raw.githubusercontent.com/{PENGGUNA_GITHUB}/{NAMA_REPO}/"
            f"{CABANG}/{nama}")


def main():
    catatan = sys.argv[1] if len(sys.argv) > 1 else "Perbaikan dan penyempurnaan."
    versi = baca_versi()

    berkas = {}
    hilang = []
    for nama in BERKAS_RILIS:
        p = BASE / nama
        if not p.is_file():
            hilang.append(nama)
            continue
        berkas[nama] = {
            "url": url_mentah(nama),
            "sha256": sidik_jari(p),
            "ukuran": p.stat().st_size,
        }

    if hilang:
        print("Peringatan — berkas tidak ditemukan, dilewati: " + ", ".join(hilang))
    if not berkas:
        raise SystemExit("Tidak ada berkas yang bisa dirilis.")

    manifes = {
        "versi": versi,
        "tanggal": date.today().isoformat(),
        "catatan": catatan,
        "berkas": berkas,
    }

    DIR_RILIS.mkdir(exist_ok=True)
    tujuan = DIR_RILIS / "versi.json"
    tujuan.write_text(json.dumps(manifes, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  versi.json dibuat untuk versi {versi}\n")
    for nama, info in berkas.items():
        print(f"    {nama:<24} {info['ukuran']:>8,} bita   {info['sha256'][:16]}…")

    print(f"\n  Tersimpan di: {tujuan}")
    print("\n  Langkah berikutnya:")
    print("    git add -A")
    print(f'    git commit -m "Rilis {versi}"')
    print("    git push")
    print("\n  Pemakai akan melihat pemberitahuan dalam waktu 6 jam,")
    print("  atau langsung kalau menekan PERIKSA PEMBARUAN.\n")

    # Pengingat yang mudah terlewat
    if versi == "1.0.0":
        print("  Catatan: nomor versi masih 1.0.0. Kalau ini rilis baru,")
        print("  naikkan dulu VERSI di terminal_ringan.py, lalu jalankan ulang.\n")


if __name__ == "__main__":
    main()
