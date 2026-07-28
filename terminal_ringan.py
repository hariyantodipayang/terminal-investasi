# -*- coding: utf-8 -*-
"""
TERMINAL RINGAN
Terminal data keuangan sederhana, berbahasa Indonesia, tanpa kredit.

Seluruh data diambil langsung dari sumber terbuka yang gratis:
  - Yahoo Finance  : harga saham, kripto, indeks, komoditas  (tanpa API key)
  - Bank Dunia     : indikator makro ekonomi                 (tanpa API key)
  - RSS            : berita pasar Indonesia dan global       (tanpa API key)

Data portofolio dan watchlist Anda disimpan di folder "data/" di sebelah
berkas ini. Tidak ada yang dikirim ke mana pun.

Jalankan dengan:  streamlit run terminal_ringan.py
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ──────────────────────────────────────────────────────────────────────
#  PENGATURAN DASAR  — ubah di sini kalau mau menyesuaikan
# ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

BERKAS_WATCHLIST = DATA_DIR / "watchlist.json"
BERKAS_PORTOFOLIO = DATA_DIR / "portofolio.json"
BERKAS_DOMPET = DATA_DIR / "dompet.json"
BERKAS_PERINGATAN = DATA_DIR / "peringatan.json"
BERKAS_JURNAL = DATA_DIR / "jurnal.json"

# ── Jaringan blockchain yang didukung pelacak dompet ──────────────────
# Semuanya hanya BACA, lewat alamat publik. Aplikasi ini tidak pernah
# meminta seed phrase atau private key — dan Anda pun jangan pernah
# memasukkannya ke aplikasi mana pun.
JARINGAN = {
    "Bitcoin": {
        "kode": "BTC",
        "koin": "bitcoin",
        "pola": r"^(bc1[a-zA-HJ-NP-Z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$",
        "contoh": "bc1q... atau 1A1zP...",
        "desimal": 8,
    },
    "Ethereum": {
        "kode": "ETH",
        "koin": "ethereum",
        "pola": r"^0x[a-fA-F0-9]{40}$",
        "contoh": "0x742d35Cc...",
        "desimal": 18,
    },
    "Solana": {
        "kode": "SOL",
        "koin": "solana",
        "pola": r"^[1-9A-HJ-NP-Za-km-z]{32,44}$",
        "contoh": "7xKXtg2C...",
        "desimal": 9,
    },
}

WATCHLIST_AWAL = ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "AAPL", "MSFT", "BTC-USD"]

INDEKS_PANTAU = {
    "^JKSE": "IHSG",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^N225": "Nikkei 225",
    "^HSI": "Hang Seng",
    "^FTSE": "FTSE 100",
}

# ── Forex ─────────────────────────────────────────────────────────────
# Yahoo Finance memakai akhiran "=X" untuk pasangan mata uang.
FOREX_UTAMA = {
    "EURUSD=X": "EUR / USD",
    "GBPUSD=X": "GBP / USD",
    "USDJPY=X": "USD / JPY",
    "USDCHF=X": "USD / CHF",
    "AUDUSD=X": "AUD / USD",
    "USDCAD=X": "USD / CAD",
    "NZDUSD=X": "NZD / USD",
    "USDCNY=X": "USD / CNY",
}

FOREX_RUPIAH = {
    "USDIDR=X": "USD / IDR",
    "EURIDR=X": "EUR / IDR",
    "SGDIDR=X": "SGD / IDR",
    "JPYIDR=X": "JPY / IDR",
    "AUDIDR=X": "AUD / IDR",
    "CNYIDR=X": "CNY / IDR",
    "MYRIDR=X": "MYR / IDR",
    "GBPIDR=X": "GBP / IDR",
}

FOREX_SILANG = {
    "EURJPY=X": "EUR / JPY",
    "GBPJPY=X": "GBP / JPY",
    "EURGBP=X": "EUR / GBP",
    "AUDJPY=X": "AUD / JPY",
    "EURAUD=X": "EUR / AUD",
    "CHFJPY=X": "CHF / JPY",
}

FOREX_SEMUA = {**FOREX_UTAMA, **FOREX_RUPIAH, **FOREX_SILANG}

# Satu lot standar = 100.000 unit mata uang dasar.
# ── Interval untuk backtest ───────────────────────────────────────────
# Yahoo Finance membatasi seberapa jauh ke belakang data rentang pendek bisa
# diambil. Batas ini nyata dan tidak bisa ditawar — jadi tiap interval hanya
# menawarkan periode yang memang tersedia, supaya pemakai tidak menemui
# tabel kosong tanpa penjelasan.
INTERVAL_BACKTEST = {
    "Bulanan": {
        "kode": "1mo", "periode": ["2y", "5y", "10y", "max"], "min_batang": 24,
        "catatan": "Satu batang = satu bulan. Rata-rata 20 pada strategi berarti "
                   "20 bulan, bukan 20 hari.",
    },
    "Mingguan": {
        "kode": "1wk", "periode": ["1y", "2y", "5y", "10y", "max"], "min_batang": 40,
        "catatan": "Satu batang = satu minggu.",
    },
    "Harian": {
        "kode": "1d", "periode": ["3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
        "min_batang": 60, "catatan": "",
    },
    "Per jam": {
        "kode": "1h", "periode": ["1mo", "3mo", "6mo", "1y", "2y"], "min_batang": 100,
        "catatan": "Yahoo Finance hanya menyimpan data per jam sampai sekitar dua "
                   "tahun ke belakang.",
    },
    "Per 30 menit": {
        "kode": "30m", "periode": ["5d", "1mo"], "min_batang": 100,
        "catatan": "Data 30 menit hanya tersedia untuk 60 hari terakhir.",
    },
    "Per 15 menit": {
        "kode": "15m", "periode": ["5d", "1mo"], "min_batang": 100,
        "catatan": "Data 15 menit hanya tersedia untuk 60 hari terakhir.",
    },
    "Per 5 menit": {
        "kode": "5m", "periode": ["5d", "1mo"], "min_batang": 100,
        "catatan": "Data 5 menit hanya tersedia untuk 60 hari terakhir.",
    },
    "Per menit": {
        "kode": "1m", "periode": ["5d"], "min_batang": 100,
        "catatan": "Data per menit hanya tersedia untuk 7 hari terakhir.",
    },
}

LOT_FOREX = {"Standar (100.000)": 100_000, "Mini (10.000)": 10_000,
             "Mikro (1.000)": 1_000, "Nano (100)": 100}

# Spread khas broker ritel, dalam pip. Selalu periksa ke broker Anda sendiri.
SPREAD_KHAS = {"EURUSD=X": 1.0, "GBPUSD=X": 1.5, "USDJPY=X": 1.2, "USDCHF=X": 1.8,
               "AUDUSD=X": 1.4, "USDCAD=X": 1.8, "NZDUSD=X": 2.0, "USDIDR=X": 30.0}

KOMODITAS_PANTAU = {
    "USDIDR=X": "USD / IDR",
    "GC=F": "Emas",
    "CL=F": "Minyak WTI",
    "SI=F": "Perak",
    "DX-Y.NYB": "Indeks Dolar",
    "^TNX": "Obligasi AS 10 Tahun",
}

SAHAM_IDX_PANTAU = {
    "BBCA.JK": "Bank Central Asia",
    "BBRI.JK": "Bank Rakyat Indonesia",
    "BMRI.JK": "Bank Mandiri",
    "TLKM.JK": "Telkom Indonesia",
    "ASII.JK": "Astra International",
    "GOTO.JK": "GoTo Gojek Tokopedia",
    "ANTM.JK": "Aneka Tambang",
    "ADRO.JK": "Alamtri Resources",
    "ICBP.JK": "Indofood CBP",
}

MAKRO_PANTAU = {
    "USDIDR=X": "USD/IDR",
    "^TNX": "US 10Y (%)",
    "DX-Y.NYB": "Indeks Dolar",
    "GC=F": "Emas",
    "CL=F": "Minyak WTI",
    "BTC-USD": "Bitcoin",
}

JUMLAH_KRIPTO = 12  # berapa koin teratas yang ditampilkan di Denyut Kripto

# ── Semesta saham untuk Screener ──────────────────────────────────────
# Bukan seluruh bursa. Daftar ini dipilih dari saham yang paling likuid supaya
# penyaringan selesai dalam hitungan detik, bukan menit. Tambah atau kurangi
# sesuka Anda — cukup ikuti pola penulisan simbolnya.

UNIVERS_IDX = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK", "BBTN.JK", "BJBR.JK", "BNGA.JK",
    "TLKM.JK", "EXCL.JK", "ISAT.JK", "TOWR.JK", "TBIG.JK", "MTEL.JK",
    "ASII.JK", "UNTR.JK", "AUTO.JK", "GJTL.JK",
    "UNVR.JK", "ICBP.JK", "INDF.JK", "MYOR.JK", "CPIN.JK", "JPFA.JK", "GGRM.JK", "HMSP.JK",
    "AMRT.JK", "MAPI.JK", "ERAA.JK", "ACES.JK", "RALS.JK", "LPPF.JK",
    "ADRO.JK", "PTBA.JK", "ITMG.JK", "HRUM.JK", "INDY.JK", "BUMI.JK", "MEDC.JK", "PGAS.JK",
    "ANTM.JK", "INCO.JK", "TINS.JK", "MDKA.JK", "NCKL.JK", "BRMS.JK", "PSAB.JK",
    "SMGR.JK", "INTP.JK", "WTON.JK", "WIKA.JK", "PTPP.JK", "ADHI.JK", "WSKT.JK",
    "BSDE.JK", "CTRA.JK", "SMRA.JK", "PWON.JK", "ASRI.JK", "DMAS.JK",
    "KLBF.JK", "SIDO.JK", "MIKA.JK", "HEAL.JK", "SILO.JK", "PRDA.JK",
    "GOTO.JK", "BUKA.JK", "EMTK.JK", "MNCN.JK", "SCMA.JK", "BELI.JK",
    "AKRA.JK", "BRPT.JK", "TPIA.JK", "ESSA.JK", "CUAN.JK", "PANI.JK",
    "AALI.JK", "LSIP.JK", "DSNG.JK", "SSMS.JK", "TAPG.JK",
    "JSMR.JK", "GIAA.JK", "ASSA.JK", "BIRD.JK", "SMDR.JK", "TMAS.JK",
    "ARTO.JK", "BBYB.JK", "AMMN.JK", "BREN.JK", "CDIA.JK", "RAJA.JK",
]

UNIVERS_US = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "AMD", "INTC",
    "NFLX", "ADBE", "CRM", "ORCL", "CSCO", "QCOM", "TXN", "MU", "PLTR", "UBER",
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP", "BRK-B", "BLK",
    "JNJ", "PFE", "MRK", "ABBV", "LLY", "UNH", "TMO", "ABT",
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "PG", "KO", "PEP", "DIS",
    "XOM", "CVX", "COP", "CAT", "BA", "GE", "HON", "LMT", "UPS", "T",
]

UNIVERS_MY = [  # Bursa Malaysia
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5183.KL", "5225.KL", "3816.KL", "5681.KL",
    "6888.KL", "6012.KL", "5819.KL", "1066.KL", "4197.KL", "2445.KL", "1961.KL", "3182.KL",
    "4707.KL", "4065.KL", "3034.KL", "7277.KL", "5285.KL", "6033.KL", "4715.KL", "7113.KL",
]

UNIVERS_SG = [  # Singapore Exchange
    "D05.SI", "O39.SI", "U11.SI", "Z74.SI", "C6L.SI", "C38U.SI", "A17U.SI", "BN4.SI",
    "F34.SI", "S63.SI", "G13.SI", "Y92.SI", "U96.SI", "H78.SI", "J36.SI", "ME8U.SI",
    "N2IU.SI", "S58.SI", "V03.SI", "C09.SI", "U14.SI", "S68.SI",
]

UNIVERS_TH = [  # Stock Exchange of Thailand
    "PTT.BK", "AOT.BK", "CPALL.BK", "ADVANC.BK", "SCB.BK", "KBANK.BK", "BBL.BK", "PTTEP.BK",
    "SCC.BK", "GULF.BK", "BDMS.BK", "CPN.BK", "MINT.BK", "TRUE.BK", "KTB.BK", "BH.BK",
    "EA.BK", "DELTA.BK", "TU.BK", "IVL.BK", "OR.BK", "CRC.BK",
]

UNIVERS_HK = [  # Hong Kong Exchange
    "0700.HK", "9988.HK", "0941.HK", "0005.HK", "1299.HK", "3690.HK", "0388.HK", "1810.HK",
    "2318.HK", "0939.HK", "1398.HK", "0883.HK", "0857.HK", "2628.HK", "1211.HK", "9618.HK",
    "0016.HK", "0011.HK", "0002.HK", "0001.HK", "0027.HK", "2020.HK",
]

UNIVERS_JP = [  # Tokyo Stock Exchange
    "7203.T", "6758.T", "6861.T", "8306.T", "9432.T", "6098.T", "9983.T", "8035.T",
    "4063.T", "6501.T", "7267.T", "8058.T", "8001.T", "4502.T", "6902.T", "9433.T",
    "8316.T", "6367.T", "7741.T", "6594.T", "4661.T", "6954.T",
]

UNIVERS_IN = [  # National Stock Exchange of India
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS", "BAJFINANCE.NS", "WIPRO.NS",
    "NESTLEIND.NS", "ULTRACEMCO.NS", "HCLTECH.NS", "ADANIENT.NS",
]

UNIVERS_AU = [  # Australian Securities Exchange
    "BHP.AX", "CBA.AX", "CSL.AX", "NAB.AX", "WBC.AX", "ANZ.AX", "WES.AX", "MQG.AX",
    "WOW.AX", "TLS.AX", "RIO.AX", "FMG.AX", "GMG.AX", "TCL.AX", "ALL.AX", "WDS.AX",
    "COL.AX", "STO.AX", "QAN.AX", "REA.AX",
]

UNIVERS_UK = [  # London Stock Exchange
    "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "RIO.L", "GSK.L", "DGE.L",
    "BATS.L", "LSEG.L", "REL.L", "NG.L", "VOD.L", "BARC.L", "LLOY.L", "TSCO.L",
    "PRU.L", "AAL.L", "IMB.L", "CPG.L",
]

UNIVERS_DE = [  # Deutsche Börse XETRA
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "AIR.DE", "MBG.DE", "BAS.DE", "BMW.DE",
    "MUV2.DE", "IFX.DE", "DBK.DE", "VOW3.DE", "RWE.DE", "ADS.DE", "BAYN.DE", "HEN3.DE",
    "MRK.DE", "EOAN.DE", "DB1.DE", "DTG.DE",
]

UNIVERS_KR = [  # Korea Exchange
    "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "000270.KS",
    "068270.KS", "005490.KS", "035420.KS", "051910.KS", "006400.KS", "012330.KS",
    "028260.KS", "105560.KS", "055550.KS", "086790.KS",
]

# Tiap semesta menyimpan mata uangnya sendiri. Ini penting: kapitalisasi pasar
# dilaporkan dalam mata uang asli, jadi menyaring "di atas 10 triliun" berarti
# hal yang sangat berbeda antara rupiah dan dolar.
SEMESTA = {
    "Indonesia — IDX":       {"daftar": UNIVERS_IDX, "mata_uang": "IDR", "satuan": "triliun Rp"},
    "Amerika Serikat — US":  {"daftar": UNIVERS_US,  "mata_uang": "USD", "satuan": "miliar $"},
    "Malaysia — Bursa":      {"daftar": UNIVERS_MY,  "mata_uang": "MYR", "satuan": "miliar RM"},
    "Singapura — SGX":       {"daftar": UNIVERS_SG,  "mata_uang": "SGD", "satuan": "miliar S$"},
    "Thailand — SET":        {"daftar": UNIVERS_TH,  "mata_uang": "THB", "satuan": "miliar ฿"},
    "Hong Kong — HKEX":      {"daftar": UNIVERS_HK,  "mata_uang": "HKD", "satuan": "miliar HK$"},
    "Jepang — TSE":          {"daftar": UNIVERS_JP,  "mata_uang": "JPY", "satuan": "triliun ¥"},
    "India — NSE":           {"daftar": UNIVERS_IN,  "mata_uang": "INR", "satuan": "miliar ₹"},
    "Australia — ASX":       {"daftar": UNIVERS_AU,  "mata_uang": "AUD", "satuan": "miliar A$"},
    "Inggris — LSE":         {"daftar": UNIVERS_UK,  "mata_uang": "GBP", "satuan": "miliar £"},
    "Jerman — XETRA":        {"daftar": UNIVERS_DE,  "mata_uang": "EUR", "satuan": "miliar €"},
    "Korea Selatan — KRX":   {"daftar": UNIVERS_KR,  "mata_uang": "KRW", "satuan": "triliun ₩"},
}

# Pengali untuk mengubah satuan penyaring kapitalisasi jadi angka penuh
PENGALI_KAP = {"triliun Rp": 1e12, "triliun ¥": 1e12, "triliun ₩": 1e12}

# ── Biaya transaksi bawaan ────────────────────────────────────────────
# Angka umum sekuritas ritel Indonesia. Biaya jual lebih besar karena sudah
# termasuk pajak penjualan 0,1%. Cek ke sekuritas Anda dan sesuaikan.
BIAYA_BELI = 0.15   # persen
BIAYA_JUAL = 0.25   # persen
LOT = 100           # satu lot di Bursa Efek Indonesia = 100 lembar

SEBUTAN_FNG = {
    "Extreme Fear": "Sangat Takut",
    "Fear": "Takut",
    "Neutral": "Netral",
    "Greed": "Serakah",
    "Extreme Greed": "Sangat Serakah",
}

RSS_INDONESIA = {
    "CNBC Indonesia — Market": "https://www.cnbcindonesia.com/market/rss",
    "Kontan — Investasi": "https://investasi.kontan.co.id/rss",
    "Bisnis.com — Market": "https://market.bisnis.com/rss",
}

RSS_GLOBAL = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
    "CNBC — Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
}

INDIKATOR_BANK_DUNIA = {
    "NY.GDP.MKTP.KD.ZG": "Pertumbuhan PDB (% per tahun)",
    "FP.CPI.TOTL.ZG": "Inflasi harga konsumen (% per tahun)",
    "SL.UEM.TOTL.ZS": "Tingkat pengangguran (% angkatan kerja)",
    "NE.EXP.GNFS.ZS": "Ekspor barang & jasa (% PDB)",
    "BN.CAB.XOKA.GD.ZS": "Neraca transaksi berjalan (% PDB)",
}

NEGARA = {
    "IDN": "Indonesia",
    "MYS": "Malaysia",
    "SGP": "Singapura",
    "THA": "Thailand",
    "VNM": "Vietnam",
    "USA": "Amerika Serikat",
    "CHN": "Tiongkok",
    "JPN": "Jepang",
}

# Profil pembuat — tampil di halaman Tentang, tab "Pembuat"
PROFIL = {
    "nama": "Hariyanto, S.Sos",
    "moto": "Mengabdi dengan ilmu, bertumbuh lewat inovasi.",
    "peran": ["ASN Kepahiang", "Developer", "Crypto Creator", "YouTuber"],
    "foto": "https://cdn.lynkid.my.id/profile/01-05-2026/1777639293606_8868403.webp",
    "profil_web": "https://dipayang.idcrypt.xyz/profil",
    "tentang": (
        "Seorang Aparatur Sipil Negara yang percaya bahwa tugas negara dan semangat "
        "berinovasi bisa berjalan beriringan. Di sela pengabdian, saya membangun aplikasi, "
        "mengeksplorasi dunia kripto, dan berbagi lewat konten digital — karena belajar "
        "tidak mengenal batas jabatan. Saat ini sedang menempuh pendidikan Magister "
        "Ekonomi Syariah di IAIN Curup."
    ),
    "proyek": [
        ("DIPAYANG", "Sistem digitalisasi pengamanan aset daerah Kabupaten Kepahiang. "
                     "Objek tesis magister sekaligus inovasi unggulan pemerintah daerah.",
         "https://dipayang.idcrypt.xyz"),
        ("IDCrypt", "Website kripto berbahasa Inggris — edukasi, analisis pasar, dan "
                    "komunitas investor lokal.",
         "https://idcrypt.xyz"),
        ("Shopping IDCrypt", "Perbandingan harga produk antara Tokopedia dan Shopee.",
         "https://shopping.idcrypt.xyz"),
        ("SIPANDAI", "Aplikasi manajemen untuk Badan Kesatuan Bangsa dan Politik "
                     "Kabupaten Kepahiang.",
         "https://kphinside.github.io/sipandai-app/"),
        ("KIBAS", "Kebun Induk Berbasis Aplikasi Smart — solusi AppSheet untuk Dinas "
                  "Pertanian Kabupaten Kepahiang.", ""),
        ("BKD Kepahiang", "Pengelolaan website resmi Badan Keuangan Daerah Kabupaten "
                          "Kepahiang.",
         "https://bkd.kepahiangkab.go.id"),
    ],
    "layanan": [
        ("Pengembangan aplikasi",
         "Website, sistem informasi, dan aplikasi berbasis AppSheet untuk instansi & bisnis."),
        ("Video AI & konten digital",
         "Produksi konten berbantuan AI — video, narasi, dan materi edukasi digital."),
        ("Edukasi kripto",
         "Konsultasi dan konten seputar aset kripto, analisis pasar, dan strategi investasi."),
        ("Produk digital",
         "Template, tools, dan produk digital siap pakai tersedia di Lynk.id."),
    ],
    "donasi": {
        "layanan": "DANA",
        "nomor": "0852-1493-9989",
        "nomor_salin": "085214939989",
        "atas_nama": "Hariyanto",
        # Letakkan gambar QR Anda di aset/qris.png — lihat aset/CARA-PASANG-QRIS.md.
        # Kalau berkasnya belum ada, aplikasi otomatis menampilkan nomornya saja.
        "berkas_qris": "aset/qris.png",
        "keterangan_qris": "Pindai dengan aplikasi DANA atau kamera ponsel",
    },
    "tautan": [
        ("Profil lengkap", "https://dipayang.idcrypt.xyz/profil"),
        ("YouTube — Ardion News", "https://www.youtube.com/@ardion_news"),
        ("Produk Digital — Lynk.id", "https://lynk.id/agribinka"),
        ("WhatsApp", "https://wa.me/6285609326414"),
    ],
}

# ──────────────────────────────────────────────────────────────────────
#  TAMPILAN
# ──────────────────────────────────────────────────────────────────────

BERKAS_PENGATURAN = DATA_DIR / "pengaturan.json"

# ── Versi dan saluran pembaruan ───────────────────────────────────────
VERSI = "1.0.0"

# Alamat berkas keterangan versi. Ganti dengan repositori Anda sendiri.
# Harus HTTPS — pembaruan lewat sambungan biasa bisa disusupi di tengah jalan.
URL_RILIS = ("https://raw.githubusercontent.com/hariyantodipayang/terminal-investasi/"
             "main/rilis/versi.json")

# Hanya alamat dari inang berikut yang akan diunduh. Ini pagar terakhir kalau
# suatu saat berkas keterangan versi diubah orang lain: ia tetap tidak bisa
# menyuruh aplikasi mengambil kode dari tempat sembarangan.
INANG_TEPERCAYA = ("raw.githubusercontent.com", "github.com", "objects.githubusercontent.com")

# Berkas yang boleh diganti oleh pembaruan. Sengaja dibatasi — pembaruan tidak
# boleh menyentuh data pemakai, dan tidak boleh menaruh berkas baru sembarangan.
BERKAS_BOLEH_DIPERBARUI = ("terminal_ringan.py", "requirements.txt", "BACA-DULU.md")

DIR_CADANGAN = BASE_DIR / "cadangan"


def muat_json_awal(berkas, bawaan):
    """Versi ringkas muat_json, dipakai sebelum fungsi utama didefinisikan."""
    try:
        if berkas.exists():
            return json.loads(berkas.read_text(encoding="utf-8"))
    except Exception:
        pass
    return bawaan


# ── Palet warna ───────────────────────────────────────────────────────
# Dua tema dengan nama kunci yang sama persis. Menambah tema baru cukup
# menyalin salah satu blok dan mengganti nilainya.
PALET = {
    "gelap": {
        "latar": "#0a0a0a", "panel": "#111111", "panel2": "#0d0d0d", "sidebar": "#101010",
        "garis": "#2a2a2a", "kisi": "#1e1e1e", "kisi2": "#3a3a3a", "pemisah": "#1a1a1a",
        "teks": "#d8d8d8", "teks2": "#a8a8a8", "teks3": "#7a7a7a", "teks4": "#5f5f5f",
        "teks5": "#6f6f6f", "teks6": "#9a9a9a", "terang": "#e8e8e8", "diam": "#8a8a8a",
        "aksen": "#e08b2a", "aksen2": "#ffab4a", "naik": "#33d17a", "turun": "#e05252",
        "biru": "#4a90d9", "ungu": "#b06fd0", "kuning": "#f2d16b", "teal": "#5ab5b0",
        "coklat": "#c98a5e", "tbl_latar": "#1a1208", "tbl_garis": "#4a3418",
        "lembut": "#5a5a5a", "plotly": "plotly_dark",
    },
    "terang": {
        "latar": "#ffffff", "panel": "#fbfbfa", "panel2": "#ffffff", "sidebar": "#f5f4f2",
        "garis": "#e2e0dc", "kisi": "#eeecea", "kisi2": "#c9c6c1", "pemisah": "#eeecea",
        "teks": "#23211e", "teks2": "#4a4744", "teks3": "#6d6a66", "teks4": "#8c8985",
        "teks5": "#7d7a76", "teks6": "#4a4744", "terang": "#141312", "diam": "#8c8985",
        "aksen": "#a85f11", "aksen2": "#8a4c0a", "naik": "#137a43", "turun": "#b03028",
        "biru": "#2a5f9e", "ungu": "#6d3f8a", "kuning": "#8f6e14", "teal": "#1f6b66",
        "coklat": "#8a5730", "tbl_latar": "#fdf3e6", "tbl_garis": "#dfbc8e",
        "lembut": "#b5b2ad", "plotly": "plotly_white",
    },
}


def pal() -> dict:
    """Palet yang sedang aktif. Aman dipanggil sebelum tema tersimpan dibaca."""
    return PALET.get(st.session_state.get("tema", "gelap"), PALET["gelap"])


st.set_page_config(page_title="Terminal Ringan", page_icon="▚", layout="wide")

# Tema dibaca sebelum apa pun digambar, supaya tidak ada kedipan warna.
if "tema" not in st.session_state:
    tersimpan = muat_json_awal(BERKAS_PENGATURAN, {})
    st.session_state.tema = tersimpan.get("tema", "gelap")
    st.session_state.cek_otomatis = tersimpan.get("cek_otomatis", True)

GAYA = """
<style>
  :root {
__VARIABEL__
  }
  html, body, [class*="css"]  { font-family: "Consolas","JetBrains Mono",monospace; }
  .stApp { background-color: var(--latar); color: var(--teks); }
  section[data-testid="stSidebar"] { background-color: var(--sidebar); border-right: 1px solid var(--garis); }
  h1, h2, h3 { color: var(--aksen) !important; letter-spacing: 0.06em; }
  .kop {
      border-bottom: 1px solid var(--garis); padding: 0.35rem 0 0.6rem 0; margin-bottom: 0.9rem;
      display: flex; gap: 1.4rem; align-items: baseline; font-size: 0.82rem; color: var(--teks5);
      flex-wrap: wrap;
  }
  .kop .merek { color: var(--aksen); font-weight: 700; letter-spacing: 0.18em; font-size: 0.95rem; }
  .kop .hidup { color: var(--naik); }
  .naik { color: var(--naik); } .turun { color: var(--turun); } .diam { color: var(--diam); }
  .kartu {
      border: 1px solid var(--garis); border-radius: 3px; padding: 0.65rem 0.85rem;
      background: var(--panel); margin-bottom: 0.55rem;
  }
  .kartu .label { font-size: 0.66rem; color: var(--teks3); letter-spacing: 0.12em; }
  .kartu .angka { font-size: 1.18rem; font-weight: 600; color: var(--terang); }
  .kartu .delta { font-size: 0.78rem; }
  .catatan { font-size: 0.74rem; color: var(--teks5); line-height: 1.6; }
  .berita-judul { color: var(--teks); text-decoration: none; font-size: 0.88rem; }
  .berita-judul:hover { color: var(--aksen); }
  .berita-meta { color: var(--teks4); font-size: 0.7rem; }
  div[data-testid="stDataFrame"] { border: 1px solid var(--garis); }
  .stButton>button {
      background: var(--tbl_latar); color: var(--aksen); border: 1px solid var(--tbl_garis);
      border-radius: 2px; font-family: inherit; letter-spacing: 0.08em;
  }
  .stButton>button:hover { border-color: var(--aksen); color: var(--aksen2); }
  footer, #MainMenu { visibility: hidden; }

  /* ── Menyelaraskan komponen bawaan Streamlit dengan tema ──────────
     Streamlit menulis gayanya sendiri lewat JavaScript, bukan variabel CSS,
     jadi bagian ini perlu menimpanya secara tegas agar mode terang tidak
     menyisakan kotak-kotak gelap.                                        */

  /* Tabel data memakai grid berbasis kanvas dengan variabelnya sendiri */
  [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {
      --gdg-bg-cell: var(--panel);
      --gdg-bg-cell-medium: var(--panel2);
      --gdg-bg-header: var(--sidebar);
      --gdg-bg-header-hovered: var(--kisi);
      --gdg-bg-header-has-focus: var(--kisi);
      --gdg-bg-bubble: var(--panel);
      --gdg-bg-search-result: var(--tbl_latar);
      --gdg-text-dark: var(--teks);
      --gdg-text-medium: var(--teks2);
      --gdg-text-light: var(--teks3);
      --gdg-text-header: var(--teks3);
      --gdg-text-header-selected: var(--aksen);
      --gdg-border-color: var(--garis);
      --gdg-horizontal-border-color: var(--kisi);
      --gdg-accent-color: var(--aksen);
      --gdg-accent-light: var(--tbl_latar);
  }

  /* Kolom isian, angka, area teks, dropdown */
  .stTextInput input, .stNumberInput input, .stTextArea textarea,
  .stDateInput input, [data-baseweb="select"] > div, [data-baseweb="input"] {
      background-color: var(--panel) !important;
      color: var(--teks) !important;
      border-color: var(--garis) !important;
  }
  input::placeholder, textarea::placeholder { color: var(--teks4) !important; }

  /* Daftar pilihan yang mengambang */
  [data-baseweb="popover"] div, [data-baseweb="menu"], [data-baseweb="menu"] li {
      background-color: var(--panel) !important;
      color: var(--teks) !important;
  }
  [data-baseweb="menu"] li:hover { background-color: var(--kisi) !important; }

  /* Label, teks umum, pemisah */
  label, label p, .stMarkdown p, .stMarkdown li, .stRadio label, .stSlider label {
      color: var(--teks) !important;
  }
  hr, [data-testid="stDivider"] { border-color: var(--garis) !important; }

  /* Panel lipat */
  [data-testid="stExpander"] {
      border: 1px solid var(--garis) !important;
      background-color: var(--panel) !important;
      border-radius: 3px;
  }
  [data-testid="stExpander"] summary { color: var(--teks2) !important; }

  /* Tab */
  .stTabs [data-baseweb="tab"] { color: var(--teks3) !important; }
  .stTabs [aria-selected="true"] { color: var(--aksen) !important; }
  .stTabs [data-baseweb="tab-highlight"] { background-color: var(--aksen) !important; }
  .stTabs [data-baseweb="tab-border"] { background-color: var(--garis) !important; }

  /* Kotak pesan */
  [data-testid="stNotification"], .stAlert {
      background-color: var(--panel) !important;
      color: var(--teks) !important;
      border: 1px solid var(--garis) !important;
  }

  /* Kotak kode (nomor yang bisa disalin) */
  .stCode, pre, code {
      background-color: var(--panel) !important;
      color: var(--teks) !important;
  }

  /* Penanda geser */
  .stSlider [data-baseweb="slider"] div[role="slider"] { background-color: var(--aksen) !important; }
</style>
"""
def pasang_gaya():
    """Suntikkan palet aktif sebagai variabel CSS, lalu pasang seluruh gaya."""
    warna = "\n".join(f"    --{k}: {v};" for k, v in pal().items() if k != "plotly")
    st.markdown(GAYA.replace("__VARIABEL__", warna), unsafe_allow_html=True)


pasang_gaya()


# ──────────────────────────────────────────────────────────────────────
#  PENYIMPANAN LOKAL
# ──────────────────────────────────────────────────────────────────────

def muat_json(berkas: Path, bawaan):
    try:
        if berkas.exists():
            return json.loads(berkas.read_text(encoding="utf-8"))
    except Exception:
        pass
    return bawaan


def simpan_pengaturan() -> None:
    """Simpan seluruh pengaturan sekaligus, supaya satu tidak menimpa yang lain."""
    simpan_json(BERKAS_PENGATURAN, {
        "tema": st.session_state.get("tema", "gelap"),
        "cek_otomatis": st.session_state.get("cek_otomatis", True),
    })


def simpan_json(berkas: Path, isi) -> None:
    try:
        berkas.write_text(json.dumps(isi, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        st.warning(f"Gagal menyimpan {berkas.name}: {e}")


# ──────────────────────────────────────────────────────────────────────
#  PENGAMBIL DATA
# ──────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def ambil_kutipan(simbol: tuple) -> pd.DataFrame:
    """Harga terakhir dan perubahan harian untuk sekumpulan simbol."""
    import yfinance as yf

    if not simbol:
        return pd.DataFrame()

    try:
        # Ambil sebulan, bukan lima hari: selain harga terakhir kita juga butuh
        # deretan angka untuk grafik mungil di dalam kartu.
        data = yf.download(
            list(simbol), period="1mo", interval="1d",
            progress=False, group_by="ticker", auto_adjust=False, threads=True,
        )
    except Exception as e:
        st.error(f"Tidak bisa mengambil data harga: {e}")
        return pd.DataFrame()

    if data is None or len(data) == 0:
        return pd.DataFrame()

    baris = []
    for s in simbol:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if s not in data.columns.get_level_values(0):
                    continue
                sub = data[s]
            else:
                sub = data
            sub = sub.dropna(subset=["Close"])
            if len(sub) == 0:
                continue
            akhir = float(sub["Close"].iloc[-1])
            awal = float(sub["Close"].iloc[-2]) if len(sub) > 1 else akhir
            selisih = akhir - awal
            persen = (selisih / awal * 100) if awal else 0.0
            volume = float(sub["Volume"].iloc[-1]) if "Volume" in sub.columns else float("nan")
            baris.append({
                "Simbol": s,
                "Harga": akhir,
                "Perubahan": selisih,
                "Persen": persen,
                "Volume": volume,
                "Seri": [float(v) for v in sub["Close"].tail(30).tolist()],
            })
        except Exception:
            continue

    return pd.DataFrame(baris)


@st.cache_data(ttl=300, show_spinner=False)
def ambil_riwayat(simbol: str, periode: str, interval: str) -> pd.DataFrame:
    import yfinance as yf
    try:
        df = yf.Ticker(simbol).history(period=periode, interval=interval)
        return df.dropna()
    except Exception as e:
        st.error(f"Tidak bisa mengambil riwayat {simbol}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def ambil_berita(umpan: dict, batas: int = 12) -> list:
    import feedparser
    hasil = []
    for nama, url in umpan.items():
        try:
            f = feedparser.parse(url)
            for e in f.entries[:batas]:
                waktu = None
                if getattr(e, "published_parsed", None):
                    waktu = datetime(*e.published_parsed[:6])
                hasil.append({
                    "sumber": nama,
                    "judul": getattr(e, "title", "(tanpa judul)"),
                    "tautan": getattr(e, "link", ""),
                    "waktu": waktu,
                })
        except Exception:
            continue
    hasil.sort(key=lambda x: x["waktu"] or datetime(1970, 1, 1), reverse=True)
    return hasil


def _angka(x):
    """Ubah apa pun jadi float, atau NaN kalau tidak masuk akal."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return float("nan") if (math.isnan(f) or math.isinf(f)) else f


@st.cache_data(ttl=3600, show_spinner=False)
def ambil_fundamental_banyak(simbol: tuple) -> pd.DataFrame:
    """Rasio keuangan untuk banyak saham sekaligus, diambil paralel."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor

    def satu(s):
        try:
            info = yf.Ticker(s).info
            if not isinstance(info, dict) or not info.get("regularMarketPrice"):
                return None
            dy = _angka(info.get("dividendYield"))
            # yfinance tidak konsisten: kadang 0,045 kadang 4,5. Samakan ke persen.
            if not math.isnan(dy) and dy < 1:
                dy *= 100
            kap = _angka(info.get("marketCap"))
            utang = _angka(info.get("totalDebt"))
            kas = _angka(info.get("totalCash"))
            return {
                "Simbol": s,
                "Nama": info.get("shortName") or info.get("longName") or s,
                "Sektor": info.get("sector") or "—",
                "Industri": info.get("industry") or "—",
                "Utang": utang,
                "Kas": kas,
                "Utang/Kap %": (utang / kap * 100) if kap else float("nan"),
                "Kas/Kap %": (kas / kap * 100) if kap else float("nan"),
                "Harga": _angka(info.get("regularMarketPrice")),
                "Kapitalisasi": _angka(info.get("marketCap")),
                "PER": _angka(info.get("trailingPE")),
                "PBV": _angka(info.get("priceToBook")),
                "ROE %": _angka(info.get("returnOnEquity")) * 100,
                "Margin %": _angka(info.get("profitMargins")) * 100,
                "DER": _angka(info.get("debtToEquity")),
                "Dividen %": dy,
                "Tumbuh Laba %": _angka(info.get("earningsGrowth")) * 100,
                "Tumbuh Omzet %": _angka(info.get("revenueGrowth")) * 100,
                "Beta": _angka(info.get("beta")),
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as kolam:
        hasil = [h for h in kolam.map(satu, simbol) if h]

    return pd.DataFrame(hasil) if hasil else pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def ambil_fundamental_satu(simbol: str) -> dict:
    import yfinance as yf
    try:
        info = yf.Ticker(simbol).info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def ambil_laporan(simbol: str) -> dict:
    """Laporan keuangan tahunan — laba rugi, neraca, arus kas."""
    import yfinance as yf
    try:
        t = yf.Ticker(simbol)
        return {
            "laba_rugi": t.income_stmt,
            "neraca": t.balance_sheet,
            "arus_kas": t.cashflow,
        }
    except Exception:
        return {}


@st.cache_data(ttl=180, show_spinner=False)
def ambil_kripto_screener(jumlah: int = 100) -> pd.DataFrame:
    """Koin untuk penyaringan — satu permintaan, banyak koin sekaligus."""
    import requests
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc",
                    "per_page": min(jumlah, 250), "page": 1,
                    "price_change_percentage": "24h,7d,30d"},
            timeout=25,
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        return pd.DataFrame([{
            "Simbol": (c.get("symbol") or "").upper(),
            "Nama": c.get("name"),
            "Harga": _angka(c.get("current_price")),
            "Kapitalisasi": _angka(c.get("market_cap")),
            "Volume": _angka(c.get("total_volume")),
            "24 jam %": _angka(c.get("price_change_percentage_24h_in_currency")),
            "7 hari %": _angka(c.get("price_change_percentage_7d_in_currency")),
            "30 hari %": _angka(c.get("price_change_percentage_30d_in_currency")),
            "Dari puncak %": _angka(c.get("ath_change_percentage")),
            "Peringkat": _angka(c.get("market_cap_rank")),
        } for c in data])
    except Exception:
        return pd.DataFrame()


def alamat_sah(jaringan: str, alamat: str) -> bool:
    import re
    j = JARINGAN.get(jaringan)
    return bool(j) and bool(re.match(j["pola"], (alamat or "").strip()))


@st.cache_data(ttl=120, show_spinner=False)
def ambil_harga_koin(koin: tuple) -> dict:
    """Harga beberapa koin dalam USD dan IDR sekaligus — sumber: CoinGecko."""
    import requests
    if not koin:
        return {}
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ",".join(koin), "vs_currencies": "usd,idr",
                    "include_24hr_change": "true"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json() or {}
    except Exception:
        return {}


@st.cache_data(ttl=120, show_spinner=False)
def ambil_saldo_dompet(jaringan: str, alamat: str) -> dict:
    """
    Baca saldo sebuah alamat publik. Tidak ada API key, tidak ada kunci pribadi.
    Kembalikan {'saldo': float, 'transaksi': int, 'token': [...], 'galat': str}.
    """
    import requests
    alamat = (alamat or "").strip()
    if not alamat_sah(jaringan, alamat):
        return {"galat": "Format alamat tidak sesuai untuk jaringan ini."}

    try:
        if jaringan == "Bitcoin":
            r = requests.get(f"https://blockstream.info/api/address/{alamat}", timeout=20)
            r.raise_for_status()
            d = r.json()
            ck, mp = d.get("chain_stats", {}), d.get("mempool_stats", {})
            sat = (ck.get("funded_txo_sum", 0) - ck.get("spent_txo_sum", 0)
                   + mp.get("funded_txo_sum", 0) - mp.get("spent_txo_sum", 0))
            return {"saldo": sat / 1e8,
                    "transaksi": ck.get("tx_count", 0) + mp.get("tx_count", 0),
                    "token": []}

        if jaringan == "Ethereum":
            # "freekey" adalah kunci umum resmi Ethplorer untuk pemakaian ringan.
            r = requests.get(f"https://api.ethplorer.io/getAddressInfo/{alamat}",
                             params={"apiKey": "freekey"}, timeout=25)
            r.raise_for_status()
            d = r.json()
            if d.get("error"):
                return {"galat": str(d["error"].get("message", "Alamat tidak ditemukan."))}
            token = []
            for t in (d.get("tokens") or [])[:40]:
                info = t.get("tokenInfo", {})
                try:
                    des = int(info.get("decimals") or 18)
                    jml = float(t.get("rawBalance", 0)) / (10 ** des)
                except (TypeError, ValueError):
                    continue
                if jml <= 0:
                    continue
                harga = (info.get("price") or {})
                token.append({
                    "nama": info.get("name") or "—",
                    "kode": (info.get("symbol") or "—")[:12],
                    "jumlah": jml,
                    "nilai_usd": jml * float(harga.get("rate", 0) or 0)
                    if isinstance(harga, dict) else 0.0,
                })
            return {"saldo": float((d.get("ETH") or {}).get("balance", 0) or 0),
                    "transaksi": int(d.get("countTxs", 0) or 0),
                    "token": sorted(token, key=lambda x: -x["nilai_usd"])}

        if jaringan == "Solana":
            r = requests.post(
                "https://api.mainnet-beta.solana.com",
                json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [alamat]},
                timeout=20,
            )
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                return {"galat": str(d["error"].get("message", "Alamat tidak ditemukan."))}
            lamport = (d.get("result") or {}).get("value", 0)
            return {"saldo": lamport / 1e9, "transaksi": None, "token": []}

    except requests.exceptions.HTTPError as e:
        kode = getattr(e.response, "status_code", "?")
        if kode == 400:
            return {"galat": "Alamat ditolak jaringan. Periksa lagi penulisannya."}
        if kode == 429:
            return {"galat": "Terlalu banyak permintaan. Tunggu sebentar lalu coba lagi."}
        return {"galat": f"Jaringan menolak permintaan (kode {kode})."}
    except Exception:
        return {"galat": "Tidak bisa menghubungi jaringan. Periksa koneksi internet Anda."}

    return {"galat": "Jaringan belum didukung."}


@st.cache_data(ttl=180, show_spinner=False)
def ambil_kripto_global() -> dict:
    """Ringkasan pasar kripto sedunia — sumber: CoinGecko (gratis, tanpa API key)."""
    import requests
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=20)
        r.raise_for_status()
        d = r.json().get("data", {})
        return {
            "kapitalisasi": d.get("total_market_cap", {}).get("usd"),
            "volume": d.get("total_volume", {}).get("usd"),
            "perubahan": d.get("market_cap_change_percentage_24h_usd"),
            "dominasi_btc": d.get("market_cap_percentage", {}).get("btc"),
            "dominasi_eth": d.get("market_cap_percentage", {}).get("eth"),
            "jumlah_koin": d.get("active_cryptocurrencies"),
        }
    except Exception:
        return {}


@st.cache_data(ttl=180, show_spinner=False)
def ambil_kripto_teratas(jumlah: int = 12) -> pd.DataFrame:
    """Koin terbesar berdasarkan kapitalisasi pasar — sumber: CoinGecko."""
    import requests
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "order": "market_cap_desc",
                    "per_page": jumlah, "page": 1, "price_change_percentage": "24h,7d"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        return pd.DataFrame([{
            "Koin": (c.get("symbol") or "").upper(),
            "Nama": c.get("name"),
            "Harga": c.get("current_price"),
            "24 jam %": c.get("price_change_percentage_24h_in_currency"),
            "7 hari %": c.get("price_change_percentage_7d_in_currency"),
            "Kapitalisasi": c.get("market_cap"),
            "Volume 24 jam": c.get("total_volume"),
        } for c in data])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def ambil_takut_serakah() -> dict:
    """Indeks Takut & Serakah kripto — sumber: alternative.me (gratis)."""
    import requests
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20)
        r.raise_for_status()
        d = r.json().get("data", [])
        if not d:
            return {}
        return {"nilai": int(d[0]["value"]), "sebutan": d[0].get("value_classification", "")}
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def ambil_bank_dunia(kode_negara: str, indikator: str) -> pd.DataFrame:
    import requests
    url = (f"https://api.worldbank.org/v2/country/{kode_negara}"
           f"/indicator/{indikator}?format=json&per_page=70")
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        js = r.json()
        if not isinstance(js, list) or len(js) < 2 or js[1] is None:
            return pd.DataFrame()
        baris = [{"Tahun": int(d["date"]), "Nilai": d["value"]}
                 for d in js[1] if d.get("value") is not None]
        if not baris:
            return pd.DataFrame()
        return pd.DataFrame(baris).sort_values("Tahun")
    except Exception:
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────
#  PERHITUNGAN INDIKATOR
# ──────────────────────────────────────────────────────────────────────

def hitung_rsi(harga: pd.Series, periode: int = 14) -> pd.Series:
    selisih = harga.diff()
    naik = selisih.clip(lower=0).ewm(alpha=1 / periode, adjust=False).mean()
    turun = (-selisih.clip(upper=0)).ewm(alpha=1 / periode, adjust=False).mean()
    # Pembagian dengan nol di sini justru benar secara matematis:
    #   naik>0, turun=0  -> rs tak hingga -> RSI = 100 (naik tanpa jeda)
    #   naik=0, turun=0  -> rs tak tentu  -> RSI = 50  (harga diam)
    rs = naik / turun
    return (100 - 100 / (1 + rs)).fillna(50)


# ──────────────────────────────────────────────────────────────────────
#  PEMBARUAN APLIKASI
# ──────────────────────────────────────────────────────────────────────

def urai_versi(v: str) -> tuple:
    """'1.2.10' -> (1, 2, 10) supaya bisa dibandingkan sebagai angka, bukan teks."""
    bagian = []
    for x in str(v).strip().split("."):
        angka = "".join(c for c in x if c.isdigit())
        bagian.append(int(angka) if angka else 0)
    while len(bagian) < 3:
        bagian.append(0)
    return tuple(bagian[:3])


def inang_tepercaya(url: str) -> bool:
    """Hanya izinkan HTTPS ke inang yang sudah ditentukan di kode."""
    from urllib.parse import urlparse
    try:
        u = urlparse(url)
    except Exception:
        return False
    return u.scheme == "https" and u.netloc.lower() in INANG_TEPERCAYA


@st.cache_data(ttl=21600, show_spinner=False)
def cek_pembaruan(url: str) -> dict:
    """Baca keterangan versi terbaru. Tidak mengunduh kode apa pun di sini."""
    import requests
    if not inang_tepercaya(url):
        return {"galat": "Alamat pembaruan tidak memenuhi syarat keamanan."}
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"galat": f"Tidak bisa menghubungi server pembaruan ({type(e).__name__})."}

    if not isinstance(d, dict) or "versi" not in d:
        return {"galat": "Keterangan versi tidak dikenali bentuknya."}

    d["lebih_baru"] = urai_versi(d["versi"]) > urai_versi(VERSI)
    return d


def unduh_dan_periksa(url: str, sidik_harap: str):
    """
    Unduh satu berkas lalu cocokkan sidik jarinya.

    Sidik jari SHA-256 adalah inti pengamanannya. Tanpa itu, siapa pun yang bisa
    menyisipkan diri di jalur unduhan bisa menukar isinya dengan kode lain, dan
    aplikasi akan menjalankannya tanpa curiga.
    """
    import hashlib
    import requests

    if not inang_tepercaya(url):
        return None, "Alamat berkas berada di luar daftar inang tepercaya."
    if not sidik_harap or len(sidik_harap) != 64:
        return None, "Sidik jari SHA-256 tidak ada atau tidak sah."

    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        isi = r.content
    except Exception as e:
        return None, f"Gagal mengunduh ({type(e).__name__})."

    if len(isi) > 20 * 1024 * 1024:
        return None, "Berkas terlalu besar, dibatalkan."

    sidik = hashlib.sha256(isi).hexdigest()
    if sidik.lower() != sidik_harap.lower():
        return None, ("Sidik jari berkas TIDAK COCOK dengan yang diumumkan. "
                      "Pembaruan dibatalkan demi keamanan.")
    return isi, None


def terapkan_pembaruan(manifes: dict):
    """Unduh semua berkas, periksa semuanya dulu, baru tulis. Kembalikan (berhasil, pesan)."""
    berkas = manifes.get("berkas")
    if not isinstance(berkas, dict) or not berkas:
        return False, "Keterangan versi tidak memuat daftar berkas."

    # Tahap 1 — unduh dan periksa SEMUANYA lebih dulu.
    # Menulis satu per satu sambil mengunduh berisiko meninggalkan aplikasi
    # dalam keadaan setengah diperbarui kalau salah satu gagal di tengah.
    siap = {}
    for nama, info in berkas.items():
        if nama not in BERKAS_BOLEH_DIPERBARUI:
            return False, f"Pembaruan mencoba mengganti berkas yang tidak diizinkan: {nama}"
        if not isinstance(info, dict):
            return False, f"Keterangan berkas {nama} tidak dikenali."
        isi, galat = unduh_dan_periksa(info.get("url", ""), info.get("sha256", ""))
        if galat:
            return False, f"{nama}: {galat}"
        siap[nama] = isi

    # Tahap 2 — simpan salinan versi sekarang, supaya bisa dikembalikan.
    import shutil
    cap = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = DIR_CADANGAN / f"v{VERSI}-{cap}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for nama in siap:
            asal = BASE_DIR / nama
            if asal.exists():
                shutil.copy2(asal, folder / nama)
    except Exception as e:
        return False, f"Gagal menyimpan salinan cadangan: {e}"

    # Tahap 3 — tulis berkas baru.
    try:
        for nama, isi in siap.items():
            sementara = BASE_DIR / f"{nama}.baru"
            sementara.write_bytes(isi)
            os.replace(sementara, BASE_DIR / nama)
    except Exception as e:
        return False, (f"Gagal menulis berkas: {e}. Salinan versi lama ada di "
                       f"folder cadangan/{folder.name}.")

    return True, (f"{len(siap)} berkas diperbarui ke versi {manifes.get('versi')}. "
                  f"Salinan versi lama disimpan di cadangan/{folder.name}.")


def daftar_cadangan() -> list:
    if not DIR_CADANGAN.is_dir():
        return []
    return sorted((d for d in DIR_CADANGAN.iterdir() if d.is_dir()), reverse=True)


def kembalikan_cadangan(folder) -> tuple:
    import shutil
    try:
        jumlah = 0
        for berkas in folder.iterdir():
            if berkas.name in BERKAS_BOLEH_DIPERBARUI:
                shutil.copy2(berkas, BASE_DIR / berkas.name)
                jumlah += 1
        return True, f"{jumlah} berkas dikembalikan dari {folder.name}."
    except Exception as e:
        return False, f"Gagal mengembalikan: {e}"


def mata_uang_pasangan(simbol: str):
    """Pecah 'EURUSD=X' jadi ('EUR', 'USD'). Kembalikan (None, None) kalau bukan forex."""
    s = (simbol or "").upper().replace("=X", "")
    if len(s) != 6 or not s.isalpha():
        return None, None
    return s[:3], s[3:]


def ukuran_pip(simbol: str, harga: float = None) -> float:
    """
    Besar satu pip. Aturannya tidak seragam antar pasangan:
      - pasangan ber-JPY memakai 0,01 karena kuotasinya dua desimal
      - pasangan ber-IDR memakai 1 karena angkanya ribuan
      - selebihnya 0,0001
    """
    dasar, kutip = mata_uang_pasangan(simbol)
    if kutip in ("JPY",):
        return 0.01
    if kutip in ("IDR", "KRW", "VND"):
        return 1.0
    if kutip is None:
        # Bukan pasangan yang dikenali — perkirakan dari besaran harganya.
        if harga and harga >= 1000:
            return 1.0
        if harga and harga >= 50:
            return 0.01
        return 0.0001
    return 0.0001


def nilai_pip(simbol: str, harga: float, unit: int, kurs_kutip_ke_idr: float = None) -> dict:
    """
    Nilai satu pip untuk ukuran posisi tertentu.

    Nilai pip selalu lahir dalam mata uang KUTIPAN (yang di belakang). Untuk
    pemakai Indonesia, angka itu baru berarti setelah ditukar ke rupiah — dan
    itulah yang paling sering dilewatkan orang saat menghitung risiko.
    """
    pip = ukuran_pip(simbol, harga)
    dasar, kutip = mata_uang_pasangan(simbol)
    nilai_kutip = pip * unit
    hasil = {"pip": pip, "unit": unit, "mata_uang_kutip": kutip or "?",
             "nilai_kutip": nilai_kutip, "nilai_idr": float("nan")}
    if kutip == "IDR":
        hasil["nilai_idr"] = nilai_kutip
    elif kurs_kutip_ke_idr:
        hasil["nilai_idr"] = nilai_kutip * kurs_kutip_ke_idr
    return hasil


@st.cache_data(ttl=300, show_spinner=False)
def ambil_kurs_ke_idr(mata_uang: str) -> float:
    """Berapa rupiah untuk satu satuan mata uang ini."""
    mata_uang = (mata_uang or "").upper()
    if mata_uang == "IDR":
        return 1.0
    df = ambil_kutipan((f"{mata_uang}IDR=X",))
    if df.empty:
        return float("nan")
    return float(df.iloc[0]["Harga"])


def hitung_atr(df: pd.DataFrame, periode: int = 14) -> pd.Series:
    """Average True Range — ukuran seberapa lebar harga bergerak tiap hari."""
    tinggi, rendah, tutup = df["High"], df["Low"], df["Close"]
    sebelum = tutup.shift(1)
    rentang = pd.concat([
        tinggi - rendah,
        (tinggi - sebelum).abs(),
        (rendah - sebelum).abs(),
    ], axis=1).max(axis=1)
    # Wilder memakai perataan 1/n, bukan 2/(n+1) seperti EMA biasa.
    return rentang.ewm(alpha=1 / periode, adjust=False).mean()


def hitung_adx(df: pd.DataFrame, periode: int = 14):
    """
    ADX mengukur *kekuatan* tren, bukan arahnya. Di bawah 20 biasanya berarti
    harga bergerak menyamping; di atas 25 berarti ada tren yang jelas.
    """
    tinggi, rendah = df["High"], df["Low"]
    naik = tinggi.diff()
    turun = -rendah.diff()

    dm_naik = pd.Series(0.0, index=df.index)
    dm_turun = pd.Series(0.0, index=df.index)
    dm_naik[(naik > turun) & (naik > 0)] = naik
    dm_turun[(turun > naik) & (turun > 0)] = turun

    atr = hitung_atr(df, periode).replace(0, float("nan"))
    di_naik = 100 * dm_naik.ewm(alpha=1 / periode, adjust=False).mean() / atr
    di_turun = 100 * dm_turun.ewm(alpha=1 / periode, adjust=False).mean() / atr

    jumlah = (di_naik + di_turun).replace(0, float("nan"))
    dx = 100 * (di_naik - di_turun).abs() / jumlah
    adx = dx.ewm(alpha=1 / periode, adjust=False).mean()
    return adx.fillna(0), di_naik.fillna(0), di_turun.fillna(0)


def cari_titik_balik(df: pd.DataFrame, jendela: int = 5):
    """
    Titik balik = harga tertinggi (atau terendah) di antara tetangga kiri-kanannya.
    Ini cara paling sederhana dan paling jujur menemukan puncak dan lembah.
    """
    tinggi, rendah = df["High"].values, df["Low"].values
    n = len(df)
    puncak, lembah = [], []

    # Syaratnya tidak simetris — kiri boleh sama tinggi, kanan harus lebih rendah.
    # Ini menangani harga yang mendatar beberapa hari (sering terjadi pada saham
    # tipis atau saat auto-reject): satu puncak diambil, bukan nol seperti kalau
    # kita menuntut nilainya benar-benar tunggal.
    for i in range(jendela, n - jendela):
        kiri_t = tinggi[i - jendela:i]
        kanan_t = tinggi[i + 1:i + jendela + 1]
        if (tinggi[i] >= kiri_t).all() and (tinggi[i] > kanan_t).all():
            puncak.append((df.index[i], float(tinggi[i])))

        kiri_r = rendah[i - jendela:i]
        kanan_r = rendah[i + 1:i + jendela + 1]
        if (rendah[i] <= kiri_r).all() and (rendah[i] < kanan_r).all():
            lembah.append((df.index[i], float(rendah[i])))

    return puncak, lembah


def kumpulkan_level(titik: list, toleransi: float, minimal: int = 2) -> list:
    """
    Gabungkan titik balik yang harganya berdekatan jadi satu level.
    Makin sering harga menyentuh level itu, makin berarti dia.
    """
    if not titik:
        return []
    harga = sorted(h for _, h in titik)
    gugus, sekarang = [], [harga[0]]
    for h in harga[1:]:
        if abs(h - sekarang[-1]) <= toleransi:
            sekarang.append(h)
        else:
            gugus.append(sekarang)
            sekarang = [h]
    gugus.append(sekarang)
    return sorted(
        ({"harga": sum(g) / len(g), "sentuhan": len(g)} for g in gugus if len(g) >= minimal),
        key=lambda x: -x["sentuhan"],
    )


def kemiringan_tren(harga: pd.Series) -> dict:
    """Garis lurus terbaik pada harga (skala logaritma) — arah dan keandalannya."""
    import numpy as np
    y = harga.dropna()
    if len(y) < 10:
        return {"persen_tahun": float("nan"), "keandalan": float("nan"), "garis": None}
    log_y = np.log(y.values)
    x = np.arange(len(log_y), dtype=float)
    kemiringan, potong = np.polyfit(x, log_y, 1)
    ramal = kemiringan * x + potong
    sisa = log_y - ramal
    varian = log_y.var()
    keandalan = 1 - (sisa.var() / varian) if varian > 0 else float("nan")
    return {
        "persen_tahun": (math.exp(kemiringan * 252) - 1) * 100,
        "keandalan": keandalan * 100 if not math.isnan(keandalan) else float("nan"),
        "garis": pd.Series(np.exp(ramal), index=y.index),
    }


def hitung_macd(harga: pd.Series, cepat=12, lambat=26, sinyal=9):
    ema_cepat = harga.ewm(span=cepat, adjust=False).mean()
    ema_lambat = harga.ewm(span=lambat, adjust=False).mean()
    macd = ema_cepat - ema_lambat
    garis_sinyal = macd.ewm(span=sinyal, adjust=False).mean()
    return macd, garis_sinyal, macd - garis_sinyal


# ──────────────────────────────────────────────────────────────────────
#  ALAT TAMPILAN
# ──────────────────────────────────────────────────────────────────────

def warna(nilai) -> str:
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        return "diam"
    if math.isnan(nilai):
        return "diam"
    return "naik" if nilai > 0 else ("turun" if nilai < 0 else "diam")


def format_angka(x, desimal: int = 2) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(x):
        return "—"
    return f"{x:,.{desimal}f}"


def format_ringkas(x, mata_uang: str = "$") -> str:
    """Ubah angka besar jadi bentuk pendek: 3,4 T · 812 M · 45 jt."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(x):
        return "—"
    tanda = "-" if x < 0 else ""
    x = abs(x)
    for batas, satuan in ((1e12, " T"), (1e9, " M"), (1e6, " jt"), (1e3, " rb")):
        if x >= batas:
            return f"{tanda}{mata_uang}{x / batas:,.2f}{satuan}"
    return f"{tanda}{mata_uang}{x:,.2f}"


def format_harga_koin(x) -> str:
    """Koin murah butuh lebih banyak angka di belakang koma."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(x):
        return "—"
    if x >= 1000:
        return f"${x:,.0f}"
    if x >= 1:
        return f"${x:,.2f}"
    if x >= 0.01:
        return f"${x:,.4f}"
    return f"${x:,.8f}".rstrip("0")


def kartu(label: str, angka: str, delta: str = "", kelas: str = "diam"):
    st.markdown(
        f'<div class="kartu"><div class="label">{label}</div>'
        f'<div class="angka">{angka}</div>'
        f'<div class="delta {kelas}">{delta}</div></div>',
        unsafe_allow_html=True,
    )


def warna_kelas(kelas: str) -> str:
    """Warna untuk arah harga, mengikuti tema yang sedang aktif."""
    return pal().get({"naik": "naik", "turun": "turun"}.get(kelas, "diam"))


def grafik_mungil(nilai, kelas: str = "diam", lebar: int = 220, tinggi: int = 44) -> str:
    """Garis tren mungil sebagai SVG — ringan, tanpa perlu pustaka grafik."""
    # Saring satu per satu: deret dari bursa kadang berlubang (hari libur,
    # perdagangan dihentikan), dan satu nilai kosong tak boleh merusak seluruh kartu.
    bersih = []
    for v in nilai or []:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        bersih.append(f)
    nilai = bersih
    if len(nilai) < 2:
        return ""

    rendah, tinggi_nilai = min(nilai), max(nilai)
    rentang = (tinggi_nilai - rendah) or 1.0
    n = len(nilai)
    pad = 3

    titik = [
        (i / (n - 1) * lebar,
         tinggi - pad - (v - rendah) / rentang * (tinggi - 2 * pad))
        for i, v in enumerate(nilai)
    ]
    garis = " ".join(f"{x:.2f},{y:.2f}" for x, y in titik)
    bidang = f"0,{tinggi} " + garis + f" {lebar},{tinggi}"
    c = warna_kelas(kelas)
    uid = f"g{abs(hash((tuple(nilai[:4]), kelas))) % 100000}"

    return (
        f'<svg viewBox="0 0 {lebar} {tinggi}" preserveAspectRatio="none" '
        f'style="width:100%;height:{tinggi}px;display:block;margin-top:0.45rem;">'
        f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{c}" stop-opacity="0.28"/>'
        f'<stop offset="100%" stop-color="{c}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{bidang}" fill="url(#{uid})"/>'
        f'<polyline points="{garis}" fill="none" stroke="{c}" stroke-width="1.4" '
        f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        f'</svg>'
    )


def kartu_pasar(nama: str, harga: str, selisih: str, persen: str,
                seri=None, catatan: str = ""):
    """Kartu besar: nama, harga, perubahan, dan garis tren 30 hari."""
    try:
        arah = float(persen.replace("%", "").replace("+", "").replace(",", ""))
    except (ValueError, AttributeError):
        arah = 0.0
    kelas = "naik" if arah > 0 else ("turun" if arah < 0 else "diam")
    panah = "▲" if arah > 0 else ("▼" if arah < 0 else "•")
    c = warna_kelas(kelas)

    st.markdown(
        f'<div class="kartu" style="border-left:2px solid {c};padding:0.7rem 0.9rem 0.5rem;">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
        f'<span class="label">{nama}</span>'
        f'<span style="color:{c};font-size:0.72rem;">{panah} {persen}</span>'
        f'</div>'
        f'<div class="angka" style="margin-top:0.15rem;">{harga}</div>'
        f'<div class="delta {kelas}" style="font-size:0.74rem;">{selisih}'
        f'{"  ·  " + catatan if catatan else ""}</div>'
        f'{grafik_mungil(seri or [], kelas)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def petak_pasar(peta: dict, per_baris: int = 3, sufiks: str = ""):
    """Susun kartu pasar dalam petak rapi dari sekumpulan simbol."""
    df = ambil_kutipan(tuple(peta))
    if df.empty:
        st.warning("Data tidak bisa diambil sekarang. Periksa koneksi internet Anda, "
                   "lalu tekan MUAT ULANG.")
        return

    isian = list(peta.items())
    for i in range(0, len(isian), per_baris):
        kolom = st.columns(per_baris)
        for k, (simbol, nama) in zip(kolom, isian[i:i + per_baris]):
            with k:
                baris = df[df["Simbol"] == simbol]
                if baris.empty:
                    kartu(nama, "—", "data tidak tersedia")
                    continue
                r = baris.iloc[0]
                kartu_pasar(
                    nama,
                    format_angka(r["Harga"]) + sufiks,
                    f'{r["Perubahan"]:+,.2f}',
                    f'{r["Persen"]:+.2f}%',
                    r.get("Seri"),
                )


def periksa_qris():
    """Kembalikan (jalur, ada, pesan_kesalahan) untuk gambar QR donasi."""
    d = PROFIL["donasi"]
    qris = BASE_DIR / d.get("berkas_qris", "")
    if not d.get("berkas_qris") or not qris.is_file():
        return qris, False, ""

    # Berkas ada belum tentu berkas gambar. Kalau isinya rusak atau salah format,
    # beri pesan yang ramah — jangan sampai seluruh halaman ikut mati.
    try:
        from PIL import Image
        with Image.open(qris) as gambar:
            gambar.verify()
    except Exception:
        return qris, False, (
            f'Berkas <code>{d["berkas_qris"]}</code> ada, tetapi tidak bisa dibaca '
            f'sebagai gambar. Pastikan itu memang berkas PNG atau JPG hasil ekspor '
            f'dari aplikasi DANA, bukan berkas lain yang kebetulan bernama sama.'
        )
    return qris, True, ""


def kartu_donasi(ringkas: bool = False):
    """Ajakan dukungan sukarela — menggantikan tombol Deploy bawaan Streamlit."""
    d = PROFIL["donasi"]
    qris, ada_qris, pesan_qris = periksa_qris()

    if ringkas:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);'
            f'padding:0.6rem 0.7rem;margin-bottom:0;">'
            f'<div class="label">DUKUNG PENGEMBANGAN</div>'
            + (''  # QR sudah memuat semua keterangan, tak perlu diulang sebagai teks
               if ada_qris else
               f'<div style="color:var(--aksen);font-size:0.98rem;font-weight:700;'
               f'letter-spacing:0.04em;margin-top:0.2rem;">{d["layanan"]} {d["nomor"]}</div>'
               f'<div style="color:var(--teks3);font-size:0.68rem;margin-top:0.15rem;">'
               f'a.n. {d["atas_nama"]}</div>')
            + '</div>',
            unsafe_allow_html=True,
        )
        if ada_qris:
            try:
                st.image(str(qris), use_container_width=True)
                st.markdown(
                    f'<div class="catatan" style="text-align:center;margin-top:-0.4rem;">'
                    f'{d.get("keterangan_qris", "Pindai untuk mengirim dukungan")}</div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                pass
        return

    kiri, kanan = st.columns([1, 2]) if ada_qris else (None, st.container())

    if ada_qris:
        with kiri:
            try:
                st.image(str(qris), use_container_width=True)
                st.markdown(
                    f'<div class="catatan" style="text-align:center;">'
                    f'{d.get("keterangan_qris", "Pindai untuk mengirim dukungan")}</div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    '<div class="catatan">Gambar QRIS gagal ditampilkan.</div>',
                    unsafe_allow_html=True,
                )

    with kanan:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);padding:0.9rem 1.1rem;">'
            f'<div class="label">DUKUNG PENGEMBANGAN</div>'
            f'<div style="color:var(--teks2);font-size:0.8rem;line-height:1.7;margin:0.35rem 0 0.6rem;">'
            f'Terminal Ringan gratis dan akan tetap gratis. Kalau aplikasi ini berguna bagi Anda '
            f'dan ingin ikut menjaganya tetap hidup, dukungan sukarela lewat {d["layanan"]} '
            f'sangat berarti — sekecil apa pun.</div>'
            + ('' if ada_qris else
               f'<div style="display:flex;gap:0.8rem;align-items:baseline;flex-wrap:wrap;">'
               f'<span style="color:var(--aksen);font-size:1.3rem;font-weight:700;'
               f'letter-spacing:0.06em;">{d["nomor"]}</span>'
               f'<span style="color:var(--teks3);font-size:0.76rem;">'
               f'{d["layanan"]} · a.n. {d["atas_nama"]}</span></div>')
            + '</div>',
            unsafe_allow_html=True,
        )

        if not ada_qris:
            st.code(d["nomor_salin"], language=None)
            st.markdown(
                f'<div class="catatan">{pesan_qris or "Belum ada gambar QRIS."} '
                f'Ekspor dari aplikasi DANA, simpan sebagai <code>aset/qris.png</code>, '
                f'lalu muat ulang halaman ini — panduannya ada di '
                f'<code>aset/CARA-PASANG-QRIS.md</code>.</div>',
                unsafe_allow_html=True,
            )


def kop_halaman():
    jam = datetime.now().strftime("%d %b %Y  %H:%M")
    st.markdown(
        f'<div class="kop">'
        f'<span class="merek">TERMINAL RINGAN</span>'
        f'<span class="hidup">● DATA TERBUKA</span>'
        f'<span>TANPA KREDIT · TANPA API KEY</span>'
        f'<span>{jam}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 1 — PASAR
# ──────────────────────────────────────────────────────────────────────

def halaman_pasar():
    st.subheader("Denyut Pasar")

    t1, t2, t5, t3, t4 = st.tabs(["Indeks Dunia", "Kripto", "Forex",
                                  "Komoditas & Kurs", "Saham Indonesia"])

    with t1:
        petak_pasar(INDEKS_PANTAU, per_baris=3)
        st.markdown(
            '<div class="catatan">Garis di tiap kartu menggambarkan pergerakan 30 hari '
            'terakhir. Bursa yang sedang tutup menampilkan harga penutupan terakhir.</div>',
            unsafe_allow_html=True,
        )

    with t2:
        bagian_kripto()

    with t3:
        petak_pasar(KOMODITAS_PANTAU, per_baris=3)
        st.markdown(
            '<div class="catatan">Emas dan perak dalam dolar per troy ounce, minyak per barel. '
            'USD/IDR adalah kurs pasar, bukan kurs jual-beli bank.</div>',
            unsafe_allow_html=True,
        )

    with t5:
        bagian_forex()

    with t4:
        petak_pasar(SAHAM_IDX_PANTAU, per_baris=4)
        st.markdown(
            '<div class="catatan">Sembilan saham berkapitalisasi besar di Bursa Efek Indonesia. '
            'Harga dalam rupiah per lembar. Daftar ini bisa diubah lewat '
            '<code>SAHAM_IDX_PANTAU</code> di bagian pengaturan berkas.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    kiri, kanan = st.columns([3, 1])
    with kiri:
        st.subheader("Watchlist")
    with kanan:
        if st.button("⟳  MUAT ULANG", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    watchlist = st.session_state.watchlist

    with st.expander("Ubah daftar pantauan"):
        a, b = st.columns([3, 1])
        with a:
            baru = st.text_input(
                "Tambah simbol",
                placeholder="Contoh: BMRI.JK, GOTO.JK, NVDA, ETH-USD",
                label_visibility="collapsed",
            )
        with b:
            if st.button("TAMBAH", use_container_width=True) and baru.strip():
                for s in [x.strip().upper() for x in baru.split(",") if x.strip()]:
                    if s not in watchlist:
                        watchlist.append(s)
                simpan_json(BERKAS_WATCHLIST, watchlist)
                st.rerun()

        buang = st.multiselect("Hapus simbol", watchlist, label_visibility="collapsed",
                               placeholder="Pilih simbol yang mau dihapus")
        if buang and st.button("HAPUS TERPILIH"):
            st.session_state.watchlist = [s for s in watchlist if s not in buang]
            simpan_json(BERKAS_WATCHLIST, st.session_state.watchlist)
            st.rerun()

        st.markdown(
            '<div class="catatan">'
            'Saham Indonesia memakai akhiran <b>.JK</b> (BBCA.JK, TLKM.JK). '
            'Kripto memakai pasangan mata uang (BTC-USD, ETH-USD). '
            'Indeks diawali tanda sisipan (^JKSE untuk IHSG).'
            '</div>',
            unsafe_allow_html=True,
        )

    if not watchlist:
        st.info("Watchlist masih kosong. Tambahkan simbol lewat kotak di atas.")
        return

    df = ambil_kutipan(tuple(watchlist))
    if df.empty:
        st.warning("Tidak ada data yang berhasil diambil. Periksa koneksi internet Anda.")
        return

    tampil = pd.DataFrame({
        "Simbol": df["Simbol"],
        "Harga": df["Harga"].map(format_angka),
        "Perubahan": df["Perubahan"].map(lambda x: f"{x:+,.2f}"),
        "Persen": df["Persen"].map(lambda x: f"{x:+.2f}%"),
        "Volume": df["Volume"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—"),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True)

    naik = int((df["Persen"] > 0).sum())
    turun = int((df["Persen"] < 0).sum())
    st.markdown(
        f'<div class="catatan">'
        f'<span class="naik">▲ {naik} naik</span> &nbsp;·&nbsp; '
        f'<span class="turun">▼ {turun} turun</span> &nbsp;·&nbsp; '
        f'{len(df)} simbol dipantau &nbsp;·&nbsp; data disegarkan tiap 60 detik'
        f'</div>',
        unsafe_allow_html=True,
    )


def bagian_forex():
    kelompok = st.radio("Kelompok", ["Pasangan Utama", "Terhadap Rupiah", "Silang"],
                        horizontal=True, label_visibility="collapsed", key="kel_forex")
    peta = {"Pasangan Utama": FOREX_UTAMA, "Terhadap Rupiah": FOREX_RUPIAH,
            "Silang": FOREX_SILANG}[kelompok]
    petak_pasar(peta, per_baris=4)

    st.markdown(
        '<div class="catatan">'
        'Membaca kuotasi: <b>EUR / USD 1,0850</b> berarti satu euro dihargai 1,0850 dolar. '
        'Mata uang di depan disebut dasar, yang di belakang disebut kutipan. Naiknya angka '
        'berarti mata uang dasar menguat.<br><br>'
        'Harga di sini adalah kurs pasar antarbank, bukan kurs jual-beli bank atau '
        'money changer — yang selalu lebih lebar. Untuk keperluan sehari-hari, anggap ini '
        'titik tengah, bukan harga yang akan Anda dapatkan di loket.'
        '</div>',
        unsafe_allow_html=True,
    )


def bagian_kripto():
    st.subheader("Denyut Kripto")

    dunia = ambil_kripto_global()
    fng = ambil_takut_serakah()

    if not dunia and not fng:
        st.info("Data pasar kripto tidak bisa diambil sekarang. "
                "CoinGecko membatasi jumlah permintaan gratis — coba lagi sebentar lagi.")
    else:
        k = st.columns(5)
        with k[0]:
            kartu("KAPITALISASI PASAR", format_ringkas(dunia.get("kapitalisasi")),
                  f'{dunia["perubahan"]:+.2f}% (24 jam)' if dunia.get("perubahan") is not None else "",
                  warna(dunia.get("perubahan")))
        with k[1]:
            kartu("VOLUME 24 JAM", format_ringkas(dunia.get("volume")))
        with k[2]:
            d = dunia.get("dominasi_btc")
            kartu("DOMINASI BITCOIN", f"{d:.1f}%" if d is not None else "—",
                  f'Ethereum {dunia["dominasi_eth"]:.1f}%' if dunia.get("dominasi_eth") else "")
        with k[3]:
            n = dunia.get("jumlah_koin")
            kartu("KOIN AKTIF", f"{n:,}" if n else "—")
        with k[4]:
            if fng:
                nilai = fng["nilai"]
                sebutan = SEBUTAN_FNG.get(fng["sebutan"], fng["sebutan"])
                # Skala takut-serakah: 0 sangat takut (merah) → 100 sangat serakah (hijau)
                kelas = "turun" if nilai < 45 else ("naik" if nilai > 55 else "diam")
                kartu("TAKUT & SERAKAH", f"{nilai}/100", sebutan, kelas)
            else:
                kartu("TAKUT & SERAKAH", "—", "tidak tersedia")

    df = ambil_kripto_teratas(JUMLAH_KRIPTO)
    if df.empty:
        return

    tampil = pd.DataFrame({
        "#": range(1, len(df) + 1),
        "Koin": df["Koin"],
        "Nama": df["Nama"],
        "Harga": df["Harga"].map(format_harga_koin),
        "24 jam": df["24 jam %"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"),
        "7 hari": df["7 hari %"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"),
        "Kapitalisasi": df["Kapitalisasi"].map(format_ringkas),
        "Volume 24 jam": df["Volume 24 jam"].map(format_ringkas),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True)

    sah = df["24 jam %"].dropna()
    if len(sah):
        naik = int((sah > 0).sum())
        turun = int((sah < 0).sum())
        st.markdown(
            f'<div class="catatan">'
            f'<span class="naik">▲ {naik} menguat</span> &nbsp;·&nbsp; '
            f'<span class="turun">▼ {turun} melemah</span> dalam 24 jam terakhir '
            f'&nbsp;·&nbsp; sumber CoinGecko &amp; alternative.me, keduanya gratis tanpa API key'
            f'</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 2 — GRAFIK
# ──────────────────────────────────────────────────────────────────────

def halaman_grafik():
    st.subheader("Grafik & Analisa")

    pilihan = list(dict.fromkeys(
        (st.session_state.watchlist or list(WATCHLIST_AWAL)) + list(FOREX_SEMUA)))
    a, b, c = st.columns([2, 1, 1])
    with a:
        simbol = st.selectbox("Simbol", pilihan,
                              format_func=lambda x: FOREX_SEMUA.get(x, x))
    with b:
        periode = st.selectbox("Periode", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    with c:
        interval = st.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)

    t_grafik, t_baca = st.tabs(["Grafik & Indikator", "Pembacaan Teknikal"])
    with t_grafik:
        bagian_grafik(simbol, periode, interval)
    with t_baca:
        bagian_pembacaan(simbol, periode, interval)


def bagian_pembacaan(simbol: str, periode: str, interval: str):
    df = ambil_riwayat(simbol, periode, interval)
    if df.empty or len(df) < 30:
        st.warning("Butuh setidaknya 30 batang data untuk dibaca. "
                   "Coba periode yang lebih panjang.")
        return

    b = baca_teknikal(df)
    if not b:
        st.warning("Data belum cukup untuk dibaca.")
        return

    tafsir = tafsir_teknikal(b)

    # Grafik beranotasi: harga, garis tren, level penting, titik balik
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=simbol, increasing_line_color=pal()["naik"], decreasing_line_color=pal()["turun"],
    ))

    garis = b["tren"].get("garis")
    if garis is not None:
        fig.add_trace(go.Scatter(x=garis.index, y=garis, name="Garis tren",
                                 line=dict(color=pal()["aksen"], width=1.6, dash="dash")))

    for n, warna_ma in ((50, pal()["biru"]), (200, pal()["ungu"])):
        if n in b["sma_seri"]:
            fig.add_trace(go.Scatter(x=df.index, y=b["sma_seri"][n], name=f"MA{n}",
                                     line=dict(color=warna_ma, width=1)))

    for lv in b["resistensi"][:3]:
        fig.add_hline(y=lv["harga"], line=dict(color=pal()["turun"], width=1, dash="dot"),
                      annotation_text=f'penahan {format_angka(lv["harga"])} '
                                      f'({lv["sentuhan"]}x)',
                      annotation_position="right",
                      annotation_font=dict(size=9, color=pal()["turun"]))
    for lv in b["sokongan"][:3]:
        fig.add_hline(y=lv["harga"], line=dict(color=pal()["naik"], width=1, dash="dot"),
                      annotation_text=f'sokongan {format_angka(lv["harga"])} '
                                      f'({lv["sentuhan"]}x)',
                      annotation_position="right",
                      annotation_font=dict(size=9, color=pal()["naik"]))

    if b["puncak"]:
        fig.add_trace(go.Scatter(
            x=[t for t, _ in b["puncak"]], y=[h for _, h in b["puncak"]],
            mode="markers", name="Puncak",
            marker=dict(symbol="triangle-down", size=7, color=pal()["turun"])))
    if b["lembah"]:
        fig.add_trace(go.Scatter(
            x=[t for t, _ in b["lembah"]], y=[h for _, h in b["lembah"]],
            mode="markers", name="Lembah",
            marker=dict(symbol="triangle-up", size=7, color=pal()["naik"])))

    fig.update_layout(
        height=460, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=90, t=36, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Yang terbaca dari grafik ini**")
    for judul, isi, nada in tafsir:
        c = warna_kelas(nada)
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid {c};">'
            f'<div style="color:{c};font-weight:600;font-size:0.86rem;'
            f'letter-spacing:0.04em;">{judul}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;line-height:1.7;'
            f'margin-top:0.3rem;">{isi}</div></div>',
            unsafe_allow_html=True,
        )

    with st.expander("Angka mentahnya"):
        st.dataframe(pd.DataFrame({
            "Ukuran": ["Harga", "ATR (14)", "ATR % harga", "ADX (14)", "DI+", "DI-",
                       "RSI (14)", "MACD", "Sinyal MACD", "Lebar Bollinger %",
                       "Tertinggi 52 minggu", "Terendah 52 minggu"],
            "Nilai": [format_angka(b["harga"]), format_angka(b["atr"]),
                      f'{b["atr_persen"]:.2f}%', f'{b["adx"]:.1f}',
                      f'{b["di_naik"]:.1f}', f'{b["di_turun"]:.1f}',
                      f'{b["rsi"]:.1f}', format_angka(b["macd"], 4),
                      format_angka(b["macd_sinyal"], 4),
                      f'{b["lebar_bollinger"]:.2f}%',
                      format_angka(b["tertinggi_52"]), format_angka(b["terendah_52"])],
        }), use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="catatan">'
        '<b>Cara memperlakukan halaman ini.</b> Semua di atas adalah <i>uraian</i> tentang '
        'apa yang sudah terjadi pada harga, bukan ramalan dan bukan anjuran. Tidak ada '
        'satu pun angka di sini yang tahu apa yang akan terjadi besok.<br><br>'
        'Analisa teknikal punya keterbatasan yang jujur perlu disebut: pola yang sama bisa '
        'ditafsirkan berbeda oleh dua orang, indikator selalu tertinggal dari harga karena '
        'dihitung dari masa lalu, dan makin banyak indikator dipakai makin mudah menemukan '
        'yang kebetulan mendukung keinginan kita. Gunakan sebagai satu bahan pertimbangan, '
        'bukan satu-satunya.<br><br>'
        'Level sokongan dan penahan diambil dari puncak dan lembah yang harganya berdekatan, '
        'dengan toleransi 0,6 kali ATR. Angka dalam kurung menunjukkan berapa kali harga '
        'menyentuh level itu — makin sering, makin banyak pelaku pasar yang memperhatikannya.'
        '</div>',
        unsafe_allow_html=True,
    )


def bagian_grafik(simbol: str, periode: str, interval: str):
    indikator = st.multiselect(
        "Indikator",
        ["SMA 20", "SMA 50", "SMA 200", "EMA 20", "Bollinger", "RSI", "MACD", "Volume"],
        default=["SMA 20", "SMA 50", "RSI", "Volume"],
    )

    df = ambil_riwayat(simbol, periode, interval)
    if df.empty:
        st.warning("Data tidak tersedia untuk kombinasi ini. Coba periode atau interval lain.")
        return

    tutup = df["Close"]
    terakhir = float(tutup.iloc[-1])
    awal = float(tutup.iloc[0])
    perubahan = (terakhir - awal) / awal * 100 if awal else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kartu("Harga terakhir", format_angka(terakhir))
    with k2:
        kartu("Perubahan periode", f"{perubahan:+.2f}%", "", warna(perubahan))
    with k3:
        kartu("Tertinggi periode", format_angka(float(df["High"].max())))
    with k4:
        kartu("Terendah periode", format_angka(float(df["Low"].min())))

    panel = 1
    tinggi = [0.62]
    if "Volume" in indikator:
        panel += 1
        tinggi.append(0.13)
    if "RSI" in indikator:
        panel += 1
        tinggi.append(0.16)
    if "MACD" in indikator:
        panel += 1
        tinggi.append(0.16)
    total = sum(tinggi)
    tinggi = [t / total for t in tinggi]

    fig = make_subplots(rows=panel, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=tinggi)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=simbol, increasing_line_color=pal()["naik"], decreasing_line_color=pal()["turun"],
    ), row=1, col=1)

    garis = {
        "SMA 20": (tutup.rolling(20).mean(), pal()["aksen"]),
        "SMA 50": (tutup.rolling(50).mean(), pal()["biru"]),
        "SMA 200": (tutup.rolling(200).mean(), pal()["ungu"]),
        "EMA 20": (tutup.ewm(span=20, adjust=False).mean(), pal()["kuning"]),
    }
    for nama, (seri, warna_garis) in garis.items():
        if nama in indikator:
            fig.add_trace(go.Scatter(x=df.index, y=seri, name=nama,
                                     line=dict(color=warna_garis, width=1.2)), row=1, col=1)

    if "Bollinger" in indikator:
        tengah = tutup.rolling(20).mean()
        deviasi = tutup.rolling(20).std()
        for seri, nama in [(tengah + 2 * deviasi, "Bollinger atas"),
                           (tengah - 2 * deviasi, "Bollinger bawah")]:
            fig.add_trace(go.Scatter(x=df.index, y=seri, name=nama,
                                     line=dict(color=pal()["lembut"], width=1, dash="dot")), row=1, col=1)

    baris = 1
    if "Volume" in indikator:
        baris += 1
        warna_bar = [pal()["naik"] if c >= o else pal()["turun"]
                     for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                             marker_color=warna_bar, opacity=0.55), row=baris, col=1)

    if "RSI" in indikator:
        baris += 1
        fig.add_trace(go.Scatter(x=df.index, y=hitung_rsi(tutup), name="RSI 14",
                                 line=dict(color=pal()["aksen"], width=1.2)), row=baris, col=1)
        for level, warna_level in [(70, pal()["turun"]), (30, pal()["naik"])]:
            fig.add_hline(y=level, line=dict(color=warna_level, width=0.8, dash="dot"),
                          row=baris, col=1)

    if "MACD" in indikator:
        baris += 1
        macd, sinyal, batang = hitung_macd(tutup)
        fig.add_trace(go.Bar(x=df.index, y=batang, name="Histogram",
                             marker_color=[pal()["naik"] if v >= 0 else pal()["turun"] for v in batang],
                             opacity=0.6), row=baris, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=macd, name="MACD",
                                 line=dict(color=pal()["biru"], width=1.2)), row=baris, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sinyal, name="Sinyal",
                                 line=dict(color=pal()["aksen"], width=1.2)), row=baris, col=1)

    fig.update_layout(
        height=200 + 130 * panel, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.06, x=0, font=dict(size=10)),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="catatan">'
        'Indikator teknikal menggambarkan apa yang <i>sudah</i> terjadi pada harga. '
        'Ia tidak meramal apa pun. Perlakukan sebagai ringkasan visual, bukan sinyal beli-jual.'
        '</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  PENAPISAN SYARIAH
# ──────────────────────────────────────────────────────────────────────
#
#  PENTING — batas kejujuran alat ini.
#
#  Penapisan syariah yang sah punya dua tahap: penapisan kegiatan usaha, dan
#  penapisan rasio keuangan. Tahap kedua menuntut angka yang TIDAK tersedia di
#  data terbuka mana pun secara cuma-cuma — khususnya pendapatan non-halal dan
#  piutang usaha per emiten.
#
#  Karena itu alat ini hanya menghitung apa yang bisa dihitung, dan menyebut
#  dengan terang apa yang tidak. Hasilnya adalah PENYARING AWAL untuk
#  mempersempit daftar bacaan, bukan penetapan status halal. Rujukan yang sah
#  bagi pemodal Indonesia tetap Daftar Efek Syariah (DES) yang diterbitkan OJK
#  dua kali setahun, atau indeks ISSI dan JII.

INDUSTRI_DIKECUALIKAN = [
    # Keuangan berbasis bunga
    "bank", "credit services", "capital markets", "insurance", "mortgage",
    "financial conglomerates", "asset management", "financial data",
    # Barang dan jasa yang dilarang
    "tobacco", "brewers", "distilleries", "wineries", "beverages—brewers",
    "gambling", "casino", "resorts & casinos", "adult",
    # Persenjataan
    "aerospace & defense", "defense",
]

AMBANG_SYARIAH = {
    "AAOIFI": {
        "utang_kap": 30.0,
        "kas_kap": 30.0,
        "keterangan": "Standar AAOIFI — dipakai luas di indeks syariah global "
                      "(Dow Jones Islamic, S&P Shariah). Ambang 30% dihitung "
                      "terhadap kapitalisasi pasar.",
    },
    "DSN-MUI / OJK": {
        "utang_kap": 45.0,
        "kas_kap": 100.0,  # tidak diatur dengan ambang kas terhadap kapitalisasi
        "keterangan": "Mengikuti semangat POJK 35/2017 dan fatwa DSN-MUI: utang "
                      "berbasis bunga dibanding total aset maksimal 45%. Di sini "
                      "pembandingnya kapitalisasi pasar, karena total aset tidak "
                      "tersedia di data terbuka — jadi angkanya mendekati, bukan sama.",
    },
}


def periksa_syariah(baris, ambang: dict) -> dict:
    """Nilai satu saham terhadap ambang yang dipilih. Kembalikan rincian, bukan vonis."""
    industri = str(baris.get("Industri", "") or "").lower()
    sektor = str(baris.get("Sektor", "") or "").lower()
    gabung = f"{industri} {sektor}"

    terlarang = [k for k in INDUSTRI_DIKECUALIKAN if k in gabung]
    utang = baris.get("Utang/Kap %", float("nan"))
    kas = baris.get("Kas/Kap %", float("nan"))

    lolos_usaha = not terlarang
    lolos_utang = (not math.isnan(utang)) and utang <= ambang["utang_kap"]
    lolos_kas = (not math.isnan(kas)) and kas <= ambang["kas_kap"]
    data_kurang = math.isnan(utang) or math.isnan(kas)

    return {
        "lolos": lolos_usaha and lolos_utang and lolos_kas and not data_kurang,
        "usaha": lolos_usaha,
        "utang": lolos_utang,
        "kas": lolos_kas,
        "data_kurang": data_kurang,
        "alasan": terlarang,
    }


# ──────────────────────────────────────────────────────────────────────
#  SKOR GABUNGAN
# ──────────────────────────────────────────────────────────────────────

def hitung_skor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Skor 0–100 dari peringkat relatif di dalam kelompoknya sendiri.
    Sengaja memakai peringkat, bukan nilai mutlak: PER 12 itu murah di Amerika
    tetapi biasa saja di Indonesia, jadi membandingkan antar pasar tidak adil.
    """
    d = df.copy()

    def peringkat(kolom, kecil_lebih_baik=False, hanya_positif=False):
        s = pd.to_numeric(d.get(kolom), errors="coerce")
        if hanya_positif:
            s = s.where(s > 0)
        if s.notna().sum() < 3:
            return pd.Series(float("nan"), index=d.index)
        # Arahnya mudah tertukar. Untuk ukuran yang "makin kecil makin baik"
        # (PER, PBV, DER), peringkat harus dibalik supaya nilai terkecil justru
        # mendapat skor tertinggi.
        return s.rank(pct=True, ascending=not kecil_lebih_baik) * 100

    # Nilai — makin murah makin tinggi skornya
    nilai = pd.concat([peringkat("PER", True, True), peringkat("PBV", True, True)],
                      axis=1).mean(axis=1)
    # Kualitas — profitabilitas
    kualitas = pd.concat([peringkat("ROE %"), peringkat("Margin %")], axis=1).mean(axis=1)
    # Neraca — utang rendah lebih baik
    neraca = peringkat("DER", True)
    # Imbal — dividen
    imbal = peringkat("Dividen %")

    d["Skor Nilai"] = nilai
    d["Skor Kualitas"] = kualitas
    d["Skor Neraca"] = neraca
    d["Skor Imbal"] = imbal
    d["Skor"] = pd.concat([nilai, kualitas, neraca, imbal], axis=1).mean(axis=1, skipna=True)
    return d


PRESET = {
    "Saham Nilai": {
        "keterangan": "Harga murah dibanding laba dan nilai bukunya, tetapi labanya "
                      "masih sehat. Cara klasik Benjamin Graham.",
        "nilai": {"per": 15.0, "pbv": 2.0, "roe": 10.0, "div": 0.0, "der": 0.0, "kap": 0.0},
    },
    "Pemburu Dividen": {
        "keterangan": "Dividen besar dengan neraca yang tidak berat utang — supaya "
                      "dividennya punya peluang bertahan.",
        "nilai": {"per": 0.0, "pbv": 0.0, "roe": 8.0, "div": 4.0, "der": 100.0, "kap": 0.0},
    },
    "Kualitas Tinggi": {
        "keterangan": "Perusahaan yang produktif memakai modal dan tidak bergantung "
                      "pada utang. Harga tidak disaring — kualitas jarang murah.",
        "nilai": {"per": 0.0, "pbv": 0.0, "roe": 18.0, "div": 0.0, "der": 60.0, "kap": 0.0},
    },
    "Tanpa Saringan": {
        "keterangan": "Kembalikan semua ke nol untuk mulai dari awal.",
        "nilai": {"per": 0.0, "pbv": 0.0, "roe": 0.0, "div": 0.0, "der": 0.0, "kap": 0.0},
    },
}


# ──────────────────────────────────────────────────────────────────────
#  MESIN PEMBACAAN TEKNIKAL
# ──────────────────────────────────────────────────────────────────────

def baca_teknikal(df: pd.DataFrame) -> dict:
    """
    Kumpulkan semua yang bisa diukur dari grafik. Fungsi ini hanya MENGUKUR —
    penafsirannya dikerjakan terpisah supaya angkanya bisa diperiksa sendiri.
    """
    tutup = df["Close"].dropna()
    if len(tutup) < 30:
        return {}

    kini = float(tutup.iloc[-1])
    atr = hitung_atr(df)
    atr_kini = float(atr.iloc[-1]) if len(atr) else float("nan")
    adx, di_naik, di_turun = hitung_adx(df)
    rsi = hitung_rsi(tutup)
    macd, sinyal_macd, batang = hitung_macd(tutup)

    sma = {n: tutup.rolling(n).mean() for n in (20, 50, 200) if len(tutup) >= n}
    sma_kini = {n: float(s.iloc[-1]) for n, s in sma.items() if not math.isnan(s.iloc[-1])}

    puncak, lembah = cari_titik_balik(df)
    toleransi = atr_kini * 0.6 if not math.isnan(atr_kini) else kini * 0.015
    resistensi = [x for x in kumpulkan_level(puncak, toleransi) if x["harga"] > kini][:4]
    sokongan = [x for x in kumpulkan_level(lembah, toleransi) if x["harga"] < kini][:4]

    tren = kemiringan_tren(tutup)

    # Perpotongan rata-rata dalam 30 hari terakhir
    silang = None
    if 50 in sma and 200 in sma:
        c50, c200 = sma[50], sma[200]
        atas = (c50 > c200)
        ganti = atas.astype(int).diff().fillna(0)
        baru = ganti.tail(30)
        if (baru == 1).any():
            silang = ("emas", baru[baru == 1].index[-1])
        elif (baru == -1).any():
            silang = ("maut", baru[baru == -1].index[-1])

    # Lebar pita Bollinger — penyempitan sering mendahului pergerakan besar
    tengah = tutup.rolling(20).mean()
    deviasi = tutup.rolling(20).std()
    lebar = ((tengah + 2 * deviasi) - (tengah - 2 * deviasi)) / tengah * 100
    lebar_kini = float(lebar.iloc[-1]) if len(lebar.dropna()) else float("nan")
    lebar_persentil = (float((lebar.dropna().tail(252) < lebar_kini).mean() * 100)
                       if len(lebar.dropna()) > 30 else float("nan"))

    volume_rata = float(df["Volume"].tail(20).mean()) if "Volume" in df else float("nan")
    volume_kini = float(df["Volume"].iloc[-1]) if "Volume" in df else float("nan")

    setahun = tutup.tail(252)
    return {
        "harga": kini,
        "atr": atr_kini,
        "atr_persen": atr_kini / kini * 100 if kini else float("nan"),
        "adx": float(adx.iloc[-1]),
        "di_naik": float(di_naik.iloc[-1]),
        "di_turun": float(di_turun.iloc[-1]),
        "rsi": float(rsi.iloc[-1]),
        "rsi_sebelum": float(rsi.iloc[-6]) if len(rsi) > 6 else float("nan"),
        "macd": float(macd.iloc[-1]),
        "macd_sinyal": float(sinyal_macd.iloc[-1]),
        "macd_batang": float(batang.iloc[-1]),
        "macd_batang_sebelum": float(batang.iloc[-2]) if len(batang) > 2 else float("nan"),
        "sma": sma_kini,
        "sma_seri": sma,
        "silang": silang,
        "resistensi": resistensi,
        "sokongan": sokongan,
        "tren": tren,
        "lebar_bollinger": lebar_kini,
        "lebar_persentil": lebar_persentil,
        "volume": volume_kini,
        "volume_rata": volume_rata,
        "tertinggi_52": float(setahun.max()),
        "terendah_52": float(setahun.min()),
        "puncak": puncak,
        "lembah": lembah,
    }


def tafsir_teknikal(b: dict) -> list:
    """
    Ubah angka jadi kalimat. Tiap butir: (judul, isi, nada).
    Nada hanya mewarnai tampilan — bukan anjuran membeli atau menjual.
    """
    if not b:
        return []
    hasil = []
    kini = b["harga"]

    # ── Arah dan kekuatan tren ──
    di_atas = [n for n, v in b["sma"].items() if kini > v]
    urut_rapi = (len(b["sma"]) >= 3
                 and b["sma"].get(20, 0) > b["sma"].get(50, 0) > b["sma"].get(200, 0))
    urut_terbalik = (len(b["sma"]) >= 3
                     and b["sma"].get(20, 9e9) < b["sma"].get(50, 9e9) < b["sma"].get(200, 9e9))
    adx = b["adx"]

    if adx < 20:
        kuat = "Kekuatan tren lemah — harga cenderung bergerak menyamping."
        nada_kuat = "diam"
    elif adx < 25:
        kuat = "Kekuatan tren mulai terbentuk, tetapi belum meyakinkan."
        nada_kuat = "diam"
    elif adx < 40:
        kuat = "Ada tren yang jelas."
        nada_kuat = "naik"
    else:
        kuat = "Tren sangat kuat — perlu diingat, tren sekuat ini juga sering mendekati batasnya."
        nada_kuat = "naik"

    if urut_rapi and adx >= 25:
        arah, nada = "Tren naik", "naik"
    elif urut_terbalik and adx >= 25:
        arah, nada = "Tren turun", "turun"
    elif len(di_atas) >= 2:
        arah, nada = "Cenderung naik", "naik"
    elif len(di_atas) == 0 and b["sma"]:
        arah, nada = "Cenderung turun", "turun"
    else:
        arah, nada = "Bergerak menyamping", "diam"

    posisi = (f'Harga berada di atas {len(di_atas)} dari {len(b["sma"])} rata-rata '
              f'({", ".join("MA" + str(n) for n in sorted(di_atas))}). '
              if di_atas else
              f'Harga berada di bawah seluruh rata-rata bergerak. ')
    tren_tahun = b["tren"]["persen_tahun"]
    keandalan = b["tren"]["keandalan"]
    lurus = ""
    if not math.isnan(tren_tahun):
        lurus = (f'Garis tren terbaik menunjukkan laju sekitar {tren_tahun:+.0f}% per tahun, '
                 f'dengan keteraturan {keandalan:.0f}% — makin tinggi angka itu, makin rapi '
                 f'harga mengikuti garisnya.')
    hasil.append((arah, posisi + kuat + " " + lurus + f" (ADX {adx:.0f})", nada))

    # ── Perpotongan rata-rata ──
    if b["silang"]:
        jenis, tanggal = b["silang"]
        if jenis == "emas":
            hasil.append(("Perpotongan emas",
                          f'MA50 memotong ke atas MA200 pada {tanggal:%d %b %Y}. Pola ini '
                          f'sering disebut awal tren naik. Perlu jujur dikatakan: karena '
                          f'dihitung dari rata-rata panjang, sinyalnya selalu datang '
                          f'terlambat, dan cukup sering keliru.', "naik"))
        else:
            hasil.append(("Perpotongan maut",
                          f'MA50 memotong ke bawah MA200 pada {tanggal:%d %b %Y}. Sama seperti '
                          f'kembarannya, pola ini terlambat dan sering meleset — terutama '
                          f'pada saham yang bergerak liar.', "turun"))

    # ── Momentum ──
    rsi = b["rsi"]
    beda_rsi = rsi - b["rsi_sebelum"] if not math.isnan(b["rsi_sebelum"]) else 0
    if rsi >= 70:
        isi_rsi = (f'RSI {rsi:.0f} — masuk wilayah yang biasa disebut jenuh beli. '
                   f'Perlu dicatat, pada tren naik yang kuat RSI bisa bertahan tinggi '
                   f'berminggu-minggu tanpa harga turun.')
        nada_rsi = "turun"
    elif rsi <= 30:
        isi_rsi = (f'RSI {rsi:.0f} — wilayah jenuh jual. Ini menggambarkan tekanan jual '
                   f'yang deras, bukan jaminan harga akan berbalik.')
        nada_rsi = "naik"
    else:
        isi_rsi = f'RSI {rsi:.0f} — di wilayah tengah, tidak menunjukkan tekanan berlebihan.'
        nada_rsi = "diam"
    isi_rsi += f' Lima hari terakhir bergerak {beda_rsi:+.0f} poin.'
    hasil.append(("Momentum", isi_rsi, nada_rsi))

    # ── MACD ──
    batang, sebelum = b["macd_batang"], b["macd_batang_sebelum"]
    di_atas_sinyal = b["macd"] > b["macd_sinyal"]
    menguat = batang > sebelum if not math.isnan(sebelum) else None
    isi = (f'MACD berada {"di atas" if di_atas_sinyal else "di bawah"} garis sinyalnya, '
           f'dan selisihnya sedang {"melebar" if menguat else "menyempit"}. ')
    if di_atas_sinyal and menguat:
        isi += "Dorongan naik sedang bertambah."; nada_m = "naik"
    elif di_atas_sinyal and not menguat:
        isi += "Dorongan naik masih ada tetapi mulai berkurang."; nada_m = "diam"
    elif not di_atas_sinyal and not menguat:
        isi += "Tekanan turun sedang bertambah."; nada_m = "turun"
    else:
        isi += "Tekanan turun masih ada tetapi mulai mereda."; nada_m = "diam"
    hasil.append(("Arah dorongan (MACD)", isi, nada_m))

    # ── Gejolak ──
    atr_p = b["atr_persen"]
    pers = b["lebar_persentil"]
    isi_v = (f'Rentang gerak harian rata-rata {atr_p:.2f}% dari harga '
             f'(ATR {format_angka(b["atr"])}). ')
    if not math.isnan(pers):
        if pers < 20:
            isi_v += (f'Pita Bollinger sedang menyempit — lebih rapat daripada {100 - pers:.0f}% '
                      f'hari dalam setahun terakhir. Penyempitan sering mendahului pergerakan '
                      f'besar, tetapi tidak memberi tahu ke arah mana.')
            nada_v = "diam"
        elif pers > 80:
            isi_v += (f'Pita Bollinger sedang melebar — lebih lebar daripada {pers:.0f}% hari '
                      f'dalam setahun terakhir. Pasar sedang bergejolak.')
            nada_v = "turun"
        else:
            isi_v += "Gejolak berada di kisaran normalnya."
            nada_v = "diam"
    else:
        nada_v = "diam"
    hasil.append(("Gejolak", isi_v, nada_v))

    # ── Volume ──
    if not math.isnan(b["volume_rata"]) and b["volume_rata"] > 0:
        rasio = b["volume"] / b["volume_rata"]
        if rasio > 1.5:
            isi_vol = (f'Volume hari terakhir {rasio:.1f} kali rata-rata 20 hari. '
                       f'Pergerakan yang disertai volume besar umumnya dianggap lebih '
                       f'meyakinkan daripada yang sepi.')
            nada_vol = "naik"
        elif rasio < 0.6:
            isi_vol = (f'Volume hanya {rasio:.1f} kali rata-rata 20 hari. Pergerakan harga '
                       f'dalam kondisi sepi lebih mudah berbalik.')
            nada_vol = "turun"
        else:
            isi_vol = f'Volume {rasio:.1f} kali rata-rata 20 hari — wajar.'
            nada_vol = "diam"
        hasil.append(("Volume", isi_vol, nada_vol))

    # ── Jarak ke level penting ──
    bagian = []
    if b["sokongan"]:
        s = b["sokongan"][0]
        bagian.append(f'sokongan terdekat di {format_angka(s["harga"])} '
                      f'({(s["harga"] / kini - 1) * 100:+.1f}%, {s["sentuhan"]} kali disentuh)')
    if b["resistensi"]:
        r = b["resistensi"][0]
        bagian.append(f'penahan terdekat di {format_angka(r["harga"])} '
                      f'({(r["harga"] / kini - 1) * 100:+.1f}%, {r["sentuhan"]} kali disentuh)')
    if bagian:
        hasil.append(("Level penting",
                      "Dari puncak dan lembah sebelumnya: " + ", ".join(bagian) +
                      ". Level ini bukan dinding — ia hanya harga yang dulu sempat "
                      "menghentikan pergerakan, dan bisa saja ditembus.", "diam"))

    # ── Posisi dalam rentang setahun ──
    t, r = b["tertinggi_52"], b["terendah_52"]
    if t > r:
        letak = (kini - r) / (t - r) * 100
        hasil.append(("Posisi setahun",
                      f'Harga berada {letak:.0f}% dari dasar rentang 52 minggu '
                      f'({format_angka(r)} sampai {format_angka(t)}), '
                      f'{(kini / t - 1) * 100:+.1f}% dari puncaknya.',
                      "naik" if letak > 60 else ("turun" if letak < 40 else "diam")))

    return hasil


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — SCREENER
# ──────────────────────────────────────────────────────────────────────

def halaman_screener():
    st.subheader("Screener")
    st.markdown(
        '<div class="catatan">Menyaring bukan berarti menemukan saham bagus — hanya '
        'mempersempit daftar yang layak dibaca lebih jauh. Angka murah sering murah karena '
        'ada alasannya.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    t_saham, t_kripto = st.tabs(["Saham", "Kripto"])
    with t_saham:
        screener_saham()
    with t_kripto:
        screener_kripto()


def screener_saham():
    a, b = st.columns([2, 1])
    with a:
        pilihan = st.selectbox("Pasar", list(SEMESTA))
    with b:
        st.write("")
        muat = st.button("SARING SEKARANG", use_container_width=True, key="saring_saham")

    pasar = SEMESTA[pilihan]
    daftar, mata_uang, satuan = pasar["daftar"], pasar["mata_uang"], pasar["satuan"]
    pengali = PENGALI_KAP.get(satuan, 1e9)

    st.markdown(
        f'<div class="catatan">{len(daftar)} saham dalam daftar, harga dan kapitalisasi '
        f'dalam <b>{mata_uang}</b>. Penyaringan pertama memakan waktu 20–40 detik karena '
        f'setiap saham diambil satu per satu; sesudah itu hasilnya disimpan satu jam.</div>',
        unsafe_allow_html=True,
    )

    kunci = f"fund_{pilihan}"
    if muat:
        with st.spinner(f"Mengambil data {len(daftar)} saham…"):
            st.session_state[kunci] = ambil_fundamental_banyak(tuple(daftar))

    df = st.session_state.get(kunci)
    if df is None:
        st.info("Tekan **SARING SEKARANG** untuk mengambil data.")
        return
    if df.empty:
        st.warning("Tidak ada data yang berhasil diambil. Periksa koneksi internet Anda.")
        return

    st.divider()
    st.markdown(f"**Penyaring** — {len(df)} saham berhasil diambil")

    st.markdown('<div class="catatan">Saringan siap pakai — sekali klik:</div>',
                unsafe_allow_html=True)
    kol = st.columns(len(PRESET))
    for k, (nama_preset, isi) in zip(kol, PRESET.items()):
        with k:
            if st.button(nama_preset.upper(), use_container_width=True,
                         key=f"preset_{nama_preset}", help=isi["keterangan"]):
                for kunci, nilai in isi["nilai"].items():
                    st.session_state[f"f_{kunci}"] = nilai
                st.rerun()

    with st.expander("Atur batas penyaringan", expanded=True):
        k1, k2, k3 = st.columns(3)
        with k1:
            per_maks = st.number_input("PER maksimum", value=0.0, step=1.0, key="f_per",
                                       help="0 berarti tidak disaring. PER 15 artinya "
                                            "harga 15 kali laba setahun.")
            pbv_maks = st.number_input("PBV maksimum", value=0.0, step=0.1, key="f_pbv",
                                       help="0 berarti tidak disaring. PBV di bawah 1 "
                                            "artinya harga di bawah nilai buku.")
        with k2:
            roe_min = st.number_input("ROE minimum (%)", value=0.0, step=1.0, key="f_roe",
                                      help="Seberapa produktif modal pemegang saham.")
            div_min = st.number_input("Dividen minimum (%)", value=0.0, step=0.5, key="f_div")
        with k3:
            der_maks = st.number_input("DER maksimum", value=0.0, step=10.0, key="f_der",
                                       help="Utang dibanding modal. 100 berarti utang "
                                            "sebesar modal sendiri.")
            kap_min = st.number_input(f"Kapitalisasi minimum ({satuan})",
                                      value=0.0, step=1.0, key="f_kap",
                                      help=f"Dalam mata uang asli pasar ini ({mata_uang}). "
                                           f"Nilainya tidak dikonversi ke rupiah.")

        sektor_ada = sorted(x for x in df["Sektor"].dropna().unique() if x != "—")
        sektor = st.multiselect("Sektor", sektor_ada, placeholder="Semua sektor")

        syariah = st.selectbox(
            "Penapisan syariah", ["Tidak dipakai"] + list(AMBANG_SYARIAH),
            help="Penyaring awal untuk mempersempit bacaan, bukan penetapan status "
                 "halal. Baca catatan di bawah tabel.")

    hasil = df.copy()
    saringan = []
    if per_maks > 0:
        hasil = hasil[(hasil["PER"] > 0) & (hasil["PER"] <= per_maks)]
        saringan.append(f"PER ≤ {per_maks:g}")
    if pbv_maks > 0:
        hasil = hasil[(hasil["PBV"] > 0) & (hasil["PBV"] <= pbv_maks)]
        saringan.append(f"PBV ≤ {pbv_maks:g}")
    if roe_min > 0:
        hasil = hasil[hasil["ROE %"] >= roe_min]
        saringan.append(f"ROE ≥ {roe_min:g}%")
    if div_min > 0:
        hasil = hasil[hasil["Dividen %"] >= div_min]
        saringan.append(f"Dividen ≥ {div_min:g}%")
    if der_maks > 0:
        hasil = hasil[(hasil["DER"] >= 0) & (hasil["DER"] <= der_maks)]
        saringan.append(f"DER ≤ {der_maks:g}")
    if kap_min > 0:
        hasil = hasil[hasil["Kapitalisasi"] >= kap_min * pengali]
        saringan.append(f"Kapitalisasi ≥ {kap_min:g} {satuan}")
    if sektor:
        hasil = hasil[hasil["Sektor"].isin(sektor)]
        saringan.append(f"{len(sektor)} sektor")

    rincian_syariah = None
    if syariah != "Tidak dipakai":
        ambang = AMBANG_SYARIAH[syariah]
        periksa = hasil.apply(lambda r: periksa_syariah(r, ambang), axis=1)
        rincian_syariah = pd.DataFrame(list(periksa), index=hasil.index)
        hasil = hasil[rincian_syariah["lolos"]]
        rincian_syariah = rincian_syariah.loc[hasil.index]
        saringan.append(f"penapisan {syariah}")

    st.markdown(
        f'<div class="catatan">Penyaring aktif: '
        f'{" · ".join(saringan) if saringan else "belum ada — semua saham ditampilkan"}'
        f' &nbsp;→&nbsp; <b style="color:var(--aksen);">{len(hasil)} saham lolos</b></div>',
        unsafe_allow_html=True,
    )

    if hasil.empty:
        st.warning("Tidak ada saham yang lolos. Longgarkan batasannya.")
        return

    hasil = hitung_skor(hasil)

    urut = st.selectbox("Urutkan berdasarkan",
                        ["Skor", "Kapitalisasi", "PER", "PBV", "ROE %", "Dividen %",
                         "Margin %", "DER", "Tumbuh Laba %"])
    menaik = urut in ("PER", "PBV", "DER")
    hasil = hasil.sort_values(urut, ascending=menaik, na_position="last")

    tampil = pd.DataFrame({
        "Skor": hasil["Skor"].map(lambda x: f"{x:.0f}" if pd.notna(x) else "—"),
        "Simbol": hasil["Simbol"],
        "Nama": hasil["Nama"],
        "Sektor": hasil["Sektor"],
        "Harga": hasil["Harga"].map(format_angka),
        "Kapitalisasi": hasil["Kapitalisasi"].map(format_ringkas),
        "PER": hasil["PER"].map(lambda x: format_angka(x, 1)),
        "PBV": hasil["PBV"].map(lambda x: format_angka(x, 2)),
        "ROE %": hasil["ROE %"].map(lambda x: format_angka(x, 1)),
        "Margin %": hasil["Margin %"].map(lambda x: format_angka(x, 1)),
        "DER": hasil["DER"].map(lambda x: format_angka(x, 1)),
        "Dividen %": hasil["Dividen %"].map(lambda x: format_angka(x, 2)),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True, height=460)

    st.markdown(
        '<div class="catatan"><b>Skor</b> adalah rata-rata peringkat saham ini terhadap '
        'sesamanya dalam empat hal: harga murah, produktivitas, kesehatan neraca, dan '
        'dividen. Karena berbasis peringkat, angkanya hanya berarti <i>di dalam pasar yang '
        'sama</i> — skor 80 di IDX tidak sebanding dengan 80 di Amerika. Skor tinggi berarti '
        '"pantas dibaca lebih jauh", bukan "pantas dibeli".</div>',
        unsafe_allow_html=True,
    )

    if rincian_syariah is not None:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
            f'<div class="label">CATATAN PENAPISAN SYARIAH</div>'
            f'<div style="color:var(--teks2);font-size:0.8rem;line-height:1.75;'
            f'margin-top:0.35rem;">'
            f'{AMBANG_SYARIAH[syariah]["keterangan"]}<br><br>'
            f'<b class="turun">Yang sudah dihitung:</b> penapisan kegiatan usaha '
            f'(mengeluarkan bank dan lembaga keuangan berbasis bunga, asuransi '
            f'konvensional, rokok, minuman keras, perjudian, dan persenjataan), serta '
            f'rasio utang berbunga dan kas terhadap kapitalisasi pasar.<br><br>'
            f'<b class="turun">Yang TIDAK bisa dihitung di sini:</b> pendapatan non-halal '
            f'terhadap total pendapatan, dan piutang usaha terhadap total aset. Kedua angka '
            f'ini tidak tersedia di sumber data terbuka mana pun secara cuma-cuma, padahal '
            f'keduanya bagian sah dari penapisan yang utuh.<br><br>'
            f'Karena itu hasil di atas adalah <b>penyaring awal</b> untuk mempersempit '
            f'daftar bacaan Anda — bukan penetapan status halal. Rujukan yang sah bagi '
            f'pemodal Indonesia tetap <b>Daftar Efek Syariah (DES)</b> yang diterbitkan OJK '
            f'dua kali setahun, atau indeks <b>ISSI</b> dan <b>JII</b>. Sebuah saham bisa '
            f'lolos di sini tetapi tidak ada di DES, dan sebaliknya.'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # ── Kirim ke watchlist ──
    st.markdown("**Tindak lanjut**")
    a, b = st.columns([3, 1])
    with a:
        terpilih = st.multiselect("Pilih saham", hasil["Simbol"].tolist(),
                                  placeholder="Pilih untuk dibandingkan atau dipantau",
                                  key="pilih_screener")
    with b:
        st.write("")
        if st.button("KE WATCHLIST", use_container_width=True, key="ke_watchlist"):
            if terpilih:
                baru_ditambah = [x for x in terpilih if x not in st.session_state.watchlist]
                st.session_state.watchlist.extend(baru_ditambah)
                simpan_json(BERKAS_WATCHLIST, st.session_state.watchlist)
                st.success(f"{len(baru_ditambah)} simbol ditambahkan ke watchlist."
                           if baru_ditambah else "Semua sudah ada di watchlist.")
            else:
                st.warning("Belum ada saham yang dipilih.")

    if len(terpilih) >= 2:
        banding = hasil[hasil["Simbol"].isin(terpilih)].set_index("Simbol")
        ukuran = [("Harga", format_angka), ("Kapitalisasi", format_ringkas),
                  ("PER", lambda x: format_angka(x, 1)), ("PBV", lambda x: format_angka(x, 2)),
                  ("ROE %", lambda x: format_angka(x, 1)),
                  ("Margin %", lambda x: format_angka(x, 1)),
                  ("DER", lambda x: format_angka(x, 1)),
                  ("Dividen %", lambda x: format_angka(x, 2)),
                  ("Tumbuh Laba %", lambda x: format_angka(x, 1)),
                  ("Skor", lambda x: format_angka(x, 0)),
                  ("Skor Nilai", lambda x: format_angka(x, 0)),
                  ("Skor Kualitas", lambda x: format_angka(x, 0)),
                  ("Skor Neraca", lambda x: format_angka(x, 0)),
                  ("Skor Imbal", lambda x: format_angka(x, 0))]
        tabel = pd.DataFrame(
            {s: [f(banding.loc[s, k]) if k in banding.columns else "—" for k, f in ukuran]
             for s in terpilih if s in banding.index},
            index=[k for k, _ in ukuran],
        )
        st.markdown("**Perbandingan berdampingan**")
        st.dataframe(tabel, use_container_width=True)
        st.markdown(
            '<div class="catatan">Membandingkan saham dari sektor berbeda sering '
            'menyesatkan: bank wajar berutang besar, perusahaan teknologi wajar ber-PER '
            'tinggi. Perbandingan paling berguna dilakukan di dalam satu sektor.</div>',
            unsafe_allow_html=True,
        )
    elif len(terpilih) == 1:
        st.markdown('<div class="catatan">Pilih setidaknya dua saham untuk '
                    'dibandingkan.</div>', unsafe_allow_html=True)

    st.download_button(
        "UNDUH HASIL (CSV)",
        hasil.to_csv(index=False).encode("utf-8"),
        file_name=f"screener-{datetime.now():%Y%m%d-%H%M}.csv",
        mime="text/csv",
    )

    st.markdown(
        '<div class="catatan">'
        '<b>Membaca angkanya.</b> PER dan PBV rendah bisa berarti murah, bisa juga berarti '
        'pasar sedang memperkirakan labanya akan turun. ROE tinggi bagus, tapi periksa DER — '
        'ROE bisa digelembungkan dengan utang. Dividen besar patut dicurigai kalau harga '
        'sahamnya sedang jatuh, karena persentasenya naik justru karena penyebutnya mengecil. '
        'Semua angka berasal dari laporan yang sudah lewat, bukan ramalan.'
        '</div>',
        unsafe_allow_html=True,
    )


def screener_kripto():
    a, b = st.columns([2, 1])
    with a:
        jumlah = st.slider("Ambil berapa koin teratas", 50, 250, 100, step=50)
    with b:
        st.write("")
        if st.button("SEGARKAN", use_container_width=True, key="segar_kripto"):
            ambil_kripto_screener.clear()

    df = ambil_kripto_screener(jumlah)
    if df.empty:
        st.warning("Data tidak bisa diambil. CoinGecko membatasi permintaan gratis — "
                   "tunggu sebentar lalu coba lagi.")
        return

    with st.expander("Atur batas penyaringan", expanded=True):
        k1, k2, k3 = st.columns(3)
        with k1:
            kap_min = st.number_input("Kapitalisasi minimum (miliar $)", value=0.0, step=1.0)
        with k2:
            naik_7h = st.number_input("Kenaikan 7 hari minimum (%)", value=-100.0, step=5.0)
        with k3:
            dari_puncak = st.number_input("Maksimal turun dari puncak (%)", value=-100.0,
                                          step=10.0,
                                          help="-80 berarti hanya koin yang turunnya "
                                               "tidak lebih dari 80% dari harga tertingginya.")

    hasil = df.copy()
    if kap_min > 0:
        hasil = hasil[hasil["Kapitalisasi"] >= kap_min * 1e9]
    if naik_7h > -100:
        hasil = hasil[hasil["7 hari %"] >= naik_7h]
    if dari_puncak > -100:
        hasil = hasil[hasil["Dari puncak %"] >= dari_puncak]

    st.markdown(
        f'<div class="catatan"><b style="color:var(--aksen);">{len(hasil)} koin lolos</b> '
        f'dari {len(df)} yang diambil</div>',
        unsafe_allow_html=True,
    )
    if hasil.empty:
        st.warning("Tidak ada koin yang lolos. Longgarkan batasannya.")
        return

    urut = st.selectbox("Urutkan berdasarkan",
                        ["Peringkat", "Kapitalisasi", "24 jam %", "7 hari %",
                         "30 hari %", "Dari puncak %", "Volume"], key="urut_kripto")
    hasil = hasil.sort_values(urut, ascending=(urut == "Peringkat"), na_position="last")

    persen = lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
    tampil = pd.DataFrame({
        "#": hasil["Peringkat"].map(lambda x: f"{int(x)}" if pd.notna(x) else "—"),
        "Koin": hasil["Simbol"],
        "Nama": hasil["Nama"],
        "Harga": hasil["Harga"].map(format_harga_koin),
        "24 jam": hasil["24 jam %"].map(persen),
        "7 hari": hasil["7 hari %"].map(persen),
        "30 hari": hasil["30 hari %"].map(persen),
        "Dari puncak": hasil["Dari puncak %"].map(persen),
        "Kapitalisasi": hasil["Kapitalisasi"].map(format_ringkas),
        "Volume 24 jam": hasil["Volume"].map(format_ringkas),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True, height=460)

    st.download_button(
        "UNDUH HASIL (CSV)",
        hasil.to_csv(index=False).encode("utf-8"),
        file_name=f"screener-kripto-{datetime.now():%Y%m%d-%H%M}.csv",
        mime="text/csv",
        key="unduh_kripto",
    )

    st.markdown(
        '<div class="catatan">Kolom <b>Dari puncak</b> menunjukkan jarak harga sekarang '
        'terhadap harga tertinggi sepanjang sejarah koin itu. Angka −90% berarti koin perlu '
        'naik sepuluh kali lipat hanya untuk kembali ke titik semula.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — FUNDAMENTAL
# ──────────────────────────────────────────────────────────────────────

def halaman_fundamental():
    st.subheader("Analisis Fundamental")

    a, b = st.columns([3, 1])
    with a:
        simbol = st.text_input("Simbol saham", value="BBCA.JK",
                               placeholder="BBCA.JK, TLKM.JK, AAPL, MSFT")
    with b:
        st.write("")
        if st.button("SEGARKAN", use_container_width=True, key="segar_fund"):
            ambil_fundamental_satu.clear()
            ambil_laporan.clear()

    simbol = simbol.strip().upper()
    if not simbol:
        return

    info = ambil_fundamental_satu(simbol)
    if not info or not info.get("regularMarketPrice"):
        st.warning(f"Data untuk **{simbol}** tidak ditemukan. Periksa penulisan simbolnya — "
                   "saham Indonesia butuh akhiran `.JK`.")
        return

    nama = info.get("longName") or info.get("shortName") or simbol
    st.markdown(
        f'<div style="font-size:1.25rem;font-weight:700;color:var(--terang);">{nama}</div>'
        f'<div style="color:var(--teks3);font-size:0.78rem;">{simbol} &nbsp;·&nbsp; '
        f'{info.get("sector") or "—"} &nbsp;·&nbsp; {info.get("industry") or "—"}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    dy = _angka(info.get("dividendYield"))
    if not math.isnan(dy) and dy < 1:
        dy *= 100

    ukuran = [
        ("HARGA", format_angka(info.get("regularMarketPrice")), ""),
        ("KAPITALISASI", format_ringkas(info.get("marketCap"), ""), ""),
        ("PER", format_angka(info.get("trailingPE"), 1), "harga ÷ laba"),
        ("PBV", format_angka(info.get("priceToBook"), 2), "harga ÷ nilai buku"),
        ("ROE", f'{_angka(info.get("returnOnEquity")) * 100:.1f}%'
                if not math.isnan(_angka(info.get("returnOnEquity"))) else "—", "imbal modal"),
        ("MARGIN LABA", f'{_angka(info.get("profitMargins")) * 100:.1f}%'
                        if not math.isnan(_angka(info.get("profitMargins"))) else "—", ""),
        ("DER", format_angka(info.get("debtToEquity"), 1), "utang ÷ modal"),
        ("DIVIDEN", f"{dy:.2f}%" if not math.isnan(dy) else "—", "imbal hasil"),
    ]
    for i in range(0, len(ukuran), 4):
        kolom = st.columns(4)
        for k, (label, nilai, ket) in zip(kolom, ukuran[i:i + 4]):
            with k:
                kartu(label, nilai, ket)

    tinggi = _angka(info.get("fiftyTwoWeekHigh"))
    rendah = _angka(info.get("fiftyTwoWeekLow"))
    kini = _angka(info.get("regularMarketPrice"))
    if not any(math.isnan(v) for v in (tinggi, rendah, kini)) and tinggi > rendah:
        posisi = (kini - rendah) / (tinggi - rendah) * 100
        st.markdown(
            f'<div class="kartu"><div class="label">POSISI DALAM RENTANG 52 MINGGU</div>'
            f'<div style="position:relative;height:8px;background:var(--kisi);border-radius:4px;'
            f'margin:0.6rem 0 0.35rem;">'
            f'<div style="position:absolute;left:{posisi:.1f}%;top:-3px;width:3px;height:14px;'
            f'background:var(--aksen);border-radius:1px;"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;'
            f'color:var(--teks3);"><span>{format_angka(rendah)}</span>'
            f'<span style="color:var(--aksen);">{posisi:.0f}% dari bawah</span>'
            f'<span>{format_angka(tinggi)}</span></div></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    laporan = ambil_laporan(simbol)
    t1, t2, t3 = st.tabs(["Laba Rugi", "Neraca", "Arus Kas"])
    for tab, kunci, judul in [(t1, "laba_rugi", "laba rugi"),
                              (t2, "neraca", "neraca"),
                              (t3, "arus_kas", "arus kas")]:
        with tab:
            tabel_laporan(laporan.get(kunci), judul)

    st.markdown(
        '<div class="catatan">Angka laporan keuangan berasal dari Yahoo Finance dan '
        'kadang tidak lengkap untuk emiten kecil. Untuk keputusan penting, bandingkan dengan '
        'laporan resmi di situs IDX atau situs emiten. Rasio menggambarkan masa lalu — '
        'harga saham bergerak karena perkiraan masa depan.</div>',
        unsafe_allow_html=True,
    )


def tabel_laporan(df, judul: str):
    if df is None or not hasattr(df, "empty") or df.empty:
        st.info(f"Laporan {judul} tidak tersedia untuk emiten ini.")
        return

    tampil = df.copy()
    tampil.columns = [c.strftime("%Y") if hasattr(c, "strftime") else str(c)
                      for c in tampil.columns]
    tampil = tampil.map(lambda x: format_ringkas(x, "") if pd.notna(x) else "—")
    st.dataframe(tampil, use_container_width=True, height=420)
    st.markdown(
        '<div class="catatan">Satuan: rb = ribu · jt = juta · M = miliar · T = triliun, '
        'dalam mata uang pelaporan emiten.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — KALKULATOR POSISI & RISIKO
# ──────────────────────────────────────────────────────────────────────

def halaman_kalkulator():
    st.subheader("Kalkulator Posisi & Risiko")
    st.markdown(
        '<div class="catatan">Alat ini tidak menebak arah harga. Ia menjawab pertanyaan '
        'yang lebih penting: <i>kalau saya salah, berapa yang hilang?</i></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    t1, t4, t2, t3 = st.tabs(["Ukuran Posisi", "Posisi Forex",
                              "Rata-rata Harga", "Titik Impas"])
    with t1:
        kalkulator_posisi()
    with t4:
        kalkulator_forex()
    with t2:
        kalkulator_averaging()
    with t3:
        kalkulator_impas()


def kalkulator_forex():
    st.markdown("**Berapa lot yang boleh saya buka, dan berapa rupiah risikonya?**")

    a, b = st.columns(2)
    with a:
        pasangan = st.selectbox("Pasangan", list(FOREX_SEMUA),
                                format_func=lambda x: FOREX_SEMUA[x], key="fx_pair")
        modal = st.number_input("Modal akun (Rp)", min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f", key="fx_modal")
        risiko_persen = st.slider("Risiko per transaksi (%)", 0.5, 10.0, 2.0, 0.5,
                                  key="fx_risiko")
    with b:
        jenis_lot = st.selectbox("Ukuran lot", list(LOT_FOREX), key="fx_lot")
        stop_pip = st.number_input("Jarak stop loss (pip)", min_value=1.0, value=30.0,
                                   step=5.0, key="fx_stop")
        target_pip = st.number_input("Jarak target (pip)", min_value=0.0, value=60.0,
                                     step=5.0, key="fx_target")

    kutipan = ambil_kutipan((pasangan,))
    if kutipan.empty:
        st.warning("Harga pasangan ini tidak bisa diambil sekarang.")
        return
    harga = float(kutipan.iloc[0]["Harga"])
    dasar, kutip = mata_uang_pasangan(pasangan)
    unit = LOT_FOREX[jenis_lot]

    kurs = ambil_kurs_ke_idr(kutip) if kutip else float("nan")
    n = nilai_pip(pasangan, harga, unit, kurs if not math.isnan(kurs) else None)

    if math.isnan(n["nilai_idr"]):
        st.warning(f"Kurs {kutip} ke rupiah tidak bisa diambil, jadi risiko rupiah "
                   f"tidak bisa dihitung. Nilai pip dalam {kutip}: "
                   f"{n['nilai_kutip']:,.2f} per lot.")
        return

    nominal_risiko = modal * risiko_persen / 100
    risiko_per_lot = stop_pip * n["nilai_idr"]
    lot = nominal_risiko / risiko_per_lot if risiko_per_lot else 0

    k = st.columns(4)
    with k[0]:
        kartu("HARGA SEKARANG", format_angka(harga, 4), f"1 pip = {n['pip']:g}")
    with k[1]:
        kartu("NILAI 1 PIP", "Rp " + format_angka(n["nilai_idr"], 0),
              f"per {jenis_lot.split(' ')[0].lower()} lot")
    with k[2]:
        kartu("BOLEH BUKA", f"{lot:.2f} lot",
              f"{lot * unit:,.0f} unit {dasar}" if dasar else "")
    with k[3]:
        kartu("RISIKO", "Rp " + format_angka(nominal_risiko, 0),
              f"{risiko_persen:g}% dari modal", "turun")

    if target_pip > 0:
        rasio = target_pip / stop_pip
        untung = lot * target_pip * n["nilai_idr"]
        k = st.columns(3)
        with k[0]:
            kartu("POTENSI UNTUNG", "Rp " + format_angka(untung, 0),
                  f"kalau target {target_pip:g} pip tercapai", "naik")
        with k[1]:
            kartu("RASIO UNTUNG : RUGI", f"{rasio:.2f} : 1",
                  "di atas 1 berarti target lebih jauh dari stop",
                  "naik" if rasio >= 1 else "turun")
        with k[2]:
            perlu = 100 / (1 + rasio)
            kartu("MENANG MINIMAL", f"{perlu:.0f}%", "agar tidak merugi jangka panjang")

    if lot < 0.01:
        st.warning("Ukuran posisi yang dihitung lebih kecil dari 0,01 lot. Modal Anda "
                   "terlalu kecil untuk jarak stop sebesar itu, atau risikonya terlalu ketat.")

    st.markdown(
        f'<div class="catatan">'
        f'<b>Cara angka ini dihitung.</b> Nilai satu pip lahir dalam mata uang kutipan '
        f'({kutip}), lalu ditukar ke rupiah memakai kurs {kutip}/IDR '
        f'{format_angka(kurs, 2) if not math.isnan(kurs) else "—"}. Langkah penukaran ini '
        f'sering dilewatkan orang, dan akibatnya risiko yang sesungguhnya bisa meleset jauh '
        f'dari yang dikira.<br><br>'
        f'Perhitungan ini <b>belum</b> memasukkan spread, komisi, dan bunga menginap. '
        f'Perhitungan ini juga mengandaikan stop loss Anda benar-benar tereksekusi di harga '
        f'itu — saat berita besar keluar, harga bisa melompat melewatinya.<br><br>'
        f'<b class="turun">Satu hal yang pantas diketahui sebelum mulai.</b> Broker forex '
        f'ritel di Eropa, Inggris, dan Australia diwajibkan hukum mengumumkan berapa persen '
        f'nasabahnya merugi. Angka yang mereka umumkan sendiri berkisar 70–80%. Daya ungkit '
        f'yang membuat forex terasa menggoda adalah juga sebab utama angka itu setinggi itu.'
        f'</div>',
        unsafe_allow_html=True,
    )


def kalkulator_posisi():
    k1, k2 = st.columns(2)
    with k1:
        modal = st.number_input("Total modal (Rp)", min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f")
        risiko_persen = st.slider("Risiko maksimum per transaksi (%)", 0.5, 10.0, 2.0, 0.5,
                                  help="Aturan umum: 1–2% dari modal. Artinya kalau salah, "
                                       "kerugian dibatasi sebesar itu.")
    with k2:
        harga_masuk = st.number_input("Harga beli (Rp)", min_value=0.0, value=5000.0, step=50.0)
        stop_loss = st.number_input("Batas rugi / stop loss (Rp)", min_value=0.0,
                                    value=4700.0, step=50.0)

    target = st.number_input("Target harga jual (Rp) — boleh dikosongkan",
                             min_value=0.0, value=5800.0, step=50.0)

    if harga_masuk <= 0 or stop_loss <= 0:
        st.info("Isi harga beli dan batas rugi.")
        return
    if stop_loss >= harga_masuk:
        st.warning("Batas rugi harus **di bawah** harga beli.")
        return

    rugi_per_lembar = harga_masuk - stop_loss
    nominal_risiko = modal * risiko_persen / 100
    lembar = nominal_risiko / rugi_per_lembar
    lot = int(lembar // LOT)

    if lot < 1:
        st.warning(
            f"Dengan risiko {risiko_persen:g}% ({format_angka(nominal_risiko, 0)}) dan jarak "
            f"stop loss {format_angka(rugi_per_lembar, 0)} per lembar, Anda belum mampu "
            f"membeli satu lot pun. Pilihannya: perbesar modal, perlonggar risiko, atau "
            f"cari harga masuk yang lebih dekat ke batas rugi."
        )
        return

    nilai_beli = lot * LOT * harga_masuk
    rugi_nyata = lot * LOT * rugi_per_lembar
    porsi_modal = nilai_beli / modal * 100 if modal else 0

    k = st.columns(4)
    with k[0]:
        kartu("BOLEH BELI", f"{lot:,} lot", f"{lot * LOT:,} lembar")
    with k[1]:
        kartu("NILAI PEMBELIAN", format_angka(nilai_beli, 0), f"{porsi_modal:.1f}% dari modal")
    with k[2]:
        kartu("RISIKO NYATA", format_angka(rugi_nyata, 0),
              f"{rugi_nyata / modal * 100:.2f}% dari modal" if modal else "", "turun")
    with k[3]:
        if target > harga_masuk:
            untung = lot * LOT * (target - harga_masuk)
            rasio = (target - harga_masuk) / rugi_per_lembar
            kartu("POTENSI UNTUNG", format_angka(untung, 0),
                  f"rasio {rasio:.2f} : 1", "naik")
        else:
            kartu("POTENSI UNTUNG", "—", "target belum diisi")

    if porsi_modal > 100:
        st.warning(f"Nilai pembelian melebihi modal Anda ({porsi_modal:.0f}%). "
                   f"Jarak stop loss terlalu sempit untuk ukuran risiko yang dipilih.")

    if target > harga_masuk:
        rasio = (target - harga_masuk) / rugi_per_lembar
        if rasio < 1:
            st.markdown(
                f'<div class="catatan"><b class="turun">Rasio {rasio:.2f} : 1.</b> '
                f'Anda mempertaruhkan lebih banyak daripada yang mungkin didapat. '
                f'Agar tetap untung dalam jangka panjang, Anda harus benar lebih dari '
                f'{100 / (1 + rasio):.0f}% dari waktu — sesuatu yang jarang tercapai.</div>',
                unsafe_allow_html=True,
            )
        else:
            menang_perlu = 100 / (1 + rasio)
            st.markdown(
                f'<div class="catatan"><b class="naik">Rasio {rasio:.2f} : 1.</b> '
                f'Dengan rasio ini, Anda cukup benar {menang_perlu:.0f}% dari waktu untuk '
                f'impas — sisanya menjadi keuntungan.</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="catatan">Perhitungan ini mengabaikan biaya transaksi dan mengandaikan '
        'stop loss Anda benar-benar tereksekusi di harga itu. Saat pasar bergerak liar atau '
        'saham tidak likuid, harga jual sesungguhnya bisa lebih rendah.</div>',
        unsafe_allow_html=True,
    )


def kalkulator_averaging():
    st.markdown("**Berapa harga rata-rata saya setelah membeli lagi?**")

    k1, k2 = st.columns(2)
    with k1:
        lot1 = st.number_input("Lot yang sudah dimiliki", min_value=0.0, value=10.0, step=1.0)
        harga1 = st.number_input("Harga beli rata-rata sekarang (Rp)",
                                 min_value=0.0, value=5000.0, step=50.0)
    with k2:
        lot2 = st.number_input("Lot yang akan dibeli", min_value=0.0, value=10.0, step=1.0)
        harga2 = st.number_input("Harga beli baru (Rp)", min_value=0.0, value=4200.0, step=50.0)

    harga_pasar = st.number_input("Harga pasar sekarang (Rp)", min_value=0.0,
                                  value=4200.0, step=50.0)

    total_lot = lot1 + lot2
    if total_lot <= 0:
        st.info("Isi jumlah lot.")
        return

    modal_lama = lot1 * LOT * harga1
    modal_baru = lot2 * LOT * harga2
    total_modal = modal_lama + modal_baru
    rata = total_modal / (total_lot * LOT) if total_lot else 0

    nilai_kini = total_lot * LOT * harga_pasar
    laba = nilai_kini - total_modal
    laba_persen = laba / total_modal * 100 if total_modal else 0

    laba_sebelum = lot1 * LOT * harga_pasar - modal_lama
    persen_sebelum = laba_sebelum / modal_lama * 100 if modal_lama else 0

    k = st.columns(4)
    with k[0]:
        kartu("HARGA RATA-RATA BARU", format_angka(rata, 0),
              f"dari {format_angka(harga1, 0)}",
              "naik" if rata < harga1 else ("turun" if rata > harga1 else "diam"))
    with k[1]:
        kartu("TOTAL MODAL", format_angka(total_modal, 0), f"{total_lot:g} lot")
    with k[2]:
        kartu("LABA / RUGI SEKARANG", f"{laba:+,.0f}", f"{laba_persen:+.2f}%", warna(laba))
    with k[3]:
        kartu("SEBELUM MENAMBAH", f"{laba_sebelum:+,.0f}", f"{persen_sebelum:+.2f}%",
              warna(laba_sebelum))

    impas = rata
    st.markdown(
        f'<div class="catatan">Harga perlu kembali ke <b style="color:var(--aksen);">'
        f'{format_angka(impas, 0)}</b> agar Anda impas — '
        f'{(impas / harga_pasar - 1) * 100:+.1f}% dari harga sekarang.'
        f'</div>',
        unsafe_allow_html=True,
    )

    if harga2 < harga1:
        st.markdown(
            '<div class="catatan" style="margin-top:0.6rem;">'
            '<b>Sebelum menambah di harga lebih rendah,</b> tanyakan satu hal: apakah Anda '
            'membeli lagi karena perusahaannya masih baik, atau karena tidak sanggup mengakui '
            'kerugian? Menambah posisi pada saham yang jatuh memperbesar taruhan pada satu '
            'keyakinan yang sejauh ini terbukti keliru. Kadang itu tepat. Sering kali tidak.'
            '</div>',
            unsafe_allow_html=True,
        )


def kalkulator_impas():
    st.markdown("**Berapa harga jual agar saya benar-benar untung setelah biaya?**")

    k1, k2, k3 = st.columns(3)
    with k1:
        harga_beli = st.number_input("Harga beli (Rp)", min_value=0.0, value=5000.0, step=50.0,
                                     key="impas_beli")
        jumlah_lot = st.number_input("Jumlah lot", min_value=0.0, value=10.0, step=1.0,
                                     key="impas_lot")
    with k2:
        biaya_beli = st.number_input("Biaya beli (%)", min_value=0.0, value=BIAYA_BELI,
                                     step=0.01, format="%.3f")
        biaya_jual = st.number_input("Biaya jual (%)", min_value=0.0, value=BIAYA_JUAL,
                                     step=0.01, format="%.3f",
                                     help="Biasanya sudah termasuk pajak penjualan 0,1%.")
    with k3:
        target_untung = st.number_input("Target untung bersih (%)", min_value=0.0,
                                        value=10.0, step=1.0)

    if harga_beli <= 0 or jumlah_lot <= 0:
        st.info("Isi harga beli dan jumlah lot.")
        return

    lembar = jumlah_lot * LOT
    nilai_beli = lembar * harga_beli
    ongkos_beli = nilai_beli * biaya_beli / 100
    modal_total = nilai_beli + ongkos_beli

    # Jual di harga H: terima = lembar*H*(1 - biaya_jual/100). Impas saat = modal_total.
    faktor_jual = 1 - biaya_jual / 100
    harga_impas = modal_total / (lembar * faktor_jual) if faktor_jual > 0 else float("nan")
    harga_target = (modal_total * (1 + target_untung / 100)) / (lembar * faktor_jual) \
        if faktor_jual > 0 else float("nan")

    k = st.columns(4)
    with k[0]:
        kartu("MODAL KELUAR", format_angka(modal_total, 0),
              f"termasuk biaya {format_angka(ongkos_beli, 0)}")
    with k[1]:
        kartu("HARGA IMPAS", format_angka(harga_impas, 0),
              f"{(harga_impas / harga_beli - 1) * 100:+.2f}% dari harga beli")
    with k[2]:
        kartu("HARGA UNTUK UNTUNG " + f"{target_untung:g}%", format_angka(harga_target, 0),
              f"{(harga_target / harga_beli - 1) * 100:+.2f}% dari harga beli", "naik")
    with k[3]:
        untung_bersih = modal_total * target_untung / 100
        kartu("UNTUNG BERSIH", format_angka(untung_bersih, 0), "setelah semua biaya", "naik")

    st.markdown(
        f'<div class="catatan">Biaya total pulang-pergi sekitar '
        f'<b>{biaya_beli + biaya_jual:.2f}%</b>. Artinya harga harus naik sebanyak itu '
        f'hanya untuk kembali ke titik nol. Inilah alasan trading terlalu sering menggerus '
        f'modal: setiap putaran memungut ongkos, entah Anda benar atau salah.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — PERINGATAN HARGA
# ──────────────────────────────────────────────────────────────────────

def halaman_peringatan():
    st.subheader("Peringatan Harga")
    st.markdown(
        '<div class="catatan">Peringatan diperiksa setiap kali halaman ini dibuka. '
        'Tidak ada notifikasi yang dikirim ke ponsel — aplikasi ini berjalan di komputer '
        'Anda, tanpa server yang mengawasi pasar saat aplikasi ditutup.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    daftar = st.session_state.peringatan

    with st.expander("Pasang peringatan baru", expanded=not daftar):
        a, b, c, d = st.columns([2, 1.2, 1.2, 1])
        with a:
            simbol = st.text_input("Simbol", placeholder="BBCA.JK, AAPL, BTC-USD",
                                   key="alert_simbol")
        with b:
            arah = st.selectbox("Kondisi", ["Naik ke atas", "Turun ke bawah"])
        with c:
            batas = st.number_input("Harga batas", min_value=0.0, value=0.0, step=1.0,
                                    format="%.4f")
        with d:
            st.write("")
            st.write("")
            if st.button("PASANG", use_container_width=True, key="pasang_alert"):
                if simbol.strip() and batas > 0:
                    daftar.append({
                        "simbol": simbol.strip().upper(),
                        "arah": "atas" if arah == "Naik ke atas" else "bawah",
                        "batas": batas,
                        "dipasang": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    simpan_json(BERKAS_PERINGATAN, daftar)
                    st.rerun()
                else:
                    st.warning("Simbol dan harga batas harus diisi.")

        if daftar:
            label = [f'{p["simbol"]} {"≥" if p["arah"] == "atas" else "≤"} '
                     f'{format_angka(p["batas"])}' for p in daftar]
            buang = st.multiselect("Hapus peringatan", list(range(len(daftar))),
                                   format_func=lambda i: label[i],
                                   placeholder="Pilih yang mau dihapus")
            if buang and st.button("HAPUS TERPILIH", key="hapus_alert"):
                st.session_state.peringatan = [p for i, p in enumerate(daftar)
                                               if i not in buang]
                simpan_json(BERKAS_PERINGATAN, st.session_state.peringatan)
                st.rerun()

    if not daftar:
        st.info("Belum ada peringatan. Pasang lewat panel di atas.")
        return

    df = ambil_kutipan(tuple(sorted({p["simbol"] for p in daftar})))
    if df.empty:
        st.warning("Harga tidak bisa diambil sekarang. Periksa koneksi internet Anda.")
        return
    peta = dict(zip(df["Simbol"], df["Harga"]))

    kena, menunggu, gagal = [], [], []
    for p in daftar:
        harga = peta.get(p["simbol"])
        if harga is None:
            gagal.append(p)
            continue
        tercapai = harga >= p["batas"] if p["arah"] == "atas" else harga <= p["batas"]
        jarak = (harga - p["batas"]) / p["batas"] * 100 if p["batas"] else 0
        (kena if tercapai else menunggu).append({**p, "harga": harga, "jarak": jarak})

    k = st.columns(3)
    with k[0]:
        kartu("TERSENTUH", str(len(kena)), "sudah melewati batas",
              "naik" if kena else "diam")
    with k[1]:
        kartu("MENUNGGU", str(len(menunggu)), "belum tercapai")
    with k[2]:
        kartu("GAGAL DIBACA", str(len(gagal)), "simbol bermasalah" if gagal else "")

    if kena:
        st.write("")
        st.markdown("**Sudah tersentuh**")
        for p in kena:
            tanda = "≥" if p["arah"] == "atas" else "≤"
            st.markdown(
                f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<span style="color:var(--terang);font-weight:600;">{p["simbol"]}</span>'
                f'<span style="color:var(--aksen);font-size:0.78rem;">TERCAPAI</span></div>'
                f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.25rem;">'
                f'Harga sekarang <b>{format_angka(p["harga"])}</b>, '
                f'batas {tanda} {format_angka(p["batas"])} '
                f'<span class="{warna(p["jarak"])}">({p["jarak"]:+.2f}%)</span></div>'
                f'<div style="color:var(--teks4);font-size:0.68rem;margin-top:0.2rem;">'
                f'dipasang {p["dipasang"]}</div></div>',
                unsafe_allow_html=True,
            )

    if menunggu:
        st.write("")
        st.markdown("**Masih menunggu**")
        st.dataframe(pd.DataFrame({
            "Simbol": [p["simbol"] for p in menunggu],
            "Kondisi": ["≥" if p["arah"] == "atas" else "≤" for p in menunggu],
            "Batas": [format_angka(p["batas"]) for p in menunggu],
            "Harga sekarang": [format_angka(p["harga"]) for p in menunggu],
            "Jarak": [f'{p["jarak"]:+.2f}%' for p in menunggu],
            "Dipasang": [p["dipasang"] for p in menunggu],
        }), use_container_width=True, hide_index=True)

    if gagal:
        st.warning("Simbol berikut tidak bisa dibaca — periksa penulisannya: "
                   + ", ".join(p["simbol"] for p in gagal))


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — JURNAL TRANSAKSI
# ──────────────────────────────────────────────────────────────────────

def halaman_jurnal():
    st.subheader("Jurnal Transaksi")
    st.markdown(
        '<div class="catatan">Mencatat <i>alasan</i> membeli jauh lebih berguna daripada '
        'mencatat harganya. Harga bisa dilihat kapan saja; alasan menguap dalam hitungan '
        'minggu — dan bersamanya, kemampuan Anda mengenali kesalahan yang berulang.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    jurnal = st.session_state.jurnal
    t_catat, t_riwayat, t_statistik = st.tabs(["Catat", "Riwayat", "Statistik"])

    with t_catat:
        a, b, c = st.columns(3)
        with a:
            simbol = st.text_input("Simbol", placeholder="BBCA.JK", key="j_simbol")
            aksi = st.selectbox("Aksi", ["Beli", "Jual"], key="j_aksi")
        with b:
            jumlah = st.number_input("Jumlah (lembar/unit)", min_value=0.0, value=0.0,
                                     step=100.0, key="j_jumlah")
            harga = st.number_input("Harga", min_value=0.0, value=0.0, step=1.0,
                                    format="%.4f", key="j_harga")
        with c:
            tanggal = st.date_input("Tanggal", value=datetime.now(), key="j_tanggal")
            emosi = st.selectbox("Suasana hati saat memutuskan",
                                 ["Tenang", "Ragu", "Takut ketinggalan", "Panik",
                                  "Percaya diri", "Terpaksa"], key="j_emosi")

        alasan = st.text_area("Alasan keputusan ini",
                              placeholder="Contoh: laba kuartal naik 18%, PER masih di bawah "
                                          "rata-rata sektor, dan harga baru memantul dari "
                                          "support 4.200.",
                              key="j_alasan", height=100)

        if st.button("SIMPAN CATATAN", key="j_simpan"):
            if simbol.strip() and jumlah > 0 and harga > 0:
                jurnal.append({
                    "tanggal": str(tanggal),
                    "simbol": simbol.strip().upper(),
                    "aksi": aksi,
                    "jumlah": jumlah,
                    "harga": harga,
                    "nilai": jumlah * harga,
                    "emosi": emosi,
                    "alasan": alasan.strip(),
                })
                simpan_json(BERKAS_JURNAL, jurnal)
                st.success("Tercatat.")
                st.rerun()
            else:
                st.warning("Simbol, jumlah, dan harga harus diisi.")

    with t_riwayat:
        if not jurnal:
            st.info("Belum ada catatan.")
        else:
            urut = sorted(jurnal, key=lambda x: x["tanggal"], reverse=True)
            for i, c in enumerate(urut):
                kelas = "naik" if c["aksi"] == "Beli" else "turun"
                st.markdown(
                    f'<div class="kartu" style="border-left:2px solid {warna_kelas(kelas)};">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:baseline;">'
                    f'<span style="color:var(--terang);font-weight:600;">'
                    f'{c["aksi"].upper()} {c["simbol"]}</span>'
                    f'<span style="color:var(--teks3);font-size:0.72rem;">{c["tanggal"]}</span>'
                    f'</div>'
                    f'<div style="color:var(--teks2);font-size:0.8rem;margin-top:0.2rem;">'
                    f'{c["jumlah"]:,.0f} @ {format_angka(c["harga"])} = '
                    f'<b>{format_angka(c["nilai"], 0)}</b></div>'
                    f'<div style="color:var(--aksen);font-size:0.7rem;margin-top:0.25rem;">'
                    f'Suasana: {c.get("emosi", "—")}</div>'
                    + (f'<div style="color:var(--teks6);font-size:0.78rem;line-height:1.6;'
                       f'margin-top:0.4rem;border-top:1px solid var(--kisi);padding-top:0.4rem;">'
                       f'{c["alasan"]}</div>' if c.get("alasan") else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )

            st.write("")
            label = [f'{c["tanggal"]} · {c["aksi"]} {c["simbol"]}' for c in jurnal]
            buang = st.multiselect("Hapus catatan", list(range(len(jurnal))),
                                   format_func=lambda i: label[i],
                                   placeholder="Pilih catatan yang mau dihapus")
            if buang and st.button("HAPUS TERPILIH", key="hapus_jurnal"):
                st.session_state.jurnal = [c for i, c in enumerate(jurnal) if i not in buang]
                simpan_json(BERKAS_JURNAL, st.session_state.jurnal)
                st.rerun()

            st.download_button(
                "UNDUH JURNAL (CSV)",
                pd.DataFrame(jurnal).to_csv(index=False).encode("utf-8"),
                file_name=f"jurnal-{datetime.now():%Y%m%d}.csv",
                mime="text/csv",
            )

    with t_statistik:
        statistik_jurnal(jurnal)


def pasangkan_transaksi(jurnal: list) -> pd.DataFrame:
    """
    Pasangkan Beli dan Jual per simbol dengan cara masuk-duluan-keluar-duluan (FIFO),
    lalu hitung untung-rugi tiap pasangan yang sudah tertutup.
    """
    from collections import defaultdict, deque

    antre = defaultdict(deque)
    tutup = []
    for c in sorted(jurnal, key=lambda x: x["tanggal"]):
        s, jml, hrg = c["simbol"], float(c["jumlah"]), float(c["harga"])
        if c["aksi"] == "Beli":
            antre[s].append({"jumlah": jml, "harga": hrg, "tanggal": c["tanggal"],
                             "emosi": c.get("emosi", "—")})
            continue
        sisa = jml
        while sisa > 1e-9 and antre[s]:
            beli = antre[s][0]
            pakai = min(sisa, beli["jumlah"])
            tutup.append({
                "Simbol": s,
                "Masuk": beli["tanggal"],
                "Keluar": c["tanggal"],
                "Jumlah": pakai,
                "Harga beli": beli["harga"],
                "Harga jual": hrg,
                "Laba": pakai * (hrg - beli["harga"]),
                "Persen": (hrg - beli["harga"]) / beli["harga"] * 100 if beli["harga"] else 0,
                "Emosi beli": beli["emosi"],
            })
            beli["jumlah"] -= pakai
            sisa -= pakai
            if beli["jumlah"] <= 1e-9:
                antre[s].popleft()

    return pd.DataFrame(tutup)


def statistik_jurnal(jurnal: list):
    if not jurnal:
        st.info("Belum ada catatan untuk dianalisis.")
        return

    df = pasangkan_transaksi(jurnal)
    if df.empty:
        st.info("Belum ada transaksi yang tertutup. Statistik muncul setelah ada penjualan "
                "yang berpasangan dengan pembelian sebelumnya.")
        return

    menang = df[df["Laba"] > 0]
    kalah = df[df["Laba"] < 0]
    total = len(df)
    tingkat_menang = len(menang) / total * 100 if total else 0
    rata_menang = menang["Laba"].mean() if len(menang) else 0
    rata_kalah = kalah["Laba"].mean() if len(kalah) else 0

    k = st.columns(4)
    with k[0]:
        kartu("TRANSAKSI TERTUTUP", str(total), f"dari {len(jurnal)} catatan")
    with k[1]:
        kartu("TINGKAT MENANG", f"{tingkat_menang:.0f}%", f"{len(menang)} dari {total}",
              "naik" if tingkat_menang >= 50 else "turun")
    with k[2]:
        laba_total = df["Laba"].sum()
        kartu("LABA BERSIH", f"{laba_total:+,.0f}", "seluruh riwayat", warna(laba_total))
    with k[3]:
        harapan = (tingkat_menang / 100 * rata_menang) + ((100 - tingkat_menang) / 100 * rata_kalah)
        kartu("HARAPAN PER TRANSAKSI", f"{harapan:+,.0f}",
              "rata-rata hasil tiap kali", warna(harapan))

    k = st.columns(3)
    with k[0]:
        kartu("RATA-RATA MENANG", f"{rata_menang:+,.0f}", f"{len(menang)} transaksi", "naik")
    with k[1]:
        kartu("RATA-RATA KALAH", f"{rata_kalah:+,.0f}", f"{len(kalah)} transaksi", "turun")
    with k[2]:
        rasio = abs(rata_menang / rata_kalah) if rata_kalah else float("nan")
        kartu("RASIO MENANG : KALAH", format_angka(rasio, 2),
              "di atas 1 berarti menang lebih besar",
              "naik" if rasio and rasio > 1 else "turun")

    if not math.isnan(rasio) and total >= 5:
        perlu = 100 / (1 + rasio)
        if tingkat_menang < perlu:
            pesan = (f'Dengan rasio {rasio:.2f}, Anda perlu benar setidaknya '
                     f'<b>{perlu:.0f}%</b> dari waktu untuk impas. Saat ini '
                     f'<b class="turun">{tingkat_menang:.0f}%</b> — kerugian rata-rata '
                     f'Anda terlalu besar dibanding keuntungannya. Yang perlu diperbaiki '
                     f'biasanya bukan cara memilih saham, melainkan kapan memotong rugi.')
        else:
            pesan = (f'Dengan rasio {rasio:.2f}, Anda cukup benar <b>{perlu:.0f}%</b> '
                     f'dari waktu untuk impas, dan saat ini '
                     f'<b class="naik">{tingkat_menang:.0f}%</b>. Pola ini sehat: '
                     f'kemenangan Anda lebih besar daripada kekalahan.')
        st.markdown(f'<div class="catatan">{pesan}</div>', unsafe_allow_html=True)

    st.write("")
    kiri, kanan = st.columns(2)

    with kiri:
        per_simbol = df.groupby("Simbol")["Laba"].sum().sort_values()
        fig = go.Figure(go.Bar(
            x=per_simbol.values, y=per_simbol.index, orientation="h",
            marker_color=[pal()["turun"] if v < 0 else pal()["naik"] for v in per_simbol.values],
        ))
        fig.update_layout(
            height=340, template=pal()["plotly"],
            paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
            margin=dict(l=10, r=10, t=40, b=10),
            title=dict(text="Laba / rugi per simbol", font=dict(size=12, color=pal()["aksen"])),
            font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
        )
        fig.update_xaxes(gridcolor=pal()["kisi"], zerolinecolor=pal()["kisi2"])
        fig.update_yaxes(gridcolor=pal()["kisi"])
        st.plotly_chart(fig, use_container_width=True)

    with kanan:
        if "Emosi beli" in df.columns and df["Emosi beli"].notna().any():
            per_emosi = df.groupby("Emosi beli")["Laba"].mean().sort_values()
            fig = go.Figure(go.Bar(
                x=per_emosi.values, y=per_emosi.index, orientation="h",
                marker_color=[pal()["turun"] if v < 0 else pal()["naik"] for v in per_emosi.values],
            ))
            fig.update_layout(
                height=340, template=pal()["plotly"],
                paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text="Rata-rata hasil menurut suasana hati saat membeli",
                           font=dict(size=12, color=pal()["aksen"])),
                font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
            )
            fig.update_xaxes(gridcolor=pal()["kisi"], zerolinecolor=pal()["kisi2"])
            fig.update_yaxes(gridcolor=pal()["kisi"])
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Rincian transaksi tertutup**")
    st.dataframe(pd.DataFrame({
        "Simbol": df["Simbol"],
        "Masuk": df["Masuk"],
        "Keluar": df["Keluar"],
        "Jumlah": df["Jumlah"].map(lambda x: f"{x:,.0f}"),
        "Harga beli": df["Harga beli"].map(format_angka),
        "Harga jual": df["Harga jual"].map(format_angka),
        "Laba": df["Laba"].map(lambda x: f"{x:+,.0f}"),
        "Persen": df["Persen"].map(lambda x: f"{x:+.2f}%"),
        "Suasana": df["Emosi beli"],
    }), use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="catatan">Pasangan beli-jual dihitung dengan cara masuk-duluan-'
        'keluar-duluan (FIFO), sama seperti yang umum dipakai sekuritas. Grafik suasana hati '
        'sering paling membuka mata: kalau batang "Takut ketinggalan" jauh di sebelah kiri, '
        'Anda baru saja menemukan kebocoran terbesar dalam cara Anda berinvestasi.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — DOMPET KRIPTO
# ──────────────────────────────────────────────────────────────────────

def halaman_dompet():
    st.subheader("Dompet Kripto")
    st.markdown(
        '<div class="kartu" style="border-left:2px solid var(--naik);">'
        '<div class="label">HANYA BACA</div>'
        '<div style="color:var(--teks2);font-size:0.8rem;line-height:1.7;margin-top:0.3rem;">'
        'Aplikasi ini hanya membaca <b>alamat publik</b> — deretan yang memang dirancang '
        'untuk dibagikan dan bisa dilihat siapa pun di explorer blockchain. Tidak ada yang '
        'bisa dipindahkan dari sini.<br><br>'
        '<b class="turun">Aplikasi ini tidak akan pernah meminta seed phrase atau private '
        'key Anda.</b> Kalau ada aplikasi mana pun yang memintanya — termasuk yang mengaku '
        'resmi — itu penipuan. Tutup, jangan isi.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    dompet = st.session_state.dompet

    with st.expander("Tambah atau hapus alamat", expanded=not dompet):
        a, b, c = st.columns([1, 3, 1])
        with a:
            jaringan = st.selectbox("Jaringan", list(JARINGAN))
        with b:
            alamat = st.text_input("Alamat publik",
                                   placeholder=JARINGAN[jaringan]["contoh"])
        with c:
            st.write("")
            st.write("")
            if st.button("TAMBAH", use_container_width=True, key="tambah_dompet"):
                alamat = alamat.strip()
                if not alamat:
                    st.warning("Alamat masih kosong.")
                elif not alamat_sah(jaringan, alamat):
                    st.error(f"Bukan alamat {jaringan} yang sah. "
                             f"Contoh bentuknya: {JARINGAN[jaringan]['contoh']}")
                elif any(d["alamat"] == alamat for d in dompet):
                    st.warning("Alamat itu sudah ada dalam daftar.")
                else:
                    dompet.append({"jaringan": jaringan, "alamat": alamat,
                                   "label": f"{JARINGAN[jaringan]['kode']} "
                                            f"#{len(dompet) + 1}"})
                    simpan_json(BERKAS_DOMPET, dompet)
                    st.rerun()

        if dompet:
            label = [f'{d["jaringan"]} — {d["alamat"][:14]}…{d["alamat"][-6:]}' for d in dompet]
            buang = st.multiselect("Hapus alamat", list(range(len(dompet))),
                                   format_func=lambda i: label[i],
                                   placeholder="Pilih alamat yang mau dihapus")
            if buang and st.button("HAPUS TERPILIH", key="hapus_dompet"):
                st.session_state.dompet = [d for i, d in enumerate(dompet) if i not in buang]
                simpan_json(BERKAS_DOMPET, st.session_state.dompet)
                st.rerun()

    if not dompet:
        st.info("Belum ada alamat. Tambahkan lewat panel di atas. "
                "Alamat disimpan lokal di folder `data/`, tidak dikirim ke mana pun "
                "selain ke jaringan blockchain untuk membaca saldonya.")
        return

    if st.button("⟳  MUAT ULANG SALDO"):
        ambil_saldo_dompet.clear()
        ambil_harga_koin.clear()
        st.rerun()

    harga = ambil_harga_koin(tuple(sorted({JARINGAN[d["jaringan"]]["koin"] for d in dompet})))

    total_usd = 0.0
    baris = []
    for d in dompet:
        j = JARINGAN[d["jaringan"]]
        hasil = ambil_saldo_dompet(d["jaringan"], d["alamat"])
        if hasil.get("galat"):
            baris.append({**d, "galat": hasil["galat"]})
            continue
        h = harga.get(j["koin"], {})
        usd = hasil["saldo"] * float(h.get("usd", 0) or 0)
        idr = hasil["saldo"] * float(h.get("idr", 0) or 0)
        nilai_token = sum(t["nilai_usd"] for t in hasil.get("token", []))
        total_usd += usd + nilai_token
        baris.append({**d, **hasil, "usd": usd, "idr": idr,
                      "ubah": float(h.get("usd_24h_change", 0) or 0),
                      "nilai_token": nilai_token})

    sah = [b for b in baris if "galat" not in b]
    if sah:
        k = st.columns(3)
        with k[0]:
            kartu("TOTAL NILAI", format_ringkas(total_usd), f"{len(sah)} alamat terbaca")
        with k[1]:
            total_idr = sum(b["idr"] for b in sah) + 0
            kartu("SETARA RUPIAH", "Rp " + format_angka(total_idr, 0),
                  "kurs dari CoinGecko")
        with k[2]:
            jml_token = sum(len(b.get("token", [])) for b in sah)
            kartu("TOKEN TERDETEKSI", f"{jml_token}", "di luar koin utama")
        st.write("")

    for b in baris:
        j = JARINGAN[b["jaringan"]]
        alamat_pendek = f'{b["alamat"][:16]}…{b["alamat"][-8:]}'

        if "galat" in b:
            st.markdown(
                f'<div class="kartu" style="border-left:2px solid var(--turun);">'
                f'<div class="label">{b["jaringan"].upper()}</div>'
                f'<div style="color:var(--teks3);font-size:0.72rem;font-family:monospace;">'
                f'{alamat_pendek}</div>'
                f'<div class="turun" style="font-size:0.8rem;margin-top:0.4rem;">'
                f'{b["galat"]}</div></div>',
                unsafe_allow_html=True,
            )
            continue

        kelas = warna(b["ubah"])
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid {warna_kelas(kelas)};">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span class="label">{b["jaringan"].upper()}</span>'
            f'<span class="{kelas}" style="font-size:0.72rem;">'
            f'{b["ubah"]:+.2f}% (24 jam)</span></div>'
            f'<div style="color:var(--teks3);font-size:0.72rem;font-family:monospace;'
            f'margin-top:0.15rem;">{alamat_pendek}</div>'
            f'<div class="angka" style="margin-top:0.45rem;">'
            f'{b["saldo"]:,.{j["desimal"] if b["saldo"] < 1 else 4}f} {j["kode"]}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;">'
            f'{format_ringkas(b["usd"])} &nbsp;·&nbsp; Rp {format_angka(b["idr"], 0)}</div>'
            + (f'<div style="color:var(--teks3);font-size:0.72rem;margin-top:0.25rem;">'
               f'{b["transaksi"]:,} transaksi</div>' if b.get("transaksi") else '')
            + '</div>',
            unsafe_allow_html=True,
        )

        if b.get("token"):
            with st.expander(f'{len(b["token"])} token di alamat ini'):
                st.dataframe(pd.DataFrame({
                    "Token": [t["kode"] for t in b["token"]],
                    "Nama": [t["nama"] for t in b["token"]],
                    "Jumlah": [f'{t["jumlah"]:,.4f}' for t in b["token"]],
                    "Nilai": [format_ringkas(t["nilai_usd"]) for t in b["token"]],
                }), use_container_width=True, hide_index=True)
                st.markdown(
                    '<div class="catatan">Banyak token bernilai nol adalah token sampah '
                    'yang dikirim tanpa diminta. Jangan pernah menukar atau menyetujui '
                    'token yang tidak Anda kenal — itu cara umum menguras dompet.</div>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        '<div class="catatan" style="margin-top:0.8rem;">'
        'Sumber data: Blockstream (Bitcoin), Ethplorer (Ethereum), RPC publik Solana, '
        'harga dari CoinGecko. Semuanya gratis tanpa API key. Saldo yang tampil adalah '
        'yang tercatat di blockchain — aset yang Anda simpan di bursa tidak akan muncul '
        'di sini karena tidak berada di alamat Anda sendiri.'
        '</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  MESIN BACKTEST
# ──────────────────────────────────────────────────────────────────────

def jalankan_backtest(harga: pd.Series, sinyal: pd.Series, modal_awal: float,
                      biaya_persen: float) -> dict:
    """
    Simulasi sederhana: sinyal 1 berarti ingin memegang, 0 berarti keluar.

    Sinyal digeser satu hari (shift) supaya keputusan hari ini dieksekusi pada
    harga besok. Tanpa itu, kita diam-diam berdagang memakai informasi yang
    belum tersedia — kesalahan paling umum dan paling menyesatkan dalam backtest.
    """
    harga = harga.dropna()
    sinyal = sinyal.reindex(harga.index).fillna(0).clip(0, 1)
    posisi = sinyal.shift(1).fillna(0)

    imbal_harian = harga.pct_change().fillna(0)
    imbal_strategi = imbal_harian * posisi

    # Biaya dipungut setiap kali posisi berubah (masuk atau keluar).
    ganti = posisi.diff().abs().fillna(0)
    imbal_strategi = imbal_strategi - ganti * (biaya_persen / 100)

    kurva = (1 + imbal_strategi).cumprod() * modal_awal
    kurva_pasar = (1 + imbal_harian).cumprod() * modal_awal

    jumlah_transaksi = int(ganti.sum())

    # Lama pengujian dihitung dari tanggal sungguhan, bukan dari jumlah batang.
    # Ini membuat hasil per tahun dan rasio Sharpe tetap benar untuk interval
    # apa pun — bulanan, mingguan, harian, maupun per jam. Menganggap satu
    # batang selalu sama dengan satu hari adalah cara paling mudah menghasilkan
    # angka yang terlihat mengesankan tetapi keliru.
    try:
        rentang_hari = (harga.index[-1] - harga.index[0]).total_seconds() / 86400
    except (AttributeError, TypeError):
        rentang_hari = len(harga)
    tahun = rentang_hari / 365.25 if rentang_hari > 0 else 0

    # Banyak batang per tahun diturunkan dari datanya sendiri, bukan ditebak.
    batang_per_tahun = (len(harga) / tahun) if tahun > 0 else 252

    def cagr(akhir):
        if tahun <= 0 or modal_awal <= 0 or akhir <= 0:
            return float("nan")
        return ((akhir / modal_awal) ** (1 / tahun) - 1) * 100

    def penurunan_terdalam(k):
        puncak = k.cummax()
        return float(((k - puncak) / puncak).min() * 100) if len(k) else float("nan")

    sd = imbal_strategi.std()
    sharpe = (imbal_strategi.mean() / sd * math.sqrt(batang_per_tahun)
              if sd and sd > 0 else float("nan"))

    # Bagi jadi transaksi terpisah — sekaligus catat tanggal dan hasilnya,
    # supaya bisa digambar di grafik dan dihitung sebarannya.
    transaksi = []
    masuk_harga = masuk_tgl = None
    for tgl, p in posisi.items():
        if p == 1 and masuk_tgl is None:
            masuk_tgl, masuk_harga = tgl, float(harga.loc[tgl])
        elif p == 0 and masuk_tgl is not None:
            keluar = float(harga.loc[tgl])
            transaksi.append({
                "masuk": masuk_tgl, "keluar": tgl,
                "harga_masuk": masuk_harga, "harga_keluar": keluar,
                "hasil": (keluar / masuk_harga - 1) * 100 if masuk_harga else 0.0,
                "hari": (tgl - masuk_tgl).days,
            })
            masuk_tgl = masuk_harga = None
    # Posisi yang masih terbuka di ujung data
    terbuka = None
    if masuk_tgl is not None:
        akhir_h = float(harga.iloc[-1])
        terbuka = {"masuk": masuk_tgl, "keluar": harga.index[-1],
                   "harga_masuk": masuk_harga, "harga_keluar": akhir_h,
                   "hasil": (akhir_h / masuk_harga - 1) * 100 if masuk_harga else 0.0}

    menang = sum(1 for t in transaksi if t["hasil"] > 0)
    total_tutup = len(transaksi)

    # Kurva penurunan (underwater) — jarak modal terhadap puncaknya sendiri
    puncak = kurva.cummax()
    penurunan_seri = (kurva - puncak) / puncak * 100

    # Hasil per bulan, untuk peta panas.
    # Modal awal ditaruh di depan sebagai titik acuan — tanpa itu, bulan pertama
    # tidak punya pembanding dan hasilnya raib dari peta, sehingga perkalian
    # seluruh bulan tidak lagi sama dengan hasil akhir.
    try:
        akhir_bulan = kurva.resample("ME").last().dropna()
        if len(akhir_bulan):
            deret = pd.concat([pd.Series([modal_awal]),
                               pd.Series(akhir_bulan.values)], ignore_index=True)
            bulanan = pd.Series(deret.pct_change().dropna().values * 100,
                                index=akhir_bulan.index)
        else:
            bulanan = pd.Series(dtype=float)
    except (TypeError, ValueError):
        bulanan = pd.Series(dtype=float)

    return {
        "kurva": kurva,
        "kurva_pasar": kurva_pasar,
        "akhir": float(kurva.iloc[-1]) if len(kurva) else float("nan"),
        "akhir_pasar": float(kurva_pasar.iloc[-1]) if len(kurva_pasar) else float("nan"),
        "cagr": cagr(float(kurva.iloc[-1])) if len(kurva) else float("nan"),
        "cagr_pasar": cagr(float(kurva_pasar.iloc[-1])) if len(kurva_pasar) else float("nan"),
        "penurunan": penurunan_terdalam(kurva),
        "penurunan_pasar": penurunan_terdalam(kurva_pasar),
        "sharpe": sharpe,
        "transaksi": jumlah_transaksi,
        "menang": menang,
        "total_tutup": total_tutup,
        "tahun": tahun,
        "waktu_di_pasar": float(posisi.mean() * 100) if len(posisi) else float("nan"),
        "daftar_transaksi": transaksi,
        "posisi_terbuka": terbuka,
        "penurunan_seri": penurunan_seri,
        "bulanan": bulanan,
        "posisi": posisi,
        "harga": harga,
        "batang": len(harga),
        "batang_per_tahun": batang_per_tahun,
    }


def buat_sinyal(strategi: str, harga: pd.Series, p: dict) -> pd.Series:
    if strategi == "Perpotongan Rata-rata":
        cepat = harga.rolling(p["cepat"]).mean()
        lambat = harga.rolling(p["lambat"]).mean()
        return (cepat > lambat).astype(int)

    if strategi == "RSI":
        rsi = hitung_rsi(harga, p["periode"])
        sinyal = pd.Series(0, index=harga.index)
        pegang = 0
        for i, nilai in enumerate(rsi):
            if pegang == 0 and nilai < p["beli"]:
                pegang = 1
            elif pegang == 1 and nilai > p["jual"]:
                pegang = 0
            sinyal.iloc[i] = pegang
        return sinyal

    if strategi == "Di Atas Rata-rata":
        return (harga > harga.rolling(p["periode"]).mean()).astype(int)

    return pd.Series(1, index=harga.index)  # Beli dan Tahan


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — BACKTEST
# ──────────────────────────────────────────────────────────────────────

def halaman_backtest():
    st.subheader("Backtest Strategi")
    st.markdown(
        '<div class="catatan">Backtest menunjukkan bagaimana sebuah aturan <i>akan</i> '
        'berjalan seandainya dipakai di masa lalu. Ia bukan ramalan, dan hasil yang '
        'mengagumkan justru pantas dicurigai lebih dulu.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    jenis = st.radio("Jenis instrumen", ["Saham & Kripto", "Forex"],
                     horizontal=True, key="bt_jenis")
    forex = jenis == "Forex"

    a, b, c, d = st.columns([2, 1, 1, 1.2])
    with a:
        if forex:
            pilihan = list(FOREX_SEMUA)
            simbol = st.selectbox("Pasangan mata uang", pilihan, key="bt_simbol_fx",
                                  format_func=lambda x: FOREX_SEMUA.get(x, x))
        else:
            pilihan = list(dict.fromkeys(
                (st.session_state.watchlist or []) + ["BBCA.JK", "TLKM.JK", "AAPL", "BTC-USD"]))
            simbol = st.selectbox("Simbol", pilihan, key="bt_simbol")
    with b:
        nama_interval = st.selectbox("Rentang waktu", list(INTERVAL_BACKTEST),
                                     index=2, key="bt_interval")
    with c:
        aturan = INTERVAL_BACKTEST[nama_interval]
        periode = st.selectbox("Lama pengujian", aturan["periode"],
                               index=len(aturan["periode"]) - 1, key=f"bt_p_{nama_interval}")
    with d:
        strategi = st.selectbox("Strategi", ["Perpotongan Rata-rata", "RSI",
                                             "Di Atas Rata-rata", "Beli dan Tahan"])

    interval = aturan["kode"]
    if aturan["catatan"]:
        st.markdown(f'<div class="catatan">{aturan["catatan"]}</div>',
                    unsafe_allow_html=True)

    p = {}
    k1, k2, k3 = st.columns(3)
    if strategi == "Perpotongan Rata-rata":
        with k1:
            p["cepat"] = st.number_input("Rata-rata cepat (hari)", 2, 100, 20)
        with k2:
            p["lambat"] = st.number_input("Rata-rata lambat (hari)", 5, 300, 50)
        if p["cepat"] >= p["lambat"]:
            st.warning("Rata-rata cepat harus lebih pendek daripada yang lambat.")
            return
    elif strategi == "RSI":
        with k1:
            p["periode"] = st.number_input("Periode RSI", 2, 50, 14)
        with k2:
            p["beli"] = st.number_input("Beli saat RSI di bawah", 5, 50, 30)
        with k3:
            p["jual"] = st.number_input("Jual saat RSI di atas", 50, 95, 70)
    elif strategi == "Di Atas Rata-rata":
        with k1:
            p["periode"] = st.number_input("Periode rata-rata (hari)", 5, 300, 200)

    df = ambil_riwayat(simbol, periode, interval)
    if df.empty:
        st.warning(f"Data {nama_interval.lower()} untuk **{simbol}** tidak tersedia pada "
                   f"periode ini. Rentang waktu pendek biasanya tidak ada untuk saham "
                   f"yang jarang diperdagangkan — coba rentang yang lebih panjang.")
        return
    if len(df) < aturan["min_batang"]:
        st.warning(f"Hanya {len(df)} batang data — terlalu sedikit untuk diuji "
                   f"(minimal {aturan['min_batang']}). Pilih periode yang lebih panjang, "
                   f"atau rentang waktu yang lebih pendek.")
        return

    harga = df["Close"].dropna()
    harga_kini = float(harga.iloc[-1])

    d1, d2 = st.columns(2)
    with d1:
        modal = st.number_input("Modal awal (Rp)", min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f")
    with d2:
        if forex:
            pip = ukuran_pip(simbol, harga_kini)
            spread_pip = st.number_input(
                "Spread (pip)", min_value=0.0, value=SPREAD_KHAS.get(simbol, 2.0),
                step=0.1, format="%.1f",
                help="Selisih harga beli dan jual yang dipungut broker. Ini biaya "
                     "utama di forex — bukan komisi persen seperti saham.")
            # Spread dibayar sekali per putaran (masuk + keluar). Mesin backtest
            # memungut biaya di tiap perubahan posisi, jadi separuhnya per perubahan.
            biaya = (spread_pip * pip / harga_kini * 100) / 2 if harga_kini else 0.0
            st.markdown(
                f'<div class="catatan">1 pip = {pip:g} · spread {spread_pip:g} pip setara '
                f'<b>{spread_pip * pip / harga_kini * 100:.4f}%</b> per putaran pada harga '
                f'{format_angka(harga_kini, 4)}</div>',
                unsafe_allow_html=True)
        else:
            biaya = st.number_input("Biaya per transaksi (%)", min_value=0.0,
                                    value=BIAYA_BELI, step=0.05, format="%.3f",
                                    help="Dipungut setiap kali masuk dan keluar posisi.")

    if forex:
        st.markdown(
            '<div class="kartu" style="border-left:2px solid var(--turun);">'
            '<div class="label">TIGA HAL YANG DIABAIKAN UJI INI</div>'
            '<div style="color:var(--teks2);font-size:0.8rem;line-height:1.75;'
            'margin-top:0.3rem;">'
            '<b>1. Bunga menginap (swap).</b> Posisi forex yang dibawa melewati pukul 5 sore '
            'waktu New York dikenai atau diberi bunga tiap malam, tergantung selisih suku '
            'bunga kedua negara. Pada posisi yang ditahan berbulan-bulan, angka ini bisa '
            'lebih besar daripada seluruh keuntungan harganya.<br>'
            '<b>2. Daya ungkit (leverage).</b> Uji ini menganggap Anda memakai modal penuh '
            'tanpa pinjaman. Broker ritel umumnya menawarkan 1:100 sampai 1:500 — yang '
            'melipatgandakan hasil sekaligus kerugian, dan memunculkan risiko akun '
            'tersapu habis (margin call) yang tidak tergambar di sini sama sekali.<br>'
            '<b>3. Data harian.</b> Kebanyakan pedagang forex bekerja di rentang menit atau '
            'jam. Menguji di data harian menjawab pertanyaan yang berbeda dari yang mungkin '
            'Anda maksud.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        st.write("")
    sinyal = buat_sinyal(strategi, harga, p)
    h = jalankan_backtest(harga, sinyal, modal, biaya)

    lebih_baik = h["akhir"] > h["akhir_pasar"]
    selisih = h["akhir"] - h["akhir_pasar"]
    warna_utama = pal()["naik"] if lebih_baik else pal()["turun"]

    # ── Papan hasil utama ──────────────────────────────────────────────
    hasil_s = (h["akhir"] / modal - 1) * 100 if modal else 0
    hasil_p = (h["akhir_pasar"] / modal - 1) * 100 if modal else 0
    lebar_s = min(abs(hasil_s), 200) / 2
    lebar_p = min(abs(hasil_p), 200) / 2

    st.markdown(
        f'<div class="kartu" style="border-left:3px solid {warna_utama};padding:1rem 1.2rem;">'
        f'<div class="label">HASIL PENGUJIAN — {strategi.upper()} PADA {simbol} '
        f'· {nama_interval.upper()} · {h["batang"]:,} BATANG</div>'
        f'<div style="font-size:1.9rem;font-weight:700;color:{warna_utama};'
        f'margin:0.3rem 0 0.1rem;">{selisih:+,.0f}</div>'
        f'<div style="color:var(--teks2);font-size:0.84rem;margin-bottom:0.9rem;">'
        f'{"lebih banyak" if lebih_baik else "lebih sedikit"} dibanding sekadar membeli lalu '
        f'mendiamkannya selama {h["tahun"]:.1f} tahun</div>'

        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.35rem;">'
        f'<span style="width:120px;font-size:0.72rem;color:var(--teks3);">STRATEGI</span>'
        f'<div style="flex:1;background:var(--kisi);height:16px;border-radius:2px;'
        f'overflow:hidden;"><div style="width:{lebar_s:.1f}%;height:100%;'
        f'background:{pal()["naik"] if hasil_s >= 0 else pal()["turun"]};"></div></div>'
        f'<span style="width:92px;text-align:right;font-size:0.82rem;font-weight:600;'
        f'color:{pal()["naik"] if hasil_s >= 0 else pal()["turun"]};">{hasil_s:+.1f}%</span></div>'

        f'<div style="display:flex;align-items:center;gap:0.6rem;">'
        f'<span style="width:120px;font-size:0.72rem;color:var(--teks3);">BELI &amp; TAHAN</span>'
        f'<div style="flex:1;background:var(--kisi);height:16px;border-radius:2px;'
        f'overflow:hidden;"><div style="width:{lebar_p:.1f}%;height:100%;'
        f'background:var(--biru);opacity:0.75;"></div></div>'
        f'<span style="width:92px;text-align:right;font-size:0.82rem;font-weight:600;'
        f'color:var(--biru);">{hasil_p:+.1f}%</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    k = st.columns(4)
    with k[0]:
        kartu("MODAL AKHIR", format_angka(h["akhir"], 0),
              f'dari {format_angka(modal, 0)}', warna(h["akhir"] - modal))
    with k[1]:
        kartu("HASIL PER TAHUN", f'{h["cagr"]:.2f}%' if not math.isnan(h["cagr"]) else "—",
              f'pasar {h["cagr_pasar"]:.2f}%' if not math.isnan(h["cagr_pasar"]) else "",
              "naik" if lebih_baik else "turun")
    with k[2]:
        kartu("PENURUNAN TERDALAM", f'{h["penurunan"]:.1f}%',
              f'pasar {h["penurunan_pasar"]:.1f}%', "turun")
    with k[3]:
        kartu("RASIO SHARPE", format_angka(h["sharpe"], 2), "makin tinggi makin baik")

    k = st.columns(4)
    with k[0]:
        kartu("JUMLAH TRANSAKSI", f'{h["transaksi"]:,}',
              f'{h["transaksi"] / h["tahun"]:.1f} per tahun' if h["tahun"] > 0 else "")
    with k[1]:
        menang = (h["menang"] / h["total_tutup"] * 100) if h["total_tutup"] else float("nan")
        kartu("TRANSAKSI UNTUNG", f"{menang:.0f}%" if not math.isnan(menang) else "—",
              f'{h["menang"]} dari {h["total_tutup"]}',
              "naik" if not math.isnan(menang) and menang >= 50 else "turun")
    with k[2]:
        kartu("WAKTU DI PASAR", f'{h["waktu_di_pasar"]:.0f}%', "sisanya memegang tunai")
    with k[3]:
        tr = h["daftar_transaksi"]
        rerata = sum(t["hari"] for t in tr) / len(tr) if tr else float("nan")
        if not math.isnan(rerata) and rerata < 1:
            jam = sum((t["keluar"] - t["masuk"]).total_seconds() / 3600
                      for t in tr) / len(tr)
            teks = f"{jam:.1f} jam"
        else:
            teks = f"{rerata:.0f} hari" if not math.isnan(rerata) else "—"
        kartu("RATA-RATA DITAHAN", teks, "per transaksi")

    # ── Kurva modal + kurva penurunan ─────────────────────────────────
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.68, 0.32],
                        subplot_titles=("Pertumbuhan modal", "Jarak dari puncak modal"))

    fig.add_trace(go.Scatter(x=h["kurva"].index, y=h["kurva"], name=strategi,
                             line=dict(color=pal()["aksen"], width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=h["kurva_pasar"].index, y=h["kurva_pasar"],
                             name="Beli dan Tahan",
                             line=dict(color=pal()["biru"], width=1.4, dash="dot")),
                  row=1, col=1)
    fig.add_hline(y=modal, line=dict(color=pal()["kisi2"], width=1), row=1, col=1)

    fig.add_trace(go.Scatter(x=h["penurunan_seri"].index, y=h["penurunan_seri"],
                             name="Penurunan", fill="tozeroy",
                             line=dict(color=pal()["turun"], width=1)), row=2, col=1)

    fig.update_layout(
        height=520, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", y=1.09, x=0, font=dict(size=10)),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    for anotasi in fig["layout"]["annotations"]:
        anotasi["font"] = dict(size=11, color=pal()["aksen"])
        anotasi["x"] = 0
        anotasi["xanchor"] = "left"
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(ticksuffix="%", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # ── Harga dengan masa memegang diarsir ────────────────────────────
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=h["harga"].index, y=h["harga"], name="Harga",
                              line=dict(color=pal()["teks3"], width=1.2)))
    for t in h["daftar_transaksi"]:
        fig2.add_vrect(x0=t["masuk"], x1=t["keluar"], line_width=0,
                       fillcolor=pal()["naik"] if t["hasil"] > 0 else pal()["turun"],
                       opacity=0.13, layer="below")
    if h["posisi_terbuka"]:
        t = h["posisi_terbuka"]
        fig2.add_vrect(x0=t["masuk"], x1=t["keluar"], line_width=0,
                       fillcolor=pal()["aksen"], opacity=0.13, layer="below")
    if h["daftar_transaksi"]:
        fig2.add_trace(go.Scatter(
            x=[t["masuk"] for t in h["daftar_transaksi"]],
            y=[t["harga_masuk"] for t in h["daftar_transaksi"]],
            mode="markers", name="Masuk",
            marker=dict(symbol="triangle-up", size=9, color=pal()["naik"])))
        fig2.add_trace(go.Scatter(
            x=[t["keluar"] for t in h["daftar_transaksi"]],
            y=[t["harga_keluar"] for t in h["daftar_transaksi"]],
            mode="markers", name="Keluar",
            marker=dict(symbol="triangle-down", size=9, color=pal()["turun"])))
    fig2.update_layout(
        height=320, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text="Kapan strategi memegang — arsir hijau untung, merah rugi",
                   font=dict(size=12, color=pal()["aksen"])),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig2.update_xaxes(gridcolor=pal()["kisi"])
    fig2.update_yaxes(gridcolor=pal()["kisi"])
    st.plotly_chart(fig2, use_container_width=True)

    # ── Peta panas bulanan + sebaran hasil transaksi ──────────────────
    kiri, kanan = st.columns([3, 2])

    with kiri:
        b = h["bulanan"]
        if len(b) >= 2:
            NAMA_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
            tabel = pd.DataFrame({"tahun": b.index.year, "bulan": b.index.month,
                                  "nilai": b.values}).pivot_table(
                index="tahun", columns="bulan", values="nilai")
            tabel = tabel.reindex(columns=range(1, 13))
            batas = max(abs(np.nanmin(tabel.values)), abs(np.nanmax(tabel.values)), 1)
            fig3 = go.Figure(go.Heatmap(
                z=tabel.values, x=NAMA_BULAN, y=[str(t) for t in tabel.index],
                colorscale=[[0, pal()["turun"]], [0.5, pal()["panel"]], [1, pal()["naik"]]],
                zmid=0, zmin=-batas, zmax=batas,
                text=[[f"{v:+.1f}" if not (v != v) else "" for v in baris]
                      for baris in tabel.values],
                texttemplate="%{text}", textfont=dict(size=9),
                hovertemplate="%{y} %{x}: %{z:+.2f}%<extra></extra>",
                showscale=False, xgap=2, ygap=2))
            fig3.update_layout(
                height=max(220, 46 * len(tabel) + 90), template=pal()["plotly"],
                paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["latar"],
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text="Hasil per bulan (%)",
                           font=dict(size=12, color=pal()["aksen"])),
                font=dict(family="Consolas, monospace", size=10, color=pal()["teks2"]))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Periode terlalu pendek untuk peta panas bulanan.")

    with kanan:
        tr = h["daftar_transaksi"]
        if len(tr) >= 3:
            hasil_tr = [t["hasil"] for t in tr]
            fig4 = go.Figure(go.Histogram(
                x=hasil_tr, nbinsx=min(24, max(6, len(hasil_tr) // 2)),
                marker=dict(color=pal()["aksen"], line=dict(color=pal()["latar"], width=1))))
            fig4.add_vline(x=0, line=dict(color=pal()["kisi2"], width=1.4))
            rerata = sum(hasil_tr) / len(hasil_tr)
            fig4.add_vline(x=rerata, line=dict(color=pal()["biru"], width=1.4, dash="dash"),
                           annotation_text=f"rata-rata {rerata:+.1f}%",
                           annotation_font=dict(size=9, color=pal()["biru"]))
            fig4.update_layout(
                height=max(220, 46 * max(1, len(h["bulanan"].index.year.unique())) + 90),
                template=pal()["plotly"],
                paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text="Sebaran hasil tiap transaksi (%)",
                           font=dict(size=12, color=pal()["aksen"])),
                bargap=0.05,
                font=dict(family="Consolas, monospace", size=10, color=pal()["teks2"]))
            fig4.update_xaxes(gridcolor=pal()["kisi"], ticksuffix="%")
            fig4.update_yaxes(gridcolor=pal()["kisi"])
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Transaksi terlalu sedikit untuk digambar sebarannya.")

    # ── Daftar transaksi ──────────────────────────────────────────────
    if h["daftar_transaksi"]:
        with st.expander(f'Rincian {len(h["daftar_transaksi"])} transaksi'):
            tr = h["daftar_transaksi"]
            st.dataframe(pd.DataFrame({
                "Masuk": [f'{t["masuk"]:%d %b %Y}' for t in tr],
                "Keluar": [f'{t["keluar"]:%d %b %Y}' for t in tr],
                "Hari": [t["hari"] for t in tr],
                "Harga masuk": [format_angka(t["harga_masuk"]) for t in tr],
                "Harga keluar": [format_angka(t["harga_keluar"]) for t in tr],
                "Hasil": [f'{t["hasil"]:+.2f}%' for t in tr],
            }), use_container_width=True, hide_index=True, height=340)

    if lebih_baik:
        putusan = (f'Strategi ini mengungguli beli-dan-tahan sebesar '
                   f'<b class="naik">{selisih:+,.0f}</b> selama {h["tahun"]:.1f} tahun.')
    else:
        putusan = (f'Strategi ini <b class="turun">kalah</b> dari sekadar membeli lalu '
                   f'mendiamkannya, selisih {selisih:+,.0f}.')
    st.markdown(f'<div class="catatan">{putusan}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="catatan" style="margin-top:0.8rem;">'
        '<b>Cara membaca hasil ini dengan jujur.</b><br>'
        '• Sinyal sudah digeser satu hari, jadi keputusan hari ini dieksekusi di harga besok. '
        'Tanpa itu, angkanya akan terlihat jauh lebih indah — dan palsu.<br>'
        '• Biaya transaksi sudah dipungut tiap kali masuk dan keluar. Strategi yang sering '
        'berpindah posisi biasanya kalah justru karena ini.<br>'
        '• Uji ini memakai satu saham dan satu rentang waktu. Ganti simbolnya, ganti '
        'periodenya, ganti rentang waktunya — kalau hasilnya langsung berantakan, berarti '
        'Anda menemukan kebetulan, bukan strategi.<br>'
        '• Hasil per tahun dan rasio Sharpe dihitung dari rentang tanggal sungguhnya, '
        'bukan dari jumlah batang, sehingga tetap sebanding antar rentang waktu.<br>'
        '• Makin pendek rentang waktunya, makin besar peran biaya. Strategi yang terlihat '
        'menguntungkan di grafik harian sering habis dimakan spread di grafik lima menit.<br>'
        '• Data rentang pendek dari Yahoo Finance tidak selalu lengkap dan tidak memuat '
        'harga bid-ask. Untuk rentang menit, anggap hasilnya kasar.<br>'
        '• Dividen tidak dihitung, dan saham yang sudah delisting tidak ada di data. '
        'Keduanya membuat hasil masa lalu terlihat lebih baik dari kenyataan.<br>'
        '• Penurunan terdalam sering lebih penting daripada hasil akhir. Angka −40% berarti '
        'ada masa ketika modal Anda tinggal separuh lebih sedikit. Tanyakan jujur pada diri '
        'sendiri apakah Anda akan bertahan.'
        '</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 3 — BERITA & MAKRO
# ──────────────────────────────────────────────────────────────────────

def halaman_berita():
    st.subheader("Berita & Data Makro")

    tab_berita, tab_makro = st.tabs(["Kabel Berita", "Indikator Ekonomi"])

    with tab_berita:
        a, b = st.columns([3, 1])
        with a:
            lingkup = st.radio("Lingkup", ["Indonesia", "Global", "Semua"],
                               horizontal=True, label_visibility="collapsed")
        with b:
            if st.button("⟳  SEGARKAN", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        if lingkup == "Global":
            umpan = dict(RSS_GLOBAL)
        elif lingkup == "Semua":
            umpan = dict(RSS_INDONESIA, **RSS_GLOBAL)
        else:
            umpan = dict(RSS_INDONESIA)

        berita = ambil_berita(umpan)
        if not berita:
            st.warning("Tidak ada berita yang bisa diambil. Periksa koneksi internet Anda.")
        else:
            for item in berita[:40]:
                waktu = item["waktu"].strftime("%d %b · %H:%M") if item["waktu"] else "—"
                st.markdown(
                    f'<div style="padding:0.45rem 0;border-bottom:1px solid var(--pemisah);">'
                    f'<a class="berita-judul" href="{item["tautan"]}" target="_blank">{item["judul"]}</a>'
                    f'<div class="berita-meta">{item["sumber"]} &nbsp;·&nbsp; {waktu}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with tab_makro:
        st.markdown("**Potret pasar saat ini**")
        df_makro = ambil_kutipan(tuple(MAKRO_PANTAU))
        kolom = st.columns(len(MAKRO_PANTAU))
        for k, (simbol, nama) in zip(kolom, MAKRO_PANTAU.items()):
            with k:
                baris = df_makro[df_makro["Simbol"] == simbol] if not df_makro.empty else pd.DataFrame()
                if baris.empty:
                    kartu(nama, "—", "tidak tersedia")
                else:
                    r = baris.iloc[0]
                    kartu(nama, format_angka(r["Harga"]), f'{r["Persen"]:+.2f}%', warna(r["Persen"]))

        st.divider()
        st.markdown("**Indikator jangka panjang — sumber: Bank Dunia**")

        a, b = st.columns(2)
        with a:
            negara = st.selectbox("Negara", list(NEGARA), format_func=lambda k: NEGARA[k])
        with b:
            indikator = st.selectbox("Indikator", list(INDIKATOR_BANK_DUNIA),
                                     format_func=lambda k: INDIKATOR_BANK_DUNIA[k])

        df_wb = ambil_bank_dunia(negara, indikator)
        if df_wb.empty:
            st.info("Data tidak tersedia untuk kombinasi ini.")
        else:
            fig = go.Figure(go.Scatter(
                x=df_wb["Tahun"], y=df_wb["Nilai"], mode="lines+markers",
                line=dict(color=pal()["aksen"], width=2), marker=dict(size=4),
            ))
            fig.add_hline(y=0, line=dict(color=pal()["kisi2"], width=1))
            fig.update_layout(
                height=380, template=pal()["plotly"],
                paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text=f"{NEGARA[negara]} — {INDIKATOR_BANK_DUNIA[indikator]}",
                           font=dict(size=13, color=pal()["aksen"])),
                font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
            )
            fig.update_xaxes(gridcolor=pal()["kisi"])
            fig.update_yaxes(gridcolor=pal()["kisi"])
            st.plotly_chart(fig, use_container_width=True)

            terbaru = df_wb.iloc[-1]
            st.markdown(
                f'<div class="catatan">Angka terbaru: <b>{terbaru["Nilai"]:.2f}</b> '
                f'pada tahun {int(terbaru["Tahun"])}. '
                f'Data Bank Dunia biasanya tertinggal satu sampai dua tahun dari hari ini.</div>',
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 4 — PORTOFOLIO
# ──────────────────────────────────────────────────────────────────────

def halaman_portofolio():
    st.subheader("Portofolio")

    posisi = st.session_state.portofolio

    with st.expander("Tambah atau hapus posisi", expanded=not posisi):
        a, b, c, d = st.columns([2, 1, 1.2, 1])
        with a:
            simbol = st.text_input("Simbol", placeholder="BBCA.JK")
        with b:
            jumlah = st.number_input("Jumlah", min_value=0.0, step=1.0, format="%.4f")
        with c:
            harga_beli = st.number_input("Harga beli rata-rata", min_value=0.0,
                                         step=1.0, format="%.4f")
        with d:
            st.write("")
            st.write("")
            if st.button("SIMPAN", use_container_width=True):
                if simbol.strip() and jumlah > 0 and harga_beli > 0:
                    posisi.append({
                        "simbol": simbol.strip().upper(),
                        "jumlah": jumlah,
                        "harga_beli": harga_beli,
                        "dicatat": datetime.now().strftime("%Y-%m-%d"),
                    })
                    simpan_json(BERKAS_PORTOFOLIO, posisi)
                    st.rerun()
                else:
                    st.warning("Simbol, jumlah, dan harga beli harus diisi.")

        if posisi:
            label = [f'{p["simbol"]} — {p["jumlah"]:g} @ {p["harga_beli"]:,.2f}' for p in posisi]
            buang = st.multiselect("Hapus posisi", list(range(len(posisi))),
                                   format_func=lambda i: label[i],
                                   placeholder="Pilih posisi yang mau dihapus")
            if buang and st.button("HAPUS POSISI TERPILIH"):
                st.session_state.portofolio = [p for i, p in enumerate(posisi) if i not in buang]
                simpan_json(BERKAS_PORTOFOLIO, st.session_state.portofolio)
                st.rerun()

    if not posisi:
        st.info("Belum ada posisi. Tambahkan lewat panel di atas. "
                "Data disimpan lokal di folder data/, tidak dikirim ke mana pun.")
        return

    simbol_unik = tuple(sorted({p["simbol"] for p in posisi}))
    kutipan = ambil_kutipan(simbol_unik)
    if kutipan.empty:
        st.warning("Harga pasar tidak bisa diambil. Periksa koneksi internet Anda.")
        return

    peta_harga = dict(zip(kutipan["Simbol"], kutipan["Harga"]))
    peta_persen = dict(zip(kutipan["Simbol"], kutipan["Persen"]))

    baris = []
    for p in posisi:
        harga_kini = peta_harga.get(p["simbol"])
        if harga_kini is None:
            continue
        modal = p["jumlah"] * p["harga_beli"]
        nilai = p["jumlah"] * harga_kini
        laba = nilai - modal
        baris.append({
            "Simbol": p["simbol"],
            "Jumlah": p["jumlah"],
            "Harga beli": p["harga_beli"],
            "Harga kini": harga_kini,
            "Modal": modal,
            "Nilai kini": nilai,
            "Laba/Rugi": laba,
            "Persen": (laba / modal * 100) if modal else 0.0,
            "Hari ini %": peta_persen.get(p["simbol"], 0.0),
        })

    if not baris:
        st.warning("Tidak ada posisi yang harganya berhasil diambil.")
        return

    df = pd.DataFrame(baris)
    total_modal = float(df["Modal"].sum())
    total_nilai = float(df["Nilai kini"].sum())
    total_laba = total_nilai - total_modal
    total_persen = (total_laba / total_modal * 100) if total_modal else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kartu("Total modal", format_angka(total_modal))
    with k2:
        kartu("Nilai sekarang", format_angka(total_nilai))
    with k3:
        kartu("Laba / rugi", f"{total_laba:+,.2f}", f"{total_persen:+.2f}%", warna(total_laba))
    with k4:
        kartu("Jumlah posisi", str(len(df)))

    st.markdown("**Rincian posisi**")
    tampil = pd.DataFrame({
        "Simbol": df["Simbol"],
        "Jumlah": df["Jumlah"].map(lambda x: f"{x:g}"),
        "Harga beli": df["Harga beli"].map(format_angka),
        "Harga kini": df["Harga kini"].map(format_angka),
        "Modal": df["Modal"].map(format_angka),
        "Nilai kini": df["Nilai kini"].map(format_angka),
        "Laba/Rugi": df["Laba/Rugi"].map(lambda x: f"{x:+,.2f}"),
        "Persen": df["Persen"].map(lambda x: f"{x:+.2f}%"),
        "Hari ini %": df["Hari ini %"].map(lambda x: f"{x:+.2f}%"),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True)

    kiri, kanan = st.columns(2)
    with kiri:
        fig = go.Figure(go.Pie(
            labels=df["Simbol"], values=df["Nilai kini"], hole=0.55,
            marker=dict(colors=[pal()[k] for k in ("aksen","biru","naik","ungu",
                                                       "kuning","turun","teal","coklat")]),
            textinfo="label+percent", textfont=dict(size=10),
        ))
        fig.update_layout(
            height=340, template=pal()["plotly"], showlegend=False,
            paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["latar"],
            margin=dict(l=10, r=10, t=40, b=10),
            title=dict(text="Alokasi berdasarkan nilai", font=dict(size=12, color=pal()["aksen"])),
            font=dict(family="Consolas, monospace", color=pal()["teks2"]),
        )
        st.plotly_chart(fig, use_container_width=True)

    with kanan:
        urut = df.sort_values("Laba/Rugi")
        fig = go.Figure(go.Bar(
            x=urut["Laba/Rugi"], y=urut["Simbol"], orientation="h",
            marker_color=[pal()["turun"] if v < 0 else pal()["naik"] for v in urut["Laba/Rugi"]],
        ))
        fig.update_layout(
            height=340, template=pal()["plotly"],
            paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
            margin=dict(l=10, r=10, t=40, b=10),
            title=dict(text="Laba / rugi per posisi", font=dict(size=12, color=pal()["aksen"])),
            font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
        )
        fig.update_xaxes(gridcolor=pal()["kisi"], zerolinecolor=pal()["kisi2"])
        fig.update_yaxes(gridcolor=pal()["kisi"])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="catatan">'
        'Perhitungan ini mengabaikan biaya transaksi, pajak, dan dividen — '
        'jadi angka sesungguhnya di rekening Anda akan sedikit berbeda. '
        'Semua nilai memakai mata uang asli tiap simbol dan <b>tidak</b> dikonversi, '
        'jadi menjumlahkan rupiah dengan dolar tidak bermakna. '
        'Pisahkan portofolio per mata uang bila perlu.'
        '</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — LAPORAN PDF
# ──────────────────────────────────────────────────────────────────────

def _teks_pdf(s) -> str:
    """FPDF dengan font bawaan hanya paham Latin-1. Ganti yang di luar itu."""
    ganti = {"—": "-", "–": "-", "≥": ">=", "≤": "<=", "·": "-", "▲": "^", "▼": "v",
             "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "→": "->", "₿": "BTC"}
    s = str(s)
    for a, b in ganti.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def buat_pdf(judul: str, subjudul: str, bagian: list, penyusun: str) -> bytes:
    """
    bagian = daftar dari:
      ("teks",  isi)
      ("kunci", [(label, nilai), ...])
      ("tabel", (judul, [kolom...], [[baris...], ...]))
    """
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Kop
    pdf.set_fill_color(224, 139, 42)
    pdf.rect(0, 0, 210, 3, "F")
    pdf.set_font("helvetica", "B", 17)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(6)
    pdf.cell(0, 9, _teks_pdf(judul), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, _teks_pdf(subjudul), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, _teks_pdf(f"Disusun {datetime.now():%d %B %Y, %H:%M} - {penyusun}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    for jenis, isi in bagian:
        if jenis == "teks":
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 5.2, _teks_pdf(isi))
            pdf.ln(3)

        elif jenis == "kunci":
            pdf.set_font("helvetica", "", 9.5)
            for label, nilai in isi:
                pdf.set_text_color(120, 120, 120)
                pdf.cell(70, 6, _teks_pdf(label), border=0)
                pdf.set_text_color(30, 30, 30)
                pdf.set_font("helvetica", "B", 9.5)
                pdf.cell(0, 6, _teks_pdf(nilai), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("helvetica", "", 9.5)
            pdf.ln(3)

        elif jenis == "tabel":
            judul_tabel, kolom, baris = isi
            if judul_tabel:
                pdf.set_font("helvetica", "B", 11)
                pdf.set_text_color(224, 139, 42)
                pdf.cell(0, 7, _teks_pdf(judul_tabel), new_x="LMARGIN", new_y="NEXT")
            if not kolom:
                continue
            lebar = (210 - 20) / len(kolom)
            pdf.set_font("helvetica", "B", 7.6)
            pdf.set_fill_color(245, 245, 245)
            pdf.set_text_color(70, 70, 70)
            for c in kolom:
                pdf.cell(lebar, 6.5, _teks_pdf(c)[:22], border=0, fill=True, align="L")
            pdf.ln()
            pdf.set_font("helvetica", "", 7.6)
            pdf.set_text_color(40, 40, 40)
            for i, r in enumerate(baris[:45]):
                if pdf.get_y() > 268:
                    pdf.add_page()
                pdf.set_fill_color(252, 252, 252)
                for sel in r:
                    pdf.cell(lebar, 5.6, _teks_pdf(sel)[:22], border=0,
                             fill=(i % 2 == 0), align="L")
                pdf.ln()
            if len(baris) > 45:
                pdf.set_text_color(140, 140, 140)
                pdf.cell(0, 5, _teks_pdf(f"...dan {len(baris) - 45} baris lainnya"),
                         new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

    # Kaki halaman
    pdf.set_y(-16)
    pdf.set_font("helvetica", "I", 7.5)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, _teks_pdf(
        "Dibuat dengan Terminal Ringan. Data berasal dari sumber terbuka dan dapat "
        "tertunda. Dokumen ini bukan nasihat investasi."))

    keluaran = pdf.output()
    return bytes(keluaran)


def halaman_laporan():
    st.subheader("Laporan PDF")
    st.markdown(
        '<div class="catatan">Cetak isi terminal jadi dokumen rapi — berguna untuk arsip '
        'pribadi, laporan berkala, atau kalau Anda memakai aplikasi ini melayani orang '
        'lain.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    a, b = st.columns(2)
    with a:
        jenis = st.selectbox("Isi laporan",
                             ["Portofolio", "Jurnal Transaksi", "Dompet Kripto", "Watchlist"])
    with b:
        penyusun = st.text_input("Disusun oleh", value=PROFIL["nama"])

    catatan = st.text_area("Catatan pembuka (boleh dikosongkan)",
                           placeholder="Ringkasan singkat, konteks, atau pesan untuk pembaca.",
                           height=90)

    bagian = []
    if catatan.strip():
        bagian.append(("teks", catatan.strip()))

    subjudul = ""

    if jenis == "Portofolio":
        posisi = st.session_state.portofolio
        if not posisi:
            st.info("Portofolio masih kosong. Isi dulu di halaman Portofolio.")
            return
        kutipan = ambil_kutipan(tuple(sorted({p["simbol"] for p in posisi})))
        peta = dict(zip(kutipan["Simbol"], kutipan["Harga"])) if not kutipan.empty else {}

        baris, modal_total, nilai_total = [], 0.0, 0.0
        for p in posisi:
            kini = peta.get(p["simbol"])
            modal = p["jumlah"] * p["harga_beli"]
            nilai = p["jumlah"] * kini if kini else float("nan")
            modal_total += modal
            if kini:
                nilai_total += nilai
            baris.append([
                p["simbol"], f'{p["jumlah"]:g}', format_angka(p["harga_beli"]),
                format_angka(kini) if kini else "-", format_angka(modal, 0),
                format_angka(nilai, 0) if kini else "-",
                f"{nilai - modal:+,.0f}" if kini else "-",
            ])

        laba = nilai_total - modal_total
        subjudul = f"Ringkasan portofolio - {len(posisi)} posisi"
        bagian.append(("kunci", [
            ("Jumlah posisi", str(len(posisi))),
            ("Total modal", format_angka(modal_total, 0)),
            ("Nilai sekarang", format_angka(nilai_total, 0)),
            ("Laba / rugi", f"{laba:+,.0f}"),
            ("Persentase", f"{laba / modal_total * 100:+.2f}%" if modal_total else "-"),
        ]))
        bagian.append(("tabel", ("Rincian posisi",
                                 ["Simbol", "Jumlah", "Hrg beli", "Hrg kini",
                                  "Modal", "Nilai", "Laba/Rugi"], baris)))

    elif jenis == "Jurnal Transaksi":
        jurnal = st.session_state.jurnal
        if not jurnal:
            st.info("Jurnal masih kosong. Isi dulu di halaman Jurnal.")
            return
        tutup = pasangkan_transaksi(jurnal)
        subjudul = f"Jurnal transaksi - {len(jurnal)} catatan"

        if not tutup.empty:
            menang = tutup[tutup["Laba"] > 0]
            bagian.append(("kunci", [
                ("Transaksi tertutup", str(len(tutup))),
                ("Tingkat menang", f"{len(menang) / len(tutup) * 100:.0f}%"),
                ("Laba bersih", f'{tutup["Laba"].sum():+,.0f}'),
                ("Rata-rata menang",
                 f'{menang["Laba"].mean():+,.0f}' if len(menang) else "-"),
            ]))
            bagian.append(("tabel", ("Transaksi tertutup",
                                     ["Simbol", "Masuk", "Keluar", "Hrg beli",
                                      "Hrg jual", "Laba", "Persen"],
                                     [[r["Simbol"], r["Masuk"], r["Keluar"],
                                       format_angka(r["Harga beli"]),
                                       format_angka(r["Harga jual"]),
                                       f'{r["Laba"]:+,.0f}', f'{r["Persen"]:+.2f}%']
                                      for _, r in tutup.iterrows()])))

        bagian.append(("tabel", ("Seluruh catatan",
                                 ["Tanggal", "Aksi", "Simbol", "Jumlah", "Harga", "Suasana"],
                                 [[c["tanggal"], c["aksi"], c["simbol"],
                                   f'{c["jumlah"]:,.0f}', format_angka(c["harga"]),
                                   c.get("emosi", "-")]
                                  for c in sorted(jurnal, key=lambda x: x["tanggal"],
                                                  reverse=True)])))

    elif jenis == "Dompet Kripto":
        dompet = st.session_state.dompet
        if not dompet:
            st.info("Belum ada alamat dompet. Tambahkan dulu di halaman Dompet Kripto.")
            return
        subjudul = f"Dompet kripto - {len(dompet)} alamat"
        harga = ambil_harga_koin(tuple(sorted({JARINGAN[d["jaringan"]]["koin"]
                                               for d in dompet})))
        baris, total = [], 0.0
        for d in dompet:
            j = JARINGAN[d["jaringan"]]
            h = ambil_saldo_dompet(d["jaringan"], d["alamat"])
            if h.get("galat"):
                baris.append([d["jaringan"], d["alamat"][:24] + "...", "-", "-", h["galat"][:20]])
                continue
            usd = h["saldo"] * float(harga.get(j["koin"], {}).get("usd", 0) or 0)
            total += usd
            baris.append([d["jaringan"], d["alamat"][:24] + "...",
                          f'{h["saldo"]:,.6f} {j["kode"]}', format_ringkas(usd), "OK"])
        bagian.append(("kunci", [("Jumlah alamat", str(len(dompet))),
                                 ("Total nilai koin utama", format_ringkas(total))]))
        bagian.append(("tabel", ("Alamat yang dipantau",
                                 ["Jaringan", "Alamat", "Saldo", "Nilai", "Status"], baris)))
        bagian.append(("teks", "Hanya saldo koin utama tiap jaringan yang dijumlahkan. "
                               "Token lain tidak termasuk dalam total."))

    else:  # Watchlist
        wl = st.session_state.watchlist
        if not wl:
            st.info("Watchlist masih kosong.")
            return
        df = ambil_kutipan(tuple(wl))
        if df.empty:
            st.warning("Harga tidak bisa diambil sekarang.")
            return
        subjudul = f"Watchlist - {len(df)} simbol"
        bagian.append(("kunci", [
            ("Simbol dipantau", str(len(df))),
            ("Menguat hari ini", str(int((df["Persen"] > 0).sum()))),
            ("Melemah hari ini", str(int((df["Persen"] < 0).sum()))),
        ]))
        bagian.append(("tabel", ("Harga terakhir",
                                 ["Simbol", "Harga", "Perubahan", "Persen"],
                                 [[r["Simbol"], format_angka(r["Harga"]),
                                   f'{r["Perubahan"]:+,.2f}', f'{r["Persen"]:+.2f}%']
                                  for _, r in df.iterrows()])))

    st.divider()
    if st.button("BUAT PDF", use_container_width=True):
        try:
            isi = buat_pdf(f"Laporan {jenis}", subjudul, bagian, penyusun or "-")
        except ImportError:
            st.error("Pustaka **fpdf2** belum terpasang. Tutup aplikasi, lalu jalankan "
                     "`MULAI.cmd` sekali lagi — pustaka yang kurang akan dipasang otomatis.")
            return
        except Exception as e:
            st.error(f"Gagal membuat PDF: {e}")
            return

        st.success(f"PDF siap — {len(isi) / 1024:.0f} KB")
        st.download_button(
            "UNDUH PDF",
            isi,
            file_name=f"laporan-{jenis.lower().replace(' ', '-')}-"
                      f"{datetime.now():%Y%m%d-%H%M}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 5 — TENTANG
# ──────────────────────────────────────────────────────────────────────

def halaman_tentang():
    st.subheader("Tentang")
    tab_aplikasi, tab_pembuat, tab_versi = st.tabs(["Aplikasi", "Pembuat", "Pembaruan"])

    with tab_pembuat:
        bagian_pembuat()

    with tab_aplikasi:
        bagian_aplikasi()

    with tab_versi:
        bagian_pembaruan()


def bagian_pembaruan():
    a, b = st.columns([1, 1])
    with a:
        kartu("VERSI TERPASANG", VERSI, "di komputer ini")
    with b:
        if st.button("⟳  PERIKSA PEMBARUAN", use_container_width=True, key="cek_versi"):
            cek_pembaruan.clear()
            st.rerun()

    otomatis = st.toggle(
        "Periksa pembaruan otomatis saat aplikasi dibuka",
        value=st.session_state.get("cek_otomatis", True),
        key="saklar_cek",
        help="Kalau dimatikan, aplikasi tidak menghubungi internet untuk urusan "
             "pembaruan sama sekali. Anda tetap bisa memeriksa manual kapan saja.")
    if otomatis != st.session_state.get("cek_otomatis", True):
        st.session_state.cek_otomatis = otomatis
        simpan_pengaturan()
        st.rerun()

    if not otomatis:
        st.markdown(
            '<div class="catatan">Pemeriksaan otomatis dimatikan. Aplikasi tidak '
            'menghubungi GitHub sampai Anda menekan tombol di atas.</div>',
            unsafe_allow_html=True,
        )
        if not st.session_state.get("periksa_manual"):
            if st.button("PERIKSA SEKARANG (SEKALI INI)", key="manual_sekali"):
                st.session_state.periksa_manual = True
                st.rerun()
            st.divider()
            bagian_catatan_pembaruan()
            return

    manifes = cek_pembaruan(URL_RILIS)

    if manifes.get("galat"):
        st.markdown(
            f'<div class="kartu"><div class="label">TIDAK BISA MEMERIKSA</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.3rem;">'
            f'{manifes["galat"]}<br><br>Ini bukan masalah besar — aplikasi tetap berjalan '
            f'normal. Anda juga selalu bisa mengunduh versi terbaru secara manual dari '
            f'halaman rilis.</div></div>',
            unsafe_allow_html=True,
        )
    elif not manifes.get("lebih_baru"):
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--naik);">'
            f'<div class="label">SUDAH VERSI TERBARU</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.3rem;">'
            f'Versi terbaru yang tersedia adalah {manifes.get("versi")}, sama dengan yang '
            f'terpasang di sini.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
            f'<div class="label">TERSEDIA PEMBARUAN</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:var(--aksen);'
            f'margin:0.25rem 0;">{VERSI} → {manifes.get("versi")}</div>'
            f'<div style="color:var(--teks3);font-size:0.72rem;">'
            f'dirilis {manifes.get("tanggal", "—")}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;line-height:1.7;'
            f'margin-top:0.6rem;white-space:pre-line;">'
            f'{manifes.get("catatan", "Tidak ada keterangan perubahan.")}</div></div>',
            unsafe_allow_html=True,
        )

        berkas = manifes.get("berkas", {})
        if berkas:
            st.dataframe(pd.DataFrame({
                "Berkas": list(berkas),
                "Diizinkan": ["ya" if n in BERKAS_BOLEH_DIPERBARUI else "TIDAK"
                              for n in berkas],
                "Sidik jari (SHA-256)": [str(i.get("sha256", ""))[:16] + "…"
                                         for i in berkas.values()],
            }), use_container_width=True, hide_index=True)

        setuju = st.checkbox("Saya mengerti berkas aplikasi akan diganti, dan salinan "
                             "versi sekarang akan disimpan di folder cadangan.",
                             key="setuju_perbarui")
        if st.button("UNDUH DAN PASANG PEMBARUAN", use_container_width=True,
                     disabled=not setuju, key="pasang_perbarui"):
            with st.spinner("Mengunduh dan memeriksa sidik jari berkas…"):
                berhasil, pesan = terapkan_pembaruan(manifes)
            if berhasil:
                st.success(pesan)
                st.info("**Tutup aplikasi lalu jalankan MULAI.cmd lagi** supaya versi baru "
                        "benar-benar dipakai. Data Anda di folder data/ tidak tersentuh.")
            else:
                st.error(pesan)

    # ── Kembalikan versi sebelumnya ───────────────────────────────────
    cadangan = daftar_cadangan()
    if cadangan:
        st.divider()
        st.markdown("**Kembali ke versi sebelumnya**")
        pilih = st.selectbox("Salinan tersimpan", cadangan,
                             format_func=lambda p: p.name, key="pilih_cadangan")
        if st.button("KEMBALIKAN VERSI INI", key="pulihkan"):
            berhasil, pesan = kembalikan_cadangan(pilih)
            (st.success if berhasil else st.error)(pesan)
            if berhasil:
                st.info("Tutup aplikasi lalu jalankan MULAI.cmd lagi.")

    st.divider()
    bagian_catatan_pembaruan()


def bagian_catatan_pembaruan():
    st.markdown(
        f'<div class="catatan">'
        f'<b>Cara pembaruan ini bekerja, selengkapnya.</b><br><br>'
        f'<b>Yang berjalan sendiri:</b> tiap kali aplikasi dibuka, ia mengambil satu berkas '
        f'keterangan versi dari <code>{URL_RILIS.split("/")[2]}</code> — isinya hanya nomor '
        f'versi, tanggal, catatan perubahan, dan sidik jari. Hasilnya disimpan enam jam, '
        f'jadi tidak diambil berulang-ulang. Karena ini permintaan lewat internet, '
        f'<b>GitHub dapat melihat alamat IP Anda</b>, sebagaimana setiap kali Anda membuka '
        f'situs mana pun. Aplikasi ini tidak mengirimkan data Anda — tidak portofolio, tidak '
        f'watchlist, tidak jurnal. Kalau Anda tidak menghendakinya, matikan lewat saklar di '
        f'atas.<br><br>'
        f'<b>Yang menunggu persetujuan Anda:</b> pengunduhan kode aplikasi dan penggantian '
        f'berkas. Keduanya hanya terjadi setelah Anda mencentang persetujuan dan menekan '
        f'tombol. Tidak pernah otomatis.<br><br>'
        f'Tiap berkas yang diunduh dicocokkan <b>sidik jari SHA-256</b>-nya dengan yang '
        f'diumumkan. Kalau meleset satu bit pun, pembaruan dibatalkan. Semua berkas juga '
        f'diunduh dan diperiksa lebih dulu sebelum ada satu pun yang ditulis, supaya '
        f'aplikasi tidak pernah tertinggal dalam keadaan setengah diperbarui.<br><br>'
        f'Hanya tiga berkas yang boleh diganti: <code>terminal_ringan.py</code>, '
        f'<code>requirements.txt</code>, dan <code>BACA-DULU.md</code>. Folder '
        f'<code>data/</code> berisi watchlist, portofolio, jurnal, dan pengaturan Anda — '
        f'tidak pernah disentuh pembaruan.<br><br>'
        f'<b class="turun">Yang jujur perlu Anda sadari.</b> Saluran pembaruan adalah juga '
        f'jalan masuk. Siapa pun yang menguasai akun rilis bisa mengirim kode apa pun ke '
        f'seluruh pemakai. Sidik jari melindungi dari penyusup di tengah jalan, tetapi tidak '
        f'melindungi dari akun yang jatuh ke tangan lain. Kalau Anda yang menerbitkan '
        f'aplikasi ini, nyalakan autentikasi dua langkah di akun GitHub Anda — itu satu '
        f'langkah yang paling menentukan.'
        f'</div>',
        unsafe_allow_html=True,
    )


def bagian_pembuat():
    p = PROFIL

    kiri, kanan = st.columns([1, 2.6])
    with kiri:
        st.markdown(
            f'<img src="{p["foto"]}" alt="Foto {p["nama"]}" '
            f'style="width:100%;max-width:210px;border-radius:4px;'
            f'border:1px solid var(--garis);filter:saturate(0.92);">',
            unsafe_allow_html=True,
        )
    with kanan:
        lencana = "".join(
            f'<span style="border:1px solid var(--tbl_garis);color:var(--aksen);background:var(--tbl_latar);'
            f'padding:0.12rem 0.5rem;border-radius:2px;font-size:0.68rem;'
            f'letter-spacing:0.08em;margin-right:0.35rem;display:inline-block;'
            f'margin-bottom:0.3rem;">{x.upper()}</span>'
            for x in p["peran"]
        )
        st.markdown(
            f'<div style="padding-top:0.2rem;">'
            f'<div style="font-size:1.35rem;font-weight:700;color:var(--terang);">{p["nama"]}</div>'
            f'<div style="color:var(--aksen);font-size:0.92rem;font-style:italic;'
            f'margin:0.25rem 0 0.7rem 0;">{p["moto"]}</div>'
            f'<div>{lencana}</div>'
            f'<div style="color:var(--teks2);font-size:0.84rem;line-height:1.7;'
            f'margin-top:0.7rem;">{p["tentang"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("**Portofolio proyek**")

    for i in range(0, len(p["proyek"]), 2):
        kolom = st.columns(2)
        for k, (nama, ket, url) in zip(kolom, p["proyek"][i:i + 2]):
            with k:
                tautan = (f'<div style="margin-top:0.4rem;"><a href="{url}" target="_blank" '
                          f'style="color:var(--biru);font-size:0.72rem;text-decoration:none;">'
                          f'{url.replace("https://", "")} ↗</a></div>') if url else ""
                st.markdown(
                    f'<div class="kartu" style="min-height:118px;">'
                    f'<div style="color:var(--aksen);font-weight:600;font-size:0.9rem;'
                    f'letter-spacing:0.04em;">{nama}</div>'
                    f'<div style="color:var(--teks6);font-size:0.75rem;line-height:1.6;'
                    f'margin-top:0.3rem;">{ket}</div>'
                    f'{tautan}</div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    st.markdown("**Layanan**")
    kolom = st.columns(len(p["layanan"]))
    for k, (nama, ket) in zip(kolom, p["layanan"]):
        with k:
            st.markdown(
                f'<div class="kartu" style="min-height:110px;">'
                f'<div style="color:var(--terang);font-weight:600;font-size:0.82rem;">{nama}</div>'
                f'<div style="color:var(--diam);font-size:0.72rem;line-height:1.6;'
                f'margin-top:0.35rem;">{ket}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    kartu_donasi()

    st.divider()
    tautan = " &nbsp;·&nbsp; ".join(
        f'<a href="{url}" target="_blank" style="color:var(--aksen);text-decoration:none;">{nama} ↗</a>'
        for nama, url in p["tautan"]
    )
    st.markdown(f'<div style="font-size:0.82rem;">{tautan}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="catatan" style="margin-top:1rem;">'
        'Terminal Ringan dibangun sebagai proyek pribadi — sebuah percobaan menjawab '
        'pertanyaan sederhana: seberapa jauh sebuah terminal data keuangan bisa berjalan '
        'tanpa langganan, tanpa kredit, dan tanpa satu pun API berbayar.'
        '</div>',
        unsafe_allow_html=True,
    )


def bagian_aplikasi():
    st.markdown("""
**Terminal Ringan** adalah versi sederhana dari terminal data keuangan, dibuat untuk
dijalankan sendiri di komputer Anda. Tidak ada langganan, tidak ada kredit, tidak ada
akun yang perlu didaftarkan.

#### Dari mana datanya?

| Yang Anda lihat | Sumber | Biaya |
|---|---|---|
| Harga saham, kripto, indeks, komoditas | Yahoo Finance | Gratis, tanpa API key |
| Berita pasar | RSS CNBC Indonesia, Kontan, Bisnis.com, Yahoo, CNBC | Gratis |
| Indikator ekonomi | API Bank Dunia | Gratis, tanpa API key |
| Watchlist & portofolio Anda | Folder `data/` di komputer Anda | — |

#### Apa yang sengaja tidak ada

Terminal komersial menawarkan puluhan modul. Yang ini hanya empat. Itu keputusan sadar,
bukan kekurangan: modul yang jarang dipakai hanya menambah kebingungan dan titik kegagalan.

Tidak ada di sini: pengiriman order ke broker, agen AI, backtesting, dan data privat
berbayar. Tiga yang pertama bisa ditambahkan nanti kalau memang dibutuhkan. Yang terakhir
memang tidak mungkin gratis.

#### Batasan yang jujur

- Harga dari Yahoo Finance **tertunda**, biasanya 15 sampai 20 menit untuk saham.
  Cukup untuk memantau, tidak cukup untuk trading cepat.
- Yahoo Finance adalah sumber tak resmi. Sewaktu-waktu formatnya berubah dan aplikasi ini
  perlu disesuaikan.
- Data Bank Dunia tertinggal satu sampai dua tahun.
- Tidak ada apa pun di sini yang merupakan nasihat investasi.

#### Menambah sendiri

Seluruh aplikasi ada dalam satu berkas `terminal_ringan.py`. Daftar simbol, sumber berita,
dan indikator ekonomi ada di bagian **PENGATURAN DASAR** paling atas — ubah di sana,
simpan berkasnya, lalu tekan tombol muat ulang di browser.
    """)


# ──────────────────────────────────────────────────────────────────────
#  KERANGKA UTAMA
# ──────────────────────────────────────────────────────────────────────

def main():
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = muat_json(BERKAS_WATCHLIST, list(WATCHLIST_AWAL))
    if "portofolio" not in st.session_state:
        st.session_state.portofolio = muat_json(BERKAS_PORTOFOLIO, [])
    if "dompet" not in st.session_state:
        st.session_state.dompet = muat_json(BERKAS_DOMPET, [])
    if "peringatan" not in st.session_state:
        st.session_state.peringatan = muat_json(BERKAS_PERINGATAN, [])
    if "jurnal" not in st.session_state:
        st.session_state.jurnal = muat_json(BERKAS_JURNAL, [])

    with st.sidebar:
        st.markdown(
            '<div style="padding:0.4rem 0 1rem 0;">'
            '<div style="color:var(--aksen);font-weight:700;letter-spacing:0.16em;font-size:1.02rem;">'
            'TERMINAL RINGAN</div>'
            f'<div style="color:var(--teks4);font-size:0.7rem;letter-spacing:0.08em;">'
            f'DATA TERBUKA · v{VERSI}</div></div>',
            unsafe_allow_html=True,
        )

        # Pemberitahuan versi baru, tanpa mengganggu.
        # Hanya dijalankan kalau pemeriksaan otomatis dinyalakan — lihat
        # Tentang → Pembaruan untuk mematikannya.
        info_versi = cek_pembaruan(URL_RILIS) if st.session_state.get("cek_otomatis", True) else {}
        if info_versi.get("lebih_baru"):
            st.markdown(
                f'<div class="kartu" style="border-left:2px solid var(--aksen);'
                f'padding:0.5rem 0.6rem;margin-bottom:0.5rem;">'
                f'<div class="label">VERSI BARU TERSEDIA</div>'
                f'<div style="color:var(--aksen);font-weight:700;font-size:0.9rem;">'
                f'{info_versi.get("versi")}</div>'
                f'<div style="color:var(--teks4);font-size:0.66rem;">'
                f'buka Tentang → Pembaruan</div></div>',
                unsafe_allow_html=True,
            )

        gelap = st.session_state.tema == "gelap"
        if st.button("☀  MODE TERANG" if gelap else "☾  MODE GELAP",
                     use_container_width=True, key="tukar_tema"):
            st.session_state.tema = "terang" if gelap else "gelap"
            simpan_pengaturan()
            st.rerun()
        halaman = st.radio(
            "Menu",
            ["Pasar", "Grafik", "Screener", "Fundamental", "Backtest",
             "Kalkulator", "Berita & Makro", "Portofolio", "Dompet Kripto",
             "Peringatan", "Jurnal", "Laporan", "Tentang"],
            label_visibility="collapsed",
        )
        st.divider()
        st.markdown(
            '<div class="catatan">'
            f'{len(st.session_state.watchlist)} simbol dipantau<br>'
            f'{len(st.session_state.portofolio)} posisi tercatat<br><br>'
            'Data tersimpan lokal di folder <code>data/</code>.<br><br>'
            f'Dibuat oleh<br><b style="color:var(--teks6);">{PROFIL["nama"]}</b><br>'
            f'<a href="{PROFIL["profil_web"]}" target="_blank" '
            f'style="color:var(--aksen);text-decoration:none;">idcrypt.xyz ↗</a>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        kartu_donasi(ringkas=True)

    kop_halaman()

    if halaman == "Pasar":
        halaman_pasar()
    elif halaman == "Grafik":
        halaman_grafik()
    elif halaman == "Screener":
        halaman_screener()
    elif halaman == "Fundamental":
        halaman_fundamental()
    elif halaman == "Backtest":
        halaman_backtest()
    elif halaman == "Kalkulator":
        halaman_kalkulator()
    elif halaman == "Berita & Makro":
        halaman_berita()
    elif halaman == "Portofolio":
        halaman_portofolio()
    elif halaman == "Dompet Kripto":
        halaman_dompet()
    elif halaman == "Peringatan":
        halaman_peringatan()
    elif halaman == "Jurnal":
        halaman_jurnal()
    elif halaman == "Laporan":
        halaman_laporan()
    else:
        halaman_tentang()


if __name__ == "__main__":
    main()
