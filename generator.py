import os
import re
import math
import subprocess
import tempfile
import urllib.request
import base64
import zipfile
from typing import List, Dict, Any, Optional
import openpyxl

def terbilang(n: float) -> str:
    """Konversi nominal angka ke kalimat terbilang Rupiah dalam Bahasa Indonesia."""
    try:
        n = int(round(float(n)))
    except (ValueError, TypeError):
        return "Nol Rupiah"
    
    if n == 0:
        return "Nol Rupiah"
    if n < 0:
        return "Minus " + terbilang(abs(n))
    
    satuan = ['', 'Satu', 'Dua', 'Tiga', 'Empat', 'Lima', 'Enam', 'Tujuh', 'Delapan', 'Sembilan', 'Sepuluh', 'Sebelas']
    
    def bilang(x):
        if x < 12:
            return satuan[x]
        elif x < 20:
            return bilang(x - 10) + ' Belas'
        elif x < 100:
            hasil = bilang(x // 10) + ' Puluh'
            sisa = x % 10
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 200:
            hasil = 'Seratus'
            sisa = x - 100
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 1000:
            hasil = bilang(x // 100) + ' Ratus'
            sisa = x % 100
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 2000:
            hasil = 'Seribu'
            sisa = x - 1000
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 1000000:
            hasil = bilang(x // 1000) + ' Ribu'
            sisa = x % 1000
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 1000000000:
            hasil = bilang(x // 1000000) + ' Juta'
            sisa = x % 1000000
            return hasil + (' ' + bilang(sisa) if sisa else '')
        elif x < 1000000000000:
            hasil = bilang(x // 1000000000) + ' Miliar'
            sisa = x % 1000000000
            return hasil + (' ' + bilang(sisa) if sisa else '')
        return str(x)

    words = bilang(n).strip()
    return words + " Rupiah"

def format_rupiah(val: Any) -> str:
    """Format angka ke format ribuan rupiah (misal: 3,500,000)."""
    try:
        if val is None or val == "":
            return "0"
        num = float(val)
        if num == 0:
            return "0"
        if num.is_integer():
            return f"{int(num):,}"
        return f"{num:,.2f}"
    except (ValueError, TypeError):
        return "0"

def clean_rekening(val: Any) -> str:
    """Membersihkan format nomor rekening dari suffix .0, notasi ilmiah, atau tipe float."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return ""
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return ""
        if val.is_integer():
            return str(int(val))
        return f"{val:.0f}"
    
    val_str = str(val).strip()
    if not val_str:
        return ""
    
    # Hilangkan suffix .0 atau .00
    val_str = re.sub(r'\.0+$', '', val_str)
    
    # Tangani jika string berupa notasi ilmiah
    if re.search(r'[eE][+-]?\d+', val_str):
        try:
            f = float(val_str)
            if f.is_integer():
                return str(int(f))
            return f"{f:.0f}"
        except (ValueError, OverflowError):
            pass
            
    try:
        f = float(val_str)
        if f.is_integer():
            return str(int(f))
    except (ValueError, OverflowError):
        pass

    return val_str

MONTH_NAMES = [
    ("januari", "Januari"), ("january", "Januari"),
    ("februari", "Februari"), ("february", "Februari"),
    ("maret", "Maret"), ("march", "Maret"),
    ("april", "April"),
    ("mei", "Mei"), ("may", "Mei"),
    ("juni", "Juni"), ("june", "Juni"),
    ("juli", "Juli"), ("july", "Juli"),
    ("agustus", "Agustus"), ("august", "Agustus"),
    ("september", "September"),
    ("oktober", "Oktober"), ("october", "Oktober"),
    ("november", "November"),
    ("desember", "Desember"), ("december", "Desember"),
]

def detect_period_from_header(header_text: str) -> tuple[str, str]:
    """
    Ekstrak nama bulan dan tahun dari teks header (misal 'Take Home September\\n(sum{a:f}-g)').
    Mengembalikan tuple: (detected_period, detected_slip_date).
    Contoh: ('September 2026', 'Bandung, 29 September 2026')
    """
    if not header_text:
        return "August 2026", "Bandung, 29 Agustus 2026"
        
    text = str(header_text).strip()
    
    found_month = None
    for pattern, std_month in sorted(MONTH_NAMES, key=lambda x: len(x[0]), reverse=True):
        if re.search(r'\b' + re.escape(pattern) + r'\b', text, re.IGNORECASE):
            found_month = std_month
            break
            
    if not found_month:
        return "August 2026", "Bandung, 29 Agustus 2026"
        
    year_match = re.search(r'\b(20\d{2})\b', text)
    year = year_match.group(1) if year_match else "2026"
    
    detected_period = f"{found_month} {year}"
    detected_slip_date = f"Bandung, 29 {found_month} {year}"
    return detected_period, detected_slip_date

def clean_sheet_url(url: str) -> str:
    """Mengubah URL Google Sheet ke direct export URL format XLSX."""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        doc_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
    return url

def fetch_data_from_sheet(sheet_url_or_path: str):
    """
    Download atau baca file XLSX / Google Sheets dan mengekstrak daftar karyawan,
    periode yang terdeteksi, serta tanggal slip.
    """
    if sheet_url_or_path.startswith("http://") or sheet_url_or_path.startswith("https://"):
        export_url = clean_sheet_url(sheet_url_or_path)
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            with urllib.request.urlopen(req) as resp:
                tmp_file.write(resp.read())
        try:
            wb = openpyxl.load_workbook(tmp_path, data_only=True)
            employees, period, slip_date = parse_workbook(wb)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    else:
        wb = openpyxl.load_workbook(sheet_url_or_path, data_only=True)
        employees, period, slip_date = parse_workbook(wb)
    
    return employees, period, slip_date

def parse_workbook(wb: openpyxl.Workbook):
    sheet = wb.active
    
    # Deteksi periode dan tanggal slip dari kolom 41 (AO) baris 1
    col41_val = sheet.cell(1, 41).value or ""
    detected_period, detected_slip_date = detect_period_from_header(str(col41_val))
    if detected_period == "August 2026" and not re.search(r'\b(agustus|august)\b', str(col41_val), re.IGNORECASE):
        for col_idx in range(1, min(sheet.max_column + 1, 60)):
            cval = str(sheet.cell(1, col_idx).value or "")
            p, s = detect_period_from_header(cval)
            if p != "August 2026" or re.search(r'\b(agustus|august)\b', cval, re.IGNORECASE):
                detected_period, detected_slip_date = p, s
                break

    employees = []
    
    for r in range(2, sheet.max_row + 1):
        nama = sheet.cell(r, 2).value
        if not nama or not str(nama).strip() or str(nama).strip().startswith("="):
            continue
        
        nama_clean = str(nama).strip()
        no_val = sheet.cell(r, 1).value
        try:
            no = int(float(no_val)) if no_val is not None else len(employees) + 1
        except (ValueError, TypeError):
            no = len(employees) + 1

        bagian = sheet.cell(r, 4).value or "OPERASIONAL"
        posisi = sheet.cell(r, 5).value or ""
        rek_raw = sheet.cell(r, 6).value
        rek = clean_rekening(rek_raw)
        
        # Nominal gaji
        gaji_pokok = float(sheet.cell(r, 34).value or sheet.cell(r, 7).value or 0)
        tunj_posisi = float(sheet.cell(r, 35).value or sheet.cell(r, 8).value or 0)
        tunj_kehadiran = float(sheet.cell(r, 36).value or sheet.cell(r, 14).value or 0)
        lembur_wfa = float(sheet.cell(r, 37).value or sheet.cell(r, 18).value or 0)
        bonus_kinerja = float(sheet.cell(r, 38).value or sheet.cell(r, 21).value or 0)
        pendapatan_lain = float(sheet.cell(r, 39).value or sheet.cell(r, 22).value or 0)
        
        # Potongan
        potongan_kehadiran = float(sheet.cell(r, 40).value or sheet.cell(r, 27).value or 0)
        potongan_lain = 0.0
        
        total_bonus_kotor = tunj_posisi + tunj_kehadiran + lembur_wfa + bonus_kinerja + pendapatan_lain
        penerimaan_kotor = gaji_pokok + total_bonus_kotor
        total_potongan = potongan_kehadiran + potongan_lain
        thp = penerimaan_kotor - total_potongan
        
        employees.append({
            "id": no,
            "no": str(no),
            "nama": nama_clean,
            "bagian": str(bagian).strip(),
            "posisi": str(posisi).strip(),
            "rekening": rek,
            "period": detected_period,
            "slip_date": detected_slip_date,
            "gaji_pokok": gaji_pokok,
            "tunjangan_kehadiran_a": tunj_posisi,      # 2.a
            "bonus_kehadiran_b": tunj_kehadiran,       # 2.b
            "lembur_wfa_c": lembur_wfa,                # 2.c
            "bonus_kinerja_d": bonus_kinerja,          # 2.d
            "pendapatan_lain_e": pendapatan_lain,      # 2.e
            "penerimaan_kotor": penerimaan_kotor,
            "potongan_kehadiran": potongan_kehadiran,  # 3.a
            "potongan_lain": potongan_lain,            # 3.b
            "total_potongan": total_potongan,
            "total_penghasilan": thp,
            "terbilang": terbilang(thp)
        })
    
    return employees, detected_period, detected_slip_date

def get_base64_image(image_path: str) -> str:
    """Mengubah file gambar lokal menjadi Base64 Data URI."""
    if not image_path or not os.path.exists(image_path):
        return ""
    ext = os.path.splitext(image_path)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    mime = f"image/{ext}" if ext != "svg" else "image/svg+xml"
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"

def render_slip_html(emp: Dict[str, Any], config: Dict[str, Any], preview_mode: bool = False) -> str:
    """
    Menghasilkan HTML slip gaji dengan tata letak dan font presisi
    sesuai dengan template contoh PDF B5.
    """
    logo_src = config.get("logo_data_uri", "")
    if not logo_src and config.get("logo_path"):
        logo_src = get_base64_image(config["logo_path"])
        
    sig_src = config.get("signature_data_uri", "")
    if not sig_src and config.get("signature_path"):
        sig_src = get_base64_image(config["signature_path"])

    company_title = config.get("company_title", "SLIP GAJI")
    company_subtitle = config.get("company_subtitle", "KARYAWAN SESAR LEMBANG KALCER")
    company_address = config.get("company_address", "Jl. Cigadung Raya Barat No. 18, Bandung")
    period = config.get("period", "September 2026")
    slip_date = config.get("slip_date", "Bandung, 29 September 2026")
    signer_title = config.get("signer_title", "Bagian Keuangan,")
    signer_name = config.get("signer_name", "Reza Fauzi")
    
    label_2a = config.get("label_2a", "Tunjangan Kehadiran")
    label_2b = config.get("label_2b", "Bonus Kehadiran")
    label_2c = config.get("label_2c", "Lembur/Tunj.Hadir Kary. WFA")
    label_2d = config.get("label_2d", "Bonus Kinerja SLK")
    label_2e = config.get("label_2e", "Lain-Lain")
    template = config.get("template", "default")
    page_class = "page theme-algae" if template == "algae" else "page"

    nama_display = emp['nama']

    extra_head = ""
    extra_wrap_open = ""
    extra_wrap_close = ""
    extra_script = ""

    if preview_mode:
        extra_head = """<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  html, body {
    background-color: #f4f4f5 !important;
    min-height: 100%;
  }
  .stage-wrap {
    width: 100%;
    min-height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 8px;
    box-sizing: border-box;
  }
  .page-scaler {
    position: relative;
    margin: 0 auto;
  }
  .page {
    width: 665px !important;
    min-height: 945px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
    border: 1px solid #e4e4e7 !important;
    border-radius: 4px !important;
    margin: 0 auto !important;
  }
  @media print {
    html, body { background: #fff !important; }
    .stage-wrap { padding: 0 !important; display: block !important; }
    .page-scaler { width: 176mm !important; height: auto !important; margin: 0 !important; }
    .page {
      transform: none !important;
      width: 176mm !important;
      min-height: 250mm !important;
      box-shadow: none !important;
      border: none !important;
      margin: 0 !important;
    }
  }
</style>"""
        extra_wrap_open = """<div class="stage-wrap"><div class="page-scaler" id="slipScaler">"""
        extra_wrap_close = """</div></div>"""
        extra_script = """<script>
(function() {
  function autoScale() {
    var page = document.getElementById('slipPage');
    var scaler = document.getElementById('slipScaler');
    if (!page || !scaler) return;
    var availW = window.innerWidth;
    var pageW = 665;
    if (availW < pageW + 20) {
      var scale = (availW - 20) / pageW;
      page.style.transformOrigin = 'top left';
      page.style.transform = 'scale(' + scale + ')';
      scaler.style.width = Math.ceil(pageW * scale) + 'px';
      scaler.style.height = Math.ceil(page.offsetHeight * scale) + 'px';
    } else {
      page.style.transform = 'none';
      scaler.style.width = pageW + 'px';
      scaler.style.height = page.offsetHeight + 'px';
    }
  }
  window.addEventListener('resize', autoScale);
  window.addEventListener('load', autoScale);
  if (document.readyState === 'complete') autoScale();
  else document.addEventListener('DOMContentLoaded', autoScale);
})();
</script>"""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Slip Gaji - {emp['nama']}</title>
{extra_head}
<style>
  @page {{
    size: 176mm 250mm; /* Standar B5 sesuai referensi asli */
    margin: 0;
  }}
  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  body {{
    margin: 0;
    padding: 0;
    background-color: #ffffff;
    font-family: 'Calibri', 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
    color: #000000;
    line-height: 1.3;
  }}
  .page {{
    width: 176mm;
    min-height: 250mm;
    margin: 0 auto;
    padding: 24mm 16mm 20mm 16mm;
    position: relative;
    background: #fff;
  }}

  /* HEADER */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }}
  .logo-box {{
    width: 155px;
    height: 90px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
  }}
  .logo-box img {{
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }}
  .header-right {{
    width: 270px;
    text-align: center;
  }}
  .title-main {{
    font-weight: bold;
    font-size: 14.5px;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
  }}
  .title-sub {{
    font-weight: bold;
    font-size: 12.5px;
    white-space: nowrap;
    margin-bottom: 3px;
  }}
  .title-address {{
    font-size: 10.5px;
    margin-bottom: 5px;
  }}
  .header-divider {{
    border: none;
    border-top: 1.5px solid #000;
    margin: 2px 0 5px 0;
    width: 100%;
  }}
  .no-row {{
    display: flex;
    justify-content: space-between;
    padding-left: 95px;
    padding-right: 5px;
    font-size: 11px;
  }}

  /* EMPLOYEE INFO */
  .emp-info {{
    margin-top: 8px;
    margin-bottom: 12px;
    width: 100%;
  }}
  .emp-table {{
    border-collapse: collapse;
    width: 100%;
  }}
  .emp-table td {{
    padding: 2px 0;
    vertical-align: top;
    font-size: 11px;
  }}
  .emp-table .emp-label {{
    font-weight: bold;
    width: 130px;
    letter-spacing: 0.5px;
  }}
  .emp-table .emp-colon {{
    width: 25px;
    text-align: center;
  }}
  .emp-table .emp-val {{
    font-weight: normal;
  }}

  .divider-thick {{
    border: none;
    border-top: 2.2px solid #000;
    margin: 10px 0 16px 0;
  }}

  /* RINCIAN HEADER */
  .section-title {{
    text-align: center;
    font-weight: bold;
    font-size: 11.5px;
    text-decoration: underline;
    letter-spacing: 0.3px;
    margin-bottom: 16px;
  }}

  /* SALARY TABLE */
  .salary-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }}
  .salary-table td {{
    padding: 2px 0;
    vertical-align: middle;
  }}
  .col-item {{
    width: 240px;
  }}
  .col-colon {{
    width: 16px;
    text-align: center;
  }}
  .col-sub-val {{
    width: 90px;
    text-align: right;
    padding-right: 28px;
  }}
  .col-rp {{
    width: 26px;
    text-align: left;
  }}
  .col-val {{
    width: 95px;
    text-align: right;
  }}

  .indent-sub {{
    padding-left: 18px !important;
  }}
  .indent-total {{
    padding-left: 28px !important;
  }}

  .row-gap {{
    height: 10px;
  }}

  .total-row {{
    font-weight: bold;
  }}
  .total-row td {{
    padding-top: 7px;
    padding-bottom: 7px;
  }}

  /* TERBILANG */
  .terbilang-box {{
    margin-top: 8px;
    border-top: 1.5px solid #000;
    padding-top: 8px;
    padding-bottom: 8px;
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-style: italic;
  }}
  .terbilang-text {{
    text-align: center;
    width: 100%;
    padding: 0 10px;
  }}

  /* SIGNATURE SECTION */
  .sig-section {{
    margin-top: 42px;
    float: right;
    width: 175px;
    text-align: center;
    font-size: 11px;
  }}
  .sig-date {{
    margin-bottom: 2px;
  }}
  .sig-title {{
    margin-bottom: 2px;
  }}
  .sig-image-box {{
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .sig-image-box img {{
    max-height: 48px;
    max-width: 140px;
    object-fit: contain;
  }}
  .sig-line {{
    border: none;
    border-top: 1px solid #000;
    margin: 2px auto 4px auto;
    width: 150px;
  }}
  .sig-name {{
    font-size: 11px;
  }}

  /* ═══════════════ THEME: ALGAE GREEN (CLEAN WHITE BACKGROUND) ═══════════════ */
  /* Palette: #13714C, #3AB67D, #A2E494, #E9EBED, Background: #FFFFFF */
  .theme-algae {{
    color: #1a2e22;
  }}
  .theme-algae .title-main {{
    color: #13714C;
    font-weight: 800;
    letter-spacing: 0.6px;
  }}
  .theme-algae .title-sub {{
    color: #24563e;
  }}
  .theme-algae .title-address {{
    color: #4b6b59;
  }}
  .theme-algae .header-divider {{
    border-top: 2px solid #13714C;
  }}
  .theme-algae .no-row {{
    color: #13714C;
    font-weight: 600;
  }}
  .theme-algae .emp-table .emp-label {{
    color: #13714C;
  }}
  .theme-algae .divider-thick {{
    border-top: 2.2px solid #13714C;
  }}
  .theme-algae .section-title {{
    color: #13714C;
    text-decoration: none;
    background: #f0f8f4;
    padding: 3px 14px;
    border-radius: 4px;
    border-left: 3px solid #13714C;
    border-right: 3px solid #3AB67D;
    display: inline-block;
  }}
  .theme-algae .salary-table td.col-item[style*="font-weight: bold"] {{
    color: #13714C;
  }}
  .theme-algae .salary-table tr.total-row {{
    color: #13714C;
    background: #f2f9f5;
  }}
  .theme-algae .salary-table tr.total-row td {{
    border-top: 1.5px solid #3AB67D;
    border-bottom: 2px solid #13714C;
    padding-top: 5px;
    padding-bottom: 5px;
  }}
  .theme-algae .terbilang-box {{
    border-top: 1.5px solid #A2E494;
    background: #fafdfb;
    border-radius: 3px;
    padding: 6px 12px;
    color: #13714C;
    font-weight: 500;
  }}
  .theme-algae .sig-date {{
    color: #4b6b59;
  }}
  .theme-algae .sig-title {{
    color: #13714C;
    font-weight: 600;
  }}
  .theme-algae .sig-line {{
    border-top: 1.5px solid #13714C;
  }}
  .theme-algae .sig-name {{
    color: #13714C;
    font-weight: bold;
  }}
</style>
</head>
<body>
{extra_wrap_open}
<div class="{page_class}" id="slipPage">
  <!-- HEADER -->
  <div class="header">
    <div class="logo-box">
      {"<img src='" + logo_src + "' alt='Logo' />" if logo_src else "<div style='font-size:16px;font-weight:bold;'>[LOGO]</div>"}
    </div>
    <div class="header-right">
      <div class="title-main">{company_title}</div>
      <div class="title-sub">{company_subtitle}</div>
      <div class="title-address">{company_address}</div>
      <hr class="header-divider" />
      <div class="no-row">
        <span>NO :</span>
        <span>{emp['no']}</span>
      </div>
    </div>
  </div>

  <!-- EMPLOYEE INFO -->
  <div class="emp-info">
    <table class="emp-table">
      <tr>
        <td class="emp-label">NAMA</td>
        <td class="emp-colon">:</td>
        <td class="emp-val">{nama_display}</td>
      </tr>
      <tr>
        <td class="emp-label">DIVISI</td>
        <td class="emp-colon">:</td>
        <td class="emp-val">{emp['bagian']}</td>
      </tr>
      <tr>
        <td class="emp-label">REKENING</td>
        <td class="emp-colon">:</td>
        <td class="emp-val">{emp['rekening']}</td>
      </tr>
      <tr>
        <td class="emp-label">GAJI BULANAN</td>
        <td class="emp-colon">:</td>
        <td class="emp-val">{period}</td>
      </tr>
    </table>
  </div>

  <hr class="divider-thick" />

  <!-- RINCIAN PENERIMA GAJI -->
  <div class="section-title">RINCIAN PENERIMA GAJI</div>

  <table class="salary-table">
    <!-- 1 GAJI POKOK -->
    <tr>
      <td class="col-item">1 GAJI POKOK</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val"></td>
      <td class="col-rp">Rp</td>
      <td class="col-val">{format_rupiah(emp['gaji_pokok'])}</td>
    </tr>
    <!-- 2 BONUS -->
    <tr>
      <td class="col-item" colspan="5">2 BONUS</td>
    </tr>
    <tr>
      <td class="col-item indent-sub">a {label_2a}</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val">{format_rupiah(emp['tunjangan_kehadiran_a'])}</td>
      <td class="col-rp"></td>
      <td class="col-val"></td>
    </tr>
    <tr>
      <td class="col-item indent-sub">b {label_2b}</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val">{format_rupiah(emp['bonus_kehadiran_b'])}</td>
      <td class="col-rp"></td>
      <td class="col-val"></td>
    </tr>
    <tr>
      <td class="col-item indent-sub">c {label_2c}</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val">{format_rupiah(emp['lembur_wfa_c'])}</td>
      <td class="col-rp"></td>
      <td class="col-val"></td>
    </tr>
    <tr>
      <td class="col-item indent-sub">d {label_2d}</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val">{format_rupiah(emp['bonus_kinerja_d'])}</td>
      <td class="col-rp"></td>
      <td class="col-val"></td>
    </tr>
    <tr>
      <td class="col-item indent-sub">e {label_2e}</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val">{format_rupiah(emp['pendapatan_lain_e'])}</td>
      <td class="col-rp"></td>
      <td class="col-val"></td>
    </tr>
    <tr>
      <td class="col-item indent-total">Jumlah Penerimaan Kotor</td>
      <td class="col-colon">:</td>
      <td class="col-sub-val"></td>
      <td class="col-rp">Rp</td>
      <td class="col-val">{format_rupiah(emp['penerimaan_kotor'])}</td>
    </tr>

    <!-- GAP -->
    <tr class="row-gap"><td colspan="5"></td></tr>

    <!-- 3 POTONGAN -->
    <tr>
      <td class="col-item" colspan="5">3 Potongan</td>
    </tr>
    <tr>
      <td class="col-item indent-sub">a Kehadiran</td>
      <td class="col-colon"></td>
      <td class="col-sub-val"></td>
      <td class="col-rp">Rp</td>
      <td class="col-val">{format_rupiah(emp['potongan_kehadiran'])}</td>
    </tr>
    <tr>
      <td class="col-item indent-sub">b Lain-lain</td>
      <td class="col-colon"></td>
      <td class="col-sub-val"></td>
      <td class="col-rp">Rp</td>
      <td class="col-val">{format_rupiah(emp['potongan_lain']) if emp['potongan_lain'] > 0 else ""}</td>
    </tr>

    <!-- TOTAL PENGHASILAN -->
    <tr class="total-row">
      <td class="col-item">TOTAL PENGHASILAN</td>
      <td class="col-colon"></td>
      <td class="col-sub-val"></td>
      <td class="col-rp">Rp</td>
      <td class="col-val">{format_rupiah(emp['total_penghasilan'])}</td>
    </tr>
  </table>

  <!-- TERBILANG -->
  <div class="terbilang-box">
    <span>(</span>
    <span class="terbilang-text">{emp['terbilang']}</span>
    <span>)</span>
  </div>

  <!-- SIGNATURE -->
  <div class="sig-section">
    <div class="sig-date">{slip_date}</div>
    <div class="sig-title">{signer_title}</div>
    <div class="sig-image-box">
      {"<img src='" + sig_src + "' alt='Tanda Tangan' />" if sig_src else ""}
    </div>
    <hr class="sig-line" />
    <div class="sig-name">{signer_name}</div>
  </div>
</div>
{extra_wrap_close}
{extra_script}
</body>
</html>"""
    return html

def generate_pdf_from_html(html_content: str, output_pdf_path: str) -> bool:
    """
    Menggunakan Google Chrome headless bawaan MacOS untuk menghasilkan PDF
    yang 100% presisi dan identik dengan hasil browser.
    """
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        tmp_html_path = f.name
        f.write(html_content)

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        chrome_path = "google-chrome"

    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf_path}",
        f"file://{tmp_html_path}"
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        return os.path.exists(output_pdf_path) and os.path.getsize(output_pdf_path) > 0
    finally:
        if os.path.exists(tmp_html_path):
            os.remove(tmp_html_path)

def batch_generate_zip(employees: List[Dict[str, Any]], config: Dict[str, Any], output_zip_path: str) -> str:
    """
    Menghasilkan PDF untuk banyak karyawan dan mengemasnya dalam 1 file ZIP.
    Format nama file: Slip_Gaji_{Periode}_{Nama}.pdf
    """
    temp_dir = tempfile.mkdtemp()
    try:
        period_slug = config.get("period", "Bulan").replace(" ", "_")
        pdf_paths = []
        for emp in employees:
            safe_nama = re.sub(r'[^a-zA-Z0-9_\- ]', '', emp['nama']).strip()
            pdf_filename = f"Slip_Gaji_{period_slug}_{safe_nama}.pdf"
            pdf_path = os.path.join(temp_dir, pdf_filename)
            html = render_slip_html(emp, config)
            success = generate_pdf_from_html(html, pdf_path)
            if success:
                pdf_paths.append((pdf_path, pdf_filename))
        
        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for p_path, p_name in pdf_paths:
                zipf.write(p_path, p_name)
                
        return output_zip_path
    finally:
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass
