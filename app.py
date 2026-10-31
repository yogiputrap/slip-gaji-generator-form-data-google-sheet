import os
import re
import io
import json
import base64
import shutil
import tempfile
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import generator
import auth
import share

app = FastAPI(title="Auto Slip Gaji Generator")

# Pastikan direktori tersedia
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR: lokasi data yang bisa ditulis (unggahan logo/TTD, hasil PDF). Saat deploy (Docker/Dokploy)
# arahkan ke volume persisten, mis. /data. Default: folder proyek (pengembangan lokal).
DATA_DIR = os.environ.get("DATA_DIR", "").strip() or BASE_DIR
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
SHARE_DIR = os.path.join(DATA_DIR, "shared")
BUNDLED_ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Salin aset bawaan (logo default dll.) ke volume data bila belum ada; file yang sudah ada tidak ditimpa
if os.path.abspath(ASSETS_DIR) != os.path.abspath(BUNDLED_ASSETS_DIR) and os.path.isdir(BUNDLED_ASSETS_DIR):
    for _name in os.listdir(BUNDLED_ASSETS_DIR):
        _src, _dst = os.path.join(BUNDLED_ASSETS_DIR, _name), os.path.join(ASSETS_DIR, _name)
        if os.path.isfile(_src) and not os.path.exists(_dst):
            shutil.copy2(_src, _dst)
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ─── Autentikasi (kredensial dari env, tanpa database) ───
# Hanya halaman login dan logonya yang publik; /assets lain (mis. tanda tangan) tetap terkunci.
PUBLIC_PATHS = {"/login", "/assets/logo_default.png"}

if not auth.is_configured():
    print("[PERINGATAN] AUTH_USERNAME/AUTH_PASSWORD belum di-set: login ditolak, dashboard tidak bisa diakses.")

@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    # /s/<token>: link berbagi slip (token acak, lihat share.py); sisanya wajib login
    if path in PUBLIC_PATHS or path.startswith("/s/") or auth.verify_token(request.cookies.get(auth.COOKIE_NAME)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Belum login"}, status_code=401)
    return RedirectResponse("/login", status_code=303)

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if auth.verify_token(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/", status_code=303)
    with open(os.path.join(BASE_DIR, "templates", "login.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-store"})

@app.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form("")):
    ip = _client_ip(request)
    if not auth.is_configured():
        return RedirectResponse("/login?e=3", status_code=303)
    if auth.is_locked(ip):
        return RedirectResponse("/login?e=2", status_code=303)
    if not auth.check_credentials(username, password):
        auth.record_fail(ip)
        return RedirectResponse("/login?e=1", status_code=303)
    auth.clear_fails(ip)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        auth.COOKIE_NAME, auth.make_token(),
        max_age=auth.session_seconds(), httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
    )
    return resp

@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp

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
    "label_2a": "Tunjangan Jabatan",
    "label_2b": "Bonus Kehadiran",
    "label_2c": "Lembur",
    "label_2d": "Bonus Kinerja SLK",
    "label_2e": "Lain-Lain",
    "template": "default"
}

# Cache karyawan saat ini (kosong pada startup, tidak auto-fetch)
CACHED_EMPLOYEES = []

class ConfigUpdate(BaseModel):
    template: Optional[str] = None
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
        # Nama unik per file agar tanda tangan lama tidak tertimpa dan bisa dipilih lagi
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(os.path.basename(file.filename))[0]).strip("_")
        stem = re.sub(r"^custom_signature_?", "", stem) or "ttd"
        custom_sig_path = os.path.join(ASSETS_DIR, f"{SIGNATURE_PREFIX}_{stem}{os.path.splitext(file.filename)[1].lower()}")
        with open(custom_sig_path, "wb") as f:
            f.write(content)
        CURRENT_CONFIG["signature_path"] = custom_sig_path
        return {"status": "success", "signature_preview": b64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal upload tanda tangan: {str(e)}")

SIGNATURE_PREFIX = "custom_signature"
SIGNATURE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")

def _list_signature_files() -> List[str]:
    return sorted(
        f for f in os.listdir(ASSETS_DIR)
        if f.startswith(SIGNATURE_PREFIX) and f.lower().endswith(SIGNATURE_EXTS)
    )

@app.get("/api/signatures")
def list_signatures():
    current = os.path.basename(CURRENT_CONFIG.get("signature_path", ""))
    return {
        "signatures": [
            {"name": f, "url": f"/assets/{f}", "selected": f == current}
            for f in _list_signature_files()
        ]
    }

@app.post("/api/select-signature")
def select_signature(name: str = Form(...)):
    # Hanya nama file yang ada di daftar assets (cegah path traversal)
    if name not in _list_signature_files():
        raise HTTPException(status_code=404, detail="Tanda tangan tidak ditemukan di folder assets")
    path = os.path.join(ASSETS_DIR, name)
    CURRENT_CONFIG["signature_data_uri"] = ""
    CURRENT_CONFIG["signature_path"] = path
    return {"status": "success", "signature_preview": generator.get_base64_image(path), "name": name}

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

def _share_key(emp: dict) -> str:
    return f"{CURRENT_CONFIG.get('period', '')}|{emp['nama']}".lower()

def _build_slip_pdf(emp: dict):
    period_slug = CURRENT_CONFIG.get("period", "Bulan").replace(" ", "_")
    safe_nama = re.sub(r'[^a-zA-Z0-9_\- ]', '', emp['nama']).strip()
    filename = f"Slip_Gaji_{period_slug}_{safe_nama}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    html = generator.render_slip_html(emp, CURRENT_CONFIG)
    if not generator.generate_pdf_from_html(html, output_path):
        raise HTTPException(status_code=500, detail="Gagal mengenerate file PDF")
    return output_path, filename

@app.post("/api/share/{emp_id}")
def create_share_link(emp_id: int, request: Request):
    emp = next((e for e in CACHED_EMPLOYEES if e["id"] == emp_id), None)
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    pdf_path, filename = _build_slip_pdf(emp)
    token, exp = share.create(SHARE_DIR, _share_key(emp), filename, pdf_path)
    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}/s/{token}", "expires_at": exp, "ttl_days": round(share.ttl_seconds() / 86400)}

@app.delete("/api/share/{emp_id}")
def revoke_share_link(emp_id: int):
    emp = next((e for e in CACHED_EMPLOYEES if e["id"] == emp_id), None)
    if not emp:
        raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
    return {"revoked": share.revoke(SHARE_DIR, _share_key(emp))}

@app.delete("/api/share")
def revoke_all_share_links():
    return {"revoked": share.revoke(SHARE_DIR)}

@app.get("/s/{token}")
def open_shared_slip(token: str, request: Request):
    ip = "share:" + _client_ip(request)
    if auth.is_locked(ip):
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan, coba lagi nanti")
    found = share.resolve(SHARE_DIR, token)
    if not found:
        auth.record_fail(ip)
        raise HTTPException(status_code=404, detail="Link tidak valid atau sudah kedaluwarsa")
    path, filename = found
    return FileResponse(
        path, media_type="application/pdf", filename=filename, content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"},
    )

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
