"""
Ombor xarajatlari tekshiruvi:
  1) Qaytgan tovar omborda yotib, har kuni pullik saqlanyapti (yukxat raqami bilan).
  2) "O'lik ombor": sotuv yo'q, lekin ombor uchun har oy pul yechilyapti.

Uzum xarajat nomi namunasi:
  "6725297 - sonli yukxat boʻyicha yigʻilgan qaytarishni saqlash xizmatlari uchun toʻlov"
"""
import re
from collections import defaultdict

import profit

_DAY = 86400000
_INVOICE = re.compile(r"^\s*(\d{4,})\s*-\s*sonli\s*yuk\s*xat", re.IGNORECASE)


def _norm(s):
    return (s or "").lower().replace("ʻ", "'").replace("‘", "'").replace("`", "'")


def _is_return_storage(name):
    n = _norm(name)
    return "qaytarish" in n and "saqlash" in n


def run():
    now = profit.now_ms()
    exps = profit._expenses(now - 365 * _DAY, now)
    findings = []

    # --- 1) qaytgan tovarlarni saqlash, yukxat bo'yicha ---
    inv = defaultdict(lambda: {"total": 0.0, "first": None, "last": None, "last30": 0.0})
    for e in exps:
        if (e.get("type") or "").upper() == "INCOME":
            continue
        name = e.get("name") or ""
        m = _INVOICE.match(name)
        if not (m and _is_return_storage(name)):
            continue
        ts = profit._to_ms(e.get("dateService") or e.get("dateCreated"))
        if ts is None:
            continue
        amt = profit.expense_amount(e)
        d = inv[m.group(1)]
        d["total"] += amt
        d["first"] = ts if d["first"] is None else min(d["first"], ts)
        d["last"] = ts if d["last"] is None else max(d["last"], ts)
        if ts >= now - 30 * _DAY:
            d["last30"] += amt

    for num, d in inv.items():
        active = d["last"] >= now - 5 * _DAY
        days = max(1, round((now - d["first"]) / _DAY))
        if active:
            month = d["last30"] or d["total"] / max(1, days) * 30
            findings.append({
                "key": f"saqlash:{num}", "source": "saqlash", "level": "red",
                "title": f"Qaytgan tovar omborda {days} kundan beri (yukxat {num})",
                "text": f"Har kuni pullik saqlash yechilyapti. Jami {profit.fmt(d['total'])} so'm to'langan.",
                "action": "Kabinet → Ta'minlashlar → Qaytarishlar: olish vaqtini tanlang va tovarni olib keting.",
                "money": month, "urgent": True,
            })
        elif d["total"] >= 50000:
            period = "1 yildan ortiq" if days >= 360 else f"{days} kun"
            findings.append({
                "key": f"saqlash-old:{num}", "source": "saqlash", "level": "green",
                "title": f"Qaytgan tovar saqlash uchun {profit.fmt(d['total'])} so'm to'langan (yukxat {num})",
                "text": f"{period} davomida yechilgan, hozir to'xtagan.",
                "action": "Kelajakda qaytgan tovarni 1–2 hafta ichida olib keting — ogohlantirishni biz yuboramiz.",
                "money": 0,
            })

    # --- 2) o'lik ombor: 60 kun sotuv yo'q, lekin oxirgi 30 kunda ombor xarajati bor ---
    orders = profit._orders(now - 60 * _DAY, now)
    sold60 = sum(profit._qty(o) for o in orders if (o.get("status") or "").upper() != "CANCELED")
    storage30 = sum(profit.expense_amount(e) for e in exps
                    if (profit._to_ms(e.get("dateService") or e.get("dateCreated")) or 0) >= now - 30 * _DAY
                    and "ombor" in _norm(e.get("source")) and (e.get("type") or "").upper() != "INCOME")
    if sold60 == 0 and storage30 > 0:
        findings.append({
            "key": "olik-ombor", "source": "saqlash", "level": "red",
            "title": "Sotuv yo'q, lekin ombor uchun pul ketyapti",
            "text": f"Oxirgi 60 kunda birorta sotuv bo'lmagan, oxirgi 30 kunda ombor uchun {profit.fmt(storage30)} so'm yechilgan.",
            "action": "Qolgan tovarni chegirma bilan soting yoki ombordan olib chiqing.",
            "money": storage30, "urgent": True,
        })
    return findings
