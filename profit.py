"""
Sof foyda hisoboti va aqlli narx maslahati.

Hisob (har bir tovar uchun):
    tushum      = sotuv narxi × sotilgan soni (bekor qilingan va qaytganlar hisobga olinmaydi)
    − komissiya (Uzum)
    − logistika (Uzum)
    − tannarx   (tovar narxi + yetkazib kelish, 1 dona × soni)
    − soliq     (tushum × soliq stavkasi)
    − Uzum xarajatlari (saqlash, reklama, jarimalar) — tushumga mutanosib taqsimlanadi
    = sof foyda

Narx formulasi:
    min      = (tannarx + qo'shimcha + logistika) / (1 − komissiya% − soliq%)
    tavsiya  = (tannarx + qo'shimcha + logistika) / (1 − komissiya% − soliq% − marja%)
    chizilgan narx (fullPrice) ≈ tavsiya × 1.3
"""
import math
import time
from datetime import datetime, timedelta, timezone

import config
import db
from uzum_client import client, UzumError

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (serverda ham to'g'ri ishlaydi)
_DAY_MS = 24 * 3600 * 1000

PERIODS = {
    "today": "Bugun",
    "week": "Oxirgi 7 kun",
    "month": "Oxirgi 30 kun",
    "year": "Oxirgi 365 kun",
    "all": "Barcha vaqt",
}

EXPENSE_NAMES = {  # demo ma'lumot uchun; Uzum o'zi o'zbekcha nom beradi (Ombor, Marketing, ...)
    "STORAGE": "Saqlash",
    "ADVERTISING": "Reklama",
    "PENALTY": "Jarimalar",
    "OMBOR": "Ombor (saqlash)",
}


def default_period():
    return "month" if client.demo else "year"

_cache = {}
_CACHE_SEC = 300  # Uzum limitlari uchun natijani 5 daqiqa saqlaymiz


