import os
import re
import io
import json
import base64
import tempfile
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import generator

app = FastAPI(title="Auto Slip Gaji Generator")

# Pastikan direktori tersedia
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# State konfigurasi default
CURRENT_CONFIG = {
    "sheet_url": "",
    "logo_path": os.path.join(ASSETS_DIR, "logo_default.png"),
    "logo_data_uri": "",
    "signature_path": "",
    "signature_data_uri": "",
    "company_title": "SLIP GAJI",
    "company_subtitle": "KARYAWAN SESAR LEMBANG KALCER",
    "company_address": "Jl. Cigadung Raya Barat No. 18, Bandung",
    "period": "September 2026",
    "slip_date": "Bandung, 29 September 2026",
    "signer_title": "Bagian Keuangan,",
    "signer_name": "Reza Fauzi",
    "label_2a": "Tunjangan Kehadiran",
    "label_2b": "Bonus Kehadiran",
    "label_2c": "Lembur/Tunj.Hadir Kary. WFA",
    "label_2d": "Bonus Kinerja SLK",
    "label_2e": "Lain-Lain"
}

# Cache karyawan saat ini (kosong pada startup, tidak auto-fetch)
CACHED_EMPLOYEES = []

class ConfigUpdate(BaseModel):
    company_title: Optional[str] = None
    company_subtitle: Optional[str] = None
    company_address: Optional[str] = None
    period: Optional[str] = None
    slip_date: Optional[str] = None
    signer_title: Optional[str] = None
    signer_name: Optional[str] = None

class GenerateBatchRequest(BaseModel):
    ids: List[int]
    config: Optional[dict] = None

@app.get("/api/config")
def get_config():
    # Sertakan preview logo & tanda tangan saat ini dalam base64
    logo_b64 = CURRENT_CONFIG.get("logo_data_uri") or generator.get_base64_image(CURRENT_CONFIG.get("logo_path", ""))
    sig_b64 = CURRENT_CONFIG.get("signature_data_uri") or generator.get_base64_image(CURRENT_CONFIG.get("signature_path", ""))
    
    cfg = dict(CURRENT_CONFIG)
    cfg["logo_preview"] = logo_b64
    cfg["signature_preview"] = sig_b64
    return cfg

@app.post("/api/config")
def update_config(data: ConfigUpdate):
    for k, v in data.dict(exclude_unset=True).items():
        if v is not None:
            CURRENT_CONFIG[k] = v
    return {"status": "success", "config": CURRENT_CONFIG}

