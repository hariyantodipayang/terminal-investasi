# Terminal Ringan

Terminal data keuangan sederhana, berbahasa Indonesia, berjalan di komputer Anda sendiri.
**Tanpa kredit. Tanpa langganan. Tanpa API key.**

---

## Cara menjalankan

Klik dua kali **`MULAI.cmd`**.

Itu saja. Pertama kali dijalankan akan memakan waktu 2–3 menit karena berkas ini menyiapkan
lingkungan Python dan memasang pustaka yang dibutuhkan. Sesudah itu, tiap kali dibuka hanya
butuh beberapa detik. Browser akan terbuka sendiri di alamat `http://localhost:8501`.

Untuk berhenti: tutup jendela hitam yang muncul, atau tekan Ctrl+C di dalamnya.

**Syarat satu-satunya:** Python sudah terpasang di komputer. Anda sudah punya (Python 3.11,
3.13, dan 3.14 semuanya terdeteksi di komputer Anda), jadi tidak ada yang perlu dipasang lagi.

> **Catatan tentang OneDrive.** Folder ini ada di dalam OneDrive, jadi lingkungan Python
> sengaja diletakkan di luar — tepatnya di `%LOCALAPPDATA%\terminal-ringan-venv`. Isinya
> ribuan berkas kecil; kalau ditaruh di dalam OneDrive, sinkronisasi akan berjalan
> terus-menerus dan memberatkan komputer Anda.

---

## Apa isinya

**Pasar** — **Denyut Pasar** dengan empat tab:

- *Indeks Dunia* — enam indeks termasuk IHSG
- *Kripto* — kapitalisasi pasar sedunia, volume 24 jam, dominasi Bitcoin, indeks Takut &
  Serakah, plus tabel 12 koin terbesar
- *Komoditas & Kurs* — USD/IDR, emas, perak, minyak WTI, indeks dolar, obligasi AS 10 tahun
- *Saham Indonesia* — sembilan saham berkapitalisasi besar di Bursa Efek Indonesia

Tiap kartu punya garis tren 30 hari yang warnanya ikut arah harga. Di bawahnya ada
**Watchlist** berisi simbol pilihan Anda sendiri, bisa ditambah dan dihapus sesuka hati.

**Grafik & Analisa** — Dua tab.

*Grafik & Indikator*: candlestick dengan SMA 20/50/200, EMA 20, Bollinger Bands, RSI, MACD,
dan volume.

*Pembacaan Teknikal*: aplikasi membaca sendiri grafiknya. Garis tren digambar otomatis,
level sokongan dan penahan ditarik dari puncak-lembah sebelumnya, puncak dan lembah ditandai
segitiga. Di bawahnya, uraian berbahasa Indonesia tentang arah tren dan kekuatannya (ADX),
momentum (RSI), arah dorongan (MACD), gejolak (ATR dan lebar Bollinger), volume, jarak ke
level penting, dan posisi dalam rentang 52 minggu.

> **Ini uraian, bukan ramalan.** Pembacaan teknikal menjelaskan apa yang *sudah* terjadi
> pada harga. Tidak ada anjuran membeli atau menjual di mana pun dalam aplikasi ini — itu
> keputusan Anda, dan sebaiknya tetap begitu.

**Screener** — Dua tab.

*Saham*: **12 pasar** — Indonesia, Amerika, Malaysia, Singapura, Thailand, Hong Kong,
Jepang, India, Australia, Inggris, Jerman, Korea Selatan (363 saham). Saring berdasarkan
PER, PBV, ROE, dividen, DER, kapitalisasi, dan sektor. Tiap pasar memakai mata uangnya
sendiri dan label penyaring kapitalisasi ikut menyesuaikan.

Empat **saringan siap pakai** sekali klik: Saham Nilai, Pemburu Dividen, Kualitas Tinggi,
Tanpa Saringan. **Skor 0–100** meringkas peringkat tiap saham dalam hal harga murah,
produktivitas, kesehatan neraca, dan dividen — dengan rincian per bagian supaya tidak jadi
kotak hitam. Hasil bisa langsung dikirim ke watchlist atau dibandingkan berdampingan.