def _cached(key, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_SEC:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def clear_cache():
    _cache.clear()


# ---------- yordamchi ----------
def fmt(n) -> str:
    """1234567 → '1 234 567'"""
    try:
        n = int(round(float(n)))
    except (TypeError, ValueError):
        return "0"
    s = f"{abs(n):,}".replace(",", " ")
    return ("−" if n < 0 else "") + s


def now_ms() -> int:
    return int(time.time() * 1000)


def period_range(period: str):
    """Davr uchun (boshlanish_ms, tugash_ms)."""
    now = datetime.now(TZ)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "year":
        start = now - timedelta(days=365)
    elif period == "all":
        start = now - timedelta(days=3 * 365)
    else:
        start = now - timedelta(days=30)
    return int(start.timestamp() * 1000), int(now.timestamp() * 1000)


def _to_ms(v):
    """Sana ISO matn ham, millisekund ham bo'lishi mumkin."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v if v > 1e11 else v * 1000)
    s = str(v).strip()
    if s.isdigit():
        return _to_ms(int(s))
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def _num(d, *keys, default=0):
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def tax_rate():
    return db.get_float_setting("tax_rate", config.DEFAULT_TAX_RATE)


def target_margin():
    return db.get_float_setting("target_margin", config.DEFAULT_TARGET_MARGIN)


# ---------- do'kon va tovarlar ----------
def shop():
    """Birinchi do'kon (yoki sozlamada tanlangan)."""
    shops = _cached("shops", client.shops)
    if not shops:
        raise UzumError("Uzum'da do'kon topilmadi.")
    sid = db.get_setting("shop_id")
    for s in shops:
        if str(s.get("id")) == str(sid):
            return s
    return shops[0]


def shop_id():
    return int(shop()["id"])


def skus():
    """Barcha SKU lar tekis ro'yxat ko'rinishida."""
    def load():
        out = []
        for p in client.products(shop_id()):
            for s in p.get("skuList") or []:
                if s.get("archived"):
                    continue
                ptitle = s.get("productTitle") or p.get("title") or ""
                variant = s.get("skuTitle") or ""
                if ptitle and variant and variant != ptitle:
                    title = f"{ptitle} — {variant}"
                else:
                    title = ptitle or variant or str(s.get("skuId"))
                comm = _num(s, "commission") or _num(p.get("commissionDto") or {}, "maxCommission")
                out.append({
                    "product_id": p.get("productId") or p.get("id"),
                    "sku_id": int(s.get("skuId") or s.get("id")),
                    "title": title,
                    "full_title": s.get("skuFullTitle") or variant,
                    "commission_pct": comm / 100 if comm > 1 else comm,
                    "barcode": s.get("barcode"),
                    "price": int(_num(s, "sellPrice", "price")),
                    "full_price": int(_num(s, "fullPrice")),
                    "purchase_price": _num(s, "purchasePrice"),
                    "stock": int(_num(s, "quantityActive") + _num(s, "quantityFbs")),
                })
        return out
    return _cached(("skus", shop_id()), load)


def _sku_index():
    """Buyurtma qatorini SKU ga bog'lash: skuId (demo) yoki skuTitle == skuFullTitle (haqiqiy Uzum)."""
    by_id, by_title = {}, {}
    for s in skus():
        by_id[s["sku_id"]] = s
        if s.get("full_title"):
            by_title[s["full_title"]] = s
    return by_id, by_title


def _order_sku(o, idx):
    """(kalit, sku_info). SKU topilmasa (arxivlangan bo'lsa) kalit — sarlavha matni."""
    by_id, by_title = idx
    sid = o.get("skuId")
    if sid and int(sid) in by_id:
        return int(sid), by_id[int(sid)]
    t = o.get("skuTitle") or ""
    if t in by_title:
        s = by_title[t]
        return s["sku_id"], s
    return ("t:" + (t or str(o.get("productId")))), {}


def _qty(o):
    """Sotilgan soni. Uzum'da `amount` qaytarilganlar ayirilgan holda keladi (bekor: amount=0, returns=1),
    commission va logisticDeliveryFee esa qator uchun JAMI (haqiqiy do'konda tekshirilgan)."""
    return max(0.0, _num(o, "amount"))


def unit_cost(sku_id, purchase_price=0):
    """(tannarx, qo'shimcha, manba). Panelda kiritilgani ustun, bo'lmasa Uzum'dagi purchasePrice."""
    c = db.get_costs().get(int(sku_id))
    if c and (c["unit_cost"] or c["extra_cost"]):
        return float(c["unit_cost"]), float(c["extra_cost"]), "kiritilgan"
    if purchase_price:
        return float(purchase_price), 0.0, "uzum"
    return 0.0, 0.0, "yo'q"


# ---------- ma'lumot yuklash ----------
def _orders(date_from, date_to):
    key = ("orders", shop_id(), date_from // 60000, date_to // 60000)
    return _cached(key, lambda: client.finance_orders([shop_id()], date_from, date_to))


def _expenses(date_from, date_to):
    key = ("exp", shop_id(), date_from // 60000, date_to // 60000)
    return _cached(key, lambda: client.expenses([shop_id()], date_from, date_to))


def _row_profit(o, idx, tax):
    """Bitta buyurtma qatori: (kalit, info, qty, tushum, komissiya, logistika, tannarx, manba)."""
    key, info = _order_sku(o, idx)
    qty = _qty(o)
    revenue = _num(o, "sellPrice") * qty
    uc, extra, src = unit_cost(key, _num(o, "purchasePrice") or info.get("purchase_price", 0)) \
        if isinstance(key, int) else (_num(o, "purchasePrice"), 0.0, "uzum" if o.get("purchasePrice") else "yo'q")
    return key, info, qty, revenue, _num(o, "commission"), _num(o, "logisticDeliveryFee"), (uc + extra) * qty, src


def expense_amount(e):
    """Xarajat summasi. Uzum'da `paymentPrice` — summa, `amount` — soni. Daromad (INCOME) manfiy."""
    amt = abs(_num(e, "paymentPrice", "amount"))
    return -amt if (e.get("type") or "OUTCOME").upper() == "INCOME" else amt


# ---------- hisobot ----------
def report(period: str = "month"):
    date_from, date_to = period_range(period)
    rows = _orders(date_from, date_to)
    tax = tax_rate()
    idx = _sku_index()

    per = {}
    canceled = 0
    for o in rows:
        status = (o.get("status") or "").upper()
        if status == "CANCELED":
            canceled += 1
            continue
        key, info, qty, revenue, commission, logistics, cost, src = _row_profit(o, idx, tax)
        r = per.setdefault(key, {
            "sku_id": key if isinstance(key, int) else None, "product_id": o.get("productId"),
            "title": info.get("title") or o.get("productTitle") or o.get("skuTitle") or str(key),
            "qty": 0, "returns": 0, "revenue": 0, "commission": 0, "logistics": 0, "cost": 0,
            "tax": 0, "cost_source": src,
        })
        r["qty"] += qty
        r["returns"] += _num(o, "amountReturns")
        r["revenue"] += revenue
        r["commission"] += commission
        r["logistics"] += logistics
        r["cost"] += cost
        r["tax"] += revenue * tax

    # Uzum xarajatlari
    exp_rows = _expenses(date_from, date_to)
    exp_by = {}
    exp_total = 0.0
    for e in exp_rows:
        amt = expense_amount(e)
        src = e.get("source") or ""
        name = EXPENSE_NAMES.get(src.upper()) or src or e.get("name") or "Boshqa"
        exp_by[name] = exp_by.get(name, 0) + amt
        exp_total += amt

    total_rev = sum(r["revenue"] for r in per.values())
    items = []
    for r in per.values():
        r["expenses"] = exp_total * (r["revenue"] / total_rev) if total_rev else 0
        r["profit_before_exp"] = r["revenue"] - r["commission"] - r["logistics"] - r["cost"] - r["tax"]
        r["profit"] = r["profit_before_exp"] - r["expenses"]
        r["margin"] = r["profit"] / r["revenue"] if r["revenue"] else 0
        items.append(r)
    items.sort(key=lambda x: x["profit"], reverse=True)

    t = {k: sum(r[k] for r in items) for k in ("qty", "returns", "revenue", "commission", "logistics", "cost", "tax")}
    t["expenses"] = exp_total
    t["profit"] = t["revenue"] - t["commission"] - t["logistics"] - t["cost"] - t["tax"] - exp_total
    t["margin"] = t["profit"] / t["revenue"] if t["revenue"] else 0
    t["orders"] = len(rows) - canceled
    t["canceled"] = canceled

    return {
        "period": period,
        "period_name": PERIODS.get(period, period),
        "from": date_from, "to": date_to,
        "totals": t,
        "items": items,
        "expenses_by": sorted(exp_by.items(), key=lambda x: -x[1]),
        "missing_costs": [r["title"] for r in items if r["cost_source"] == "yo'q"],
        "demo": client.demo,
        "shop_name": shop().get("name", ""),
    }


def series(period: str = "month"):
    """Grafik: qisqa davrlarda oxirgi 30 kun kunma-kun, yil/barcha vaqtda oyma-oy.
    Foyda — Uzum xarajatlarigacha (ular kunlarga taqsimlanmagan)."""
    now = datetime.now(TZ)
    if period in ("year", "all"):
        months = 12 if period == "year" else 24
        y, m = now.year, now.month
        labels = []
        for _ in range(months):
            labels.append(f"{y}-{m:02d}")
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        labels.reverse()
        start = datetime(int(labels[0][:4]), int(labels[0][5:]), 1, tzinfo=TZ)
        fmt_key, title = "%Y-%m", f"Oxirgi {months} oy (oyma-oy)"
    else:
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = end - timedelta(days=30)
        labels = [(start + timedelta(days=i)).strftime("%m-%d") for i in range(30)]
        fmt_key, title = "%m-%d", "Oxirgi 30 kun"
    rows = _orders(int(start.timestamp() * 1000), now_ms())
    tax = tax_rate()
    idx = _sku_index()
    buckets = {}
    for o in rows:
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        ts = _to_ms(o.get("date") or o.get("dateIssued") or o.get("dateCreated") or o.get("createdAt"))
        if ts is None:
            continue
        k = datetime.fromtimestamp(ts / 1000, TZ).strftime(fmt_key)
        _, _, _, rev, comm, logi, cost, _ = _row_profit(o, idx, tax)
        b = buckets.setdefault(k, [0, 0])
        b[0] += rev
        b[1] += rev - comm - logi - cost - rev * tax
    return {"title": title, "labels": labels,
            "revenue": [round(buckets.get(d, [0, 0])[0]) for d in labels],
            "profit": [round(buckets.get(d, [0, 0])[1]) for d in labels]}


# ---------- narx maslahati ----------
def _ceil1000(x):
    return int(math.ceil(x / 1000.0) * 1000)


def price_for_cost(cost, extra=0, commission_rate=None, logistics=None, tax=None, margin=None):
    """Formula bo'yicha (min, tavsiya, chizilgan) narx. Bo'lmasa None."""
    commission_rate = config.DEFAULT_COMMISSION_RATE if commission_rate is None else commission_rate
    logistics = config.DEFAULT_LOGISTICS_FEE if logistics is None else logistics
    tax = tax_rate() if tax is None else tax
    margin = target_margin() if margin is None else margin
    base = float(cost) + float(extra) + float(logistics)
    d_min = 1 - commission_rate - tax
    d_rec = d_min - margin
    if base <= 0 or d_rec <= 0.05:
        return None
    rec = _ceil1000(base / d_rec)
    return {"min": _ceil1000(base / d_min), "rec": rec, "full": _ceil1000(rec * 1.3)}


def sku_history(days: int = 365):
    """Har bir SKU ning o'z tarixidan komissiya % va 1 donaga logistika (oxirgi 1 yil)."""
    date_from = now_ms() - days * _DAY_MS
    idx = _sku_index()
    hist = {}
    for o in _orders(date_from, now_ms()):
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        sid, _ = _order_sku(o, idx)
        amount = _qty(o)
        if not amount:
            continue
        h = hist.setdefault(sid, {"rev": 0, "comm": 0, "logi": 0, "qty": 0})
        h["rev"] += _num(o, "sellPrice") * amount
        h["comm"] += _num(o, "commission")
        h["logi"] += _num(o, "logisticDeliveryFee")
        h["qty"] += amount
    out = {}
    for sid, h in hist.items():
        if h["rev"] > 0 and h["qty"] > 0:
            out[sid] = {"commission_rate": h["comm"] / h["rev"], "logistics": h["logi"] / h["qty"],
                        "qty90": h["qty"]}
    return out


def price_advice():
    """Har bir SKU uchun narx maslahati."""
    hist = sku_history()
    tax = tax_rate()
    margin = target_margin()
    out = []
    for s in skus():
        h = hist.get(s["sku_id"])
        comm = h["commission_rate"] if h else (s.get("commission_pct") or config.DEFAULT_COMMISSION_RATE)
        logi = h["logistics"] if h else config.DEFAULT_LOGISTICS_FEE
        uc, extra, src = unit_cost(s["sku_id"], s["purchase_price"])
        a = dict(s, commission_rate=comm, logistics=logi, unit_cost=uc, extra_cost=extra,
                 cost_source=src, from_history=bool(h), sold90=int(h["qty90"]) if h else 0)
        p = price_for_cost(uc, extra, comm, logi, tax, margin) if uc > 0 else None
        if not p:
            a.update(min=None, rec=None, full=None, status="nocost",
                     status_text="Tannarx kiritilmagan", action=False)
        else:
            a.update(p)
            price = s["price"]
            unit_profit = price * (1 - comm - tax) - uc - extra - logi
            a["unit_profit"] = unit_profit
            if price < p["min"]:
                a["status"], a["status_text"] = "loss", "Zarar qilyapti"
            elif price < p["rec"] - 500:
                a["status"], a["status_text"] = "low", "Marja past"
            elif price > p["rec"] * 1.4:
                a["status"], a["status_text"] = "high", "Narx baland"
            else:
                a["status"], a["status_text"] = "ok", "Yaxshi"
            a["action"] = a["status"] in ("loss", "low")
        out.append(a)
    order = {"loss": 0, "low": 1, "nocost": 2, "high": 3, "ok": 4}
    out.sort(key=lambda x: order.get(x["status"], 9))
    return out


def create_proposals():
    """Narxi past/zarardagi tovarlar uchun takliflar yaratadi. Yaratilganlar sonini qaytaradi."""
    n = 0
    sid = shop_id()
    for a in price_advice():
        if not a["action"]:
            continue
        reason = (f"{a['status_text']}: hozir {fmt(a['price'])} so'm, zararsiz minimum {fmt(a['min'])} so'm. "
                  f"Komissiya {a['commission_rate'] * 100:.0f}%, logistika {fmt(a['logistics'])} so'm, "
                  f"tannarx {fmt(a['unit_cost'] + a['extra_cost'])} so'm"
                  f"{' (tarixdan)' if a['from_history'] else ' (taxminiy)'}.")
        db.add_proposal(shop_id=sid, product_id=a["product_id"], sku_id=a["sku_id"], title=a["title"],
                        old_price=a["price"], new_price=a["rec"], full_price=a["full"], min_price=a["min"],
                        reason=reason)
        n += 1
    return n


def approve_proposal(pid):
    """Taklifni tasdiqlaydi va narxni Uzum'ga yuboradi. (ok, xabar)"""
    p = db.get_proposal(pid)
    if not p:
        return False, "Taklif topilmadi"
    if p["status"] != "pending":
        return False, "Bu taklif allaqachon ko'rib chiqilgan"
    if int(p["shop_id"]) != shop_id():
        return False, "Bu taklif boshqa do'kon uchun — joriy do'konda tasdiqlab bo'lmaydi"
    try:
        client.send_price(p["shop_id"], p["product_id"], p["sku_id"], p["new_price"], p["full_price"])
    except UzumError as e:
        db.set_proposal_status(pid, "failed", str(e))
        return False, f"Uzum xatosi: {e}"
    db.set_proposal_status(pid, "approved")
    clear_cache()
    return True, f"Narx o'zgardi: {p['title']} → {fmt(p['new_price'])} so'm"


def proposals(status=None, limit=100):
    """Faqat joriy do'kon takliflari."""
    sid = shop_id()
    return [p for p in db.list_proposals(status, limit) if int(p["shop_id"] or 0) == sid]


def reject_proposal(pid):
    p = db.get_proposal(pid)
    if not p or p["status"] != "pending":
        return False, "Taklif topilmadi"
    db.set_proposal_status(pid, "rejected")
    return True, "Rad etildi"


# ---------- matnli hisobot (Telegram uchun) ----------
def report_text(period="today"):
    from html import escape as _e
    escape = lambda s: _e(str(s), quote=False)  # noqa: E731
    r = report(period)
    t = r["totals"]
    lines = [
        f"📊 <b>{r['period_name']}</b> — {escape(r['shop_name'])}" + (" (demo)" if r["demo"] else ""),
        "",
        f"🛒 Buyurtmalar: <b>{int(t['orders'])}</b> (bekor: {t['canceled']})",
        f"💰 Tushum: <b>{fmt(t['revenue'])}</b> so'm",
        f"➖ Komissiya: {fmt(t['commission'])}",
        f"➖ Logistika: {fmt(t['logistics'])}",
        f"➖ Tannarx: {fmt(t['cost'])}",
        f"➖ Soliq: {fmt(t['tax'])}",
        f"➖ Uzum xarajatlari: {fmt(t['expenses'])}",
        "",
        f"{'✅' if t['profit'] >= 0 else '🔻'} <b>Sof foyda: {fmt(t['profit'])} so'm</b> ({t['margin'] * 100:.1f}%)",
    ]
    if r["items"]:
        best = r["items"][0]
        worst = r["items"][-1]
        lines += ["", f"🏆 Eng foydali: {escape(best['title'])} ({fmt(best['profit'])})"]
        if worst["profit"] < 0:
            lines.append(f"⚠️ Zararli: {escape(worst['title'])} ({fmt(worst['profit'])})")
    if r["missing_costs"]:
        lines.append(f"\n❗ {len(r['missing_costs'])} ta tovarga tannarx kiritilmagan")
    return "\n".join(lines)
