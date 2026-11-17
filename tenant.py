"""
Ko'p mijozli rejim: "hozir kimning ma'lumoti bilan ishlayapmiz" — joriy sotuvchi konteksti.

  with tenant.use(seller_id):
      profit.report(...)        # faqat shu sotuvchining do'koni, tannarxi, takliflari

Bot har bir xabarda, veb-panel har bir so'rovda kontekstni o'rnatadi. Baza (db.py) va
hisob-kitob (profit.py) faqat joriy sotuvchi ma'lumotini o'qiydi/yozadi — ajratish bitta joyda.

Sotuvchi #1 — loyiha egasi (eski bitta-egalik rejimi): kaliti .env dan olinishi mumkin.
Kontekst o'rnatilmagan skriptlar (estimate_costs.py, testlar) sotuvchi #1 bilan ishlaydi.
"""
import contextvars
import hashlib
import threading
from contextlib import contextmanager

import config
import db
import secure
from uzum_client import UzumClient

OWNER_ID = 1
_current = contextvars.ContextVar("seller_id", default=None)
_clients = {}
_lock = threading.Lock()


def current_id() -> int:
    v = _current.get()
    return OWNER_ID if v is None else v


def set_current(seller_id):
    return _current.set(int(seller_id))


def reset(token):
    _current.reset(token)


@contextmanager
def use(seller_id):
    tok = set_current(seller_id)
    try:
        yield
    finally:
        reset(tok)


def seller(seller_id=None):
    return db.get_seller(seller_id or current_id())


def token(seller_id=None) -> str:
    s = seller(seller_id)
    if not s:
        return ""
    if s.get("token_enc"):
        return secure.decrypt(s["token_enc"])
    if s["id"] == OWNER_ID:
        return config.UZUM_API_TOKEN
    return ""


def is_demo(seller_id=None) -> bool:
    s = seller(seller_id)
    if not s:
        return True
    if s["id"] == OWNER_ID and not s.get("token_enc"):
        return config.DEMO_MODE  # eski rejim: .env bo'yicha
    return bool(s.get("demo")) and not s.get("token_enc")


def connected(seller_id=None) -> bool:
    return is_demo(seller_id) or bool(token(seller_id))


def client(seller_id=None) -> UzumClient:
    """Har bir sotuvchiga alohida Uzum klienti (o'z tokeni va o'z so'rov tezligi bilan)."""
    sid = seller_id or current_id()
    tok, demo = token(sid), is_demo(sid)
    fingerprint = hashlib.sha256(f"{tok}|{demo}".encode()).hexdigest()
    with _lock:
        c = _clients.get(sid)
        if c is None or c[0] != fingerprint:
            c = (fingerprint, UzumClient(token=tok, demo=demo))
            _clients[sid] = c
        return c[1]


def forget(seller_id):
    with _lock:
        _clients.pop(int(seller_id), None)
