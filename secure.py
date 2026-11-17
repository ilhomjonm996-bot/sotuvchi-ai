"""
Sotuvchilarning Uzum API kalitlarini shifrlash (Fernet: AES-128-CBC + HMAC).

Shifrlash kaliti:
  1) .env dagi SECRET_ENC_KEY (serverda shu yo'l tavsiya qilinadi), yoki
  2) birinchi ishga tushishda data/secret.key fayliga yaratiladi.
Kalit yo'qolsa, saqlangan tokenlarni ochib bo'lmaydi — sotuvchilar qayta ulaydi.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

import config

_KEY_FILE = config.DATA_DIR / "secret.key"
_fernet = None


def _key():
    env = os.environ.get("SECRET_ENC_KEY", "").strip()
    if env:
        return env.encode()
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    try:
        os.chmod(_KEY_FILE, 0o600)
    except OSError:
        pass
    return key


def _f():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_key())
    return _fernet


def encrypt(text: str) -> str:
    return _f().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _f().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return ""


def mask(token: str) -> str:
    """Logda ko'rsatish uchun: abcd…wxyz"""
    t = token or ""
    return f"{t[:4]}…{t[-4:]}" if len(t) > 10 else "***"
