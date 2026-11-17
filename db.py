"""
Mahalliy baza (SQLite) — bitta fayl: data/sotuvchi.db

Ko'p mijozli rejim: har bir sotuvchiga tegishli yozuv `seller_id` bilan saqlanadi va
quyidagi funksiyalar FAQAT joriy sotuvchining (tenant.current_id()) ma'lumotini o'qiydi/yozadi.
Bu ajratishning yagona markaziy joyi — boshqa modullar seller_id ni o'zi uzatmaydi.

Jadvallar:
  sellers          — sotuvchilar (Telegram chat, shifrlangan Uzum kaliti, demo belgisi)
  seller_costs     — tannarx va qo'shimcha xarajat (sotuvchi + SKU)
  price_proposals  — narx takliflari
  cards            — AI kartochkalar
  settings         — sozlamalar; sotuvchiniki "s{id}:kalit" ko'rinishida
  login_tokens     — veb-panelga bir martalik kirish havolalari
"""
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sellers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_chat_id TEXT UNIQUE,
    name TEXT,
    token_enc TEXT,
    demo INTEGER DEFAULT 0,
    created INTEGER,
    last_seen INTEGER
);
CREATE TABLE IF NOT EXISTS seller_costs (
    seller_id INTEGER NOT NULL,
    sku_id INTEGER NOT NULL,
    title TEXT,
    unit_cost REAL DEFAULT 0,      -- tovarning o'zi necha puldan olingan (1 dona)
    extra_cost REAL DEFAULT 0,     -- yetkazib kelish, qadoqlash va h.k. (1 dona)
    updated INTEGER,
    PRIMARY KEY (seller_id, sku_id)
);
CREATE TABLE IF NOT EXISTS price_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER, product_id INTEGER, sku_id INTEGER, title TEXT,
    old_price INTEGER, new_price INTEGER, full_price INTEGER,
    min_price INTEGER, reason TEXT,
    status TEXT DEFAULT 'pending',  -- pending / approved / rejected / failed
    error TEXT, created INTEGER, decided INTEGER
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created INTEGER, name TEXT, input_json TEXT, result_json TEXT,
    photo_path TEXT, infographic_path TEXT
);
CREATE TABLE IF NOT EXISTS login_tokens (
    token TEXT PRIMARY KEY, seller_id INTEGER, expires INTEGER, used INTEGER DEFAULT 0
);
"""

_GLOBAL_KEYS = {"schema_version"}


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _sid():
    import tenant  # aylanma importdan qochish uchun
    return tenant.current_id()


def _columns(c, table):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        for table in ("price_proposals", "cards"):
            if "seller_id" not in _columns(c, table):
                c.execute(f"ALTER TABLE {table} ADD COLUMN seller_id INTEGER DEFAULT 1")
        ver = c.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
        if not ver:
            _migrate_v1(c)
            c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('schema_version','2')")


def _migrate_v1(c):
    """Bitta-egalik bazasidan ko'chirish: eski ma'lumot sotuvchi #1 (ega) ga beriladi."""
    old_owner = c.execute("SELECT value FROM settings WHERE key='tg_owner'").fetchone()
    chat = (old_owner["value"] if old_owner else None) or config.TELEGRAM_OWNER_ID or None
    if not c.execute("SELECT 1 FROM sellers WHERE id=1").fetchone():
        c.execute("INSERT INTO sellers(id, tg_chat_id, name, demo, created) VALUES(1, ?, 'Ega', 0, ?)",
                  (str(chat) if chat else None, int(time.time())))
    if "costs" in {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        c.execute("""INSERT OR IGNORE INTO seller_costs(seller_id, sku_id, title, unit_cost, extra_cost, updated)
                     SELECT 1, sku_id, title, unit_cost, extra_cost, updated FROM costs""")
    for r in c.execute("SELECT key, value FROM settings").fetchall():
        k = r["key"]
        if ":" not in k and k not in _GLOBAL_KEYS and k != "tg_owner":
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (f"s1:{k}", r["value"]))


# ---------- sotuvchilar ----------
def get_seller(seller_id):
    with conn() as c:
        r = c.execute("SELECT * FROM sellers WHERE id=?", (int(seller_id),)).fetchone()
    return dict(r) if r else None


def get_seller_by_chat(chat_id):
    with conn() as c:
        r = c.execute("SELECT * FROM sellers WHERE tg_chat_id=?", (str(chat_id),)).fetchone()
    return dict(r) if r else None


def create_seller(chat_id=None, name=None, demo=0):
    with conn() as c:
        cur = c.execute("INSERT INTO sellers(tg_chat_id, name, demo, created, last_seen) VALUES(?,?,?,?,?)",
                        (str(chat_id) if chat_id else None, name, int(demo), int(time.time()), int(time.time())))
        return cur.lastrowid


_SELLER_FIELDS = {"tg_chat_id", "name", "token_enc", "demo", "last_seen"}


def update_seller(seller_id, **fields):
    fields = {k: v for k, v in fields.items() if k in _SELLER_FIELDS}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE sellers SET {sets} WHERE id=?", (*fields.values(), int(seller_id)))


def list_sellers():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM sellers ORDER BY id")]


def wipe_seller(seller_id):
    """Sotuvchi ma'lumotini butunlay o'chiradi (/uzish). Ega (#1) qatori qoladi, faqat kaliti tozalanadi."""
    sid = int(seller_id)
    with conn() as c:
        for table in ("seller_costs", "price_proposals", "cards", "login_tokens"):
            c.execute(f"DELETE FROM {table} WHERE seller_id=?", (sid,))
        c.execute("DELETE FROM settings WHERE key LIKE ?", (f"s{sid}:%",))
        if sid == 1:
            c.execute("UPDATE sellers SET token_enc=NULL, demo=0 WHERE id=1")
        else:
            c.execute("DELETE FROM sellers WHERE id=?", (sid,))


