# -*- coding: utf-8 -*-
"""
Terminal Investasi
Terminal data keuangan sederhana dalam enam bahasa, tanpa kredit dan tanpa langganan.

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
    "GC=F": "mk_emas",
    "CL=F": "mk_minyak",
    "SI=F": "mk_perak",
    "DX-Y.NYB": "mk_dolar",
    "^TNX": "mk_obligasi",
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
    "DX-Y.NYB": "mk_dolar",
    "GC=F": "mk_emas",
    "CL=F": "mk_minyak",
    "BTC-USD": "Bitcoin",
}

JUMLAH_KRIPTO = 12  # berapa koin teratas yang ditampilkan di Denyut Kripto

# ── Ikhtisar lintas aset ──────────────────────────────────────────────
# Sengaja pendek. Gunanya menjawab "pasar sedang ke mana" dalam satu layar,
# bukan menampung segalanya — untuk itu sudah ada tab masing-masing.
IKHTISAR_PANTAU = {
    "^JKSE": "IHSG",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "GC=F": "mk_emas",
    "CL=F": "mk_minyak",
    "USDIDR=X": "USD / IDR",
    "DX-Y.NYB": "mk_dolar",
}

# ── Emas ──────────────────────────────────────────────────────────────
# Harga emas dunia dikutip dalam dolar per troy ounce. Angka di bawah ini
# yang mengubahnya menjadi satuan yang dipakai orang sehari-hari: gram.
GRAM_PER_OUNCE = 31.1034768
SIMBOL_EMAS = "GC=F"          # kontrak berjangka emas, dolar per troy ounce
SIMBOL_PERAK = "SI=F"
SIMBOL_KURS = "USDIDR=X"

# Berat yang lazim diperjualbelikan di Indonesia, dalam gram.
BERAT_LAZIM = [0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 25.0, 50.0, 100.0]

# Ambang zakat. Nisab emas 85 gram berasal dari 20 dinar, nisab perak 595
# gram dari 200 dirham. Kadarnya 2,5% — seperempat dari sepersepuluh.
NISAB_EMAS_GRAM = 85.0
NISAB_PERAK_GRAM = 595.0
KADAR_ZAKAT = 0.025
HARI_HAUL = 354               # satu tahun hijriah, bukan 365

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

# Nilainya kunci terjemahan, bukan teks jadi — dipakai lewat t() saat tampil.
SEBUTAN_FNG = {
    "Extreme Fear": "fng_sangat_takut",
    "Fear": "fng_takut",
    "Neutral": "fng_netral",
    "Greed": "fng_serakah",
    "Extreme Greed": "fng_sangat_serakah",
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
    "NY.GDP.MKTP.KD.ZG": "ind_pdb",
    "FP.CPI.TOTL.ZG": "ind_inflasi",
    "SL.UEM.TOTL.ZS": "ind_pengangguran",
    "NE.EXP.GNFS.ZS": "ind_ekspor",
    "BN.CAB.XOKA.GD.ZS": "ind_transaksi",
}

NEGARA = {
    "IDN": "neg_idn",
    "MYS": "neg_mys",
    "SGP": "neg_sgp",
    "THA": "neg_tha",
    "VNM": "neg_vnm",
    "USA": "neg_usa",
    "CHN": "neg_chn",
    "JPN": "neg_jpn",
}

# Profil pembuat — tampil di halaman Tentang, tab "Pembuat"
PROFIL = {
    "nama": "Hariyanto, S.Sos",
    "moto": {"id": "Mengabdi dengan ilmu, bertumbuh lewat inovasi.",
             "en": "Serving through knowledge, growing through innovation.",
             "ms": "Berkhidmat dengan ilmu, berkembang melalui inovasi.",
             "zh": "以学识服务，以创新成长。",
             "es": "Servir con conocimiento, crecer con innovación.",
             "pt": "Servir com conhecimento, crescer com inovação."},
    "peran": {"id": ["ASN Kepahiang", "Developer", "Kreator Kripto", "YouTuber"],
              "en": ["Civil Servant, Kepahiang", "Developer", "Crypto Creator", "YouTuber"],
              "ms": ["Penjawat Awam Kepahiang", "Pembangun", "Pencipta Kripto", "YouTuber"],
              "zh": ["Kepahiang 县公务员", "开发者", "加密内容创作者", "YouTuber"],
              "es": ["Funcionario en Kepahiang", "Desarrollador", "Creador Cripto", "YouTuber"],
              "pt": ["Servidor Público em Kepahiang", "Desenvolvedor", "Criador Cripto", "YouTuber"]},
    "foto": "https://cdn.lynkid.my.id/profile/01-05-2026/1777639293606_8868403.webp",
    "profil_web": "https://dipayang.idcrypt.xyz/profil",
    "tentang": {
        "id": "Seorang Aparatur Sipil Negara yang percaya bahwa tugas negara dan semangat "
              "berinovasi bisa berjalan beriringan. Di sela pengabdian, saya membangun "
              "aplikasi, mengeksplorasi dunia kripto, dan berbagi lewat konten digital — "
              "karena belajar tidak mengenal batas jabatan. Saat ini sedang menempuh "
              "pendidikan Magister Ekonomi Syariah di IAIN Curup.",
        "en": "A civil servant who believes public duty and the urge to build can run side "
              "by side. Around that service I write applications, explore crypto, and share "
              "through digital content — because learning recognises no rank. Currently "
              "pursuing a master's degree in Islamic Economics at IAIN Curup.",
        "ms": "Seorang penjawat awam yang percaya bahawa tugas negara dan semangat berinovasi "
              "boleh berjalan seiring. Di sela pengabdian, saya membina aplikasi, meneroka "
              "dunia kripto, dan berkongsi melalui kandungan digital — kerana belajar tidak "
              "mengenal batas jawatan. Kini sedang menuntut Sarjana Ekonomi Syariah di "
              "IAIN Curup.",
        "zh": "一名公务员，相信公职与创造的热情可以并行不悖。在服务之余，我编写应用、探索加密世界，"
              "并通过数字内容分享所学——因为学习不分职级。目前正在 IAIN Curup 攻读伊斯兰经济学硕士。",
        "es": "Un funcionario público que cree que el deber público y las ganas de construir "
              "pueden ir de la mano. Alrededor de ese servicio escribo aplicaciones, exploro "
              "el mundo cripto y comparto mediante contenido digital, porque aprender no "
              "entiende de jerarquías. Actualmente curso un máster en Economía Islámica en "
              "IAIN Curup.",
        "pt": "Um servidor público que acredita que o dever público e a vontade de construir "
              "podem caminhar juntos. Em volta desse serviço, escrevo aplicativos, exploro o "
              "mundo cripto e compartilho por meio de conteúdo digital — porque aprender não "
              "reconhece hierarquia. Atualmente cursando mestrado em Economia Islâmica na "
              "IAIN Curup.",
    },
    # Keterangan proyek dan layanan ditulis per bahasa; nama proyek tetap.
    "proyek": [
        ("DIPAYANG",
         {"id": "Sistem digitalisasi pengamanan aset daerah Kabupaten Kepahiang. Objek tesis magister sekaligus inovasi unggulan pemerintah daerah.", "en": "A system for digitising the safeguarding of regional assets in Kepahiang Regency. It is both the subject of my master's thesis and a flagship innovation of the local government.", "ms": "Sistem pendigitalan pengamanan aset daerah Kabupaten Kepahiang. Menjadi objek tesis sarjana sekali gus inovasi utama kerajaan tempatan.", "zh": "Kepahiang 县地方资产保全数字化系统。既是我的硕士论文课题，也是当地政府的重点创新项目。", "es": "Sistema de digitalización para la protección de activos regionales en el distrito de Kepahiang. Es a la vez el tema de mi tesis de máster y una innovación destacada del gobierno local.", "pt": "Sistema de digitalização para a proteção de ativos regionais no distrito de Kepahiang. É ao mesmo tempo tema da minha dissertação de mestrado e uma inovação de destaque do governo local."},
         "https://dipayang.idcrypt.xyz"),
        ("IDCrypt",
         {"id": "Website kripto berbahasa Inggris — edukasi, analisis pasar, dan komunitas investor lokal.", "en": "An English-language crypto site — education, market analysis, and a community of local investors.", "ms": "Laman web kripto berbahasa Inggeris — pendidikan, analisis pasaran, dan komuniti pelabur tempatan.", "zh": "英文加密货币网站——教育内容、市场分析，以及本地投资者社区。", "es": "Sitio de criptomonedas en inglés: formación, análisis de mercado y una comunidad de inversores locales.", "pt": "Site de criptomoedas em inglês — educação, análise de mercado e uma comunidade de investidores locais."},
         "https://idcrypt.xyz"),
        ("Shopping IDCrypt",
         {"id": "Perbandingan harga produk antara Tokopedia dan Shopee — membantu konsumen belanja lebih cerdas.", "en": "Product price comparison between Tokopedia and Shopee, so shoppers can buy more knowingly.", "ms": "Perbandingan harga produk antara Tokopedia dan Shopee — membantu pengguna berbelanja dengan lebih bijak.", "zh": "在 Tokopedia 与 Shopee 之间比较商品价格，帮助消费者买得更明白。", "es": "Comparador de precios entre Tokopedia y Shopee, para que quien compra lo haga con más criterio.", "pt": "Comparador de preços entre Tokopedia e Shopee, para quem compra decidir com mais clareza."},
         "https://shopping.idcrypt.xyz"),
        ("SIPANDAI",
         {"id": "Aplikasi manajemen untuk Badan Kesatuan Bangsa dan Politik Kabupaten Kepahiang.", "en": "A management application for the National Unity and Politics Agency of Kepahiang Regency.", "ms": "Aplikasi pengurusan untuk Badan Perpaduan Negara dan Politik Kabupaten Kepahiang.", "zh": "为Kepahiang 县民族团结与政治局开发的管理应用。", "es": "Aplicación de gestión para la Agencia de Unidad Nacional y Política del distrito de Kepahiang.", "pt": "Aplicativo de gestão para a Agência de Unidade Nacional e Política do distrito de Kepahiang."},
         "https://kphinside.github.io/sipandai-app/"),
        ("KIBAS",
         {"id": "Kebun Induk Berbasis Aplikasi Smart — solusi AppSheet untuk Dinas Pertanian Kabupaten Kepahiang.", "en": "An app-based nursery-garden management system — an AppSheet solution for the Kepahiang Regency Agriculture Office.", "ms": "Sistem pengurusan kebun induk berasaskan aplikasi — penyelesaian AppSheet untuk Jabatan Pertanian Kabupaten Kepahiang.", "zh": "基于应用的母本园管理系统——为Kepahiang 县农业局开发的 AppSheet 方案。", "es": "Sistema de gestión de viveros basado en app: una solución AppSheet para la Oficina de Agricultura del distrito de Kepahiang.", "pt": "Sistema de gestão de viveiros baseado em app — uma solução AppSheet para a Secretaria de Agricultura do distrito de Kepahiang."},
         ""),
        ("BKD Kepahiang",
         {"id": "Pengelolaan website resmi Badan Keuangan Daerah Kabupaten Kepahiang.", "en": "Managing the official website of the Kepahiang Regency Regional Finance Agency.", "ms": "Pengurusan laman web rasmi Badan Kewangan Daerah Kabupaten Kepahiang.", "zh": "负责Kepahiang 县地方财政局官方网站的运营维护。", "es": "Gestión del sitio web oficial de la Agencia de Finanzas Regionales del distrito de Kepahiang.", "pt": "Gestão do site oficial da Agência de Finanças Regionais do distrito de Kepahiang."},
         "https://bkd.kepahiangkab.go.id"),
    ],
    "layanan": [
        ({"id": "Pengembangan aplikasi", "en": "Application development", "ms": "Pembangunan aplikasi", "zh": "应用开发", "es": "Desarrollo de aplicaciones", "pt": "Desenvolvimento de aplicações"},
         {"id": "Website, sistem informasi, dan aplikasi berbasis AppSheet untuk instansi & bisnis.", "en": "Websites, information systems, and AppSheet-based applications for institutions and businesses.", "ms": "Laman web, sistem maklumat, dan aplikasi berasaskan AppSheet untuk institusi & perniagaan.", "zh": "为机构与企业开发网站、信息系统，以及基于 AppSheet 的应用。", "es": "Sitios web, sistemas de información y aplicaciones basadas en AppSheet para instituciones y empresas.", "pt": "Sites, sistemas de informação e aplicações baseadas em AppSheet para instituições e empresas."}),
        ({"id": "Video AI & konten digital", "en": "AI video & digital content", "ms": "Video AI & kandungan digital", "zh": "AI 视频与数字内容", "es": "Vídeo con IA y contenido digital", "pt": "Vídeo com IA e conteúdo digital"},
         {"id": "Produksi konten berbantuan AI — video, narasi, dan materi edukasi digital.", "en": "AI-assisted content production — video, narration, and digital teaching material.", "ms": "Penghasilan kandungan berbantukan AI — video, naratif, dan bahan pendidikan digital.", "zh": "AI 辅助的内容制作——视频、旁白与数字教学素材。", "es": "Producción de contenido asistida por IA: vídeo, narración y material educativo digital.", "pt": "Produção de conteúdo assistida por IA — vídeo, narração e material educativo digital."}),
        ({"id": "Edukasi kripto", "en": "Crypto education", "ms": "Pendidikan kripto", "zh": "加密资产教育", "es": "Formación en cripto", "pt": "Educação em cripto"},
         {"id": "Konsultasi dan konten seputar aset kripto, analisis pasar, dan strategi investasi.", "en": "Consulting and content on crypto assets, market analysis, and investment strategy.", "ms": "Perundingan dan kandungan mengenai aset kripto, analisis pasaran, dan strategi pelaburan.", "zh": "围绕加密资产、市场分析与投资策略的咨询与内容。", "es": "Consultoría y contenido sobre criptoactivos, análisis de mercado y estrategia de inversión.", "pt": "Consultoria e conteúdo sobre criptoativos, análise de mercado e estratégia de investimento."}),
        ({"id": "Produk digital", "en": "Digital products", "ms": "Produk digital", "zh": "数字产品", "es": "Productos digitales", "pt": "Produtos digitais"},
         {"id": "Template, tools, dan produk digital siap pakai tersedia di Lynk.id.", "en": "Templates, tools, and ready-to-use digital products available on Lynk.id.", "ms": "Templat, alat, dan produk digital siap guna tersedia di Lynk.id.", "zh": "模板、工具与即用型数字产品，可在 Lynk.id 获取。", "es": "Plantillas, herramientas y productos digitales listos para usar en Lynk.id.", "pt": "Modelos, ferramentas e produtos digitais prontos para uso no Lynk.id."}),
    ],
    # Cara dukungan. Tiap butir berdiri sendiri — hapus salah satu kalau tidak
    # dipakai, atau tambahkan yang baru dengan pola yang sama.
    "donasi": [
        {
            "layanan": "PayPal",
            "nomor": "idcrypt",
            "nomor_salin": "idcrypt",
            "atas_nama": "Hariyanto",
            "berkas_qris": "aset/paypal.png",
            "keterangan_qris": ("Pindai dengan aplikasi PayPal",
                                "Scan with the PayPal app"),
            "untuk": ("Luar negeri", "International"),
        },
        {
            "layanan": "DANA",
            "nomor": "0852-1493-9989",
            "nomor_salin": "085214939989",
            "atas_nama": "Hariyanto",
            "berkas_qris": "aset/qris.png",
            "keterangan_qris": ("Pindai dengan aplikasi DANA atau kamera ponsel",
                                "Scan with the DANA app or your phone camera"),
            "untuk": ("Dalam negeri", "Indonesia"),
        },
    ],
    "aplikasi": [
        {
                "nama": "Kasir Kita",
                "ket": {
                        "id": "Aplikasi kasir sederhana berbasis web — siap pakai untuk usaha kecil dan menengah.",
                        "en": "A simple web-based point-of-sale app, ready to use for small and medium businesses.",
                        "ms": "Aplikasi kaunter jualan ringkas berasaskan web — sedia guna untuk perniagaan kecil dan sederhana.",
                        "zh": "简易的网页版收银应用，中小商户开箱即用。",
                        "es": "Una aplicación de punto de venta web sencilla, lista para pequeños y medianos negocios.",
                        "pt": "Um aplicativo de PDV web simples, pronto para pequenos e médios negócios."
                },
                "aplikasi": "https://hariyantodipayang.github.io/kasir-kita/",
                "kode": "https://github.com/hariyantodipayang/kasir-kita"
        },
        {
                "nama": "Terminal Investasi",
                "ket": {
                        "id": "Terminal data investasi sederhana, terilhami Bloomberg Terminal dan Fincept Terminal. Aplikasi yang sedang Anda pakai ini.",
                        "en": "A simple investment data terminal, inspired by Bloomberg Terminal and Fincept Terminal. The application you are using right now.",
                        "ms": "Terminal data pelaburan ringkas, diilhamkan oleh Bloomberg Terminal dan Fincept Terminal. Aplikasi yang sedang anda guna ini.",
                        "zh": "一个简易的投资数据终端，灵感来自 Bloomberg Terminal 与 Fincept Terminal。也就是你正在使用的这个应用。",
                        "es": "Un terminal de datos de inversión sencillo, inspirado en Bloomberg Terminal y Fincept Terminal. La aplicación que estás usando ahora.",
                        "pt": "Um terminal de dados de investimento simples, inspirado no Bloomberg Terminal e no Fincept Terminal. O aplicativo que você está usando agora."
                },
                "aplikasi": "",
                "kode": "https://github.com/hariyantodipayang/terminal-investasi"
        }
    ],
    "buku": [
        {
                "judul": "Quantum Apocalypse",
                "ket": {
                        "id": "Panduan satire tentang kripto, keuangan halal, dan teknologi yang akan melahap koin Anda.",
                        "en": "A satirical guide to crypto, halal finance, and the technology that will eat your coins.",
                        "ms": "Panduan satira tentang kripto, kewangan halal, dan teknologi yang akan menelan syiling anda.",
                        "zh": "一本关于加密货币、清真金融，以及那项将吞掉你的币的技术的讽刺指南。",
                        "es": "Una guía satírica sobre cripto, finanzas halal y la tecnología que se comerá tus monedas.",
                        "pt": "Um guia satírico sobre cripto, finanças halal e a tecnologia que vai devorar suas moedas."
                },
                "toko": "Amazon",
                "url": "https://www.amazon.com/dp/B0H9HVCKG5",
                "gratis": False
        },
        {
                "judul": "Cuan Halal dari Bursa Syariah",
                "ket": {
                        "id": "Panduan berinvestasi halal di pasar modal syariah.",
                        "en": "A guide to investing in the Islamic capital market.",
                        "ms": "Panduan melabur secara halal di pasaran modal patuh syariah.",
                        "zh": "在伊斯兰资本市场进行合规投资的指南。",
                        "es": "Una guía para invertir en el mercado de capitales islámico.",
                        "pt": "Um guia para investir no mercado de capitais islâmico."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/ll7vdk1ww1dp",
                "gratis": False
        },
        {
                "judul": "Retakan Fondasi",
                "ket": {
                        "id": "Mengapa sistem ekonomi dunia harus dirombak total — sebelum semuanya terlambat.",
                        "en": "Why the world's economic system needs rebuilding from the ground up, before it is too late.",
                        "ms": "Mengapa sistem ekonomi dunia perlu dirombak sepenuhnya sebelum terlambat.",
                        "zh": "为什么世界经济体系必须彻底重建——趁一切还来得及。",
                        "es": "Por qué el sistema económico mundial debe reconstruirse desde los cimientos, antes de que sea tarde.",
                        "pt": "Por que o sistema econômico mundial precisa ser reconstruído desde a base, antes que seja tarde."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/wo8mk6383mw0",
                "gratis": False
        },
        {
                "judul": "Rahasia Siklus Bitcoin",
                "ket": {
                        "id": "Yang tidak diceritakan para pemengaruh.",
                        "en": "What the influencers leave out.",
                        "ms": "Apa yang tidak diceritakan oleh pempengaruh.",
                        "zh": "那些网红不会告诉你的部分。",
                        "es": "Lo que los influencers no cuentan.",
                        "pt": "O que os influenciadores não contam."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/47g42yq4xy79",
                "gratis": False
        },
        {
                "judul": "Strategi Cerdas di Pi Network",
                "ket": {
                        "id": "Ikut, tunggu, atau tinggalkan?",
                        "en": "Join, wait, or walk away?",
                        "ms": "Sertai, tunggu, atau tinggalkan?",
                        "zh": "参与、观望，还是离开？",
                        "es": "¿Entrar, esperar o marcharse?",
                        "pt": "Entrar, esperar ou sair?"
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/2r1946je0j1j",
                "gratis": False
        },
        {
                "judul": "Masa Depan Pi",
                "ket": {
                        "id": "Tiga skenario besar yang mungkin terjadi.",
                        "en": "Three big scenarios that could play out.",
                        "ms": "Tiga senario besar yang mungkin berlaku.",
                        "zh": "可能发生的三种主要情景。",
                        "es": "Tres grandes escenarios posibles.",
                        "pt": "Três grandes cenários possíveis."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/5j2ook7wl8xy",
                "gratis": False
        },
        {
                "judul": "Ekonomi Pi",
                "ket": {
                        "id": "Jika gratis, kenapa bisa bernilai?",
                        "en": "If it is free, where does the value come from?",
                        "ms": "Jika percuma, mengapa ia boleh bernilai?",
                        "zh": "既然免费，价值从何而来？",
                        "es": "Si es gratis, ¿de dónde sale el valor?",
                        "pt": "Se é grátis, de onde vem o valor?"
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/p2zxv9l1r3k6",
                "gratis": False
        },
        {
                "judul": "Pi Network: Fakta, Ilusi, dan Realita",
                "ket": {
                        "id": "Yang tidak diceritakan.",
                        "en": "The part that does not get told.",
                        "ms": "Yang tidak diceritakan.",
                        "zh": "没有被讲出来的那部分。",
                        "es": "La parte que no se cuenta.",
                        "pt": "A parte que não se conta."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/k954jn8ydy35",
                "gratis": False
        },
        {
                "judul": "Pi Network: Antara Sultan Mendadak & Halu Berjamaah",
                "ket": {
                        "id": "Buku gratis.",
                        "en": "A free book.",
                        "ms": "Buku percuma.",
                        "zh": "免费电子书。",
                        "es": "Un libro gratuito.",
                        "pt": "Um livro gratuito."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/knqe0y1k22mx",
                "gratis": True
        },
        {
                "judul": "Sudah Kenal Bitcoin, Tapi Dompet Masih Tipis?",
                "ket": {
                        "id": "Ini penyebabnya. Buku gratis.",
                        "en": "Here is why. A free book.",
                        "ms": "Inilah puncanya. Buku percuma.",
                        "zh": "原因在这里。免费电子书。",
                        "es": "Aquí está el motivo. Libro gratuito.",
                        "pt": "Eis o motivo. Livro gratuito."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/6km735ekg863",
                "gratis": True
        },
        {
                "judul": "Aplikasi Kasir Offline Lengkap",
                "ket": {
                        "id": "Versi distribusi Kasir Kita — siap pakai tanpa koneksi internet.",
                        "en": "The distributable build of Kasir Kita, usable with no internet connection.",
                        "ms": "Versi edaran Kasir Kita — boleh digunakan tanpa sambungan internet.",
                        "zh": "Kasir Kita 的分发版本，无需联网即可使用。",
                        "es": "La versión distribuible de Kasir Kita, utilizable sin conexión a internet.",
                        "pt": "A versão distribuível do Kasir Kita, utilizável sem conexão à internet."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/9qnmpwg1mg9w",
                "gratis": False
        },
        {
                "judul": "Template Web Desa",
                "ket": {
                        "id": "Template situs web desa siap pakai. Gratis.",
                        "en": "A ready-to-use website template for village administrations. Free.",
                        "ms": "Templat laman web desa sedia guna. Percuma.",
                        "zh": "面向乡村行政的网站模板，开箱即用。免费。",
                        "es": "Una plantilla web lista para administraciones locales. Gratis.",
                        "pt": "Um modelo de site pronto para administrações de vilarejos. Grátis."
                },
                "toko": "Lynk.id",
                "url": "https://lynk.id/agribinka/wxvr8xww4z0j",
                "gratis": True
        }
    ],
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
VERSI = "2.0.0"

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


# ── Bahasa ────────────────────────────────────────────────────────────
# Bahasa Indonesia adalah sumbernya. Kalau sebuah kunci belum diterjemahkan,
# teks Indonesianya yang dipakai — jadi menambah bahasa baru tidak pernah
# membuat aplikasi menampilkan kunci mentah kepada pemakai.

BAHASA = {
    "en": {"_nama": "English"},
    "id": {"_nama": "Bahasa Indonesia"},
    "ms": {"_nama": "Bahasa Melayu"},
    "zh": {"_nama": "简体中文"},
    "es": {"_nama": "Español"},
    "pt": {"_nama": "Português (Brasil)"},
}

# Urutan mundur kalau sebuah kunci belum diterjemahkan. Melayu jatuh ke
# Indonesia karena paling berdekatan; selebihnya ke Inggris, lalu Indonesia.
# Dengan begitu pemakai tidak pernah melihat kunci mentah.
CADANGAN_BAHASA = {
    "en": ("en", "id"),
    "id": ("id", "en"),
    "ms": ("ms", "id", "en"),
    "zh": ("zh", "en", "id"),
    "es": ("es", "en", "id"),
    "pt": ("pt", "es", "en", "id"),
}

TEKS = {
    "merek": {"id": "TERMINAL INVESTASI", "en": "TERMINAL INVESTASI", "ms": "TERMINAL INVESTASI", "zh": "TERMINAL INVESTASI", "es": "TERMINAL INVESTASI", "pt": "TERMINAL INVESTASI"},
    "data_terbuka": {"id": "● DATA TERBUKA", "en": "● OPEN DATA", "ms": "● DATA TERBUKA", "zh": "● 开放数据", "es": "● DATOS ABIERTOS", "pt": "● DADOS ABERTOS"},
    "tanpa_kredit": {"id": "TANPA KREDIT · TANPA API KEY", "en": "NO CREDITS · NO API KEYS", "ms": "TANPA KREDIT · TANPA API KEY", "zh": "无积分 · 无需 API 密钥", "es": "SIN CRÉDITOS · SIN CLAVES API", "pt": "SEM CRÉDITOS · SEM CHAVES API"},
    "sub_merek": {"id": "DATA TERBUKA", "en": "OPEN DATA", "ms": "DATA TERBUKA", "zh": "开放数据", "es": "DATOS ABIERTOS", "pt": "DADOS ABERTOS"},
    "m_pasar": {"id": "Pasar", "en": "Market", "ms": "Pasaran", "zh": "市场", "es": "Mercado", "pt": "Mercado"},
    "m_grafik": {"id": "Grafik", "en": "Charts", "ms": "Carta", "zh": "图表", "es": "Gráficos", "pt": "Gráficos"},
    "m_screener": {"id": "Screener", "en": "Screener", "ms": "Penyaring", "zh": "选股器", "es": "Filtro", "pt": "Filtro"},
    "m_fundamental": {"id": "Fundamental", "en": "Fundamentals", "ms": "Fundamental", "zh": "基本面", "es": "Fundamentales", "pt": "Fundamentos"},
    "m_backtest": {"id": "Backtest", "en": "Backtest", "ms": "Ujian Balik", "zh": "回测", "es": "Backtest", "pt": "Backtest"},
    "m_kalkulator": {"id": "Kalkulator", "en": "Calculators", "ms": "Kalkulator", "zh": "计算器", "es": "Calculadoras", "pt": "Calculadoras"},
    "m_berita": {"id": "Berita & Makro", "en": "News & Macro", "ms": "Berita & Makro", "zh": "新闻与宏观", "es": "Noticias y Macro", "pt": "Notícias e Macro"},
    "m_portofolio": {"id": "Portofolio", "en": "Portfolio", "ms": "Portfolio", "zh": "投资组合", "es": "Cartera", "pt": "Carteira"},
    "m_dompet": {"id": "Dompet Kripto", "en": "Crypto Wallet", "ms": "Dompet Kripto", "zh": "加密钱包", "es": "Billetera Cripto", "pt": "Carteira Cripto"},
    "m_peringatan": {"id": "Peringatan", "en": "Alerts", "ms": "Amaran", "zh": "价格提醒", "es": "Alertas", "pt": "Alertas"},
    "m_jurnal": {"id": "Jurnal", "en": "Journal", "ms": "Jurnal", "zh": "交易日志", "es": "Diario", "pt": "Diário"},
    "m_laporan": {"id": "Laporan", "en": "Reports", "ms": "Laporan", "zh": "报告", "es": "Informes", "pt": "Relatórios"},
    "m_tentang": {"id": "Tentang", "en": "About", "ms": "Perihal", "zh": "关于", "es": "Acerca de", "pt": "Sobre"},
    "mode_terang": {"id": "☀  MODE TERANG", "en": "☀  LIGHT MODE", "ms": "☀  MOD CERAH", "zh": "☀  浅色模式", "es": "☀  MODO CLARO", "pt": "☀  MODO CLARO"},
    "mode_gelap": {"id": "☾  MODE GELAP", "en": "☾  DARK MODE", "ms": "☾  MOD GELAP", "zh": "☾  深色模式", "es": "☾  MODO OSCURO", "pt": "☾  MODO ESCURO"},
    "sb_simbol": {"id": "simbol dipantau", "en": "symbols tracked", "ms": "simbol dipantau", "zh": "个跟踪标的", "es": "símbolos seguidos", "pt": "símbolos monitorados"},
    "sb_posisi": {"id": "posisi tercatat", "en": "positions recorded", "ms": "posisi direkod", "zh": "个记录持仓", "es": "posiciones registradas", "pt": "posições registradas"},
    "sb_lokal": {"id": "Data tersimpan lokal di folder <code>data/</code>.", "en": "Data is stored locally in the <code>data/</code> folder.", "ms": "Data disimpan setempat dalam folder <code>data/</code>.", "zh": "数据保存在本地 <code>data/</code> 文件夹中。", "es": "Los datos se guardan localmente en la carpeta <code>data/</code>.", "pt": "Os dados ficam na pasta local <code>data/</code>."},
    "sb_dibuat": {"id": "Dibuat oleh", "en": "Built by", "ms": "Dibina oleh", "zh": "开发者", "es": "Creado por", "pt": "Criado por"},
    "sb_versi_baru": {"id": "VERSI BARU TERSEDIA", "en": "NEW VERSION AVAILABLE", "ms": "VERSI BARU TERSEDIA", "zh": "有新版本", "es": "NUEVA VERSIÓN DISPONIBLE", "pt": "NOVA VERSÃO DISPONÍVEL"},
    "sb_buka_tentang": {"id": "buka Tentang → Pembaruan", "en": "open About → Updates", "ms": "buka Perihal → Kemas Kini", "zh": "打开 关于 → 更新", "es": "abrir Acerca de → Actualizaciones", "pt": "abrir Sobre → Atualizações"},
    "bahasa": {"id": "Bahasa", "en": "Language", "ms": "Bahasa", "zh": "语言", "es": "Idioma", "pt": "Idioma"},
    "j_denyut": {"id": "Denyut Pasar", "en": "Market Pulse", "ms": "Nadi Pasaran", "zh": "市场脉搏", "es": "Pulso del Mercado", "pt": "Pulso do Mercado"},
    "j_grafik": {"id": "Grafik & Analisa", "en": "Charts & Analysis", "ms": "Carta & Analisis", "zh": "图表与分析", "es": "Gráficos y Análisis", "pt": "Gráficos e Análise"},
    "j_screener": {"id": "Screener", "en": "Screener", "ms": "Penyaring Saham", "zh": "选股器", "es": "Filtro de Acciones", "pt": "Filtro de Ações"},
    "j_fundamental": {"id": "Analisis Fundamental", "en": "Fundamental Analysis", "ms": "Analisis Fundamental", "zh": "基本面分析", "es": "Análisis Fundamental", "pt": "Análise Fundamentalista"},
    "j_backtest": {"id": "Backtest Strategi", "en": "Strategy Backtest", "ms": "Ujian Balik Strategi", "zh": "策略回测", "es": "Backtest de Estrategia", "pt": "Backtest de Estratégia"},
    "j_kalkulator": {"id": "Kalkulator Posisi & Risiko", "en": "Position & Risk Calculator", "ms": "Kalkulator Posisi & Risiko", "zh": "仓位与风险计算器", "es": "Calculadora de Posición y Riesgo", "pt": "Calculadora de Posição e Risco"},
    "j_berita": {"id": "Berita & Data Makro", "en": "News & Macro Data", "ms": "Berita & Data Makro", "zh": "新闻与宏观数据", "es": "Noticias y Datos Macro", "pt": "Notícias e Dados Macro"},
    "j_portofolio": {"id": "Portofolio", "en": "Portfolio", "ms": "Portfolio", "zh": "投资组合", "es": "Cartera", "pt": "Carteira"},
    "j_dompet": {"id": "Dompet Kripto", "en": "Crypto Wallet", "ms": "Dompet Kripto", "zh": "加密钱包", "es": "Billetera Cripto", "pt": "Carteira Cripto"},
    "j_peringatan": {"id": "Peringatan Harga", "en": "Price Alerts", "ms": "Amaran Harga", "zh": "价格提醒", "es": "Alertas de Precio", "pt": "Alertas de Preço"},
    "j_jurnal": {"id": "Jurnal Transaksi", "en": "Trade Journal", "ms": "Jurnal Dagangan", "zh": "交易日志", "es": "Diario de Operaciones", "pt": "Diário de Operações"},
    "j_laporan": {"id": "Laporan PDF", "en": "PDF Reports", "ms": "Laporan PDF", "zh": "PDF 报告", "es": "Informes PDF", "pt": "Relatórios PDF"},
    "j_tentang": {"id": "Tentang", "en": "About", "ms": "Perihal", "zh": "关于", "es": "Acerca de", "pt": "Sobre"},
    "j_denyut_kripto": {"id": "Denyut Kripto", "en": "Crypto Pulse", "ms": "Nadi Kripto", "zh": "加密市场脉搏", "es": "Pulso Cripto", "pt": "Pulso Cripto"},
    "j_watchlist": {"id": "Watchlist", "en": "Watchlist", "ms": "Senarai Pantau", "zh": "自选列表", "es": "Lista de Seguimiento", "pt": "Lista de Acompanhamento"},
    "t_indeks": {"id": "Indeks Dunia", "en": "World Indices", "ms": "Indeks Dunia", "zh": "全球指数", "es": "Índices Mundiales", "pt": "Índices Mundiais"},
    "t_kripto": {"id": "Kripto", "en": "Crypto", "ms": "Kripto", "zh": "加密货币", "es": "Cripto", "pt": "Cripto"},
    "t_forex": {"id": "Forex", "en": "Forex", "ms": "Forex", "zh": "外汇", "es": "Forex", "pt": "Forex"},
    "t_komoditas": {"id": "Komoditas & Kurs", "en": "Commodities & FX", "ms": "Komoditi & Kadar", "zh": "商品与汇率", "es": "Materias Primas y Divisas", "pt": "Commodities e Câmbio"},
    "t_saham_id": {"id": "Saham Indonesia", "en": "Indonesian Equities", "ms": "Saham Indonesia", "zh": "印尼股票", "es": "Acciones de Indonesia", "pt": "Ações da Indonésia"},
    "t_grafik_ind": {"id": "Grafik & Indikator", "en": "Charts & Indicators", "ms": "Carta & Penunjuk", "zh": "图表与指标", "es": "Gráficos e Indicadores", "pt": "Gráficos e Indicadores"},
    "t_pembacaan": {"id": "Pembacaan Teknikal", "en": "Technical Read", "ms": "Bacaan Teknikal", "zh": "技术解读", "es": "Lectura Técnica", "pt": "Leitura Técnica"},
    "t_saham": {"id": "Saham", "en": "Stocks", "ms": "Saham", "zh": "股票", "es": "Acciones", "pt": "Ações"},
    "t_ukuran_posisi": {"id": "Ukuran Posisi", "en": "Position Size", "ms": "Saiz Posisi", "zh": "仓位大小", "es": "Tamaño de Posición", "pt": "Tamanho da Posição"},
    "t_posisi_forex": {"id": "Posisi Forex", "en": "Forex Position", "ms": "Posisi Forex", "zh": "外汇仓位", "es": "Posición Forex", "pt": "Posição Forex"},
    "t_rata_harga": {"id": "Rata-rata Harga", "en": "Averaging", "ms": "Purata Harga", "zh": "摊平成本", "es": "Promediado", "pt": "Preço Médio"},
    "t_impas": {"id": "Titik Impas", "en": "Break-even", "ms": "Titik Pulang Modal", "zh": "盈亏平衡", "es": "Punto de Equilibrio", "pt": "Ponto de Equilíbrio"},
    "t_kabel_berita": {"id": "Kabel Berita", "en": "News Wire", "ms": "Kawat Berita", "zh": "新闻快讯", "es": "Cable de Noticias", "pt": "Fio de Notícias"},
    "t_indikator_ek": {"id": "Indikator Ekonomi", "en": "Economic Indicators", "ms": "Penunjuk Ekonomi", "zh": "经济指标", "es": "Indicadores Económicos", "pt": "Indicadores Econômicos"},
    "t_laba_rugi": {"id": "Laba Rugi", "en": "Income Statement", "ms": "Untung Rugi", "zh": "利润表", "es": "Estado de Resultados", "pt": "Demonstração de Resultados"},
    "t_neraca": {"id": "Neraca", "en": "Balance Sheet", "ms": "Kunci Kira-kira", "zh": "资产负债表", "es": "Balance General", "pt": "Balanço Patrimonial"},
    "t_arus_kas": {"id": "Arus Kas", "en": "Cash Flow", "ms": "Aliran Tunai", "zh": "现金流量表", "es": "Flujo de Caja", "pt": "Fluxo de Caixa"},
    "t_catat": {"id": "Catat", "en": "Record", "ms": "Rekod", "zh": "记录", "es": "Registrar", "pt": "Registrar"},
    "t_riwayat": {"id": "Riwayat", "en": "History", "ms": "Sejarah", "zh": "历史", "es": "Historial", "pt": "Histórico"},
    "t_statistik": {"id": "Statistik", "en": "Statistics", "ms": "Statistik", "zh": "统计", "es": "Estadísticas", "pt": "Estatísticas"},
    "t_aplikasi": {"id": "Aplikasi", "en": "Application", "ms": "Aplikasi", "zh": "应用", "es": "Aplicación", "pt": "Aplicativo"},
    "t_pembuat": {"id": "Pembuat", "en": "Author", "ms": "Pembina", "zh": "作者", "es": "Autor", "pt": "Autor"},
    "t_pembaruan": {"id": "Pembaruan", "en": "Updates", "ms": "Kemas Kini", "zh": "更新", "es": "Actualizaciones", "pt": "Atualizações"},
    "b_muat_ulang": {"id": "⟳  MUAT ULANG", "en": "⟳  RELOAD", "ms": "⟳  MUAT SEMULA", "zh": "⟳  刷新", "es": "⟳  RECARGAR", "pt": "⟳  RECARREGAR"},
    "b_segarkan": {"id": "⟳  SEGARKAN", "en": "⟳  REFRESH", "ms": "⟳  SEGARKAN", "zh": "⟳  刷新", "es": "⟳  ACTUALIZAR", "pt": "⟳  ATUALIZAR"},
    "b_tambah": {"id": "TAMBAH", "en": "ADD", "ms": "TAMBAH", "zh": "添加", "es": "AÑADIR", "pt": "ADICIONAR"},
    "b_hapus": {"id": "HAPUS TERPILIH", "en": "DELETE SELECTED", "ms": "PADAM PILIHAN", "zh": "删除所选", "es": "ELIMINAR SELECCIÓN", "pt": "EXCLUIR SELECIONADOS"},
    "b_simpan": {"id": "SIMPAN", "en": "SAVE", "ms": "SIMPAN", "zh": "保存", "es": "GUARDAR", "pt": "SALVAR"},
    "k_simbol": {"id": "Simbol", "en": "Symbol", "ms": "Simbol", "zh": "代码", "es": "Símbolo", "pt": "Símbolo"},
    "k_nama": {"id": "Nama", "en": "Name", "ms": "Nama", "zh": "名称", "es": "Nombre", "pt": "Nome"},
    "k_harga": {"id": "Harga", "en": "Price", "ms": "Harga", "zh": "价格", "es": "Precio", "pt": "Preço"},
    "k_perubahan": {"id": "Perubahan", "en": "Change", "ms": "Perubahan", "zh": "涨跌", "es": "Cambio", "pt": "Variação"},
    "k_persen": {"id": "Persen", "en": "Percent", "ms": "Peratus", "zh": "涨跌幅", "es": "Porcentaje", "pt": "Percentual"},
    "k_volume": {"id": "Volume", "en": "Volume", "ms": "Volum", "zh": "成交量", "es": "Volumen", "pt": "Volume"},
    "k_sektor": {"id": "Sektor", "en": "Sector", "ms": "Sektor", "zh": "行业", "es": "Sector", "pt": "Setor"},
    "k_jumlah": {"id": "Jumlah", "en": "Quantity", "ms": "Kuantiti", "zh": "数量", "es": "Cantidad", "pt": "Quantidade"},
    "k_nilai": {"id": "Nilai", "en": "Value", "ms": "Nilai", "zh": "价值", "es": "Valor", "pt": "Valor"},
    "k_laba_rugi": {"id": "Laba/Rugi", "en": "P&L", "ms": "Untung/Rugi", "zh": "盈亏", "es": "P&G", "pt": "Lucro/Prejuízo"},
    "k_kapitalisasi": {"id": "Kapitalisasi", "en": "Market cap", "ms": "Permodalan Pasaran", "zh": "市值", "es": "Capitalización", "pt": "Valor de Mercado"},
    "k_dividen": {"id": "Dividen %", "en": "Dividend %", "ms": "Dividen %", "zh": "股息率 %", "es": "Dividendo %", "pt": "Dividendo %"},
    "dukung": {"id": "DUKUNG PENGEMBANGAN", "en": "SUPPORT DEVELOPMENT", "ms": "SOKONG PEMBANGUNAN", "zh": "支持开发", "es": "APOYAR EL DESARROLLO", "pt": "APOIAR O DESENVOLVIMENTO"},
    "dukung_teks": {"id": "Terminal ini gratis dan akan tetap gratis. Kalau aplikasi ini berguna bagi Anda dan ingin ikut menjaganya tetap hidup, dukungan sukarela sangat berarti — sekecil apa pun.", "en": "This terminal is free and will stay free. If it's useful to you and you'd like to help keep it alive, voluntary support means a great deal — however small.", "ms": "Terminal ini percuma dan akan kekal percuma. Jika ia berguna kepada anda dan anda ingin membantu mengekalkannya, sokongan sukarela amat bermakna — sekecil mana pun.", "zh": "本终端免费，并将一直免费。如果它对您有帮助，愿意支持它继续运作，任何数额的自愿捐助都意义重大。", "es": "Esta terminal es gratuita y seguirá siéndolo. Si te resulta útil y quieres ayudar a mantenerla, cualquier apoyo voluntario significa mucho, por pequeño que sea.", "pt": "Este terminal é gratuito e continuará sendo. Se ele é útil para você e quiser ajudar a mantê-lo, qualquer apoio voluntário significa muito, por menor que seja."},
    "qr_rusak": {"id": "Berkas ada, tetapi tidak bisa dibaca sebagai gambar.", "en": "The file exists but cannot be read as an image.", "ms": "Fail wujud tetapi tidak boleh dibaca sebagai imej.", "zh": "文件存在，但无法作为图片读取。", "es": "El archivo existe pero no puede leerse como imagen.", "pt": "O arquivo existe mas não pode ser lido como imagem."},
    "qr_gagal": {"id": "Gambar QR gagal ditampilkan.", "en": "The QR image failed to display.", "ms": "Imej QR gagal dipaparkan.", "zh": "二维码图片无法显示。", "es": "La imagen QR no pudo mostrarse.", "pt": "A imagem do QR não pôde ser exibida."},
    "s_pasar": {"id": "Pasar", "en": "Market", "ms": "Pasaran", "zh": "市场", "es": "Mercado", "pt": "Mercado"},
    "s_intro": {"id": "Menyaring bukan berarti menemukan saham bagus — hanya mempersempit daftar yang layak dibaca lebih jauh. Angka murah sering murah karena ada alasannya.", "en": "Screening doesn't find good stocks — it only narrows the list worth reading further. Cheap numbers are often cheap for a reason.", "ms": "Menyaring bukan bermakna menemui saham yang bagus — ia hanya memendekkan senarai yang wajar dibaca lebih lanjut. Angka yang murah selalunya murah atas sebab tertentu.", "zh": "筛选并不能找出好股票，只是缩小值得进一步研究的范围。便宜的估值往往便宜得有原因。", "es": "Filtrar no encuentra buenas acciones: solo reduce la lista que vale la pena estudiar. Lo barato suele estar barato por algo.", "pt": "Filtrar não encontra boas ações — apenas reduz a lista que vale a pena estudar. O que está barato costuma estar barato por um motivo."},
    "s_saring": {"id": "SARING SEKARANG", "en": "RUN SCREEN", "ms": "SARING SEKARANG", "zh": "开始筛选", "es": "EJECUTAR FILTRO", "pt": "EXECUTAR FILTRO"},
    "s_tekan": {"id": "Tekan **SARING SEKARANG** untuk mengambil data.", "en": "Press **RUN SCREEN** to fetch the data.", "ms": "Tekan **SARING SEKARANG** untuk mengambil data.", "zh": "点击 **开始筛选** 获取数据。", "es": "Pulsa **EJECUTAR FILTRO** para obtener los datos.", "pt": "Clique em **EXECUTAR FILTRO** para buscar os dados."},
    "s_gagal": {"id": "Tidak ada data yang berhasil diambil. Periksa koneksi internet Anda.", "en": "No data could be retrieved. Check your internet connection.", "ms": "Tiada data berjaya diambil. Periksa sambungan internet anda.", "zh": "未能获取数据。请检查网络连接。", "es": "No se pudieron obtener datos. Revisa tu conexión a internet.", "pt": "Nenhum dado foi obtido. Verifique sua conexão de internet."},
    "s_penyaring": {"id": "Penyaring", "en": "Filters", "ms": "Penapis", "zh": "筛选条件", "es": "Filtros", "pt": "Filtros"},
    "s_diambil": {"id": "saham berhasil diambil", "en": "stocks retrieved", "ms": "saham berjaya diambil", "zh": "只股票已获取", "es": "acciones obtenidas", "pt": "ações obtidas"},
    "s_siap_pakai": {"id": "Saringan siap pakai — sekali klik:", "en": "One-click presets:", "ms": "Penapis siap sedia — sekali klik:", "zh": "一键预设：", "es": "Preajustes de un clic:", "pt": "Predefinições de um clique:"},
    "s_atur": {"id": "Atur batas penyaringan", "en": "Set filter thresholds", "ms": "Tetapkan had penapisan", "zh": "设置筛选阈值", "es": "Ajustar umbrales del filtro", "pt": "Definir limites do filtro"},
    "s_per_maks": {"id": "PER maksimum", "en": "Max P/E", "ms": "P/E maksimum", "zh": "市盈率上限", "es": "P/E máximo", "pt": "P/L máximo"},
    "s_pbv_maks": {"id": "PBV maksimum", "en": "Max P/B", "ms": "P/B maksimum", "zh": "市净率上限", "es": "P/B máximo", "pt": "P/VP máximo"},
    "s_roe_min": {"id": "ROE minimum (%)", "en": "Min ROE (%)", "ms": "ROE minimum (%)", "zh": "净资产收益率下限 (%)", "es": "ROE mínimo (%)", "pt": "ROE mínimo (%)"},
    "s_div_min": {"id": "Dividen minimum (%)", "en": "Min dividend yield (%)", "ms": "Dividen minimum (%)", "zh": "股息率下限 (%)", "es": "Rentabilidad por dividendo mínima (%)", "pt": "Dividend yield mínimo (%)"},
    "s_der_maks": {"id": "DER maksimum", "en": "Max debt/equity", "ms": "Nisbah hutang/ekuiti maksimum", "zh": "负债权益比上限", "es": "Deuda/patrimonio máximo", "pt": "Dívida/patrimônio máximo"},
    "s_kap_min": {"id": "Kapitalisasi minimum", "en": "Min market cap", "ms": "Permodalan pasaran minimum", "zh": "市值下限", "es": "Capitalización mínima", "pt": "Valor de mercado mínimo"},
    "s_sektor": {"id": "Sektor", "en": "Sector", "ms": "Sektor", "zh": "行业", "es": "Sector", "pt": "Setor"},
    "s_semua_sektor": {"id": "Semua sektor", "en": "All sectors", "ms": "Semua sektor", "zh": "全部行业", "es": "Todos los sectores", "pt": "Todos os setores"},
    "s_syariah": {"id": "Penapisan syariah", "en": "Shariah screening", "ms": "Penapisan patuh syariah", "zh": "伊斯兰合规筛选", "es": "Filtro conforme a la sharía", "pt": "Filtro conforme a sharia"},
    "s_tak_dipakai": {"id": "Tidak dipakai", "en": "Not applied", "ms": "Tidak digunakan", "zh": "不使用", "es": "No aplicado", "pt": "Não aplicado"},
    "s_aktif": {"id": "Penyaring aktif:", "en": "Active filters:", "ms": "Penapis aktif:", "zh": "生效的筛选条件：", "es": "Filtros activos:", "pt": "Filtros ativos:"},
    "s_belum_ada": {"id": "belum ada — semua saham ditampilkan", "en": "none — all stocks shown", "ms": "tiada — semua saham dipaparkan", "zh": "无 — 显示全部股票", "es": "ninguno — se muestran todas", "pt": "nenhum — todas as ações exibidas"},
    "s_lolos": {"id": "saham lolos", "en": "stocks passed", "ms": "saham lulus", "zh": "只股票通过", "es": "acciones pasaron", "pt": "ações aprovadas"},
    "s_kosong": {"id": "Tidak ada saham yang lolos. Longgarkan batasannya.", "en": "No stocks passed. Loosen the thresholds.", "ms": "Tiada saham yang lulus. Longgarkan hadnya.", "zh": "没有股票通过筛选。请放宽条件。", "es": "Ninguna acción pasó. Relaja los umbrales.", "pt": "Nenhuma ação passou. Afrouxe os limites."},
    "s_urutkan": {"id": "Urutkan berdasarkan", "en": "Sort by", "ms": "Susun mengikut", "zh": "排序方式", "es": "Ordenar por", "pt": "Ordenar por"},
    "s_unduh": {"id": "UNDUH HASIL (CSV)", "en": "DOWNLOAD RESULTS (CSV)", "ms": "MUAT TURUN HASIL (CSV)", "zh": "下载结果 (CSV)", "es": "DESCARGAR RESULTADOS (CSV)", "pt": "BAIXAR RESULTADOS (CSV)"},
    "s_tindak": {"id": "Tindak lanjut", "en": "Next steps", "ms": "Tindakan seterusnya", "zh": "后续操作", "es": "Siguientes pasos", "pt": "Próximos passos"},
    "s_pilih_saham": {"id": "Pilih saham", "en": "Select stocks", "ms": "Pilih saham", "zh": "选择股票", "es": "Seleccionar acciones", "pt": "Selecionar ações"},
    "s_pilih_ph": {"id": "Pilih untuk dibandingkan atau dipantau", "en": "Select to compare or track", "ms": "Pilih untuk dibandingkan atau dipantau", "zh": "选择以比较或加入自选", "es": "Selecciona para comparar o seguir", "pt": "Selecione para comparar ou acompanhar"},
    "s_ke_watchlist": {"id": "KE WATCHLIST", "en": "ADD TO WATCHLIST", "ms": "KE SENARAI PANTAU", "zh": "加入自选", "es": "AÑADIR A LA LISTA", "pt": "ADICIONAR À LISTA"},
    "s_ditambahkan": {"id": "simbol ditambahkan ke watchlist.", "en": "symbols added to watchlist.", "ms": "simbol ditambah ke senarai pantau.", "zh": "个标的已加入自选。", "es": "símbolos añadidos a la lista.", "pt": "símbolos adicionados à lista."},
    "s_sudah_ada": {"id": "Semua sudah ada di watchlist.", "en": "All are already in your watchlist.", "ms": "Semua sudah ada dalam senarai pantau.", "zh": "全部已在自选列表中。", "es": "Todos ya están en tu lista.", "pt": "Todos já estão na sua lista."},
    "s_belum_pilih": {"id": "Belum ada saham yang dipilih.", "en": "No stocks selected yet.", "ms": "Belum ada saham dipilih.", "zh": "尚未选择股票。", "es": "Aún no has seleccionado acciones.", "pt": "Nenhuma ação selecionada ainda."},
    "s_banding": {"id": "Perbandingan berdampingan", "en": "Side-by-side comparison", "ms": "Perbandingan bersebelahan", "zh": "并排对比", "es": "Comparación lado a lado", "pt": "Comparação lado a lado"},
    "s_pilih_dua": {"id": "Pilih setidaknya dua saham untuk dibandingkan.", "en": "Select at least two stocks to compare.", "ms": "Pilih sekurang-kurangnya dua saham untuk dibandingkan.", "zh": "请至少选择两只股票进行比较。", "es": "Selecciona al menos dos acciones para comparar.", "pt": "Selecione ao menos duas ações para comparar."},
    "s_koin_ambil": {"id": "Ambil berapa koin teratas", "en": "How many top coins to fetch", "ms": "Berapa syiling teratas hendak diambil", "zh": "获取排名前多少的币种", "es": "Cuántas monedas principales obtener", "pt": "Quantas moedas principais buscar"},
    "s_koin_lolos": {"id": "koin lolos", "en": "coins passed", "ms": "syiling lulus", "zh": "个币种通过", "es": "monedas pasaron", "pt": "moedas aprovadas"},
    "s_koin_dari": {"id": "dari", "en": "of", "ms": "daripada", "zh": "／共", "es": "de", "pt": "de"},
    "s_koin_kosong": {"id": "Tidak ada koin yang lolos. Longgarkan batasannya.", "en": "No coins passed. Loosen the thresholds.", "ms": "Tiada syiling yang lulus. Longgarkan hadnya.", "zh": "没有币种通过筛选。请放宽条件。", "es": "Ninguna moneda pasó. Relaja los umbrales.", "pt": "Nenhuma moeda passou. Afrouxe os limites."},
    "s_kripto_gagal": {"id": "Data tidak bisa diambil. CoinGecko membatasi permintaan gratis — tunggu sebentar lalu coba lagi.", "en": "Data unavailable. CoinGecko rate-limits free usage — wait a moment and try again.", "ms": "Data tidak dapat diambil. CoinGecko mengehadkan permintaan percuma — tunggu sebentar dan cuba lagi.", "zh": "无法获取数据。CoinGecko 对免费使用有频率限制，请稍候再试。", "es": "Datos no disponibles. CoinGecko limita el uso gratuito: espera un momento y vuelve a intentarlo.", "pt": "Dados indisponíveis. O CoinGecko limita o uso gratuito — aguarde um momento e tente novamente."},
    "s_kap_min_miliar": {"id": "Kapitalisasi minimum (miliar $)", "en": "Min market cap (billion $)", "ms": "Permodalan minimum (bilion $)", "zh": "市值下限（十亿美元）", "es": "Capitalización mínima (mil millones $)", "pt": "Valor de mercado mínimo (bilhões $)"},
    "s_naik7": {"id": "Kenaikan 7 hari minimum (%)", "en": "Min 7-day change (%)", "ms": "Kenaikan 7 hari minimum (%)", "zh": "7 日涨幅下限 (%)", "es": "Cambio mínimo en 7 días (%)", "pt": "Variação mínima em 7 dias (%)"},
    "s_dari_puncak": {"id": "Maksimal turun dari puncak (%)", "en": "Max drop from all-time high (%)", "ms": "Penurunan maksimum dari puncak (%)", "zh": "距历史高点最大跌幅 (%)", "es": "Caída máxima desde máximos (%)", "pt": "Queda máxima desde a máxima histórica (%)"},
    "bt_intro": {"id": "Backtest menunjukkan bagaimana sebuah aturan <i>akan</i> berjalan seandainya dipakai di masa lalu. Ia bukan ramalan, dan hasil yang mengagumkan justru pantas dicurigai lebih dulu.", "en": "A backtest shows how a rule <i>would</i> have performed in the past. It is not a forecast, and impressive results deserve suspicion before applause.", "ms": "Ujian balik menunjukkan bagaimana sesuatu peraturan <i>akan</i> berprestasi pada masa lalu. Ia bukan ramalan, dan keputusan yang mengagumkan patut dicurigai dahulu.", "zh": "回测显示某项规则在过去<i>本会</i>有怎样的表现。它不是预测；亮眼的结果值得先怀疑，而不是先鼓掌。", "es": "Un backtest muestra cómo <i>habría</i> funcionado una regla en el pasado. No es un pronóstico, y los resultados impresionantes merecen sospecha antes que aplausos.", "pt": "Um backtest mostra como uma regra <i>teria</i> se comportado no passado. Não é previsão, e resultados impressionantes merecem desconfiança antes de aplausos."},
    "bt_jenis": {"id": "Jenis instrumen", "en": "Instrument type", "ms": "Jenis instrumen", "zh": "品种类型", "es": "Tipo de instrumento", "pt": "Tipo de instrumento"},
    "bt_saham_kripto": {"id": "Saham & Kripto", "en": "Stocks & Crypto", "ms": "Saham & Kripto", "zh": "股票与加密货币", "es": "Acciones y Cripto", "pt": "Ações e Cripto"},
    "bt_pasangan": {"id": "Pasangan mata uang", "en": "Currency pair", "ms": "Pasangan mata wang", "zh": "货币对", "es": "Par de divisas", "pt": "Par de moedas"},
    "bt_rentang": {"id": "Rentang waktu", "en": "Timeframe", "ms": "Jangka masa", "zh": "周期", "es": "Marco temporal", "pt": "Período do candle"},
    "bt_lama": {"id": "Lama pengujian", "en": "Test period", "ms": "Tempoh ujian", "zh": "测试时长", "es": "Periodo de prueba", "pt": "Período de teste"},
    "bt_strategi": {"id": "Strategi", "en": "Strategy", "ms": "Strategi", "zh": "策略", "es": "Estrategia", "pt": "Estratégia"},
    "bt_modal": {"id": "Modal awal (Rp)", "en": "Starting capital", "ms": "Modal permulaan", "zh": "初始资金", "es": "Capital inicial", "pt": "Capital inicial"},
    "bt_biaya": {"id": "Biaya per transaksi (%)", "en": "Cost per trade (%)", "ms": "Kos setiap dagangan (%)", "zh": "每笔交易成本 (%)", "es": "Coste por operación (%)", "pt": "Custo por operação (%)"},
    "bt_spread": {"id": "Spread (pip)", "en": "Spread (pips)", "ms": "Spread (pip)", "zh": "点差（点）", "es": "Spread (pips)", "pt": "Spread (pips)"},
    "bt_hasil": {"id": "HASIL PENGUJIAN", "en": "TEST RESULT", "ms": "KEPUTUSAN UJIAN", "zh": "测试结果", "es": "RESULTADO DE LA PRUEBA", "pt": "RESULTADO DO TESTE"},
    "bt_batang": {"id": "BATANG", "en": "BARS", "ms": "BAR", "zh": "根K线", "es": "BARRAS", "pt": "BARRAS"},
    "bt_lebih_banyak": {"id": "lebih banyak", "en": "more", "ms": "lebih banyak", "zh": "更多", "es": "más", "pt": "a mais"},
    "bt_lebih_sedikit": {"id": "lebih sedikit", "en": "less", "ms": "lebih sedikit", "zh": "更少", "es": "menos", "pt": "a menos"},
    "bt_dibanding": {"id": "dibanding sekadar membeli lalu mendiamkannya selama", "en": "than simply buying and holding for", "ms": "berbanding sekadar membeli dan menyimpannya selama", "zh": "相比单纯买入并持有，历时", "es": "que simplemente comprar y mantener durante", "pt": "do que simplesmente comprar e segurar por"},
    "bt_tahun": {"id": "tahun", "en": "years", "ms": "tahun", "zh": "年", "es": "años", "pt": "anos"},
    "bt_modal_akhir": {"id": "MODAL AKHIR", "en": "FINAL CAPITAL", "ms": "MODAL AKHIR", "zh": "期末资金", "es": "CAPITAL FINAL", "pt": "CAPITAL FINAL"},
    "bt_dari": {"id": "dari", "en": "from", "ms": "daripada", "zh": "起始", "es": "desde", "pt": "de"},
    "bt_per_tahun": {"id": "HASIL PER TAHUN", "en": "ANNUAL RETURN", "ms": "PULANGAN TAHUNAN", "zh": "年化收益", "es": "RENTABILIDAD ANUAL", "pt": "RETORNO ANUAL"},
    "bt_pasar": {"id": "pasar", "en": "market", "ms": "pasaran", "zh": "市场", "es": "mercado", "pt": "mercado"},
    "bt_penurunan": {"id": "PENURUNAN TERDALAM", "en": "MAX DRAWDOWN", "ms": "PENURUNAN TERBESAR", "zh": "最大回撤", "es": "CAÍDA MÁXIMA", "pt": "QUEDA MÁXIMA"},
    "bt_sharpe": {"id": "RASIO SHARPE", "en": "SHARPE RATIO", "ms": "NISBAH SHARPE", "zh": "夏普比率", "es": "RATIO DE SHARPE", "pt": "ÍNDICE DE SHARPE"},
    "bt_makin_tinggi": {"id": "makin tinggi makin baik", "en": "higher is better", "ms": "lebih tinggi lebih baik", "zh": "越高越好", "es": "cuanto más alto, mejor", "pt": "quanto maior, melhor"},
    "bt_jml_transaksi": {"id": "JUMLAH TRANSAKSI", "en": "TRADE COUNT", "ms": "BILANGAN DAGANGAN", "zh": "交易次数", "es": "NÚMERO DE OPERACIONES", "pt": "NÚMERO DE OPERAÇÕES"},
    "bt_per_tahun2": {"id": "per tahun", "en": "per year", "ms": "setahun", "zh": "每年", "es": "por año", "pt": "por ano"},
    "bt_untung": {"id": "TRANSAKSI UNTUNG", "en": "WINNING TRADES", "ms": "DAGANGAN UNTUNG", "zh": "盈利交易", "es": "OPERACIONES GANADORAS", "pt": "OPERAÇÕES VENCEDORAS"},
    "bt_dari2": {"id": "dari", "en": "of", "ms": "daripada", "zh": "／共", "es": "de", "pt": "de"},
    "bt_waktu_pasar": {"id": "WAKTU DI PASAR", "en": "TIME IN MARKET", "ms": "MASA DALAM PASARAN", "zh": "持仓时间占比", "es": "TIEMPO EN MERCADO", "pt": "TEMPO NO MERCADO"},
    "bt_sisanya_tunai": {"id": "sisanya memegang tunai", "en": "otherwise in cash", "ms": "selebihnya memegang tunai", "zh": "其余时间持有现金", "es": "el resto en efectivo", "pt": "o restante em caixa"},
    "bt_ditahan": {"id": "RATA-RATA DITAHAN", "en": "AVG HOLDING TIME", "ms": "PURATA TEMPOH PEGANGAN", "zh": "平均持仓时长", "es": "TIEMPO MEDIO DE TENENCIA", "pt": "TEMPO MÉDIO DE POSIÇÃO"},
    "bt_per_transaksi": {"id": "per transaksi", "en": "per trade", "ms": "setiap dagangan", "zh": "每笔交易", "es": "por operación", "pt": "por operação"},
    "bt_hari": {"id": "hari", "en": "days", "ms": "hari", "zh": "天", "es": "días", "pt": "dias"},
    "bt_jam": {"id": "jam", "en": "hours", "ms": "jam", "zh": "小时", "es": "horas", "pt": "horas"},
    "bt_pertumbuhan": {"id": "Pertumbuhan modal", "en": "Capital growth", "ms": "Pertumbuhan modal", "zh": "资金增长", "es": "Crecimiento del capital", "pt": "Crescimento do capital"},
    "bt_jarak_puncak": {"id": "Jarak dari puncak modal", "en": "Distance from capital peak", "ms": "Jarak dari puncak modal", "zh": "距资金峰值的回撤", "es": "Distancia desde el máximo", "pt": "Distância do pico de capital"},
    "bt_beli_tahan": {"id": "Beli dan Tahan", "en": "Buy and Hold", "ms": "Beli dan Simpan", "zh": "买入持有", "es": "Comprar y Mantener", "pt": "Comprar e Segurar"},
    "bt_kapan_pegang": {"id": "Kapan strategi memegang — arsir hijau untung, merah rugi", "en": "When the strategy held — green shading profitable, red losing", "ms": "Bila strategi memegang posisi — lorekan hijau untung, merah rugi", "zh": "策略持仓期间 — 绿色为盈利，红色为亏损", "es": "Cuándo mantuvo la estrategia — verde con ganancia, rojo con pérdida", "pt": "Quando a estratégia esteve posicionada — verde com lucro, vermelho com prejuízo"},
    "bt_masuk": {"id": "Masuk", "en": "Entry", "ms": "Masuk", "zh": "买入", "es": "Entrada", "pt": "Entrada"},
    "bt_keluar": {"id": "Keluar", "en": "Exit", "ms": "Keluar", "zh": "卖出", "es": "Salida", "pt": "Saída"},
    "bt_per_bulan": {"id": "Hasil per bulan (%)", "en": "Monthly returns (%)", "ms": "Pulangan bulanan (%)", "zh": "月度收益 (%)", "es": "Rentabilidad mensual (%)", "pt": "Retorno mensal (%)"},
    "bt_sebaran": {"id": "Sebaran hasil tiap transaksi (%)", "en": "Distribution of trade results (%)", "ms": "Taburan hasil setiap dagangan (%)", "zh": "单笔交易结果分布 (%)", "es": "Distribución de resultados por operación (%)", "pt": "Distribuição dos resultados por operação (%)"},
    "bt_rata_rata": {"id": "rata-rata", "en": "average", "ms": "purata", "zh": "平均", "es": "media", "pt": "média"},
    "bt_rincian": {"id": "Rincian", "en": "Details of", "ms": "Perincian", "zh": "明细：", "es": "Detalle de", "pt": "Detalhe de"},
    "bt_transaksi": {"id": "transaksi", "en": "trades", "ms": "dagangan", "zh": "笔交易", "es": "operaciones", "pt": "operações"},
    "bt_terlalu_pendek": {"id": "Periode terlalu pendek untuk peta panas bulanan.", "en": "Period too short for a monthly heatmap.", "ms": "Tempoh terlalu pendek untuk peta haba bulanan.", "zh": "周期太短，无法生成月度热力图。", "es": "Periodo demasiado corto para el mapa de calor mensual.", "pt": "Período curto demais para o mapa de calor mensal."},
    "bt_terlalu_sedikit": {"id": "Transaksi terlalu sedikit untuk digambar sebarannya.", "en": "Too few trades to plot a distribution.", "ms": "Terlalu sedikit dagangan untuk melukis taburan.", "zh": "交易次数太少，无法绘制分布图。", "es": "Muy pocas operaciones para trazar una distribución.", "pt": "Poucas operações para traçar uma distribuição."},
    "bt_data_kurang": {"id": "Data tidak cukup untuk diuji. Coba periode yang lebih panjang.", "en": "Not enough data to test. Try a longer period.", "ms": "Data tidak mencukupi untuk diuji. Cuba tempoh yang lebih panjang.", "zh": "数据不足以进行测试，请选择更长的周期。", "es": "Datos insuficientes para probar. Prueba un periodo más largo.", "pt": "Dados insuficientes para testar. Tente um período maior."},
    "kal_intro": {"id": "Alat ini tidak menebak arah harga. Ia menjawab pertanyaan yang lebih penting: <i>kalau saya salah, berapa yang hilang?</i>", "en": "These tools don't guess where price is going. They answer a more important question: <i>if I'm wrong, how much do I lose?</i>", "ms": "Alat ini tidak meneka arah harga. Ia menjawab soalan yang lebih penting: <i>jika saya silap, berapa banyak yang hilang?</i>", "zh": "这些工具不猜测价格方向，而是回答一个更重要的问题：<i>如果我判断错了，会亏多少？</i>", "es": "Estas herramientas no adivinan hacia dónde va el precio. Responden algo más importante: <i>si me equivoco, ¿cuánto pierdo?</i>", "pt": "Estas ferramentas não adivinham para onde vai o preço. Elas respondem a algo mais importante: <i>se eu estiver errado, quanto perco?</i>"},
    "kal_modal": {"id": "Total modal (Rp)", "en": "Total capital", "ms": "Jumlah modal", "zh": "总资金", "es": "Capital total", "pt": "Capital total"},
    "kal_risiko": {"id": "Risiko maksimum per transaksi (%)", "en": "Max risk per trade (%)", "ms": "Risiko maksimum setiap dagangan (%)", "zh": "单笔最大风险 (%)", "es": "Riesgo máximo por operación (%)", "pt": "Risco máximo por operação (%)"},
    "kal_harga_beli": {"id": "Harga beli (Rp)", "en": "Entry price", "ms": "Harga belian", "zh": "买入价", "es": "Precio de entrada", "pt": "Preço de entrada"},
    "kal_stop": {"id": "Batas rugi / stop loss (Rp)", "en": "Stop loss", "ms": "Had rugi / stop loss", "zh": "止损价", "es": "Stop loss", "pt": "Stop loss"},
    "kal_target": {"id": "Target harga jual (Rp) — boleh dikosongkan", "en": "Target price — optional", "ms": "Harga sasaran — pilihan", "zh": "目标价 — 可不填", "es": "Precio objetivo — opcional", "pt": "Preço-alvo — opcional"},
    "kal_boleh_beli": {"id": "BOLEH BELI", "en": "MAY BUY", "ms": "BOLEH BELI", "zh": "可买入", "es": "PUEDES COMPRAR", "pt": "PODE COMPRAR"},
    "kal_lembar": {"id": "lembar", "en": "shares", "ms": "unit", "zh": "股", "es": "acciones", "pt": "ações"},
    "kal_nilai_beli": {"id": "NILAI PEMBELIAN", "en": "POSITION VALUE", "ms": "NILAI POSISI", "zh": "持仓金额", "es": "VALOR DE LA POSICIÓN", "pt": "VALOR DA POSIÇÃO"},
    "kal_dari_modal": {"id": "dari modal", "en": "of capital", "ms": "daripada modal", "zh": "占总资金", "es": "del capital", "pt": "do capital"},
    "kal_risiko_nyata": {"id": "RISIKO NYATA", "en": "ACTUAL RISK", "ms": "RISIKO SEBENAR", "zh": "实际风险", "es": "RIESGO REAL", "pt": "RISCO REAL"},
    "kal_potensi": {"id": "POTENSI UNTUNG", "en": "POTENTIAL GAIN", "ms": "POTENSI UNTUNG", "zh": "潜在收益", "es": "GANANCIA POTENCIAL", "pt": "GANHO POTENCIAL"},
    "kal_rasio": {"id": "rasio", "en": "ratio", "ms": "nisbah", "zh": "比率", "es": "ratio", "pt": "proporção"},
    "kal_target_kosong": {"id": "target belum diisi", "en": "no target set", "ms": "sasaran belum ditetapkan", "zh": "未设定目标价", "es": "sin objetivo definido", "pt": "sem alvo definido"},
    "p_portofolio": {"id": "Portofolio proyek", "en": "Project portfolio", "ms": "Portfolio projek", "zh": "项目作品", "es": "Portafolio de proyectos", "pt": "Portfólio de projetos"},
    "p_layanan": {"id": "Layanan", "en": "Services", "ms": "Perkhidmatan", "zh": "提供的服务", "es": "Servicios", "pt": "Serviços"},
    "p_penutup": {"id": "Terminal ini dibangun sebagai proyek pribadi — sebuah percobaan menjawab pertanyaan sederhana: seberapa jauh sebuah terminal data keuangan bisa berjalan tanpa langganan, tanpa kredit, dan tanpa satu pun API berbayar.", "en": "This terminal was built as a personal project — an experiment answering one simple question: how far can a financial data terminal go with no subscription, no credits, and not a single paid API?", "ms": "Terminal ini dibina sebagai projek peribadi — satu percubaan menjawab soalan mudah: sejauh mana sebuah terminal data kewangan boleh berfungsi tanpa langganan, tanpa kredit, dan tanpa satu pun API berbayar.", "zh": "这个终端是一个个人项目，用来回答一个简单的问题：一个金融数据终端，在没有订阅、没有积分、没有任何付费 API 的情况下，究竟能走多远？", "es": "Esta terminal nació como proyecto personal: un experimento para responder una pregunta simple. ¿Hasta dónde puede llegar una terminal de datos financieros sin suscripción, sin créditos y sin una sola API de pago?", "pt": "Este terminal nasceu como projeto pessoal — um experimento para responder a uma pergunta simples: até onde vai um terminal de dados financeiros sem assinatura, sem créditos e sem uma única API paga?"},
    "u_versi_terpasang": {"id": "VERSI TERPASANG", "en": "INSTALLED VERSION", "ms": "VERSI DIPASANG", "zh": "当前版本", "es": "VERSIÓN INSTALADA", "pt": "VERSÃO INSTALADA"},
    "u_di_komputer": {"id": "di komputer ini", "en": "on this computer", "ms": "pada komputer ini", "zh": "在本机上", "es": "en este ordenador", "pt": "neste computador"},
    "u_periksa": {"id": "⟳  PERIKSA PEMBARUAN", "en": "⟳  CHECK FOR UPDATES", "ms": "⟳  SEMAK KEMAS KINI", "zh": "⟳  检查更新", "es": "⟳  BUSCAR ACTUALIZACIONES", "pt": "⟳  VERIFICAR ATUALIZAÇÕES"},
    "u_otomatis": {"id": "Periksa pembaruan otomatis saat aplikasi dibuka", "en": "Check for updates automatically at startup", "ms": "Semak kemas kini secara automatik semasa dibuka", "zh": "启动时自动检查更新", "es": "Buscar actualizaciones automáticamente al iniciar", "pt": "Verificar atualizações automaticamente ao iniciar"},
    "u_otomatis_bantuan": {"id": "Kalau dimatikan, aplikasi tidak menghubungi internet untuk urusan pembaruan sama sekali. Anda tetap bisa memeriksa manual kapan saja.", "en": "When off, the app never contacts the internet for updates. You can still check manually at any time.", "ms": "Jika dimatikan, aplikasi langsung tidak menghubungi internet untuk kemas kini. Anda masih boleh menyemak secara manual bila-bila masa.", "zh": "关闭后，应用完全不会为更新联网。您仍可随时手动检查。", "es": "Si se desactiva, la aplicación no contacta con internet para actualizaciones. Puedes comprobarlo manualmente cuando quieras.", "pt": "Se desativado, o aplicativo não acessa a internet para atualizações. Você ainda pode verificar manualmente quando quiser."},
    "u_mati": {"id": "Pemeriksaan otomatis dimatikan. Aplikasi tidak menghubungi GitHub sampai Anda menekan tombol di atas.", "en": "Automatic checking is off. The app will not contact GitHub until you press the button above.", "ms": "Semakan automatik dimatikan. Aplikasi tidak akan menghubungi GitHub sehingga anda menekan butang di atas.", "zh": "自动检查已关闭。在您点击上方按钮之前，应用不会连接 GitHub。", "es": "La comprobación automática está desactivada. La aplicación no contactará con GitHub hasta que pulses el botón.", "pt": "A verificação automática está desligada. O aplicativo não acessará o GitHub até você clicar no botão."},
    "u_sekali": {"id": "PERIKSA SEKARANG (SEKALI INI)", "en": "CHECK NOW (THIS TIME ONLY)", "ms": "SEMAK SEKARANG (SEKALI SAHAJA)", "zh": "立即检查（仅此一次）", "es": "COMPROBAR AHORA (SOLO ESTA VEZ)", "pt": "VERIFICAR AGORA (SÓ DESTA VEZ)"},
    "u_tak_bisa": {"id": "TIDAK BISA MEMERIKSA", "en": "CANNOT CHECK", "ms": "TIDAK DAPAT MENYEMAK", "zh": "无法检查", "es": "NO SE PUEDE COMPROBAR", "pt": "NÃO FOI POSSÍVEL VERIFICAR"},
    "u_tak_bisa_teks": {"id": "Ini bukan masalah besar — aplikasi tetap berjalan normal. Anda juga selalu bisa mengunduh versi terbaru secara manual dari halaman rilis.", "en": "This is not serious — the app keeps working normally. You can always download the latest version manually from the releases page.", "ms": "Ini bukan masalah besar — aplikasi tetap berjalan seperti biasa. Anda juga boleh memuat turun versi terkini secara manual.", "zh": "这不是大问题——应用仍可正常使用。您也可以随时从发布页面手动下载最新版本。", "es": "No es grave: la aplicación sigue funcionando con normalidad. Siempre puedes descargar la última versión desde la página de releases.", "pt": "Não é grave — o aplicativo continua funcionando normalmente. Você sempre pode baixar a versão mais recente na página de releases."},
    "u_terbaru": {"id": "SUDAH VERSI TERBARU", "en": "UP TO DATE", "ms": "SUDAH VERSI TERKINI", "zh": "已是最新版本", "es": "ESTÁ ACTUALIZADO", "pt": "ESTÁ ATUALIZADO"},
    "u_terbaru_teks": {"id": "Versi terbaru yang tersedia sama dengan yang terpasang di sini.", "en": "The latest available version is the same as the one installed here.", "ms": "Versi terkini yang tersedia sama dengan yang dipasang di sini.", "zh": "可用的最新版本与本机安装的版本相同。", "es": "La última versión disponible es la misma que tienes instalada.", "pt": "A versão mais recente disponível é a mesma que está instalada aqui."},
    "u_tersedia": {"id": "TERSEDIA PEMBARUAN", "en": "UPDATE AVAILABLE", "ms": "KEMAS KINI TERSEDIA", "zh": "有可用更新", "es": "ACTUALIZACIÓN DISPONIBLE", "pt": "ATUALIZAÇÃO DISPONÍVEL"},
    "u_dirilis": {"id": "dirilis", "en": "released", "ms": "dikeluarkan", "zh": "发布于", "es": "publicado", "pt": "lançado em"},
    "u_tanpa_catatan": {"id": "Tidak ada keterangan perubahan.", "en": "No change notes provided.", "ms": "Tiada nota perubahan.", "zh": "没有提供更新说明。", "es": "Sin notas de cambios.", "pt": "Sem notas de alteração."},
    "u_berkas": {"id": "Berkas", "en": "File", "ms": "Fail", "zh": "文件", "es": "Archivo", "pt": "Arquivo"},
    "u_diizinkan": {"id": "Diizinkan", "en": "Allowed", "ms": "Dibenarkan", "zh": "是否允许", "es": "Permitido", "pt": "Permitido"},
    "u_ya": {"id": "ya", "en": "yes", "ms": "ya", "zh": "是", "es": "sí", "pt": "sim"},
    "u_tidak": {"id": "TIDAK", "en": "NO", "ms": "TIDAK", "zh": "否", "es": "NO", "pt": "NÃO"},
    "u_sidik": {"id": "Sidik jari (SHA-256)", "en": "Fingerprint (SHA-256)", "ms": "Cap jari (SHA-256)", "zh": "指纹 (SHA-256)", "es": "Huella (SHA-256)", "pt": "Impressão digital (SHA-256)"},
    "u_setuju": {"id": "Saya mengerti berkas aplikasi akan diganti, dan salinan versi sekarang akan disimpan di folder cadangan.", "en": "I understand the application files will be replaced, and a copy of the current version will be saved to the backup folder.", "ms": "Saya faham fail aplikasi akan diganti, dan salinan versi semasa akan disimpan dalam folder sandaran.", "zh": "我了解应用文件将被替换，当前版本的副本会保存到备份文件夹。", "es": "Entiendo que los archivos de la aplicación serán reemplazados y que se guardará una copia de la versión actual en la carpeta de respaldo.", "pt": "Entendo que os arquivos do aplicativo serão substituídos e que uma cópia da versão atual será salva na pasta de backup."},
    "u_pasang": {"id": "UNDUH DAN PASANG PEMBARUAN", "en": "DOWNLOAD AND INSTALL UPDATE", "ms": "MUAT TURUN DAN PASANG KEMAS KINI", "zh": "下载并安装更新", "es": "DESCARGAR E INSTALAR ACTUALIZACIÓN", "pt": "BAIXAR E INSTALAR ATUALIZAÇÃO"},
    "u_mengunduh": {"id": "Mengunduh dan memeriksa sidik jari berkas…", "en": "Downloading and verifying file fingerprints…", "ms": "Memuat turun dan mengesahkan cap jari fail…", "zh": "正在下载并校验文件指纹…", "es": "Descargando y verificando huellas de los archivos…", "pt": "Baixando e verificando as impressões digitais dos arquivos…"},
    "u_restart": {"id": "**Tutup aplikasi lalu jalankan peluncurnya lagi** supaya versi baru benar-benar dipakai. Data Anda di folder data/ tidak tersentuh.", "en": "**Close the app and run the launcher again** so the new version takes effect. Your data in the data/ folder is untouched.", "ms": "**Tutup aplikasi dan jalankan pelancar semula** supaya versi baharu digunakan. Data anda dalam folder data/ tidak disentuh.", "zh": "**请关闭应用并重新运行启动器**，新版本才会生效。您在 data/ 文件夹中的数据不受影响。", "es": "**Cierra la aplicación y vuelve a ejecutar el lanzador** para que la nueva versión surta efecto. Tus datos en la carpeta data/ quedan intactos.", "pt": "**Feche o aplicativo e execute o inicializador novamente** para a nova versão valer. Seus dados na pasta data/ não são tocados."},
    "u_kembali": {"id": "Kembali ke versi sebelumnya", "en": "Roll back to a previous version", "ms": "Kembali ke versi terdahulu", "zh": "回退到先前版本", "es": "Volver a una versión anterior", "pt": "Voltar a uma versão anterior"},
    "u_salinan": {"id": "Salinan tersimpan", "en": "Saved backups", "ms": "Salinan tersimpan", "zh": "已保存的备份", "es": "Copias guardadas", "pt": "Backups salvos"},
    "u_pulihkan": {"id": "KEMBALIKAN VERSI INI", "en": "RESTORE THIS VERSION", "ms": "PULIHKAN VERSI INI", "zh": "恢复此版本", "es": "RESTAURAR ESTA VERSIÓN", "pt": "RESTAURAR ESTA VERSÃO"},
    "u_restart2": {"id": "Tutup aplikasi lalu jalankan peluncurnya lagi.", "en": "Close the app and run the launcher again.", "ms": "Tutup aplikasi dan jalankan pelancar semula.", "zh": "请关闭应用并重新运行启动器。", "es": "Cierra la aplicación y vuelve a ejecutar el lanzador.", "pt": "Feche o aplicativo e execute o inicializador novamente."},
    "f_simbol": {"id": "Simbol saham", "en": "Stock symbol", "ms": "Simbol saham", "zh": "股票代码", "es": "Símbolo de la acción", "pt": "Código da ação"},
    "n_global": {"id": "Global", "en": "Global", "ms": "Global", "zh": "全球", "es": "Global", "pt": "Global"},
    "n_indonesia": {"id": "Indonesia", "en": "Indonesia", "ms": "Indonesia", "zh": "印尼", "es": "Indonesia", "pt": "Indonésia"},
    "n_semua": {"id": "Semua", "en": "All", "ms": "Semua", "zh": "全部", "es": "Todo", "pt": "Tudo"},
    "n_negara": {"id": "Negara", "en": "Country", "ms": "Negara", "zh": "国家", "es": "País", "pt": "País"},
    "tk_judul": {"id": "Yang terbaca dari grafik ini", "en": "What this chart is telling us", "ms": "Apa yang dibaca daripada carta ini", "zh": "这张图表在说什么", "es": "Lo que dice este gráfico", "pt": "O que este gráfico está dizendo"},
    "tk_angka": {"id": "Angka mentahnya", "en": "The raw numbers", "ms": "Angka mentahnya", "zh": "原始数据", "es": "Los números en bruto", "pt": "Os números brutos"},
    "tk_ukuran": {"id": "Ukuran", "en": "Measure", "ms": "Ukuran", "zh": "指标", "es": "Medida", "pt": "Medida"},
    "tk_nilai": {"id": "Nilai", "en": "Value", "ms": "Nilai", "zh": "数值", "es": "Valor", "pt": "Valor"},
    "tk_garis_tren": {"id": "Garis tren", "en": "Trend line", "ms": "Garis arah aliran", "zh": "趋势线", "es": "Línea de tendencia", "pt": "Linha de tendência"},
    "tk_puncak": {"id": "Puncak", "en": "Swing high", "ms": "Puncak", "zh": "波段高点", "es": "Máximo relativo", "pt": "Topo"},
    "tk_lembah": {"id": "Lembah", "en": "Swing low", "ms": "Lembah", "zh": "波段低点", "es": "Mínimo relativo", "pt": "Fundo"},
    "tk_penahan": {"id": "penahan", "en": "resistance", "ms": "rintangan", "zh": "阻力", "es": "resistencia", "pt": "resistência"},
    "tk_sokongan": {"id": "sokongan", "en": "support", "ms": "sokongan", "zh": "支撑", "es": "soporte", "pt": "suporte"},
    "tk_butuh_data": {"id": "Butuh setidaknya 30 batang data untuk dibaca. Coba periode yang lebih panjang.", "en": "At least 30 bars of data are needed. Try a longer period.", "ms": "Sekurang-kurangnya 30 bar data diperlukan. Cuba tempoh yang lebih panjang.", "zh": "至少需要 30 根K线数据。请尝试更长的周期。", "es": "Se necesitan al menos 30 barras de datos. Prueba un periodo más largo.", "pt": "São necessárias pelo menos 30 barras de dados. Tente um período maior."},
    "tk_tren_naik": {"id": "Tren naik", "en": "Uptrend", "ms": "Aliran menaik", "zh": "上升趋势", "es": "Tendencia alcista", "pt": "Tendência de alta"},
    "tk_tren_turun": {"id": "Tren turun", "en": "Downtrend", "ms": "Aliran menurun", "zh": "下降趋势", "es": "Tendencia bajista", "pt": "Tendência de baixa"},
    "tk_cenderung_naik": {"id": "Cenderung naik", "en": "Leaning up", "ms": "Cenderung menaik", "zh": "偏向上行", "es": "Sesgo alcista", "pt": "Viés de alta"},
    "tk_cenderung_turun": {"id": "Cenderung turun", "en": "Leaning down", "ms": "Cenderung menurun", "zh": "偏向下行", "es": "Sesgo bajista", "pt": "Viés de baixa"},
    "tk_menyamping": {"id": "Bergerak menyamping", "en": "Moving sideways", "ms": "Bergerak mendatar", "zh": "横盘整理", "es": "Movimiento lateral", "pt": "Movimento lateral"},
    "tk_kuat_lemah": {"id": "Kekuatan tren lemah — harga cenderung bergerak menyamping.", "en": "Trend strength is weak — price tends to move sideways.", "ms": "Kekuatan aliran lemah — harga cenderung bergerak mendatar.", "zh": "趋势强度偏弱，价格倾向于横盘。", "es": "La fuerza de la tendencia es débil: el precio tiende a moverse de lado.", "pt": "A força da tendência é fraca — o preço tende a andar de lado."},
    "tk_kuat_mulai": {"id": "Kekuatan tren mulai terbentuk, tetapi belum meyakinkan.", "en": "Trend strength is forming, but not yet convincing.", "ms": "Kekuatan aliran mula terbentuk, tetapi belum meyakinkan.", "zh": "趋势强度正在形成，但尚不具说服力。", "es": "La fuerza de la tendencia se está formando, pero aún no convence.", "pt": "A força da tendência está se formando, mas ainda não convence."},
    "tk_kuat_jelas": {"id": "Ada tren yang jelas.", "en": "There is a clear trend.", "ms": "Terdapat aliran yang jelas.", "zh": "存在明确的趋势。", "es": "Hay una tendencia clara.", "pt": "Há uma tendência clara."},
    "tk_kuat_sangat": {"id": "Tren sangat kuat — perlu diingat, tren sekuat ini juga sering mendekati batasnya.", "en": "The trend is very strong — worth remembering that trends this strong are often near their limit.", "ms": "Aliran sangat kuat — perlu diingat, aliran sekuat ini juga sering menghampiri hadnya.", "zh": "趋势非常强劲——但要记住，如此强劲的趋势往往也接近尾声。", "es": "La tendencia es muy fuerte, pero conviene recordar que las tendencias así de fuertes suelen estar cerca de su límite.", "pt": "A tendência está muito forte — vale lembrar que tendências assim costumam estar perto do limite."},
    "tk_posisi_atas": {"id": "Harga berada di atas {n} dari {total} rata-rata ({daftar}). ", "en": "Price is above {n} of {total} moving averages ({daftar}). ", "ms": "Harga berada di atas {n} daripada {total} purata bergerak ({daftar}). ", "zh": "价格位于 {total} 条均线中 {n} 条之上（{daftar}）。", "es": "El precio está por encima de {n} de {total} medias móviles ({daftar}). ", "pt": "O preço está acima de {n} de {total} médias móveis ({daftar}). "},
    "tk_posisi_bawah": {"id": "Harga berada di bawah seluruh rata-rata bergerak. ", "en": "Price is below every moving average. ", "ms": "Harga berada di bawah semua purata bergerak. ", "zh": "价格位于所有均线之下。", "es": "El precio está por debajo de todas las medias móviles. ", "pt": "O preço está abaixo de todas as médias móveis. "},
    "tk_garis_lurus": {"id": "Garis tren terbaik menunjukkan laju sekitar {laju:+.0f}% per tahun, dengan keteraturan {andal:.0f}% — makin tinggi angka itu, makin rapi harga mengikuti garisnya.", "en": "The best-fit trend line implies roughly {laju:+.0f}% per year, with {andal:.0f}% regularity — the higher that figure, the more closely price has hugged the line.", "ms": "Garis aliran terbaik menunjukkan kadar kira-kira {laju:+.0f}% setahun, dengan keteraturan {andal:.0f}% — makin tinggi angka itu, makin rapi harga mengikuti garisnya.", "zh": "最佳拟合趋势线显示年化约 {laju:+.0f}%，规整度 {andal:.0f}%——该数值越高，价格贴合这条线越紧密。", "es": "La línea de tendencia ajustada implica alrededor de {laju:+.0f}% anual, con {andal:.0f}% de regularidad: cuanto mayor sea esa cifra, más se ha ceñido el precio a la línea.", "pt": "A linha de tendência ajustada indica cerca de {laju:+.0f}% ao ano, com {andal:.0f}% de regularidade — quanto maior esse número, mais o preço seguiu a linha."},
    "tk_emas": {"id": "Perpotongan emas", "en": "Golden cross", "ms": "Silangan emas", "zh": "黄金交叉", "es": "Cruce dorado", "pt": "Cruzamento dourado"},
    "tk_maut": {"id": "Perpotongan maut", "en": "Death cross", "ms": "Silangan maut", "zh": "死亡交叉", "es": "Cruce de la muerte", "pt": "Cruzamento da morte"},
    "tk_emas_isi": {"id": "MA50 memotong ke atas MA200 pada {tgl}. Pola ini sering disebut awal tren naik. Perlu jujur dikatakan: karena dihitung dari rata-rata panjang, sinyalnya selalu datang terlambat, dan cukup sering keliru.", "en": "MA50 crossed above MA200 on {tgl}. This pattern is often called the start of an uptrend. Honestly stated: because it is built from long averages, the signal always arrives late, and is wrong often enough to matter.", "ms": "MA50 memotong ke atas MA200 pada {tgl}. Corak ini sering disebut permulaan aliran menaik. Perlu dinyatakan dengan jujur: kerana dikira daripada purata panjang, isyaratnya sentiasa lewat dan agak kerap tersilap.", "zh": "MA50 于 {tgl} 上穿 MA200。这一形态常被称作上升趋势的开始。但需要坦白说：由于基于长周期均线计算，该信号总是滞后，且出错的频率不低。", "es": "La MA50 cruzó por encima de la MA200 el {tgl}. Este patrón suele señalarse como el inicio de una tendencia alcista. Con honestidad: al construirse con medias largas, la señal siempre llega tarde y falla con bastante frecuencia.", "pt": "A MM50 cruzou acima da MM200 em {tgl}. Esse padrão costuma ser chamado de início de alta. Sendo honesto: por ser calculado com médias longas, o sinal sempre chega atrasado e erra com frequência."},
    "tk_maut_isi": {"id": "MA50 memotong ke bawah MA200 pada {tgl}. Sama seperti kembarannya, pola ini terlambat dan sering meleset — terutama pada saham yang bergerak liar.", "en": "MA50 crossed below MA200 on {tgl}. Like its twin, this pattern is late and often wrong — especially on volatile names.", "ms": "MA50 memotong ke bawah MA200 pada {tgl}. Sama seperti kembarnya, corak ini lewat dan sering tersasar — terutamanya pada saham yang bergerak liar.", "zh": "MA50 于 {tgl} 下穿 MA200。与其孪生形态一样，这个信号滞后且经常出错——在波动剧烈的标的上尤其如此。", "es": "La MA50 cruzó por debajo de la MA200 el {tgl}. Como su gemelo, este patrón llega tarde y suele fallar, sobre todo en valores volátiles.", "pt": "A MM50 cruzou abaixo da MM200 em {tgl}. Como seu gêmeo, esse padrão chega atrasado e erra bastante — especialmente em ativos voláteis."},
    "tk_momentum": {"id": "Momentum", "en": "Momentum", "ms": "Momentum", "zh": "动能", "es": "Momento", "pt": "Momento"},
    "tk_rsi_tinggi": {"id": "RSI {rsi:.0f} — masuk wilayah yang biasa disebut jenuh beli. Perlu dicatat, pada tren naik yang kuat RSI bisa bertahan tinggi berminggu-minggu tanpa harga turun.", "en": "RSI {rsi:.0f} — in what is usually called overbought territory. Worth noting: in a strong uptrend, RSI can stay high for weeks without price falling.", "ms": "RSI {rsi:.0f} — memasuki kawasan yang biasa disebut terlebih beli. Perlu dicatat, dalam aliran menaik yang kuat RSI boleh kekal tinggi berminggu-minggu tanpa harga jatuh.", "zh": "RSI {rsi:.0f}——进入通常所说的超买区间。需要注意：在强劲上升趋势中，RSI 可以连续数周维持高位而价格不跌。", "es": "RSI {rsi:.0f}: en lo que suele llamarse zona de sobrecompra. Conviene notar que en una tendencia alcista fuerte el RSI puede quedarse alto semanas sin que el precio caiga.", "pt": "RSI {rsi:.0f} — no que costuma se chamar de zona de sobrecompra. Vale notar: em alta forte, o RSI pode ficar elevado por semanas sem o preço cair."},
    "tk_rsi_rendah": {"id": "RSI {rsi:.0f} — wilayah jenuh jual. Ini menggambarkan tekanan jual yang deras, bukan jaminan harga akan berbalik.", "en": "RSI {rsi:.0f} — oversold territory. This describes heavy selling pressure, not a guarantee that price will turn.", "ms": "RSI {rsi:.0f} — kawasan terlebih jual. Ini menggambarkan tekanan jualan yang deras, bukan jaminan harga akan berbalik.", "zh": "RSI {rsi:.0f}——超卖区间。这描述的是沉重的卖压，而非价格必将反转的保证。", "es": "RSI {rsi:.0f}: zona de sobreventa. Describe una fuerte presión vendedora, no una garantía de giro.", "pt": "RSI {rsi:.0f} — zona de sobrevenda. Isso descreve forte pressão vendedora, não garantia de reversão."},
    "tk_rsi_tengah": {"id": "RSI {rsi:.0f} — di wilayah tengah, tidak menunjukkan tekanan berlebihan.", "en": "RSI {rsi:.0f} — mid-range, showing no excessive pressure either way.", "ms": "RSI {rsi:.0f} — di kawasan tengah, tiada tekanan berlebihan.", "zh": "RSI {rsi:.0f}——处于中间区域，未显示任何一方的过度压力。", "es": "RSI {rsi:.0f}: en zona media, sin presión excesiva en ningún sentido.", "pt": "RSI {rsi:.0f} — em zona intermediária, sem pressão excessiva."},
    "tk_rsi_gerak": {"id": " Lima hari terakhir bergerak {beda:+.0f} poin.", "en": " It has moved {beda:+.0f} points over the last five bars.", "ms": " Lima bar terakhir bergerak {beda:+.0f} mata.", "zh": " 最近五根K线变动 {beda:+.0f} 点。", "es": " Se ha movido {beda:+.0f} puntos en las últimas cinco barras.", "pt": " Moveu {beda:+.0f} pontos nas últimas cinco barras."},
    "tk_macd": {"id": "Arah dorongan (MACD)", "en": "Momentum direction (MACD)", "ms": "Arah dorongan (MACD)", "zh": "动能方向 (MACD)", "es": "Dirección del impulso (MACD)", "pt": "Direção do impulso (MACD)"},
    "tk_macd_atas": {"id": "di atas", "en": "above", "ms": "di atas", "zh": "上方", "es": "por encima de", "pt": "acima"},
    "tk_macd_bawah": {"id": "di bawah", "en": "below", "ms": "di bawah", "zh": "下方", "es": "por debajo de", "pt": "abaixo"},
    "tk_macd_isi": {"id": "MACD berada {posisi} garis sinyalnya, dan selisihnya sedang {arah}. ", "en": "MACD sits {posisi} its signal line, and the gap is {arah}. ", "ms": "MACD berada {posisi} garis isyaratnya, dan jurangnya sedang {arah}. ", "zh": "MACD 位于信号线{posisi}，两者差距正在{arah}。", "es": "El MACD está {posisi} su línea de señal, y la brecha se está {arah}. ", "pt": "O MACD está {posisi} da linha de sinal, e a diferença está {arah}. "},
    "tk_macd_melebar": {"id": "melebar", "en": "widening", "ms": "melebar", "zh": "扩大", "es": "ampliando", "pt": "aumentando"},
    "tk_macd_menyempit": {"id": "menyempit", "en": "narrowing", "ms": "menyempit", "zh": "收窄", "es": "estrechando", "pt": "diminuindo"},
    "tk_macd_naik_tambah": {"id": "Dorongan naik sedang bertambah.", "en": "Upward momentum is building.", "ms": "Dorongan menaik sedang bertambah.", "zh": "上行动能正在增强。", "es": "El impulso alcista está aumentando.", "pt": "O impulso de alta está aumentando."},
    "tk_macd_naik_kurang": {"id": "Dorongan naik masih ada tetapi mulai berkurang.", "en": "Upward momentum is still there but fading.", "ms": "Dorongan menaik masih ada tetapi mula berkurang.", "zh": "上行动能仍在，但开始减弱。", "es": "El impulso alcista sigue, pero se está desvaneciendo.", "pt": "O impulso de alta ainda existe, mas está enfraquecendo."},
    "tk_macd_turun_tambah": {"id": "Tekanan turun sedang bertambah.", "en": "Downward pressure is building.", "ms": "Tekanan menurun sedang bertambah.", "zh": "下行压力正在加大。", "es": "La presión bajista está aumentando.", "pt": "A pressão de baixa está aumentando."},
    "tk_macd_turun_reda": {"id": "Tekanan turun masih ada tetapi mulai mereda.", "en": "Downward pressure is still there but easing.", "ms": "Tekanan menurun masih ada tetapi mula reda.", "zh": "下行压力仍在，但开始缓解。", "es": "La presión bajista sigue, pero se está aliviando.", "pt": "A pressão de baixa ainda existe, mas está diminuindo."},
    "tk_gejolak": {"id": "Gejolak", "en": "Volatility", "ms": "Kemeruapan", "zh": "波动性", "es": "Volatilidad", "pt": "Volatilidade"},
    "tk_atr_isi": {"id": "Rentang gerak harian rata-rata {p:.2f}% dari harga (ATR {atr}). ", "en": "Average daily range is {p:.2f}% of price (ATR {atr}). ", "ms": "Julat pergerakan harian purata {p:.2f}% daripada harga (ATR {atr}). ", "zh": "日均波动幅度为价格的 {p:.2f}%（ATR {atr}）。", "es": "El rango diario medio es {p:.2f}% del precio (ATR {atr}). ", "pt": "A amplitude diária média é {p:.2f}% do preço (ATR {atr}). "},
    "tk_boll_sempit": {"id": "Pita Bollinger sedang menyempit — lebih rapat daripada {p:.0f}% hari dalam setahun terakhir. Penyempitan sering mendahului pergerakan besar, tetapi tidak memberi tahu ke arah mana.", "en": "Bollinger Bands are narrowing — tighter than on {p:.0f}% of days in the past year. Squeezes often precede large moves, but say nothing about direction.", "ms": "Jalur Bollinger sedang menyempit — lebih ketat daripada {p:.0f}% hari dalam setahun lalu. Penyempitan sering mendahului pergerakan besar, tetapi tidak memberitahu arahnya.", "zh": "布林带正在收窄——比过去一年中 {p:.0f}% 的交易日更窄。收窄常常先于大幅波动出现，但并不指明方向。", "es": "Las Bandas de Bollinger se están estrechando: más que en el {p:.0f}% de los días del último año. Los estrechamientos suelen preceder movimientos grandes, pero no dicen la dirección.", "pt": "As Bandas de Bollinger estão se estreitando — mais do que em {p:.0f}% dos dias do último ano. Compressões costumam anteceder movimentos grandes, mas não indicam a direção."},
    "tk_boll_lebar": {"id": "Pita Bollinger sedang melebar — lebih lebar daripada {p:.0f}% hari dalam setahun terakhir. Pasar sedang bergejolak.", "en": "Bollinger Bands are widening — wider than on {p:.0f}% of days in the past year. The market is turbulent.", "ms": "Jalur Bollinger sedang melebar — lebih lebar daripada {p:.0f}% hari dalam setahun lalu. Pasaran sedang bergolak.", "zh": "布林带正在扩张——比过去一年中 {p:.0f}% 的交易日更宽。市场处于动荡之中。", "es": "Las Bandas de Bollinger se están ampliando: más que en el {p:.0f}% de los días del último año. El mercado está turbulento.", "pt": "As Bandas de Bollinger estão se alargando — mais do que em {p:.0f}% dos dias do último ano. O mercado está turbulento."},
    "tk_boll_normal": {"id": "Gejolak berada di kisaran normalnya.", "en": "Volatility is in its normal range.", "ms": "Kemeruapan berada dalam julat normalnya.", "zh": "波动性处于正常区间。", "es": "La volatilidad está en su rango normal.", "pt": "A volatilidade está na faixa normal."},
    "tk_volume": {"id": "Volume", "en": "Volume", "ms": "Volum", "zh": "成交量", "es": "Volumen", "pt": "Volume"},
    "tk_vol_besar": {"id": "Volume hari terakhir {r:.1f} kali rata-rata 20 hari. Pergerakan yang disertai volume besar umumnya dianggap lebih meyakinkan daripada yang sepi.", "en": "Latest volume is {r:.1f}× the 20-day average. Moves backed by heavy volume are generally considered more convincing than quiet ones.", "ms": "Volum hari terakhir {r:.1f} kali purata 20 hari. Pergerakan yang disertai volum besar umumnya dianggap lebih meyakinkan.", "zh": "最新成交量为 20 日均量的 {r:.1f} 倍。放量伴随的走势，通常被认为比缩量走势更可信。", "es": "El volumen más reciente es {r:.1f}× la media de 20 días. Los movimientos con volumen alto suelen considerarse más convincentes que los tranquilos.", "pt": "O volume mais recente é {r:.1f}× a média de 20 dias. Movimentos com volume forte costumam ser considerados mais convincentes."},
    "tk_vol_kecil": {"id": "Volume hanya {r:.1f} kali rata-rata 20 hari. Pergerakan harga dalam kondisi sepi lebih mudah berbalik.", "en": "Volume is only {r:.1f}× the 20-day average. Price moves on thin volume reverse more easily.", "ms": "Volum hanya {r:.1f} kali purata 20 hari. Pergerakan harga dalam keadaan sepi lebih mudah berbalik.", "zh": "成交量仅为 20 日均量的 {r:.1f} 倍。缩量下的价格变动更容易反转。", "es": "El volumen es solo {r:.1f}× la media de 20 días. Los movimientos con poco volumen se revierten con más facilidad.", "pt": "O volume é apenas {r:.1f}× a média de 20 dias. Movimentos com volume fraco revertem mais facilmente."},
    "tk_vol_wajar": {"id": "Volume {r:.1f} kali rata-rata 20 hari — wajar.", "en": "Volume is {r:.1f}× the 20-day average — unremarkable.", "ms": "Volum {r:.1f} kali purata 20 hari — biasa.", "zh": "成交量为 20 日均量的 {r:.1f} 倍——属正常水平。", "es": "El volumen es {r:.1f}× la media de 20 días: nada destacable.", "pt": "O volume é {r:.1f}× a média de 20 dias — nada notável."},
    "tk_level": {"id": "Level penting", "en": "Key levels", "ms": "Aras penting", "zh": "关键价位", "es": "Niveles clave", "pt": "Níveis-chave"},
    "tk_level_awal": {"id": "Dari puncak dan lembah sebelumnya: ", "en": "From prior swing highs and lows: ", "ms": "Daripada puncak dan lembah terdahulu: ", "zh": "根据此前的波段高低点：", "es": "A partir de máximos y mínimos previos: ", "pt": "A partir de topos e fundos anteriores: "},
    "tk_level_sok": {"id": "sokongan terdekat di {h} ({j:+.1f}%, {n} kali disentuh)", "en": "nearest support at {h} ({j:+.1f}%, touched {n}×)", "ms": "sokongan terdekat pada {h} ({j:+.1f}%, disentuh {n} kali)", "zh": "最近支撑位 {h}（{j:+.1f}%，被触及 {n} 次）", "es": "soporte más cercano en {h} ({j:+.1f}%, tocado {n} veces)", "pt": "suporte mais próximo em {h} ({j:+.1f}%, tocado {n}×)"},
    "tk_level_res": {"id": "penahan terdekat di {h} ({j:+.1f}%, {n} kali disentuh)", "en": "nearest resistance at {h} ({j:+.1f}%, touched {n}×)", "ms": "rintangan terdekat pada {h} ({j:+.1f}%, disentuh {n} kali)", "zh": "最近阻力位 {h}（{j:+.1f}%，被触及 {n} 次）", "es": "resistencia más cercana en {h} ({j:+.1f}%, tocada {n} veces)", "pt": "resistência mais próxima em {h} ({j:+.1f}%, tocada {n}×)"},
    "tk_level_akhir": {"id": ". Level ini bukan dinding — ia hanya harga yang dulu sempat menghentikan pergerakan, dan bisa saja ditembus.", "en": ". These are not walls — merely prices that once halted a move, and they can be broken.", "ms": ". Aras ini bukan dinding — ia hanya harga yang pernah menghentikan pergerakan, dan boleh ditembusi.", "zh": "。这些不是墙——它们只是曾经让走势停下的价格，随时可能被突破。", "es": ". No son muros: solo precios que en su día frenaron un movimiento, y pueden romperse.", "pt": ". Não são paredes — apenas preços que já interromperam um movimento, e podem ser rompidos."},
    "tk_posisi52": {"id": "Posisi setahun", "en": "Position in the year", "ms": "Kedudukan setahun", "zh": "年度区间位置", "es": "Posición en el año", "pt": "Posição no ano"},
    "tk_posisi52_isi": {"id": "Harga berada {letak:.0f}% dari dasar rentang 52 minggu ({bawah} sampai {atas}), {dari:+.1f}% dari puncaknya.", "en": "Price sits {letak:.0f}% up from the bottom of its 52-week range ({bawah} to {atas}), {dari:+.1f}% from the high.", "ms": "Harga berada {letak:.0f}% dari dasar julat 52 minggu ({bawah} hingga {atas}), {dari:+.1f}% daripada puncaknya.", "zh": "价格位于 52 周区间（{bawah} 至 {atas}）自底部起 {letak:.0f}% 处，距高点 {dari:+.1f}%。", "es": "El precio está {letak:.0f}% por encima del mínimo de su rango de 52 semanas ({bawah} a {atas}), a {dari:+.1f}% del máximo.", "pt": "O preço está {letak:.0f}% acima do fundo da faixa de 52 semanas ({bawah} a {atas}), a {dari:+.1f}% da máxima."},
    "w_data_kombinasi": {"id": "Data tidak tersedia untuk kombinasi ini. Coba periode atau interval lain.", "en": "No data for this combination. Try a different period or interval.", "ms": "Tiada data untuk gabungan ini. Cuba tempoh atau selang lain.", "zh": "该组合没有数据。请尝试其他周期或间隔。", "es": "No hay datos para esta combinación. Prueba otro periodo o intervalo.", "pt": "Sem dados para esta combinação. Tente outro período ou intervalo."},
    "w_tak_tersedia": {"id": "Data tidak tersedia untuk kombinasi ini.", "en": "No data available for this combination.", "ms": "Tiada data untuk gabungan ini.", "zh": "该组合暂无数据。", "es": "No hay datos para esta combinación.", "pt": "Sem dados para esta combinação."},
    "w_harga_gagal": {"id": "Harga tidak bisa diambil sekarang. Periksa koneksi internet Anda.", "en": "Prices are unavailable right now. Check your internet connection.", "ms": "Harga tidak dapat diambil sekarang. Periksa sambungan internet anda.", "zh": "当前无法获取价格。请检查网络连接。", "es": "No se pueden obtener precios ahora. Revisa tu conexión.", "pt": "Não foi possível obter preços agora. Verifique sua conexão."},
    "w_pasar_gagal": {"id": "Harga pasar tidak bisa diambil. Periksa koneksi internet Anda.", "en": "Market prices are unavailable. Check your internet connection.", "ms": "Harga pasaran tidak dapat diambil. Periksa sambungan internet anda.", "zh": "无法获取市场价格。请检查网络连接。", "es": "No se pueden obtener precios de mercado. Revisa tu conexión.", "pt": "Não foi possível obter preços de mercado. Verifique sua conexão."},
    "w_berita_gagal": {"id": "Tidak ada berita yang bisa diambil. Periksa koneksi internet Anda.", "en": "No news could be fetched. Check your internet connection.", "ms": "Tiada berita dapat diambil. Periksa sambungan internet anda.", "zh": "无法获取新闻。请检查网络连接。", "es": "No se pudieron obtener noticias. Revisa tu conexión.", "pt": "Não foi possível obter notícias. Verifique sua conexão."},
    "w_kripto_gagal2": {"id": "Data pasar kripto tidak bisa diambil sekarang. CoinGecko membatasi permintaan gratis — coba lagi sebentar lagi.", "en": "Crypto market data is unavailable right now. CoinGecko rate-limits free usage — try again shortly.", "ms": "Data pasaran kripto tidak dapat diambil sekarang. CoinGecko mengehadkan permintaan percuma — cuba lagi sebentar.", "zh": "当前无法获取加密市场数据。CoinGecko 对免费使用有频率限制，请稍后再试。", "es": "Los datos del mercado cripto no están disponibles. CoinGecko limita el uso gratuito: inténtalo en un momento.", "pt": "Dados do mercado cripto indisponíveis. O CoinGecko limita o uso gratuito — tente novamente em instantes."},
    "w_muat_ulang": {"id": "Data tidak bisa diambil sekarang. Periksa koneksi internet Anda, lalu tekan MUAT ULANG.", "en": "Data unavailable right now. Check your internet connection, then press RELOAD.", "ms": "Data tidak dapat diambil sekarang. Periksa sambungan internet anda, kemudian tekan MUAT SEMULA.", "zh": "当前无法获取数据。请检查网络连接后点击刷新。", "es": "Datos no disponibles. Revisa tu conexión y pulsa RECARGAR.", "pt": "Dados indisponíveis. Verifique sua conexão e clique em RECARREGAR."},
    "w_ma_urutan": {"id": "Rata-rata cepat harus lebih pendek daripada yang lambat.", "en": "The fast average must be shorter than the slow one.", "ms": "Purata pantas mesti lebih pendek daripada yang perlahan.", "zh": "快速均线的周期必须短于慢速均线。", "es": "La media rápida debe ser más corta que la lenta.", "pt": "A média rápida deve ser mais curta que a lenta."},
    "w_emiten_hilang": {"id": "tidak ditemukan. Periksa penulisan simbolnya — saham Indonesia butuh akhiran .JK", "en": "not found. Check the symbol spelling — Indonesian stocks need the .JK suffix.", "ms": "tidak dijumpai. Periksa ejaan simbol — saham Indonesia perlu akhiran .JK", "zh": "未找到。请检查代码拼写——印尼股票需要 .JK 后缀。", "es": "no encontrado. Revisa el símbolo: las acciones de Indonesia necesitan el sufijo .JK", "pt": "não encontrado. Verifique o símbolo — ações da Indonésia precisam do sufixo .JK"},
    "w_laporan_hilang": {"id": "Laporan ini tidak tersedia untuk emiten tersebut.", "en": "This statement is not available for that company.", "ms": "Penyata ini tidak tersedia untuk syarikat tersebut.", "zh": "该公司没有这份报表。", "es": "Este estado no está disponible para esa empresa.", "pt": "Esta demonstração não está disponível para essa empresa."},
    "c_satuan": {"id": "Satuan: rb = ribu · jt = juta · M = miliar · T = triliun, dalam mata uang pelaporan emiten.", "en": "Units: rb = thousand · jt = million · M = billion · T = trillion, in the company's reporting currency.", "ms": "Unit: rb = ribu · jt = juta · M = bilion · T = trilion, dalam mata wang pelaporan syarikat.", "zh": "单位：rb = 千 · jt = 百万 · M = 十亿 · T = 万亿，以公司报表币种计。", "es": "Unidades: rb = mil · jt = millón · M = mil millones · T = billón, en la moneda de reporte de la empresa.", "pt": "Unidades: rb = mil · jt = milhão · M = bilhão · T = trilhão, na moeda de reporte da empresa."},
    "c_indikator": {"id": "Indikator teknikal menggambarkan apa yang <i>sudah</i> terjadi pada harga. Ia tidak meramal apa pun. Perlakukan sebagai ringkasan visual, bukan sinyal beli-jual.", "en": "Technical indicators describe what has <i>already</i> happened to price. They forecast nothing. Treat them as a visual summary, not a buy or sell signal.", "ms": "Penunjuk teknikal menggambarkan apa yang <i>sudah</i> berlaku pada harga. Ia tidak meramal apa-apa. Anggap ia ringkasan visual, bukan isyarat beli-jual.", "zh": "技术指标描述的是价格<i>已经</i>发生的事情，它们不预测任何东西。请把它们当作视觉摘要，而非买卖信号。", "es": "Los indicadores técnicos describen lo que <i>ya</i> ocurrió con el precio. No pronostican nada. Trátalos como un resumen visual, no como señal de compra o venta.", "pt": "Indicadores técnicos descrevem o que <i>já</i> aconteceu com o preço. Eles não preveem nada. Trate-os como resumo visual, não como sinal de compra ou venda."},
    "c_denyut_kartu": {"id": "Garis di tiap kartu menggambarkan pergerakan 30 hari terakhir. Bursa yang sedang tutup menampilkan harga penutupan terakhir.", "en": "The line on each card shows the last 30 days of movement. Exchanges that are closed show their most recent close.", "ms": "Garis pada setiap kad menunjukkan pergerakan 30 hari terakhir. Bursa yang tutup memaparkan harga penutup terakhir.", "zh": "每张卡片上的曲线显示最近 30 天的走势。已收盘的市场显示最新收盘价。", "es": "La línea de cada tarjeta muestra los últimos 30 días. Los mercados cerrados muestran su último cierre.", "pt": "A linha em cada cartão mostra os últimos 30 dias. Bolsas fechadas exibem o último fechamento."},
    "c_kurs_pasar": {"id": "Emas dan perak dalam dolar per troy ounce, minyak per barel. Kurs yang tampil adalah kurs pasar, bukan kurs jual-beli bank.", "en": "Gold and silver in dollars per troy ounce, oil per barrel. Rates shown are market rates, not bank buy-sell rates.", "ms": "Emas dan perak dalam dolar per auns troy, minyak per tong. Kadar yang dipaparkan ialah kadar pasaran, bukan kadar jual-beli bank.", "zh": "黄金与白银以美元/金衡盎司计价，原油以桶计价。所示汇率为市场汇率，非银行买卖价。", "es": "Oro y plata en dólares por onza troy, petróleo por barril. Las cotizaciones son de mercado, no precios de compraventa bancarios.", "pt": "Ouro e prata em dólares por onça troy, petróleo por barril. As cotações são de mercado, não taxas de compra e venda de banco."},
    "c_forex_baca": {"id": "Membaca kuotasi: <b>EUR / USD 1,0850</b> berarti satu euro dihargai 1,0850 dolar. Mata uang di depan disebut dasar, yang di belakang disebut kutipan. Naiknya angka berarti mata uang dasar menguat.<br><br>Harga di sini adalah kurs pasar antarbank, bukan kurs money changer — yang selalu lebih lebar.", "en": "Reading a quote: <b>EUR / USD 1.0850</b> means one euro costs 1.0850 dollars. The front currency is the base, the back one the quote. A rising number means the base currency is strengthening.<br><br>These are interbank market rates, not money-changer rates — which are always wider.", "ms": "Membaca sebut harga: <b>EUR / USD 1.0850</b> bermakna satu euro berharga 1.0850 dolar. Mata wang di hadapan ialah asas, yang di belakang ialah sebutan. Angka yang naik bermakna mata wang asas menguat.<br><br>Ini kadar pasaran antara bank, bukan kadar pengurup wang yang sentiasa lebih lebar.", "zh": "读懂报价：<b>EUR / USD 1.0850</b> 表示 1 欧元值 1.0850 美元。前面的货币叫基础货币，后面的叫计价货币。数字上升意味着基础货币走强。<br><br>此处为银行间市场汇率，并非货币兑换商的报价——后者点差总是更宽。", "es": "Cómo leer una cotización: <b>EUR / USD 1,0850</b> significa que un euro cuesta 1,0850 dólares. La primera divisa es la base, la segunda la cotizada. Si el número sube, la base se fortalece.<br><br>Son tipos del mercado interbancario, no de casas de cambio, que siempre son más amplios.", "pt": "Como ler uma cotação: <b>EUR / USD 1,0850</b> significa que um euro custa 1,0850 dólares. A primeira moeda é a base, a segunda é a cotada. Número subindo significa base se fortalecendo.<br><br>São taxas do mercado interbancário, não de casas de câmbio, que sempre têm spread maior."},
    "c_dari_puncak": {"id": "Kolom <b>Dari puncak</b> menunjukkan jarak harga sekarang terhadap harga tertinggi sepanjang sejarah koin itu. Angka −90% berarti koin perlu naik sepuluh kali lipat hanya untuk kembali ke titik semula.", "en": "The <b>From ATH</b> column shows how far price sits from that coin's all-time high. A figure of −90% means the coin must rise tenfold just to return to where it was.", "ms": "Lajur <b>Dari puncak</b> menunjukkan jarak harga semasa daripada harga tertinggi sepanjang sejarah syiling itu. Angka −90% bermakna syiling perlu naik sepuluh kali ganda hanya untuk kembali ke titik asal.", "zh": "<b>距历史高点</b>一列显示当前价格与该币历史最高价的距离。−90% 意味着该币需要上涨十倍，才能回到原点。", "es": "La columna <b>Desde máximos</b> muestra cuán lejos está el precio de su máximo histórico. Un −90% significa que la moneda debe multiplicarse por diez solo para volver al punto de partida.", "pt": "A coluna <b>Da máxima</b> mostra a distância do preço até a máxima histórica da moeda. Um −90% significa que ela precisa subir dez vezes só para voltar ao ponto de partida."},
    "t_ikhtisar": {"id": "Ikhtisar", "en": "Overview", "ms": "Ikhtisar", "zh": "总览", "es": "Panorama", "pt": "Panorama"},
    "ik_ringkas": {"id": "RINGKASAN HARI INI", "en": "TODAY IN ONE PARAGRAPH", "ms": "RINGKASAN HARI INI", "zh": "今日一览", "es": "HOY EN UN PÁRRAFO", "pt": "HOJE EM UM PARÁGRAFO"},
    "ik_menguat": {"id": "menguat", "en": "up", "ms": "menguat", "zh": "上涨", "es": "al alza", "pt": "em alta"},
    "ik_melemah": {"id": "melemah", "en": "down", "ms": "melemah", "zh": "下跌", "es": "a la baja", "pt": "em baixa"},
    "ik_dari_total": {"id": "dari", "en": "out of", "ms": "daripada", "zh": "，共", "es": "de", "pt": "de"},
    "ik_dipimpin": {"id": "Dipimpin", "en": "Led by", "ms": "Dipimpin", "zh": "领涨的是", "es": "Lidera", "pt": "Puxado por"},
    "ik_tertinggal": {"id": "tertinggal", "en": "and trailed by", "ms": "tertinggal", "zh": "，垫底的是", "es": "y cierra", "pt": "e na lanterna"},
    "ik_serempak_naik": {"id": "Hampir semuanya bergerak searah ke atas — ini kabar tentang pasar, bukan tentang satu aset.", "en": "Almost everything moved the same way, upward — that says something about the market, not about any one asset.", "ms": "Hampir semuanya bergerak searah ke atas — ini berita tentang pasaran, bukan tentang satu aset.", "zh": "几乎所有品种同向上涨——这说明的是市场，而不是某一个标的。", "es": "Casi todo se movió en la misma dirección, al alza: eso habla del mercado, no de un activo concreto.", "pt": "Quase tudo se moveu na mesma direção, para cima — isso diz respeito ao mercado, não a um ativo isolado."},
    "ik_serempak_turun": {"id": "Hampir semuanya bergerak searah ke bawah — ini kabar tentang pasar, bukan tentang satu aset.", "en": "Almost everything moved the same way, downward — that says something about the market, not about any one asset.", "ms": "Hampir semuanya bergerak searah ke bawah — ini berita tentang pasaran, bukan tentang satu aset.", "zh": "几乎所有品种同向下跌——这说明的是市场，而不是某一个标的。", "es": "Casi todo se movió en la misma dirección, a la baja: eso habla del mercado, no de un activo concreto.", "pt": "Quase tudo se moveu na mesma direção, para baixo — isso diz respeito ao mercado, não a um ativo isolado."},
    "ik_berpencar": {"id": "Arahnya berpencar — yang bergerak bergerak sendiri-sendiri, bukan karena satu sebab bersama.", "en": "The moves were scattered — each asset went its own way rather than following one common cause.", "ms": "Arahnya bertaburan — setiap aset bergerak sendiri, bukan kerana satu sebab bersama.", "zh": "走势分化——各标的各走各的，并非出自同一个共同原因。", "es": "Los movimientos fueron dispares: cada activo fue por su lado, no por una causa común.", "pt": "Os movimentos ficaram dispersos — cada ativo seguiu seu próprio caminho, não uma causa comum."},
    "ik_tabel": {"id": "Lintas aset dalam satu layar", "en": "Every asset on one screen", "ms": "Merentas aset dalam satu skrin", "zh": "一屏看全部资产", "es": "Todos los activos en una pantalla", "pt": "Todos os ativos em uma tela"},
    "ik_1h": {"id": "1 hari", "en": "1d", "ms": "1 hari", "zh": "1 日", "es": "1d", "pt": "1d"},
    "ik_1p": {"id": "1 pekan", "en": "1w", "ms": "1 minggu", "zh": "1 周", "es": "1sem", "pt": "1sem"},
    "ik_1b": {"id": "1 bulan", "en": "1m", "ms": "1 bulan", "zh": "1 月", "es": "1m", "pt": "1m"},
    "ik_ytd": {"id": "Sejak awal tahun", "en": "YTD", "ms": "Sejak awal tahun", "zh": "年初至今", "es": "En el año", "pt": "No ano"},
    "ik_1t": {"id": "1 tahun", "en": "1y", "ms": "1 tahun", "zh": "1 年", "es": "1a", "pt": "1a"},
    "ik_posisi52": {"id": "Posisi 52 minggu", "en": "52w position", "ms": "Kedudukan 52 minggu", "zh": "52 周位置", "es": "Posición 52 sem", "pt": "Posição 52 sem"},
    "c_ik_tabel": {"id": "Perubahan dihitung terhadap hari kalender, bukan jumlah batang — sebulan berarti sebulan, berapa pun hari bursanya. Tanda “—” berarti riwayatnya belum cukup panjang.", "en": "Changes are measured against calendar days, not bar counts — a month means a month, however many trading days it contained. A dash means the history is not long enough.", "ms": "Perubahan dikira terhadap hari kalendar, bukan bilangan bar — sebulan bermaksud sebulan. Tanda “—” bermakna sejarahnya belum cukup panjang.", "zh": "涨跌幅按日历天数计算，而非 K 线根数——一个月就是一个月，无论其中有多少个交易日。“—” 表示历史数据长度不足。", "es": "Las variaciones se miden en días naturales, no en número de barras: un mes es un mes, tenga los días hábiles que tenga. Un guion indica historial insuficiente.", "pt": "As variações são medidas em dias corridos, não em número de barras — um mês é um mês, com quantos pregões tiver. Um traço indica histórico insuficiente."},
    "ik_judul52": {"id": "Di mana harganya berdiri dalam setahun terakhir", "en": "Where each price stands within its past year", "ms": "Di mana harganya berdiri dalam setahun lalu", "zh": "每个价格在过去一年中的位置", "es": "Dónde se sitúa cada precio en su último año", "pt": "Onde cada preço está dentro do seu último ano"},
    "p_aplikasi": {"id": "Aplikasi & kode sumber", "en": "Applications & source code", "ms": "Aplikasi & kod sumber", "zh": "应用与源代码", "es": "Aplicaciones y código fuente", "pt": "Aplicações e código-fonte"},
    "p_buka_aplikasi": {"id": "Buka aplikasi", "en": "Open the app", "ms": "Buka aplikasi", "zh": "打开应用", "es": "Abrir la app", "pt": "Abrir o app"},
    "p_kode_sumber": {"id": "Kode sumber", "en": "Source code", "ms": "Kod sumber", "zh": "源代码", "es": "Código fuente", "pt": "Código-fonte"},
    "p_buku": {"id": "Buku & produk digital", "en": "Books & digital products", "ms": "Buku & produk digital", "zh": "书籍与数字产品", "es": "Libros y productos digitales", "pt": "Livros e produtos digitais"},
    "p_gratis": {"id": "GRATIS", "en": "FREE", "ms": "PERCUMA", "zh": "免费", "es": "GRATIS", "pt": "GRÁTIS"},
    "c_buku": {"id": "Sebagian besar berbahasa Indonesia. Menekan tautan akan membuka toko di luar aplikasi ini.", "en": "Most of these are written in Indonesian. Following a link opens a store outside this application.", "ms": "Kebanyakannya dalam bahasa Indonesia. Menekan pautan akan membuka kedai di luar aplikasi ini.", "zh": "其中大部分为印尼语。点击链接将打开本应用之外的商店页面。", "es": "La mayoría están en indonesio. Seguir un enlace abre una tienda fuera de esta aplicación.", "pt": "A maioria está em indonésio. Seguir um link abre uma loja fora deste aplicativo."},
    "p_temukan": {"id": "Temukan saya di", "en": "Find me at", "ms": "Temui saya di", "zh": "在这些地方找到我", "es": "Encuéntrame en", "pt": "Onde me encontrar"},
    "lp_singkat_tahun": {"id": " th", "en": "y", "ms": " th", "zh": " 年", "es": "a", "pt": "a"},
    "mk_perak": {"id": "Perak", "en": "Silver", "ms": "Perak", "zh": "白银", "es": "Plata", "pt": "Prata"},
    "mk_obligasi": {"id": "Obligasi AS 10 Tahun", "en": "US 10-Year Treasury", "ms": "Bon AS 10 Tahun", "zh": "美国 10 年期国债", "es": "Bono EE. UU. a 10 años", "pt": "Treasury de 10 anos dos EUA"},
    "t_emas": {"id": "Emas", "en": "Gold", "ms": "Emas", "zh": "黄金", "es": "Oro", "pt": "Ouro"},
    "t_zakat_emas": {"id": "Zakat Emas", "en": "Gold Zakat", "ms": "Zakat Emas", "zh": "黄金天课", "es": "Zakat del Oro", "pt": "Zakat do Ouro"},
    "t_tabung_emas": {"id": "Menabung Emas", "en": "Gold Saving", "ms": "Menabung Emas", "zh": "黄金定投", "es": "Ahorro en Oro", "pt": "Poupança em Ouro"},
    "t_lindung_nilai": {"id": "Pelindung Nilai", "en": "Store of Value", "ms": "Pelindung Nilai", "zh": "价值储存", "es": "Reserva de Valor", "pt": "Reserva de Valor"},
    "j_emas": {"id": "Harga Emas", "en": "Gold Prices", "ms": "Harga Emas", "zh": "黄金价格", "es": "Precios del Oro", "pt": "Preços do Ouro"},
    "em_gagal": {"id": "Harga emas tidak bisa diambil sekarang. Periksa koneksi internet Anda, lalu muat ulang.", "en": "Gold prices could not be fetched right now. Check your internet connection, then reload.", "ms": "Harga emas tidak dapat diambil sekarang. Periksa sambungan internet anda, kemudian muat semula.", "zh": "目前无法获取黄金价格。请检查网络连接后重新加载。", "es": "No se pudieron obtener los precios del oro. Revisa tu conexión y vuelve a cargar.", "pt": "Não foi possível obter os preços do ouro agora. Verifique sua conexão e recarregue."},
    "em_harga_dunia": {"id": "HARGA DUNIA", "en": "WORLD PRICE", "ms": "HARGA DUNIA", "zh": "国际金价", "es": "PRECIO MUNDIAL", "pt": "PREÇO MUNDIAL"},
    "em_per_ons": {"id": "per troy ounce", "en": "per troy ounce", "ms": "per troy ounce", "zh": "每金衡盎司", "es": "por onza troy", "pt": "por onça troy"},
    "em_per_gram": {"id": "PER GRAM", "en": "PER GRAM", "ms": "PER GRAM", "zh": "每克", "es": "POR GRAMO", "pt": "POR GRAMA"},
    "em_24_karat": {"id": "24 karat · harga dunia", "en": "24 karat · world price", "ms": "24 karat · harga dunia", "zh": "24K · 国际价", "es": "24 quilates · precio mundial", "pt": "24 quilates · preço mundial"},
    "em_kurs": {"id": "KURS", "en": "EXCHANGE RATE", "ms": "KADAR TUKARAN", "zh": "汇率", "es": "TIPO DE CAMBIO", "pt": "TAXA DE CÂMBIO"},
    "em_perak": {"id": "PERAK PER GRAM", "en": "SILVER PER GRAM", "ms": "PERAK PER GRAM", "zh": "白银每克", "es": "PLATA POR GRAMO", "pt": "PRATA POR GRAMA"},
    "em_nisbah": {"id": "nisbah emas-perak", "en": "gold-to-silver ratio", "ms": "nisbah emas-perak", "zh": "金银比", "es": "ratio oro-plata", "pt": "razão ouro-prata"},
    "em_tabel_berat": {"id": "Nilai menurut berat", "en": "Value by weight", "ms": "Nilai mengikut berat", "zh": "按重量计价", "es": "Valor según el peso", "pt": "Valor por peso"},
    "em_berat": {"id": "Berat", "en": "Weight", "ms": "Berat", "zh": "重量", "es": "Peso", "pt": "Peso"},
    "em_nilai_dunia": {"id": "Nilai harga dunia", "en": "At the world price", "ms": "Pada harga dunia", "zh": "按国际价计", "es": "Al precio mundial", "pt": "Ao preço mundial"},
    "em_setara_usd": {"id": "Setara dolar", "en": "In dollars", "ms": "Setara dolar", "zh": "折合美元", "es": "En dólares", "pt": "Em dólares"},
    "em_periksa_premi": {"id": "Periksa premi toko Anda", "en": "Check your dealer's premium", "ms": "Periksa premium kedai anda", "zh": "核对你所在商家的溢价", "es": "Comprueba la prima de tu tienda", "pt": "Confira o ágio da sua loja"},
    "em_harga_toko": {"id": "Harga jual toko (Rp per gram)", "en": "Dealer's selling price (per gram)", "ms": "Harga jualan kedai (per gram)", "zh": "商家售价（每克）", "es": "Precio de venta del comercio (por gramo)", "pt": "Preço de venda da loja (por grama)"},
    "em_harga_toko_bantuan": {"id": "Angka yang tertera di gerai Antam, Pegadaian, atau toko emas — harga yang benar-benar Anda bayar.", "en": "The figure shown at your dealer — the price you would actually pay.", "ms": "Angka yang tertera di kedai — harga yang benar-benar anda bayar.", "zh": "商家标出的价格——你实际要付的钱。", "es": "La cifra que muestra tu tienda: el precio que realmente pagarías.", "pt": "O número exibido na loja — o preço que você realmente pagaria."},
    "em_buyback": {"id": "Harga buyback (Rp per gram)", "en": "Buyback price (per gram)", "ms": "Harga buyback (per gram)", "zh": "回购价（每克）", "es": "Precio de recompra (por gramo)", "pt": "Preço de recompra (por grama)"},
    "em_buyback_bantuan": {"id": "Harga saat toko membeli kembali emas Anda. Isi 0 kalau tidak ingin dihitung.", "en": "What the dealer pays when buying your gold back. Leave 0 to skip.", "ms": "Harga apabila kedai membeli semula emas anda. Biarkan 0 untuk melangkau.", "zh": "商家回购你黄金时给的价格。填 0 表示跳过。", "es": "Lo que la tienda paga al recomprar tu oro. Deja 0 para omitirlo.", "pt": "O que a loja paga ao recomprar seu ouro. Deixe 0 para pular."},
    "em_premi_ket": {"id": "lebih mahal daripada harga dunia hari ini,", "en": "above today's world price of", "ms": "lebih mahal daripada harga dunia hari ini,", "zh": "高于今日国际金价", "es": "por encima del precio mundial de hoy,", "pt": "acima do preço mundial de hoje,"},
    "em_spread_ket": {"id": "hilang seketika saat Anda membeli lalu langsung menjual kembali. Inilah biaya sesungguhnya, dan biasanya butuh satu sampai dua tahun kenaikan harga hanya untuk menutupnya.", "en": "disappears the moment you buy and immediately sell back. That is the real cost, and it usually takes one to two years of price gains just to recover it.", "ms": "lenyap sebaik sahaja anda beli lalu terus jual semula. Itulah kos sebenar, dan biasanya perlu satu hingga dua tahun kenaikan harga untuk menutupnya.", "zh": "在你买入后立刻卖回的瞬间就没了。这才是真实成本，通常需要一到两年的涨幅才能补回来。", "es": "desaparece en el momento en que compras y revendes de inmediato. Ese es el coste real, y suele hacer falta uno o dos años de subidas solo para recuperarlo.", "pt": "desaparece no instante em que você compra e revende. Esse é o custo real, e costuma levar um a dois anos de valorização só para recuperá-lo."},
    "em_judul_grafik": {"id": "Emas dalam rupiah per gram, dibanding harga dunianya", "en": "Gold in local currency per gram, against its world price", "ms": "Emas dalam mata wang tempatan per gram, berbanding harga dunianya", "zh": "每克黄金的本币价格与国际价格对比", "es": "Oro en moneda local por gramo, frente a su precio mundial", "pt": "Ouro em moeda local por grama, ante seu preço mundial"},
    "em_garis_rupiah": {"id": "Rupiah per gram", "en": "Local currency per gram", "ms": "Mata wang tempatan per gram", "zh": "本币 / 克", "es": "Moneda local por gramo", "pt": "Moeda local por grama"},
    "em_garis_dolar": {"id": "Dolar per gram", "en": "Dollars per gram", "ms": "Dolar per gram", "zh": "美元 / 克", "es": "Dólares por gramo", "pt": "Dólares por grama"},
    "em_selama": {"id": "Selama", "en": "Over", "ms": "Selama", "zh": "过去", "es": "En", "pt": "Ao longo de"},
    "em_dalam_rupiah": {"id": "dalam rupiah", "en": "in local currency", "ms": "dalam mata wang tempatan", "zh": "（以本币计）", "es": "en moneda local", "pt": "em moeda local"},
    "em_dalam_dolar": {"id": "dalam dolar", "en": "in dollars", "ms": "dalam dolar", "zh": "（以美元计）", "es": "en dólares", "pt": "em dólares"},
    "c_emas_sumber": {"id": "Harga dunia berasal dari kontrak berjangka emas dan kurs USD/IDR di Yahoo Finance. Ini <b>bukan</b> harga Antam atau Pegadaian — lihat catatan di bawah.", "en": "World prices come from gold futures and the USD exchange rate on Yahoo Finance. These are <b>not</b> retail dealer prices — see the note below.", "ms": "Harga dunia daripada kontrak niaga hadapan emas dan kadar tukaran USD di Yahoo Finance. Ini <b>bukan</b> harga kedai runcit — lihat nota di bawah.", "zh": "国际价格来自 Yahoo Finance 的黄金期货与美元汇率。这<b>不是</b>零售商报价——见下方说明。", "es": "Los precios mundiales provienen de futuros del oro y del tipo de cambio del dólar en Yahoo Finance. <b>No</b> son precios de tiendas minoristas: mira la nota siguiente.", "pt": "Os preços mundiais vêm de futuros de ouro e da taxa do dólar no Yahoo Finance. <b>Não</b> são preços de lojas de varejo — veja a nota abaixo."},
    "zk_judul": {"id": "**Apakah simpanan emas saya sudah wajib dizakati, dan berapa?**", "en": "**Has my gold reached the zakat threshold, and how much is due?**", "ms": "**Adakah simpanan emas saya sudah wajib dizakati, dan berapa?**", "zh": "**我的黄金达到天课起征点了吗？该缴多少？**", "es": "**¿Mi oro alcanza el umbral del zakat, y cuánto corresponde?**", "pt": "**Meu ouro atingiu o limite do zakat, e quanto é devido?**"},
    "zk_berat": {"id": "Berat emas yang dimiliki (gram)", "en": "Weight of gold held (grams)", "ms": "Berat emas yang dimiliki (gram)", "zh": "持有黄金重量（克）", "es": "Peso del oro que posees (gramos)", "pt": "Peso do ouro que você possui (gramas)"},
    "zk_berat_bantuan": {"id": "Emas batangan, koin, dan tabungan emas. Perhiasan yang dipakai sehari-hari diperselisihkan — lihat penjelasan di bawah.", "en": "Bars, coins, and gold savings accounts. Jewellery in regular use is disputed — see the note below.", "ms": "Jongkong, syiling, dan simpanan emas. Barang kemas yang dipakai harian diperselisihkan — lihat nota di bawah.", "zh": "金条、金币与黄金存折。日常佩戴的首饰存在教法分歧——见下方说明。", "es": "Lingotes, monedas y cuentas de ahorro en oro. Las joyas de uso habitual son objeto de discrepancia: mira la nota.", "pt": "Barras, moedas e contas de poupança em ouro. Joias de uso habitual são objeto de divergência — veja a nota."},
    "zk_harga_gram": {"id": "Harga emas per gram (Rp)", "en": "Gold price per gram", "ms": "Harga emas per gram", "zh": "黄金每克价格", "es": "Precio del oro por gramo", "pt": "Preço do ouro por grama"},
    "zk_harga_bantuan": {"id": "Terisi otomatis dari harga dunia. Sebagian lembaga zakat memakai harga jual toko — silakan sesuaikan.", "en": "Pre-filled from the world price. Some zakat institutions use the retail dealer price instead — adjust as you see fit.", "ms": "Diisi automatik daripada harga dunia. Sesetengah institusi zakat menggunakan harga kedai — sesuaikan mengikut keperluan.", "zh": "按国际价自动填入。部分天课机构改用零售价——可自行调整。", "es": "Se rellena con el precio mundial. Algunas instituciones de zakat usan el precio minorista: ajústalo si procede.", "pt": "Preenchido com o preço mundial. Algumas instituições de zakat usam o preço de varejo — ajuste conforme necessário."},
    "zk_haul": {"id": "Sudah dimiliki genap satu tahun (haul)", "en": "Held for a full lunar year (haul)", "ms": "Sudah dimiliki genap setahun (haul)", "zh": "已满一个太阴年（haul）", "es": "En posesión durante un año lunar completo (haul)", "pt": "Mantido por um ano lunar completo (haul)"},
    "zk_haul_bantuan": {"id": "Satu tahun hijriah, sekitar 354 hari — bukan 365. Yang dihitung adalah simpanan terendah selama setahun itu, bukan yang tertinggi.", "en": "One lunar year, about 354 days — not 365. What counts is the lowest holding during that year, not the peak.", "ms": "Setahun hijrah, kira-kira 354 hari — bukan 365. Yang dikira ialah simpanan terendah sepanjang tahun itu, bukan yang tertinggi.", "zh": "一个伊斯兰历年，约 354 天，而非 365 天。计算依据是该年内的最低持有量，而非峰值。", "es": "Un año lunar, unos 354 días, no 365. Cuenta la tenencia más baja de ese año, no el máximo.", "pt": "Um ano lunar, cerca de 354 dias — não 365. Vale a menor quantidade mantida no período, não o pico."},
    "zk_nisab": {"id": "NISAB EMAS", "en": "GOLD THRESHOLD", "ms": "NISAB EMAS", "zh": "黄金起征点", "es": "UMBRAL DEL ORO", "pt": "LIMITE DO OURO"},
    "zk_simpanan": {"id": "SIMPANAN ANDA", "en": "YOUR HOLDING", "ms": "SIMPANAN ANDA", "zh": "你的持有量", "es": "TU TENENCIA", "pt": "SUA POSSE"},
    "zk_status": {"id": "STATUS", "en": "STATUS", "ms": "STATUS", "zh": "状态", "es": "ESTADO", "pt": "SITUAÇÃO"},
    "zk_capai": {"id": "Mencapai nisab", "en": "Threshold reached", "ms": "Mencapai nisab", "zh": "已达起征点", "es": "Umbral alcanzado", "pt": "Limite atingido"},
    "zk_belum": {"id": "Belum mencapai", "en": "Not yet reached", "ms": "Belum mencapai", "zh": "尚未达到", "es": "Aún no alcanzado", "pt": "Ainda não atingido"},
    "zk_dari_nisab": {"id": "dari nisab", "en": "of the threshold", "ms": "daripada nisab", "zh": "（占起征点）", "es": "del umbral", "pt": "do limite"},
    "zk_wajib": {"id": "ZAKAT YANG DIKELUARKAN", "en": "ZAKAT DUE", "ms": "ZAKAT YANG DIKELUARKAN", "zh": "应缴天课", "es": "ZAKAT A PAGAR", "pt": "ZAKAT DEVIDO"},
    "zk_belum_haul": {"id": "Simpanan sudah mencapai nisab, tetapi haul satu tahun belum genap. Zakat baru wajib setelah kepemilikan melewati satu tahun hijriah.", "en": "The holding has reached the threshold, but the one-year haul is not complete. Zakat becomes due only after a full lunar year of ownership.", "ms": "Simpanan sudah mencapai nisab, tetapi haul setahun belum genap. Zakat hanya wajib selepas pemilikan melepasi setahun hijrah.", "zh": "持有量已达起征点，但尚未满一年。须持满一个太阴年后才应缴天课。", "es": "La tenencia alcanza el umbral, pero aún no se completa el año. El zakat solo es exigible tras un año lunar completo de posesión.", "pt": "A posse atingiu o limite, mas o ano ainda não se completou. O zakat só é devido após um ano lunar completo."},
    "zk_kurang": {"id": "Kurang", "en": "Short by", "ms": "Kurang", "zh": "还差", "es": "Faltan", "pt": "Faltam"},
    "zk_kurang2": {"id": "lagi untuk mencapai nisab.", "en": "to reach the threshold.", "ms": "lagi untuk mencapai nisab.", "zh": "才能达到起征点。", "es": "para alcanzar el umbral.", "pt": "para atingir o limite."},
    "zk_nisab_perak": {"id": "Nisab perak — mengapa angkanya berbeda", "en": "The silver threshold — why the number differs", "ms": "Nisab perak — mengapa angkanya berbeza", "zh": "白银起征点——为何数字不同", "es": "El umbral de la plata: por qué difiere", "pt": "O limite da prata — por que o número difere"},
    "zk_perak_setara": {"id": "Nisab perak hari ini setara", "en": "The silver threshold today comes to", "ms": "Nisab perak hari ini bersamaan", "zh": "今日白银起征点约为", "es": "El umbral de la plata hoy equivale a", "pt": "O limite da prata hoje equivale a"},
    "zk_perak_banding": {"id": "sementara nisab emas", "en": "while the gold threshold is", "ms": "manakala nisab emas", "zh": "而黄金起征点为", "es": "mientras que el del oro es", "pt": "enquanto o do ouro é"},
    "zk_perhiasan": {"id": "Perhiasan yang dipakai sehari-hari", "en": "Jewellery worn in daily life", "ms": "Barang kemas yang dipakai harian", "zh": "日常佩戴的首饰", "es": "Joyas de uso cotidiano", "pt": "Joias de uso cotidiano"},
    "tb_judul": {"id": "**Kalau saya menabung emas sekian rupiah tiap bulan, jadi berapa?**", "en": "**If I buy this much gold every month, where does it end up?**", "ms": "**Jika saya menabung emas sekian setiap bulan, jadi berapa?**", "zh": "**如果每月定投这么多黄金，最后会怎样？**", "es": "**Si compro esta cantidad de oro cada mes, ¿en qué acaba?**", "pt": "**Se eu comprar essa quantia em ouro todo mês, no que dá?**"},
    "tb_setoran": {"id": "Setoran per bulan (Rp)", "en": "Monthly contribution", "ms": "Setoran setiap bulan", "zh": "每月投入", "es": "Aportación mensual", "pt": "Aporte mensal"},
    "tb_lama": {"id": "Lama menabung", "en": "How long", "ms": "Tempoh menabung", "zh": "定投时长", "es": "Durante cuánto tiempo", "pt": "Por quanto tempo"},
    "tb_deposito": {"id": "Bunga deposito pembanding (% per tahun)", "en": "Comparison deposit rate (% per year)", "ms": "Kadar deposit pembanding (% setahun)", "zh": "对比用定存利率（年 %）", "es": "Tipo de depósito comparativo (% anual)", "pt": "Taxa de depósito para comparação (% ao ano)"},
    "tb_deposito_bantuan": {"id": "Sebagai pembanding sederhana. Isi sesuai bunga deposito yang benar-benar Anda dapat.", "en": "A simple benchmark. Enter the rate you could actually get.", "ms": "Sebagai penanda aras ringkas. Isi kadar yang benar-benar anda peroleh.", "zh": "作为简单基准。填入你实际能拿到的利率。", "es": "Una referencia sencilla. Pon el tipo que realmente podrías obtener.", "pt": "Uma referência simples. Informe a taxa que você realmente conseguiria."},
    "tb_premi": {"id": "Premi beli di toko (%)", "en": "Dealer buy premium (%)", "ms": "Premium belian di kedai (%)", "zh": "商家买入溢价（%）", "es": "Prima de compra en tienda (%)", "pt": "Ágio de compra na loja (%)"},
    "tb_premi_bantuan": {"id": "Selisih harga toko terhadap harga dunia. Untuk kepingan kecil biasanya lebih besar daripada batangan besar.", "en": "How far the dealer price sits above the world price. Small pieces usually carry a larger premium than big bars.", "ms": "Berapa jauh harga kedai di atas harga dunia. Kepingan kecil biasanya bermargin lebih besar daripada jongkong besar.", "zh": "商家价格高于国际价的幅度。小规格通常比大金条溢价更高。", "es": "Cuánto supera el precio de la tienda al precio mundial. Las piezas pequeñas suelen tener mayor prima.", "pt": "Quanto o preço da loja fica acima do mundial. Peças pequenas costumam ter ágio maior."},
    "tb_potongan": {"id": "Potongan saat dijual kembali (%)", "en": "Discount when selling back (%)", "ms": "Potongan ketika dijual semula (%)", "zh": "回售折价（%）", "es": "Descuento al revender (%)", "pt": "Deságio na revenda (%)"},
    "tb_potongan_bantuan": {"id": "Berapa persen di bawah harga dunia saat toko membelinya kembali dari Anda.", "en": "How far below the world price the dealer pays when buying it back from you.", "ms": "Berapa peratus di bawah harga dunia apabila kedai membelinya semula.", "zh": "商家从你手中回购时低于国际价的比例。", "es": "Cuánto por debajo del precio mundial paga la tienda al recomprarlo.", "pt": "Quanto abaixo do preço mundial a loja paga ao recomprar."},
    "tb_terlalu_pendek": {"id": "Data yang tersedia terlalu pendek untuk disimulasikan. Pilih jangka waktu yang lebih panjang.", "en": "The available data is too short to simulate. Choose a longer period.", "ms": "Data yang ada terlalu pendek untuk disimulasikan. Pilih tempoh yang lebih panjang.", "zh": "可用数据太短，无法模拟。请选择更长的时间。", "es": "Los datos disponibles son demasiado cortos. Elige un periodo más largo.", "pt": "Os dados disponíveis são curtos demais. Escolha um período maior."},
    "tb_total_setor": {"id": "TOTAL DISETOR", "en": "TOTAL PAID IN", "ms": "JUMLAH DISETOR", "zh": "累计投入", "es": "TOTAL APORTADO", "pt": "TOTAL APORTADO"},
    "tb_kali_setor": {"id": "kali setoran", "en": "contributions", "ms": "kali setoran", "zh": "次投入", "es": "aportaciones", "pt": "aportes"},
    "tb_gram": {"id": "EMAS TERKUMPUL", "en": "GOLD ACCUMULATED", "ms": "EMAS TERKUMPUL", "zh": "累计黄金", "es": "ORO ACUMULADO", "pt": "OURO ACUMULADO"},
    "tb_nilai_jual": {"id": "NILAI KALAU DIJUAL", "en": "VALUE IF SOLD", "ms": "NILAI JIKA DIJUAL", "zh": "卖出可得", "es": "VALOR SI SE VENDE", "pt": "VALOR SE VENDIDO"},
    "tb_imbal": {"id": "IMBAL HASIL", "en": "RETURN", "ms": "PULANGAN", "zh": "收益率", "es": "RENTABILIDAD", "pt": "RETORNO"},
    "tb_per_tahun": {"id": "per tahun, sudah memperhitungkan waktu setoran", "en": "per year, weighted by when you paid in", "ms": "setahun, mengambil kira masa setoran", "zh": "年化，已按投入时点加权", "es": "anual, ponderada por el momento de cada aporte", "pt": "ao ano, ponderado pelo momento dos aportes"},
    "tb_judul_grafik": {"id": "Nilai tabungan emas dibanding setoran dan deposito", "en": "Gold savings value against contributions and a deposit", "ms": "Nilai simpanan emas berbanding setoran dan deposit", "zh": "黄金定投价值 vs 投入本金 vs 定存", "es": "Valor del ahorro en oro frente a aportes y a un depósito", "pt": "Valor da poupança em ouro ante aportes e um depósito"},
    "tb_garis_emas": {"id": "Tabungan emas", "en": "Gold savings", "ms": "Simpanan emas", "zh": "黄金定投", "es": "Ahorro en oro", "pt": "Poupança em ouro"},
    "tb_garis_deposito": {"id": "Deposito", "en": "Deposit", "ms": "Deposit", "zh": "定期存款", "es": "Depósito", "pt": "Depósito"},
    "tb_garis_setoran": {"id": "Setoran kumulatif", "en": "Cumulative contributions", "ms": "Setoran terkumpul", "zh": "累计投入", "es": "Aportes acumulados", "pt": "Aportes acumulados"},
    "tb_emas_unggul": {"id": "Emas unggul atas deposito sebesar", "en": "Gold came out ahead of the deposit by", "ms": "Emas mengatasi deposit sebanyak", "zh": "黄金跑赢定存", "es": "El oro superó al depósito por", "pt": "O ouro superou o depósito em"},
    "tb_deposito_unggul": {"id": "Deposito justru unggul atas emas sebesar", "en": "The deposit actually came out ahead of gold by", "ms": "Deposit sebenarnya mengatasi emas sebanyak", "zh": "反而是定存跑赢黄金", "es": "En realidad el depósito superó al oro por", "pt": "Na verdade o depósito superou o ouro em"},
    "lp_judul": {"id": "Emas dibanding saham dan pelemahan mata uang", "en": "Gold against stocks and currency weakness", "ms": "Emas berbanding saham dan kelemahan mata wang", "zh": "黄金 vs 股票 vs 货币贬值", "es": "El oro frente a la bolsa y a la debilidad de la moneda", "pt": "Ouro ante ações e a fraqueza da moeda"},
    "lp_judul_grafik": {"id": "Semua disetarakan ke 100 pada hari pertama", "en": "All rebased to 100 on the first day", "ms": "Semua disetarakan kepada 100 pada hari pertama", "zh": "全部以首日为 100 重新基准化", "es": "Todo reajustado a 100 el primer día", "pt": "Tudo rebaseado para 100 no primeiro dia"},
    "lp_emas_rupiah": {"id": "Emas (rupiah)", "en": "Gold (local currency)", "ms": "Emas (mata wang tempatan)", "zh": "黄金（本币）", "es": "Oro (moneda local)", "pt": "Ouro (moeda local)"},
    "lp_emas_dolar": {"id": "Emas (dolar)", "en": "Gold (dollars)", "ms": "Emas (dolar)", "zh": "黄金（美元）", "es": "Oro (dólares)", "pt": "Ouro (dólares)"},
    "lp_kurs": {"id": "Kurs USD/IDR", "en": "USD exchange rate", "ms": "Kadar tukaran USD", "zh": "美元汇率", "es": "Tipo de cambio del dólar", "pt": "Taxa do dólar"},
    "lp_ihsg": {"id": "IHSG", "en": "Jakarta Composite", "ms": "Indeks Komposit Jakarta", "zh": "印尼综合指数", "es": "Índice de Yakarta", "pt": "Índice de Jacarta"},
    "lp_tabel": {"id": "Imbal hasil rata-rata per tahun", "en": "Average return per year", "ms": "Pulangan purata setahun", "zh": "年均收益率", "es": "Rentabilidad media anual", "pt": "Retorno médio ao ano"},
    "lp_per_tahun_ket": {"id": "Angka di atas sudah dirata-ratakan per tahun, bukan hasil total. Tanda “—” berarti riwayatnya belum cukup panjang.", "en": "The figures above are annualised, not cumulative. A dash means the history is not long enough.", "ms": "Angka di atas adalah kadar tahunan, bukan jumlah terkumpul. Tanda “—” bermakna sejarahnya belum cukup panjang.", "zh": "上表为年化数字，并非累计涨幅。“—” 表示历史数据长度不足。", "es": "Las cifras están anualizadas, no acumuladas. Un guion significa que el historial no es lo bastante largo.", "pt": "Os números estão anualizados, não acumulados. Um traço indica histórico insuficiente."},
    "lp_inflasi_kalimat": {"id": "Selama sepuluh tahun terakhir emas naik rata-rata", "en": "Over the past ten years gold rose an average of", "ms": "Sepanjang sepuluh tahun lalu emas naik purata", "zh": "过去十年，黄金年均上涨", "es": "En los últimos diez años el oro subió de media", "pt": "Nos últimos dez anos o ouro subiu em média"},
    "lp_inflasi_vs": {"id": "per tahun, sementara inflasi Indonesia rata-rata", "en": "per year, while inflation averaged", "ms": "setahun, manakala inflasi purata", "zh": "，而同期通胀年均", "es": "al año, mientras la inflación promedió", "pt": "ao ano, enquanto a inflação ficou em média"},
    "lp_inflasi_selisih": {"id": "selisihnya", "en": "a gap of", "ms": "jurangnya", "zh": "，差距为", "es": "una diferencia de", "pt": "uma diferença de"},
    "lp_inflasi_titik": {"id": "per tahun.", "en": "per year.", "ms": "setahun.", "zh": "每年。", "es": "al año.", "pt": "ao ano."},
    "k_skor": {"id": "Skor", "en": "Score", "ms": "Skor", "zh": "评分", "es": "Puntuación", "pt": "Pontuação"},
    "k_roe": {"id": "ROE %", "en": "ROE %", "ms": "ROE %", "zh": "ROE %", "es": "ROE %", "pt": "ROE %"},
    "k_margin": {"id": "Margin %", "en": "Margin %", "ms": "Margin %", "zh": "利润率 %", "es": "Margen %", "pt": "Margem %"},
    "k_dividen_persen": {"id": "Dividen %", "en": "Dividend %", "ms": "Dividen %", "zh": "股息率 %", "es": "Dividendo %", "pt": "Dividendo %"},
    "k_harga_beli": {"id": "Harga beli", "en": "Buy price", "ms": "Harga beli", "zh": "买入价", "es": "Precio de compra", "pt": "Preço de compra"},
    "k_harga_jual": {"id": "Harga jual", "en": "Sell price", "ms": "Harga jual", "zh": "卖出价", "es": "Precio de venta", "pt": "Preço de venda"},
    "k_laba": {"id": "Laba", "en": "Profit", "ms": "Untung", "zh": "盈亏金额", "es": "Beneficio", "pt": "Lucro"},
    "k_suasana": {"id": "Suasana", "en": "Mood", "ms": "Suasana", "zh": "心态", "es": "Estado de ánimo", "pt": "Estado emocional"},
    "k_token": {"id": "Token", "en": "Token", "ms": "Token", "zh": "代币", "es": "Token", "pt": "Token"},
    "k_nilai_kolom": {"id": "Nilai", "en": "Value", "ms": "Nilai", "zh": "价值", "es": "Valor", "pt": "Valor"},
    "k_masuk": {"id": "Masuk", "en": "Bought", "ms": "Masuk", "zh": "买入日", "es": "Compra", "pt": "Compra"},
    "k_keluar": {"id": "Keluar", "en": "Sold", "ms": "Keluar", "zh": "卖出日", "es": "Venta", "pt": "Venda"},
    "bt_kurva_turun": {"id": "Penurunan", "en": "Drawdown", "ms": "Penurunan", "zh": "回撤", "es": "Caída", "pt": "Queda"},
    "w_ubah": {"id": "Ubah daftar pantauan", "en": "Edit your watchlist", "ms": "Ubah senarai pantau", "zh": "编辑自选列表", "es": "Editar tu lista de seguimiento", "pt": "Editar sua lista de acompanhamento"},
    "w_tambah_simbol": {"id": "Tambah simbol", "en": "Add symbols", "ms": "Tambah simbol", "zh": "添加标的", "es": "Añadir símbolos", "pt": "Adicionar símbolos"},
    "w_hapus_simbol": {"id": "Hapus simbol", "en": "Remove symbols", "ms": "Buang simbol", "zh": "移除标的", "es": "Quitar símbolos", "pt": "Remover símbolos"},
    "w_pilih_hapus": {"id": "Pilih simbol yang mau dihapus", "en": "Select symbols to remove", "ms": "Pilih simbol untuk dibuang", "zh": "选择要移除的标的", "es": "Selecciona los símbolos a quitar", "pt": "Selecione os símbolos a remover"},
    "w_panduan": {"id": "Saham Indonesia memakai akhiran <b>.JK</b> (BBCA.JK, TLKM.JK). Kripto memakai pasangan mata uang (BTC-USD, ETH-USD). Indeks diawali tanda sisipan (^JKSE untuk IHSG, ^GSPC untuk S&P 500).", "en": "Indonesian stocks use the <b>.JK</b> suffix (BBCA.JK, TLKM.JK). Crypto uses a currency pair (BTC-USD, ETH-USD). Indices start with a caret (^GSPC for the S&P 500, ^JKSE for IHSG).", "ms": "Saham Indonesia menggunakan akhiran <b>.JK</b> (BBCA.JK, TLKM.JK). Kripto menggunakan pasangan mata wang (BTC-USD, ETH-USD). Indeks bermula dengan tanda sisipan (^GSPC, ^JKSE).", "zh": "印尼股票使用 <b>.JK</b> 后缀（BBCA.JK、TLKM.JK）。加密货币使用货币对（BTC-USD、ETH-USD）。指数以 ^ 开头（^GSPC 表示标普 500，^JKSE 表示印尼综指）。", "es": "Las acciones de Indonesia llevan el sufijo <b>.JK</b> (BBCA.JK, TLKM.JK). Las cripto usan un par de divisas (BTC-USD, ETH-USD). Los índices empiezan con acento circunflejo (^GSPC para el S&P 500).", "pt": "Ações da Indonésia usam o sufixo <b>.JK</b> (BBCA.JK, TLKM.JK). Cripto usa par de moedas (BTC-USD, ETH-USD). Índices começam com acento circunflexo (^GSPC para o S&P 500)."},
    "w_kosong": {"id": "Watchlist masih kosong. Tambahkan simbol lewat kotak di atas.", "en": "Your watchlist is empty. Add symbols using the box above.", "ms": "Senarai pantau masih kosong. Tambah simbol melalui kotak di atas.", "zh": "自选列表为空。请使用上方输入框添加标的。", "es": "Tu lista está vacía. Añade símbolos en el cuadro de arriba.", "pt": "Sua lista está vazia. Adicione símbolos na caixa acima."},
    "kr_kapitalisasi": {"id": "KAPITALISASI PASAR", "en": "MARKET CAP", "ms": "PERMODALAN PASARAN", "zh": "总市值", "es": "CAPITALIZACIÓN", "pt": "VALOR DE MERCADO"},
    "kr_volume24": {"id": "VOLUME 24 JAM", "en": "24H VOLUME", "ms": "VOLUM 24 JAM", "zh": "24 小时成交量", "es": "VOLUMEN 24H", "pt": "VOLUME 24H"},
    "kr_dominasi": {"id": "DOMINASI BITCOIN", "en": "BITCOIN DOMINANCE", "ms": "DOMINASI BITCOIN", "zh": "比特币占比", "es": "DOMINANCIA DE BITCOIN", "pt": "DOMINÂNCIA DO BITCOIN"},
    "kr_koin_aktif": {"id": "KOIN AKTIF", "en": "ACTIVE COINS", "ms": "SYILING AKTIF", "zh": "活跃币种", "es": "MONEDAS ACTIVAS", "pt": "MOEDAS ATIVAS"},
    "kr_fng": {"id": "TAKUT & SERAKAH", "en": "FEAR & GREED", "ms": "TAKUT & TAMAK", "zh": "恐惧与贪婪", "es": "MIEDO Y CODICIA", "pt": "MEDO E GANÂNCIA"},
    "kr_24jam": {"id": "24 jam", "en": "24h", "ms": "24 jam", "zh": "24 小时", "es": "24h", "pt": "24h"},
    "kr_tak_ada": {"id": "tidak tersedia", "en": "unavailable", "ms": "tidak tersedia", "zh": "暂无数据", "es": "no disponible", "pt": "indisponível"},
    "fng_sangat_takut": {"id": "Sangat Takut", "en": "Extreme Fear", "ms": "Sangat Takut", "zh": "极度恐惧", "es": "Miedo Extremo", "pt": "Medo Extremo"},
    "fng_takut": {"id": "Takut", "en": "Fear", "ms": "Takut", "zh": "恐惧", "es": "Miedo", "pt": "Medo"},
    "fng_netral": {"id": "Netral", "en": "Neutral", "ms": "Neutral", "zh": "中性", "es": "Neutral", "pt": "Neutro"},
    "fng_serakah": {"id": "Serakah", "en": "Greed", "ms": "Tamak", "zh": "贪婪", "es": "Codicia", "pt": "Ganância"},
    "fng_sangat_serakah": {"id": "Sangat Serakah", "en": "Extreme Greed", "ms": "Sangat Tamak", "zh": "极度贪婪", "es": "Codicia Extrema", "pt": "Ganância Extrema"},
    "kr_koin": {"id": "Koin", "en": "Coin", "ms": "Syiling", "zh": "币种", "es": "Moneda", "pt": "Moeda"},
    "kr_7hari": {"id": "7 hari", "en": "7d", "ms": "7 hari", "zh": "7 日", "es": "7d", "pt": "7d"},
    "kr_30hari": {"id": "30 hari", "en": "30d", "ms": "30 hari", "zh": "30 日", "es": "30d", "pt": "30d"},
    "kr_dari_puncak": {"id": "Dari puncak", "en": "From ATH", "ms": "Dari puncak", "zh": "距历史高点", "es": "Desde máximos", "pt": "Da máxima"},
    "kr_vol_kolom": {"id": "Volume 24 jam", "en": "24h volume", "ms": "Volum 24 jam", "zh": "24 小时成交量", "es": "Volumen 24h", "pt": "Volume 24h"},
    "fd_harga": {"id": "HARGA", "en": "PRICE", "ms": "HARGA", "zh": "价格", "es": "PRECIO", "pt": "PREÇO"},
    "fd_kapitalisasi": {"id": "KAPITALISASI", "en": "MARKET CAP", "ms": "PERMODALAN", "zh": "市值", "es": "CAPITALIZACIÓN", "pt": "VALOR DE MERCADO"},
    "fd_per_ket": {"id": "harga ÷ laba", "en": "price ÷ earnings", "ms": "harga ÷ keuntungan", "zh": "股价 ÷ 每股收益", "es": "precio ÷ beneficio", "pt": "preço ÷ lucro"},
    "fd_pbv_ket": {"id": "harga ÷ nilai buku", "en": "price ÷ book value", "ms": "harga ÷ nilai buku", "zh": "股价 ÷ 每股净资产", "es": "precio ÷ valor contable", "pt": "preço ÷ valor patrimonial"},
    "fd_roe_ket": {"id": "imbal modal", "en": "return on equity", "ms": "pulangan ekuiti", "zh": "净资产收益率", "es": "rentabilidad del capital", "pt": "retorno sobre patrimônio"},
    "fd_margin": {"id": "MARGIN LABA", "en": "PROFIT MARGIN", "ms": "MARGIN UNTUNG", "zh": "净利率", "es": "MARGEN DE BENEFICIO", "pt": "MARGEM DE LUCRO"},
    "fd_der_ket": {"id": "utang ÷ modal", "en": "debt ÷ equity", "ms": "hutang ÷ ekuiti", "zh": "负债 ÷ 权益", "es": "deuda ÷ patrimonio", "pt": "dívida ÷ patrimônio"},
    "fd_dividen": {"id": "DIVIDEN", "en": "DIVIDEND", "ms": "DIVIDEN", "zh": "股息", "es": "DIVIDENDO", "pt": "DIVIDENDO"},
    "fd_dividen_ket": {"id": "imbal hasil", "en": "yield", "ms": "pulangan", "zh": "股息率", "es": "rentabilidad", "pt": "rendimento"},
    "fd_rentang52": {"id": "POSISI DALAM RENTANG 52 MINGGU", "en": "POSITION IN THE 52-WEEK RANGE", "ms": "KEDUDUKAN DALAM JULAT 52 MINGGU", "zh": "在 52 周区间中的位置", "es": "POSICIÓN EN EL RANGO DE 52 SEMANAS", "pt": "POSIÇÃO NA FAIXA DE 52 SEMANAS"},
    "fd_dari_bawah": {"id": "dari bawah", "en": "up from the low", "ms": "dari bawah", "zh": "（自低点起）", "es": "desde el mínimo", "pt": "acima do fundo"},
    "bt_kol_masuk": {"id": "Masuk", "en": "Entry", "ms": "Masuk", "zh": "买入", "es": "Entrada", "pt": "Entrada"},
    "bt_kol_keluar": {"id": "Keluar", "en": "Exit", "ms": "Keluar", "zh": "卖出", "es": "Salida", "pt": "Saída"},
    "bt_kol_hari": {"id": "Hari", "en": "Days", "ms": "Hari", "zh": "天数", "es": "Días", "pt": "Dias"},
    "bt_kol_hmasuk": {"id": "Harga masuk", "en": "Entry price", "ms": "Harga masuk", "zh": "买入价", "es": "Precio de entrada", "pt": "Preço de entrada"},
    "bt_kol_hkeluar": {"id": "Harga keluar", "en": "Exit price", "ms": "Harga keluar", "zh": "卖出价", "es": "Precio de salida", "pt": "Preço de saída"},
    "bt_kol_hasil": {"id": "Hasil", "en": "Result", "ms": "Hasil", "zh": "结果", "es": "Resultado", "pt": "Resultado"},
    "n_potret": {"id": "Potret pasar saat ini", "en": "Market snapshot", "ms": "Potret pasaran semasa", "zh": "当前市场快照", "es": "Panorama del mercado", "pt": "Panorama do mercado"},
    "n_jangka_panjang": {"id": "Indikator jangka panjang — sumber: Bank Dunia", "en": "Long-run indicators — source: World Bank", "ms": "Penunjuk jangka panjang — sumber: Bank Dunia", "zh": "长期指标 — 数据来源：世界银行", "es": "Indicadores de largo plazo — fuente: Banco Mundial", "pt": "Indicadores de longo prazo — fonte: Banco Mundial"},
    "n_indikator": {"id": "Indikator", "en": "Indicator", "ms": "Penunjuk", "zh": "指标", "es": "Indicador", "pt": "Indicador"},
    "n_terbaru": {"id": "Angka terbaru", "en": "Latest figure", "ms": "Angka terkini", "zh": "最新数值", "es": "Cifra más reciente", "pt": "Número mais recente"},
    "n_pada_tahun": {"id": "pada tahun", "en": "in", "ms": "pada tahun", "zh": "年份：", "es": "en", "pt": "em"},
    "n_tertinggal": {"id": "Data Bank Dunia biasanya tertinggal satu sampai dua tahun dari hari ini.", "en": "World Bank data typically lags one to two years behind today.", "ms": "Data Bank Dunia biasanya ketinggalan satu hingga dua tahun.", "zh": "世界银行数据通常比当下滞后一到两年。", "es": "Los datos del Banco Mundial suelen ir uno o dos años por detrás.", "pt": "Os dados do Banco Mundial costumam ter defasagem de um a dois anos."},
    "ind_pdb": {"id": "Pertumbuhan PDB (% per tahun)", "en": "GDP growth (% per year)", "ms": "Pertumbuhan KDNK (% setahun)", "zh": "GDP 增长率（年 %）", "es": "Crecimiento del PIB (% anual)", "pt": "Crescimento do PIB (% ao ano)"},
    "ind_inflasi": {"id": "Inflasi harga konsumen (% per tahun)", "en": "Consumer price inflation (% per year)", "ms": "Inflasi harga pengguna (% setahun)", "zh": "消费者物价通胀（年 %）", "es": "Inflación de precios al consumo (% anual)", "pt": "Inflação ao consumidor (% ao ano)"},
    "ind_pengangguran": {"id": "Tingkat pengangguran (% angkatan kerja)", "en": "Unemployment rate (% of labour force)", "ms": "Kadar pengangguran (% tenaga buruh)", "zh": "失业率（占劳动力 %）", "es": "Tasa de desempleo (% de la población activa)", "pt": "Taxa de desemprego (% da força de trabalho)"},
    "ind_ekspor": {"id": "Ekspor barang & jasa (% PDB)", "en": "Exports of goods & services (% of GDP)", "ms": "Eksport barang & perkhidmatan (% KDNK)", "zh": "商品与服务出口（占 GDP %）", "es": "Exportaciones de bienes y servicios (% del PIB)", "pt": "Exportações de bens e serviços (% do PIB)"},
    "ind_transaksi": {"id": "Neraca transaksi berjalan (% PDB)", "en": "Current account balance (% of GDP)", "ms": "Imbangan akaun semasa (% KDNK)", "zh": "经常账户余额（占 GDP %）", "es": "Saldo por cuenta corriente (% del PIB)", "pt": "Saldo em conta corrente (% do PIB)"},
    "neg_idn": {"id": "Indonesia", "en": "Indonesia", "ms": "Indonesia", "zh": "印度尼西亚", "es": "Indonesia", "pt": "Indonésia"},
    "neg_mys": {"id": "Malaysia", "en": "Malaysia", "ms": "Malaysia", "zh": "马来西亚", "es": "Malasia", "pt": "Malásia"},
    "neg_sgp": {"id": "Singapura", "en": "Singapore", "ms": "Singapura", "zh": "新加坡", "es": "Singapur", "pt": "Singapura"},
    "neg_tha": {"id": "Thailand", "en": "Thailand", "ms": "Thailand", "zh": "泰国", "es": "Tailandia", "pt": "Tailândia"},
    "neg_vnm": {"id": "Vietnam", "en": "Vietnam", "ms": "Vietnam", "zh": "越南", "es": "Vietnam", "pt": "Vietnã"},
    "neg_usa": {"id": "Amerika Serikat", "en": "United States", "ms": "Amerika Syarikat", "zh": "美国", "es": "Estados Unidos", "pt": "Estados Unidos"},
    "neg_chn": {"id": "Tiongkok", "en": "China", "ms": "China", "zh": "中国", "es": "China", "pt": "China"},
    "neg_jpn": {"id": "Jepang", "en": "Japan", "ms": "Jepun", "zh": "日本", "es": "Japón", "pt": "Japão"},
    "mk_dolar": {"id": "Indeks Dolar", "en": "Dollar Index", "ms": "Indeks Dolar", "zh": "美元指数", "es": "Índice Dólar", "pt": "Índice do Dólar"},
    "mk_emas": {"id": "Emas", "en": "Gold", "ms": "Emas", "zh": "黄金", "es": "Oro", "pt": "Ouro"},
    "mk_minyak": {"id": "Minyak WTI", "en": "WTI Crude", "ms": "Minyak WTI", "zh": "WTI 原油", "es": "Crudo WTI", "pt": "Petróleo WTI"},
    "c_skor": {"id": "<b>Skor</b> adalah rata-rata peringkat saham ini terhadap sesamanya dalam empat hal: harga murah, produktivitas, kesehatan neraca, dan dividen. Karena berbasis peringkat, angkanya hanya berarti <i>di dalam pasar yang sama</i>. Skor tinggi berarti “pantas dibaca lebih jauh”, bukan “pantas dibeli”.", "en": "The <b>Score</b> averages this stock's rank against its peers on four things: cheapness, profitability, balance-sheet health, and yield. Being rank-based, the number only means something <i>within the same market</i>. A high score means “worth reading further”, not “worth buying”.", "ms": "<b>Skor</b> ialah purata kedudukan saham ini berbanding rakan sebayanya dalam empat perkara: harga murah, produktiviti, kesihatan kunci kira-kira, dan dividen. Kerana berasaskan kedudukan, angkanya hanya bermakna <i>dalam pasaran yang sama</i>. Skor tinggi bermaksud “wajar dibaca lebih lanjut”, bukan “wajar dibeli”.", "zh": "<b>评分</b>是该股在四个方面相对同行的排名平均值：估值便宜程度、盈利能力、资产负债表健康度、股息。由于基于排名，该数值只在<i>同一市场内</i>才有意义。高分意味着“值得进一步研究”，而不是“值得买入”。", "es": "La <b>Puntuación</b> promedia el ranking de esta acción frente a sus pares en cuatro aspectos: precio barato, rentabilidad, salud del balance y dividendo. Al basarse en rankings, solo tiene sentido <i>dentro del mismo mercado</i>. Una puntuación alta significa “vale la pena estudiarla”, no “vale la pena comprarla”.", "pt": "A <b>Pontuação</b> é a média da posição desta ação frente aos pares em quatro aspectos: preço barato, rentabilidade, saúde do balanço e dividendo. Por ser baseada em ranking, só faz sentido <i>dentro do mesmo mercado</i>. Pontuação alta significa “vale estudar mais”, não “vale comprar”."},
    "c_banding_sektor": {"id": "Membandingkan saham dari sektor berbeda sering menyesatkan: bank wajar berutang besar, perusahaan teknologi wajar ber-PER tinggi. Perbandingan paling berguna dilakukan di dalam satu sektor.", "en": "Comparing stocks across sectors is often misleading: banks carry large debt by nature, technology companies carry high P/E by nature. Comparison is most useful within a single sector.", "ms": "Membandingkan saham daripada sektor berbeza sering mengelirukan: bank memang berhutang besar, syarikat teknologi memang ber-P/E tinggi. Perbandingan paling berguna dalam satu sektor.", "zh": "跨行业比较股票常常具有误导性：银行天然负债高，科技公司天然市盈率高。比较在同一行业内才最有价值。", "es": "Comparar acciones de sectores distintos suele engañar: los bancos cargan deuda por naturaleza, las tecnológicas cotizan a P/E alto por naturaleza. La comparación es más útil dentro de un mismo sector.", "pt": "Comparar ações de setores diferentes costuma enganar: bancos carregam dívida por natureza, empresas de tecnologia têm P/L alto por natureza. A comparação é mais útil dentro do mesmo setor."},
    "c_laporan_yahoo": {"id": "Angka laporan keuangan berasal dari Yahoo Finance dan kadang tidak lengkap untuk emiten kecil. Untuk keputusan penting, bandingkan dengan laporan resmi emiten. Rasio menggambarkan masa lalu — harga saham bergerak karena perkiraan masa depan.", "en": "Financial statement figures come from Yahoo Finance and are sometimes incomplete for smaller companies. For decisions that matter, compare against the company's official filings. Ratios describe the past — share prices move on expectations about the future.", "ms": "Angka penyata kewangan datang daripada Yahoo Finance dan kadangkala tidak lengkap bagi syarikat kecil. Untuk keputusan penting, bandingkan dengan penyata rasmi syarikat. Nisbah menggambarkan masa lalu — harga saham bergerak kerana jangkaan masa depan.", "zh": "财务报表数据来自 Yahoo Finance，小公司的数据有时并不完整。做重要决定前，请与公司官方披露对照。财务比率描述的是过去，而股价反映的是对未来的预期。", "es": "Las cifras contables provienen de Yahoo Finance y a veces están incompletas en empresas pequeñas. Para decisiones importantes, contrasta con los informes oficiales. Los ratios describen el pasado; el precio se mueve por expectativas de futuro.", "pt": "Os números contábeis vêm do Yahoo Finance e às vezes ficam incompletos em empresas menores. Para decisões importantes, confira os relatórios oficiais. Índices descrevem o passado — o preço se move por expectativas sobre o futuro."},
    "c_portofolio": {"id": "Perhitungan ini mengabaikan biaya transaksi, pajak, dan dividen — jadi angka sesungguhnya di rekening Anda akan sedikit berbeda. Semua nilai memakai mata uang asli tiap simbol dan <b>tidak</b> dikonversi, jadi menjumlahkan mata uang berbeda tidak bermakna.", "en": "This ignores transaction costs, taxes, and dividends — so the real figures in your account will differ slightly. All values use each symbol's native currency and are <b>not</b> converted, so summing across currencies is meaningless.", "ms": "Pengiraan ini mengabaikan kos transaksi, cukai dan dividen — jadi angka sebenar dalam akaun anda akan berbeza sedikit. Semua nilai menggunakan mata wang asal setiap simbol dan <b>tidak</b> ditukar.", "zh": "此处未计入交易成本、税费和股息，因此您账户中的实际数字会略有出入。所有数值均使用各标的的原始币种，<b>不做</b>换算，因此跨币种求和没有意义。", "es": "Esto ignora costes de transacción, impuestos y dividendos, así que las cifras reales de tu cuenta diferirán algo. Todos los valores usan la moneda nativa de cada símbolo y <b>no</b> se convierten: sumar entre monedas no tiene sentido.", "pt": "Isto ignora custos de transação, impostos e dividendos — então os números reais na sua conta serão um pouco diferentes. Todos os valores usam a moeda nativa de cada símbolo e <b>não</b> são convertidos; somar moedas diferentes não faz sentido."},
    "d_hanya_baca": {"id": "HANYA BACA", "en": "READ-ONLY", "ms": "BACA SAHAJA", "zh": "只读", "es": "SOLO LECTURA", "pt": "SOMENTE LEITURA"},
    "d_hanya_baca_teks": {"id": "Aplikasi ini hanya membaca <b>alamat publik</b> — deretan yang memang dirancang untuk dibagikan dan bisa dilihat siapa pun di explorer blockchain. Tidak ada yang bisa dipindahkan dari sini.<br><br><b class='turun'>Aplikasi ini tidak akan pernah meminta seed phrase atau private key Anda.</b> Kalau ada aplikasi mana pun yang memintanya — termasuk yang mengaku resmi — itu penipuan. Tutup, jangan isi.", "en": "This app only reads <b>public addresses</b> — strings designed to be shared, visible to anyone on a blockchain explorer. Nothing can be moved from here.<br><br><b class='turun'>This app will never ask for your seed phrase or private key.</b> If any application asks for them — including ones claiming to be official — it is a scam. Close it. Do not fill it in.", "ms": "Aplikasi ini hanya membaca <b>alamat awam</b> — rentetan yang memang direka untuk dikongsi dan boleh dilihat sesiapa pada penjelajah blockchain. Tiada apa-apa boleh dipindahkan dari sini.<br><br><b class='turun'>Aplikasi ini tidak akan sesekali meminta seed phrase atau private key anda.</b> Jika mana-mana aplikasi memintanya — termasuk yang mendakwa rasmi — itu penipuan. Tutup, jangan isi.", "zh": "本应用只读取<b>公开地址</b>——这类字符串本就是用来分享的，任何人都能在区块链浏览器上看到。从这里无法转移任何资产。<br><br><b class='turun'>本应用永远不会索要您的助记词或私钥。</b>如果有任何应用向您索要——包括自称官方的——那就是诈骗。关掉它，不要填。", "es": "Esta aplicación solo lee <b>direcciones públicas</b>: cadenas pensadas para compartirse, visibles para cualquiera en un explorador de blockchain. Desde aquí no se puede mover nada.<br><br><b class='turun'>Esta aplicación nunca te pedirá tu frase semilla ni tu clave privada.</b> Si alguna aplicación te las pide —incluso diciéndose oficial— es una estafa. Ciérrala. No la rellenes.", "pt": "Este aplicativo apenas lê <b>endereços públicos</b> — sequências feitas para serem compartilhadas, visíveis a qualquer um em um explorador de blockchain. Nada pode ser movido daqui.<br><br><b class='turun'>Este aplicativo jamais pedirá sua seed phrase ou chave privada.</b> Se algum aplicativo pedir — inclusive os que se dizem oficiais — é golpe. Feche. Não preencha."},
    "d_alamat": {"id": "Alamat publik", "en": "Public address", "ms": "Alamat awam", "zh": "公开地址", "es": "Dirección pública", "pt": "Endereço público"},
    "d_jaringan": {"id": "Jaringan", "en": "Network", "ms": "Rangkaian", "zh": "网络", "es": "Red", "pt": "Rede"},
    "d_tambah_hapus": {"id": "Tambah atau hapus alamat", "en": "Add or remove an address", "ms": "Tambah atau buang alamat", "zh": "添加或删除地址", "es": "Añadir o quitar dirección", "pt": "Adicionar ou remover endereço"},
    "d_kosong": {"id": "Alamat masih kosong.", "en": "The address field is empty.", "ms": "Alamat masih kosong.", "zh": "地址为空。", "es": "El campo de dirección está vacío.", "pt": "O campo de endereço está vazio."},
    "d_tak_sah": {"id": "Bukan alamat yang sah untuk jaringan ini. Contoh bentuknya:", "en": "Not a valid address for this network. Example format:", "ms": "Bukan alamat yang sah untuk rangkaian ini. Contoh bentuknya:", "zh": "这不是该网络的有效地址。格式示例：", "es": "No es una dirección válida para esta red. Formato de ejemplo:", "pt": "Não é um endereço válido para esta rede. Formato de exemplo:"},
    "d_kembar": {"id": "Alamat itu sudah ada dalam daftar.", "en": "That address is already in the list.", "ms": "Alamat itu sudah ada dalam senarai.", "zh": "该地址已在列表中。", "es": "Esa dirección ya está en la lista.", "pt": "Esse endereço já está na lista."},
    "d_belum_ada": {"id": "Belum ada alamat. Tambahkan lewat panel di atas. Alamat disimpan lokal di folder data/, tidak dikirim ke mana pun selain ke jaringan blockchain untuk membaca saldonya.", "en": "No addresses yet. Add one using the panel above. Addresses are stored locally in the data/ folder and are sent nowhere except to the blockchain network to read the balance.", "ms": "Belum ada alamat. Tambah melalui panel di atas. Alamat disimpan setempat dalam folder data/ dan tidak dihantar ke mana-mana selain ke rangkaian blockchain untuk membaca baki.", "zh": "尚未添加地址。请使用上方面板添加。地址保存在本地 data/ 文件夹，除了向区块链网络查询余额之外不会发送到任何地方。", "es": "Aún no hay direcciones. Añade una en el panel de arriba. Las direcciones se guardan localmente en la carpeta data/ y no se envían a ningún sitio salvo a la red blockchain para leer el saldo.", "pt": "Nenhum endereço ainda. Adicione pelo painel acima. Os endereços ficam salvos localmente na pasta data/ e não são enviados a lugar nenhum, exceto à rede blockchain para ler o saldo."},
    "d_muat_saldo": {"id": "⟳  MUAT ULANG SALDO", "en": "⟳  RELOAD BALANCES", "ms": "⟳  MUAT SEMULA BAKI", "zh": "⟳  刷新余额", "es": "⟳  RECARGAR SALDOS", "pt": "⟳  RECARREGAR SALDOS"},
    "d_total": {"id": "TOTAL NILAI", "en": "TOTAL VALUE", "ms": "JUMLAH NILAI", "zh": "总价值", "es": "VALOR TOTAL", "pt": "VALOR TOTAL"},
    "d_terbaca": {"id": "alamat terbaca", "en": "addresses read", "ms": "alamat dibaca", "zh": "个地址已读取", "es": "direcciones leídas", "pt": "endereços lidos"},
    "d_token_terdeteksi": {"id": "TOKEN TERDETEKSI", "en": "TOKENS DETECTED", "ms": "TOKEN DIKESAN", "zh": "检测到的代币", "es": "TOKENS DETECTADOS", "pt": "TOKENS DETECTADOS"},
    "d_diluar_koin": {"id": "di luar koin utama", "en": "beyond the native coin", "ms": "selain syiling utama", "zh": "（原生币之外）", "es": "además de la moneda nativa", "pt": "além da moeda nativa"},
    "d_transaksi": {"id": "transaksi", "en": "transactions", "ms": "transaksi", "zh": "笔交易", "es": "transacciones", "pt": "transações"},
    "d_token_di": {"id": "token di alamat ini", "en": "tokens at this address", "ms": "token pada alamat ini", "zh": "个代币在此地址", "es": "tokens en esta dirección", "pt": "tokens neste endereço"},
    "d_token_sampah": {"id": "Banyak token bernilai nol adalah token sampah yang dikirim tanpa diminta. Jangan pernah menukar atau menyetujui token yang tidak Anda kenal — itu cara umum menguras dompet.", "en": "Many zero-value tokens are junk sent unsolicited. Never swap or approve a token you don't recognise — that is a common way wallets get drained.", "ms": "Banyak token bernilai sifar ialah token sampah yang dihantar tanpa diminta. Jangan sesekali menukar atau meluluskan token yang anda tidak kenal — itu cara biasa dompet dikuras.", "zh": "许多零价值代币是未经请求发来的垃圾币。切勿兑换或授权您不认识的代币——这是钱包被掏空的常见途径。", "es": "Muchos tokens sin valor son basura enviada sin pedirla. Nunca intercambies ni apruebes un token que no reconozcas: es una forma habitual de vaciar carteras.", "pt": "Muitos tokens sem valor são lixo enviado sem pedido. Nunca troque nem aprove um token que você não reconhece — é uma forma comum de esvaziar carteiras."},
    "d_sumber": {"id": "Sumber data: Blockstream (Bitcoin), Ethplorer (Ethereum), RPC publik Solana, harga dari CoinGecko. Semuanya gratis tanpa API key. Saldo yang tampil adalah yang tercatat di blockchain — aset yang Anda simpan di bursa tidak akan muncul di sini karena tidak berada di alamat Anda sendiri.", "en": "Sources: Blockstream (Bitcoin), Ethplorer (Ethereum), Solana public RPC, prices from CoinGecko — all free, no API key. Balances shown are those recorded on-chain. Assets you hold on an exchange will not appear here, because they are not at your own address.", "ms": "Sumber data: Blockstream (Bitcoin), Ethplorer (Ethereum), RPC awam Solana, harga daripada CoinGecko. Semuanya percuma tanpa kunci API. Baki yang dipaparkan ialah yang tercatat pada rantaian — aset yang anda simpan di bursa tidak akan muncul di sini.", "zh": "数据来源：Blockstream（比特币）、Ethplorer（以太坊）、Solana 公共 RPC，价格来自 CoinGecko，全部免费且无需 API 密钥。显示的是链上记录的余额。您存放在交易所的资产不会出现在这里，因为它们并不在您自己的地址上。", "es": "Fuentes: Blockstream (Bitcoin), Ethplorer (Ethereum), RPC público de Solana, precios de CoinGecko: todo gratis y sin clave API. Los saldos mostrados son los registrados en cadena. Los activos que tengas en un exchange no aparecerán aquí, porque no están en tu propia dirección.", "pt": "Fontes: Blockstream (Bitcoin), Ethplorer (Ethereum), RPC público da Solana, preços da CoinGecko — tudo grátis, sem chave de API. Os saldos mostrados são os registrados on-chain. Ativos que você mantém em uma corretora não aparecem aqui, pois não estão no seu próprio endereço."},
    "a_intro": {"id": "Peringatan diperiksa setiap kali halaman ini dibuka. Tidak ada notifikasi yang dikirim ke ponsel — aplikasi ini berjalan di komputer Anda, tanpa server yang mengawasi pasar saat aplikasi ditutup.", "en": "Alerts are checked each time you open this page. No notifications are sent to your phone — this app runs on your computer, with no server watching the market while it's closed.", "ms": "Amaran disemak setiap kali halaman ini dibuka. Tiada pemberitahuan dihantar ke telefon — aplikasi ini berjalan pada komputer anda, tanpa pelayan yang memantau pasaran ketika ditutup.", "zh": "每次打开本页时都会检查提醒。不会向手机推送通知——本应用运行在您的电脑上，关闭后没有服务器代为盯盘。", "es": "Las alertas se revisan cada vez que abres esta página. No se envían notificaciones al móvil: la aplicación se ejecuta en tu ordenador, sin servidor vigilando el mercado mientras está cerrada.", "pt": "Os alertas são verificados sempre que você abre esta página. Nenhuma notificação é enviada ao celular — o aplicativo roda no seu computador, sem servidor vigiando o mercado enquanto está fechado."},
    "a_pasang": {"id": "Pasang peringatan baru", "en": "Set a new alert", "ms": "Pasang amaran baharu", "zh": "设置新提醒", "es": "Crear una alerta", "pt": "Criar um alerta"},
    "a_kondisi": {"id": "Kondisi", "en": "Condition", "ms": "Keadaan", "zh": "条件", "es": "Condición", "pt": "Condição"},
    "a_naik_ke": {"id": "Naik ke atas", "en": "Rises above", "ms": "Naik melebihi", "zh": "上涨突破", "es": "Sube por encima de", "pt": "Sobe acima de"},
    "a_turun_ke": {"id": "Turun ke bawah", "en": "Falls below", "ms": "Turun ke bawah", "zh": "下跌跌破", "es": "Cae por debajo de", "pt": "Cai abaixo de"},
    "a_batas": {"id": "Harga batas", "en": "Threshold price", "ms": "Harga had", "zh": "触发价格", "es": "Precio umbral", "pt": "Preço-limite"},
    "a_tombol": {"id": "PASANG", "en": "SET ALERT", "ms": "PASANG", "zh": "设置", "es": "CREAR", "pt": "CRIAR"},
    "a_isi_dulu": {"id": "Simbol dan harga batas harus diisi.", "en": "Symbol and threshold price are both required.", "ms": "Simbol dan harga had mesti diisi.", "zh": "代码和触发价格都必须填写。", "es": "Hay que rellenar símbolo y precio umbral.", "pt": "Símbolo e preço-limite são obrigatórios."},
    "a_belum": {"id": "Belum ada peringatan. Pasang lewat panel di atas.", "en": "No alerts yet. Create one using the panel above.", "ms": "Belum ada amaran. Pasang melalui panel di atas.", "zh": "尚无提醒。请使用上方面板创建。", "es": "Aún no hay alertas. Crea una en el panel de arriba.", "pt": "Nenhum alerta ainda. Crie um pelo painel acima."},
    "a_tersentuh": {"id": "TERSENTUH", "en": "TRIGGERED", "ms": "TERSENTUH", "zh": "已触发", "es": "ACTIVADAS", "pt": "DISPARADOS"},
    "a_menunggu": {"id": "MENUNGGU", "en": "WAITING", "ms": "MENUNGGU", "zh": "等待中", "es": "EN ESPERA", "pt": "AGUARDANDO"},
    "a_gagal_baca": {"id": "GAGAL DIBACA", "en": "UNREADABLE", "ms": "GAGAL DIBACA", "zh": "读取失败", "es": "NO LEGIBLES", "pt": "NÃO LIDOS"},
    "a_sudah_lewat": {"id": "sudah melewati batas", "en": "past the threshold", "ms": "sudah melepasi had", "zh": "已越过阈值", "es": "superaron el umbral", "pt": "passaram do limite"},
    "a_belum_capai": {"id": "belum tercapai", "en": "not yet reached", "ms": "belum dicapai", "zh": "尚未达到", "es": "aún no alcanzadas", "pt": "ainda não atingidos"},
    "a_bermasalah": {"id": "simbol bermasalah", "en": "problem symbols", "ms": "simbol bermasalah", "zh": "代码有问题", "es": "símbolos con problemas", "pt": "símbolos com problema"},
    "a_sudah_kena": {"id": "Sudah tersentuh", "en": "Already triggered", "ms": "Sudah tersentuh", "zh": "已触发", "es": "Ya activadas", "pt": "Já disparados"},
    "a_masih_tunggu": {"id": "Masih menunggu", "en": "Still waiting", "ms": "Masih menunggu", "zh": "仍在等待", "es": "Aún esperando", "pt": "Ainda aguardando"},
    "a_tercapai": {"id": "TERCAPAI", "en": "REACHED", "ms": "TERCAPAI", "zh": "已达成", "es": "ALCANZADA", "pt": "ATINGIDO"},
    "a_harga_kini": {"id": "Harga sekarang", "en": "Current price", "ms": "Harga semasa", "zh": "当前价格", "es": "Precio actual", "pt": "Preço atual"},
    "a_batas_kata": {"id": "batas", "en": "threshold", "ms": "had", "zh": "阈值", "es": "umbral", "pt": "limite"},
    "a_dipasang": {"id": "dipasang", "en": "set", "ms": "dipasang", "zh": "设置于", "es": "creada", "pt": "criado"},
    "a_jarak": {"id": "Jarak", "en": "Distance", "ms": "Jarak", "zh": "距离", "es": "Distancia", "pt": "Distância"},
    "a_tak_terbaca": {"id": "Simbol berikut tidak bisa dibaca — periksa penulisannya:", "en": "These symbols could not be read — check their spelling:", "ms": "Simbol berikut tidak dapat dibaca — periksa ejaannya:", "zh": "以下代码无法读取，请检查拼写：", "es": "Estos símbolos no se pudieron leer; revisa la escritura:", "pt": "Estes símbolos não puderam ser lidos — verifique a grafia:"},
    "bt_forex_abai": {"id": "TIGA HAL YANG DIABAIKAN UJI INI", "en": "THREE THINGS THIS TEST IGNORES", "ms": "TIGA PERKARA YANG DIABAIKAN UJIAN INI", "zh": "本测试忽略的三件事", "es": "TRES COSAS QUE ESTA PRUEBA IGNORA", "pt": "TRÊS COISAS QUE ESTE TESTE IGNORA"},
    "pr_nilai": {"id": "Saham Nilai", "en": "Value Stocks", "ms": "Saham Nilai", "zh": "价值股", "es": "Acciones Valor", "pt": "Ações de Valor"},
    "pr_dividen": {"id": "Pemburu Dividen", "en": "Dividend Hunter", "ms": "Pemburu Dividen", "zh": "高股息", "es": "Cazador de Dividendos", "pt": "Caçador de Dividendos"},
    "pr_kualitas": {"id": "Kualitas Tinggi", "en": "High Quality", "ms": "Kualiti Tinggi", "zh": "高质量", "es": "Alta Calidad", "pt": "Alta Qualidade"},
    "pr_kosong": {"id": "Tanpa Saringan", "en": "No Filter", "ms": "Tanpa Penapis", "zh": "不筛选", "es": "Sin Filtro", "pt": "Sem Filtro"},
    "pr_nilai_ket": {"id": "Harga murah dibanding laba dan nilai bukunya, tetapi labanya masih sehat. Cara klasik Benjamin Graham.", "en": "Cheap against earnings and book value, but with profitability still intact. The classic Benjamin Graham approach.", "ms": "Harga murah berbanding keuntungan dan nilai bukunya, tetapi keuntungannya masih sihat. Cara klasik Benjamin Graham.", "zh": "相对盈利和账面价值便宜，但盈利能力依然健康。本杰明·格雷厄姆的经典做法。", "es": "Barato frente a beneficios y valor contable, pero con rentabilidad intacta. El enfoque clásico de Benjamin Graham.", "pt": "Barato frente a lucros e valor patrimonial, mas com rentabilidade intacta. A abordagem clássica de Benjamin Graham."},
    "pr_dividen_ket": {"id": "Dividen besar dengan neraca yang tidak berat utang — supaya dividennya punya peluang bertahan.", "en": "Large dividends with a balance sheet not weighed down by debt — so the dividend has a chance of lasting.", "ms": "Dividen besar dengan kunci kira-kira yang tidak berat hutang — supaya dividennya berpeluang kekal.", "zh": "高股息，且资产负债表没有被债务压垮——这样股息才有持续下去的机会。", "es": "Dividendos altos con un balance no cargado de deuda, para que el dividendo tenga opción de mantenerse.", "pt": "Dividendos altos com balanço não sobrecarregado de dívida — para o dividendo ter chance de durar."},
    "pr_kualitas_ket": {"id": "Perusahaan yang produktif memakai modal dan tidak bergantung pada utang. Harga tidak disaring — kualitas jarang murah.", "en": "Companies that use capital productively without leaning on debt. Price is not filtered — quality is rarely cheap.", "ms": "Syarikat yang produktif menggunakan modal dan tidak bergantung pada hutang. Harga tidak ditapis — kualiti jarang murah.", "zh": "能高效运用资本、且不依赖债务的公司。不筛选估值——优质很少便宜。", "es": "Empresas que usan el capital de forma productiva sin apoyarse en deuda. El precio no se filtra: la calidad rara vez está barata.", "pt": "Empresas que usam capital de forma produtiva sem depender de dívida. O preço não é filtrado — qualidade raramente é barata."},
    "pr_kosong_ket": {"id": "Kembalikan semua ke nol untuk mulai dari awal.", "en": "Reset everything to zero and start over.", "ms": "Kembalikan semua ke sifar untuk mula semula.", "zh": "全部重置为零，重新开始。", "es": "Restablece todo a cero y empieza de nuevo.", "pt": "Zera tudo e recomeça."},
    "e_alamat_format": {"id": "Format alamat tidak sesuai untuk jaringan ini.", "en": "The address format does not match this network.", "ms": "Format alamat tidak sepadan dengan rangkaian ini.", "zh": "地址格式与该网络不符。", "es": "El formato de la dirección no corresponde a esta red.", "pt": "O formato do endereço não corresponde a esta rede."},
    "e_sidik_beda": {"id": "Sidik jari berkas TIDAK COCOK dengan yang diumumkan. Pembaruan dibatalkan demi keamanan.", "en": "The file fingerprint DOES NOT MATCH the published one. The update was cancelled for safety.", "ms": "Cap jari fail TIDAK SEPADAN dengan yang diumumkan. Kemas kini dibatalkan demi keselamatan.", "zh": "文件指纹与公布的值不一致。为安全起见，更新已取消。", "es": "La huella del archivo NO COINCIDE con la publicada. La actualización se canceló por seguridad.", "pt": "A impressão digital do arquivo NÃO CONFERE com a publicada. A atualização foi cancelada por segurança."},
    "e_berkas_dilarang": {"id": "Pembaruan mencoba mengganti berkas yang tidak diizinkan:", "en": "The update tried to replace a file that is not permitted:", "ms": "Kemas kini cuba menggantikan fail yang tidak dibenarkan:", "zh": "更新试图替换一个不被允许的文件：", "es": "La actualización intentó reemplazar un archivo no permitido:", "pt": "A atualização tentou substituir um arquivo não permitido:"},
    "c_kurs_tengah": {"id": "Harga di sini adalah kurs pasar antarbank, bukan kurs money changer — yang selalu lebih lebar. Anggap ini titik tengah, bukan harga yang akan Anda dapatkan di loket.", "en": "These are interbank market rates, not money-changer rates, which are always wider. Treat them as a midpoint, not the price you will get at a counter.", "ms": "Ini kadar pasaran antara bank, bukan kadar pengurup wang yang sentiasa lebih lebar. Anggap ia titik tengah, bukan harga yang anda akan dapat di kaunter.", "zh": "这里是银行间市场汇率，而非货币兑换商的报价——后者点差总是更宽。请把它当作中间价，而不是您在柜台能拿到的价格。", "es": "Son tipos del mercado interbancario, no de casas de cambio, que siempre son más amplios. Tómalos como punto medio, no como el precio que obtendrás en ventanilla.", "pt": "São taxas do mercado interbancário, não de casas de câmbio, que sempre têm spread maior. Encare como ponto médio, não como o preço que você vai conseguir no balcão."},
    "s_skor_pasar": {"id": "skor 80 di IDX tidak sebanding dengan 80 di Amerika", "en": "a score of 80 on one exchange is not comparable to 80 on another", "ms": "skor 80 di satu bursa tidak setanding dengan 80 di bursa lain", "zh": "某个市场的 80 分与另一个市场的 80 分并不可比", "es": "un 80 en una bolsa no es comparable con un 80 en otra", "pt": "uma nota 80 em uma bolsa não é comparável a 80 em outra"},
    "s_puncak_bantuan": {"id": "−80 berarti hanya koin yang turunnya tidak lebih dari 80% dari harga tertingginya.", "en": "−80 means only coins that have fallen no more than 80% from their all-time high.", "ms": "−80 bermakna hanya syiling yang jatuh tidak melebihi 80% daripada harga tertingginya.", "zh": "−80 表示只显示自历史高点回撤不超过 80% 的币种。", "es": "−80 significa solo monedas que han caído no más del 80% desde su máximo histórico.", "pt": "−80 significa apenas moedas que caíram no máximo 80% da máxima histórica."},
    "kal_forex_judul": {"id": "**Berapa lot yang boleh saya buka, dan berapa rupiah risikonya?**", "en": "**How many lots may I open, and what does that risk in my own currency?**", "ms": "**Berapa lot yang boleh saya buka, dan berapa risikonya dalam mata wang saya?**", "zh": "**我可以开多少手，用本币计算的风险是多少？**", "es": "**¿Cuántos lotes puedo abrir, y cuánto arriesgo en mi propia moneda?**", "pt": "**Quantos lotes posso abrir, e qual o risco na minha própria moeda?**"},
    "kal_kurs_gagal": {"id": "Kurs ke rupiah tidak bisa diambil, jadi risiko rupiah tidak bisa dihitung. Nilai pip dalam mata uang kutipan:", "en": "The conversion rate is unavailable, so risk in your own currency cannot be computed. Pip value in the quote currency:", "ms": "Kadar penukaran tidak dapat diambil, jadi risiko dalam mata wang anda tidak dapat dikira. Nilai pip dalam mata wang sebutan:", "zh": "无法获取换算汇率，因此无法计算以本币计的风险。以计价货币表示的每点价值：", "es": "No se pudo obtener el tipo de cambio, así que no puede calcularse el riesgo en tu moneda. Valor del pip en la divisa cotizada:", "pt": "Não foi possível obter a taxa de câmbio, então o risco na sua moeda não pode ser calculado. Valor do pip na moeda cotada:"},
    "kal_lot_kecil": {"id": "Ukuran posisi yang dihitung lebih kecil dari 0,01 lot. Modal Anda terlalu kecil untuk jarak stop sebesar itu, atau risikonya terlalu ketat.", "en": "The computed position is smaller than 0.01 lot. Your capital is too small for that stop distance, or the risk limit is too tight.", "ms": "Saiz posisi yang dikira lebih kecil daripada 0.01 lot. Modal anda terlalu kecil untuk jarak stop sebesar itu, atau risikonya terlalu ketat.", "zh": "计算出的仓位小于 0.01 手。相对于该止损距离，您的资金太小，或者风险上限设得太紧。", "es": "La posición calculada es menor que 0,01 lote. Tu capital es demasiado pequeño para esa distancia de stop, o el límite de riesgo es demasiado estrecho.", "pt": "A posição calculada é menor que 0,01 lote. Seu capital é pequeno demais para essa distância de stop, ou o limite de risco está apertado demais."},
    "kal_aturan_umum": {"id": "Aturan umum: 1–2% dari modal. Artinya kalau salah, kerugian dibatasi sebesar itu.", "en": "Common rule of thumb: 1–2% of capital. Meaning if you are wrong, the loss is capped there.", "ms": "Panduan umum: 1–2% daripada modal. Bermakna jika anda silap, kerugian terhad kepada jumlah itu.", "zh": "常用经验法则：本金的 1–2%。也就是说，如果判断错了，亏损就止步于此。", "es": "Regla habitual: 1–2% del capital. Es decir, si te equivocas, la pérdida queda limitada ahí.", "pt": "Regra comum: 1–2% do capital. Ou seja, se você errar, a perda para por ali."},
    "kal_melebihi_modal": {"id": "Nilai pembelian melebihi modal Anda ({p:.0f}%). Jarak stop loss terlalu sempit untuk ukuran risiko yang dipilih.", "en": "The position value exceeds your capital ({p:.0f}%). The stop-loss distance is too tight for the risk size chosen.", "ms": "Nilai posisi melebihi modal anda ({p:.0f}%). Jarak stop loss terlalu sempit untuk saiz risiko yang dipilih.", "zh": "持仓金额超过了您的资金（{p:.0f}%）。相对于所选风险额度，止损距离太近。", "es": "El valor de la posición supera tu capital ({p:.0f}%). La distancia del stop es demasiado estrecha para el riesgo elegido.", "pt": "O valor da posição excede seu capital ({p:.0f}%). A distância do stop é apertada demais para o risco escolhido."},
    "kal_stop_sempit": {"id": "Jarak stop loss terlalu sempit untuk ukuran risiko yang dipilih.", "en": "The stop-loss distance is too tight for the risk size you chose.", "ms": "Jarak stop loss terlalu sempit untuk saiz risiko yang dipilih.", "zh": "相对于您选择的风险额度，止损距离太近了。", "es": "La distancia del stop loss es demasiado estrecha para el riesgo elegido.", "pt": "A distância do stop loss é apertada demais para o risco escolhido."},
    "kal_rasio_buruk": {"id": "Anda mempertaruhkan lebih banyak daripada yang mungkin didapat. Agar tetap untung dalam jangka panjang, Anda harus benar lebih dari {p:.0f}% dari waktu — sesuatu yang jarang tercapai.", "en": "You are risking more than you stand to gain. To stay profitable long-term you would need to be right more than {p:.0f}% of the time — something rarely achieved.", "ms": "Anda mempertaruhkan lebih banyak daripada yang mungkin diperoleh. Untuk kekal untung jangka panjang, anda perlu betul lebih daripada {p:.0f}% masa — sesuatu yang jarang dicapai.", "zh": "您承担的风险大于可能的收益。要长期保持盈利，您的胜率必须超过 {p:.0f}%——这很少有人做到。", "es": "Estás arriesgando más de lo que puedes ganar. Para ser rentable a largo plazo tendrías que acertar más del {p:.0f}% de las veces, algo que rara vez se logra.", "pt": "Você está arriscando mais do que pode ganhar. Para ser lucrativo no longo prazo, precisaria acertar mais de {p:.0f}% das vezes — algo raramente alcançado."},
    "kal_rasio_baik": {"id": "Dengan rasio ini, Anda cukup benar {p:.0f}% dari waktu untuk impas — sisanya menjadi keuntungan.", "en": "At this ratio you only need to be right {p:.0f}% of the time to break even — anything beyond that is profit.", "ms": "Dengan nisbah ini, anda hanya perlu betul {p:.0f}% masa untuk pulang modal — selebihnya menjadi keuntungan.", "zh": "在这个盈亏比下，您只需 {p:.0f}% 的胜率即可保本，超过部分即为盈利。", "es": "Con esta relación solo necesitas acertar el {p:.0f}% de las veces para no perder; lo demás es beneficio.", "pt": "Com essa relação, você só precisa acertar {p:.0f}% das vezes para empatar — o resto vira lucro."},
    "j_belum_tutup": {"id": "Belum ada transaksi yang tertutup. Statistik muncul setelah ada penjualan yang berpasangan dengan pembelian sebelumnya.", "en": "No closed trades yet. Statistics appear once a sale is matched against an earlier purchase.", "ms": "Belum ada dagangan yang ditutup. Statistik muncul selepas ada jualan yang dipadankan dengan belian terdahulu.", "zh": "尚无已平仓交易。当卖出与此前的买入配对后，统计数据才会出现。", "es": "Aún no hay operaciones cerradas. Las estadísticas aparecen cuando una venta se empareja con una compra previa.", "pt": "Ainda não há operações encerradas. As estatísticas aparecem quando uma venda é pareada com uma compra anterior."},
    "j_perlu_menang": {"id": "Dengan rasio {r:.2f}, Anda perlu benar setidaknya <b>{p:.0f}%</b> dari waktu untuk impas. Saat ini <b class=\"turun\">{s:.0f}%</b> — kerugian rata-rata Anda terlalu besar dibanding keuntungannya. Yang perlu diperbaiki biasanya bukan cara memilih saham, melainkan kapan memotong rugi.", "en": "At a ratio of {r:.2f}, you need to be right at least <b>{p:.0f}%</b> of the time to break even. You are at <b class=\"turun\">{s:.0f}%</b> — your average loss is too large relative to your average win. What usually needs fixing is not stock selection, but when you cut losses.", "ms": "Dengan nisbah {r:.2f}, anda perlu betul sekurang-kurangnya <b>{p:.0f}%</b> masa untuk pulang modal. Kini <b class=\"turun\">{s:.0f}%</b> — kerugian purata anda terlalu besar berbanding keuntungannya. Yang perlu dibaiki biasanya bukan cara memilih saham, tetapi bila memotong rugi.", "zh": "在 {r:.2f} 的盈亏比下，您的胜率至少要达到 <b>{p:.0f}%</b> 才能保本。目前是 <b class=\"turun\">{s:.0f}%</b>——您的平均亏损相对平均盈利过大。通常需要改进的不是选股，而是何时止损。", "es": "Con una relación de {r:.2f}, necesitas acertar al menos el <b>{p:.0f}%</b> de las veces para no perder. Estás en <b class=\"turun\">{s:.0f}%</b>: tu pérdida media es demasiado grande frente a tu ganancia media. Lo que suele fallar no es la selección, sino cuándo cortas pérdidas.", "pt": "Com uma relação de {r:.2f}, você precisa acertar pelo menos <b>{p:.0f}%</b> das vezes para empatar. Está em <b class=\"turun\">{s:.0f}%</b> — sua perda média é grande demais frente ao ganho médio. O que costuma precisar de ajuste não é a escolha, e sim quando você corta prejuízo."},
    "j_pola_sehat": {"id": "Dengan rasio {r:.2f}, Anda cukup benar <b>{p:.0f}%</b> dari waktu untuk impas, dan saat ini <b class=\"naik\">{s:.0f}%</b>. Pola ini sehat: kemenangan Anda lebih besar daripada kekalahan.", "en": "At a ratio of {r:.2f}, you only need <b>{p:.0f}%</b> to break even, and you are at <b class=\"naik\">{s:.0f}%</b>. That is a healthy pattern: your wins are larger than your losses.", "ms": "Dengan nisbah {r:.2f}, anda hanya perlu <b>{p:.0f}%</b> untuk pulang modal, dan kini <b class=\"naik\">{s:.0f}%</b>. Corak ini sihat: kemenangan anda lebih besar daripada kekalahan.", "zh": "在 {r:.2f} 的盈亏比下，您只需 <b>{p:.0f}%</b> 的胜率即可保本，而目前是 <b class=\"naik\">{s:.0f}%</b>。这是健康的模式：您的盈利大于亏损。", "es": "Con una relación de {r:.2f}, solo necesitas <b>{p:.0f}%</b> para no perder, y estás en <b class=\"naik\">{s:.0f}%</b>. Es un patrón sano: tus ganancias son mayores que tus pérdidas.", "pt": "Com uma relação de {r:.2f}, você só precisa de <b>{p:.0f}%</b> para empatar, e está em <b class=\"naik\">{s:.0f}%</b>. Padrão saudável: seus ganhos são maiores que suas perdas."},
    "bt_data_interval": {"id": "tidak tersedia pada periode ini. Rentang waktu pendek biasanya tidak ada untuk saham yang jarang diperdagangkan — coba rentang yang lebih panjang.", "en": "is not available for this period. Short timeframes are usually missing for thinly traded stocks — try a longer one.", "ms": "tidak tersedia untuk tempoh ini. Jangka masa pendek biasanya tiada bagi saham yang jarang didagangkan — cuba yang lebih panjang.", "zh": "在此周期内不可用。交投稀少的股票通常没有短周期数据——请尝试更长的周期。", "es": "no está disponible para este periodo. Los marcos cortos suelen faltar en valores poco negociados: prueba uno más largo.", "pt": "não está disponível para este período. Tempos gráficos curtos costumam faltar em ativos pouco negociados — tente um maior."},
    "bt_batang_kurang": {"id": "batang data — terlalu sedikit untuk diuji. Pilih periode yang lebih panjang, atau rentang waktu yang lebih pendek.", "en": "bars of data — too few to test. Choose a longer period, or a shorter timeframe.", "ms": "bar data — terlalu sedikit untuk diuji. Pilih tempoh yang lebih panjang, atau jangka masa yang lebih pendek.", "zh": "根K线——数量太少，无法测试。请选择更长的周期，或更短的时间尺度。", "es": "barras de datos: muy pocas para probar. Elige un periodo más largo o un marco temporal más corto.", "pt": "barras de dados — poucas demais para testar. Escolha um período maior ou um tempo gráfico menor."},
    "bt_spread_bantuan": {"id": "Selisih harga beli dan jual yang dipungut broker. Ini biaya utama di forex — bukan komisi persen seperti saham.", "en": "The gap between bid and ask that the broker charges. This is the main cost in forex — not a percentage commission as with stocks.", "ms": "Jurang antara harga beli dan jual yang dikenakan broker. Ini kos utama dalam forex — bukan komisen peratus seperti saham.", "zh": "经纪商收取的买卖价差。这是外汇的主要成本，而不是像股票那样按百分比收佣金。", "es": "La diferencia entre compra y venta que cobra el bróker. Es el coste principal en forex, no una comisión porcentual como en acciones.", "pt": "A diferença entre compra e venda cobrada pela corretora. É o custo principal no forex — não uma comissão percentual como em ações."},
    "pdf_kaki": {"id": "Dibuat dengan Terminal Investasi. Data berasal dari sumber terbuka dan dapat tertunda. Dokumen ini bukan nasihat investasi.", "en": "Generated with Terminal Investasi. Data comes from open sources and may be delayed. This document is not investment advice.", "ms": "Dijana dengan Terminal Investasi. Data daripada sumber terbuka dan mungkin tertangguh. Dokumen ini bukan nasihat pelaburan.", "zh": "由 Terminal Investasi 生成。数据来自公开来源，可能存在延迟。本文件不构成投资建议。", "es": "Generado con Terminal Investasi. Los datos provienen de fuentes abiertas y pueden estar retrasados. Este documento no es asesoramiento de inversión.", "pt": "Gerado com Terminal Investasi. Os dados vêm de fontes abertas e podem estar atrasados. Este documento não é recomendação de investimento."},
    "pdf_fpdf_hilang": {"id": "Pustaka fpdf2 belum terpasang. Tutup aplikasi lalu jalankan peluncurnya sekali lagi — pustaka yang kurang akan dipasang otomatis.", "en": "The fpdf2 library is not installed. Close the app and run the launcher once more — missing libraries are installed automatically.", "ms": "Pustaka fpdf2 belum dipasang. Tutup aplikasi dan jalankan pelancar sekali lagi — pustaka yang kurang akan dipasang secara automatik.", "zh": "未安装 fpdf2 库。请关闭应用并重新运行启动器——缺失的库会自动安装。", "es": "La librería fpdf2 no está instalada. Cierra la aplicación y vuelve a ejecutar el lanzador: las librerías que faltan se instalan solas.", "pt": "A biblioteca fpdf2 não está instalada. Feche o aplicativo e execute o inicializador novamente — bibliotecas ausentes são instaladas automaticamente."},
    "j_alasan_label": {"id": "Alasan keputusan ini", "en": "Why you made this decision", "ms": "Sebab keputusan ini", "zh": "做出这个决定的理由", "es": "Por qué tomaste esta decisión", "pt": "Por que você tomou esta decisão"},
    "p_naik": {"id": "naik", "en": "up", "ms": "naik", "zh": "上涨", "es": "suben", "pt": "em alta"},
    "p_turun": {"id": "turun", "en": "down", "ms": "turun", "zh": "下跌", "es": "bajan", "pt": "em baixa"},
    "p_dipantau": {"id": "simbol dipantau", "en": "symbols tracked", "ms": "simbol dipantau", "zh": "个标的", "es": "símbolos seguidos", "pt": "símbolos monitorados"},
    "p_segar60": {"id": "data disegarkan tiap 60 detik", "en": "data refreshes every 60 seconds", "ms": "data disegarkan setiap 60 saat", "zh": "数据每 60 秒刷新一次", "es": "los datos se actualizan cada 60 segundos", "pt": "dados atualizados a cada 60 segundos"},
    "p_menguat": {"id": "menguat", "en": "gained", "ms": "menguat", "zh": "上涨", "es": "subieron", "pt": "subiram"},
    "p_melemah": {"id": "melemah", "en": "declined", "ms": "melemah", "zh": "下跌", "es": "bajaron", "pt": "caíram"},
    "p_24jam": {"id": "dalam 24 jam terakhir", "en": "in the last 24 hours", "ms": "dalam 24 jam terakhir", "zh": "过去 24 小时内", "es": "en las últimas 24 horas", "pt": "nas últimas 24 horas"},
    "p_sumber_kripto": {"id": "sumber CoinGecko & alternative.me, keduanya gratis tanpa API key", "en": "sources: CoinGecko & alternative.me, both free without an API key", "ms": "sumber CoinGecko & alternative.me, kedua-duanya percuma tanpa kunci API", "zh": "数据来自 CoinGecko 与 alternative.me，均免费且无需 API 密钥", "es": "fuentes: CoinGecko y alternative.me, ambas gratis sin clave API", "pt": "fontes: CoinGecko e alternative.me, ambas grátis sem chave de API"},
    "p_kelompok": {"id": "Kelompok", "en": "Group", "ms": "Kumpulan", "zh": "分组", "es": "Grupo", "pt": "Grupo"},
    "p_fx_utama": {"id": "Pasangan Utama", "en": "Majors", "ms": "Pasangan Utama", "zh": "主要货币对", "es": "Principales", "pt": "Principais"},
    "p_fx_rupiah": {"id": "Terhadap Rupiah", "en": "Against IDR", "ms": "Terhadap Rupiah", "zh": "兑印尼盾", "es": "Frente al IDR", "pt": "Contra o IDR"},
    "p_fx_silang": {"id": "Silang", "en": "Crosses", "ms": "Silang", "zh": "交叉盘", "es": "Cruces", "pt": "Cruzados"},
    "p_saham_id_ket": {"id": "Sembilan saham berkapitalisasi besar di Bursa Efek Indonesia. Harga dalam rupiah per lembar.", "en": "Nine large-cap names on the Indonesia Stock Exchange. Prices in rupiah per share.", "ms": "Sembilan saham permodalan besar di Bursa Saham Indonesia. Harga dalam rupiah seunit.", "zh": "印尼证券交易所九只大盘股。价格以每股印尼盾计。", "es": "Nueve valores de gran capitalización de la Bolsa de Indonesia. Precios en rupias por acción.", "pt": "Nove ações de grande capitalização da Bolsa da Indonésia. Preços em rupias por ação."},
    "g_harga_akhir": {"id": "Harga terakhir", "en": "Last price", "ms": "Harga terakhir", "zh": "最新价", "es": "Último precio", "pt": "Último preço"},
    "g_perubahan": {"id": "Perubahan periode", "en": "Period change", "ms": "Perubahan tempoh", "zh": "区间涨跌", "es": "Cambio del periodo", "pt": "Variação do período"},
    "g_tertinggi": {"id": "Tertinggi periode", "en": "Period high", "ms": "Tertinggi tempoh", "zh": "区间最高", "es": "Máximo del periodo", "pt": "Máxima do período"},
    "g_terendah": {"id": "Terendah periode", "en": "Period low", "ms": "Terendah tempoh", "zh": "区间最低", "es": "Mínimo del periodo", "pt": "Mínima do período"},
    "g_periode": {"id": "Periode", "en": "Period", "ms": "Tempoh", "zh": "周期", "es": "Periodo", "pt": "Período"},
    "g_interval": {"id": "Interval", "en": "Interval", "ms": "Selang", "zh": "间隔", "es": "Intervalo", "pt": "Intervalo"},
    "g_indikator": {"id": "Indikator", "en": "Indicators", "ms": "Penunjuk", "zh": "指标", "es": "Indicadores", "pt": "Indicadores"},
    "s_dalam_daftar": {"id": "saham dalam daftar, harga dan kapitalisasi dalam", "en": "stocks in this list; prices and market caps in", "ms": "saham dalam senarai, harga dan permodalan dalam", "zh": "只股票，价格与市值以", "es": "acciones en la lista; precios y capitalización en", "pt": "ações na lista; preços e valor de mercado em"},
    "s_lama_pertama": {"id": "Penyaringan pertama memakan waktu 20–40 detik karena setiap saham diambil satu per satu; sesudah itu hasilnya disimpan satu jam.", "en": "The first screen takes 20–40 seconds because each stock is fetched individually; after that results are cached for an hour.", "ms": "Penyaringan pertama mengambil masa 20–40 saat kerana setiap saham diambil satu per satu; selepas itu hasilnya disimpan sejam.", "zh": "首次筛选需要 20–40 秒，因为每只股票都是单独获取的；之后结果会缓存一小时。", "es": "El primer filtrado tarda 20–40 segundos porque cada acción se descarga por separado; después los resultados se cachean una hora.", "pt": "A primeira filtragem leva 20–40 segundos porque cada ação é buscada individualmente; depois os resultados ficam em cache por uma hora."},
    "bt_ma_cepat": {"id": "Rata-rata cepat (batang)", "en": "Fast average (bars)", "ms": "Purata pantas (bar)", "zh": "快速均线（K线数）", "es": "Media rápida (barras)", "pt": "Média rápida (barras)"},
    "bt_ma_lambat": {"id": "Rata-rata lambat (batang)", "en": "Slow average (bars)", "ms": "Purata perlahan (bar)", "zh": "慢速均线（K线数）", "es": "Media lenta (barras)", "pt": "Média lenta (barras)"},
    "bt_rsi_periode": {"id": "Periode RSI", "en": "RSI period", "ms": "Tempoh RSI", "zh": "RSI 周期", "es": "Periodo RSI", "pt": "Período do RSI"},
    "bt_rsi_beli": {"id": "Beli saat RSI di bawah", "en": "Buy when RSI below", "ms": "Beli apabila RSI di bawah", "zh": "RSI 低于此值时买入", "es": "Comprar cuando el RSI baje de", "pt": "Comprar quando o RSI ficar abaixo de"},
    "bt_rsi_jual": {"id": "Jual saat RSI di atas", "en": "Sell when RSI above", "ms": "Jual apabila RSI di atas", "zh": "RSI 高于此值时卖出", "es": "Vender cuando el RSI supere", "pt": "Vender quando o RSI ficar acima de"},
    "bt_ma_periode": {"id": "Periode rata-rata (batang)", "en": "Average period (bars)", "ms": "Tempoh purata (bar)", "zh": "均线周期（K线数）", "es": "Periodo de la media (barras)", "pt": "Período da média (barras)"},
    "st_ma_silang": {"id": "Perpotongan Rata-rata", "en": "Moving Average Crossover", "ms": "Silangan Purata Bergerak", "zh": "均线交叉", "es": "Cruce de Medias", "pt": "Cruzamento de Médias"},
    "st_rsi": {"id": "RSI", "en": "RSI", "ms": "RSI", "zh": "RSI", "es": "RSI", "pt": "RSI"},
    "st_atas_ma": {"id": "Di Atas Rata-rata", "en": "Above Moving Average", "ms": "Di Atas Purata", "zh": "站上均线", "es": "Por Encima de la Media", "pt": "Acima da Média"},
    "st_beli_tahan": {"id": "Beli dan Tahan", "en": "Buy and Hold", "ms": "Beli dan Simpan", "zh": "买入持有", "es": "Comprar y Mantener", "pt": "Comprar e Segurar"},
    "bt_unggul": {"id": "Strategi ini mengungguli beli-dan-tahan sebesar", "en": "This strategy beat buy-and-hold by", "ms": "Strategi ini mengatasi beli-dan-simpan sebanyak", "zh": "该策略跑赢买入持有", "es": "Esta estrategia superó a comprar y mantener por", "pt": "Esta estratégia superou comprar-e-segurar em"},
    "bt_selama": {"id": "selama", "en": "over", "ms": "selama", "zh": "，历时", "es": "en", "pt": "ao longo de"},
    "bt_kalah": {"id": "Strategi ini <b class=\"turun\">kalah</b> dari sekadar membeli lalu mendiamkannya, selisih", "en": "This strategy <b class=\"turun\">lost</b> to simply buying and holding, by", "ms": "Strategi ini <b class=\"turun\">kalah</b> berbanding sekadar membeli dan menyimpan, beza", "zh": "该策略<b class=\"turun\">输给</b>了单纯的买入持有，差距为", "es": "Esta estrategia <b class=\"turun\">perdió</b> frente a comprar y mantener, por", "pt": "Esta estratégia <b class=\"turun\">perdeu</b> para simplesmente comprar e segurar, por"},
    "pf_tambah": {"id": "Tambah atau hapus posisi", "en": "Add or remove a position", "ms": "Tambah atau buang posisi", "zh": "添加或删除持仓", "es": "Añadir o quitar posición", "pt": "Adicionar ou remover posição"},
    "pf_harga_beli": {"id": "Harga beli rata-rata", "en": "Average buy price", "ms": "Harga belian purata", "zh": "平均买入价", "es": "Precio medio de compra", "pt": "Preço médio de compra"},
    "pf_belum": {"id": "Belum ada posisi. Tambahkan lewat panel di atas. Data disimpan lokal di folder data/, tidak dikirim ke mana pun.", "en": "No positions yet. Add one using the panel above. Data is stored locally in the data/ folder and sent nowhere.", "ms": "Belum ada posisi. Tambah melalui panel di atas. Data disimpan setempat dalam folder data/ dan tidak dihantar ke mana-mana.", "zh": "尚无持仓。请使用上方面板添加。数据保存在本地 data/ 文件夹，不会发送到任何地方。", "es": "Aún no hay posiciones. Añade una en el panel de arriba. Los datos se guardan localmente en data/ y no se envían a ningún sitio.", "pt": "Nenhuma posição ainda. Adicione pelo painel acima. Os dados ficam salvos localmente em data/ e não são enviados a lugar nenhum."},
    "pf_isi_dulu": {"id": "Simbol, jumlah, dan harga beli harus diisi.", "en": "Symbol, quantity, and buy price are all required.", "ms": "Simbol, kuantiti dan harga belian mesti diisi.", "zh": "代码、数量和买入价都必须填写。", "es": "Símbolo, cantidad y precio de compra son obligatorios.", "pt": "Símbolo, quantidade e preço de compra são obrigatórios."},
    "pf_hapus_posisi": {"id": "Hapus posisi", "en": "Remove positions", "ms": "Buang posisi", "zh": "删除持仓", "es": "Quitar posiciones", "pt": "Remover posições"},
    "pf_pilih_hapus": {"id": "Pilih yang mau dihapus", "en": "Select what to remove", "ms": "Pilih yang hendak dibuang", "zh": "选择要删除的项", "es": "Selecciona qué quitar", "pt": "Selecione o que remover"},
    "pf_hapus_terpilih": {"id": "HAPUS POSISI TERPILIH", "en": "REMOVE SELECTED", "ms": "BUANG POSISI TERPILIH", "zh": "删除所选持仓", "es": "QUITAR SELECCIONADAS", "pt": "REMOVER SELECIONADAS"},
    "pf_total_modal": {"id": "TOTAL MODAL", "en": "TOTAL COST", "ms": "JUMLAH MODAL", "zh": "总成本", "es": "COSTE TOTAL", "pt": "CUSTO TOTAL"},
    "pf_nilai_kini": {"id": "NILAI SEKARANG", "en": "CURRENT VALUE", "ms": "NILAI SEMASA", "zh": "当前市值", "es": "VALOR ACTUAL", "pt": "VALOR ATUAL"},
    "pf_laba_rugi": {"id": "LABA / RUGI", "en": "PROFIT / LOSS", "ms": "UNTUNG / RUGI", "zh": "盈亏", "es": "GANANCIA / PÉRDIDA", "pt": "LUCRO / PREJUÍZO"},
    "pf_jml_posisi": {"id": "JUMLAH POSISI", "en": "POSITIONS", "ms": "BILANGAN POSISI", "zh": "持仓数量", "es": "POSICIONES", "pt": "POSIÇÕES"},
    "pf_rincian": {"id": "Rincian posisi", "en": "Position detail", "ms": "Perincian posisi", "zh": "持仓明细", "es": "Detalle de posiciones", "pt": "Detalhe das posições"},
    "pf_alokasi": {"id": "Alokasi berdasarkan nilai", "en": "Allocation by value", "ms": "Peruntukan mengikut nilai", "zh": "按市值分布", "es": "Asignación por valor", "pt": "Alocação por valor"},
    "pf_lr_posisi": {"id": "Laba / rugi per posisi", "en": "Profit / loss by position", "ms": "Untung / rugi setiap posisi", "zh": "各持仓盈亏", "es": "Ganancia / pérdida por posición", "pt": "Lucro / prejuízo por posição"},
    "pf_harga_kini": {"id": "Harga kini", "en": "Current price", "ms": "Harga semasa", "zh": "现价", "es": "Precio actual", "pt": "Preço atual"},
    "pf_modal": {"id": "Modal", "en": "Cost", "ms": "Modal", "zh": "成本", "es": "Coste", "pt": "Custo"},
    "pf_hari_ini": {"id": "Hari ini %", "en": "Today %", "ms": "Hari ini %", "zh": "今日 %", "es": "Hoy %", "pt": "Hoje %"},
    "pf_tak_terbaca": {"id": "Tidak ada posisi yang harganya berhasil diambil.", "en": "No position prices could be retrieved.", "ms": "Tiada harga posisi berjaya diambil.", "zh": "未能获取任何持仓的价格。", "es": "No se pudo obtener el precio de ninguna posición.", "pt": "Não foi possível obter o preço de nenhuma posição."},
    "j_belum_catatan": {"id": "Belum ada catatan.", "en": "No entries yet.", "ms": "Belum ada catatan.", "zh": "尚无记录。", "es": "Aún no hay entradas.", "pt": "Nenhum registro ainda."},
    "j_belum_analisis": {"id": "Belum ada catatan untuk dianalisis.", "en": "No entries to analyse yet.", "ms": "Belum ada catatan untuk dianalisis.", "zh": "尚无可供分析的记录。", "es": "Aún no hay entradas para analizar.", "pt": "Ainda não há registros para analisar."},
    "j_aksi": {"id": "Aksi", "en": "Action", "ms": "Tindakan", "zh": "操作", "es": "Acción", "pt": "Ação"},
    "j_beli": {"id": "Beli", "en": "Buy", "ms": "Beli", "zh": "买入", "es": "Compra", "pt": "Compra"},
    "j_jual": {"id": "Jual", "en": "Sell", "ms": "Jual", "zh": "卖出", "es": "Venta", "pt": "Venda"},
    "j_jumlah": {"id": "Jumlah (lembar/unit)", "en": "Quantity (shares/units)", "ms": "Kuantiti (unit)", "zh": "数量（股/单位）", "es": "Cantidad (acciones/unidades)", "pt": "Quantidade (ações/unidades)"},
    "j_tanggal": {"id": "Tanggal", "en": "Date", "ms": "Tarikh", "zh": "日期", "es": "Fecha", "pt": "Data"},
    "j_emosi": {"id": "Suasana hati saat memutuskan", "en": "How you felt when deciding", "ms": "Perasaan ketika membuat keputusan", "zh": "做决定时的心情", "es": "Cómo te sentías al decidir", "pt": "Como você se sentia ao decidir"},
    "j_simpan": {"id": "SIMPAN CATATAN", "en": "SAVE ENTRY", "ms": "SIMPAN CATATAN", "zh": "保存记录", "es": "GUARDAR ENTRADA", "pt": "SALVAR REGISTRO"},
    "j_tercatat": {"id": "Tercatat.", "en": "Recorded.", "ms": "Tercatat.", "zh": "已记录。", "es": "Registrado.", "pt": "Registrado."},
    "j_isi_dulu": {"id": "Simbol, jumlah, dan harga harus diisi.", "en": "Symbol, quantity, and price are all required.", "ms": "Simbol, kuantiti dan harga mesti diisi.", "zh": "代码、数量和价格都必须填写。", "es": "Símbolo, cantidad y precio son obligatorios.", "pt": "Símbolo, quantidade e preço são obrigatórios."},
    "j_suasana": {"id": "Suasana", "en": "Mood", "ms": "Perasaan", "zh": "心情", "es": "Ánimo", "pt": "Humor"},
    "j_hapus": {"id": "Hapus catatan", "en": "Delete entries", "ms": "Padam catatan", "zh": "删除记录", "es": "Eliminar entradas", "pt": "Excluir registros"},
    "j_unduh": {"id": "UNDUH JURNAL (CSV)", "en": "DOWNLOAD JOURNAL (CSV)", "ms": "MUAT TURUN JURNAL (CSV)", "zh": "下载日志 (CSV)", "es": "DESCARGAR DIARIO (CSV)", "pt": "BAIXAR DIÁRIO (CSV)"},
    "em_tenang": {"id": "Tenang", "en": "Calm", "ms": "Tenang", "zh": "平静", "es": "Tranquilo", "pt": "Calmo"},
    "em_ragu": {"id": "Ragu", "en": "Uncertain", "ms": "Ragu", "zh": "犹豫", "es": "Dudoso", "pt": "Incerto"},
    "em_fomo": {"id": "Takut ketinggalan", "en": "Fear of missing out", "ms": "Takut ketinggalan", "zh": "怕错过", "es": "Miedo a quedarse fuera", "pt": "Medo de ficar de fora"},
    "em_panik": {"id": "Panik", "en": "Panicked", "ms": "Panik", "zh": "恐慌", "es": "En pánico", "pt": "Em pânico"},
    "em_yakin": {"id": "Percaya diri", "en": "Confident", "ms": "Yakin", "zh": "自信", "es": "Confiado", "pt": "Confiante"},
    "em_terpaksa": {"id": "Terpaksa", "en": "Forced", "ms": "Terpaksa", "zh": "被迫", "es": "Forzado", "pt": "Forçado"},
    "r_isi": {"id": "Isi laporan", "en": "Report contents", "ms": "Kandungan laporan", "zh": "报告内容", "es": "Contenido del informe", "pt": "Conteúdo do relatório"},
    "r_penyusun": {"id": "Disusun oleh", "en": "Prepared by", "ms": "Disediakan oleh", "zh": "编制者", "es": "Preparado por", "pt": "Preparado por"},
    "r_catatan": {"id": "Catatan pembuka (boleh dikosongkan)", "en": "Opening note (optional)", "ms": "Nota pembuka (pilihan)", "zh": "开头备注（可选）", "es": "Nota inicial (opcional)", "pt": "Nota de abertura (opcional)"},
    "r_catatan_ph": {"id": "Ringkasan singkat, konteks, atau pesan untuk pembaca.", "en": "A short summary, some context, or a message for the reader.", "ms": "Ringkasan pendek, konteks, atau pesanan untuk pembaca.", "zh": "简短摘要、背景说明，或给读者的一段话。", "es": "Un breve resumen, algo de contexto o un mensaje para el lector.", "pt": "Um breve resumo, algum contexto ou uma mensagem ao leitor."},
    "r_pf_kosong": {"id": "Portofolio masih kosong. Isi dulu di halaman Portofolio.", "en": "Your portfolio is empty. Fill it in on the Portfolio page first.", "ms": "Portfolio masih kosong. Isi dahulu di halaman Portfolio.", "zh": "投资组合为空，请先在「投资组合」页面填写。", "es": "Tu cartera está vacía. Complétala primero en la página Cartera.", "pt": "Sua carteira está vazia. Preencha primeiro na página Carteira."},
    "r_j_kosong": {"id": "Jurnal masih kosong. Isi dulu di halaman Jurnal.", "en": "Your journal is empty. Fill it in on the Journal page first.", "ms": "Jurnal masih kosong. Isi dahulu di halaman Jurnal.", "zh": "交易日志为空，请先在「交易日志」页面填写。", "es": "Tu diario está vacío. Complétalo primero en la página Diario.", "pt": "Seu diário está vazio. Preencha primeiro na página Diário."},
    "r_d_kosong": {"id": "Belum ada alamat dompet. Tambahkan dulu di halaman Dompet Kripto.", "en": "No wallet addresses yet. Add one on the Crypto Wallet page first.", "ms": "Belum ada alamat dompet. Tambah dahulu di halaman Dompet Kripto.", "zh": "尚未添加钱包地址，请先在「加密钱包」页面添加。", "es": "Aún no hay direcciones. Añade una primero en la página Billetera Cripto.", "pt": "Nenhum endereço ainda. Adicione primeiro na página Carteira Cripto."},
    "r_w_kosong": {"id": "Watchlist masih kosong.", "en": "Your watchlist is empty.", "ms": "Senarai pantau masih kosong.", "zh": "自选列表为空。", "es": "Tu lista de seguimiento está vacía.", "pt": "Sua lista de acompanhamento está vazia."},
    "r_buat": {"id": "BUAT PDF", "en": "GENERATE PDF", "ms": "JANA PDF", "zh": "生成 PDF", "es": "GENERAR PDF", "pt": "GERAR PDF"},
    "r_siap": {"id": "PDF siap", "en": "PDF ready", "ms": "PDF sedia", "zh": "PDF 已就绪", "es": "PDF listo", "pt": "PDF pronto"},
    "r_unduh": {"id": "UNDUH PDF", "en": "DOWNLOAD PDF", "ms": "MUAT TURUN PDF", "zh": "下载 PDF", "es": "DESCARGAR PDF", "pt": "BAIXAR PDF"},
    "r_gagal": {"id": "Gagal membuat PDF", "en": "Failed to generate the PDF", "ms": "Gagal menjana PDF", "zh": "生成 PDF 失败", "es": "No se pudo generar el PDF", "pt": "Falha ao gerar o PDF"},
    "kf_pasangan": {"id": "Pasangan", "en": "Pair", "ms": "Pasangan", "zh": "货币对", "es": "Par", "pt": "Par"},
    "kf_modal": {"id": "Modal akun", "en": "Account capital", "ms": "Modal akaun", "zh": "账户资金", "es": "Capital de la cuenta", "pt": "Capital da conta"},
    "kf_risiko": {"id": "Risiko per transaksi (%)", "en": "Risk per trade (%)", "ms": "Risiko setiap dagangan (%)", "zh": "单笔风险 (%)", "es": "Riesgo por operación (%)", "pt": "Risco por operação (%)"},
    "kf_lot": {"id": "Ukuran lot", "en": "Lot size", "ms": "Saiz lot", "zh": "手数规格", "es": "Tamaño del lote", "pt": "Tamanho do lote"},
    "kf_stop": {"id": "Jarak stop loss (pip)", "en": "Stop-loss distance (pips)", "ms": "Jarak stop loss (pip)", "zh": "止损距离（点）", "es": "Distancia del stop (pips)", "pt": "Distância do stop (pips)"},
    "kf_target": {"id": "Jarak target (pip)", "en": "Target distance (pips)", "ms": "Jarak sasaran (pip)", "zh": "目标距离（点）", "es": "Distancia del objetivo (pips)", "pt": "Distância do alvo (pips)"},
    "kf_harga_kini": {"id": "HARGA SEKARANG", "en": "CURRENT PRICE", "ms": "HARGA SEMASA", "zh": "当前价格", "es": "PRECIO ACTUAL", "pt": "PREÇO ATUAL"},
    "kf_nilai_pip": {"id": "NILAI 1 PIP", "en": "VALUE OF 1 PIP", "ms": "NILAI 1 PIP", "zh": "1 点价值", "es": "VALOR DE 1 PIP", "pt": "VALOR DE 1 PIP"},
    "kf_per_lot": {"id": "per", "en": "per", "ms": "setiap", "zh": "每", "es": "por", "pt": "por"},
    "kf_boleh_buka": {"id": "BOLEH BUKA", "en": "MAY OPEN", "ms": "BOLEH BUKA", "zh": "可开仓", "es": "PUEDES ABRIR", "pt": "PODE ABRIR"},
    "kf_unit": {"id": "unit", "en": "units of", "ms": "unit", "zh": "单位", "es": "unidades de", "pt": "unidades de"},
    "kf_risiko_kartu": {"id": "RISIKO", "en": "RISK", "ms": "RISIKO", "zh": "风险", "es": "RIESGO", "pt": "RISCO"},
    "kf_dari_modal": {"id": "dari modal", "en": "of capital", "ms": "daripada modal", "zh": "占资金", "es": "del capital", "pt": "do capital"},
    "kf_kalau_target": {"id": "kalau target", "en": "if target of", "ms": "jika sasaran", "zh": "若达到", "es": "si se alcanza el objetivo de", "pt": "se o alvo de"},
    "kf_tercapai": {"id": "pip tercapai", "en": "pips is reached", "ms": "pip dicapai", "zh": "点的目标", "es": "pips", "pt": "pips for atingido"},
    "kf_rasio": {"id": "RASIO UNTUNG : RUGI", "en": "REWARD : RISK", "ms": "NISBAH UNTUNG : RUGI", "zh": "盈亏比", "es": "BENEFICIO : RIESGO", "pt": "RETORNO : RISCO"},
    "kf_rasio_ket": {"id": "di atas 1 berarti target lebih jauh dari stop", "en": "above 1 means the target is further than the stop", "ms": "melebihi 1 bermakna sasaran lebih jauh daripada stop", "zh": "大于 1 表示目标比止损更远", "es": "por encima de 1 significa que el objetivo está más lejos que el stop", "pt": "acima de 1 significa que o alvo está mais longe que o stop"},
    "kf_menang_min": {"id": "MENANG MINIMAL", "en": "MIN WIN RATE", "ms": "KADAR MENANG MINIMUM", "zh": "最低胜率", "es": "TASA DE ACIERTO MÍNIMA", "pt": "TAXA MÍNIMA DE ACERTO"},
    "kf_agar_untung": {"id": "agar tidak merugi jangka panjang", "en": "to avoid losing over the long run", "ms": "untuk mengelak rugi jangka panjang", "zh": "以避免长期亏损", "es": "para no perder a largo plazo", "pt": "para não perder no longo prazo"},
    "ka_judul": {"id": "**Berapa harga rata-rata saya setelah membeli lagi?**", "en": "**What becomes my average price after buying more?**", "ms": "**Berapa harga purata saya selepas membeli lagi?**", "zh": "**再次买入后，我的平均成本是多少？**", "es": "**¿Cuál será mi precio medio tras comprar más?**", "pt": "**Qual será meu preço médio depois de comprar mais?**"},
    "ka_lot_punya": {"id": "Lot yang sudah dimiliki", "en": "Lots already held", "ms": "Lot yang sudah dimiliki", "zh": "已持有手数", "es": "Lotes ya en cartera", "pt": "Lotes já detidos"},
    "ka_harga_lama": {"id": "Harga beli rata-rata sekarang", "en": "Current average buy price", "ms": "Harga belian purata semasa", "zh": "当前平均买入价", "es": "Precio medio de compra actual", "pt": "Preço médio de compra atual"},
    "ka_lot_baru": {"id": "Lot yang akan dibeli", "en": "Lots to buy", "ms": "Lot yang akan dibeli", "zh": "计划买入手数", "es": "Lotes a comprar", "pt": "Lotes a comprar"},
    "ka_harga_baru": {"id": "Harga beli baru", "en": "New buy price", "ms": "Harga belian baharu", "zh": "新买入价", "es": "Nuevo precio de compra", "pt": "Novo preço de compra"},
    "ka_harga_pasar": {"id": "Harga pasar sekarang", "en": "Current market price", "ms": "Harga pasaran semasa", "zh": "当前市价", "es": "Precio de mercado actual", "pt": "Preço de mercado atual"},
    "ka_isi_lot": {"id": "Isi jumlah lot.", "en": "Enter the number of lots.", "ms": "Isi bilangan lot.", "zh": "请填写手数。", "es": "Introduce el número de lotes.", "pt": "Informe o número de lotes."},
    "ka_rata_baru": {"id": "HARGA RATA-RATA BARU", "en": "NEW AVERAGE PRICE", "ms": "HARGA PURATA BAHARU", "zh": "新的平均成本", "es": "NUEVO PRECIO MEDIO", "pt": "NOVO PREÇO MÉDIO"},
    "ka_lr_kini": {"id": "LABA / RUGI SEKARANG", "en": "CURRENT P&L", "ms": "UNTUNG / RUGI SEMASA", "zh": "当前盈亏", "es": "P&G ACTUAL", "pt": "RESULTADO ATUAL"},
    "ka_sebelum": {"id": "SEBELUM MENAMBAH", "en": "BEFORE ADDING", "ms": "SEBELUM MENAMBAH", "zh": "加仓之前", "es": "ANTES DE AÑADIR", "pt": "ANTES DE AUMENTAR"},
    "ka_impas_perlu": {"id": "Harga perlu kembali ke <b>{h}</b> agar Anda impas — {p:+.1f}% dari harga sekarang.", "en": "Price must return to <b>{h}</b> for you to break even — {p:+.1f}% from here.", "ms": "Harga perlu kembali ke <b>{h}</b> untuk anda pulang modal — {p:+.1f}% daripada harga semasa.", "zh": "价格需回到 <b>{h}</b> 您才能保本——距现价 {p:+.1f}%。", "es": "El precio debe volver a <b>{h}</b> para que empates: {p:+.1f}% desde aquí.", "pt": "O preço precisa voltar a <b>{h}</b> para você empatar — {p:+.1f}% a partir daqui."},
    "ki_judul": {"id": "**Berapa harga jual agar saya benar-benar untung setelah biaya?**", "en": "**What sell price actually leaves me in profit after fees?**", "ms": "**Berapa harga jualan supaya saya benar-benar untung selepas kos?**", "zh": "**卖到多少价，扣除费用后才是真的赚钱？**", "es": "**¿A qué precio de venta gano de verdad tras comisiones?**", "pt": "**Que preço de venda realmente dá lucro depois das taxas?**"},
    "ki_jumlah_lot": {"id": "Jumlah lot", "en": "Number of lots", "ms": "Bilangan lot", "zh": "手数", "es": "Número de lotes", "pt": "Número de lotes"},
    "ki_biaya_beli": {"id": "Biaya beli (%)", "en": "Buy fee (%)", "ms": "Kos belian (%)", "zh": "买入费率 (%)", "es": "Comisión de compra (%)", "pt": "Taxa de compra (%)"},
    "ki_biaya_jual": {"id": "Biaya jual (%)", "en": "Sell fee (%)", "ms": "Kos jualan (%)", "zh": "卖出费率 (%)", "es": "Comisión de venta (%)", "pt": "Taxa de venda (%)"},
    "ki_biaya_jual_ket": {"id": "Biasanya sudah termasuk pajak penjualan.", "en": "Usually already includes sales tax.", "ms": "Biasanya sudah termasuk cukai jualan.", "zh": "通常已包含卖出税费。", "es": "Normalmente ya incluye el impuesto de venta.", "pt": "Geralmente já inclui o imposto de venda."},
    "ki_target": {"id": "Target untung bersih (%)", "en": "Target net profit (%)", "ms": "Sasaran untung bersih (%)", "zh": "目标净利润 (%)", "es": "Beneficio neto objetivo (%)", "pt": "Lucro líquido alvo (%)"},
    "ki_isi_dulu": {"id": "Isi harga beli dan jumlah lot.", "en": "Enter the buy price and number of lots.", "ms": "Isi harga belian dan bilangan lot.", "zh": "请填写买入价和手数。", "es": "Introduce el precio de compra y el número de lotes.", "pt": "Informe o preço de compra e o número de lotes."},
    "ki_modal_keluar": {"id": "MODAL KELUAR", "en": "CASH OUTLAY", "ms": "MODAL KELUAR", "zh": "实际支出", "es": "DESEMBOLSO", "pt": "DESEMBOLSO"},
    "ki_termasuk": {"id": "termasuk biaya", "en": "including fees of", "ms": "termasuk kos", "zh": "含费用", "es": "incluye comisiones de", "pt": "incluindo taxas de"},
    "ki_impas": {"id": "HARGA IMPAS", "en": "BREAK-EVEN PRICE", "ms": "HARGA PULANG MODAL", "zh": "保本价", "es": "PRECIO DE EQUILIBRIO", "pt": "PREÇO DE EQUILÍBRIO"},
    "ki_dari_beli": {"id": "dari harga beli", "en": "from the buy price", "ms": "daripada harga belian", "zh": "相对买入价", "es": "desde el precio de compra", "pt": "do preço de compra"},
    "ki_untuk_untung": {"id": "HARGA UNTUK UNTUNG", "en": "PRICE FOR PROFIT OF", "ms": "HARGA UNTUK UNTUNG", "zh": "目标利润对应价格", "es": "PRECIO PARA GANAR", "pt": "PREÇO PARA LUCRO DE"},
    "ki_untung_bersih": {"id": "UNTUNG BERSIH", "en": "NET PROFIT", "ms": "UNTUNG BERSIH", "zh": "净利润", "es": "BENEFICIO NETO", "pt": "LUCRO LÍQUIDO"},
    "ki_setelah_biaya": {"id": "setelah semua biaya", "en": "after all fees", "ms": "selepas semua kos", "zh": "扣除所有费用后", "es": "después de todas las comisiones", "pt": "depois de todas as taxas"},
    "kal_rasio_kalimat": {"id": "Rasio {r:.2f} : 1.", "en": "Ratio of {r:.2f} : 1.", "ms": "Nisbah {r:.2f} : 1.", "zh": "盈亏比 {r:.2f} : 1。", "es": "Relación {r:.2f} : 1.", "pt": "Relação {r:.2f} : 1."},
    "j_contoh_alasan": {"id": "Contoh: laba kuartal naik 18%, PER masih di bawah rata-rata sektor, dan harga baru memantul dari support 4.200.", "en": "Example: quarterly earnings up 18%, P/E still below the sector average, and price just bounced off support at 4,200.", "ms": "Contoh: keuntungan suku tahun naik 18%, P/E masih di bawah purata sektor, dan harga baru melantun dari sokongan 4,200.", "zh": "例如：季度利润增长 18%，市盈率仍低于行业平均，且价格刚从 4,200 的支撑位反弹。", "es": "Ejemplo: beneficio trimestral +18%, P/E aún por debajo de la media del sector, y el precio acaba de rebotar en el soporte de 4.200.", "pt": "Exemplo: lucro trimestral +18%, P/L ainda abaixo da média do setor, e o preço acabou de repicar no suporte de 4.200."},
}

PROSA = {
    "ikhtisar_52": {
        "en": """The marker shows where today's price sits between the lowest and highest point of the past year. Near the top usually means a sustained run; near the bottom means a sustained fall.<br><br>It is a description, not a verdict. Something at 95% may be expensive, or may simply be winning. Something at 5% may be a bargain, or may be falling for a reason that has not finished yet.""",
        "id": """Penanda itu menunjukkan di mana harga hari ini berdiri di antara titik terendah dan tertinggi setahun terakhir. Dekat puncak biasanya berarti kenaikan yang bertahan; dekat dasar berarti penurunan yang bertahan.<br><br>Ini keterangan, bukan penilaian. Yang berada di 95% bisa jadi mahal, bisa jadi sekadar sedang menang. Yang berada di 5% bisa jadi murah, bisa juga sedang jatuh karena sebab yang belum selesai.""",
        "ms": """Penanda itu menunjukkan di mana harga hari ini berdiri antara titik terendah dan tertinggi setahun lalu. Hampir puncak biasanya bermakna kenaikan yang berterusan; hampir dasar bermakna penurunan yang berterusan.<br><br>Ini keterangan, bukan penghakiman. Yang berada di 95% mungkin mahal, mungkin sekadar sedang menang. Yang berada di 5% mungkin murah, mungkin juga sedang jatuh kerana sebab yang belum selesai.""",
        "zh": """标记显示今日价格位于过去一年最低点与最高点之间的什么位置。靠近顶部通常意味着持续的上涨，靠近底部则意味着持续的下跌。<br><br>这是描述，不是判断。处在 95% 的可能很贵，也可能只是正在赢。处在 5% 的可能便宜，也可能正因某个尚未结束的原因而下跌。""",
        "es": """El marcador indica dónde se sitúa el precio de hoy entre el mínimo y el máximo del último año. Cerca del techo suele significar una subida sostenida; cerca del suelo, una caída sostenida.<br><br>Es una descripción, no un veredicto. Algo al 95% puede estar caro, o simplemente estar ganando. Algo al 5% puede ser una ganga, o estar cayendo por un motivo que aún no ha terminado.""",
        "pt": """O marcador mostra onde o preço de hoje está entre o ponto mais baixo e o mais alto do último ano. Perto do topo geralmente indica uma alta sustentada; perto do fundo, uma queda sustentada.<br><br>É uma descrição, não um veredicto. Algo em 95% pode estar caro, ou pode apenas estar vencendo. Algo em 5% pode ser uma pechincha, ou pode estar caindo por um motivo que ainda não se esgotou.""",
    },
    "ikhtisar_penutup": {
        "en": """<b>One caution about reading a page like this.</b> A single day tells you almost nothing. The one-day column is here because people look for it, not because it carries much information — most of it is noise that will be invisible again within a week.<br><br>The columns worth your attention are the longer ones. If the one-month, year-to-date, and one-year figures all point the same way, that is a trend. If they contradict each other, that is a turn in progress, and the shorter number is not automatically the truer one.""",
        "id": """<b>Satu peringatan dalam membaca halaman semacam ini.</b> Satu hari nyaris tidak mengabarkan apa-apa. Kolom satu hari ada di sini karena orang mencarinya, bukan karena ia banyak berisi — sebagian besarnya derau yang seminggu lagi sudah tak berbekas.<br><br>Yang pantas Anda perhatikan adalah kolom yang lebih panjang. Kalau angka sebulan, sejak awal tahun, dan setahun menunjuk ke arah yang sama, itu tren. Kalau ketiganya saling bertentangan, itu belokan yang sedang berlangsung — dan angka yang lebih pendek tidak otomatis lebih benar.""",
        "ms": """<b>Satu peringatan ketika membaca halaman seperti ini.</b> Satu hari hampir tidak memberitahu apa-apa. Lajur satu hari ada di sini kerana orang mencarinya, bukan kerana ia banyak berisi — kebanyakannya hingar yang seminggu lagi sudah tidak berbekas.<br><br>Yang wajar diberi perhatian ialah lajur yang lebih panjang. Jika angka sebulan, sejak awal tahun, dan setahun menuding arah yang sama, itu aliran. Jika ketiga-tiganya bercanggah, itu selekoh yang sedang berlaku — dan angka yang lebih pendek tidak automatik lebih benar.""",
        "zh": """<b>读这类页面时的一点提醒。</b>单独一天几乎说明不了什么。"1 日"这一列放在这里，是因为人们会找它，而不是因为它含有多少信息——其中大部分是噪音，一周后就看不见了。<br><br>值得留意的是更长的那几列。如果一个月、年初至今和一年的数字指向同一个方向，那是趋势。如果彼此矛盾，那是正在发生的转折——而更短的那个数字并不自动更接近真相。""",
        "es": """<b>Una advertencia al leer una página así.</b> Un solo día no dice casi nada. La columna de un día está aquí porque la gente la busca, no porque aporte mucha información: en su mayoría es ruido que dentro de una semana será invisible.<br><br>Las columnas que merecen tu atención son las largas. Si las cifras de un mes, del año en curso y de un año apuntan al mismo lado, eso es una tendencia. Si se contradicen, es un giro en marcha, y el número más corto no es automáticamente el más verdadero.""",
        "pt": """<b>Uma ressalva ao ler uma página assim.</b> Um único dia quase nada informa. A coluna de um dia está aqui porque as pessoas a procuram, não porque carregue muita informação — em boa parte é ruído que em uma semana já terá sumido.<br><br>As colunas que merecem sua atenção são as mais longas. Se os números de um mês, do ano corrente e de um ano apontam para o mesmo lado, isso é tendência. Se se contradizem, é uma virada em curso — e o número mais curto não é automaticamente o mais verdadeiro.""",
    },
    "emas_premi": {
        "en": """<b>The price above is not what you will pay.</b> It is the world market price for bulk gold traded between institutions. A shop selling you a one-gram piece has to cover fabrication, certification, distribution, and its own margin — so the retail price sits above it, typically somewhere between 5% and 15%. Smaller pieces carry a larger premium than big bars, because the fixed cost of making a piece is spread over less metal.<br><br>The same gap works against you on the way out: dealers buy back below the world price, not above it. Use the box below to see how wide your own dealer's spread really is.""",
        "id": """<b>Harga di atas bukan harga yang akan Anda bayar.</b> Itu harga pasar dunia untuk emas dalam jumlah besar yang diperdagangkan antarlembaga. Toko yang menjual kepingan satu gram harus menutup ongkos cetak, sertifikat, distribusi, dan marginnya sendiri — sehingga harga ecerannya berada di atas itu, biasanya antara 5% sampai 15%. Kepingan kecil bermargin lebih besar daripada batangan besar, karena ongkos tetap pembuatan satu keping dibagi ke lebih sedikit logam.<br><br>Selisih yang sama bekerja melawan Anda saat menjual: toko membeli kembali di bawah harga dunia, bukan di atasnya. Gunakan kotak di bawah untuk melihat seberapa lebar selisih toko Anda sendiri.""",
        "ms": """<b>Harga di atas bukan harga yang akan anda bayar.</b> Itu harga pasaran dunia untuk emas pukal yang didagangkan antara institusi. Kedai yang menjual kepingan satu gram perlu menampung kos penempaan, pensijilan, pengedaran, dan marginnya sendiri — jadi harga runcit berada di atasnya, lazimnya antara 5% hingga 15%. Kepingan kecil bermargin lebih besar daripada jongkong besar.<br><br>Jurang yang sama bertindak menentang anda ketika menjual: kedai membeli semula di bawah harga dunia. Gunakan kotak di bawah untuk melihat seberapa lebar jurang kedai anda sendiri.""",
        "zh": """<b>上面的价格不是你要付的价格。</b>那是机构之间大宗黄金交易的国际市场价。卖你一克金片的商家要覆盖加工、证书、流通和自身利润，所以零售价高于它，通常在 5% 到 15% 之间。小规格的溢价比大金条更高，因为制作一件的固定成本要摊到更少的金属上。<br><br>卖出时同样的差价会反过来对你不利：商家的回购价低于国际价，而非高于。用下面的输入框看看你所在商家的价差究竟有多宽。""",
        "es": """<b>El precio de arriba no es el que vas a pagar.</b> Es el precio mundial del oro al por mayor entre instituciones. Una tienda que te vende una pieza de un gramo debe cubrir fabricación, certificación, distribución y su propio margen, así que el precio minorista queda por encima, normalmente entre un 5% y un 15%. Las piezas pequeñas llevan más prima que los lingotes grandes.<br><br>La misma diferencia juega en tu contra al salir: los comercios recompran por debajo del precio mundial, no por encima. Usa la casilla de abajo para ver cuán amplio es el diferencial de tu tienda.""",
        "pt": """<b>O preço acima não é o que você vai pagar.</b> É o preço mundial do ouro em grandes volumes negociado entre instituições. Uma loja que lhe vende uma peça de um grama precisa cobrir cunhagem, certificação, distribuição e a própria margem — então o preço de varejo fica acima, normalmente entre 5% e 15%. Peças menores têm ágio maior que barras grandes.<br><br>A mesma diferença joga contra você na saída: as lojas recompram abaixo do preço mundial, não acima. Use o campo abaixo para ver o quão largo é o spread da sua loja.""",
    },
    "emas_selisih": {
        "en": """The two lines rarely move together, and the gap between them is the exchange rate. Gold can fall on the world market and still rise in your own currency, if your currency weakens faster than gold falls. For a saver, that is not a technicality — it is often most of the return.<br><br>Which also means the reverse is possible. A stronger currency can wipe out a gain in dollar terms before it ever reaches you.""",
        "id": """Dua garis itu jarang bergerak seiring, dan jarak di antaranya adalah kurs. Emas bisa turun di pasar dunia namun tetap naik dalam rupiah, kalau rupiah melemah lebih cepat daripada turunnya emas. Bagi penabung, ini bukan soal teknis — sering kali justru di situlah sebagian besar keuntungannya berasal.<br><br>Yang juga berarti kebalikannya mungkin terjadi. Rupiah yang menguat bisa menghapus kenaikan dalam dolar sebelum sempat sampai ke tangan Anda.""",
        "ms": """Dua garis itu jarang bergerak seiring, dan jurang antaranya ialah kadar tukaran. Emas boleh jatuh di pasaran dunia namun tetap naik dalam mata wang anda, jika mata wang itu melemah lebih pantas. Bagi penyimpan, ini bukan soal teknikal — selalunya di situlah sebahagian besar pulangan datang.<br><br>Yang juga bermakna sebaliknya boleh berlaku. Mata wang yang menguat boleh memadamkan keuntungan dalam dolar sebelum sempat sampai kepada anda.""",
        "zh": """两条线很少同步，二者之间的差距就是汇率。若本币贬值的速度快过金价下跌，黄金在国际市场上跌了，用本币计仍可能上涨。对储蓄者来说这不是技术细节——收益往往大部分来自这里。<br><br>反过来同样成立。本币走强可能在收益到手之前，就把美元计价的涨幅抵消掉。""",
        "es": """Las dos líneas rara vez se mueven juntas, y la distancia entre ellas es el tipo de cambio. El oro puede caer en el mercado mundial y aun así subir en tu moneda, si tu moneda se debilita más rápido de lo que cae el oro. Para quien ahorra eso no es un tecnicismo: suele ser la mayor parte del rendimiento.<br><br>Lo que también significa que puede ocurrir lo contrario. Una moneda más fuerte puede borrar una ganancia en dólares antes de que llegue a ti.""",
        "pt": """As duas linhas raramente andam juntas, e a distância entre elas é o câmbio. O ouro pode cair no mercado mundial e ainda assim subir na sua moeda, se ela se enfraquecer mais rápido do que o ouro cai. Para quem poupa, isso não é um detalhe técnico — costuma ser a maior parte do retorno.<br><br>O que também significa que o inverso é possível. Uma moeda mais forte pode apagar um ganho em dólares antes que ele chegue até você.""",
    },
    "zakat_dasar": {
        "en": """<b>How the calculation works.</b> Zakat on gold falls due when two conditions are met together: the holding reaches the threshold (<i>nisab</i>) of 85 grams, and it has been owned for a full lunar year (<i>haul</i>, about 354 days). The rate is 2.5% — a quarter of a tenth.<br><br>The 85-gram figure comes from 20 <i>dinar</i>, the classical measure. What counts is the amount held throughout the year, so a holding that dipped below the threshold mid-year is usually assessed on the lower figure, not the peak. Zakat is calculated on the metal itself, which is why the weight matters more than what you paid for it.""",
        "id": """<b>Cara hitungannya.</b> Zakat emas wajib ketika dua syarat terpenuhi bersamaan: simpanan mencapai batas (<i>nisab</i>) 85 gram, dan sudah dimiliki genap satu tahun hijriah (<i>haul</i>, sekitar 354 hari). Kadarnya 2,5% — seperempat dari sepersepuluh.<br><br>Angka 85 gram berasal dari 20 <i>dinar</i>, ukuran klasiknya. Yang dihitung adalah jumlah yang bertahan sepanjang tahun, sehingga simpanan yang sempat turun di bawah nisab di tengah tahun umumnya dinilai dari angka terendahnya, bukan yang tertinggi. Zakat dihitung atas logamnya sendiri — itu sebabnya beratnya lebih menentukan daripada berapa Anda dahulu membelinya.""",
        "ms": """<b>Cara pengiraannya.</b> Zakat emas wajib apabila dua syarat dipenuhi serentak: simpanan mencapai nisab 85 gram, dan sudah dimiliki genap setahun hijrah (<i>haul</i>, kira-kira 354 hari). Kadarnya 2.5%.<br><br>Angka 85 gram berasal daripada 20 <i>dinar</i>. Yang dikira ialah jumlah yang kekal sepanjang tahun, jadi simpanan yang sempat turun di bawah nisab pertengahan tahun lazimnya dinilai pada angka terendah. Zakat dikira atas logamnya sendiri — sebab itu beratnya lebih menentukan daripada harga belian dahulu.""",
        "zh": """<b>计算方式。</b>黄金天课在两个条件同时满足时才应缴：持有量达到起征点（<i>nisab</i>）85 克，且已持满一个太阴年（<i>haul</i>，约 354 天）。税率为 2.5%，即十分之一的四分之一。<br><br>85 克源自古典计量单位 20 <i>第纳尔</i>。计算依据是全年持续持有的数量，因此年中一度低于起征点的持有，通常按较低值而非峰值核算。天课是就金属本身计算的，所以重量比当初买入价更关键。""",
        "es": """<b>Cómo se calcula.</b> El zakat sobre el oro se debe cuando se cumplen dos condiciones a la vez: la tenencia alcanza el umbral (<i>nisab</i>) de 85 gramos y se ha poseído durante un año lunar completo (<i>haul</i>, unos 354 días). El tipo es del 2,5%.<br><br>La cifra de 85 gramos procede de 20 <i>dinares</i>, la medida clásica. Cuenta la cantidad mantenida durante todo el año, de modo que una tenencia que bajó del umbral a mitad de año suele valorarse por la cifra menor, no por el máximo. El zakat se calcula sobre el metal, por eso importa más el peso que lo que pagaste.""",
        "pt": """<b>Como o cálculo funciona.</b> O zakat sobre o ouro é devido quando duas condições se cumprem juntas: a posse atinge o limite (<i>nisab</i>) de 85 gramas e foi mantida por um ano lunar completo (<i>haul</i>, cerca de 354 dias). A alíquota é de 2,5%.<br><br>O número de 85 gramas vem de 20 <i>dinares</i>, a medida clássica. Conta a quantidade mantida ao longo do ano, de modo que uma posse que caiu abaixo do limite no meio do período costuma ser avaliada pelo valor menor, não pelo pico. O zakat incide sobre o metal, por isso o peso importa mais do que o preço pago.""",
    },
    "zakat_perak": {
        "en": """Classically the two thresholds were roughly equivalent: 20 dinar of gold and 200 dirham of silver bought similar things. They have long since drifted apart, because silver fell far behind gold in value. Today the silver threshold is a much smaller sum.<br><br>That difference matters when the question is cash savings rather than metal. Institutions that apply the silver threshold catch more people in the obligation, which some scholars prefer precisely because it directs more to those entitled to receive. Others hold to the gold threshold as the safer measure of genuine surplus wealth. Zakat bodies differ, and both positions have long-standing support.""",
        "id": """Secara klasik kedua nisab itu kurang lebih setara: 20 dinar emas dan 200 dirham perak membeli barang yang sebanding. Keduanya sudah lama berpisah jauh, karena nilai perak tertinggal amat jauh dari emas. Hari ini nisab perak jatuh pada angka yang jauh lebih kecil.<br><br>Perbedaan itu berarti ketika yang ditanyakan adalah simpanan uang, bukan logam. Lembaga yang memakai nisab perak menjaring lebih banyak orang ke dalam kewajiban — dan sebagian ulama justru memilihnya karena dengan begitu lebih banyak yang sampai kepada yang berhak. Sebagian lain berpegang pada nisab emas sebagai ukuran yang lebih hati-hati atas kelebihan harta yang sesungguhnya. Lembaga zakat berbeda-beda, dan kedua pendapat punya sandaran yang panjang.""",
        "ms": """Secara klasik kedua-dua nisab itu lebih kurang setara: 20 dinar emas dan 200 dirham perak membeli barang yang sebanding. Kini kedua-duanya sudah jauh berbeza kerana nilai perak jauh ketinggalan. Hari ini nisab perak jatuh pada jumlah yang jauh lebih kecil.<br><br>Perbezaan itu penting apabila yang dipersoalkan ialah simpanan wang, bukan logam. Institusi yang memakai nisab perak menjaring lebih ramai ke dalam kewajipan — sebahagian ulama memilihnya justeru kerana lebih banyak sampai kepada yang berhak. Sebahagian lain berpegang pada nisab emas sebagai ukuran yang lebih berhati-hati. Badan zakat berbeza-beza, dan kedua-dua pendirian mempunyai sandaran yang panjang.""",
        "zh": """在古典时期，两个起征点大致相当：20 第纳尔黄金与 200 迪拉姆白银的购买力接近。如今二者早已分道扬镳，因为白银的价值远远落后于黄金。今天白银起征点是一个小得多的数额。<br><br>当讨论的对象是现金储蓄而非金属时，这个差别就有分量了。采用白银起征点的机构会让更多人纳入义务范围——部分学者正因如此而倾向它，因为这样能有更多财富流向应受者。另一些学者坚持黄金起征点，认为它对"真正的盈余财富"衡量得更稳妥。各天课机构做法不一，两种立场都有长久的依据。""",
        "es": """Clásicamente los dos umbrales eran casi equivalentes: 20 dinares de oro y 200 dírhams de plata compraban cosas parecidas. Hace mucho que se separaron, porque la plata quedó muy por detrás del oro. Hoy el umbral de la plata es una suma bastante menor.<br><br>Esa diferencia importa cuando se trata de ahorros en efectivo y no de metal. Las instituciones que aplican el umbral de la plata incluyen a más personas en la obligación, y algunos estudiosos lo prefieren precisamente porque así llega más a quienes tienen derecho a recibir. Otros se atienen al umbral del oro como medida más prudente de riqueza realmente excedente. Los organismos difieren, y ambas posturas tienen respaldo antiguo.""",
        "pt": """Classicamente os dois limites eram quase equivalentes: 20 dinares de ouro e 200 dirhams de prata compravam coisas semelhantes. Há muito se afastaram, pois a prata ficou bem atrás do ouro. Hoje o limite da prata é uma quantia bem menor.<br><br>Essa diferença importa quando se trata de poupança em dinheiro, e não de metal. Instituições que adotam o limite da prata incluem mais pessoas na obrigação, e alguns estudiosos preferem isso justamente porque assim chega mais a quem tem direito de receber. Outros mantêm o limite do ouro como medida mais prudente de riqueza realmente excedente. Os órgãos divergem, e ambas as posições têm respaldo antigo.""",
    },
    "zakat_perhiasan": {
        "en": """This is one of the older disagreements in the subject, and it is not settled.<br><br><b>One position</b> — associated with the Hanafi school — holds that gold is gold whatever shape it takes, so jewellery is assessed like any other holding.<br><br><b>The other</b> — held by the majority of the Maliki, Shafi'i, and Hanbali schools — exempts jewellery that is genuinely worn and kept for use, on the reasoning that it functions as clothing rather than as stored wealth. That exemption is usually qualified: it applies to a reasonable amount for personal use, not to a collection held as an investment in disguise.<br><br>Both readings rest on evidence and long scholarly practice. This calculator does not choose between them — it simply counts whatever weight you enter. If jewellery makes up much of your holding, that is a question worth putting to someone qualified rather than to a spreadsheet.""",
        "id": """Ini termasuk perselisihan yang lama dalam bab ini, dan belum tuntas.<br><br><b>Satu pendapat</b> — dikaitkan dengan mazhab Hanafi — memandang emas tetaplah emas apa pun bentuknya, sehingga perhiasan dinilai seperti simpanan lainnya.<br><br><b>Pendapat lain</b> — dipegang jumhur dari mazhab Maliki, Syafi'i, dan Hanbali — mengecualikan perhiasan yang benar-benar dipakai dan disimpan untuk dipakai, dengan alasan fungsinya sebagai pakaian, bukan harta simpanan. Pengecualian itu biasanya bersyarat: berlaku untuk jumlah yang wajar bagi pemakaian pribadi, bukan untuk koleksi yang sebenarnya investasi berselubung.<br><br>Keduanya berpijak pada dalil dan praktik keilmuan yang panjang. Kalkulator ini tidak memilih di antara keduanya — ia sekadar menghitung berat yang Anda masukkan. Kalau perhiasan merupakan bagian besar dari simpanan Anda, itu pertanyaan yang lebih pantas diajukan kepada orang yang berkompeten, bukan kepada lembar hitung.""",
        "ms": """Ini antara perselisihan lama dalam bab ini, dan belum selesai.<br><br><b>Satu pendapat</b> — dikaitkan dengan mazhab Hanafi — memandang emas tetap emas apa pun bentuknya, jadi barang kemas dinilai seperti simpanan lain.<br><br><b>Pendapat lain</b> — dipegang jumhur mazhab Maliki, Syafi'i dan Hanbali — mengecualikan barang kemas yang benar-benar dipakai, dengan alasan fungsinya sebagai pakaian, bukan harta simpanan. Pengecualian itu lazimnya bersyarat: untuk jumlah yang munasabah bagi kegunaan peribadi, bukan koleksi yang sebenarnya pelaburan berselindung.<br><br>Kedua-duanya berpijak pada dalil dan amalan keilmuan yang panjang. Kalkulator ini tidak memilih antara keduanya. Jika barang kemas merupakan sebahagian besar simpanan anda, itu soalan yang lebih wajar diajukan kepada orang yang berkelayakan.""",
        "zh": """这是该议题中较古老的分歧之一，至今没有定论。<br><br><b>一种立场</b>——通常与哈乃斐学派相联系——认为黄金无论何种形态都是黄金，因此首饰与其他持有一样计入。<br><br><b>另一种立场</b>——马立克、沙斐仪与罕百里学派的多数意见——豁免真正日常佩戴、为使用而保存的首饰，理由是它的功能近于衣物而非储藏的财富。这一豁免通常附带条件：仅适用于个人使用的合理数量，而非以首饰之名行投资之实的收藏。<br><br>两种理解都有经证依据和长久的学术实践。本计算器不在二者之间做选择，只按你输入的重量计算。如果首饰占了你持有量的大部分，这个问题更适合请教有资格的人，而不是一张计算表。""",
        "es": """Es una de las discrepancias más antiguas del tema, y no está zanjada.<br><br><b>Una posición</b> —asociada a la escuela hanafí— sostiene que el oro es oro sea cual sea su forma, así que las joyas se computan como cualquier otra tenencia.<br><br><b>La otra</b> —mayoritaria en las escuelas malikí, shafi'í y hanbalí— exime las joyas que realmente se llevan y se guardan para usarse, razonando que funcionan como vestimenta y no como riqueza almacenada. Esa exención suele ir matizada: vale para una cantidad razonable de uso personal, no para una colección que en realidad es una inversión encubierta.<br><br>Ambas lecturas se apoyan en pruebas y en una larga práctica académica. Esta calculadora no elige entre ellas: solo cuenta el peso que introduzcas. Si las joyas son buena parte de tu tenencia, esa pregunta merece plantearse a alguien cualificado, no a una hoja de cálculo.""",
        "pt": """Esta é uma das divergências mais antigas do tema, e não está encerrada.<br><br><b>Uma posição</b> — associada à escola hanafita — sustenta que ouro é ouro em qualquer forma, de modo que joias entram como qualquer outra posse.<br><br><b>A outra</b> — majoritária nas escolas malikita, shafi'ita e hanbalita — isenta joias efetivamente usadas e guardadas para uso, sob o argumento de que funcionam como vestuário, não como riqueza armazenada. Essa isenção costuma vir qualificada: vale para uma quantidade razoável de uso pessoal, não para uma coleção que na prática é investimento disfarçado.<br><br>Ambas as leituras se apoiam em evidências e em longa prática acadêmica. Esta calculadora não escolhe entre elas — apenas conta o peso que você informar. Se joias representam boa parte da sua posse, essa pergunta merece ir a alguém qualificado, não a uma planilha.""",
    },
    "zakat_penutup": {
        "en": """<b>This is arithmetic, not a ruling.</b> The calculation follows the most widely used figures, but zakat has real questions attached to it that a number cannot settle: whether jewellery counts, which threshold applies to cash, how debts are treated, and what the correct date is for your own year. Those belong to a qualified scholar or an established zakat institution, not to an app.<br><br>Nothing you type here is sent anywhere or stored beyond this session, and this app does not collect or forward zakat.""",
        "id": """<b>Ini hitungan, bukan fatwa.</b> Perhitungannya mengikuti angka yang paling umum dipakai, tetapi zakat punya pertanyaan-pertanyaan sungguhan yang tidak bisa dijawab oleh sebuah angka: apakah perhiasan ikut dihitung, nisab mana yang berlaku untuk uang tunai, bagaimana utang diperlakukan, dan kapan tepatnya haul Anda jatuh tempo. Itu ranah orang yang berkompeten atau lembaga zakat resmi, bukan ranah aplikasi.<br><br>Apa pun yang Anda ketik di sini tidak dikirim ke mana-mana dan tidak disimpan melampaui sesi ini. Aplikasi ini juga tidak menerima atau menyalurkan zakat.""",
        "ms": """<b>Ini pengiraan, bukan fatwa.</b> Pengiraannya mengikut angka yang paling lazim digunakan, tetapi zakat mempunyai persoalan sebenar yang tidak dapat diselesaikan oleh satu angka: sama ada barang kemas dikira, nisab mana yang terpakai untuk wang tunai, bagaimana hutang dilayan, dan bila tepatnya haul anda. Itu bidang orang yang berkelayakan atau institusi zakat rasmi, bukan bidang aplikasi.<br><br>Apa jua yang anda taip di sini tidak dihantar ke mana-mana dan tidak disimpan melepasi sesi ini. Aplikasi ini juga tidak menerima atau menyalurkan zakat.""",
        "zh": """<b>这是算术，不是教法裁决。</b>计算采用最通行的数值，但天课牵涉的真实问题不是一个数字能解决的：首饰是否计入、现金适用哪个起征点、债务如何处理、你自己的年度截止在哪一天。这些属于有资格的学者或正规天课机构，而不属于一个应用程序。<br><br>你在此输入的任何内容都不会被发送到任何地方，也不会保存到本次会话之外。本应用也不代收或转交天课。""",
        "es": """<b>Esto es aritmética, no un dictamen.</b> El cálculo sigue las cifras de uso más extendido, pero el zakat lleva aparejadas preguntas reales que un número no resuelve: si las joyas cuentan, qué umbral se aplica al efectivo, cómo se tratan las deudas y cuál es la fecha correcta de tu propio año. Eso corresponde a alguien cualificado o a una institución de zakat establecida, no a una aplicación.<br><br>Nada de lo que escribas aquí se envía a ningún sitio ni se guarda más allá de esta sesión, y esta aplicación no recauda ni canaliza zakat.""",
        "pt": """<b>Isto é aritmética, não um parecer jurídico.</b> O cálculo segue os números de uso mais difundido, mas o zakat traz perguntas reais que um número não resolve: se joias contam, qual limite se aplica ao dinheiro, como as dívidas são tratadas e qual a data correta do seu próprio ano. Isso cabe a alguém qualificado ou a uma instituição de zakat estabelecida, não a um aplicativo.<br><br>Nada do que você digitar aqui é enviado a lugar algum nem guardado além desta sessão, e este aplicativo não arrecada nem repassa zakat.""",
    },
    "tabung_emas_catatan": {
        "en": """<b>What this simulation does and does not include.</b> It buys gold at the world price plus the premium you set, once at the start of each month, and values the result at the world price minus the buyback discount you set. Those two numbers matter more than most people expect: an 8% premium and a 5% discount together mean gold must rise about 14% before you break even.<br><br><b>Not included:</b> storage or safe-deposit costs, the risk of losing physical gold, and any tax that applies where you live. The deposit comparison ignores tax on interest too, so both sides are flattered equally.<br><br>And the obvious one: this is what <i>did</i> happen over the period you chose. A different decade produces a different answer, sometimes a very different one.""",
        "id": """<b>Apa yang dihitung dan apa yang tidak.</b> Simulasi ini membeli emas pada harga dunia ditambah premi yang Anda tetapkan, satu kali di awal tiap bulan, lalu menilainya pada harga dunia dikurangi potongan buyback yang Anda tetapkan. Kedua angka itu lebih menentukan daripada yang biasanya dikira orang: premi 8% dan potongan 5% bersama-sama berarti harga emas harus naik sekitar 14% dulu sebelum Anda sekadar impas.<br><br><b>Yang tidak dihitung:</b> biaya penyimpanan atau safe deposit box, risiko kehilangan emas fisik, dan pajak yang berlaku di tempat Anda. Pembanding deposito juga mengabaikan pajak bunga, jadi kedua sisi sama-sama diperbagus.<br><br>Dan yang paling jelas: ini yang <i>sudah</i> terjadi pada periode yang Anda pilih. Dekade yang berbeda memberi jawaban yang berbeda, kadang jauh berbeda.""",
        "ms": """<b>Apa yang dikira dan apa yang tidak.</b> Simulasi ini membeli emas pada harga dunia campur premium yang anda tetapkan, sekali pada awal setiap bulan, kemudian menilainya pada harga dunia tolak potongan buyback yang anda tetapkan. Kedua-dua angka itu lebih menentukan daripada yang disangka: premium 8% dan potongan 5% bersama bermakna harga emas perlu naik kira-kira 14% sebelum anda sekadar pulang modal.<br><br><b>Yang tidak dikira:</b> kos penyimpanan, risiko kehilangan emas fizikal, dan cukai yang terpakai di tempat anda. Pembanding deposit juga mengabaikan cukai faedah.<br><br>Dan yang paling jelas: ini yang <i>telah</i> berlaku pada tempoh yang anda pilih. Dekad berbeza memberi jawapan berbeza.""",
        "zh": """<b>这个模拟算了什么、没算什么。</b>它在每月初按国际价加上你设定的溢价买入黄金，最后按国际价减去你设定的回购折价来估值。这两个数字的分量超出多数人的预期：8% 的溢价加 5% 的折价，意味着金价要先涨约 14%，你才刚刚回本。<br><br><b>未计入：</b>保管或保险箱费用、实物黄金遗失的风险，以及你所在地适用的税费。定存对比同样忽略了利息税，所以两边被同等美化。<br><br>还有最明显的一点：这是你所选区间里<i>已经</i>发生的事。换一个十年，答案会不同，有时相差很远。""",
        "es": """<b>Qué incluye y qué no esta simulación.</b> Compra oro al precio mundial más la prima que fijes, una vez al inicio de cada mes, y valora el resultado al precio mundial menos el descuento de recompra que fijes. Esos dos números pesan más de lo que se suele creer: una prima del 8% y un descuento del 5% implican que el oro debe subir un 14% antes de que llegues a empatar.<br><br><b>No incluye:</b> costes de custodia o caja de seguridad, el riesgo de perder el oro físico, ni los impuestos de tu país. La comparación con el depósito también ignora el impuesto sobre intereses, así que ambos lados salen igual de favorecidos.<br><br>Y lo evidente: esto es lo que <i>ocurrió</i> en el periodo elegido. Otra década da otra respuesta, a veces muy distinta.""",
        "pt": """<b>O que esta simulação inclui e o que não inclui.</b> Ela compra ouro ao preço mundial mais o ágio que você definir, uma vez no início de cada mês, e avalia o resultado ao preço mundial menos o deságio de recompra que você definir. Esses dois números pesam mais do que se costuma imaginar: um ágio de 8% e um deságio de 5% significam que o ouro precisa subir cerca de 14% antes de você apenas empatar.<br><br><b>Não inclui:</b> custos de guarda ou cofre, o risco de perder o ouro físico, nem tributos do seu país. A comparação com o depósito também ignora imposto sobre juros, então os dois lados são igualmente favorecidos.<br><br>E o óbvio: isto é o que <i>aconteceu</i> no período escolhido. Outra década dá outra resposta, às vezes bem diferente.""",
    },
    "lindung_pembuka": {
        "en": """"Gold protects your purchasing power" is a claim, and claims can be checked. Below, gold, the exchange rate, and the local stock index all start at 100 on the same day, so what you see is how they moved relative to one another — not how big their prices are.<br><br>Watch how closely gold in local currency tracks the exchange-rate line. Much of what looks like a gold rally, seen from here, is a currency falling.""",
        "id": """"Emas melindungi daya beli" adalah sebuah klaim, dan klaim bisa diperiksa. Di bawah ini emas, kurs, dan indeks saham sama-sama dimulai dari 100 pada hari yang sama, sehingga yang Anda lihat adalah bagaimana ketiganya bergerak satu sama lain — bukan seberapa besar angka harganya.<br><br>Perhatikan seberapa dekat garis emas rupiah mengikuti garis kurs. Sebagian besar dari yang tampak seperti kenaikan emas, dilihat dari sini, sebenarnya adalah mata uang yang sedang jatuh.""",
        "ms": """"Emas melindungi kuasa beli" ialah satu dakwaan, dan dakwaan boleh diperiksa. Di bawah ini emas, kadar tukaran, dan indeks saham sama-sama bermula pada 100 pada hari yang sama, jadi yang anda lihat ialah bagaimana ketiga-tiganya bergerak antara satu sama lain.<br><br>Perhatikan betapa rapat garis emas mata wang tempatan mengikuti garis kadar tukaran. Sebahagian besar daripada apa yang kelihatan seperti kenaikan emas, dilihat dari sini, sebenarnya ialah mata wang yang sedang jatuh.""",
        "zh": """"黄金能保护购买力"是一个主张，而主张是可以检验的。下面把黄金、汇率和本地股指都以同一天为 100 起点，所以你看到的是三者的相对走势，而不是价格的绝对大小。<br><br>留意本币金价的曲线与汇率曲线贴合得有多紧。从这个角度看，很多看起来像黄金上涨的部分，其实是货币在下跌。""",
        "es": """"El oro protege tu poder adquisitivo" es una afirmación, y las afirmaciones se pueden comprobar. Abajo, el oro, el tipo de cambio y el índice bursátil local parten todos de 100 el mismo día, así que lo que ves es cómo se movieron unos respecto a otros, no cuán grandes son sus precios.<br><br>Fíjate en lo cerca que la línea del oro en moneda local sigue a la del tipo de cambio. Buena parte de lo que parece una subida del oro es, visto así, una moneda que cae.""",
        "pt": """"O ouro protege seu poder de compra" é uma afirmação, e afirmações podem ser verificadas. Abaixo, ouro, câmbio e o índice de ações local partem todos de 100 no mesmo dia, então o que você vê é como se moveram uns em relação aos outros — não o tamanho de seus preços.<br><br>Repare o quanto a linha do ouro em moeda local acompanha a linha do câmbio. Boa parte do que parece uma alta do ouro é, visto daqui, uma moeda caindo.""",
    },
    "lindung_penutup": {
        "en": """<b>Two honest cautions about reading this.</b> First, the period you selected shapes the answer. Gold looks like a superb hedge measured from a currency crisis and a poor one measured from a calm decade — and the start date is a choice you are making, not a fact you are discovering.<br><br>Second, the stock index here is price only. It excludes dividends, which over ten years is a large omission and understates the comparison against equities. Gold pays nothing, so it loses nothing to that adjustment; stocks do, so the line you see is lower than the real return an equity holder received.<br><br>What the chart supports is narrow and worth stating plainly: gold has tended to hold value against a weakening currency. Whether that makes it right for your own savings depends on things this page cannot see.""",
        "id": """<b>Dua peringatan jujur dalam membaca ini.</b> Pertama, periode yang Anda pilih membentuk jawabannya. Emas tampak sebagai pelindung yang hebat kalau diukur sejak krisis nilai tukar, dan tampak buruk kalau diukur sejak satu dekade yang tenang — dan tanggal mulai itu adalah pilihan yang Anda buat, bukan fakta yang Anda temukan.<br><br>Kedua, indeks saham di sini hanya harga. Dividen tidak ikut, dan pada rentang sepuluh tahun itu bukan kelalaian kecil: perbandingannya menjadi terlalu memihak emas. Emas tidak membagikan apa pun sehingga tidak kehilangan apa pun dari penyesuaian itu; saham membagikan, jadi garis yang Anda lihat lebih rendah daripada hasil yang sebenarnya diterima pemegang saham.<br><br>Yang benar-benar didukung grafik ini sempit, dan sebaiknya dikatakan apa adanya: emas cenderung menahan nilai terhadap mata uang yang melemah. Apakah itu membuatnya cocok untuk simpanan Anda sendiri bergantung pada hal-hal yang tidak bisa dilihat halaman ini.""",
        "ms": """<b>Dua peringatan jujur ketika membaca ini.</b> Pertama, tempoh yang anda pilih membentuk jawapannya. Emas kelihatan pelindung yang hebat jika diukur sejak krisis mata wang, dan kelihatan lemah jika diukur sejak sedekad yang tenang — dan tarikh mula itu pilihan anda, bukan fakta yang anda temui.<br><br>Kedua, indeks saham di sini hanya harga. Dividen tidak disertakan, dan pada jangka sepuluh tahun itu bukan kelalaian kecil: perbandingan menjadi terlalu memihak emas. Emas tidak mengagihkan apa-apa, saham mengagihkan — jadi garis yang anda lihat lebih rendah daripada pulangan sebenar pemegang saham.<br><br>Apa yang benar-benar disokong graf ini adalah sempit: emas cenderung menahan nilai terhadap mata wang yang melemah. Sama ada itu sesuai untuk simpanan anda bergantung pada perkara yang tidak dapat dilihat halaman ini.""",
        "zh": """<b>阅读时的两点诚实提醒。</b>第一，你选择的时间区间会塑造答案。从一次货币危机算起，黄金看起来是极好的对冲；从一个平静的十年算起，它看起来很平庸——而起始日期是你的选择，不是你发现的事实。<br><br>第二，这里的股指只是价格指数，不含股息。在十年尺度上这不是小遗漏：比较因此过分偏向黄金。黄金不分配任何东西，所以不受这项调整影响；股票会分配，所以你看到的线低于股东实际获得的回报。<br><br>这张图真正能支持的结论很窄，值得直说：面对走弱的货币，黄金倾向于保住价值。这是否适合你自己的储蓄，取决于这个页面看不到的东西。""",
        "es": """<b>Dos advertencias honestas al leer esto.</b> Primera, el periodo que elijas moldea la respuesta. El oro parece una cobertura excelente medido desde una crisis cambiaria y mediocre medido desde una década tranquila, y la fecha de inicio es una elección tuya, no un hecho que descubres.<br><br>Segunda, el índice bursátil aquí es solo precio. No incluye dividendos, y a diez años esa omisión no es menor: la comparación queda demasiado a favor del oro. El oro no reparte nada, así que no pierde nada con ese ajuste; las acciones sí, de modo que la línea que ves está por debajo del rendimiento real de un accionista.<br><br>Lo que el gráfico sí respalda es estrecho y conviene decirlo sin adornos: el oro ha tendido a conservar valor frente a una moneda que se debilita. Si eso lo hace adecuado para tus ahorros depende de cosas que esta página no puede ver.""",
        "pt": """<b>Duas ressalvas honestas ao ler isto.</b> Primeira, o período escolhido molda a resposta. O ouro parece uma proteção excelente medido a partir de uma crise cambial e medíocre medido a partir de uma década calma — e a data inicial é uma escolha sua, não um fato que você descobre.<br><br>Segunda, o índice de ações aqui é apenas preço. Não inclui dividendos, e em dez anos essa omissão não é pequena: a comparação fica favorável demais ao ouro. O ouro não distribui nada, então nada perde com esse ajuste; ações distribuem, de modo que a linha que você vê está abaixo do retorno real de um acionista.<br><br>O que o gráfico de fato sustenta é estreito e vale dizer sem rodeios: o ouro tende a preservar valor diante de uma moeda que enfraquece. Se isso o torna adequado para a sua poupança depende de coisas que esta página não consegue ver.""",
    },
    "forex_diabaikan": {
        "en": """<b>1. Overnight interest (swap).</b> A forex position carried past 5pm New York time is charged or credited interest every night, depending on the interest-rate gap between the two countries. On positions held for months, this can exceed the entire price gain.<br><b>2. Leverage.</b> This test assumes you use your own capital with no borrowing. Retail brokers commonly offer 1:100 to 1:500, which multiplies both gains and losses, and introduces margin-call risk that is not modelled here at all.<br><b>3. Daily data.</b> Most forex traders work in minutes or hours. Testing on daily bars answers a different question from the one you may be asking.""",
        "id": """<b>1. Bunga menginap (swap).</b> Posisi forex yang dibawa melewati pukul 5 sore waktu New York dikenai atau diberi bunga tiap malam, tergantung selisih suku bunga kedua negara. Pada posisi yang ditahan berbulan-bulan, angka ini bisa lebih besar daripada seluruh keuntungan harganya.<br><b>2. Daya ungkit (leverage).</b> Uji ini menganggap Anda memakai modal penuh tanpa pinjaman. Broker ritel umumnya menawarkan 1:100 sampai 1:500 — yang melipatgandakan hasil sekaligus kerugian, dan memunculkan risiko akun tersapu habis (margin call) yang tidak tergambar di sini sama sekali.<br><b>3. Data harian.</b> Kebanyakan pedagang forex bekerja di rentang menit atau jam. Menguji di data harian menjawab pertanyaan yang berbeda dari yang mungkin Anda maksud.""",
        "ms": """<b>1. Faedah semalaman (swap).</b> Posisi forex yang dibawa melepasi pukul 5 petang waktu New York dikenakan atau diberi faedah setiap malam, bergantung pada jurang kadar faedah kedua-dua negara. Pada posisi yang dipegang berbulan-bulan, jumlah ini boleh melebihi keseluruhan keuntungan harga.<br><b>2. Leveraj.</b> Ujian ini menganggap anda menggunakan modal sendiri tanpa pinjaman. Broker runcit lazimnya menawarkan 1:100 hingga 1:500, yang menggandakan untung sekali gus rugi, dan menimbulkan risiko margin call yang langsung tidak dimodelkan di sini.<br><b>3. Data harian.</b> Kebanyakan peniaga forex bekerja dalam jangka minit atau jam. Menguji pada data harian menjawab soalan yang berbeza.""",
        "zh": """<b>1. 隔夜利息（掉期）。</b>持仓跨过纽约时间下午 5 点的外汇仓位，每晚都会被收取或获得利息，取决于两国的利差。对于持有数月的仓位，这笔金额可能超过全部的价格收益。<br><b>2. 杠杆。</b>本测试假设您使用自有资金、不借贷。零售经纪商通常提供 1:100 至 1:500 的杠杆，它同时放大盈利和亏损，并带来爆仓风险——而这里完全没有建模。<br><b>3. 日线数据。</b>大多数外汇交易者在分钟或小时级别操作。用日线回测，回答的是一个与您真正想问的不同的问题。""",
        "es": """<b>1. Interés nocturno (swap).</b> Una posición de forex mantenida más allá de las 5pm de Nueva York paga o cobra interés cada noche, según la diferencia de tipos entre ambos países. En posiciones de meses, esto puede superar toda la ganancia de precio.<br><b>2. Apalancamiento.</b> Esta prueba asume capital propio sin préstamo. Los brókeres minoristas ofrecen habitualmente 1:100 a 1:500, lo que multiplica ganancias y pérdidas e introduce riesgo de margin call, que aquí no se modela en absoluto.<br><b>3. Datos diarios.</b> La mayoría de operadores de forex trabajan en minutos u horas. Probar en velas diarias responde a una pregunta distinta de la que quizá te haces.""",
        "pt": """<b>1. Juros de rolagem (swap).</b> Uma posição de forex carregada após as 17h de Nova York paga ou recebe juros toda noite, conforme a diferença de taxas entre os dois países. Em posições de meses, isso pode superar todo o ganho de preço.<br><b>2. Alavancagem.</b> Este teste assume capital próprio sem empréstimo. Corretoras de varejo costumam oferecer 1:100 a 1:500, o que multiplica ganhos e perdas e cria risco de margin call, que aqui não é modelado.<br><b>3. Dados diários.</b> A maioria dos operadores de forex trabalha em minutos ou horas. Testar em candles diários responde a uma pergunta diferente da sua.""",
    },
    "kal_posisi_catatan": {
        "en": """This calculation ignores transaction costs and assumes your stop loss actually executes at that price. When markets move violently or a stock is illiquid, the real exit price can be worse.""",
        "id": """Perhitungan ini mengabaikan biaya transaksi dan mengandaikan stop loss Anda benar-benar tereksekusi di harga itu. Saat pasar bergerak liar atau saham tidak likuid, harga jual sesungguhnya bisa lebih rendah.""",
        "ms": """Pengiraan ini mengabaikan kos transaksi dan menganggap stop loss anda benar-benar dilaksanakan pada harga itu. Ketika pasaran bergerak liar atau saham tidak cair, harga jualan sebenar boleh lebih rendah.""",
        "zh": """此计算未计入交易成本，并假设您的止损真的能在该价位成交。当行情剧烈波动或个股流动性差时，实际成交价可能更差。""",
        "es": """Este cálculo ignora los costes de transacción y supone que tu stop loss se ejecuta realmente a ese precio. Con mercados violentos o valores ilíquidos, el precio real de salida puede ser peor.""",
        "pt": """Este cálculo ignora custos de transação e assume que seu stop loss realmente executa naquele preço. Em mercados violentos ou ativos ilíquidos, o preço real de saída pode ser pior.""",
    },
    "kal_average_catatan": {
        "en": """<b>Before adding at a lower price,</b> ask one question: are you buying more because the business is still sound, or because you cannot bring yourself to admit a loss? Adding to a falling position enlarges a bet on a conviction that has so far been proven wrong. Sometimes that is right. Often it is not.""",
        "id": """<b>Sebelum menambah di harga lebih rendah,</b> tanyakan satu hal: apakah Anda membeli lagi karena perusahaannya masih baik, atau karena tidak sanggup mengakui kerugian? Menambah posisi pada saham yang jatuh memperbesar taruhan pada satu keyakinan yang sejauh ini terbukti keliru. Kadang itu tepat. Sering kali tidak.""",
        "ms": """<b>Sebelum menambah pada harga lebih rendah,</b> tanya satu perkara: adakah anda membeli lagi kerana syarikatnya masih baik, atau kerana tidak sanggup mengakui kerugian? Menambah posisi pada saham yang jatuh membesarkan pertaruhan pada satu keyakinan yang setakat ini terbukti silap. Kadangkala itu betul. Selalunya tidak.""",
        "zh": """<b>在更低价位加仓之前，</b>先问自己一个问题：你再买入，是因为这家公司依然优秀，还是因为你无法承认自己亏了？向下摊平，等于在一个至今被证明错误的判断上加大赌注。有时这是对的，但更多时候不是。""",
        "es": """<b>Antes de promediar a la baja,</b> hazte una pregunta: ¿compras más porque el negocio sigue siendo sólido, o porque no eres capaz de admitir una pérdida? Añadir a una posición que cae agranda una apuesta sobre una convicción que hasta ahora resultó equivocada. A veces es lo correcto. A menudo no.""",
        "pt": """<b>Antes de aumentar a posição num preço menor,</b> faça uma pergunta: você está comprando mais porque a empresa continua boa, ou porque não consegue admitir o prejuízo? Aumentar posição em ativo que cai amplia uma aposta numa convicção que até agora se mostrou errada. Às vezes é o certo. Muitas vezes não é.""",
    },
    "kal_impas_catatan": {
        "en": """Total round-trip costs come to about <b>{total}%</b>. That means price must rise by that much just to get back to zero. This is why frequent trading erodes capital: every round trip takes its cut, whether you were right or wrong.""",
        "id": """Biaya total pulang-pergi sekitar <b>{total}%</b>. Artinya harga harus naik sebanyak itu hanya untuk kembali ke titik nol. Inilah alasan trading terlalu sering menggerus modal: setiap putaran memungut ongkos, entah Anda benar atau salah.""",
        "ms": """Kos pulang-pergi berjumlah kira-kira <b>{total}%</b>. Bermakna harga mesti naik sebanyak itu hanya untuk kembali ke titik sifar. Inilah sebab berdagang terlalu kerap mengikis modal: setiap pusingan mengambil habuannya, sama ada anda betul atau silap.""",
        "zh": """一进一出的总成本约为 <b>{total}%</b>。也就是说，价格必须先上涨这么多，才刚刚回到不赚不亏。这正是频繁交易侵蚀本金的原因：每一个来回都要抽成，无论你判断对错。""",
        "es": """El coste total de ida y vuelta ronda el <b>{total}%</b>. Es decir, el precio debe subir eso solo para volver a cero. Por eso operar en exceso erosiona el capital: cada vuelta se lleva su parte, tuvieras razón o no.""",
        "pt": """O custo total de ida e volta fica em torno de <b>{total}%</b>. Ou seja, o preço precisa subir tudo isso só para voltar ao zero. É por isso que operar demais corrói o capital: cada rodada cobra sua parte, você estando certo ou errado.""",
    },
    "kal_forex_catatan": {
        "en": """<b>How these numbers are derived.</b> Pip value is born in the quote currency ({kutip}), then converted using the {kutip} rate. That conversion step is often skipped, and as a result the real risk can land far from what was assumed.<br><br>This calculation does <b>not</b> include spread, commission, or overnight swap. It also assumes your stop loss executes at that exact price — during major news, price can gap straight past it.<br><br><b class="turun">One thing worth knowing before you start.</b> Retail forex brokers in Europe, the UK, and Australia are legally required to publish what percentage of their clients lose money. The figures they publish themselves sit between 70% and 80%. The leverage that makes forex tempting is also the main reason that number is so high.""",
        "id": """<b>Cara angka ini dihitung.</b> Nilai satu pip lahir dalam mata uang kutipan ({kutip}), lalu ditukar memakai kurs {kutip}. Langkah penukaran ini sering dilewatkan orang, dan akibatnya risiko yang sesungguhnya bisa meleset jauh dari yang dikira.<br><br>Perhitungan ini <b>belum</b> memasukkan spread, komisi, dan bunga menginap. Perhitungan ini juga mengandaikan stop loss Anda benar-benar tereksekusi di harga itu — saat berita besar keluar, harga bisa melompat melewatinya.<br><br><b class="turun">Satu hal yang pantas diketahui sebelum mulai.</b> Broker forex ritel di Eropa, Inggris, dan Australia diwajibkan hukum mengumumkan berapa persen nasabahnya merugi. Angka yang mereka umumkan sendiri berkisar 70–80%. Daya ungkit yang membuat forex terasa menggoda adalah juga sebab utama angka itu setinggi itu.""",
        "ms": """<b>Cara angka ini dikira.</b> Nilai satu pip lahir dalam mata wang sebutan ({kutip}), kemudian ditukar menggunakan kadar {kutip}. Langkah penukaran ini sering dilepaskan orang, dan akibatnya risiko sebenar boleh tersasar jauh.<br><br>Pengiraan ini <b>belum</b> memasukkan spread, komisen dan faedah semalaman. Ia juga menganggap stop loss anda benar-benar dilaksanakan pada harga itu — ketika berita besar keluar, harga boleh melompat melepasinya.<br><br><b class="turun">Satu perkara yang wajar diketahui sebelum bermula.</b> Broker forex runcit di Eropah, UK dan Australia diwajibkan undang-undang mengumumkan berapa peratus pelanggan mereka rugi. Angka yang mereka umumkan sendiri berlegar antara 70% hingga 80%.""",
        "zh": """<b>这些数字是怎么算出来的。</b>每点价值最初以计价货币（{kutip}）计算，再按 {kutip} 汇率折算。这个折算步骤常被忽略，结果导致实际风险与设想相差甚远。<br><br>本计算<b>不</b>包含点差、佣金和隔夜利息。它同样假设您的止损恰好在该价位成交——重大消息发布时，价格可能直接跳空穿过。<br><br><b class="turun">开始之前值得知道的一件事。</b>欧洲、英国和澳大利亚的零售外汇经纪商依法必须公布其客户亏损的比例。他们自己公布的数字在 70% 到 80% 之间。让外汇显得诱人的杠杆，正是这个数字如此之高的主要原因。""",
        "es": """<b>Cómo se obtienen estos números.</b> El valor del pip nace en la divisa cotizada ({kutip}) y luego se convierte usando el tipo de {kutip}. Ese paso de conversión suele omitirse, y por eso el riesgo real puede quedar muy lejos de lo supuesto.<br><br>Este cálculo <b>no</b> incluye spread, comisión ni swap nocturno. También asume que tu stop loss se ejecuta exactamente a ese precio: con noticias importantes, el precio puede saltárselo por completo.<br><br><b class="turun">Algo que conviene saber antes de empezar.</b> Los brókeres minoristas de forex en Europa, Reino Unido y Australia están obligados por ley a publicar qué porcentaje de sus clientes pierde dinero. Las cifras que ellos mismos publican van del 70% al 80%. El apalancamiento que hace tentador el forex es también la razón principal de que ese número sea tan alto.""",
        "pt": """<b>Como estes números são obtidos.</b> O valor do pip nasce na moeda cotada ({kutip}) e depois é convertido pela taxa de {kutip}. Esse passo de conversão costuma ser pulado, e por isso o risco real pode ficar bem longe do imaginado.<br><br>Este cálculo <b>não</b> inclui spread, comissão nem swap noturno. Ele também assume que seu stop loss executa exatamente naquele preço — em notícias importantes, o preço pode saltar direto por cima dele.<br><br><b class="turun">Algo que vale saber antes de começar.</b> Corretoras de forex de varejo na Europa, Reino Unido e Austrália são obrigadas por lei a publicar qual percentual de seus clientes perde dinheiro. Os números que elas mesmas publicam ficam entre 70% e 80%. A alavancagem que torna o forex tentador é também a principal razão de esse número ser tão alto.""",
    },
    "jurnal_intro": {
        "en": """Recording <i>why</i> you bought is far more useful than recording the price. Price can be looked up any time; the reasoning evaporates within weeks — and with it, your ability to recognise a mistake you keep repeating.""",
        "id": """Mencatat <i>alasan</i> membeli jauh lebih berguna daripada mencatat harganya. Harga bisa dilihat kapan saja; alasan menguap dalam hitungan minggu — dan bersamanya, kemampuan Anda mengenali kesalahan yang berulang.""",
        "ms": """Mencatat <i>sebab</i> anda membeli jauh lebih berguna daripada mencatat harganya. Harga boleh dilihat bila-bila masa; sebabnya menguap dalam beberapa minggu — dan bersamanya, kemampuan anda mengenali kesilapan yang berulang.""",
        "zh": """记录你<i>为什么</i>买入，远比记录买入价有用。价格随时可以查到，而当时的理由几周内就会蒸发——随之消失的，还有你识别自己反复犯同一个错误的能力。""",
        "es": """Anotar <i>por qué</i> compraste es mucho más útil que anotar el precio. El precio se puede consultar cuando quieras; el razonamiento se evapora en semanas, y con él tu capacidad de reconocer el error que repites una y otra vez.""",
        "pt": """Registrar <i>por que</i> você comprou é muito mais útil do que registrar o preço. O preço pode ser consultado a qualquer momento; o raciocínio evapora em semanas — e com ele, sua capacidade de reconhecer o erro que você repete.""",
    },
    "jurnal_catatan": {
        "en": """Buy and sell pairs are matched first-in-first-out (FIFO), the same convention brokers use. The mood chart is often the most revealing: if the “Fear of missing out” bar sits far to the left, you have just found the largest leak in how you invest.""",
        "id": """Pasangan beli-jual dihitung dengan cara masuk-duluan-keluar-duluan (FIFO), sama seperti yang umum dipakai sekuritas. Grafik suasana hati sering paling membuka mata: kalau batang “Takut ketinggalan” jauh di sebelah kiri, Anda baru saja menemukan kebocoran terbesar dalam cara Anda berinvestasi.""",
        "ms": """Pasangan beli-jual dipadankan secara masuk-dahulu-keluar-dahulu (FIFO), sama seperti amalan broker. Carta suasana hati selalunya paling membuka mata: jika bar “Takut ketinggalan” jauh di sebelah kiri, anda baru sahaja menemui kebocoran terbesar dalam cara anda melabur.""",
        "zh": """买卖配对采用先进先出（FIFO），与券商的通行做法一致。情绪图往往最令人警醒：如果“怕错过”那一条明显偏左，你刚刚发现了自己投资方式中最大的漏洞。""",
        "es": """Las compras y ventas se emparejan por orden de entrada (FIFO), la misma convención que usan los brókeres. El gráfico por estado de ánimo suele ser el más revelador: si la barra de “miedo a quedarse fuera” está muy a la izquierda, acabas de encontrar la mayor fuga en tu forma de invertir.""",
        "pt": """Compras e vendas são pareadas por ordem de entrada (FIFO), a mesma convenção usada pelas corretoras. O gráfico por estado emocional costuma ser o mais revelador: se a barra de “medo de ficar de fora” estiver bem à esquerda, você acabou de encontrar o maior vazamento no seu jeito de investir.""",
    },
    "laporan_intro": {
        "en": """Print what the terminal holds into a clean document — useful for personal records, periodic reporting, or if you use this application on behalf of other people.""",
        "id": """Cetak isi terminal jadi dokumen rapi — berguna untuk arsip pribadi, laporan berkala, atau kalau Anda memakai aplikasi ini melayani orang lain.""",
        "ms": """Cetak kandungan terminal menjadi dokumen kemas — berguna untuk arkib peribadi, laporan berkala, atau jika anda menggunakan aplikasi ini untuk melayan orang lain.""",
        "zh": """把终端中的内容打印成整洁的文档——适合个人存档、定期汇报，或您用本应用为他人提供服务时使用。""",
        "es": """Imprime lo que hay en la terminal en un documento limpio: útil para archivo personal, informes periódicos o si usas esta aplicación al servicio de otras personas.""",
        "pt": """Imprima o conteúdo do terminal em um documento limpo — útil para arquivo pessoal, relatórios periódicos, ou se você usa este aplicativo atendendo outras pessoas.""",
    },
    "teknikal_penutup": {
        "en": """<b>How to treat this page.</b> Everything above describes what has <i>already</i> happened to price. It is not a forecast and not a recommendation. Not a single number here knows what tomorrow holds.<br><br>Technical analysis has limits worth stating plainly: the same pattern can be read differently by two people, indicators always lag price because they are computed from the past, and the more indicators you add the easier it becomes to find one that agrees with what you already wanted. Use this as one input among several, never the only one.<br><br>Support and resistance levels are drawn from swing highs and lows whose prices sit close together, within 0.6× ATR. The number in brackets counts how often price touched that level — the more touches, the more market participants are watching it.""",
        "id": """<b>Cara memperlakukan halaman ini.</b> Semua di atas adalah uraian tentang apa yang <i>sudah</i> terjadi pada harga, bukan ramalan dan bukan anjuran. Tidak ada satu pun angka di sini yang tahu apa yang akan terjadi besok.<br><br>Analisa teknikal punya keterbatasan yang jujur perlu disebut: pola yang sama bisa ditafsirkan berbeda oleh dua orang, indikator selalu tertinggal dari harga karena dihitung dari masa lalu, dan makin banyak indikator dipakai makin mudah menemukan yang kebetulan mendukung keinginan kita. Gunakan sebagai satu bahan pertimbangan, bukan satu-satunya.<br><br>Level sokongan dan penahan diambil dari puncak dan lembah yang harganya berdekatan, dengan toleransi 0,6 kali ATR. Angka dalam kurung menunjukkan berapa kali harga menyentuh level itu — makin sering, makin banyak pelaku pasar yang memperhatikannya.""",
        "ms": """<b>Cara memperlakukan halaman ini.</b> Semua di atas menerangkan apa yang <i>sudah</i> berlaku pada harga, bukan ramalan dan bukan nasihat. Tiada satu pun angka di sini tahu apa yang akan berlaku esok.<br><br>Analisis teknikal ada batasnya: corak yang sama boleh ditafsir berbeza oleh dua orang, penunjuk sentiasa ketinggalan daripada harga kerana dikira daripada masa lalu, dan makin banyak penunjuk digunakan makin mudah menemui yang kebetulan menyokong kehendak kita. Gunakan sebagai satu bahan pertimbangan sahaja.<br><br>Aras sokongan dan rintangan diambil daripada puncak dan lembah yang harganya berdekatan, dengan toleransi 0.6 kali ATR. Angka dalam kurungan menunjukkan berapa kali harga menyentuh aras itu.""",
        "zh": """<b>该如何看待这一页。</b>以上所有内容描述的都是价格<i>已经</i>发生的事，不是预测，也不是建议。这里没有任何一个数字知道明天会怎样。<br><br>技术分析有必须坦白说明的局限：同一个形态，两个人可以读出不同结论；指标永远滞后于价格，因为它们由过去的数据算出；而使用的指标越多，就越容易找到一个恰好支持你原本想法的。请把它当作众多参考之一，绝不要当作唯一依据。<br><br>支撑与阻力位取自价格相近的波段高低点，容差为 0.6 倍 ATR。括号中的数字表示价格触及该位置的次数——次数越多，说明关注它的市场参与者越多。""",
        "es": """<b>Cómo tomarse esta página.</b> Todo lo anterior describe lo que <i>ya</i> le ocurrió al precio. No es un pronóstico ni una recomendación. Ni un solo número de aquí sabe qué pasará mañana.<br><br>El análisis técnico tiene límites que conviene decir sin rodeos: el mismo patrón puede leerse distinto por dos personas, los indicadores siempre van por detrás del precio porque se calculan del pasado, y cuantos más indicadores añades, más fácil es encontrar uno que coincida con lo que ya querías creer. Úsalo como un insumo más, nunca como el único.<br><br>Los soportes y resistencias se trazan a partir de máximos y mínimos relativos con precios cercanos, dentro de 0,6× ATR. El número entre paréntesis cuenta cuántas veces el precio tocó ese nivel: cuantos más toques, más participantes lo están mirando.""",
        "pt": """<b>Como encarar esta página.</b> Tudo acima descreve o que <i>já</i> aconteceu com o preço. Não é previsão nem recomendação. Nenhum número aqui sabe o que vem amanhã.<br><br>A análise técnica tem limites que merecem ser ditos com clareza: o mesmo padrão pode ser lido de formas diferentes por duas pessoas, indicadores sempre ficam atrás do preço porque são calculados do passado, e quanto mais indicadores você adiciona, mais fácil é achar um que concorde com o que você já queria acreditar. Use como um insumo entre vários, nunca o único.<br><br>Suportes e resistências vêm de topos e fundos com preços próximos, dentro de 0,6× ATR. O número entre parênteses conta quantas vezes o preço tocou aquele nível — quanto mais toques, mais participantes o observam.""",
    },
    "backtest_jujur": {
        "en": """<b>How to read this honestly.</b><br>• Signals are shifted by one bar, so today's decision executes at tomorrow's price. Without that, the numbers would look far prettier — and be false.<br>• Transaction costs are charged on every entry and exit. Strategies that trade often usually lose precisely because of this.<br>• This tests one symbol over one window. Change the symbol, change the period, change the timeframe — if the result falls apart immediately, you found a coincidence, not a strategy.<br>• Annual return and Sharpe are derived from real calendar dates, not from bar counts, so they stay comparable across timeframes.<br>• The shorter the timeframe, the larger the role of costs. A strategy that looks profitable on daily bars is often eaten alive by spread on five-minute bars.<br>• Short-interval data from Yahoo Finance is incomplete and carries no bid-ask. For minute bars, treat results as rough.<br>• Dividends are excluded and delisted companies are absent from the data. Both make the past look better than it was.<br>• Maximum drawdown often matters more than the final figure. −40% means there was a stretch where your capital was down by nearly half. Ask yourself honestly whether you would have held on.""",
        "id": """<b>Cara membaca hasil ini dengan jujur.</b><br>• Sinyal sudah digeser satu batang, jadi keputusan hari ini dieksekusi di harga besok. Tanpa itu, angkanya akan terlihat jauh lebih indah — dan palsu.<br>• Biaya transaksi sudah dipungut tiap kali masuk dan keluar. Strategi yang sering berpindah posisi biasanya kalah justru karena ini.<br>• Uji ini memakai satu saham dan satu rentang waktu. Ganti simbolnya, ganti periodenya, ganti rentang waktunya — kalau hasilnya langsung berantakan, berarti Anda menemukan kebetulan, bukan strategi.<br>• Hasil per tahun dan rasio Sharpe dihitung dari rentang tanggal sungguhnya, bukan dari jumlah batang, sehingga tetap sebanding antar rentang waktu.<br>• Makin pendek rentang waktunya, makin besar peran biaya. Strategi yang terlihat menguntungkan di grafik harian sering habis dimakan spread di grafik lima menit.<br>• Data rentang pendek dari Yahoo Finance tidak selalu lengkap dan tidak memuat harga bid-ask. Untuk rentang menit, anggap hasilnya kasar.<br>• Dividen tidak dihitung, dan saham yang sudah delisting tidak ada di data. Keduanya membuat hasil masa lalu terlihat lebih baik dari kenyataan.<br>• Penurunan terdalam sering lebih penting daripada hasil akhir. Angka −40% berarti ada masa ketika modal Anda tinggal separuh lebih sedikit. Tanyakan jujur pada diri sendiri apakah Anda akan bertahan.""",
        "ms": """<b>Cara membaca keputusan ini dengan jujur.</b><br>• Isyarat sudah dianjak satu bar, jadi keputusan hari ini dilaksanakan pada harga esok. Tanpa itu, angkanya akan kelihatan jauh lebih cantik — dan palsu.<br>• Kos transaksi dikenakan setiap kali masuk dan keluar. Strategi yang kerap bertukar posisi selalunya kalah justeru kerana ini.<br>• Ujian ini memakai satu saham dan satu tempoh. Tukar simbolnya, tukar tempohnya — jika keputusan terus berantakan, anda menemui kebetulan, bukan strategi.<br>• Pulangan tahunan dan nisbah Sharpe dikira daripada tarikh sebenar, bukan bilangan bar.<br>• Makin pendek jangka masanya, makin besar peranan kos.<br>• Data selang pendek daripada Yahoo Finance tidak lengkap dan tiada harga bid-ask.<br>• Dividen tidak dikira, dan syarikat yang telah disenarai keluar tiada dalam data.<br>• Penurunan terbesar selalunya lebih penting daripada angka akhir. −40% bermakna ada masa modal anda tinggal separuh. Tanya diri sendiri dengan jujur sama ada anda akan bertahan.""",
        "zh": """<b>如何诚实地解读这些结果。</b><br>• 信号已整体后移一根K线，因此今天的决策按明天的价格成交。若不这样处理，数字会好看得多——但那是假的。<br>• 每次进出都计入交易成本。频繁换仓的策略，往往正是因此而亏损。<br>• 本次测试只用了一个标的、一个时间窗口。换个代码、换个周期、换个时间尺度——如果结果立刻崩塌，说明你找到的是巧合，不是策略。<br>• 年化收益和夏普比率按真实日历天数计算，而非K线根数，因此在不同周期之间仍可比较。<br>• 周期越短，成本的影响越大。在日线上看起来赚钱的策略，在五分钟图上常常被点差吃光。<br>• Yahoo Finance 的短周期数据并不完整，且不含买卖盘价。对于分钟级别，请把结果视为粗略估计。<br>• 未计入股息，数据中也不含已退市公司。两者都会让历史表现显得比实际更好。<br>• 最大回撤往往比最终收益更重要。−40% 意味着曾有一段时间，您的资金只剩下一半多一点。请诚实地问自己：那时您撑得住吗？""",
        "es": """<b>Cómo leer esto con honestidad.</b><br>• Las señales se desplazan una barra, así que la decisión de hoy se ejecuta al precio de mañana. Sin eso, los números se verían mucho más bonitos, y serían falsos.<br>• Se cobran costes en cada entrada y salida. Las estrategias que operan mucho suelen perder precisamente por esto.<br>• Esto prueba un símbolo en una ventana. Cambia el símbolo, el periodo, el marco temporal: si el resultado se desmorona al instante, encontraste una coincidencia, no una estrategia.<br>• La rentabilidad anual y el Sharpe se derivan de fechas reales, no del número de barras, así que siguen siendo comparables entre marcos.<br>• Cuanto más corto el marco, mayor el peso de los costes. Una estrategia rentable en diario suele devorarla el spread en cinco minutos.<br>• Los datos de intervalo corto de Yahoo Finance son incompletos y no traen bid-ask. En minutos, toma los resultados como aproximados.<br>• Se excluyen dividendos y no figuran las empresas deslistadas. Ambos embellecen el pasado.<br>• La caída máxima suele importar más que la cifra final. Un −40% significa que hubo un tramo en que tu capital estuvo casi a la mitad. Pregúntate con honestidad si habrías aguantado.""",
        "pt": """<b>Como ler isto com honestidade.</b><br>• Os sinais são deslocados uma barra, então a decisão de hoje é executada no preço de amanhã. Sem isso, os números pareceriam bem mais bonitos — e seriam falsos.<br>• Custos são cobrados em cada entrada e saída. Estratégias que giram muito costumam perder exatamente por isso.<br>• Isto testa um símbolo em uma janela. Troque o símbolo, o período, o tempo gráfico — se o resultado desabar na hora, você achou uma coincidência, não uma estratégia.<br>• Retorno anual e Sharpe vêm de datas reais, não da contagem de barras, então continuam comparáveis entre tempos gráficos.<br>• Quanto menor o tempo gráfico, maior o peso dos custos. Uma estratégia lucrativa no diário costuma ser devorada pelo spread no gráfico de cinco minutos.<br>• Dados de intervalo curto do Yahoo Finance são incompletos e não trazem bid-ask. Em minutos, trate os resultados como aproximados.<br>• Dividendos são excluídos e empresas deslistadas não estão nos dados. Ambos embelezam o passado.<br>• A queda máxima costuma importar mais que o número final. −40% significa que houve um trecho em que seu capital ficou quase pela metade. Pergunte-se com honestidade se teria aguentado.""",
    },
    "syariah_catatan": {
        "en": """<b>What has been computed:</b> business-activity screening (excluding banks and interest-based financial institutions, conventional insurance, tobacco, alcohol, gambling, and weapons), plus interest-bearing debt and cash ratios against market capitalisation.<br><br><b class="turun">What could NOT be computed here:</b> non-halal income as a share of total revenue, and accounts receivable against total assets. Neither figure is available from any free open data source, yet both are legitimate parts of a complete screen.<br><br>For that reason the results above are a <b>first-pass filter</b> to narrow your reading list — not a ruling on compliance. For Indonesian investors, the authoritative reference remains the <b>Daftar Efek Syariah (DES)</b> published twice yearly by the OJK, or the <b>ISSI</b> and <b>JII</b> indices. A stock may pass here yet be absent from DES, and the reverse is equally possible.""",
        "id": """<b class="turun">Yang sudah dihitung:</b> penapisan kegiatan usaha (mengeluarkan bank dan lembaga keuangan berbasis bunga, asuransi konvensional, rokok, minuman keras, perjudian, dan persenjataan), serta rasio utang berbunga dan kas terhadap kapitalisasi pasar.<br><br><b class="turun">Yang TIDAK bisa dihitung di sini:</b> pendapatan non-halal terhadap total pendapatan, dan piutang usaha terhadap total aset. Kedua angka ini tidak tersedia di sumber data terbuka mana pun secara cuma-cuma, padahal keduanya bagian sah dari penapisan yang utuh.<br><br>Karena itu hasil di atas adalah <b>penyaring awal</b> untuk mempersempit daftar bacaan Anda — bukan penetapan status halal. Rujukan yang sah bagi pemodal Indonesia tetap <b>Daftar Efek Syariah (DES)</b> yang diterbitkan OJK dua kali setahun, atau indeks <b>ISSI</b> dan <b>JII</b>. Sebuah saham bisa lolos di sini tetapi tidak ada di DES, dan sebaliknya.""",
        "ms": """<b>Yang sudah dikira:</b> penapisan kegiatan perniagaan (mengecualikan bank dan institusi kewangan berasaskan faedah, insurans konvensional, rokok, minuman keras, perjudian dan senjata), serta nisbah hutang berfaedah dan tunai terhadap permodalan pasaran.<br><br><b class="turun">Yang TIDAK dapat dikira di sini:</b> pendapatan tidak halal berbanding jumlah pendapatan, dan akaun belum terima berbanding jumlah aset. Kedua-dua angka ini tiada dalam mana-mana sumber data terbuka percuma, sedangkan kedua-duanya bahagian sah penapisan yang lengkap.<br><br>Oleh itu keputusan di atas ialah <b>penapis awal</b> untuk memendekkan senarai bacaan anda — bukan penetapan status patuh syariah. Rujukan sah bagi pelabur Malaysia ialah <b>Senarai Sekuriti Patuh Syariah</b> terbitan Majlis Penasihat Syariah SC, yang dikeluarkan dua kali setahun.""",
        "zh": """<b>已经计算的部分：</b>业务活动筛选（排除银行及基于利息的金融机构、传统保险、烟草、酒类、博彩与武器），以及有息负债与现金相对市值的比率。<br><br><b class="turun">在此无法计算的部分：</b>非合规收入占总收入的比重，以及应收账款占总资产的比重。这两项数据在任何免费开放数据源中都无法获得，而它们都是完整筛选中不可或缺的部分。<br><br>因此，以上结果只是用于缩小阅读范围的<b>初步筛选</b>，并非合规裁定。对印尼投资者而言，权威依据仍是 OJK 每年发布两次的 <b>Daftar Efek Syariah (DES)</b>，或 <b>ISSI</b> 与 <b>JII</b> 指数。一只股票可能在这里通过却不在 DES 名单中，反之亦然。""",
        "es": """<b>Lo que sí se ha calculado:</b> el filtro de actividad empresarial (excluyendo bancos e instituciones financieras basadas en interés, seguros convencionales, tabaco, alcohol, juego y armamento), más los ratios de deuda con interés y caja sobre capitalización.<br><br><b class="turun">Lo que NO se ha podido calcular aquí:</b> los ingresos no permitidos sobre los ingresos totales, y las cuentas por cobrar sobre el activo total. Ninguna de esas cifras está disponible en fuentes abiertas gratuitas, y ambas forman parte legítima de un filtro completo.<br><br>Por eso lo anterior es un <b>primer filtro</b> para acotar tu lista de lectura, no un dictamen de cumplimiento. La referencia autorizada sigue siendo la lista oficial del regulador correspondiente a tu mercado.""",
        "pt": """<b>O que foi calculado:</b> a triagem de atividade empresarial (excluindo bancos e instituições financeiras baseadas em juros, seguros convencionais, tabaco, álcool, jogos de azar e armamentos), além dos índices de dívida com juros e caixa sobre o valor de mercado.<br><br><b class="turun">O que NÃO foi possível calcular aqui:</b> receita não permitida sobre a receita total, e contas a receber sobre o ativo total. Nenhum desses números está disponível em fontes abertas gratuitas, embora ambos façam parte legítima de uma triagem completa.<br><br>Por isso o resultado acima é uma <b>triagem inicial</b> para reduzir sua lista de leitura — não um parecer de conformidade. A referência oficial continua sendo a lista publicada pelo regulador do seu mercado.""",
    },
    "screener_baca": {
        "en": """<b>Reading the numbers.</b> Low P/E and P/B can mean cheap, or can mean the market expects earnings to fall. High ROE is good, but check debt/equity — ROE can be inflated with borrowing. A large dividend yield deserves suspicion when the share price is falling, because the percentage rises simply as the denominator shrinks. Every figure here comes from reports already filed, not from forecasts.""",
        "id": """<b>Membaca angkanya.</b> PER dan PBV rendah bisa berarti murah, bisa juga berarti pasar sedang memperkirakan labanya akan turun. ROE tinggi bagus, tapi periksa DER — ROE bisa digelembungkan dengan utang. Dividen besar patut dicurigai kalau harga sahamnya sedang jatuh, karena persentasenya naik justru karena penyebutnya mengecil. Semua angka berasal dari laporan yang sudah lewat, bukan ramalan.""",
        "ms": """<b>Membaca angkanya.</b> P/E dan P/B rendah boleh bermakna murah, boleh juga bermakna pasaran menjangka keuntungannya akan jatuh. ROE tinggi itu baik, tetapi periksa nisbah hutang — ROE boleh digelembungkan dengan hutang. Dividen besar patut dicurigai apabila harga sahamnya sedang jatuh, kerana peratusannya naik hanya kerana penyebutnya mengecil. Semua angka datang daripada laporan yang sudah lepas, bukan ramalan.""",
        "zh": """<b>怎样读这些数字。</b>低市盈率和低市净率可能意味着便宜，也可能意味着市场正预期利润下滑。高净资产收益率是好事，但要看负债权益比——ROE 可以靠举债推高。当股价正在下跌时，高股息率值得怀疑，因为百分比上升往往只是因为分母变小了。这里所有数字都来自已经公布的报表，而非预测。""",
        "es": """<b>Cómo leer estas cifras.</b> Un P/E y un P/B bajos pueden significar barato, o que el mercado espera una caída de beneficios. Un ROE alto está bien, pero mira la deuda: el ROE se puede inflar con préstamos. Una rentabilidad por dividendo alta merece sospecha si la acción está cayendo, porque el porcentaje sube simplemente porque encoge el denominador. Todas las cifras vienen de informes ya publicados, no de pronósticos.""",
        "pt": """<b>Como ler estes números.</b> P/L e P/VP baixos podem significar barato, ou que o mercado espera queda nos lucros. ROE alto é bom, mas veja o endividamento — o ROE pode ser inflado com dívida. Dividend yield alto merece desconfiança quando a ação está caindo, porque o percentual sobe apenas porque o denominador encolhe. Todos os números vêm de relatórios já publicados, não de previsões.""",
    },
    "catatan_pembaruan": {
        "en": """**How updating works, in full.**

**What happens on its own:** each time the app opens, it fetches a small version file from
`{INANG}` — containing only a version number, date, change notes, and file fingerprints.
The result is cached for six hours, so it isn't fetched repeatedly. Because this is an
internet request, **GitHub can see your IP address**, exactly as it would when you visit
any website. The app sends none of your data — not your portfolio, not your watchlist, not
your journal. If you'd rather it didn't, switch it off using the toggle above.

**What waits for your consent:** downloading application code and replacing files. Both
happen only after you tick the confirmation box and press the button. Never automatically.

Every downloaded file is matched against its published **SHA-256 fingerprint**. If a single
bit is off, the update is cancelled. All files are downloaded and verified before any are
written, so the app is never left half-updated.

Only three files may ever be replaced. The `data/` folder — holding your watchlist,
portfolio, journal, and settings — is never touched by an update.

**What you deserve to know.** An update channel is also a way in. Whoever controls the
release account can send any code to every user. Fingerprints protect against tampering in
transit, but not against an account falling into someone else's hands. If you are the one
publishing this application, turn on two-factor authentication on your GitHub account —
that single step matters more than any other.""",
        "id": """**Cara pembaruan ini bekerja, selengkapnya.**

**Yang berjalan sendiri:** tiap kali aplikasi dibuka, ia mengambil satu berkas keterangan
versi dari `{INANG}` — isinya hanya nomor versi, tanggal, catatan perubahan, dan sidik
jari. Hasilnya disimpan enam jam, jadi tidak diambil berulang-ulang. Karena ini permintaan
lewat internet, **GitHub dapat melihat alamat IP Anda**, sebagaimana setiap kali Anda
membuka situs mana pun. Aplikasi ini tidak mengirimkan data Anda — tidak portofolio, tidak
watchlist, tidak jurnal. Kalau Anda tidak menghendakinya, matikan lewat saklar di atas.

**Yang menunggu persetujuan Anda:** pengunduhan kode aplikasi dan penggantian berkas.
Keduanya hanya terjadi setelah Anda mencentang persetujuan dan menekan tombol. Tidak
pernah otomatis.

Tiap berkas yang diunduh dicocokkan **sidik jari SHA-256**-nya dengan yang diumumkan.
Kalau meleset satu bit pun, pembaruan dibatalkan. Semua berkas diunduh dan diperiksa lebih
dulu sebelum ada satu pun yang ditulis, supaya aplikasi tidak pernah tertinggal dalam
keadaan setengah diperbarui.

Hanya tiga berkas yang boleh diganti. Folder `data/` — berisi watchlist, portofolio,
jurnal, dan pengaturan Anda — tidak pernah disentuh pembaruan.

**Yang jujur perlu Anda sadari.** Saluran pembaruan adalah juga jalan masuk. Siapa pun yang
menguasai akun rilis bisa mengirim kode apa pun ke seluruh pemakai. Sidik jari melindungi
dari penyusup di tengah jalan, tetapi tidak melindungi dari akun yang jatuh ke tangan lain.
Kalau Anda yang menerbitkan aplikasi ini, nyalakan autentikasi dua langkah di akun GitHub
Anda — itu satu langkah yang paling menentukan.""",
        "ms": """**Cara kemas kini ini berfungsi, selengkapnya.**

**Yang berjalan sendiri:** setiap kali aplikasi dibuka, ia mengambil satu fail keterangan
versi dari `{INANG}` — mengandungi nombor versi, tarikh, nota perubahan dan cap jari
sahaja. Hasilnya disimpan enam jam. Kerana ini permintaan internet, **GitHub dapat melihat
alamat IP anda**, sama seperti mana-mana laman web. Aplikasi ini tidak menghantar data
anda. Jika anda tidak mahu, matikan menggunakan suis di atas.

**Yang menunggu kebenaran anda:** memuat turun kod aplikasi dan menggantikan fail. Kedua-
duanya hanya berlaku selepas anda menandakan kotak persetujuan dan menekan butang.

Setiap fail yang dimuat turun dipadankan dengan **cap jari SHA-256** yang diumumkan. Jika
tersasar walau satu bit, kemas kini dibatalkan. Semua fail dimuat turun dan disahkan
sebelum satu pun ditulis.

Hanya tiga fail boleh diganti. Folder `data/` tidak pernah disentuh oleh kemas kini.

**Yang wajar anda ketahui.** Saluran kemas kini juga merupakan jalan masuk. Sesiapa yang
menguasai akaun keluaran boleh menghantar sebarang kod kepada semua pengguna. Cap jari
melindungi daripada gangguan di pertengahan jalan, tetapi bukan daripada akaun yang jatuh
ke tangan orang lain. Jika anda penerbit aplikasi ini, hidupkan pengesahan dua faktor pada
akaun GitHub anda.""",
        "zh": """**更新机制的完整说明。**

**自动进行的部分：** 每次打开应用时，它会从 `{INANG}` 获取一个小的版本文件，其中只包含版本号、日期、
更新说明和文件指纹。结果会缓存六小时，不会反复请求。由于这是一次网络请求，**GitHub 能够看到您的 IP
地址**，这与您访问任何网站时的情况相同。应用不会发送您的任何数据——不发送持仓、不发送自选、不发送交易
日志。如果您不希望如此，可用上方开关关闭。

**需要您同意的部分：** 下载应用代码和替换文件。两者都只在您勾选确认框并点击按钮之后才会发生，绝不会自动
执行。

每个下载的文件都会与公布的 **SHA-256 指纹**进行比对。哪怕相差一个比特，更新都会取消。所有文件都会先下载
并校验完毕，然后才开始写入，因此应用绝不会停留在"更新到一半"的状态。

只有三个文件可以被替换。存放您的自选、持仓、日志和设置的 `data/` 文件夹，更新过程永远不会触碰。

**您有权知道的事。** 更新通道同时也是一条入口。掌控发布账号的人，可以向所有用户推送任意代码。指纹能防止
传输途中被篡改，却防不住账号落入他人之手。如果您是本应用的发布者，请为您的 GitHub 账号开启双重验证——
这一步比其他任何措施都更关键。""",
        "es": """**Cómo funciona la actualización, en detalle.**

**Lo que ocurre solo:** cada vez que la aplicación se abre, descarga un pequeño archivo de
versión desde `{INANG}`, que contiene únicamente número de versión, fecha, notas de
cambios y huellas de archivo. El resultado se cachea seis horas. Al ser una petición por
internet, **GitHub puede ver tu dirección IP**, igual que al visitar cualquier web. La
aplicación no envía ninguno de tus datos: ni cartera, ni lista, ni diario. Si prefieres que
no lo haga, desactívalo con el interruptor de arriba.

**Lo que espera tu consentimiento:** descargar código y reemplazar archivos. Ambas cosas
ocurren solo después de que marques la casilla y pulses el botón. Nunca automáticamente.

Cada archivo descargado se coteja con su **huella SHA-256** publicada. Si falla un solo
bit, la actualización se cancela. Todos los archivos se descargan y verifican antes de
escribir ninguno, así la aplicación nunca queda a medio actualizar.

Solo tres archivos pueden reemplazarse. La carpeta `data/` — con tu lista, cartera, diario
y ajustes — nunca se toca.

**Lo que mereces saber.** Un canal de actualización es también una puerta de entrada. Quien
controle la cuenta de publicación puede enviar cualquier código a todos los usuarios. Las
huellas protegen contra manipulación en tránsito, pero no contra una cuenta en manos
ajenas. Si eres tú quien publica esta aplicación, activa la verificación en dos pasos en tu
cuenta de GitHub: ese único paso importa más que cualquier otro.""",
        "pt": """**Como a atualização funciona, em detalhe.**

**O que acontece sozinho:** sempre que o aplicativo abre, ele busca um pequeno arquivo de
versão em `{INANG}`, contendo apenas número de versão, data, notas de alteração e
impressões digitais dos arquivos. O resultado fica em cache por seis horas. Como é uma
requisição pela internet, **o GitHub consegue ver o seu endereço IP**, exatamente como ao
visitar qualquer site. O aplicativo não envia nenhum dado seu — nem carteira, nem lista,
nem diário. Se preferir que não faça isso, desligue no botão acima.

**O que espera o seu consentimento:** baixar o código e substituir arquivos. Ambos só
acontecem depois de você marcar a caixa de confirmação e clicar no botão. Nunca
automaticamente.

Cada arquivo baixado é conferido contra sua **impressão digital SHA-256** publicada. Se um
único bit divergir, a atualização é cancelada. Todos os arquivos são baixados e verificados
antes que qualquer um seja gravado.

Apenas três arquivos podem ser substituídos. A pasta `data/` — com sua lista, carteira,
diário e configurações — nunca é tocada.

**O que você merece saber.** Um canal de atualização também é uma porta de entrada. Quem
controla a conta de publicação pode enviar qualquer código a todos os usuários. As
impressões digitais protegem contra adulteração no caminho, mas não contra uma conta que
caia em mãos alheias. Se você é quem publica este aplicativo, ative a autenticação de dois
fatores na sua conta do GitHub — esse passo isolado importa mais que qualquer outro.""",
    },
    "tentang_aplikasi": {
        "en": """
**Terminal Investasi** is a stripped-down financial data terminal, built to run on your own
computer. No subscription, no credits, no account to register.

#### Where the data comes from

| What you see | Source | Cost |
|---|---|---|
| Stocks, crypto, indices, commodities, forex | Yahoo Finance | Free, no API key |
| Crypto market data | CoinGecko | Free |
| Fear & Greed Index | alternative.me | Free |
| Market news | RSS feeds | Free |
| Economic indicators | World Bank API | Free, no API key |
| Blockchain balances | Blockstream · Ethplorer · Solana RPC | Free |
| Your watchlist & portfolio | The `data/` folder on your computer | — |

#### What is deliberately absent

There are no buy or sell signals anywhere in this application. That is a decision, not an
omission. Automated signals encourage people to stop thinking, and that is usually where
money goes.

There is also no order routing to brokers, and no paid private data. The first is a
liability we chose not to carry; the second cannot be free.

#### Honest limitations

- Yahoo Finance prices are **delayed**, typically 15–20 minutes for equities. Enough for
  monitoring, not for fast trading.
- Yahoo Finance is an unofficial source. Its format changes occasionally and the app
  needs adjusting when it does.
- Intraday data is limited and carries no bid-ask, so short-timeframe backtests are
  approximate.
- Currencies are never converted. A portfolio mixing IDR and USD produces a meaningless
  total.
- Backtests exclude dividends and delisted companies — both flatter historical results.
- Forex backtests ignore overnight swap and leverage entirely.
- The Shariah screen is a first-pass filter, not a ruling. See the note on that page.
- World Bank data lags one to two years.
- **Nothing here is investment advice.**

#### Making it your own

The whole application lives in one file, `terminal_ringan.py`. Symbol lists, news sources,
economic indicators, colour palettes, and translations all sit in the **PENGATURAN DASAR**
section at the top. Edit there, save, and refresh your browser.
""",
        "id": """
**Terminal Investasi** adalah versi sederhana dari terminal data keuangan, dibuat untuk
dijalankan sendiri di komputer Anda. Tidak ada langganan, tidak ada kredit, tidak ada
akun yang perlu didaftarkan.

#### Dari mana datanya?

| Yang Anda lihat | Sumber | Biaya |
|---|---|---|
| Saham, kripto, indeks, komoditas, forex | Yahoo Finance | Gratis, tanpa API key |
| Data pasar kripto | CoinGecko | Gratis |
| Indeks Takut & Serakah | alternative.me | Gratis |
| Berita pasar | Umpan RSS | Gratis |
| Indikator ekonomi | API Bank Dunia | Gratis, tanpa API key |
| Saldo blockchain | Blockstream · Ethplorer · RPC Solana | Gratis |
| Watchlist & portofolio Anda | Folder `data/` di komputer Anda | — |

#### Apa yang sengaja tidak ada

Tidak ada satu pun sinyal beli atau jual di aplikasi ini. Itu keputusan, bukan kelalaian.
Sinyal otomatis membuat pemakai berhenti berpikir, dan di situlah uang biasanya hilang.

Tidak ada juga pengiriman order ke broker, dan tidak ada data privat berbayar. Yang
pertama adalah tanggung jawab yang sengaja tidak kami pikul; yang kedua memang tidak
mungkin gratis.

#### Batasan yang jujur

- Harga dari Yahoo Finance **tertunda**, biasanya 15 sampai 20 menit untuk saham.
  Cukup untuk memantau, tidak cukup untuk trading cepat.
- Yahoo Finance adalah sumber tak resmi. Sewaktu-waktu formatnya berubah dan aplikasi ini
  perlu disesuaikan.
- Data rentang pendek terbatas dan tanpa harga bid-ask, jadi backtest rentang menit
  sifatnya kasar.
- Mata uang tidak pernah dikonversi. Portofolio yang mencampur rupiah dan dolar
  menghasilkan total yang tidak bermakna.
- Backtest mengabaikan dividen dan emiten yang sudah delisting — keduanya membuat hasil
  masa lalu terlihat lebih baik dari kenyataan.
- Backtest forex sama sekali mengabaikan bunga menginap dan daya ungkit.
- Penapisan syariah adalah penyaring awal, bukan penetapan status halal. Lihat catatan
  di halaman itu.
- Data Bank Dunia tertinggal satu sampai dua tahun.
- **Tidak ada apa pun di sini yang merupakan nasihat investasi.**

#### Menyesuaikan sendiri

Seluruh aplikasi ada dalam satu berkas `terminal_ringan.py`. Daftar simbol, sumber berita,
indikator ekonomi, palet warna, dan terjemahan semuanya ada di bagian **PENGATURAN DASAR**
paling atas. Ubah di sana, simpan, lalu segarkan browser.
""",
        "ms": """
**Terminal Investasi** ialah versi mudah sebuah terminal data kewangan, dibina untuk
dijalankan sendiri pada komputer anda. Tiada langganan, tiada kredit, tiada akaun yang
perlu didaftarkan.

#### Dari mana datanya

| Yang anda lihat | Sumber | Kos |
|---|---|---|
| Saham, kripto, indeks, komoditi, forex | Yahoo Finance | Percuma, tanpa kunci API |
| Data pasaran kripto | CoinGecko | Percuma |
| Indeks Takut & Tamak | alternative.me | Percuma |
| Berita pasaran | Suapan RSS | Percuma |
| Penunjuk ekonomi | API Bank Dunia | Percuma, tanpa kunci API |
| Baki blockchain | Blockstream · Ethplorer · RPC Solana | Percuma |
| Senarai pantau & portfolio anda | Folder `data/` pada komputer anda | — |

#### Apa yang sengaja tiada

Tiada satu pun isyarat beli atau jual dalam aplikasi ini. Itu satu keputusan, bukan
kecuaian. Isyarat automatik membuatkan pengguna berhenti berfikir, dan di situlah wang
selalunya lesap.

Tiada juga penghantaran pesanan kepada broker, dan tiada data persendirian berbayar.

#### Batasan yang jujur

- Harga Yahoo Finance **tertangguh**, biasanya 15 hingga 20 minit bagi saham.
- Yahoo Finance ialah sumber tidak rasmi. Formatnya berubah sekali-sekala.
- Data intrahari terhad dan tiada harga bid-ask, jadi ujian balik jangka pendek adalah
  anggaran kasar.
- Mata wang tidak pernah ditukar. Portfolio yang mencampurkan mata wang berbeza
  menghasilkan jumlah yang tidak bermakna.
- Ujian balik mengabaikan dividen dan syarikat yang telah disenarai keluar.
- Ujian balik forex langsung mengabaikan faedah semalaman dan leveraj.
- Penapisan syariah ialah penapis awal, bukan penetapan hukum. Lihat nota di halaman itu.
- Data Bank Dunia ketinggalan satu hingga dua tahun.
- **Tiada apa-apa di sini merupakan nasihat pelaburan.**

#### Menyesuaikan sendiri

Seluruh aplikasi berada dalam satu fail `terminal_ringan.py`. Senarai simbol, sumber
berita, penunjuk ekonomi, palet warna dan terjemahan semuanya berada di bahagian
**PENGATURAN DASAR** di bahagian atas.
""",
        "zh": """
**Terminal Investasi**是一个精简的金融数据终端，专为在您自己的电脑上运行而设计。无需订阅、无需积分、无需注册账号。

#### 数据来自哪里

| 您看到的内容 | 数据源 | 费用 |
|---|---|---|
| 股票、加密货币、指数、商品、外汇 | Yahoo Finance | 免费，无需 API 密钥 |
| 加密市场数据 | CoinGecko | 免费 |
| 恐惧与贪婪指数 | alternative.me | 免费 |
| 市场新闻 | RSS 订阅源 | 免费 |
| 经济指标 | 世界银行 API | 免费，无需 API 密钥 |
| 区块链余额 | Blockstream · Ethplorer · Solana RPC | 免费 |
| 您的自选与持仓 | 电脑上的 `data/` 文件夹 | — |

#### 刻意不做的功能

本应用中没有任何买卖信号。这是一个决定，而非疏漏。自动信号会让人停止思考，而资金往往就是在那时消失的。

同样没有向券商下单的功能，也没有付费的私有数据。前者是我们选择不承担的责任，后者本就不可能免费。

#### 诚实的局限

- Yahoo Finance 的价格**有延迟**，股票通常延迟 15 至 20 分钟。足够用于监控，不足以用于快速交易。
- Yahoo Finance 并非官方数据源，其格式偶尔会变动，届时应用需要调整。
- 日内数据有限且不含买卖盘价，因此短周期回测只是近似结果。
- 货币从不换算。混合不同币种的投资组合，其合计数字没有意义。
- 回测不含股息，也不含已退市公司——两者都会美化历史表现。
- 外汇回测完全忽略隔夜利息与杠杆。
- 伊斯兰合规筛选只是初步过滤，并非教法裁定。请阅读该页面上的说明。
- 世界银行数据滞后一到两年。
- **本应用中的任何内容都不构成投资建议。**

#### 自行调整

整个应用只有一个文件 `terminal_ringan.py`。标的清单、新闻源、经济指标、配色方案和翻译，全部位于顶部的
**PENGATURAN DASAR** 区块。修改后保存，再刷新浏览器即可。
""",
        "es": """
**Terminal Investasi** es una terminal de datos financieros reducida a lo esencial, pensada
para ejecutarse en tu propio ordenador. Sin suscripción, sin créditos, sin cuenta que
registrar.

#### De dónde vienen los datos

| Lo que ves | Fuente | Coste |
|---|---|---|
| Acciones, cripto, índices, materias primas, divisas | Yahoo Finance | Gratis, sin clave API |
| Datos del mercado cripto | CoinGecko | Gratis |
| Índice de Miedo y Codicia | alternative.me | Gratis |
| Noticias de mercado | Fuentes RSS | Gratis |
| Indicadores económicos | API del Banco Mundial | Gratis, sin clave API |
| Saldos en blockchain | Blockstream · Ethplorer · RPC de Solana | Gratis |
| Tu lista y tu cartera | La carpeta `data/` de tu ordenador | — |

#### Lo que falta deliberadamente

En esta aplicación no hay ninguna señal de compra o venta. Es una decisión, no un olvido.
Las señales automáticas invitan a dejar de pensar, y ahí suele perderse el dinero.

Tampoco hay envío de órdenes a brókeres ni datos privados de pago. Lo primero es una
responsabilidad que preferimos no asumir; lo segundo no puede ser gratuito.

#### Limitaciones honestas

- Los precios de Yahoo Finance están **retrasados**, normalmente 15–20 minutos en renta
  variable. Suficiente para vigilar, no para operar rápido.
- Yahoo Finance es una fuente no oficial. Su formato cambia de vez en cuando.
- Los datos intradía son limitados y no incluyen bid-ask, así que los backtests de plazo
  corto son aproximados.
- Las divisas nunca se convierten. Una cartera que mezcla monedas produce un total sin
  sentido.
- Los backtests excluyen dividendos y empresas deslistadas: ambos embellecen el pasado.
- Los backtests de forex ignoran por completo el swap nocturno y el apalancamiento.
- El filtro conforme a la sharía es una primera criba, no un dictamen. Lee la nota en esa
  página.
- Los datos del Banco Mundial llevan uno o dos años de retraso.
- **Nada de esto es asesoramiento de inversión.**

#### Adaptarlo a tu gusto

Toda la aplicación vive en un solo archivo, `terminal_ringan.py`. Las listas de símbolos,
las fuentes de noticias, los indicadores económicos, la paleta de colores y las
traducciones están en la sección **PENGATURAN DASAR**, arriba del todo.
""",
        "pt": """
**Terminal Investasi** é um terminal de dados financeiros reduzido ao essencial, feito para
rodar no seu próprio computador. Sem assinatura, sem créditos, sem conta para cadastrar.

#### De onde vêm os dados

| O que você vê | Fonte | Custo |
|---|---|---|
| Ações, cripto, índices, commodities, câmbio | Yahoo Finance | Grátis, sem chave de API |
| Dados do mercado cripto | CoinGecko | Grátis |
| Índice de Medo e Ganância | alternative.me | Grátis |
| Notícias de mercado | Feeds RSS | Grátis |
| Indicadores econômicos | API do Banco Mundial | Grátis, sem chave de API |
| Saldos em blockchain | Blockstream · Ethplorer · RPC da Solana | Grátis |
| Sua lista e sua carteira | A pasta `data/` no seu computador | — |

#### O que falta de propósito

Não há nenhum sinal de compra ou venda neste aplicativo. É uma decisão, não um
esquecimento. Sinais automáticos fazem as pessoas pararem de pensar, e normalmente é aí
que o dinheiro se perde.

Também não há envio de ordens para corretoras nem dados privados pagos. O primeiro é uma
responsabilidade que escolhemos não carregar; o segundo não tem como ser gratuito.

#### Limitações honestas

- Os preços do Yahoo Finance são **atrasados**, geralmente 15 a 20 minutos para ações.
  Suficiente para acompanhar, não para operar rápido.
- O Yahoo Finance é uma fonte não oficial. O formato muda de tempos em tempos.
- Dados intradiários são limitados e não trazem bid-ask, então backtests de prazo curto
  são aproximados.
- Moedas nunca são convertidas. Uma carteira misturando moedas produz um total sem
  sentido.
- Backtests excluem dividendos e empresas deslistadas — ambos embelezam o passado.
- Backtests de forex ignoram completamente o swap noturno e a alavancagem.
- O filtro conforme a sharia é uma triagem inicial, não um parecer. Leia a nota naquela
  página.
- Os dados do Banco Mundial têm defasagem de um a dois anos.
- **Nada aqui é recomendação de investimento.**

#### Ajustando ao seu gosto

O aplicativo inteiro está em um único arquivo, `terminal_ringan.py`. Listas de símbolos,
fontes de notícias, indicadores econômicos, paleta de cores e traduções ficam na seção
**PENGATURAN DASAR**, logo no topo.
""",
    },
}


def prosa(kunci: str) -> str:
    """Ambil naskah panjang sesuai bahasa aktif, dengan rantai cadangan yang sama."""
    entri = PROSA.get(kunci, {})
    bahasa = st.session_state.get("bahasa", "en")
    for kode in CADANGAN_BAHASA.get(bahasa, (bahasa, "en", "id")):
        if entri.get(kode):
            return entri[kode]
    return next(iter(entri.values()), "")


KUNCI_MENU = {
    "Pasar": "m_pasar", "Grafik": "m_grafik", "Screener": "m_screener",
    "Fundamental": "m_fundamental", "Backtest": "m_backtest",
    "Kalkulator": "m_kalkulator", "Berita & Makro": "m_berita",
    "Portofolio": "m_portofolio", "Dompet Kripto": "m_dompet",
    "Peringatan": "m_peringatan", "Jurnal": "m_jurnal",
    "Laporan": "m_laporan", "Tentang": "m_tentang",
}


def t(kunci: str) -> str:
    """
    Ambil teks sesuai bahasa aktif.

    Tiap kunci berupa dict {kode_bahasa: teks}. Kalau bahasa yang diminta belum
    punya terjemahan, aplikasi menuruni daftar cadangan sampai menemukan yang
    ada — bukan menampilkan kunci mentah kepada pemakai.
    """
    entri = TEKS.get(kunci)
    if not entri:
        return kunci
    if isinstance(entri, (tuple, list)):          # bentuk lama (id, en)
        entri = {"id": entri[0], "en": entri[1] if len(entri) > 1 else entri[0]}
    bahasa = st.session_state.get("bahasa", "en")
    for kode in CADANGAN_BAHASA.get(bahasa, (bahasa, "en", "id")):
        nilai = entri.get(kode)
        if nilai:
            return nilai
    return next(iter(entri.values()), kunci)


def pal() -> dict:
    """Palet yang sedang aktif. Aman dipanggil sebelum tema tersimpan dibaca."""
    return PALET.get(st.session_state.get("tema", "gelap"), PALET["gelap"])


st.set_page_config(page_title="Terminal Investasi", page_icon="▚", layout="wide")

# Tema dibaca sebelum apa pun digambar, supaya tidak ada kedipan warna.
if "tema" not in st.session_state:
    tersimpan = muat_json_awal(BERKAS_PENGATURAN, {})
    st.session_state.tema = tersimpan.get("tema", "gelap")
    st.session_state.cek_otomatis = tersimpan.get("cek_otomatis", True)
    st.session_state.bahasa = tersimpan.get("bahasa", "en")

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
        "bahasa": st.session_state.get("bahasa", "en"),
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


def _seri_harian(df: pd.DataFrame) -> pd.Series:
    """Ambil harga penutupan sebagai seri harian tanpa zona waktu.

    Emas dan kurs diperdagangkan di bursa berbeda dengan zona waktu berbeda.
    Tanpa penyeragaman ini, penggabungan keduanya akan menghasilkan baris
    kosong di mana-mana.
    """
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    seri = df["Close"].astype(float).copy()
    idx = pd.to_datetime(seri.index)
    try:
        idx = idx.tz_localize(None)
    except TypeError:      # sudah tanpa zona waktu
        pass
    seri.index = idx.normalize()
    return seri[~seri.index.duplicated(keep="last")].dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def ambil_emas_riwayat(periode: str = "5y") -> pd.DataFrame:
    """Riwayat harga emas dalam rupiah per gram.

    Dua sumber digabung: harga dunia dalam dolar per troy ounce, dan kurs
    dolar terhadap rupiah. Keduanya bergerak sendiri-sendiri, dan justru di
    situ letak yang menarik — emas bisa turun di pasar dunia tetapi tetap
    naik dalam rupiah kalau rupiah melemah lebih cepat.
    """
    emas = _seri_harian(ambil_riwayat(SIMBOL_EMAS, periode, "1d"))
    kurs = _seri_harian(ambil_riwayat(SIMBOL_KURS, periode, "1d"))
    if emas.empty or kurs.empty:
        return pd.DataFrame()

    gabung = pd.concat([emas.rename("usd_ons"), kurs.rename("kurs")], axis=1)
    gabung = gabung.sort_index().ffill().dropna()
    if gabung.empty:
        return pd.DataFrame()

    gabung["usd_gram"] = gabung["usd_ons"] / GRAM_PER_OUNCE
    gabung["idr_gram"] = gabung["usd_gram"] * gabung["kurs"]
    return gabung


@st.cache_data(ttl=300, show_spinner=False)
def ambil_emas_kini() -> dict:
    """Harga emas terakhir dalam dolar per ounce dan rupiah per gram."""
    df = ambil_kutipan((SIMBOL_EMAS, SIMBOL_KURS, SIMBOL_PERAK))
    if df.empty:
        return {}

    def satu(simbol):
        baris = df[df["Simbol"] == simbol]
        return baris.iloc[0] if len(baris) else None

    emas, kurs, perak = satu(SIMBOL_EMAS), satu(SIMBOL_KURS), satu(SIMBOL_PERAK)
    if emas is None or kurs is None:
        return {}

    usd_ons = float(emas["Harga"])
    nilai_kurs = float(kurs["Harga"])
    usd_gram = usd_ons / GRAM_PER_OUNCE
    hasil = {
        "usd_ons": usd_ons,
        "usd_gram": usd_gram,
        "kurs": nilai_kurs,
        "idr_gram": usd_gram * nilai_kurs,
        "persen_emas": float(emas["Persen"]),
        "persen_kurs": float(kurs["Persen"]),
        "seri": emas.get("Seri"),
    }
    if perak is not None:
        hasil["perak_idr_gram"] = float(perak["Harga"]) / GRAM_PER_OUNCE * nilai_kurs
    return hasil


def _ubah_persen(seri: pd.Series, hari_lalu: int) -> float:
    """Perubahan harga terhadap sekian hari kalender ke belakang.

    Sengaja memakai hari kalender, bukan hitungan batang. Sebulan bagi orang
    berarti sebulan, dan jumlah hari bursa dalam sebulan tidak selalu sama.
    """
    if len(seri) < 2:
        return float("nan")
    batas = seri.index[-1] - pd.Timedelta(days=hari_lalu)
    lampau = seri[seri.index <= batas]
    if lampau.empty:
        return float("nan")
    awal = float(lampau.iloc[-1])
    return (float(seri.iloc[-1]) / awal - 1) * 100 if awal else float("nan")


@st.cache_data(ttl=900, show_spinner=False)
def ambil_ikhtisar(simbol: tuple) -> pd.DataFrame:
    """Pergerakan satu simbol dalam beberapa rentang waktu sekaligus.

    Satu unduhan untuk semua simbol, lalu semua rentang dihitung dari deret
    yang sama. Jauh lebih hemat daripada menanyakan tiap rentang satu per satu.
    """
    import yfinance as yf

    if not simbol:
        return pd.DataFrame()

    try:
        data = yf.download(
            list(simbol), period="2y", interval="1d",
            progress=False, group_by="ticker", auto_adjust=False, threads=True,
        )
    except Exception:
        return pd.DataFrame()

    if data is None or len(data) == 0:
        return pd.DataFrame()

    baris = []
    for sm in simbol:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if sm not in data.columns.get_level_values(0):
                    continue
                sub = data[sm]
            else:
                sub = data
            tutup = sub["Close"].dropna()
            if len(tutup) < 2:
                continue

            idx = pd.to_datetime(tutup.index)
            try:
                idx = idx.tz_localize(None)
            except TypeError:
                pass
            tutup.index = idx

            akhir = float(tutup.iloc[-1])
            setahun = tutup[tutup.index >= tutup.index[-1] - pd.Timedelta(days=365)]
            tinggi = float(setahun.max()) if len(setahun) else float("nan")
            rendah = float(setahun.min()) if len(setahun) else float("nan")

            # Sejak awal tahun: patokannya penutupan terakhir tahun sebelumnya.
            tahun_ini = tutup[tutup.index.year == tutup.index[-1].year]
            sebelumnya = tutup[tutup.index.year < tutup.index[-1].year]
            if len(sebelumnya):
                dasar = float(sebelumnya.iloc[-1])
            elif len(tahun_ini):
                dasar = float(tahun_ini.iloc[0])
            else:
                dasar = float("nan")
            ytd = (akhir / dasar - 1) * 100 if dasar and dasar == dasar else float("nan")

            baris.append({
                "Simbol": sm,
                "Harga": akhir,
                "1 hari": _ubah_persen(tutup, 1),
                "1 pekan": _ubah_persen(tutup, 7),
                "1 bulan": _ubah_persen(tutup, 30),
                "YTD": ytd,
                "1 tahun": _ubah_persen(tutup, 365),
                "Tertinggi 52": tinggi,
                "Terendah 52": rendah,
                "Posisi 52": ((akhir - rendah) / (tinggi - rendah) * 100
                              if tinggi > rendah else float("nan")),
                "Seri": [float(v) for v in tutup.tail(30).tolist()],
            })
        except Exception:
            continue

    return pd.DataFrame(baris)


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
        tkr = yf.Ticker(simbol)
        return {
            "laba_rugi": tkr.income_stmt,
            "neraca": tkr.balance_sheet,
            "arus_kas": tkr.cashflow,
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
        return {"galat": t("e_alamat_format")}

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
            for tk in (d.get("tokens") or [])[:40]:
                info = t.get("tokenInfo", {})
                try:
                    des = int(info.get("decimals") or 18)
                    jml = float(tk.get("rawBalance", 0)) / (10 ** des)
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
        return None, t("e_sidik_beda")
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
            return False, f'{t("e_berkas_dilarang")} {nama}'
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


def baris_rentang(ikh) -> str:
    """Baris kecil berisi perubahan sepekan, sebulan, dan setahun.

    Dikembalikan sebagai HTML kosong kalau datanya belum ada, supaya kartu
    tetap tampil rapi ketika riwayat gagal diambil.
    """
    if ikh is None:
        return ""
    bagian = []
    for kunci, label in (("1 pekan", t("ik_1p")), ("1 bulan", t("ik_1b")),
                         ("1 tahun", t("ik_1t"))):
        nilai = ikh.get(kunci)
        try:
            nilai = float(nilai)
        except (TypeError, ValueError):
            continue
        if nilai != nilai:      # NaN
            continue
        bagian.append(f'<span style="color:{warna_kelas(warna(nilai))};">'
                      f'{label} {nilai:+.1f}%</span>')
    if not bagian:
        return ""
    return (f'<div style="font-size:0.66rem;letter-spacing:0.02em;margin-top:0.2rem;">'
            f'{" &nbsp;·&nbsp; ".join(bagian)}</div>')


def kartu_pasar(nama: str, harga: str, selisih: str, persen: str,
                seri=None, catatan: str = "", ikh=None):
    """Kartu besar: nama, harga, perubahan, rentang waktu, dan garis tren."""
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
        f'{baris_rentang(ikh)}'
        f'{grafik_mungil(seri or [], kelas)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def petak_pasar(peta: dict, per_baris: int = 3, sufiks: str = ""):
    """Susun kartu pasar dalam petak rapi dari sekumpulan simbol."""
    df = ambil_kutipan(tuple(peta))
    if df.empty:
        st.warning(t("w_muat_ulang"))
        return

    # Rentang waktu yang lebih panjang. Kalau gagal diambil, kartu tetap
    # tampil — hanya tanpa baris tambahannya.
    rentang = ambil_ikhtisar(tuple(peta))
    peta_rentang = ({r["Simbol"]: r for _, r in rentang.iterrows()}
                    if not rentang.empty else {})

    isian = list(peta.items())
    for i in range(0, len(isian), per_baris):
        kolom = st.columns(per_baris)
        for k, (simbol, nama) in zip(kolom, isian[i:i + per_baris]):
            # Nilai peta boleh berupa kunci terjemahan (berawalan "mk_") atau
            # nama diri yang sama di semua bahasa, seperti "S&P 500".
            label = t(nama) if nama.startswith("mk_") else nama
            with k:
                baris = df[df["Simbol"] == simbol]
                if baris.empty:
                    kartu(label, "—", t("kr_tak_ada"))
                    continue
                r = baris.iloc[0]
                kartu_pasar(
                    label,
                    format_angka(r["Harga"]) + sufiks,
                    f'{r["Perubahan"]:+,.2f}',
                    f'{r["Persen"]:+.2f}%',
                    r.get("Seri"),
                    ikh=peta_rentang.get(simbol),
                )


def periksa_qris(d: dict):
    """Kembalikan (jalur, ada, pesan_kesalahan) untuk satu cara dukungan."""
    qris = BASE_DIR / d.get("berkas_qris", "")
    if not d.get("berkas_qris") or not qris.is_file():
        return qris, False, ""
    # Berkas ada belum tentu berkas gambar. Kalau isinya rusak atau salah
    # format, beri pesan ramah — jangan sampai seluruh halaman ikut mati.
    try:
        from PIL import Image
        with Image.open(qris) as gambar:
            gambar.verify()
    except Exception:
        return qris, False, t("qr_rusak")
    return qris, True, ""


def kartu_donasi(ringkas: bool = False):
    """Ajakan dukungan sukarela — menggantikan tombol Deploy bawaan Streamlit."""
    daftar = PROFIL["donasi"]
    en = st.session_state.get("bahasa", "en") == "en"

    if ringkas:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);'
            f'padding:0.6rem 0.7rem;margin-bottom:0;">'
            f'<div class="label">{t("dukung")}</div></div>',
            unsafe_allow_html=True,
        )
        for d in daftar:
            qris, ada, _ = periksa_qris(d)
            if ada:
                try:
                    st.image(str(qris), use_container_width=True)
                    st.markdown(
                        f'<div class="catatan" style="text-align:center;'
                        f'margin-top:-0.4rem;"><b>{d["layanan"]}</b> · '
                        f'{d["untuk"][1] if en else d["untuk"][0]}</div>',
                        unsafe_allow_html=True)
                except Exception:
                    pass
            else:
                st.markdown(
                    f'<div class="catatan" style="text-align:center;">'
                    f'<b>{d["layanan"]}</b> {d["nomor"]}</div>',
                    unsafe_allow_html=True)
        return

    st.markdown(
        f'<div class="kartu" style="border-left:2px solid var(--aksen);'
        f'padding:0.9rem 1.1rem;">'
        f'<div class="label">{t("dukung")}</div>'
        f'<div style="color:var(--teks2);font-size:0.8rem;line-height:1.7;'
        f'margin-top:0.35rem;">{t("dukung_teks")}</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    kolom = st.columns(len(daftar))
    for k, d in zip(kolom, daftar):
        with k:
            qris, ada, pesan = periksa_qris(d)
            st.markdown(
                f'<div style="text-align:center;">'
                f'<span style="color:var(--aksen);font-weight:700;font-size:1rem;'
                f'letter-spacing:0.06em;">{d["layanan"]}</span>'
                f'<span style="color:var(--teks3);font-size:0.72rem;"> · '
                f'{d["untuk"][1] if en else d["untuk"][0]}</span></div>',
                unsafe_allow_html=True,
            )
            if ada:
                try:
                    st.image(str(qris), use_container_width=True)
                    st.markdown(
                        f'<div class="catatan" style="text-align:center;'
                        f'margin-top:-0.5rem;">'
                        f'{d["keterangan_qris"][1] if en else d["keterangan_qris"][0]}'
                        f'</div>',
                        unsafe_allow_html=True)
                except Exception:
                    st.markdown(f'<div class="catatan">{t("qr_gagal")}</div>',
                                unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="kartu" style="text-align:center;">'
                    f'<div style="color:var(--aksen);font-size:1.15rem;'
                    f'font-weight:700;">{d["nomor"]}</div>'
                    f'<div style="color:var(--teks3);font-size:0.72rem;">'
                    f'a.n. {d["atas_nama"]}</div></div>',
                    unsafe_allow_html=True)
                st.code(d["nomor_salin"], language=None)
                if pesan:
                    st.markdown(f'<div class="catatan">{pesan}</div>',
                                unsafe_allow_html=True)


def kop_halaman():
    jam = datetime.now().strftime("%d %b %Y  %H:%M")
    st.markdown(
        f'<div class="kop">'
        f'<span class="merek">{t("merek")}</span>'
        f'<span class="hidup">{t("data_terbuka")}</span>'
        f'<span>{t("tanpa_kredit")}</span>'
        f'<span>{jam}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 1 — PASAR
# ──────────────────────────────────────────────────────────────────────

def bagian_ikhtisar():
    """Satu layar untuk menjawab: pasar sedang bergerak ke mana."""
    ikh = ambil_ikhtisar(tuple(IKHTISAR_PANTAU))
    if ikh.empty:
        st.warning(t("w_muat_ulang"))
        return

    ikh = ikh.copy()
    ikh["Nama"] = ikh["Simbol"].map(
        lambda x: t(IKHTISAR_PANTAU[x]) if IKHTISAR_PANTAU.get(x, "").startswith("mk_")
        else IKHTISAR_PANTAU.get(x, x))

    # ── Ringkasan naratif ─────────────────────────────────────────────
    harian = ikh.dropna(subset=["1 hari"])
    if len(harian):
        naik = int((harian["1 hari"] > 0).sum())
        turun = int((harian["1 hari"] < 0).sum())
        pimpin = harian.loc[harian["1 hari"].idxmax()]
        tinggal = harian.loc[harian["1 hari"].idxmin()]

        # Searah atau berpencar: kalau hampir semuanya bergerak ke arah yang
        # sama, itu kabar tentang pasar; kalau berpencar, itu kabar tentang
        # masing-masing aset.
        bagian_naik = naik / len(harian)
        if bagian_naik >= 0.8:
            nada = t("ik_serempak_naik")
        elif bagian_naik <= 0.2:
            nada = t("ik_serempak_turun")
        else:
            nada = t("ik_berpencar")

        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
            f'<div class="label">{t("ik_ringkas")}</div>'
            f'<div style="color:var(--teks);font-size:0.86rem;line-height:1.7;'
            f'margin-top:0.4rem;">'
            f'<span class="naik">{naik} {t("ik_menguat")}</span>, '
            f'<span class="turun">{turun} {t("ik_melemah")}</span> '
            f'{t("ik_dari_total")} {len(harian)}. {nada}<br>'
            f'{t("ik_dipimpin")} <b>{pimpin["Nama"]}</b> '
            f'<span class="{warna(pimpin["1 hari"])}">({pimpin["1 hari"]:+.2f}%)</span>, '
            f'{t("ik_tertinggal")} <b>{tinggal["Nama"]}</b> '
            f'<span class="{warna(tinggal["1 hari"])}">({tinggal["1 hari"]:+.2f}%)</span>.'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # ── Tabel lintas aset ─────────────────────────────────────────────
    st.markdown(f'**{t("ik_tabel")}**')
    persen = lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
    st.dataframe(pd.DataFrame({
        t("k_nama"): ikh["Nama"],
        t("k_harga"): ikh["Harga"].map(lambda x: format_angka(x, 2)),
        t("ik_1h"): ikh["1 hari"].map(persen),
        t("ik_1p"): ikh["1 pekan"].map(persen),
        t("ik_1b"): ikh["1 bulan"].map(persen),
        t("ik_ytd"): ikh["YTD"].map(persen),
        t("ik_1t"): ikh["1 tahun"].map(persen),
        t("ik_posisi52"): ikh["Posisi 52"].map(
            lambda x: f"{x:.0f}%" if pd.notna(x) else "—"),
    }), use_container_width=True, hide_index=True)
    st.markdown(f'<div class="catatan">{t("c_ik_tabel")}</div>',
                unsafe_allow_html=True)

    st.divider()

    # ── Posisi dalam rentang 52 minggu ────────────────────────────────
    st.markdown(f'**{t("ik_judul52")}**')
    st.markdown(f'<div class="catatan">{prosa("ikhtisar_52")}</div>',
                unsafe_allow_html=True)
    st.write("")

    punya = ikh.dropna(subset=["Posisi 52"])
    for i in range(0, len(punya), 3):
        kolom = st.columns(3)
        for k, (_, r) in zip(kolom, punya.iloc[i:i + 3].iterrows()):
            pos = float(r["Posisi 52"])
            # Warna mengikuti posisi, bukan arah harian: dekat puncak kuning,
            # dekat dasar merah, di tengah netral.
            c = (pal()["naik"] if pos >= 80 else
                 pal()["turun"] if pos <= 20 else pal()["aksen"])
            with k:
                st.markdown(
                    f'<div class="kartu" style="padding:0.6rem 0.8rem;">'
                    f'<div class="label">{r["Nama"]}</div>'
                    f'<div style="position:relative;height:6px;background:var(--kisi);'
                    f'border-radius:3px;margin:0.55rem 0 0.35rem;">'
                    f'<div style="position:absolute;left:{max(0, min(100, pos)):.1f}%;'
                    f'top:-4px;width:3px;height:14px;background:{c};'
                    f'border-radius:1px;"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:0.68rem;color:var(--teks3);">'
                    f'<span>{format_angka(r["Terendah 52"], 0)}</span>'
                    f'<span style="color:{c};">{pos:.0f}%</span>'
                    f'<span>{format_angka(r["Tertinggi 52"], 0)}</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown(f'<div class="catatan">{prosa("ikhtisar_penutup")}</div>',
                unsafe_allow_html=True)


def bagian_emas():
    """Harga emas dunia diterjemahkan ke satuan yang dipakai orang: rupiah per gram."""
    st.subheader(t("j_emas"))

    e = ambil_emas_kini()
    if not e:
        st.warning(t("em_gagal"))
        return

    k = st.columns(4)
    with k[0]:
        kartu(t("em_harga_dunia"), f'${format_angka(e["usd_ons"], 2)}',
              f'{e["persen_emas"]:+.2f}% · {t("em_per_ons")}', warna(e["persen_emas"]))
    with k[1]:
        kartu(t("em_per_gram"), f'Rp {format_angka(e["idr_gram"], 0)}',
              t("em_24_karat"), warna(e["persen_emas"]))
    with k[2]:
        kartu(t("em_kurs"), format_angka(e["kurs"], 0),
              f'{e["persen_kurs"]:+.2f}% · USD/IDR', warna(e["persen_kurs"]))
    with k[3]:
        if e.get("perak_idr_gram"):
            nisbah = e["idr_gram"] / e["perak_idr_gram"]
            kartu(t("em_perak"), f'Rp {format_angka(e["perak_idr_gram"], 0)}',
                  f'{t("em_nisbah")} {nisbah:.0f} : 1')
        else:
            kartu(t("em_perak"), "—", t("kr_tak_ada"))

    st.markdown(f'<div class="catatan">{t("c_emas_sumber")}</div>',
                unsafe_allow_html=True)

    st.divider()

    # ── Nilai per satuan berat ────────────────────────────────────────
    st.markdown(f'**{t("em_tabel_berat")}**')
    st.dataframe(pd.DataFrame({
        t("em_berat"): [f"{b:g} g" for b in BERAT_LAZIM],
        t("em_nilai_dunia"): [f'Rp {format_angka(b * e["idr_gram"], 0)}' for b in BERAT_LAZIM],
        t("em_setara_usd"): [f'${format_angka(b * e["usd_gram"], 2)}' for b in BERAT_LAZIM],
    }), use_container_width=True, hide_index=True, height=350)

    st.markdown(f'<div class="catatan">{prosa("emas_premi")}</div>',
                unsafe_allow_html=True)

    # ── Pemeriksa premi ───────────────────────────────────────────────
    st.markdown(f'**{t("em_periksa_premi")}**')
    a, b = st.columns(2)
    with a:
        harga_toko = st.number_input(t("em_harga_toko"), min_value=0.0,
                                     value=float(round(e["idr_gram"] / 1000) * 1000),
                                     step=10_000.0, format="%.0f",
                                     help=t("em_harga_toko_bantuan"))
    with b:
        buyback = st.number_input(t("em_buyback"), min_value=0.0, value=0.0,
                                  step=10_000.0, format="%.0f",
                                  help=t("em_buyback_bantuan"))

    if harga_toko > 0:
        premi = (harga_toko - e["idr_gram"]) / e["idr_gram"] * 100
        kelas = "turun" if premi > 12 else ("diam" if premi > 4 else "naik")
        st.markdown(
            f'<div class="catatan"><b class="{kelas}">{premi:+.1f}%</b> '
            f'{t("em_premi_ket")} Rp {format_angka(e["idr_gram"], 0)}.</div>',
            unsafe_allow_html=True,
        )
    if harga_toko > 0 and buyback > 0:
        selisih = (harga_toko - buyback) / harga_toko * 100
        st.markdown(
            f'<div class="catatan"><b class="turun">{selisih:.1f}%</b> '
            f'{t("em_spread_ket")}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Grafik riwayat ────────────────────────────────────────────────
    a, b = st.columns([1, 3])
    with a:
        periode = st.selectbox(t("g_periode"), ["1y", "2y", "5y", "10y", "max"],
                               index=2, key="periode_emas")
    riwayat = ambil_emas_riwayat(periode)
    if riwayat.empty:
        st.info(t("w_tak_tersedia"))
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=riwayat.index, y=riwayat["idr_gram"],
                             name=t("em_garis_rupiah"),
                             line=dict(color=pal()["aksen"], width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=riwayat.index, y=riwayat["usd_gram"],
                             name=t("em_garis_dolar"),
                             line=dict(color=pal()["biru"], width=1.3, dash="dot")),
                  secondary_y=True)
    fig.update_layout(
        height=420, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
        title=dict(text=t("em_judul_grafik"), font=dict(size=13, color=pal()["aksen"]), x=0),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"], secondary_y=False)
    fig.update_yaxes(showgrid=False, secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    awal, akhir = riwayat["idr_gram"].iloc[0], riwayat["idr_gram"].iloc[-1]
    awal_usd, akhir_usd = riwayat["usd_gram"].iloc[0], riwayat["usd_gram"].iloc[-1]
    naik_idr = (akhir / awal - 1) * 100 if awal else float("nan")
    naik_usd = (akhir_usd / awal_usd - 1) * 100 if awal_usd else float("nan")
    tahun = max((riwayat.index[-1] - riwayat.index[0]).days / 365.25, 1e-9)
    st.markdown(
        f'<div class="catatan">{t("em_selama")} {tahun:.1f} {t("bt_tahun")}: '
        f'<b class="{warna(naik_idr)}">{naik_idr:+.1f}%</b> {t("em_dalam_rupiah")} '
        f'&nbsp;·&nbsp; <b class="{warna(naik_usd)}">{naik_usd:+.1f}%</b> '
        f'{t("em_dalam_dolar")}.<br><br>{prosa("emas_selisih")}</div>',
        unsafe_allow_html=True,
    )


def halaman_pasar():
    st.subheader(t("j_denyut"))

    t0, t1, t2, t5, t6, t3, t4 = st.tabs(
        [t("t_ikhtisar"), t("t_indeks"), t("t_kripto"), t("t_forex"),
         t("t_emas"), t("t_komoditas"), t("t_saham_id")])

    with t0:
        bagian_ikhtisar()

    with t1:
        petak_pasar(INDEKS_PANTAU, per_baris=3)
        st.markdown(
            f'<div class="catatan">{t("c_denyut_kartu")}</div>',
            unsafe_allow_html=True,
        )

    with t2:
        bagian_kripto()

    with t3:
        petak_pasar(KOMODITAS_PANTAU, per_baris=3)
        st.markdown(
            f'<div class="catatan">{t("c_kurs_pasar")}</div>',
            unsafe_allow_html=True,
        )

    with t5:
        bagian_forex()

    with t6:
        bagian_emas()

    with t4:
        petak_pasar(SAHAM_IDX_PANTAU, per_baris=4)
        st.markdown(
            f'<div class="catatan">{t("p_saham_id_ket")}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    kiri, kanan = st.columns([3, 1])
    with kiri:
        st.subheader(t("j_watchlist"))
    with kanan:
        if st.button(t("b_muat_ulang"), use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    watchlist = st.session_state.watchlist

    with st.expander(t("w_ubah")):
        a, b = st.columns([3, 1])
        with a:
            baru = st.text_input(
                t("w_tambah_simbol"),
                placeholder="Contoh: BMRI.JK, GOTO.JK, NVDA, ETH-USD",
                label_visibility="collapsed",
            )
        with b:
            if st.button(t("b_tambah"), use_container_width=True) and baru.strip():
                for s in [x.strip().upper() for x in baru.split(",") if x.strip()]:
                    if s not in watchlist:
                        watchlist.append(s)
                simpan_json(BERKAS_WATCHLIST, watchlist)
                st.rerun()

        buang = st.multiselect(t("w_hapus_simbol"), watchlist, label_visibility="collapsed",
                               placeholder=t("w_pilih_hapus"))
        if buang and st.button(t("b_hapus")):
            st.session_state.watchlist = [s for s in watchlist if s not in buang]
            simpan_json(BERKAS_WATCHLIST, st.session_state.watchlist)
            st.rerun()

        st.markdown(
            f'<div class="catatan">{t("w_panduan")}</div>',
            unsafe_allow_html=True,
        )

    if not watchlist:
        st.info(t("w_kosong"))
        return

    df = ambil_kutipan(tuple(watchlist))
    if df.empty:
        st.warning(t("w_muat_ulang"))
        return

    tampil = pd.DataFrame({
        t("k_simbol"): df["Simbol"],
        t("k_harga"): df["Harga"].map(format_angka),
        t("k_perubahan"): df["Perubahan"].map(lambda x: f"{x:+,.2f}"),
        t("k_persen"): df["Persen"].map(lambda x: f"{x:+.2f}%"),
        t("k_volume"): df["Volume"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—"),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True)

    naik = int((df["Persen"] > 0).sum())
    turun = int((df["Persen"] < 0).sum())
    st.markdown(
        f'<div class="catatan">'
        f'<span class="naik">▲ {naik} {t("p_naik")}</span> &nbsp;·&nbsp; '
        f'<span class="turun">▼ {turun} {t("p_turun")}</span> &nbsp;·&nbsp; '
        f'{len(df)} {t("p_dipantau")} &nbsp;·&nbsp; {t("p_segar60")}'
        f'</div>',
        unsafe_allow_html=True,
    )


def bagian_forex():
    # Label sudah diterjemahkan sejak awal, bukan lewat format_func — lebih
    # sederhana, dan tidak menyisakan nilai lama saat bahasa berganti.
    pilihan = {t("p_fx_utama"): FOREX_UTAMA,
               t("p_fx_rupiah"): FOREX_RUPIAH,
               t("p_fx_silang"): FOREX_SILANG}
    kelompok = st.radio("Kelompok", list(pilihan), horizontal=True,
                        label_visibility="collapsed", key=f'kel_fx_{st.session_state.get("bahasa", "en")}')
    peta = pilihan[kelompok]
    petak_pasar(peta, per_baris=4)

    st.markdown(
        f'<div class="catatan">{t("c_forex_baca")}</div>',
        unsafe_allow_html=True,
    )


def bagian_kripto():
    st.subheader(t("j_denyut_kripto"))

    dunia = ambil_kripto_global()
    fng = ambil_takut_serakah()

    if not dunia and not fng:
        st.info(t("w_kripto_gagal2"))
    else:
        k = st.columns(5)
        with k[0]:
            kartu(t("kr_kapitalisasi"), format_ringkas(dunia.get("kapitalisasi")),
                  f'{dunia["perubahan"]:+.2f}% ({t("kr_24jam")})' if dunia.get("perubahan") is not None else "",
                  warna(dunia.get("perubahan")))
        with k[1]:
            kartu(t("kr_volume24"), format_ringkas(dunia.get("volume")))
        with k[2]:
            d = dunia.get("dominasi_btc")
            kartu(t("kr_dominasi"), f"{d:.1f}%" if d is not None else "—",
                  f'Ethereum {dunia["dominasi_eth"]:.1f}%' if dunia.get("dominasi_eth") else "")
        with k[3]:
            n = dunia.get("jumlah_koin")
            kartu(t("kr_koin_aktif"), f"{n:,}" if n else "—")
        with k[4]:
            if fng:
                nilai = fng["nilai"]
                kunci_fng = SEBUTAN_FNG.get(fng["sebutan"])
                sebutan = t(kunci_fng) if kunci_fng else fng["sebutan"]
                # Skala takut-serakah: 0 sangat takut (merah) → 100 sangat serakah (hijau)
                kelas = "turun" if nilai < 45 else ("naik" if nilai > 55 else "diam")
                kartu(t("kr_fng"), f"{nilai}/100", sebutan, kelas)
            else:
                kartu(t("kr_fng"), "—", t("kr_tak_ada"))

    df = ambil_kripto_teratas(JUMLAH_KRIPTO)
    if df.empty:
        return

    tampil = pd.DataFrame({
        "#": range(1, len(df) + 1),
        t("kr_koin"): df["Koin"],
        t("k_nama"): df["Nama"],
        t("k_harga"): df["Harga"].map(format_harga_koin),
        t("kr_24jam"): df["24 jam %"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"),
        t("kr_7hari"): df["7 hari %"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"),
        t("k_kapitalisasi"): df["Kapitalisasi"].map(format_ringkas),
        t("kr_vol_kolom"): df["Volume 24 jam"].map(format_ringkas),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True)

    sah = df["24 jam %"].dropna()
    if len(sah):
        naik = int((sah > 0).sum())
        turun = int((sah < 0).sum())
        st.markdown(
            f'<div class="catatan">'
            f'<span class="naik">▲ {naik} {t("p_menguat")}</span> &nbsp;·&nbsp; '
            f'<span class="turun">▼ {turun} {t("p_melemah")}</span> {t("p_24jam")} '
            f'&nbsp;·&nbsp; {t("p_sumber_kripto")}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 2 — GRAFIK
# ──────────────────────────────────────────────────────────────────────

def halaman_grafik():
    st.subheader(t("j_grafik"))

    pilihan = list(dict.fromkeys(
        (st.session_state.watchlist or list(WATCHLIST_AWAL)) + list(FOREX_SEMUA)))
    a, b, c = st.columns([2, 1, 1])
    with a:
        simbol = st.selectbox(t("k_simbol"), pilihan,
                              format_func=lambda x: FOREX_SEMUA.get(x, x))
    with b:
        periode = st.selectbox(t("g_periode"), ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    with c:
        interval = st.selectbox(t("g_interval"), ["1d", "1wk", "1mo"], index=0)

    t_grafik, t_baca = st.tabs([t("t_grafik_ind"), t("t_pembacaan")])
    with t_grafik:
        bagian_grafik(simbol, periode, interval)
    with t_baca:
        bagian_pembacaan(simbol, periode, interval)


def bagian_pembacaan(simbol: str, periode: str, interval: str):
    df = ambil_riwayat(simbol, periode, interval)
    if df.empty or len(df) < 30:
        st.warning(t("tk_butuh_data"))
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
        fig.add_trace(go.Scatter(x=garis.index, y=garis, name=t("tk_garis_tren"),
                                 line=dict(color=pal()["aksen"], width=1.6, dash="dash")))

    for n, warna_ma in ((50, pal()["biru"]), (200, pal()["ungu"])):
        if n in b["sma_seri"]:
            fig.add_trace(go.Scatter(x=df.index, y=b["sma_seri"][n], name=f"MA{n}",
                                     line=dict(color=warna_ma, width=1)))

    for lv in b["resistensi"][:3]:
        fig.add_hline(y=lv["harga"], line=dict(color=pal()["turun"], width=1, dash="dot"),
                      annotation_text=f'{t("tk_penahan")} {format_angka(lv["harga"])} '
                                      f'({lv["sentuhan"]}x)',
                      annotation_position="right",
                      annotation_font=dict(size=9, color=pal()["turun"]))
    for lv in b["sokongan"][:3]:
        fig.add_hline(y=lv["harga"], line=dict(color=pal()["naik"], width=1, dash="dot"),
                      annotation_text=f'{t("tk_sokongan")} {format_angka(lv["harga"])} '
                                      f'({lv["sentuhan"]}x)',
                      annotation_position="right",
                      annotation_font=dict(size=9, color=pal()["naik"]))

    if b["puncak"]:
        fig.add_trace(go.Scatter(
            x=[tgl for tgl, _ in b["puncak"]], y=[h for _, h in b["puncak"]],
            mode="markers", name=t("tk_puncak"),
            marker=dict(symbol="triangle-down", size=7, color=pal()["turun"])))
    if b["lembah"]:
        fig.add_trace(go.Scatter(
            x=[tgl for tgl, _ in b["lembah"]], y=[h for _, h in b["lembah"]],
            mode="markers", name=t("tk_lembah"),
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

    st.markdown(f'**{t("tk_judul")}**')
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

    with st.expander(t("tk_angka")):
        st.dataframe(pd.DataFrame({
            t("tk_ukuran"): [t("k_harga"), "ATR (14)", "ATR %", "ADX (14)", "DI+", "DI-",
                       "RSI (14)", "MACD", "MACD signal", "Bollinger width %",
                       "52w high", "52w low"],
            t("tk_nilai"): [format_angka(b["harga"]), format_angka(b["atr"]),
                      f'{b["atr_persen"]:.2f}%', f'{b["adx"]:.1f}',
                      f'{b["di_naik"]:.1f}', f'{b["di_turun"]:.1f}',
                      f'{b["rsi"]:.1f}', format_angka(b["macd"], 4),
                      format_angka(b["macd_sinyal"], 4),
                      f'{b["lebar_bollinger"]:.2f}%',
                      format_angka(b["tertinggi_52"]), format_angka(b["terendah_52"])],
        }), use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="catatan">'
        f'{prosa("teknikal_penutup")}</div>',
        unsafe_allow_html=True,
    )


def bagian_grafik(simbol: str, periode: str, interval: str):
    indikator = st.multiselect(
        t("g_indikator"),
        ["SMA 20", "SMA 50", "SMA 200", "EMA 20", "Bollinger", "RSI", "MACD", "Volume"],
        default=["SMA 20", "SMA 50", "RSI", "Volume"],
    )

    df = ambil_riwayat(simbol, periode, interval)
    if df.empty:
        st.warning(t("w_data_kombinasi"))
        return

    tutup = df["Close"]
    terakhir = float(tutup.iloc[-1])
    awal = float(tutup.iloc[0])
    perubahan = (terakhir - awal) / awal * 100 if awal else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kartu(t("g_harga_akhir"), format_angka(terakhir))
    with k2:
        kartu(t("g_perubahan"), f"{perubahan:+.2f}%", "", warna(perubahan))
    with k3:
        kartu(t("g_tertinggi"), format_angka(float(df["High"].max())))
    with k4:
        kartu(t("g_terendah"), format_angka(float(df["Low"].min())))

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
    tinggi = [x / total for x in tinggi]

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
        f'<div class="catatan">{t("c_indikator")}</div>',
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
        "kunci": "pr_nilai", "ket": "pr_nilai_ket",
        "nilai": {"per": 15.0, "pbv": 2.0, "roe": 10.0, "div": 0.0, "der": 0.0, "kap": 0.0},
    },
    "Pemburu Dividen": {
        "kunci": "pr_dividen", "ket": "pr_dividen_ket",
        "nilai": {"per": 0.0, "pbv": 0.0, "roe": 8.0, "div": 4.0, "der": 100.0, "kap": 0.0},
    },
    "Kualitas Tinggi": {
        "kunci": "pr_kualitas", "ket": "pr_kualitas_ket",
        "nilai": {"per": 0.0, "pbv": 0.0, "roe": 18.0, "div": 0.0, "der": 60.0, "kap": 0.0},
    },
    "Tanpa Saringan": {
        "kunci": "pr_kosong", "ket": "pr_kosong_ket",
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

    Seluruh kalimat diambil dari kamus terjemahan, jadi pembacaan ini ikut
    berganti bahasa bersama antarmuka lainnya.
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
        kuat = t("tk_kuat_lemah")
    elif adx < 25:
        kuat = t("tk_kuat_mulai")
    elif adx < 40:
        kuat = t("tk_kuat_jelas")
    else:
        kuat = t("tk_kuat_sangat")

    if urut_rapi and adx >= 25:
        arah, nada = t("tk_tren_naik"), "naik"
    elif urut_terbalik and adx >= 25:
        arah, nada = t("tk_tren_turun"), "turun"
    elif len(di_atas) >= 2:
        arah, nada = t("tk_cenderung_naik"), "naik"
    elif len(di_atas) == 0 and b["sma"]:
        arah, nada = t("tk_cenderung_turun"), "turun"
    else:
        arah, nada = t("tk_menyamping"), "diam"

    if di_atas:
        posisi = t("tk_posisi_atas").format(
            n=len(di_atas), total=len(b["sma"]),
            daftar=", ".join("MA" + str(n) for n in sorted(di_atas)))
    else:
        posisi = t("tk_posisi_bawah")

    tren_tahun = b["tren"]["persen_tahun"]
    keandalan = b["tren"]["keandalan"]
    lurus = ""
    if not math.isnan(tren_tahun):
        lurus = t("tk_garis_lurus").format(laju=tren_tahun, andal=keandalan)
    hasil.append((arah, f"{posisi}{kuat} {lurus} (ADX {adx:.0f})", nada))

    # ── Perpotongan rata-rata ──
    if b["silang"]:
        jenis, tanggal = b["silang"]
        tgl = f"{tanggal:%d %b %Y}"
        if jenis == "emas":
            hasil.append((t("tk_emas"), t("tk_emas_isi").format(tgl=tgl), "naik"))
        else:
            hasil.append((t("tk_maut"), t("tk_maut_isi").format(tgl=tgl), "turun"))

    # ── Momentum ──
    rsi = b["rsi"]
    beda_rsi = rsi - b["rsi_sebelum"] if not math.isnan(b["rsi_sebelum"]) else 0
    if rsi >= 70:
        isi_rsi, nada_rsi = t("tk_rsi_tinggi").format(rsi=rsi), "turun"
    elif rsi <= 30:
        isi_rsi, nada_rsi = t("tk_rsi_rendah").format(rsi=rsi), "naik"
    else:
        isi_rsi, nada_rsi = t("tk_rsi_tengah").format(rsi=rsi), "diam"
    isi_rsi += t("tk_rsi_gerak").format(beda=beda_rsi)
    hasil.append((t("tk_momentum"), isi_rsi, nada_rsi))

    # ── MACD ──
    batang, sebelum = b["macd_batang"], b["macd_batang_sebelum"]
    di_atas_sinyal = b["macd"] > b["macd_sinyal"]
    menguat = batang > sebelum if not math.isnan(sebelum) else None
    isi = t("tk_macd_isi").format(
        posisi=t("tk_macd_atas") if di_atas_sinyal else t("tk_macd_bawah"),
        arah=t("tk_macd_melebar") if menguat else t("tk_macd_menyempit"))
    if di_atas_sinyal and menguat:
        isi += t("tk_macd_naik_tambah"); nada_m = "naik"
    elif di_atas_sinyal and not menguat:
        isi += t("tk_macd_naik_kurang"); nada_m = "diam"
    elif not di_atas_sinyal and not menguat:
        isi += t("tk_macd_turun_tambah"); nada_m = "turun"
    else:
        isi += t("tk_macd_turun_reda"); nada_m = "diam"
    hasil.append((t("tk_macd"), isi, nada_m))

    # ── Gejolak ──
    isi_v = t("tk_atr_isi").format(p=b["atr_persen"], atr=format_angka(b["atr"]))
    pers = b["lebar_persentil"]
    nada_v = "diam"
    if not math.isnan(pers):
        if pers < 20:
            isi_v += t("tk_boll_sempit").format(p=100 - pers)
        elif pers > 80:
            isi_v += t("tk_boll_lebar").format(p=pers)
            nada_v = "turun"
        else:
            isi_v += t("tk_boll_normal")
    hasil.append((t("tk_gejolak"), isi_v, nada_v))

    # ── Volume ──
    if not math.isnan(b["volume_rata"]) and b["volume_rata"] > 0:
        rasio = b["volume"] / b["volume_rata"]
        if rasio > 1.5:
            isi_vol, nada_vol = t("tk_vol_besar").format(r=rasio), "naik"
        elif rasio < 0.6:
            isi_vol, nada_vol = t("tk_vol_kecil").format(r=rasio), "turun"
        else:
            isi_vol, nada_vol = t("tk_vol_wajar").format(r=rasio), "diam"
        hasil.append((t("tk_volume"), isi_vol, nada_vol))

    # ── Jarak ke level penting ──
    bagian = []
    if b["sokongan"]:
        lv = b["sokongan"][0]
        bagian.append(t("tk_level_sok").format(
            h=format_angka(lv["harga"]), j=(lv["harga"] / kini - 1) * 100, n=lv["sentuhan"]))
    if b["resistensi"]:
        lv = b["resistensi"][0]
        bagian.append(t("tk_level_res").format(
            h=format_angka(lv["harga"]), j=(lv["harga"] / kini - 1) * 100, n=lv["sentuhan"]))
    if bagian:
        hasil.append((t("tk_level"),
                      t("tk_level_awal") + ", ".join(bagian) + t("tk_level_akhir"), "diam"))

    # ── Posisi dalam rentang setahun ──
    atas, bawah = b["tertinggi_52"], b["terendah_52"]
    if atas > bawah:
        letak = (kini - bawah) / (atas - bawah) * 100
        hasil.append((t("tk_posisi52"),
                      t("tk_posisi52_isi").format(
                          letak=letak, bawah=format_angka(bawah),
                          atas=format_angka(atas), dari=(kini / atas - 1) * 100),
                      "naik" if letak > 60 else ("turun" if letak < 40 else "diam")))

    return hasil


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — SCREENER
# ──────────────────────────────────────────────────────────────────────

def halaman_screener():
    st.subheader(t("j_screener"))
    st.markdown(
        f'<div class="catatan">{t("s_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    t_saham, t_kripto = st.tabs([t("t_saham"), t("t_kripto")])
    with t_saham:
        screener_saham()
    with t_kripto:
        screener_kripto()


def screener_saham():
    a, b = st.columns([2, 1])
    with a:
        pilihan = st.selectbox(t("s_pasar"), list(SEMESTA),
                               index=list(SEMESTA).index("Amerika Serikat — US"))
    with b:
        st.write("")
        muat = st.button(t("s_saring"), use_container_width=True, key="saring_saham")

    pasar = SEMESTA[pilihan]
    daftar, mata_uang, satuan = pasar["daftar"], pasar["mata_uang"], pasar["satuan"]
    pengali = PENGALI_KAP.get(satuan, 1e9)

    st.markdown(
        f'<div class="catatan">{len(daftar)} {t("s_dalam_daftar")} <b>{mata_uang}</b>. '
        f'{t("s_lama_pertama")}</div>',
        unsafe_allow_html=True,
    )

    kunci = f"fund_{pilihan}"
    if muat:
        with st.spinner(f"Mengambil data {len(daftar)} saham…"):
            st.session_state[kunci] = ambil_fundamental_banyak(tuple(daftar))

    df = st.session_state.get(kunci)
    if df is None:
        st.info(t("s_tekan"))
        return
    if df.empty:
        st.warning("Tidak ada data yang berhasil diambil. Periksa koneksi internet Anda.")
        return

    st.divider()
    st.markdown(f'**{t("s_penyaring")}** — {len(df)} {t("s_diambil")}')

    st.markdown(f'<div class="catatan">{t("s_siap_pakai")}</div>',
                unsafe_allow_html=True)
    kol = st.columns(len(PRESET))
    for k, (nama_preset, isi) in zip(kol, PRESET.items()):
        with k:
            if st.button(t(isi["kunci"]).upper(), use_container_width=True,
                         key=f"preset_{nama_preset}", help=t(isi["ket"])):
                for kunci, nilai in isi["nilai"].items():
                    st.session_state[f"f_{kunci}"] = nilai
                st.rerun()

    with st.expander(t("s_atur"), expanded=True):
        k1, k2, k3 = st.columns(3)
        with k1:
            per_maks = st.number_input(t("s_per_maks"), value=0.0, step=1.0, key="f_per",
                                       help="0 berarti tidak disaring. PER 15 artinya "
                                            "harga 15 kali laba setahun.")
            pbv_maks = st.number_input(t("s_pbv_maks"), value=0.0, step=0.1, key="f_pbv",
                                       help="0 berarti tidak disaring. PBV di bawah 1 "
                                            "artinya harga di bawah nilai buku.")
        with k2:
            roe_min = st.number_input(t("s_roe_min"), value=0.0, step=1.0, key="f_roe",
                                      help="Seberapa produktif modal pemegang saham.")
            div_min = st.number_input(t("s_div_min"), value=0.0, step=0.5, key="f_div")
        with k3:
            der_maks = st.number_input(t("s_der_maks"), value=0.0, step=10.0, key="f_der",
                                       help="Utang dibanding modal. 100 berarti utang "
                                            "sebesar modal sendiri.")
            kap_min = st.number_input(f'{t("s_kap_min")} ({satuan})',
                                      value=0.0, step=1.0, key="f_kap",
                                      help=f"Dalam mata uang asli pasar ini ({mata_uang}). "
                                           f"Nilainya tidak dikonversi ke rupiah.")

        sektor_ada = sorted(x for x in df["Sektor"].dropna().unique() if x != "—")
        sektor = st.multiselect(t("s_sektor"), sektor_ada, placeholder=t("s_semua_sektor"))

        syariah = st.selectbox(
            t("s_syariah"), [t("s_tak_dipakai")] + list(AMBANG_SYARIAH),
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
    if syariah != t("s_tak_dipakai"):
        ambang = AMBANG_SYARIAH[syariah]
        periksa = hasil.apply(lambda r: periksa_syariah(r, ambang), axis=1)
        rincian_syariah = pd.DataFrame(list(periksa), index=hasil.index)
        hasil = hasil[rincian_syariah["lolos"]]
        rincian_syariah = rincian_syariah.loc[hasil.index]
        saringan.append(f"penapisan {syariah}")

    st.markdown(
        f'<div class="catatan">{t("s_aktif")} '
        f'{" · ".join(saringan) if saringan else t("s_belum_ada")}'
        f' &nbsp;→&nbsp; <b style="color:var(--aksen);">{len(hasil)} {t("s_lolos")}</b></div>',
        unsafe_allow_html=True,
    )

    if hasil.empty:
        st.warning(t("s_kosong"))
        return

    hasil = hitung_skor(hasil)

    urut = st.selectbox(t("s_urutkan"),
                        ["Skor", "Kapitalisasi", "PER", "PBV", "ROE %", "Dividen %",
                         "Margin %", "DER", "Tumbuh Laba %"])
    menaik = urut in ("PER", "PBV", "DER")
    hasil = hasil.sort_values(urut, ascending=menaik, na_position="last")

    tampil = pd.DataFrame({
        t("k_skor"): hasil["Skor"].map(lambda x: f"{x:.0f}" if pd.notna(x) else "—"),
        t("k_simbol"): hasil["Simbol"],
        t("k_nama"): hasil["Nama"],
        t("k_sektor"): hasil["Sektor"],
        t("k_harga"): hasil["Harga"].map(format_angka),
        t("k_kapitalisasi"): hasil["Kapitalisasi"].map(format_ringkas),
        "PER": hasil["PER"].map(lambda x: format_angka(x, 1)),
        "PBV": hasil["PBV"].map(lambda x: format_angka(x, 2)),
        t("k_roe"): hasil["ROE %"].map(lambda x: format_angka(x, 1)),
        t("k_margin"): hasil["Margin %"].map(lambda x: format_angka(x, 1)),
        "DER": hasil["DER"].map(lambda x: format_angka(x, 1)),
        t("k_dividen_persen"): hasil["Dividen %"].map(lambda x: format_angka(x, 2)),
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
            f'<div class="label">{t("s_syariah").upper()}</div>'
            f'<div style="color:var(--teks2);font-size:0.8rem;line-height:1.75;'
            f'margin-top:0.35rem;">'
            f'{AMBANG_SYARIAH[syariah]["keterangan"]}<br><br>'
            f'{prosa("syariah_catatan")}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # ── Kirim ke watchlist ──
    st.markdown(f'**{t("s_tindak")}**')
    a, b = st.columns([3, 1])
    with a:
        terpilih = st.multiselect(t("s_pilih_saham"), hasil["Simbol"].tolist(),
                                  placeholder=t("s_pilih_ph"),
                                  key="pilih_screener")
    with b:
        st.write("")
        if st.button(t("s_ke_watchlist"), use_container_width=True, key="ke_watchlist"):
            if terpilih:
                baru_ditambah = [x for x in terpilih if x not in st.session_state.watchlist]
                st.session_state.watchlist.extend(baru_ditambah)
                simpan_json(BERKAS_WATCHLIST, st.session_state.watchlist)
                st.success(f'{len(baru_ditambah)} {t("s_ditambahkan")}'
                           if baru_ditambah else t("s_sudah_ada"))
            else:
                st.warning(t("s_belum_pilih"))

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
        st.markdown(f'**{t("s_banding")}**')
        st.dataframe(tabel, use_container_width=True)
        st.markdown(
            f'<div class="catatan">{t("c_banding_sektor")}</div>',
            unsafe_allow_html=True,
        )
    elif len(terpilih) == 1:
        st.markdown(f'<div class="catatan">{t("s_pilih_dua")}</div>',
                    unsafe_allow_html=True)

    st.download_button(
        t("s_unduh"),
        hasil.to_csv(index=False).encode("utf-8"),
        file_name=f"screener-{datetime.now():%Y%m%d-%H%M}.csv",
        mime="text/csv",
    )

    st.markdown(
        '<div class="catatan">'
        f'{prosa("screener_baca")}</div>',
        unsafe_allow_html=True,
    )


def screener_kripto():
    a, b = st.columns([2, 1])
    with a:
        jumlah = st.slider(t("s_koin_ambil"), 50, 250, 100, step=50)
    with b:
        st.write("")
        if st.button(t("b_segarkan"), use_container_width=True, key="segar_kripto"):
            ambil_kripto_screener.clear()

    df = ambil_kripto_screener(jumlah)
    if df.empty:
        st.warning(t("s_kripto_gagal"))
        return

    with st.expander(t("s_atur"), expanded=True):
        k1, k2, k3 = st.columns(3)
        with k1:
            kap_min = st.number_input(t("s_kap_min_miliar"), value=0.0, step=1.0)
        with k2:
            naik_7h = st.number_input(t("s_naik7"), value=-100.0, step=5.0)
        with k3:
            dari_puncak = st.number_input(t("s_dari_puncak"), value=-100.0,
                                          step=10.0,
                                          help=t("s_puncak_bantuan"))

    hasil = df.copy()
    if kap_min > 0:
        hasil = hasil[hasil["Kapitalisasi"] >= kap_min * 1e9]
    if naik_7h > -100:
        hasil = hasil[hasil["7 hari %"] >= naik_7h]
    if dari_puncak > -100:
        hasil = hasil[hasil["Dari puncak %"] >= dari_puncak]

    st.markdown(
        f'<div class="catatan"><b style="color:var(--aksen);">{len(hasil)} {t("s_koin_lolos")}</b> '
        f'{t("s_koin_dari")} {len(df)}</div>',
        unsafe_allow_html=True,
    )
    if hasil.empty:
        st.warning(t("s_koin_kosong"))
        return

    urut = st.selectbox(t("s_urutkan"),
                        ["Peringkat", "Kapitalisasi", "24 jam %", "7 hari %",
                         "30 hari %", "Dari puncak %", "Volume"], key="urut_kripto")
    hasil = hasil.sort_values(urut, ascending=(urut == "Peringkat"), na_position="last")

    persen = lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
    tampil = pd.DataFrame({
        "#": hasil["Peringkat"].map(lambda x: f"{int(x)}" if pd.notna(x) else "—"),
        t("kr_koin"): hasil["Simbol"],
        t("k_nama"): hasil["Nama"],
        t("k_harga"): hasil["Harga"].map(format_harga_koin),
        t("kr_24jam"): hasil["24 jam %"].map(persen),
        t("kr_7hari"): hasil["7 hari %"].map(persen),
        t("kr_30hari"): hasil["30 hari %"].map(persen),
        t("kr_dari_puncak"): hasil["Dari puncak %"].map(persen),
        t("k_kapitalisasi"): hasil["Kapitalisasi"].map(format_ringkas),
        t("kr_vol_kolom"): hasil["Volume"].map(format_ringkas),
    })
    st.dataframe(tampil, use_container_width=True, hide_index=True, height=460)

    st.download_button(
        t("s_unduh"),
        hasil.to_csv(index=False).encode("utf-8"),
        file_name=f"screener-kripto-{datetime.now():%Y%m%d-%H%M}.csv",
        mime="text/csv",
        key="unduh_kripto",
    )

    st.markdown(
        f'<div class="catatan">{t("c_dari_puncak")}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — FUNDAMENTAL
# ──────────────────────────────────────────────────────────────────────

def halaman_fundamental():
    st.subheader(t("j_fundamental"))

    a, b = st.columns([3, 1])
    with a:
        simbol = st.text_input(t("f_simbol"), value="NVDA",
                               placeholder="NVDA, AAPL, MSFT, BBCA.JK")
    with b:
        st.write("")
        if st.button(t("b_segarkan"), use_container_width=True, key="segar_fund"):
            ambil_fundamental_satu.clear()
            ambil_laporan.clear()

    simbol = simbol.strip().upper()
    if not simbol:
        return

    info = ambil_fundamental_satu(simbol)
    if not info or not info.get("regularMarketPrice"):
        st.warning(f'**{simbol}** — {t("w_emiten_hilang")}')
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
        (t("fd_harga"), format_angka(info.get("regularMarketPrice")), ""),
        (t("fd_kapitalisasi"), format_ringkas(info.get("marketCap"), ""), ""),
        ("PER", format_angka(info.get("trailingPE"), 1), t("fd_per_ket")),
        ("PBV", format_angka(info.get("priceToBook"), 2), t("fd_pbv_ket")),
        ("ROE", f'{_angka(info.get("returnOnEquity")) * 100:.1f}%'
                if not math.isnan(_angka(info.get("returnOnEquity"))) else "—", t("fd_roe_ket")),
        (t("fd_margin"), f'{_angka(info.get("profitMargins")) * 100:.1f}%'
                        if not math.isnan(_angka(info.get("profitMargins"))) else "—", ""),
        ("DER", format_angka(info.get("debtToEquity"), 1), t("fd_der_ket")),
        (t("fd_dividen"), f"{dy:.2f}%" if not math.isnan(dy) else "—", t("fd_dividen_ket")),
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
            f'<div class="kartu"><div class="label">{t("fd_rentang52")}</div>'
            f'<div style="position:relative;height:8px;background:var(--kisi);border-radius:4px;'
            f'margin:0.6rem 0 0.35rem;">'
            f'<div style="position:absolute;left:{posisi:.1f}%;top:-3px;width:3px;height:14px;'
            f'background:var(--aksen);border-radius:1px;"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;'
            f'color:var(--teks3);"><span>{format_angka(rendah)}</span>'
            f'<span style="color:var(--aksen);">{posisi:.0f}% {t("fd_dari_bawah")}</span>'
            f'<span>{format_angka(tinggi)}</span></div></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    laporan = ambil_laporan(simbol)
    t1, t2, t3 = st.tabs([t("t_laba_rugi"), t("t_neraca"), t("t_arus_kas")])
    for tab, kunci, judul in [(t1, "laba_rugi", "laba rugi"),
                              (t2, "neraca", "neraca"),
                              (t3, "arus_kas", "arus kas")]:
        with tab:
            tabel_laporan(laporan.get(kunci), judul)

    st.markdown(
        f'<div class="catatan">{t("c_laporan_yahoo")}</div>',
        unsafe_allow_html=True,
    )


def tabel_laporan(df, judul: str):
    if df is None or not hasattr(df, "empty") or df.empty:
        st.info(t("w_laporan_hilang"))
        return

    tampil = df.copy()
    tampil.columns = [c.strftime("%Y") if hasattr(c, "strftime") else str(c)
                      for c in tampil.columns]
    tampil = tampil.map(lambda x: format_ringkas(x, "") if pd.notna(x) else "—")
    st.dataframe(tampil, use_container_width=True, height=420)
    st.markdown(
        f'<div class="catatan">{t("c_satuan")}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — KALKULATOR POSISI & RISIKO
# ──────────────────────────────────────────────────────────────────────

def halaman_kalkulator():
    st.subheader(t("j_kalkulator"))
    st.markdown(
        f'<div class="catatan">{t("kal_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    t1, t4, t2, t3, t5, t6 = st.tabs([t("t_ukuran_posisi"), t("t_posisi_forex"),
                                      t("t_rata_harga"), t("t_impas"),
                                      t("t_zakat_emas"), t("t_tabung_emas")])
    with t1:
        kalkulator_posisi()
    with t4:
        kalkulator_forex()
    with t2:
        kalkulator_averaging()
    with t3:
        kalkulator_impas()
    with t5:
        kalkulator_zakat_emas()
    with t6:
        kalkulator_tabung_emas()


def imbal_hasil_internal(arus: list, tebakan_bawah: float = -0.95,
                         tebakan_atas: float = 10.0) -> float:
    """IRR bulanan dari deretan arus kas, dicari dengan membelah dua.

    Dipakai karena setoran bulanan tidak bisa dinilai dengan CAGR biasa:
    uang yang disetor bulan lalu belum sempat tumbuh selama uang yang
    disetor sepuluh tahun lalu. CAGR akan melebih-lebihkan hasilnya.
    """
    def nilai_kini(r):
        return sum(a / ((1 + r) ** i) for i, a in enumerate(arus))

    bawah, atas = tebakan_bawah, tebakan_atas
    f_bawah, f_atas = nilai_kini(bawah), nilai_kini(atas)
    if f_bawah * f_atas > 0:      # tidak ada perpotongan di rentang ini
        return float("nan")
    for _ in range(200):
        tengah = (bawah + atas) / 2
        f_tengah = nilai_kini(tengah)
        if abs(f_tengah) < 1e-6:
            return tengah
        if f_bawah * f_tengah < 0:
            atas, f_atas = tengah, f_tengah
        else:
            bawah, f_bawah = tengah, f_tengah
    return (bawah + atas) / 2


def kalkulator_zakat_emas():
    st.markdown(t("zk_judul"))

    e = ambil_emas_kini()
    harga_awal = float(round(e["idr_gram"])) if e else 1_000_000.0

    a, b = st.columns(2)
    with a:
        berat = st.number_input(t("zk_berat"), min_value=0.0, value=100.0, step=1.0,
                                help=t("zk_berat_bantuan"))
    with b:
        harga = st.number_input(t("zk_harga_gram"), min_value=0.0, value=harga_awal,
                                step=10_000.0, format="%.0f", help=t("zk_harga_bantuan"))

    haul = st.checkbox(t("zk_haul"), value=True, help=t("zk_haul_bantuan"))

    nisab_rp = NISAB_EMAS_GRAM * harga
    nilai = berat * harga

    k = st.columns(3)
    with k[0]:
        kartu(t("zk_nisab"), f"{NISAB_EMAS_GRAM:g} g", f"Rp {format_angka(nisab_rp, 0)}")
    with k[1]:
        kartu(t("zk_simpanan"), f"{berat:g} g", f"Rp {format_angka(nilai, 0)}")
    with k[2]:
        cukup = berat >= NISAB_EMAS_GRAM
        kartu(t("zk_status"),
              t("zk_capai") if cukup else t("zk_belum"),
              f'{berat / NISAB_EMAS_GRAM * 100:.0f}% {t("zk_dari_nisab")}'
              if NISAB_EMAS_GRAM else "",
              "naik" if cukup else "diam")

    if berat >= NISAB_EMAS_GRAM and haul:
        zakat_gram = berat * KADAR_ZAKAT
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
            f'<div class="label">{t("zk_wajib")}</div>'
            f'<div class="angka">{zakat_gram:,.3f} g</div>'
            f'<div class="delta naik">Rp {format_angka(zakat_gram * harga, 0)} '
            f'&nbsp;·&nbsp; {KADAR_ZAKAT * 100:g}%</div></div>',
            unsafe_allow_html=True,
        )
    elif berat >= NISAB_EMAS_GRAM and not haul:
        st.info(t("zk_belum_haul"))
    else:
        kurang = NISAB_EMAS_GRAM - berat
        st.info(f'{t("zk_kurang")} {kurang:,.2f} g '
                f'(Rp {format_angka(kurang * harga, 0)}) {t("zk_kurang2")}')

    st.divider()
    st.markdown(f'<div class="catatan">{prosa("zakat_dasar")}</div>',
                unsafe_allow_html=True)

    with st.expander(t("zk_nisab_perak")):
        perak_gram = (e or {}).get("perak_idr_gram")
        if perak_gram:
            nisab_perak_rp = NISAB_PERAK_GRAM * perak_gram
            st.markdown(
                f'<div class="catatan">{t("zk_perak_setara")} '
                f'<b>Rp {format_angka(nisab_perak_rp, 0)}</b> '
                f'({NISAB_PERAK_GRAM:g} g × Rp {format_angka(perak_gram, 0)}), '
                f'{t("zk_perak_banding")} <b>Rp {format_angka(nisab_rp, 0)}</b>.</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'<div class="catatan">{prosa("zakat_perak")}</div>',
                    unsafe_allow_html=True)

    with st.expander(t("zk_perhiasan")):
        st.markdown(f'<div class="catatan">{prosa("zakat_perhiasan")}</div>',
                    unsafe_allow_html=True)

    st.markdown(f'<div class="catatan">{prosa("zakat_penutup")}</div>',
                unsafe_allow_html=True)


def kalkulator_tabung_emas():
    st.markdown(t("tb_judul"))

    a, b, c = st.columns(3)
    with a:
        setoran = st.number_input(t("tb_setoran"), min_value=0.0, value=500_000.0,
                                  step=100_000.0, format="%.0f")
    with b:
        lama = st.selectbox(t("tb_lama"), ["1y", "2y", "5y", "10y"], index=2,
                            format_func=lambda x: f'{x[:-1]}{t("lp_singkat_tahun")}')
    with c:
        bunga = st.number_input(t("tb_deposito"), min_value=0.0, max_value=20.0,
                                value=4.0, step=0.25, help=t("tb_deposito_bantuan"))

    d, f = st.columns(2)
    with d:
        premi = st.number_input(t("tb_premi"), min_value=0.0, max_value=30.0,
                                value=8.0, step=0.5, help=t("tb_premi_bantuan"))
    with f:
        potong = st.number_input(t("tb_potongan"), min_value=0.0, max_value=30.0,
                                 value=5.0, step=0.5, help=t("tb_potongan_bantuan"))

    riwayat = ambil_emas_riwayat(lama)
    if riwayat.empty:
        st.warning(t("em_gagal"))
        return

    # Satu setoran di awal tiap bulan, dibelikan emas pada harga hari itu.
    bulanan = riwayat["idr_gram"].resample("MS").first().dropna()
    if len(bulanan) < 6:
        st.warning(t("tb_terlalu_pendek"))
        return

    gram, arus, jejak = 0.0, [], []
    for tanggal, harga in bulanan.items():
        harga_beli = harga * (1 + premi / 100)
        gram += setoran / harga_beli if harga_beli > 0 else 0.0
        arus.append(-setoran)
        jejak.append({"tanggal": tanggal, "gram": gram,
                      "setoran": setoran * len(arus),
                      "nilai": gram * harga * (1 - potong / 100)})

    harga_akhir = float(riwayat["idr_gram"].iloc[-1])
    nilai_akhir = gram * harga_akhir * (1 - potong / 100)
    total_setor = setoran * len(bulanan)
    arus[-1] += nilai_akhir                       # dijual pada setoran terakhir

    bulan_irr = imbal_hasil_internal(arus)
    tahunan = ((1 + bulan_irr) ** 12 - 1) * 100 if bulan_irr == bulan_irr else float("nan")

    # Pembanding: deposito dengan bunga majemuk bulanan, setoran sama.
    r_bulan = (1 + bunga / 100) ** (1 / 12) - 1
    saldo_deposito = 0.0
    jejak_deposito = []
    for _ in range(len(bulanan)):
        saldo_deposito = (saldo_deposito + setoran) * (1 + r_bulan)
        jejak_deposito.append(saldo_deposito)

    k = st.columns(4)
    with k[0]:
        kartu(t("tb_total_setor"), f"Rp {format_angka(total_setor, 0)}",
              f'{len(bulanan)} {t("tb_kali_setor")}')
    with k[1]:
        kartu(t("tb_gram"), f"{gram:,.2f} g",
              f'Rp {format_angka(harga_akhir, 0)}/g')
    with k[2]:
        untung = nilai_akhir - total_setor
        kartu(t("tb_nilai_jual"), f"Rp {format_angka(nilai_akhir, 0)}",
              f"{untung:+,.0f}", warna(untung))
    with k[3]:
        kartu(t("tb_imbal"),
              f"{tahunan:.2f}%" if tahunan == tahunan else "—",
              t("tb_per_tahun"), warna(tahunan if tahunan == tahunan else 0))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[x["tanggal"] for x in jejak],
                             y=[x["nilai"] for x in jejak],
                             name=t("tb_garis_emas"),
                             line=dict(color=pal()["aksen"], width=2)))
    fig.add_trace(go.Scatter(x=[x["tanggal"] for x in jejak], y=jejak_deposito,
                             name=t("tb_garis_deposito"),
                             line=dict(color=pal()["biru"], width=1.4, dash="dot")))
    fig.add_trace(go.Scatter(x=[x["tanggal"] for x in jejak],
                             y=[x["setoran"] for x in jejak],
                             name=t("tb_garis_setoran"),
                             line=dict(color=pal()["kisi2"], width=1.2)))
    fig.update_layout(
        height=380, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
        title=dict(text=t("tb_judul_grafik"), font=dict(size=13, color=pal()["aksen"]), x=0),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"])
    st.plotly_chart(fig, use_container_width=True)

    selisih = nilai_akhir - saldo_deposito
    kunci = "tb_emas_unggul" if selisih > 0 else "tb_deposito_unggul"
    st.markdown(
        f'<div class="catatan">{t(kunci)} '
        f'<b class="{warna(selisih)}">Rp {format_angka(abs(selisih), 0)}</b>.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="catatan">{prosa("tabung_emas_catatan")}</div>',
                unsafe_allow_html=True)


def kalkulator_forex():
    st.markdown(t("kal_forex_judul"))

    a, b = st.columns(2)
    with a:
        pasangan = st.selectbox(t("kf_pasangan"), list(FOREX_SEMUA),
                                format_func=lambda x: FOREX_SEMUA[x], key="fx_pair")
        modal = st.number_input(t("kf_modal"), min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f", key="fx_modal")
        risiko_persen = st.slider(t("kf_risiko"), 0.5, 10.0, 2.0, 0.5,
                                  key="fx_risiko")
    with b:
        jenis_lot = st.selectbox(t("kf_lot"), list(LOT_FOREX), key="fx_lot")
        stop_pip = st.number_input(t("kf_stop"), min_value=1.0, value=30.0,
                                   step=5.0, key="fx_stop")
        target_pip = st.number_input(t("kf_target"), min_value=0.0, value=60.0,
                                     step=5.0, key="fx_target")

    kutipan = ambil_kutipan((pasangan,))
    if kutipan.empty:
        st.warning(t("w_harga_gagal"))
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
        kartu(t("kf_harga_kini"), format_angka(harga, 4), f"1 pip = {n['pip']:g}")
    with k[1]:
        kartu(t("kf_nilai_pip"), "Rp " + format_angka(n["nilai_idr"], 0),
              f'{t("kf_per_lot")} {jenis_lot.split(" ")[0].lower()} lot')
    with k[2]:
        kartu(t("kf_boleh_buka"), f"{lot:.2f} lot",
              f'{lot * unit:,.0f} {t("kf_unit")} {dasar}' if dasar else "")
    with k[3]:
        kartu(t("kf_risiko_kartu"), "Rp " + format_angka(nominal_risiko, 0),
              f'{risiko_persen:g}% {t("kf_dari_modal")}', "turun")

    if target_pip > 0:
        rasio = target_pip / stop_pip
        untung = lot * target_pip * n["nilai_idr"]
        k = st.columns(3)
        with k[0]:
            kartu("POTENSI UNTUNG", "Rp " + format_angka(untung, 0),
                  f'{t("kf_kalau_target")} {target_pip:g} {t("kf_tercapai")}', "naik")
        with k[1]:
            kartu(t("kf_rasio"), f"{rasio:.2f} : 1", t("kf_rasio_ket"),
                  "naik" if rasio >= 1 else "turun")
        with k[2]:
            perlu = 100 / (1 + rasio)
            kartu(t("kf_menang_min"), f"{perlu:.0f}%", t("kf_agar_untung"))

    if lot < 0.01:
        st.warning(t("kal_lot_kecil"))

    st.markdown(
        f'<div class="catatan">{prosa("kal_forex_catatan").format(kutip=kutip)}</div>',
        unsafe_allow_html=True,
    )


def kalkulator_posisi():
    k1, k2 = st.columns(2)
    with k1:
        modal = st.number_input(t("kal_modal"), min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f")
        risiko_persen = st.slider(t("kal_risiko"), 0.5, 10.0, 2.0, 0.5,
                                  help=t("kal_aturan_umum"))
    with k2:
        harga_masuk = st.number_input(t("kal_harga_beli"), min_value=0.0, value=5000.0, step=50.0)
        stop_loss = st.number_input(t("kal_stop"), min_value=0.0,
                                    value=4700.0, step=50.0)

    target = st.number_input(t("kal_target"),
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
        kartu(t("kal_boleh_beli"), f"{lot:,} lot", f'{lot * LOT:,} {t("kal_lembar")}')
    with k[1]:
        kartu(t("kal_nilai_beli"), format_angka(nilai_beli, 0), f'{porsi_modal:.1f}% {t("kal_dari_modal")}')
    with k[2]:
        kartu(t("kal_risiko_nyata"), format_angka(rugi_nyata, 0),
              f'{rugi_nyata / modal * 100:.2f}% {t("kal_dari_modal")}' if modal else "", "turun")
    with k[3]:
        if target > harga_masuk:
            untung = lot * LOT * (target - harga_masuk)
            rasio = (target - harga_masuk) / rugi_per_lembar
            kartu(t("kal_potensi"), format_angka(untung, 0),
                  f'{t("kal_rasio")} {rasio:.2f} : 1', "naik")
        else:
            kartu(t("kal_potensi"), "—", t("kal_target_kosong"))

    if porsi_modal > 100:
        st.warning(t("kal_melebihi_modal").format(p=porsi_modal))

    if target > harga_masuk:
        rasio = (target - harga_masuk) / rugi_per_lembar
        if rasio < 1:
            st.markdown(
                f'<div class="catatan"><b class="turun">'
                f'{t("kal_rasio_kalimat").format(r=rasio)}</b> '
                f'{t("kal_rasio_buruk").format(p=100 / (1 + rasio))}</div>',
                unsafe_allow_html=True,
            )
        else:
            menang_perlu = 100 / (1 + rasio)
            st.markdown(
                f'<div class="catatan"><b class="naik">'
                f'{t("kal_rasio_kalimat").format(r=rasio)}</b> '
                f'{t("kal_rasio_baik").format(p=menang_perlu)}</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        f'<div class="catatan">{prosa("kal_posisi_catatan")}</div>',
        unsafe_allow_html=True,
    )


def kalkulator_averaging():
    st.markdown(t("ka_judul"))

    k1, k2 = st.columns(2)
    with k1:
        lot1 = st.number_input(t("ka_lot_punya"), min_value=0.0, value=10.0, step=1.0)
        harga1 = st.number_input(t("ka_harga_lama"), min_value=0.0, value=5000.0, step=50.0)
    with k2:
        lot2 = st.number_input(t("ka_lot_baru"), min_value=0.0, value=10.0, step=1.0)
        harga2 = st.number_input(t("ka_harga_baru"), min_value=0.0, value=4200.0, step=50.0)

    harga_pasar = st.number_input(t("ka_harga_pasar"), min_value=0.0, value=4200.0, step=50.0)

    total_lot = lot1 + lot2
    if total_lot <= 0:
        st.info(t("ka_isi_lot"))
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
        kartu(t("ka_rata_baru"), format_angka(rata, 0),
              f'{t("bt_dari")} {format_angka(harga1, 0)}',
              "naik" if rata < harga1 else ("turun" if rata > harga1 else "diam"))
    with k[1]:
        kartu(t("pf_total_modal"), format_angka(total_modal, 0), f"{total_lot:g} lot")
    with k[2]:
        kartu(t("ka_lr_kini"), f"{laba:+,.0f}", f"{laba_persen:+.2f}%", warna(laba))
    with k[3]:
        kartu(t("ka_sebelum"), f"{laba_sebelum:+,.0f}", f"{persen_sebelum:+.2f}%",
              warna(laba_sebelum))

    impas = rata
    st.markdown(
        f'<div class="catatan">{t("ka_impas_perlu").format(h=format_angka(impas, 0), p=(impas / harga_pasar - 1) * 100)}</div>',
        unsafe_allow_html=True,
    )

    if harga2 < harga1:
        st.markdown(
            f'<div class="catatan" style="margin-top:0.6rem;">'
            f'{prosa("kal_average_catatan")}</div>',
            unsafe_allow_html=True,
        )


def kalkulator_impas():
    st.markdown(t("ki_judul"))

    k1, k2, k3 = st.columns(3)
    with k1:
        harga_beli = st.number_input(t("kal_harga_beli"), min_value=0.0, value=5000.0,
                                     step=50.0, key="impas_beli")
        jumlah_lot = st.number_input(t("ki_jumlah_lot"), min_value=0.0, value=10.0, step=1.0,
                                     key="impas_lot")
    with k2:
        biaya_beli = st.number_input(t("ki_biaya_beli"), min_value=0.0, value=BIAYA_BELI,
                                     step=0.01, format="%.3f")
        biaya_jual = st.number_input(t("ki_biaya_jual"), min_value=0.0, value=BIAYA_JUAL,
                                     step=0.01, format="%.3f", help=t("ki_biaya_jual_ket"))
    with k3:
        target_untung = st.number_input(t("ki_target"), min_value=0.0, value=10.0, step=1.0)

    if harga_beli <= 0 or jumlah_lot <= 0:
        st.info(t("ki_isi_dulu"))
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
        kartu(t("ki_modal_keluar"), format_angka(modal_total, 0),
              f'{t("ki_termasuk")} {format_angka(ongkos_beli, 0)}')
    with k[1]:
        kartu(t("ki_impas"), format_angka(harga_impas, 0),
              f'{(harga_impas / harga_beli - 1) * 100:+.2f}% {t("ki_dari_beli")}')
    with k[2]:
        kartu(f'{t("ki_untuk_untung")} {target_untung:g}%', format_angka(harga_target, 0),
              f'{(harga_target / harga_beli - 1) * 100:+.2f}% {t("ki_dari_beli")}', "naik")
    with k[3]:
        untung_bersih = modal_total * target_untung / 100
        kartu(t("ki_untung_bersih"), format_angka(untung_bersih, 0), t("ki_setelah_biaya"), "naik")

    st.markdown(
        f'<div class="catatan">{prosa("kal_impas_catatan").format(total=f"{biaya_beli + biaya_jual:.2f}")}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — PERINGATAN HARGA
# ──────────────────────────────────────────────────────────────────────

def halaman_peringatan():
    st.subheader(t("j_peringatan"))
    st.markdown(
        f'<div class="catatan">{t("a_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    daftar = st.session_state.peringatan

    with st.expander(t("a_pasang"), expanded=not daftar):
        a, b, c, d = st.columns([2, 1.2, 1.2, 1])
        with a:
            simbol = st.text_input(t("k_simbol"), placeholder="AAPL, NVDA, BTC-USD",
                                   key="alert_simbol")
        with b:
            arah = st.selectbox(t("a_kondisi"), ["Naik ke atas", "Turun ke bawah"],
                                format_func=lambda x: t("a_naik_ke") if x == "Naik ke atas" else t("a_turun_ke"))
        with c:
            batas = st.number_input(t("a_batas"), min_value=0.0, value=0.0, step=1.0,
                                    format="%.4f")
        with d:
            st.write("")
            st.write("")
            if st.button(t("a_tombol"), use_container_width=True, key="pasang_alert"):
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
                    st.warning(t("a_isi_dulu"))

        if daftar:
            label = [f'{p["simbol"]} {"≥" if p["arah"] == "atas" else "≤"} '
                     f'{format_angka(p["batas"])}' for p in daftar]
            buang = st.multiselect(t("b_hapus"), list(range(len(daftar))),
                                   format_func=lambda i: label[i],
                                   placeholder="Pilih yang mau dihapus")
            if buang and st.button(t("b_hapus"), key="hapus_alert"):
                st.session_state.peringatan = [p for i, p in enumerate(daftar)
                                               if i not in buang]
                simpan_json(BERKAS_PERINGATAN, st.session_state.peringatan)
                st.rerun()

    if not daftar:
        st.info(t("a_belum"))
        return

    df = ambil_kutipan(tuple(sorted({p["simbol"] for p in daftar})))
    if df.empty:
        st.warning(t("w_harga_gagal"))
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
        kartu(t("a_tersentuh"), str(len(kena)), t("a_sudah_lewat"),
              "naik" if kena else "diam")
    with k[1]:
        kartu(t("a_menunggu"), str(len(menunggu)), t("a_belum_capai"))
    with k[2]:
        kartu(t("a_gagal_baca"), str(len(gagal)), t("a_bermasalah") if gagal else "")

    if kena:
        st.write("")
        st.markdown(f'**{t("a_sudah_kena")}**')
        for p in kena:
            tanda = "≥" if p["arah"] == "atas" else "≤"
            st.markdown(
                f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<span style="color:var(--terang);font-weight:600;">{p["simbol"]}</span>'
                f'<span style="color:var(--aksen);font-size:0.78rem;">{t("a_tercapai")}</span></div>'
                f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.25rem;">'
                f'{t("a_harga_kini")} <b>{format_angka(p["harga"])}</b>, '
                f'{t("a_batas_kata")} {tanda} {format_angka(p["batas"])} '
                f'<span class="{warna(p["jarak"])}">({p["jarak"]:+.2f}%)</span></div>'
                f'<div style="color:var(--teks4);font-size:0.68rem;margin-top:0.2rem;">'
                f'{t("a_dipasang")} {p["dipasang"]}</div></div>',
                unsafe_allow_html=True,
            )

    if menunggu:
        st.write("")
        st.markdown(f'**{t("a_masih_tunggu")}**')
        st.dataframe(pd.DataFrame({
            t("k_simbol"): [p["simbol"] for p in menunggu],
            t("a_kondisi"): ["≥" if p["arah"] == "atas" else "≤" for p in menunggu],
            t("a_batas"): [format_angka(p["batas"]) for p in menunggu],
            t("a_harga_kini"): [format_angka(p["harga"]) for p in menunggu],
            t("a_jarak"): [f'{p["jarak"]:+.2f}%' for p in menunggu],
            t("a_dipasang"): [p["dipasang"] for p in menunggu],
        }), use_container_width=True, hide_index=True)

    if gagal:
        st.warning(t("a_tak_terbaca") + " " + ", ".join(p["simbol"] for p in gagal))


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — JURNAL TRANSAKSI
# ──────────────────────────────────────────────────────────────────────

def halaman_jurnal():
    st.subheader(t("j_jurnal"))
    st.markdown(
        f'<div class="catatan">{prosa("jurnal_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    jurnal = st.session_state.jurnal
    t_catat, t_riwayat, t_statistik = st.tabs([t("t_catat"), t("t_riwayat"), t("t_statistik")])

    with t_catat:
        a, b, c = st.columns(3)
        with a:
            simbol = st.text_input(t("k_simbol"), placeholder="AAPL", key="j_simbol")
            aksi = st.selectbox(t("j_aksi"), ["Beli", "Jual"], key="j_aksi",
                                format_func=lambda x: t("j_beli") if x == "Beli" else t("j_jual"))
        with b:
            jumlah = st.number_input(t("j_jumlah"), min_value=0.0, value=0.0,
                                     step=100.0, key="j_jumlah")
            harga = st.number_input(t("k_harga"), min_value=0.0, value=0.0, step=1.0,
                                    format="%.4f", key="j_harga")
        with c:
            tanggal = st.date_input(t("j_tanggal"), value=datetime.now(), key="j_tanggal")
            emosi = st.selectbox(t("j_emosi"),
                                 ["Tenang", "Ragu", "Takut ketinggalan", "Panik",
                                  "Percaya diri", "Terpaksa"], key="j_emosi",
                                 format_func=lambda x: t({"Tenang": "em_tenang", "Ragu": "em_ragu",
                                     "Takut ketinggalan": "em_fomo", "Panik": "em_panik",
                                     "Percaya diri": "em_yakin", "Terpaksa": "em_terpaksa"}[x]))

        alasan = st.text_area(t("j_alasan_label"),
                              placeholder=t("j_contoh_alasan"),
                              key="j_alasan", height=100)

        if st.button(t("j_simpan"), key="j_simpan"):
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
                st.success(t("j_tercatat"))
                st.rerun()
            else:
                st.warning(t("j_isi_dulu"))

    with t_riwayat:
        if not jurnal:
            st.info(t("j_belum_catatan"))
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
            buang = st.multiselect(t("j_hapus"), list(range(len(jurnal))),
                                   format_func=lambda i: label[i],
                                   placeholder=t("pf_pilih_hapus"))
            if buang and st.button(t("b_hapus"), key="hapus_jurnal"):
                st.session_state.jurnal = [c for i, c in enumerate(jurnal) if i not in buang]
                simpan_json(BERKAS_JURNAL, st.session_state.jurnal)
                st.rerun()

            st.download_button(
                t("j_unduh"),
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
        st.info(t("j_belum_analisis"))
        return

    df = pasangkan_transaksi(jurnal)
    if df.empty:
        st.info(t("j_belum_tutup"))
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
        t("k_simbol"): df["Simbol"],
        t("k_masuk"): df["Masuk"],
        t("k_keluar"): df["Keluar"],
        t("k_jumlah"): df["Jumlah"].map(lambda x: f"{x:,.0f}"),
        t("k_harga_beli"): df["Harga beli"].map(format_angka),
        t("k_harga_jual"): df["Harga jual"].map(format_angka),
        t("k_laba"): df["Laba"].map(lambda x: f"{x:+,.0f}"),
        t("k_persen"): df["Persen"].map(lambda x: f"{x:+.2f}%"),
        t("k_suasana"): df["Emosi beli"],
    }), use_container_width=True, hide_index=True)

    st.markdown(
        f'<div class="catatan">{prosa("jurnal_catatan")}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN — DOMPET KRIPTO
# ──────────────────────────────────────────────────────────────────────

def halaman_dompet():
    st.subheader(t("j_dompet"))
    st.markdown(
        '<div class="kartu" style="border-left:2px solid var(--naik);">'
        f'<div class="label">{t("d_hanya_baca")}</div>'
        '<div style="color:var(--teks2);font-size:0.8rem;line-height:1.7;margin-top:0.3rem;">'
        f'{t("d_hanya_baca_teks")}</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")

    dompet = st.session_state.dompet

    with st.expander(t("d_tambah_hapus"), expanded=not dompet):
        a, b, c = st.columns([1, 3, 1])
        with a:
            jaringan = st.selectbox(t("d_jaringan"), list(JARINGAN))
        with b:
            alamat = st.text_input(t("d_alamat"),
                                   placeholder=JARINGAN[jaringan]["contoh"])
        with c:
            st.write("")
            st.write("")
            if st.button(t("b_tambah"), use_container_width=True, key="tambah_dompet"):
                alamat = alamat.strip()
                if not alamat:
                    st.warning(t("d_kosong"))
                elif not alamat_sah(jaringan, alamat):
                    st.error(f'{t("d_tak_sah")} {JARINGAN[jaringan]["contoh"]}')
                elif any(d["alamat"] == alamat for d in dompet):
                    st.warning(t("d_kembar"))
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
            if buang and st.button(t("b_hapus"), key="hapus_dompet"):
                st.session_state.dompet = [d for i, d in enumerate(dompet) if i not in buang]
                simpan_json(BERKAS_DOMPET, st.session_state.dompet)
                st.rerun()

    if not dompet:
        st.info(t("d_belum_ada"))
        return

    if st.button(t("d_muat_saldo")):
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
        nilai_token = sum(x["nilai_usd"] for x in hasil.get("token", []))
        total_usd += usd + nilai_token
        baris.append({**d, **hasil, "usd": usd, "idr": idr,
                      "ubah": float(h.get("usd_24h_change", 0) or 0),
                      "nilai_token": nilai_token})

    sah = [b for b in baris if "galat" not in b]
    if sah:
        k = st.columns(3)
        with k[0]:
            kartu(t("d_total"), format_ringkas(total_usd), f'{len(sah)} {t("d_terbaca")}')
        with k[1]:
            total_idr = sum(b["idr"] for b in sah) + 0
            kartu("SETARA RUPIAH", "Rp " + format_angka(total_idr, 0),
                  "kurs dari CoinGecko")
        with k[2]:
            jml_token = sum(len(b.get("token", [])) for b in sah)
            kartu(t("d_token_terdeteksi"), f"{jml_token}", t("d_diluar_koin"))
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
               f'{b["transaksi"]:,} {t("d_transaksi")}</div>' if b.get("transaksi") else '')
            + '</div>',
            unsafe_allow_html=True,
        )

        if b.get("token"):
            with st.expander(f'{len(b["token"])} {t("d_token_di")}'):
                st.dataframe(pd.DataFrame({
                    t("k_token"): [x["kode"] for x in b["token"]],
                    t("k_nama"): [x["nama"] for x in b["token"]],
                    t("k_jumlah"): [f'{x["jumlah"]:,.4f}' for x in b["token"]],
                    t("k_nilai_kolom"): [format_ringkas(x["nilai_usd"]) for x in b["token"]],
                }), use_container_width=True, hide_index=True)
                st.markdown(
                    f'<div class="catatan">{t("d_token_sampah")}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown(
        '<div class="catatan" style="margin-top:0.8rem;">'
        f'{t("d_sumber")}</div>',
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

    menang = sum(1 for x in transaksi if x["hasil"] > 0)
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
    st.subheader(t("j_backtest"))
    st.markdown(
        f'<div class="catatan">{t("bt_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    jenis = st.radio(t("bt_jenis"), ["Saham & Kripto", "Forex"],
                     horizontal=True, key="bt_jenis",
                     format_func=lambda x: t("bt_saham_kripto") if x == "Saham & Kripto" else x)
    forex = jenis == "Forex"

    a, b, c, d = st.columns([2, 1, 1, 1.2])
    with a:
        if forex:
            pilihan = list(FOREX_SEMUA)
            simbol = st.selectbox(t("bt_pasangan"), pilihan, key="bt_simbol_fx",
                                  format_func=lambda x: FOREX_SEMUA.get(x, x))
        else:
            pilihan = list(dict.fromkeys(
                (st.session_state.watchlist or []) + ["BBCA.JK", "TLKM.JK", "AAPL", "BTC-USD"]))
            simbol = st.selectbox(t("k_simbol"), pilihan, key="bt_simbol")
    with b:
        nama_interval = st.selectbox(t("bt_rentang"), list(INTERVAL_BACKTEST),
                                     index=2, key="bt_interval")
    with c:
        aturan = INTERVAL_BACKTEST[nama_interval]
        periode = st.selectbox(t("bt_lama"), aturan["periode"],
                               index=len(aturan["periode"]) - 1, key=f"bt_p_{nama_interval}")
    with d:
        strategi = st.selectbox(
            t("bt_strategi"),
            ["Perpotongan Rata-rata", "RSI", "Di Atas Rata-rata", "Beli dan Tahan"],
            format_func=lambda x: t({"Perpotongan Rata-rata": "st_ma_silang", "RSI": "st_rsi",
                                     "Di Atas Rata-rata": "st_atas_ma",
                                     "Beli dan Tahan": "st_beli_tahan"}[x]))

    interval = aturan["kode"]
    if aturan["catatan"]:
        st.markdown(f'<div class="catatan">{aturan["catatan"]}</div>',
                    unsafe_allow_html=True)

    p = {}
    k1, k2, k3 = st.columns(3)
    if strategi == "Perpotongan Rata-rata":
        with k1:
            p["cepat"] = st.number_input(t("bt_ma_cepat"), 2, 100, 20)
        with k2:
            p["lambat"] = st.number_input(t("bt_ma_lambat"), 5, 300, 50)
        if p["cepat"] >= p["lambat"]:
            st.warning(t("w_ma_urutan"))
            return
    elif strategi == "RSI":
        with k1:
            p["periode"] = st.number_input(t("bt_rsi_periode"), 2, 50, 14)
        with k2:
            p["beli"] = st.number_input(t("bt_rsi_beli"), 5, 50, 30)
        with k3:
            p["jual"] = st.number_input(t("bt_rsi_jual"), 50, 95, 70)
    elif strategi == "Di Atas Rata-rata":
        with k1:
            p["periode"] = st.number_input(t("bt_ma_periode"), 5, 300, 200)

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
        modal = st.number_input(t("bt_modal"), min_value=0.0, value=10_000_000.0,
                                step=1_000_000.0, format="%.0f")
    with d2:
        if forex:
            pip = ukuran_pip(simbol, harga_kini)
            spread_pip = st.number_input(
                t("bt_spread"), min_value=0.0, value=SPREAD_KHAS.get(simbol, 2.0),
                step=0.1, format="%.1f",
                help=t("bt_spread_bantuan"))
            # Spread dibayar sekali per putaran (masuk + keluar). Mesin backtest
            # memungut biaya di tiap perubahan posisi, jadi separuhnya per perubahan.
            biaya = (spread_pip * pip / harga_kini * 100) / 2 if harga_kini else 0.0
            st.markdown(
                f'<div class="catatan">1 pip = {pip:g} · spread {spread_pip:g} pip setara '
                f'<b>{spread_pip * pip / harga_kini * 100:.4f}%</b> per putaran pada harga '
                f'{format_angka(harga_kini, 4)}</div>',
                unsafe_allow_html=True)
        else:
            biaya = st.number_input(t("bt_biaya"), min_value=0.0,
                                    value=BIAYA_BELI, step=0.05, format="%.3f",
                                    help="Dipungut setiap kali masuk dan keluar posisi.")

    if forex:
        st.markdown(
            '<div class="kartu" style="border-left:2px solid var(--turun);">'
            f'<div class="kartu" style="border-left:2px solid var(--turun);">'
            f'<div class="label">{t("bt_forex_abai")}</div>'
            f'<div style="color:var(--teks2);font-size:0.8rem;line-height:1.75;'
            f'margin-top:0.3rem;">{prosa("forex_diabaikan")}</div></div>',
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
        f'<div class="label">{t("bt_hasil")} — '
        f'{t({"Perpotongan Rata-rata": "st_ma_silang", "RSI": "st_rsi", "Di Atas Rata-rata": "st_atas_ma", "Beli dan Tahan": "st_beli_tahan"}[strategi]).upper()} · {simbol} '
        f'· {nama_interval.upper()} · {h["batang"]:,} {t("bt_batang")}</div>'
        f'<div style="font-size:1.9rem;font-weight:700;color:{warna_utama};'
        f'margin:0.3rem 0 0.1rem;">{selisih:+,.0f}</div>'
        f'<div style="color:var(--teks2);font-size:0.84rem;margin-bottom:0.9rem;">'
        f'{t("bt_lebih_banyak") if lebih_baik else t("bt_lebih_sedikit")} '
        f'{t("bt_dibanding")} {h["tahun"]:.1f} {t("bt_tahun")}</div>'

        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.35rem;">'
        f'<span style="width:120px;font-size:0.72rem;color:var(--teks3);">{t("bt_strategi").upper()}</span>'
        f'<div style="flex:1;background:var(--kisi);height:16px;border-radius:2px;'
        f'overflow:hidden;"><div style="width:{lebar_s:.1f}%;height:100%;'
        f'background:{pal()["naik"] if hasil_s >= 0 else pal()["turun"]};"></div></div>'
        f'<span style="width:92px;text-align:right;font-size:0.82rem;font-weight:600;'
        f'color:{pal()["naik"] if hasil_s >= 0 else pal()["turun"]};">{hasil_s:+.1f}%</span></div>'

        f'<div style="display:flex;align-items:center;gap:0.6rem;">'
        f'<span style="width:120px;font-size:0.72rem;color:var(--teks3);">{t("bt_beli_tahan").upper()}</span>'
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
        kartu(t("bt_modal_akhir"), format_angka(h["akhir"], 0),
              f'{t("bt_dari")} {format_angka(modal, 0)}', warna(h["akhir"] - modal))
    with k[1]:
        kartu(t("bt_per_tahun"), f'{h["cagr"]:.2f}%' if not math.isnan(h["cagr"]) else "—",
              f'{t("bt_pasar")} {h["cagr_pasar"]:.2f}%' if not math.isnan(h["cagr_pasar"]) else "",
              "naik" if lebih_baik else "turun")
    with k[2]:
        kartu(t("bt_penurunan"), f'{h["penurunan"]:.1f}%',
              f'{t("bt_pasar")} {h["penurunan_pasar"]:.1f}%', "turun")
    with k[3]:
        kartu(t("bt_sharpe"), format_angka(h["sharpe"], 2), t("bt_makin_tinggi"))

    k = st.columns(4)
    with k[0]:
        kartu(t("bt_jml_transaksi"), f'{h["transaksi"]:,}',
              f'{h["transaksi"] / h["tahun"]:.1f} {t("bt_per_tahun2")}' if h["tahun"] > 0 else "")
    with k[1]:
        menang = (h["menang"] / h["total_tutup"] * 100) if h["total_tutup"] else float("nan")
        kartu(t("bt_untung"), f"{menang:.0f}%" if not math.isnan(menang) else "—",
              f'{h["menang"]} {t("bt_dari2")} {h["total_tutup"]}',
              "naik" if not math.isnan(menang) and menang >= 50 else "turun")
    with k[2]:
        kartu(t("bt_waktu_pasar"), f'{h["waktu_di_pasar"]:.0f}%', t("bt_sisanya_tunai"))
    with k[3]:
        tr = h["daftar_transaksi"]
        rerata = sum(x["hari"] for x in tr) / len(tr) if tr else float("nan")
        if not math.isnan(rerata) and rerata < 1:
            jam = sum((x["keluar"] - x["masuk"]).total_seconds() / 3600
                      for x in tr) / len(tr)
            teks = f'{jam:.1f} {t("bt_jam")}'
        else:
            teks = f'{rerata:.0f} {t("bt_hari")}' if not math.isnan(rerata) else "—"
        kartu(t("bt_ditahan"), teks, t("bt_per_transaksi"))

    # ── Kurva modal + kurva penurunan ─────────────────────────────────
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.68, 0.32],
                        subplot_titles=(t("bt_pertumbuhan"), t("bt_jarak_puncak")))

    nama_strategi = t({"Perpotongan Rata-rata": "st_ma_silang", "RSI": "st_rsi",
                       "Di Atas Rata-rata": "st_atas_ma",
                       "Beli dan Tahan": "st_beli_tahan"}[strategi])
    fig.add_trace(go.Scatter(x=h["kurva"].index, y=h["kurva"], name=nama_strategi,
                             line=dict(color=pal()["aksen"], width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=h["kurva_pasar"].index, y=h["kurva_pasar"],
                             name=t("st_beli_tahan"),
                             line=dict(color=pal()["biru"], width=1.4, dash="dot")),
                  row=1, col=1)
    fig.add_hline(y=modal, line=dict(color=pal()["kisi2"], width=1), row=1, col=1)

    fig.add_trace(go.Scatter(x=h["penurunan_seri"].index, y=h["penurunan_seri"],
                             name=t("bt_kurva_turun"), fill="tozeroy",
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
    fig2.add_trace(go.Scatter(x=h["harga"].index, y=h["harga"], name=t("k_harga"),
                              line=dict(color=pal()["teks3"], width=1.2)))
    for x in h["daftar_transaksi"]:
        fig2.add_vrect(x0=x["masuk"], x1=x["keluar"], line_width=0,
                       fillcolor=pal()["naik"] if x["hasil"] > 0 else pal()["turun"],
                       opacity=0.13, layer="below")
    if h["posisi_terbuka"]:
        pt = h["posisi_terbuka"]
        fig2.add_vrect(x0=pt["masuk"], x1=pt["keluar"], line_width=0,
                       fillcolor=pal()["aksen"], opacity=0.13, layer="below")
    if h["daftar_transaksi"]:
        fig2.add_trace(go.Scatter(
            x=[x["masuk"] for x in h["daftar_transaksi"]],
            y=[x["harga_masuk"] for x in h["daftar_transaksi"]],
            mode="markers", name=t("bt_masuk"),
            marker=dict(symbol="triangle-up", size=9, color=pal()["naik"])))
        fig2.add_trace(go.Scatter(
            x=[x["keluar"] for x in h["daftar_transaksi"]],
            y=[x["harga_keluar"] for x in h["daftar_transaksi"]],
            mode="markers", name=t("bt_keluar"),
            marker=dict(symbol="triangle-down", size=9, color=pal()["turun"])))
    fig2.update_layout(
        height=320, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text=t("bt_kapan_pegang"),
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
                z=tabel.values, x=NAMA_BULAN, y=[str(x) for x in tabel.index],
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
                title=dict(text=t("bt_per_bulan"),
                           font=dict(size=12, color=pal()["aksen"])),
                font=dict(family="Consolas, monospace", size=10, color=pal()["teks2"]))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info(t("bt_terlalu_pendek"))

    with kanan:
        tr = h["daftar_transaksi"]
        if len(tr) >= 3:
            hasil_tr = [x["hasil"] for x in tr]
            fig4 = go.Figure(go.Histogram(
                x=hasil_tr, nbinsx=min(24, max(6, len(hasil_tr) // 2)),
                marker=dict(color=pal()["aksen"], line=dict(color=pal()["latar"], width=1))))
            fig4.add_vline(x=0, line=dict(color=pal()["kisi2"], width=1.4))
            rerata = sum(hasil_tr) / len(hasil_tr)
            fig4.add_vline(x=rerata, line=dict(color=pal()["biru"], width=1.4, dash="dash"),
                           annotation_text=f'{t("bt_rata_rata")} {rerata:+.1f}%',
                           annotation_font=dict(size=9, color=pal()["biru"]))
            fig4.update_layout(
                height=max(220, 46 * max(1, len(h["bulanan"].index.year.unique())) + 90),
                template=pal()["plotly"],
                paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
                margin=dict(l=10, r=10, t=40, b=10),
                title=dict(text=t("bt_sebaran"),
                           font=dict(size=12, color=pal()["aksen"])),
                bargap=0.05,
                font=dict(family="Consolas, monospace", size=10, color=pal()["teks2"]))
            fig4.update_xaxes(gridcolor=pal()["kisi"], ticksuffix="%")
            fig4.update_yaxes(gridcolor=pal()["kisi"])
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info(t("bt_terlalu_sedikit"))

    # ── Daftar transaksi ──────────────────────────────────────────────
    if h["daftar_transaksi"]:
        with st.expander(f'{t("bt_rincian")} {len(h["daftar_transaksi"])} {t("bt_transaksi")}'):
            tr = h["daftar_transaksi"]
            st.dataframe(pd.DataFrame({
                t("bt_kol_masuk"): [f'{x["masuk"]:%d %b %Y}' for x in tr],
                t("bt_kol_keluar"): [f'{x["keluar"]:%d %b %Y}' for x in tr],
                t("bt_kol_hari"): [x["hari"] for x in tr],
                t("bt_kol_hmasuk"): [format_angka(x["harga_masuk"]) for x in tr],
                t("bt_kol_hkeluar"): [format_angka(x["harga_keluar"]) for x in tr],
                t("bt_kol_hasil"): [f'{x["hasil"]:+.2f}%' for x in tr],
            }), use_container_width=True, hide_index=True, height=340)

    if lebih_baik:
        putusan = (f'{t("bt_unggul")} <b class="naik">{selisih:+,.0f}</b> '
                   f'{t("bt_selama")} {h["tahun"]:.1f} {t("bt_tahun")}.')
    else:
        putusan = f'{t("bt_kalah")} {selisih:+,.0f}.'
    st.markdown(f'<div class="catatan">{putusan}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="catatan" style="margin-top:0.8rem;">'
        f'{prosa("backtest_jujur")}</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 3 — BERITA & MAKRO
# ──────────────────────────────────────────────────────────────────────

def halaman_berita():
    st.subheader(t("j_berita"))

    tab_berita, tab_makro, tab_lindung = st.tabs(
        [t("t_kabel_berita"), t("t_indikator_ek"), t("t_lindung_nilai")])

    with tab_berita:
        a, b = st.columns([3, 1])
        with a:
            lingkup = st.radio("Lingkup", ["Global", "Indonesia", "Semua"],
                               horizontal=True, label_visibility="collapsed",
                               format_func=lambda x: {"Global": t("n_global"),
                                                      "Indonesia": t("n_indonesia"),
                                                      "Semua": t("n_semua")}[x])
        with b:
            if st.button(t("b_segarkan"), use_container_width=True):
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
            st.warning(t("w_berita_gagal"))
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
        st.markdown(f'**{t("n_potret")}**')
        df_makro = ambil_kutipan(tuple(MAKRO_PANTAU))
        kolom = st.columns(len(MAKRO_PANTAU))
        for k, (simbol, nama) in zip(kolom, MAKRO_PANTAU.items()):
            # Nilai MAKRO_PANTAU bisa berupa kunci terjemahan atau label apa adanya.
            label_makro = t(nama) if nama.startswith("mk_") else nama
            with k:
                baris = df_makro[df_makro["Simbol"] == simbol] if not df_makro.empty else pd.DataFrame()
                if baris.empty:
                    kartu(label_makro, "—", t("kr_tak_ada"))
                else:
                    r = baris.iloc[0]
                    kartu(label_makro, format_angka(r["Harga"]), f'{r["Persen"]:+.2f}%', warna(r["Persen"]))

        st.divider()
        st.markdown(f'**{t("n_jangka_panjang")}**')

        a, b = st.columns(2)
        with a:
            negara = st.selectbox(t("n_negara"), list(NEGARA),
                                  index=list(NEGARA).index("USA"),
                                  format_func=lambda k: t(NEGARA[k]))
        with b:
            indikator = st.selectbox(t("n_indikator"), list(INDIKATOR_BANK_DUNIA),
                                     format_func=lambda k: t(INDIKATOR_BANK_DUNIA[k]))

        df_wb = ambil_bank_dunia(negara, indikator)
        if df_wb.empty:
            st.info(t("w_tak_tersedia"))
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
                title=dict(text=f"{t(NEGARA[negara])} — {t(INDIKATOR_BANK_DUNIA[indikator])}",
                           font=dict(size=13, color=pal()["aksen"])),
                font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
            )
            fig.update_xaxes(gridcolor=pal()["kisi"])
            fig.update_yaxes(gridcolor=pal()["kisi"])
            st.plotly_chart(fig, use_container_width=True)

            terbaru = df_wb.iloc[-1]
            st.markdown(
                f'<div class="catatan">{t("n_terbaru")}: <b>{terbaru["Nilai"]:.2f}</b> '
                f'{t("n_pada_tahun")} {int(terbaru["Tahun"])}. '
                f'{t("n_tertinggal")}</div>',
                unsafe_allow_html=True,
            )

    with tab_lindung:
        bagian_emas_lindung()


# ──────────────────────────────────────────────────────────────────────
#  HALAMAN 4 — PORTOFOLIO
# ──────────────────────────────────────────────────────────────────────

def bagian_emas_lindung():
    """Menguji klaim bahwa emas melindungi nilai — dengan angka, bukan keyakinan."""
    st.markdown(f'**{t("lp_judul")}**')
    st.markdown(f'<div class="catatan">{prosa("lindung_pembuka")}</div>',
                unsafe_allow_html=True)

    a, _ = st.columns([1, 3])
    with a:
        periode = st.selectbox(t("g_periode"), ["2y", "5y", "10y", "max"],
                               index=1, key="periode_lindung")

    emas = ambil_emas_riwayat(periode)
    if emas.empty:
        st.info(t("w_tak_tersedia"))
        return

    ihsg = _seri_harian(ambil_riwayat("^JKSE", periode, "1d"))
    kurs = emas["kurs"]

    # Semua disetarakan ke 100 pada hari pertama yang sama-sama punya data,
    # supaya yang dibandingkan pergerakannya, bukan besaran angkanya.
    kumpul = {t("lp_emas_rupiah"): emas["idr_gram"], t("lp_kurs"): kurs}
    if not ihsg.empty:
        kumpul[t("lp_ihsg")] = ihsg
    gabung = pd.concat(kumpul, axis=1).sort_index().ffill().dropna()
    if gabung.empty or len(gabung) < 30:
        st.info(t("w_tak_tersedia"))
        return
    indeks = gabung / gabung.iloc[0] * 100

    warna_garis = [pal()["aksen"], pal()["turun"], pal()["biru"]]
    fig = go.Figure()
    for i, kol in enumerate(indeks.columns):
        fig.add_trace(go.Scatter(x=indeks.index, y=indeks[kol], name=kol,
                                 line=dict(color=warna_garis[i % len(warna_garis)],
                                           width=2 if i == 0 else 1.4,
                                           dash=None if i == 0 else "dot")))
    fig.add_hline(y=100, line=dict(color=pal()["kisi2"], width=1))
    fig.update_layout(
        height=420, template=pal()["plotly"],
        paper_bgcolor=pal()["latar"], plot_bgcolor=pal()["panel2"],
        margin=dict(l=10, r=10, t=44, b=10),
        legend=dict(orientation="h", y=1.11, x=0, font=dict(size=10)),
        title=dict(text=t("lp_judul_grafik"), font=dict(size=13, color=pal()["aksen"]), x=0),
        font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
    )
    fig.update_xaxes(gridcolor=pal()["kisi"])
    fig.update_yaxes(gridcolor=pal()["kisi"])
    st.plotly_chart(fig, use_container_width=True)

    # ── Imbal hasil per jangka waktu ──────────────────────────────────
    st.markdown(f'**{t("lp_tabel")}**')
    lengkap = pd.concat({t("lp_emas_rupiah"): emas["idr_gram"],
                         t("lp_emas_dolar"): emas["usd_gram"],
                         t("lp_kurs"): kurs,
                         **({t("lp_ihsg"): ihsg} if not ihsg.empty else {})},
                        axis=1).sort_index().ffill().dropna()

    jangka = [(1, "1"), (3, "3"), (5, "5"), (10, "10")]
    baris = {t("n_indikator"): list(lengkap.columns)}
    for tahun, label in jangka:
        mulai = lengkap.index[-1] - pd.Timedelta(days=int(365.25 * tahun))
        potong = lengkap[lengkap.index >= mulai]
        cukup = len(potong) > 20 and potong.index[0] <= mulai + pd.Timedelta(days=45)
        kolom = f'{label}{t("lp_singkat_tahun")}'
        if not cukup:
            baris[kolom] = ["—"] * len(lengkap.columns)
            continue
        total = potong.iloc[-1] / potong.iloc[0] - 1
        per_tahun = (1 + total) ** (1 / tahun) - 1
        baris[kolom] = [f"{v * 100:+.1f}%" for v in per_tahun]

    st.dataframe(pd.DataFrame(baris), use_container_width=True, hide_index=True)
    st.markdown(f'<div class="catatan">{t("lp_per_tahun_ket")}</div>',
                unsafe_allow_html=True)

    # ── Emas dibanding inflasi ────────────────────────────────────────
    inflasi = ambil_bank_dunia("IDN", "FP.CPI.TOTL.ZG")
    if not inflasi.empty and len(lengkap) > 200:
        tahun_uji = 10
        mulai = lengkap.index[-1] - pd.Timedelta(days=int(365.25 * tahun_uji))
        potong = lengkap[lengkap.index >= mulai]
        if len(potong) > 200:
            emas_th = ((potong[t("lp_emas_rupiah")].iloc[-1] /
                        potong[t("lp_emas_rupiah")].iloc[0]) ** (1 / tahun_uji) - 1) * 100
            inf = inflasi[inflasi["Tahun"] >= inflasi["Tahun"].max() - tahun_uji]
            inf_rata = float(inf["Nilai"].mean())
            lebih = emas_th - inf_rata
            st.markdown(
                f'<div class="catatan">{t("lp_inflasi_kalimat")} '
                f'<b class="{warna(emas_th)}">{emas_th:+.1f}%</b> {t("lp_inflasi_vs")} '
                f'<b>{inf_rata:.1f}%</b> — {t("lp_inflasi_selisih")} '
                f'<b class="{warna(lebih)}">{lebih:+.1f}%</b> {t("lp_inflasi_titik")}</div>',
                unsafe_allow_html=True,
            )

    st.markdown(f'<div class="catatan">{prosa("lindung_penutup")}</div>',
                unsafe_allow_html=True)


def halaman_portofolio():
    st.subheader(t("j_portofolio"))

    posisi = st.session_state.portofolio

    with st.expander(t("pf_tambah"), expanded=not posisi):
        a, b, c, d = st.columns([2, 1, 1.2, 1])
        with a:
            simbol = st.text_input(t("k_simbol"), placeholder="AAPL")
        with b:
            jumlah = st.number_input(t("k_jumlah"), min_value=0.0, step=1.0, format="%.4f")
        with c:
            harga_beli = st.number_input(t("pf_harga_beli"), min_value=0.0,
                                         step=1.0, format="%.4f")
        with d:
            st.write("")
            st.write("")
            if st.button(t("b_simpan"), use_container_width=True):
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
                    st.warning(t("pf_isi_dulu"))

        if posisi:
            label = [f'{p["simbol"]} — {p["jumlah"]:g} @ {p["harga_beli"]:,.2f}' for p in posisi]
            buang = st.multiselect(t("pf_hapus_posisi"), list(range(len(posisi))),
                                   format_func=lambda i: label[i],
                                   placeholder=t("pf_pilih_hapus"))
            if buang and st.button(t("pf_hapus_terpilih")):
                st.session_state.portofolio = [p for i, p in enumerate(posisi) if i not in buang]
                simpan_json(BERKAS_PORTOFOLIO, st.session_state.portofolio)
                st.rerun()

    if not posisi:
        st.info(t("pf_belum"))
        return

    simbol_unik = tuple(sorted({p["simbol"] for p in posisi}))
    kutipan = ambil_kutipan(simbol_unik)
    if kutipan.empty:
        st.warning(t("w_pasar_gagal"))
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
        st.warning(t("pf_tak_terbaca"))
        return

    df = pd.DataFrame(baris)
    total_modal = float(df["Modal"].sum())
    total_nilai = float(df["Nilai kini"].sum())
    total_laba = total_nilai - total_modal
    total_persen = (total_laba / total_modal * 100) if total_modal else 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kartu(t("pf_total_modal"), format_angka(total_modal))
    with k2:
        kartu(t("pf_nilai_kini"), format_angka(total_nilai))
    with k3:
        kartu(t("pf_laba_rugi"), f"{total_laba:+,.2f}", f"{total_persen:+.2f}%",
              warna(total_laba))
    with k4:
        kartu(t("pf_jml_posisi"), str(len(df)))

    st.markdown(f'**{t("pf_rincian")}**')
    tampil = pd.DataFrame({
        t("k_simbol"): df["Simbol"],
        t("k_jumlah"): df["Jumlah"].map(lambda x: f"{x:g}"),
        t("k_harga_beli"): df["Harga beli"].map(format_angka),
        t("pf_harga_kini"): df["Harga kini"].map(format_angka),
        t("pf_modal"): df["Modal"].map(format_angka),
        t("pf_nilai_kini"): df["Nilai kini"].map(format_angka),
        t("k_laba_rugi"): df["Laba/Rugi"].map(lambda x: f"{x:+,.2f}"),
        t("k_persen"): df["Persen"].map(lambda x: f"{x:+.2f}%"),
        t("pf_hari_ini"): df["Hari ini %"].map(lambda x: f"{x:+.2f}%"),
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
            title=dict(text=t("pf_alokasi"), font=dict(size=12, color=pal()["aksen"])),
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
            title=dict(text=t("pf_lr_posisi"), font=dict(size=12, color=pal()["aksen"])),
            font=dict(family="Consolas, monospace", size=11, color=pal()["teks2"]),
        )
        fig.update_xaxes(gridcolor=pal()["kisi"], zerolinecolor=pal()["kisi2"])
        fig.update_yaxes(gridcolor=pal()["kisi"])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="catatan">'
        f'{t("c_portofolio")}</div>',
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
    pdf.multi_cell(0, 4, _teks_pdf(t("pdf_kaki")))

    keluaran = pdf.output()
    return bytes(keluaran)


def halaman_laporan():
    st.subheader(t("j_laporan"))
    st.markdown(
        f'<div class="catatan">{prosa("laporan_intro")}</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    a, b = st.columns(2)
    with a:
        jenis = st.selectbox(
            t("r_isi"), ["Portofolio", "Jurnal Transaksi", "Dompet Kripto", "Watchlist"],
            format_func=lambda x: t({"Portofolio": "j_portofolio", "Jurnal Transaksi": "j_jurnal",
                                     "Dompet Kripto": "j_dompet", "Watchlist": "j_watchlist"}[x]))
    with b:
        penyusun = st.text_input(t("r_penyusun"), value=PROFIL["nama"])

    catatan = st.text_area(t("r_catatan"), placeholder=t("r_catatan_ph"), height=90)

    bagian = []
    if catatan.strip():
        bagian.append(("teks", catatan.strip()))

    subjudul = ""

    if jenis == "Portofolio":
        posisi = st.session_state.portofolio
        if not posisi:
            st.info(t("r_pf_kosong"))
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
            st.info(t("r_j_kosong"))
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
            st.info(t("r_d_kosong"))
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
            st.info(t("r_w_kosong"))
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
    if st.button(t("r_buat"), use_container_width=True):
        try:
            isi = buat_pdf(f"Laporan {jenis}", subjudul, bagian, penyusun or "-")
        except ImportError:
            st.error(t("pdf_fpdf_hilang"))
            return
        except Exception as e:
            st.error(f'{t("r_gagal")}: {e}')
            return

        st.success(f'{t("r_siap")} — {len(isi) / 1024:.0f} KB')
        st.download_button(
            t("r_unduh"),
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
    st.subheader(t("j_tentang"))
    tab_aplikasi, tab_pembuat, tab_versi = st.tabs([t("t_aplikasi"), t("t_pembuat"), t("t_pembaruan")])

    with tab_pembuat:
        bagian_pembuat()

    with tab_aplikasi:
        bagian_aplikasi()

    with tab_versi:
        bagian_pembaruan()


def bagian_pembaruan():
    a, b = st.columns([1, 1])
    with a:
        kartu(t("u_versi_terpasang"), VERSI, t("u_di_komputer"))
    with b:
        if st.button(t("u_periksa"), use_container_width=True, key="cek_versi"):
            cek_pembaruan.clear()
            st.rerun()

    otomatis = st.toggle(
        t("u_otomatis"),
        value=st.session_state.get("cek_otomatis", True),
        key="saklar_cek",
        help=t("u_otomatis_bantuan"))
    if otomatis != st.session_state.get("cek_otomatis", True):
        st.session_state.cek_otomatis = otomatis
        simpan_pengaturan()
        st.rerun()

    if not otomatis:
        st.markdown(
            f'<div class="catatan">{t("u_mati")}</div>',
            unsafe_allow_html=True,
        )
        if not st.session_state.get("periksa_manual"):
            if st.button(t("u_sekali"), key="manual_sekali"):
                st.session_state.periksa_manual = True
                st.rerun()
            st.divider()
            bagian_catatan_pembaruan()
            return

    manifes = cek_pembaruan(URL_RILIS)

    if manifes.get("galat"):
        st.markdown(
            f'<div class="kartu"><div class="label">{t("u_tak_bisa")}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.3rem;">'
            f'{manifes["galat"]}<br><br>{t("u_tak_bisa_teks")}</div></div>',
            unsafe_allow_html=True,
        )
    elif not manifes.get("lebih_baru"):
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--naik);">'
            f'<div class="label">{t("u_terbaru")}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;margin-top:0.3rem;">'
            f'{t("u_terbaru_teks")} ({manifes.get("versi")})</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="kartu" style="border-left:2px solid var(--aksen);">'
            f'<div class="label">{t("u_tersedia")}</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:var(--aksen);'
            f'margin:0.25rem 0;">{VERSI} → {manifes.get("versi")}</div>'
            f'<div style="color:var(--teks3);font-size:0.72rem;">'
            f'{t("u_dirilis")} {manifes.get("tanggal", "—")}</div>'
            f'<div style="color:var(--teks2);font-size:0.82rem;line-height:1.7;'
            f'margin-top:0.6rem;white-space:pre-line;">'
            f'{manifes.get("catatan") or t("u_tanpa_catatan")}</div></div>',
            unsafe_allow_html=True,
        )

        berkas = manifes.get("berkas", {})
        if berkas:
            st.dataframe(pd.DataFrame({
                t("u_berkas"): list(berkas),
                t("u_diizinkan"): [t("u_ya") if n in BERKAS_BOLEH_DIPERBARUI else t("u_tidak")
                              for n in berkas],
                t("u_sidik"): [str(i.get("sha256", ""))[:16] + "…"
                                         for i in berkas.values()],
            }), use_container_width=True, hide_index=True)

        setuju = st.checkbox(t("u_setuju"), key="setuju_perbarui")
        if st.button(t("u_pasang"), use_container_width=True,
                     disabled=not setuju, key="pasang_perbarui"):
            with st.spinner(t("u_mengunduh")):
                berhasil, pesan = terapkan_pembaruan(manifes)
            if berhasil:
                st.success(pesan)
                st.info(t("u_restart"))
            else:
                st.error(pesan)

    # ── Kembalikan versi sebelumnya ───────────────────────────────────
    cadangan = daftar_cadangan()
    if cadangan:
        st.divider()
        st.markdown(f'**{t("u_kembali")}**')
        pilih = st.selectbox(t("u_salinan"), cadangan,
                             format_func=lambda p: p.name, key="pilih_cadangan")
        if st.button(t("u_pulihkan"), key="pulihkan"):
            berhasil, pesan = kembalikan_cadangan(pilih)
            (st.success if berhasil else st.error)(pesan)
            if berhasil:
                st.info(t("u_restart2"))

    st.divider()
    bagian_catatan_pembaruan()


def bagian_catatan_pembaruan():
    inang = URL_RILIS.split("/")[2]
    st.markdown(
        f'<div class="catatan">'
        + prosa("catatan_pembaruan").replace("{INANG}", inang)
        .replace("**", "").replace("\n\n", "<br><br>").replace("\n", " ")
        + '</div>',
        unsafe_allow_html=True,
    )


def teks_profil(nilai):
    """Ambil bagian profil sesuai bahasa. Terima teks biasa maupun dict per bahasa."""
    if isinstance(nilai, dict):
        for kode in CADANGAN_BAHASA.get(st.session_state.get("bahasa", "en"), ("en", "id")):
            if nilai.get(kode):
                return nilai[kode]
        return next(iter(nilai.values()), "")
    return nilai


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
            for x in teks_profil(p["peran"])
        )
        st.markdown(
            f'<div style="padding-top:0.2rem;">'
            f'<div style="font-size:1.35rem;font-weight:700;color:var(--terang);">{p["nama"]}</div>'
            f'<div style="color:var(--aksen);font-size:0.92rem;font-style:italic;'
            f'margin:0.25rem 0 0.7rem 0;">{teks_profil(p["moto"])}</div>'
            f'<div>{lencana}</div>'
            f'<div style="color:var(--teks2);font-size:0.84rem;line-height:1.7;'
            f'margin-top:0.7rem;">{teks_profil(p["tentang"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(f'**{t("p_portofolio")}**')

    for i in range(0, len(p["proyek"]), 2):
        kolom = st.columns(2)
        for k, (nama, ket_bahasa, url) in zip(kolom, p["proyek"][i:i + 2]):
            ket = teks_profil(ket_bahasa)
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
    st.markdown(f'**{t("p_layanan")}**')
    kolom = st.columns(len(p["layanan"]))
    for k, (nama_bahasa, ket_bahasa) in zip(kolom, p["layanan"]):
        nama, ket = teks_profil(nama_bahasa), teks_profil(ket_bahasa)
        with k:
            st.markdown(
                f'<div class="kartu" style="min-height:110px;">'
                f'<div style="color:var(--terang);font-weight:600;font-size:0.82rem;">{nama}</div>'
                f'<div style="color:var(--diam);font-size:0.72rem;line-height:1.6;'
                f'margin-top:0.35rem;">{ket}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(f'**{t("p_aplikasi")}**')
    kolom = st.columns(len(p["aplikasi"]))
    for k, a in zip(kolom, p["aplikasi"]):
        with k:
            pautan = []
            if a["aplikasi"]:
                pautan.append(f'<a href="{a["aplikasi"]}" target="_blank" '
                              f'style="color:var(--aksen);text-decoration:none;">'
                              f'{t("p_buka_aplikasi")} ↗</a>')
            if a["kode"]:
                pautan.append(f'<a href="{a["kode"]}" target="_blank" '
                              f'style="color:var(--biru);text-decoration:none;">'
                              f'{t("p_kode_sumber")} ↗</a>')
            st.markdown(
                f'<div class="kartu" style="min-height:120px;">'
                f'<div style="color:var(--aksen);font-weight:600;font-size:0.88rem;">'
                f'{a["nama"]}</div>'
                f'<div style="color:var(--teks6);font-size:0.74rem;line-height:1.6;'
                f'margin-top:0.3rem;">{teks_profil(a["ket"])}</div>'
                f'<div style="margin-top:0.45rem;font-size:0.72rem;">'
                f'{" &nbsp;·&nbsp; ".join(pautan)}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(f'**{t("p_buku")}**')
    st.markdown(f'<div class="catatan">{t("c_buku")}</div>', unsafe_allow_html=True)
    st.write("")
    for i in range(0, len(p["buku"]), 3):
        kolom = st.columns(3)
        for k, b in zip(kolom, p["buku"][i:i + 3]):
            with k:
                tanda = (f'<span style="color:var(--naik);font-size:0.64rem;'
                         f'border:1px solid var(--naik);padding:0.02rem 0.3rem;'
                         f'border-radius:2px;margin-left:0.35rem;">'
                         f'{t("p_gratis")}</span>') if b["gratis"] else ""
                st.markdown(
                    f'<div class="kartu" style="min-height:132px;">'
                    f'<div style="color:var(--terang);font-weight:600;font-size:0.8rem;'
                    f'line-height:1.45;">{b["judul"]}{tanda}</div>'
                    f'<div style="color:var(--diam);font-size:0.72rem;line-height:1.55;'
                    f'margin-top:0.32rem;">{teks_profil(b["ket"])}</div>'
                    f'<div style="margin-top:0.45rem;"><a href="{b["url"]}" target="_blank" '
                    f'style="color:var(--aksen);font-size:0.72rem;text-decoration:none;">'
                    f'{b["toko"]} ↗</a></div></div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    kartu_donasi()

    st.divider()
    st.markdown(f'**{t("p_temukan")}**')
    tautan = " &nbsp;·&nbsp; ".join(
        f'<a href="{url}" target="_blank" style="color:var(--aksen);text-decoration:none;">{nama} ↗</a>'
        for nama, url in p["tautan"]
    )
    st.markdown(f'<div style="font-size:0.82rem;">{tautan}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="catatan" style="margin-top:1rem;">'
        f'{t("p_penutup")}'
        '</div>',
        unsafe_allow_html=True,
    )


def bagian_aplikasi():
    st.markdown(prosa("tentang_aplikasi"))


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
            f'{t("merek")}</div>'
            f'<div style="color:var(--teks4);font-size:0.7rem;letter-spacing:0.08em;">'
            f'{t("sub_merek")} · v{VERSI}</div></div>',
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
                f'<div class="label">{t("sb_versi_baru")}</div>'
                f'<div style="color:var(--aksen);font-weight:700;font-size:0.9rem;">'
                f'{info_versi.get("versi")}</div>'
                f'<div style="color:var(--teks4);font-size:0.66rem;">'
                f'{t("sb_buka_tentang")}</div></div>',
                unsafe_allow_html=True,
            )

        pilih_bahasa = st.selectbox(
            t("bahasa"), list(BAHASA),
            index=list(BAHASA).index(st.session_state.get("bahasa", "en")),
            format_func=lambda k: BAHASA[k]["_nama"], key="pilih_bahasa")
        if pilih_bahasa != st.session_state.get("bahasa", "en"):
            st.session_state.bahasa = pilih_bahasa
            simpan_pengaturan()
            st.rerun()

        gelap = st.session_state.tema == "gelap"
        if st.button(t("mode_terang") if gelap else t("mode_gelap"),
                     use_container_width=True, key="tukar_tema"):
            st.session_state.tema = "terang" if gelap else "gelap"
            simpan_pengaturan()
            st.rerun()
        halaman = st.radio(
            "Menu",
            ["Pasar", "Grafik", "Screener", "Fundamental", "Backtest",
             "Kalkulator", "Berita & Makro", "Portofolio", "Dompet Kripto",
             "Peringatan", "Jurnal", "Laporan", "Tentang"],
            format_func=lambda x: t(KUNCI_MENU[x]),
            label_visibility="collapsed",
            key="menu_utama",
        )
        st.divider()
        st.markdown(
            '<div class="catatan">'
            f'{len(st.session_state.watchlist)} {t("sb_simbol")}<br>'
            f'{len(st.session_state.portofolio)} {t("sb_posisi")}<br><br>'
            f'{t("sb_lokal")}<br><br>'
            f'{t("sb_dibuat")}<br><b style="color:var(--teks6);">{PROFIL["nama"]}</b><br>'
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
