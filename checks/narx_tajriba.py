"""
Narx tajribasi: SKU narxi o'zgargan paytlarni topib, o'zgarishdan oldin va keyin
kunlik sotuv va kunlik foydani solishtiradi. Natija — sotuvchi uchun dalil:
"narxni ko'targaningizda foyda oshdi" yoki "chegirma sotuvni oshirmadi, faqat foydani kamaytirdi".

Shovqinni kamaytirish uchun: har bir davr kamida 7 kun va kamida 5 dona sotuv.
"""
from collections import defaultdict

import profit
from checks.util import short

_DAY = 86400000
_MIN_DAYS = 7
_MIN_UNITS = 5


def _segments(rows):
    """[(ts, price, qty)] → bir xil narxli ketma-ket davrlar."""
    segs = []
    for ts, price, qty in sorted(rows):
        if segs and segs[-1]["price"] == price:
            s = segs[-1]
            s["last"], s["units"] = ts, s["units"] + qty
        else:
            segs.append({"price": price, "first": ts, "last": ts, "units": qty})
    return segs


def run():
    now = profit.now_ms()
    orders = profit._orders(now - 3 * 365 * _DAY, now)
    idx = profit._sku_index()
    advice = {a["sku_id"]: a for a in profit.price_advice()}
    tax = profit.tax_rate()

    rows = defaultdict(list)
    for o in orders:
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        key, _ = profit._order_sku(o, idx)
        ts = profit._to_ms(o.get("date") or o.get("dateIssued"))
        qty = profit._qty(o)
        if isinstance(key, int) and ts and qty:
            rows[key].append((ts, float(profit._num(o, "sellPrice")), qty))

    findings = []
    for sku, r in rows.items():
        a = advice.get(sku)
        if not a or not a.get("unit_cost"):
            continue
        segs = [s for s in _segments(r)]
        best = None
        for before, after in zip(segs, segs[1:]):
            d1 = max(_MIN_DAYS, (before["last"] - before["first"]) / _DAY + 1)
            d2 = max(_MIN_DAYS, (after["last"] - after["first"]) / _DAY + 1)
            if before["units"] < _MIN_UNITS or after["units"] < _MIN_UNITS:
                continue
            if (before["last"] - before["first"]) / _DAY < _MIN_DAYS - 1 or (after["last"] - after["first"]) / _DAY < _MIN_DAYS - 1:
                continue

            def unit_profit(p):
                return p * (1 - a["commission_rate"] - tax) - a["unit_cost"] - a["extra_cost"] - a["logistics"]

            v1, v2 = before["units"] / d1, after["units"] / d2
            p1, p2 = v1 * unit_profit(before["price"]), v2 * unit_profit(after["price"])
            change = abs(p2 - p1)
            if best is None or change > best[0]:
                best = (change, before, after, v1, v2, p1, p2)
        if not best:
            continue
        _, b, af, v1, v2, p1, p2 = best
        up = af["price"] > b["price"]
        price_pct = (af["price"] / b["price"] - 1) * 100
        vol_pct = (v2 / v1 - 1) * 100 if v1 else 0
        name = short(a["title"], 50)
        facts = (f"Narx {profit.fmt(b['price'])} → {profit.fmt(af['price'])} so'm ({price_pct:+.0f}%): "
                 f"sotuv kuniga {v1:.1f} → {v2:.1f} dona ({vol_pct:+.0f}%), "
                 f"foyda kuniga {profit.fmt(p1)} → {profit.fmt(p2)} so'm.")
        if p2 > p1 * 1.1:
            findings.append({
                "key": f"narx:{sku}", "source": "narx_tajriba", "level": "green",
                "title": f"{name}: {'narxni ko‘tarish' if up else 'narxni tushirish'} foyda berdi",
                "text": facts,
                "action": ("Narxni shu darajada ushlab turing; keyingi qadamda yana 5% ko'tarib sinab ko'rish mumkin."
                           if up else "Bu tovar narxga sezgir — chegirma va aksiyalar unga foydali."),
                "money": 0,
            })
        elif p2 < p1 * 0.9:
            findings.append({
                "key": f"narx:{sku}", "source": "narx_tajriba", "level": "orange",
                "title": f"{name}: {'narxni ko‘tarish' if up else 'chegirma'} foydani kamaytirdi",
                "text": facts,
                "action": (f"Narxni {profit.fmt(b['price'])} so'mga qaytarishni ko'rib chiqing (Narxlar bo'limida taklif yaratish mumkin)."
                           if up else "Chegirma sotuvni yetarlicha oshirmadi — keyingi aksiyalarda bu tovarni qatnashtirmang."),
                "money": (p1 - p2) * 30,
            })
    return findings