**Penapisan syariah** tersedia dengan dua ambang: AAOIFI dan DSN-MUI/OJK. Perlu dibaca
jujur — alat ini menghitung penapisan kegiatan usaha dan rasio utang berbunga terhadap
kapitalisasi, tetapi **tidak** bisa menghitung pendapatan non-halal dan piutang usaha karena
angka itu tidak tersedia di data terbuka. Jadi ini penyaring awal untuk mempersempit bacaan,
bukan penetapan status halal. Rujukan yang sah tetap Daftar Efek Syariah (DES) terbitan OJK,
atau indeks ISSI dan JII.

*Kripto*: saring sampai 250 koin berdasarkan kapitalisasi, kenaikan 7 hari, dan jarak dari
harga puncak. Kedua tab bisa diunduh sebagai CSV.

**Fundamental** — Per saham: delapan rasio kunci, posisi harga dalam rentang 52 minggu, dan
laporan keuangan tahunan lengkap — laba rugi, neraca, arus kas.

**Backtest** — Uji empat strategi (perpotongan rata-rata, RSI, di atas rata-rata, beli dan
tahan) pada data historis, dibandingkan langsung dengan sekadar membeli lalu mendiamkannya.

Delapan **rentang waktu**: bulanan, mingguan, harian, per jam, 30 menit, 15 menit, 5 menit,
dan per menit. Tiap rentang hanya menawarkan periode yang memang tersedia — Yahoo Finance
menyimpan data per menit hanya 7 hari ke belakang, data menit lainnya 60 hari, dan data
per jam sekitar dua tahun.

Hasilnya dibuka dengan papan putusan besar — berapa rupiah lebih banyak atau lebih sedikit
dibanding beli-dan-tahan, dengan batang pembanding. Lalu delapan kartu ukuran, kurva
pertumbuhan modal bertumpuk dengan **kurva penurunan** (jarak modal dari puncaknya sendiri),
**grafik harga dengan masa memegang diarsir** hijau untuk transaksi untung dan merah untuk
rugi lengkap dengan penanda masuk-keluar, **peta panas hasil per bulan**, **sebaran hasil
tiap transaksi**, dan daftar rinci seluruh transaksi.

**Forex** — Tersebar di beberapa halaman, bukan satu menu sendiri:

- *Pasar → tab Forex*: 22 pasangan dalam tiga kelompok — Utama (EUR/USD, GBP/USD, USD/JPY,
  dan seterusnya), Terhadap Rupiah (USD/IDR, EUR/IDR, SGD/IDR…), dan Silang (EUR/JPY,
  GBP/JPY…), lengkap dengan garis tren 30 hari.
- *Grafik*: seluruh pasangan bisa dipilih untuk grafik dan pembacaan teknikal.
- *Backtest*: pilih "Forex" pada jenis instrumen — biaya berubah dari komisi persen menjadi
  **spread dalam pip**, karena begitulah broker forex memungut.
- *Kalkulator → Posisi Forex*: nilai pip, ukuran lot yang boleh dibuka, dan risiko rupiah.

> **Tiga hal yang tidak dihitung backtest forex**, dan disebutkan terang-terangan di
> halamannya: bunga menginap (swap), daya ungkit berikut risiko margin call, dan kenyataan
> bahwa uji ini memakai data harian sementara kebanyakan pedagang forex bekerja di rentang
> menit atau jam.

**Kalkulator** — Empat alat. *Ukuran Posisi*: berapa lot yang boleh dibeli agar kerugian
tetap dalam batas yang Anda tetapkan. *Rata-rata Harga*: dampak menambah posisi terhadap
harga rata-rata. *Titik Impas*: harga jual minimum agar benar-benar untung setelah semua
biaya.

**Berita & Makro** — Kabel berita dari CNBC Indonesia, Kontan, dan Bisnis.com, plus sumber
global. Di tab sebelahnya, indikator ekonomi jangka panjang dari Bank Dunia untuk delapan
negara Asia dan dunia.

**Portofolio** — Catat kepemilikan Anda, lihat laba-rugi terhitung otomatis dari harga
pasar, lengkap dengan grafik alokasi dan laba-rugi per posisi.

**Dompet Kripto** — Tempel alamat publik Bitcoin, Ethereum, atau Solana untuk melihat saldo,
nilai rupiah, dan token yang dipegang. **Hanya baca.** Aplikasi ini tidak pernah meminta
seed phrase atau private key — dan Anda jangan pernah memasukkannya ke aplikasi mana pun.

