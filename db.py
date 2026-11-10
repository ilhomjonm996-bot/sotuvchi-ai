"""
Mahalliy baza (SQLite) — bitta fayl: data/sotuvchi.db

Bu yerda Uzum bermaydigan ma'lumotlar saqlanadi:
- har bir tovarning tannarxi va yetkazib kelish xarajati
- narx takliflari (tasdiqlangan / rad etilgan)
- AI yaratgan kartochkalar
- sozlamalar
"""
import json
import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS costs (
    sku_id INTEGER PRIMARY KEY,
    title TEXT,
    unit_cost REAL DEFAULT 0,      -- tovarning o'zi necha puldan olingan (1 dona)
    extra_cost REAL DEFAULT 0,     -- yetkazib kelish, qadoqlash va h.k. (1 dona)
    updated INTEGER
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
"""


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


# ---------- sozlamalar ----------
def get_setting(key, default=None):
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))


def get_float_setting(key, default):
    try:
        return float(get_setting(key, default))
    except (TypeError, ValueError):
        return default


# ---------- tannarx ----------
def get_costs():
    with conn() as c:
        return {r["sku_id"]: dict(r) for r in c.execute("SELECT * FROM costs")}


def set_cost(sku_id, unit_cost, extra_cost=0, title=None):
    with conn() as c:
        c.execute("""INSERT INTO costs(sku_id,title,unit_cost,extra_cost,updated) VALUES(?,?,?,?,?)
                     ON CONFLICT(sku_id) DO UPDATE SET unit_cost=excluded.unit_cost,
                     extra_cost=excluded.extra_cost, title=COALESCE(excluded.title, costs.title),
                     updated=excluded.updated""",
                  (int(sku_id), title, float(unit_cost), float(extra_cost), int(time.time())))


# ---------- narx takliflari ----------
def add_proposal(**kw):
    with conn() as c:
        # shu SKU bo'yicha eski kutilayotgan taklifni almashtiramiz
        c.execute("DELETE FROM price_proposals WHERE sku_id=? AND status='pending'", (kw["sku_id"],))
        cur = c.execute("""INSERT INTO price_proposals(shop_id,product_id,sku_id,title,old_price,new_price,
                           full_price,min_price,reason,created) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (kw["shop_id"], kw["product_id"], kw["sku_id"], kw["title"], kw["old_price"],
                         kw["new_price"], kw["full_price"], kw["min_price"], kw["reason"], int(time.time())))
        return cur.lastrowid


def list_proposals(status=None, limit=100):
    with conn() as c:
        if status:
            rows = c.execute("SELECT * FROM price_proposals WHERE status=? ORDER BY id DESC LIMIT ?",
                             (status, limit))
        else:
            rows = c.execute("SELECT * FROM price_proposals ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]


def get_proposal(pid):
    with conn() as c:
        r = c.execute("SELECT * FROM price_proposals WHERE id=?", (pid,)).fetchone()
    return dict(r) if r else None


def set_proposal_status(pid, status, error=None):
    with conn() as c:
        c.execute("UPDATE price_proposals SET status=?, error=?, decided=? WHERE id=?",
                  (status, error, int(time.time()), pid))


# ---------- kartochkalar ----------
def add_card(name, input_data, result, photo_path, infographic_path):
    with conn() as c:
        cur = c.execute("""INSERT INTO cards(created,name,input_json,result_json,photo_path,infographic_path)
                           VALUES(?,?,?,?,?,?)""",
                        (int(time.time()), name, json.dumps(input_data, ensure_ascii=False),
                         json.dumps(result, ensure_ascii=False), photo_path, infographic_path))
        return cur.lastrowid


def list_cards(limit=50):
    with conn() as c:
        rows = c.execute("SELECT * FROM cards ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            d["input"] = json.loads(d.pop("input_json") or "{}")
            d["result"] = json.loads(d.pop("result_json") or "{}")
            out.append(d)
        return out


def get_card(cid):
    with conn() as c:
        r = c.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["input"] = json.loads(d.pop("input_json") or "{}")
    d["result"] = json.loads(d.pop("result_json") or "{}")
    return d


init()