@app.post("/api/fetch-sheet")
def fetch_sheet(url: Optional[str] = Form(None)):
    global CACHED_EMPLOYEES
    target_url = (url or "").strip() or CURRENT_CONFIG.get("sheet_url", "").strip()
    if not target_url:
        raise HTTPException(status_code=400, detail="URL Google Sheet belum diisi")
    try:
        res = generator.fetch_data_from_sheet(target_url)
        if isinstance(res, tuple) and len(res) == 3:
            employees, period, slip_date = res
        else:
            employees, period, slip_date = res, "", ""
        CACHED_EMPLOYEES = employees
        CURRENT_CONFIG["sheet_url"] = target_url
        if period:
            CURRENT_CONFIG["period"] = period
        if slip_date:
            CURRENT_CONFIG["slip_date"] = slip_date
        stats = calculate_stats(employees)
        return {
            "status": "success",
            "count": len(employees),
            "employees": employees,
            "stats": stats,
            "config": CURRENT_CONFIG
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mengambil data dari Google Sheet: {str(e)}")

@app.post("/api/upload-sheet")
async def upload_sheet(file: UploadFile = File(...)):
    global CACHED_EMPLOYEES
    try:
        suffix = os.path.splitext(file.filename)[1].lower()
        if suffix not in [".xlsx", ".xls"]:
            raise HTTPException(status_code=400, detail="Format file harus .xlsx")
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            res = generator.fetch_data_from_sheet(tmp_path)
            if isinstance(res, tuple) and len(res) == 3:
                employees, period, slip_date = res
            else:
                employees, period, slip_date = res, "", ""
            CACHED_EMPLOYEES = employees
            if period:
                CURRENT_CONFIG["period"] = period
            if slip_date:
                CURRENT_CONFIG["slip_date"] = slip_date
            stats = calculate_stats(employees)
            return {
                "status": "success",
                "count": len(employees),
                "employees": employees,
                "stats": stats,
                "config": CURRENT_CONFIG
            }
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses file spreadsheet: {str(e)}")

@app.post("/api/upload-logo")
async def upload_logo(file: UploadFile = File(...)):
    try:
        content = await file.read()
        ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        mime = f"image/{ext}" if ext != "svg" else "image/svg+xml"
        b64 = f"data:{mime};base64,{base64.b64encode(content).decode('utf-8')}"
        CURRENT_CONFIG["logo_data_uri"] = b64
        # Simpan juga ke assets
        custom_logo_path = os.path.join(ASSETS_DIR, f"custom_logo{os.path.splitext(file.filename)[1]}")
        with open(custom_logo_path, "wb") as f:
            f.write(content)
        CURRENT_CONFIG["logo_path"] = custom_logo_path
        return {"status": "success", "logo_preview": b64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal upload logo: {str(e)}")

@app.post("/api/reset-logo")
def reset_logo():
    default_path = os.path.join(ASSETS_DIR, "logo_default.png")
    CURRENT_CONFIG["logo_data_uri"] = ""
    CURRENT_CONFIG["logo_path"] = default_path
    b64 = generator.get_base64_image(default_path)
    return {"status": "success", "logo_preview": b64}

@app.post("/api/upload-signature")
async def upload_signature(file: UploadFile = File(...)):
    try:
        content = await file.read()
        ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        mime = f"image/{ext}" if ext != "svg" else "image/svg+xml"
        b64 = f"data:{mime};base64,{base64.b64encode(content).decode('utf-8')}"
        CURRENT_CONFIG["signature_data_uri"] = b64
        custom_sig_path = os.path.join(ASSETS_DIR, f"custom_signature{os.path.splitext(file.filename)[1]}")
        with open(custom_sig_path, "wb") as f:
            f.write(content)
        CURRENT_CONFIG["signature_path"] = custom_sig_path
        return {"status": "success", "signature_preview": b64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal upload tanda tangan: {str(e)}")

@app.post("/api/clear-signature")
def clear_signature():
    CURRENT_CONFIG["signature_data_uri"] = ""
    CURRENT_CONFIG["signature_path"] = ""
    return {"status": "success", "signature_preview": ""}

def calculate_stats(employees):
    return {
        "total_karyawan": len(employees),
        "total_thp": sum(e.get("total_penghasilan", 0) for e in employees),
        "total_pokok": sum(e.get("gaji_pokok", 0) for e in employees),
        "total_bonus": sum(e.get("penerimaan_kotor", 0) - e.get("gaji_pokok", 0) for e in employees),
        "total_potongan": sum(e.get("total_potongan", 0) for e in employees),
    }

@app.get("/api/employees")
def list_employees():
    global CACHED_EMPLOYEES
    stats = calculate_stats(CACHED_EMPLOYEES)
    return {"count": len(CACHED_EMPLOYEES), "employees": CACHED_EMPLOYEES, "stats": stats}

@app.get("/api/preview-html/{emp_id}")
def preview_html(emp_id: int):
    global CACHED_EMPLOYEES
    emp = next((e for e in CACHED_EMPLOYEES if e["id"] == emp_id), None)
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    
    html = generator.render_slip_html(emp, CURRENT_CONFIG, preview_mode=True)
    return HTMLResponse(content=html)

@app.get("/api/download-pdf/{emp_id}")
def download_pdf(emp_id: int):
    global CACHED_EMPLOYEES
    emp = next((e for e in CACHED_EMPLOYEES if e["id"] == emp_id), None)
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    
    period_slug = CURRENT_CONFIG.get("period", "Bulan").replace(" ", "_")
    safe_nama = re.sub(r'[^a-zA-Z0-9_\- ]', '', emp['nama']).strip()
    filename = f"Slip_Gaji_{period_slug}_{safe_nama}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    html = generator.render_slip_html(emp, CURRENT_CONFIG)
    ok = generator.generate_pdf_from_html(html, output_path)
    if not ok:
        raise HTTPException(status_code=500, detail="Gagal mengenerate file PDF")
    
    return FileResponse(path=output_path, filename=filename, media_type="application/pdf")

@app.post("/api/download-zip")
def download_batch_zip(req: GenerateBatchRequest):
    global CACHED_EMPLOYEES
    selected = [e for e in CACHED_EMPLOYEES if e["id"] in req.ids]
    if not selected:
        raise HTTPException(status_code=400, detail="Tidak ada karyawan yang dipilih")
    
    config = dict(CURRENT_CONFIG)
    if req.config:
        config.update(req.config)
        
    period_slug = config.get("period", "Bulan").replace(" ", "_")
    zip_filename = f"Kumpulan_Slip_Gaji_{period_slug}.zip"
    zip_path = os.path.join(OUTPUT_DIR, zip_filename)
    
    generator.batch_generate_zip(selected, config, zip_path)
    return FileResponse(path=zip_path, filename=zip_filename, media_type="application/zip")

# Serve UI Single Page Application
@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(BASE_DIR, "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Template index.html belum ditemukan</h1>"