**Peringatan** — Pasang batas harga untuk saham atau koin. Saat halaman dibuka, aplikasi
menandai mana yang sudah tersentuh. Berjalan lokal, tanpa server pengawas.

**Jurnal** — Catat tiap transaksi beserta alasan dan suasana hati saat memutuskan. Statistik
menghitung tingkat menang, rata-rata untung-rugi, dan harapan per transaksi. Grafik hasil
menurut suasana hati sering paling membuka mata.

**Laporan** — Cetak portofolio, jurnal, dompet, atau watchlist jadi PDF rapi bernama Anda.

---

## Dari mana datanya, dan kenapa gratis

| Yang Anda lihat | Sumber | Butuh daftar? |
|---|---|---|
| Harga saham, kripto, indeks, komoditas | Yahoo Finance | Tidak |
| Pasar kripto & koin terbesar | CoinGecko | Tidak |
| Indeks Takut & Serakah kripto | alternative.me | Tidak |
| Berita pasar | RSS media keuangan | Tidak |
| Indikator ekonomi | API Bank Dunia | Tidak |

> CoinGecko membatasi jumlah permintaan untuk pemakai gratis. Aplikasi ini menyimpan
> hasilnya selama tiga menit, jadi batas itu praktis tak pernah tersentuh dalam pemakaian
> normal. Kalau suatu saat bagian kripto kosong, tunggu sebentar lalu muat ulang.

Terminal komersial mengenakan kredit bukan untuk data seperti ini — data ini memang terbuka.
Kredit dipakai untuk layanan yang mereka jalankan sendiri: agen AI, server proksi, dan data
privat berbayar. Karena aplikasi ini mengambil langsung dari sumbernya, tidak ada perantara
yang perlu dibayar.

---

## Kenapa tombol "Deploy" hilang?

Streamlit membubuhkan tombol **Deploy** di pojok kanan atas setiap aplikasi. Gunanya
mengunggah aplikasi ke server Streamlit Community Cloud supaya bisa diakses orang lain
lewat internet — sama sekali tidak ada hubungannya dengan pemakaian di komputer sendiri.
Untuk aplikasi pribadi, tombol itu hanya bikin bingung.

Tombolnya sudah dimatikan lewat `.streamlit/config.toml` (`toolbarMode = "minimal"`).
Tempatnya digantikan kartu dukungan sukarela lewat DANA, yang muncul di bawah sidebar dan
di halaman Tentang → Pembuat.

Nomornya diatur di bagian `PROFIL` → `"donasi"` di dalam `terminal_ringan.py`, jadi mudah
diganti kapan pun.

**Mau pakai QR code?** Letakkan gambar QRIS Anda di `aset/qris.png`. Kartu donasi otomatis
berubah jadi dua kolom — QR di kiri, nomor di kanan. Panduan lengkap mengambil QR dari
aplikasi DANA ada di `aset/CARA-PASANG-QRIS.md`.

---

## Tema terang dan gelap

Tombol di bagian atas sidebar menukar tampilan seketika, tanpa perlu memulai ulang.
Pilihan Anda tersimpan di `data/pengaturan.json` dan diingat saat aplikasi dibuka lagi.

Kedua tema memakai satu daftar warna terpusat bernama `PALET` di dalam
`terminal_ringan.py`. Mau membuat tema Anda sendiri — biru laut, sepia, apa pun? Salin
salah satu blok, ganti nilainya, beri nama baru. Tidak ada satu pun warna yang tertulis
lepas di tempat lain, jadi tidak ada yang tertinggal.

---

## Data Anda

Watchlist dan portofolio disimpan di folder **`data/`** di sebelah berkas ini, dalam bentuk
JSON biasa yang bisa Anda buka dengan Notepad. Tidak ada yang dikirim ke mana pun, tidak ada
akun, tidak ada pelacakan.

Mau memindahkan ke komputer lain? Salin folder `data/` saja.
Mau mulai dari nol? Hapus folder `data/`.

---

## Menulis simbol dengan benar

