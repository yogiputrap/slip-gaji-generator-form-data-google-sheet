"""Link berbagi slip (untuk WhatsApp) tanpa database.

Setiap link = token acak 192-bit (tidak bisa ditebak/di-enumerasi) yang menunjuk ke satu
file PDF di folder data. Metadata (pemilik, kedaluwarsa) disimpan di index.json.

Env:
  SHARE_TTL_DAYS  masa berlaku link dalam hari (default 30)
"""
import json
import os
import re
import secrets
import shutil
import threading
import time
from typing import Optional, Tuple

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
_lock = threading.Lock()


def ttl_seconds() -> int:
    try:
        return int(float(os.environ.get("SHARE_TTL_DAYS", "30")) * 86400)
    except ValueError:
        return 30 * 86400


def _index_path(share_dir: str) -> str:
    return os.path.join(share_dir, "index.json")


def _load(share_dir: str) -> dict:
    try:
        with open(_index_path(share_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(share_dir: str, data: dict) -> None:
    tmp = _index_path(share_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, _index_path(share_dir))


def _pdf_path(share_dir: str, token: str) -> str:
    return os.path.join(share_dir, f"{token}.pdf")


def _drop(share_dir: str, data: dict, token: str) -> None:
    data.pop(token, None)
    try:
        os.remove(_pdf_path(share_dir, token))
    except OSError:
        pass


def _prune(share_dir: str, data: dict) -> None:
    now = time.time()
    for token in [t for t, m in data.items() if m.get("exp", 0) <= now]:
        _drop(share_dir, data, token)


def create(share_dir: str, key: str, filename: str, pdf_src: str) -> Tuple[str, int]:
    """Buat/segarkan link untuk `key` (mis. 'periode|nama'). Token lama dipakai ulang
    agar link yang sudah dibagikan tetap valid dan menampilkan slip terbaru."""
    os.makedirs(share_dir, exist_ok=True)
    with _lock:
        data = _load(share_dir)
        _prune(share_dir, data)
        token = next((t for t, m in data.items() if m.get("key") == key), None) or secrets.token_urlsafe(24)
        shutil.copyfile(pdf_src, _pdf_path(share_dir, token))
        exp = int(time.time()) + ttl_seconds()
        data[token] = {"key": key, "filename": filename, "exp": exp}
        _save(share_dir, data)
    return token, exp


def resolve(share_dir: str, token: str) -> Optional[Tuple[str, str]]:
    """Kembalikan (path_pdf, nama_file) bila token valid dan belum kedaluwarsa."""
    if not TOKEN_RE.match(token or ""):
        return None
    with _lock:
        data = _load(share_dir)
        meta = data.get(token)
        if not meta:
            return None
        if meta.get("exp", 0) <= time.time():
            _drop(share_dir, data, token)
            _save(share_dir, data)
            return None
        path = _pdf_path(share_dir, token)
        if not os.path.isfile(path):
            return None
        return path, meta.get("filename", "slip-gaji.pdf")


def revoke(share_dir: str, key: Optional[str] = None) -> int:
    """Cabut link untuk satu `key`, atau semua bila key=None. Mengembalikan jumlah yang dicabut."""
    with _lock:
        data = _load(share_dir)
        targets = [t for t, m in data.items() if key is None or m.get("key") == key]
        for t in targets:
            _drop(share_dir, data, t)
        if targets:
            _save(share_dir, data)
        return len(targets)
