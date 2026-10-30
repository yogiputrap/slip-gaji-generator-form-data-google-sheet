# Auto Slip Gaji Generator

Aplikasi **lightweight** untuk mengekstrak data rekap penggajian dari Google Sheets (atau file Excel `.xlsx`) dan otomatis menghasilkan **Slip Gaji PDF** dengan format dan tata letak yang **100% presisi** sesuai contoh template resmi.

---

## 🌟 Fitur Utama

1. **Auto-Extract dari Google Sheet & Excel**:
   - Terhubung langsung ke URL Google Sheet rekap penggajian (URL diisi lewat dashboard atau env `SHEET_URL`, jangan ditulis di repo).
   - Mendukung juga upload langsung file `.xlsx` / `.xls` lokal.
2. **Format Standar B5 & Tipografi Presisi**:
   - Menggunakan format kertas **B5** (176mm × 250mm) dan font **Calibri**, sama persis seperti template slip resmi.
3. **Kustomisasi Logo & Tanda Tangan**:
   - **Logo**: Bisa upload gambar logo perusahaan kustom (PNG, JPG, SVG) atau gunakan logo bawaan.
   - **Tanda Tangan**: Bisa upload file gambar tanda tangan (PNG transparan) atau dikosongkan untuk tanda tangan basah manual.
   - **Kop & Informasi Slip**: Periode (misal: *September 2026*), Tanggal (*Bandung, 29 September 2026*), Jabatan (*Bagian Keuangan,*), dan Nama Penanda Tangan (*Nama Penanda Tangan*).
4. **Terbilang Otomatis (Bahasa Indonesia)**:
   - Mengonversi nominal total gaji bersih ke teks terbilang Rupiah secara otomatis (contoh: *Satu Juta Lima Ratus Ribu Rupiah*).
5. **Ekspor & Download Fleksibel**:
   - **Live Preview** slip gaji interaktif langsung di browser.
   - **Print Langsung** (`window.print`) dari browser.
   - **Download Satuan PDF** per karyawan.
   - **Batch Download ZIP** untuk semua atau karyawan yang dipilih sekaligus.
6. **Dual Mode: Web Dashboard & CLI**:
   - Tampilan web UI modern & responsif.
   - Script CLI terminal untuk proses automasi terjadwal/cron.

---

## 🚀 Cara Menjalankan

### 1. Menjalankan Web Dashboard (Rekomendasi)

Jalankan script `run.sh` atau perintah uvicorn berikut:

```bash
./run.sh
```
*Atau:*
```bash
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Buka browser di: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

#### Login

Dashboard dilindungi halaman login. Kredensial dibaca dari environment (tanpa database).
Salin `.env.example` ke `.env` lalu isi `AUTH_USERNAME`, `AUTH_PASSWORD`, dan `AUTH_SECRET`
(`run.sh` memuat `.env` otomatis). Jika `AUTH_USERNAME`/`AUTH_PASSWORD` kosong, login ditolak.

### Deploy ke Dokploy

Proyek ini membawa `Dockerfile` (Python + Chromium + font Carlito sebagai pengganti Calibri).

1. Buat aplikasi baru di Dokploy, sumber: repo Git ini, **Build Type: Dockerfile**.
2. Tab **Environment**, isi: `AUTH_USERNAME`, `AUTH_PASSWORD`, `AUTH_SECRET` (lihat `.env.example`).
3. Tab **Advanced → Volumes**, tambah volume (Volume Mount) dengan **Mount Path `/data`**. Unggahan logo/TTD disimpan di sini agar tidak hilang saat redeploy.
4. Tab **Domains**, isi domain dan **Container Port `8000`**, aktifkan HTTPS (Let's Encrypt).
5. Deploy.

Catatan: pilihan tanda tangan/logo aktif dan konfigurasi slip disimpan di memori, jadi dipilih ulang setelah container restart.

### 2. Menggunakan CLI (Terminal)

Untuk generate slip gaji langsung dari terminal. Sumber data diambil dari env `SHEET_URL`
(atau argumen `--sheet <URL atau file.xlsx>`):

```bash
export SHEET_URL="<URL Google Sheet rekap penggajian>"

# Generate seluruh slip gaji ke folder output:
python3 cli.py

# Generate hanya untuk karyawan nomor 1:
python3 cli.py --id 1

# Generate semua slip dan langsung dikemas ke file ZIP:
python3 cli.py --zip

# Kustomisasi parameter lewat CLI:
python3 cli.py --period "September 2026" --slip-date "Bandung, 30 September 2026" --signer-name "Nama Penanda Tangan"
```

---

## 📁 Struktur Direktori

```
├── app.py              # Backend FastAPI & Web API routes
├── generator.py        # Core logic: ekstraksi data, terbilang, render HTML & Chrome PDF
├── cli.py              # Antarmuka CLI untuk terminal
├── run.sh              # Script shortcut untuk menjalankan Web Dashboard
├── assets/
│   ├── logo_default.png     # Logo bawaan
│   └── custom_logo...       # Tempat penyimpanan logo kustom
├── templates/
│   └── index.html      # UI Dashboard Web (Single Page App, lightweight)
├── output/             # Tempat penyimpanan file PDF dan ZIP hasil generate
└── README.md           # Dokumentasi proyek
```

---

## ⚡ Teknologi (Lightweight Stack)

- **Backend**: Python 3 (FastAPI + openpyxl).
- **PDF Engine**: Headless Chrome (engine Skia/PDF bawaan macOS yang merupakan engine asli pembuat PDF contoh).
- **Frontend**: Vanilla HTML5 + CSS + JavaScript (tanpa framework berat node_modules, loading instan).

---

## 🔒 Keamanan Data

Repo ini mengolah data gaji dan karyawan. Jangan pernah commit hal berikut (semuanya sudah di-`.gitignore`):

- `.env` (kredensial login, `AUTH_SECRET`) dan URL Google Sheet
- `output/` (PDF/ZIP slip gaji hasil generate berisi nama, rekening, dan nominal gaji)
- File spreadsheet (`*.xlsx`, `*.xls`, `*.csv`) dan `assets/custom_*` (tanda tangan & logo kustom)

Atur akses Google Sheet ke "Dibatasi" (bukan "Siapa saja yang memiliki link") bila memungkinkan.