# ---------- veb-panelga kirish havolalari ----------
def create_login_token(seller_id, ttl=900):
    tok = secrets.token_urlsafe(24)
    with conn() as c:
        c.execute("DELETE FROM login_tokens WHERE expires < ?", (int(time.time()),))
        c.execute("INSERT INTO login_tokens(token, seller_id, expires) VALUES(?,?,?)",
                  (tok, int(seller_id), int(time.time()) + ttl))
    return tok


def use_login_token(tok):
    """Bir martalik: to'g'ri va muddati o'tmagan bo'lsa seller_id, aks holda None."""
    with conn() as c:
        r = c.execute("SELECT * FROM login_tokens WHERE token=?", (tok,)).fetchone()
        if not r or r["used"] or r["expires"] < time.time():
            return None
        c.execute("UPDATE login_tokens SET used=1 WHERE token=?", (tok,))
        return r["seller_id"]


# ---------- sozlamalar (joriy sotuvchi) ----------
def _skey(key):
    return f"s{_sid()}:{key}"


def get_setting(key, default=None):
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (_skey(key),)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (_skey(key), str(value)))


def get_float_setting(key, default):
    try:
        return float(get_setting(key, default))
    except (TypeError, ValueError):
        return default


# ---------- tannarx (joriy sotuvchi) ----------
def get_costs():
    with conn() as c:
        return {r["sku_id"]: dict(r) for r in c.execute("SELECT * FROM seller_costs WHERE seller_id=?", (_sid(),))}


def set_cost(sku_id, unit_cost, extra_cost=0, title=None):
    with conn() as c:
        c.execute("""INSERT INTO seller_costs(seller_id,sku_id,title,unit_cost,extra_cost,updated) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(seller_id, sku_id) DO UPDATE SET unit_cost=excluded.unit_cost,
                     extra_cost=excluded.extra_cost, title=COALESCE(excluded.title, seller_costs.title),
                     updated=excluded.updated""",
                  (_sid(), int(sku_id), title, float(unit_cost), float(extra_cost), int(time.time())))


# ---------- narx takliflari (joriy sotuvchi) ----------
def add_proposal(**kw):
    sid = _sid()
    with conn() as c:
        # shu SKU bo'yicha eski kutilayotgan taklifni almashtiramiz
        c.execute("DELETE FROM price_proposals WHERE seller_id=? AND sku_id=? AND status='pending'", (sid, kw["sku_id"]))
        cur = c.execute("""INSERT INTO price_proposals(seller_id,shop_id,product_id,sku_id,title,old_price,new_price,
                           full_price,min_price,reason,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (sid, kw["shop_id"], kw["product_id"], kw["sku_id"], kw["title"], kw["old_price"],
                         kw["new_price"], kw["full_price"], kw["min_price"], kw["reason"], int(time.time())))
        return cur.lastrowid


def list_proposals(status=None, limit=100):
    sid = _sid()
    with conn() as c:
        if status:
            rows = c.execute("SELECT * FROM price_proposals WHERE seller_id=? AND status=? ORDER BY id DESC LIMIT ?",
                             (sid, status, limit))
        else:
            rows = c.execute("SELECT * FROM price_proposals WHERE seller_id=? ORDER BY id DESC LIMIT ?", (sid, limit))
        return [dict(r) for r in rows]


def get_proposal(pid):
    with conn() as c:
        r = c.execute("SELECT * FROM price_proposals WHERE id=? AND seller_id=?", (pid, _sid())).fetchone()
    return dict(r) if r else None


def set_proposal_status(pid, status, error=None):
    with conn() as c:
        c.execute("UPDATE price_proposals SET status=?, error=?, decided=? WHERE id=? AND seller_id=?",
                  (status, error, int(time.time()), pid, _sid()))


# ---------- kartochkalar (joriy sotuvchi) ----------
def add_card(name, input_data, result, photo_path, infographic_path):
    with conn() as c:
        cur = c.execute("""INSERT INTO cards(seller_id,created,name,input_json,result_json,photo_path,infographic_path)
                           VALUES(?,?,?,?,?,?,?)""",
                        (_sid(), int(time.time()), name, json.dumps(input_data, ensure_ascii=False),
                         json.dumps(result, ensure_ascii=False), photo_path, infographic_path))
        return cur.lastrowid


def _card(r):
    d = dict(r)
    d["input"] = json.loads(d.pop("input_json") or "{}")
    d["result"] = json.loads(d.pop("result_json") or "{}")
    return d


def list_cards(limit=50):
    with conn() as c:
        rows = c.execute("SELECT * FROM cards WHERE seller_id=? ORDER BY id DESC LIMIT ?", (_sid(), limit))
        return [_card(r) for r in rows]


def get_card(cid):
    with conn() as c:
        r = c.execute("SELECT * FROM cards WHERE id=? AND seller_id=?", (cid, _sid())).fetchone()
    return _card(r) if r else None


def card_file_owner(filename):
    """Rasm fayli qaysi sotuvchiga tegishli (veb-panel /files uchun)."""
    like = f"%{filename}"
    with conn() as c:
        r = c.execute("SELECT seller_id FROM cards WHERE infographic_path LIKE ? OR photo_path LIKE ?",
                      (like, like)).fetchone()
    return r["seller_id"] if r else None


init()
