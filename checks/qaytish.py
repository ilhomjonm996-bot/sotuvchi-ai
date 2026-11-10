"""
Qaytish va bekor qilish tahlilchisi.

Har bir tovar uchun: bekor qilingan/qaytgan buyurtmalar ulushi (o'z tarixidan) va Uzum
ko'rsatgan returnedPercentage. 30%+ bo'lsa — topilma. Kiyim va oyoq kiyimda sabab ko'pincha o'lcham.
"""
from collections import defaultdict

import profit
from checks.util import short

_DAY = 86400000
_SIZE_WORDS = ("ko'ylak", "ko‘ylak", "kostyum", "shim", "pijama", "botinka", "oyoq kiyim", "krossovka", "etik",
               "sviter", "vodolaska", "kolgotka", "paypoq", "qo'lqop", "qo‘lqop", "qolqop", "kurtka", "palto",
               "futbolka", "yubka", "svitshot", "slipon", "tufli", "shippak")


def _is_sized(title):
    t = (title or "").lower()
    return any(w in t for w in _SIZE_WORDS)


def run():
    now = profit.now_ms()
    orders = profit._orders(now - 365 * _DAY, now)
    per = defaultdict(lambda: {"n": 0, "bad": 0, "logi": 0.0, "logi_n": 0, "title": ""})
    for o in orders:
        pid = o.get("productId")
        d = per[pid]
        d["n"] += 1
        d["title"] = d["title"] or o.get("productTitle") or o.get("skuTitle") or ""
        if (o.get("status") or "").upper() == "CANCELED" or profit._num(o, "amountReturns") > 0:
            d["bad"] += 1
        if profit._num(o, "logisticDeliveryFee") > 0:
            d["logi"] += profit._num(o, "logisticDeliveryFee")
            d["logi_n"] += 1

    products = {p.get("productId"): p for p in profit.products_raw()}
    for pid, p in products.items():  # Uzum'ning o'z ko'rsatkichi (tarix qisqa bo'lsa ham)
        d = per[pid]
        d["title"] = d["title"] or p.get("title") or ""
        d["uzum_pct"] = profit._num(p, "returnedPercentage") / 100
        d["uzum_n"] = profit._num(p, "quantitySold") + profit._num(p, "quantityReturned")

    findings = []
    for pid, d in per.items():
        own = d["bad"] / d["n"] if d["n"] >= 5 else 0
        uz = d.get("uzum_pct", 0) if d.get("uzum_n", 0) >= 5 else 0
        rate = max(own, uz)
        if rate < 0.30:
            continue
        returns = max(d["bad"], round(d.get("uzum_n", 0) * d.get("uzum_pct", 0)))
        avg_logi = d["logi"] / d["logi_n"] if d["logi_n"] else 5000
        loss_each = avg_logi * 2  # borish + qaytish logistikasi (taxminiy)
        sized = _is_sized(d["title"])
        title = short(d["title"] or str(pid))
        findings.append({
            "key": f"qaytish:{pid}", "source": "qaytish",
            "level": "red" if rate >= 0.5 else "orange",
            "title": f"{title}: {rate * 100:.0f}% qaytadi yoki bekor qilinadi",
            "text": (f"Yil davomida ~{returns} ta qaytish/bekor qilish, har biri taxminan {profit.fmt(loss_each)} so'm "
                     f"logistika yo'qotishi." + (" Kiyim/oyoq kiyimda asosiy sabab ko'pincha o'lcham." if sized else "")),
            "action": ("Kartochkaga o'lcham jadvalini va «o'lcham kichikroq/kattaroq keladi» degan izohni qo'shing; "
                       "AI kartochka bo'limida matn tayyorlash mumkin." if sized else
                       "Sharhlar va chatlarda xaridorlar nima yozganini tekshiring: sifat, rasm bilan farq yoki tavsif."),
            "money": returns * loss_each / 12,
        })
    return findings