| Jenis | Pola | Contoh |
|---|---|---|
| Saham Indonesia | kode + `.JK` | `BBCA.JK`, `TLKM.JK`, `GOTO.JK` |
| Saham Amerika | kode saja | `AAPL`, `MSFT`, `NVDA` |
| Kripto | pasangan mata uang | `BTC-USD`, `ETH-USD` |
| Indeks | diawali `^` | `^JKSE` (IHSG), `^GSPC` (S&P 500) |
| Kurs | pasangan + `=X` | `USDIDR=X` |
| Komoditas | kode + `=F` | `GC=F` (emas), `CL=F` (minyak) |

---

## Batasan yang perlu Anda tahu

- **Harga tertunda 15–20 menit** untuk saham. Cukup untuk memantau, tidak cukup untuk
  trading cepat.
- **Yahoo Finance adalah sumber tak resmi.** Sewaktu-waktu formatnya berubah dan aplikasi
  ini perlu disesuaikan. Kalau suatu hari harga tidak muncul padahal internet normal,
  kemungkinan besar itu sebabnya.
- **Data Bank Dunia tertinggal 1–2 tahun.** Sifatnya memang tahunan.
- **Mata uang tidak dikonversi.** Total portofolio yang mencampur rupiah dan dolar tidak
  bermakna. Pisahkan per mata uang bila perlu.
- **Biaya transaksi, pajak, dan dividen tidak dihitung.** Angka di rekening asli Anda akan
  sedikit berbeda.
- **Tidak ada di sini yang merupakan nasihat investasi.**

---

## Mengubah sesuai selera

Seluruh aplikasi ada dalam satu berkas: `terminal_ringan.py`. Buka dengan Notepad++ atau
VS Code, dan lihat bagian **PENGATURAN DASAR** di bagian paling atas. Di sana ada:

- `WATCHLIST_AWAL` — simbol bawaan untuk pemakai baru
- `INDEKS_PANTAU` — enam indeks di baris atas halaman Pasar
- `MAKRO_PANTAU` — kartu makro di tab Indikator Ekonomi
- `RSS_INDONESIA` dan `RSS_GLOBAL` — sumber berita
- `INDIKATOR_BANK_DUNIA` dan `NEGARA` — pilihan di grafik ekonomi

Ubah, simpan, lalu tekan tombol muat ulang di browser. Perubahan langsung terlihat.

---

## Kalau ada masalah

**"These files can't be opened — Your Internet security settings prevented one or more files
from being opened"** — Windows menandai berkas yang datang dari luar komputer sebagai
"berasal dari internet", lalu menolak menjalankannya. Tanda itu menempel diam-diam di berkas,
tidak terlihat dari Explorer. Tiga cara melepasnya, dari yang paling mudah:

1. Pakai **`MULAI.cmd`** — berkas ini dibuat langsung di komputer Anda, jadi tidak pernah
   ditandai. Ini yang seharusnya dipakai.
2. Klik kanan berkas → **Properties** → di bagian bawah tab General ada kotak centang
   **Unblock** → centang → **OK**. Kotak itu hanya muncul kalau berkasnya memang ditandai.
3. Buka Command Prompt di folder ini, lalu jalankan manual:
   `python -m streamlit run terminal_ringan.py`

**Browser tidak terbuka sendiri** — buka manual ke `http://localhost:8501`.

**Semua angka menunjukkan tanda strip** — koneksi internet terputus, atau Yahoo Finance
sedang bermasalah. Tekan tombol **⟳ MUAT ULANG**.

**Satu simbol saja yang kosong** — penulisan simbolnya kemungkinan salah. Periksa tabel
pola simbol di atas.

**Muncul pesan Python tidak ditemukan** — pasang dari python.org, dan pastikan mencentang
*"Add Python to PATH"* saat memasang.

---

## Uji yang sudah dijalankan

Sebelum diserahkan, aplikasi ini diuji:

- 20 pengujian perhitungan — RSI (termasuk kasus ekstrem harga naik terus, turun terus,
  dan diam di tempat), MACD, format angka, pewarnaan, dan aritmetika portofolio
- Kelima halaman dijalankan tanpa koneksi internet sama sekali — tidak ada yang crash,
  semua menampilkan peringatan yang wajar
- Simpan-muat watchlist dan portofolio lewat antarmuka, termasuk memastikan data bertahan
  setelah aplikasi ditutup dan dibuka lagi

Satu bug ditemukan dan diperbaiki saat pengujian: RSI menunjukkan 50 alih-alih 100 pada
harga yang naik tanpa jeda.
