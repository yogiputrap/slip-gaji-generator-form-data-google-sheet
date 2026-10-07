# Auto Slip Gaji Generator (SESAR LEMBANG KALCER)

Aplikasi **lightweight** untuk mengekstrak data rekap penggajian dari Google Sheets (atau file Excel `.xlsx`) dan otomatis menghasilkan **Slip Gaji PDF** dengan format dan tata letak yang **100% presisi** sesuai contoh template resmi.

---

## 🌟 Fitur Utama

1. **Auto-Extract dari Google Sheet & Excel**:
   - Terhubung langsung ke URL Google Sheet rekap penggajian:  
     `<URL Google Sheet rekap penggajian>`
   - Mendukung juga upload langsung file `.xlsx` / `.xls` lokal.
2. **Format Standar B5 & Tipografi Presisi**:
   - Menggunakan format kertas **B5** (176mm × 250mm) dan font **Calibri**, sama persis seperti contoh PDF rujukan (`Slip_Gaji_<Periode>_<Nama>.pdf`).
3. **Kustomisasi Logo & Tanda Tangan**:
   - **Logo**: Bisa upload gambar logo perusahaan kustom (PNG, JPG, SVG) atau gunakan logo bawaan *Sesar Lembang Kalcer*.
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

### 2. Menggunakan CLI (Terminal)

Untuk generate slip gaji langsung dari terminal:

```bash
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
│   ├── logo_default.png     # Logo bawaan SESAR LEMBANG KALCER
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
