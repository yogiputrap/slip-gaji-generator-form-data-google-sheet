"""Autentikasi sederhana tanpa database: kredensial dibaca dari environment.

Env:
  AUTH_USERNAME      username login (wajib)
  AUTH_PASSWORD      password login (wajib)
  AUTH_SECRET        kunci penanda tangan cookie sesi (disarankan; jika kosong
                     dibuat acak tiap start sehingga sesi hangus saat restart)
  AUTH_SESSION_HOURS lama sesi dalam jam (default 12)
"""
import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Dict, List, Optional

COOKIE_NAME = "slip_session"
MAX_FAILS = 5
LOCK_SECONDS = 60

_fallback_secret = secrets.token_bytes(32)
_fails: Dict[str, List[float]] = {}


def _username() -> str:
    return os.environ.get("AUTH_USERNAME", "")


def _password() -> str:
    return os.environ.get("AUTH_PASSWORD", "")


def _secret() -> bytes:
    s = os.environ.get("AUTH_SECRET", "")
    return s.encode("utf-8") if s else _fallback_secret


def session_seconds() -> int:
    try:
        return int(float(os.environ.get("AUTH_SESSION_HOURS", "12")) * 3600)
    except ValueError:
        return 12 * 3600


def is_configured() -> bool:
    return bool(_username() and _password())


def check_credentials(username: str, password: str) -> bool:
    """Bandingkan dengan waktu konstan; kedua field selalu dicek."""
    if not is_configured():
        return False
    user_ok = hmac.compare_digest(username.encode("utf-8"), _username().encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), _password().encode("utf-8"))
    return user_ok and pass_ok


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_token() -> str:
    payload = base64.urlsafe_b64encode(
        f"{_username()}|{int(time.time()) + session_seconds()}".encode("utf-8")
    ).decode("ascii")
    return f"{payload}.{_sign(payload)}"


def verify_token(token: Optional[str]) -> bool:
    if not token or not is_configured() or "." not in token:
        return False
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        username, exp = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8").split("|")
        return int(exp) > time.time() and hmac.compare_digest(
            username.encode("utf-8"), _username().encode("utf-8")
        )
    except (ValueError, UnicodeDecodeError):
        return False


def is_locked(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _fails.get(ip, []) if now - t < LOCK_SECONDS]
    _fails[ip] = recent
    return len(recent) >= MAX_FAILS


def record_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str) -> None:
    _fails.pop(ip, None)
