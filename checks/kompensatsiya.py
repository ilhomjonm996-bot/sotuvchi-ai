"""
Kompensatsiya radari — Uzum'dan qaytarib olish mumkin bo'lgan pul:

  1) Bekor qilingan buyurtma uchun logistika yechilgan, lekin qaytarilmagan.
  2) Bitta buyurtma uchun logistika bir necha marta yechilgan.
  3) Uzum omborida brak yoki yo'qolgan tovar (quantityDefected / quantityMissing).

Xarajat nomi namunalari:
  "Buyurtma № 95028581 uchun logistika xizmatlari uchun to'lov."   (OUTCOME)
  "Buyurtma № 126530763 uchun logistika to'lovini qaytarish"      (INCOME)
Bu — Uzum qoidalari bo'yicha qaytarilishi shart degani emas: ro'yxat tekshirish va so'rov uchun.
"""
import re
from collections import defaultdict

import profit
from checks.util import short

_DAY = 86400000
_ORDER = re.compile(r"Buyurtma\s*№\s*(\d+)", re.IGNORECASE)


def _list(nums, n=5):
    nums = sorted(nums)
    more = f" va yana {len(nums) - n} ta" if len(nums) > n else ""
    return ", ".join(f"№{x}" for x in nums[:n]) + more


def run():
    now = profit.now_ms()
    exps = profit._expenses(now - 365 * _DAY, now)
    orders = profit._orders(now - 365 * _DAY, now)

    rows = defaultdict(lambda: {"rows": 0, "canceled": 0})
    for o in orders:
        oid = str(o.get("orderId") or o.get("id") or "")
        if not oid:
            continue
        rows[oid]["rows"] += 1
        if (o.get("status") or "").upper() == "CANCELED":
            rows[oid]["canceled"] += 1

    logi = defaultdict(lambda: {"charged": 0.0, "n_charged": 0, "refunded": 0.0, "n_refunded": 0})
    for e in exps:
        m = _ORDER.search(e.get("name") or "")
        if not m or "logistika" not in (e.get("name") or "").lower():
            continue
        amt = abs(profit._num(e, "paymentPrice", "amount"))
        d = logi[m.group(1)]
        if (e.get("type") or "").upper() == "INCOME":
            d["refunded"] += amt
            d["n_refunded"] += 1
        else:
            d["charged"] += amt
            d["n_charged"] += 1

    not_refunded, dup = {}, {}
    for oid, d in logi.items():
        net = d["charged"] - d["refunded"]
        r = rows.get(oid)
        if r and r["rows"] and r["canceled"] == r["rows"] and net > 0:
            not_refunded[oid] = net
        elif d["n_charged"] - d["n_refunded"] > max(1, r["rows"] if r else 1) and net > 0:
            per = d["charged"] / d["n_charged"]
            dup[oid] = net - per * max(1, r["rows"] if r else 1)

    findings = []
    if not_refunded:
        total = sum(not_refunded.values())
        findings.append({
            "key": "komp:bekor", "source": "kompensatsiya", "level": "orange",
            "title": f"{len(not_refunded)} ta bekor qilingan buyurtma uchun logistika qaytarilmagan — {profit.fmt(total)} so'm",
            "text": f"Buyurtmalar: {_list(not_refunded)}. Xaridor tovarni olmasdan bekor qilgan bo'lsa, logistika odatda qaytariladi.",
            "action": "Kabinet → Yordam xizmati: ro'yxatni yuborib, logistika to'lovini qaytarishni so'rang.",
            "money": total, "once": True,
        })
    if dup:
        total = sum(v for v in dup.values() if v > 0)
        if total > 0:
            findings.append({
                "key": "komp:takror", "source": "kompensatsiya", "level": "red",
                "title": f"{len(dup)} ta buyurtma uchun logistika bir necha marta yechilgan — {profit.fmt(total)} so'm",
                "text": f"Buyurtmalar: {_list(dup)}. Bitta buyurtma uchun logistika bir martadan ko'p olingan.",
                "action": "Kabinet → Mablag'lar → Operatsiyalar: shu buyurtmalarni tekshiring va Yordam xizmatiga murojaat qiling.",
                "money": total, "once": True,
            })

    for p in profit.products_raw():
        bad = profit._num(p, "quantityDefected") + profit._num(p, "quantityMissing")
        if bad <= 0:
            continue
        prices = [profit._num(s, "sellPrice", "price") for s in p.get("skuList") or []]
        value = bad * (max(prices) if prices else 0)
        findings.append({
            "key": f"komp:brak:{p.get('productId')}", "source": "kompensatsiya", "level": "orange",
            "title": f"{short(p.get('title'), 50)}: Uzum omborida {bad:.0f} dona brak/yo'qolgan",
            "text": f"Omborda shikastlangan yoki yo'qolgan tovar uchun kompensatsiya so'rash mumkin (~{profit.fmt(value)} so'm, bir martalik).",
            "action": "Kabinet → Mahsulotlar / Yordam xizmati: brak yoki yo'qolgan tovar uchun kompensatsiya arizasini yuboring.",
            "money": value, "once": True,
        })
    return findings
