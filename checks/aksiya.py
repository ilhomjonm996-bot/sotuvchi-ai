"""
Aksiya filtri: Uzum taklif qilgan aksiya narxini (specialOffer.mechanicPrice) zararsiz minimal narx bilan solishtiradi.

  - aksiya narxi < minimum va tovar aksiyada → 🔴 aksiyadan chiqing (har sotuvda zarar)
  - aksiya narxi < minimum, Uzum tavsiya qilyapti → 🟠 qo'shilmang
  - aksiya narxi ≥ minimum, tavsiya bor, qoldiq bor → 🟢 foydali aksiya, qo'shilish mumkin
Faqat tugamagan aksiyalar ko'riladi. Bir tovar + bir aksiya = bitta topilma.
"""
from collections import defaultdict

import profit
from checks.util import short

_DAY = 86400000


def run():
    now = profit.now_ms()
    advice = {a["sku_id"]: a for a in profit.price_advice()}
    groups = defaultdict(lambda: {"loss": [], "ok": [], "in_offer": False, "rec": False, "stock": 0})
    titles = {}
    for p in profit.products_raw():
        for s in p.get("skuList") or []:
            if s.get("archived"):
                continue
            so = s.get("specialOffer") or {}
            price = so.get("mechanicPrice")
            end = so.get("endDate")
            if price is None or (end and end < now):
                continue
            a = advice.get(int(s.get("skuId") or 0))
            if not a or not a.get("min"):
                continue  # tannarx noma'lum — hisoblab bo'lmaydi
            key = (p.get("productId"), so.get("promoName") or "Uzum aksiyasi")
            titles[key] = (p.get("title") or "", end)
            g = groups[key]
            g["in_offer"] |= bool(so.get("inOffer"))
            g["rec"] |= bool(so.get("hasRecommendation"))
            g["stock"] += profit._num(s, "quantityActive") + profit._num(s, "quantityFbs")
            (g["loss"] if float(price) < a["min"] else g["ok"]).append((float(price), a))

    findings = []
    for key, g in groups.items():
        title, end = titles[key]
        promo = key[1]
        days = f", {max(0, round((end - now) / _DAY))} kun qoldi" if end else ""
        name = short(title, 50)
        if g["loss"]:
            worst_price, a = min(g["loss"], key=lambda x: x[0] - x[1]["min"])
            per_unit = a["min"] - worst_price
            daily = (a.get("sold90") or 0) / 365
            money = per_unit * max(daily, 0.5) * 30
            if g["in_offer"]:
                findings.append({
                    "key": f"aksiya:{key}", "source": "aksiya", "level": "red", "urgent": True,
                    "title": f"{name}: «{promo}» aksiyasida har sotuvda zarar",
                    "text": f"Aksiya narxi {profit.fmt(worst_price)} so'm, zararsiz minimum {profit.fmt(a['min'])} so'm — "
                            f"har dona ~{profit.fmt(per_unit)} so'm zarar{days}.",
                    "action": "Kabinet → Marketing → Aksiyalar: bu tovarni aksiyadan chiqaring yoki narxni minimumdan yuqori qiling.",
                    "money": money,
                })
            elif g["rec"]:
                findings.append({
                    "key": f"aksiya:{key}", "source": "aksiya", "level": "orange",
                    "title": f"{name}: «{promo}» aksiyasiga qo'shilmang",
                    "text": f"Uzum tavsiya qilgan aksiya narxi {profit.fmt(worst_price)} so'm — zararsiz minimumdan "
                            f"({profit.fmt(a['min'])}) {profit.fmt(per_unit)} so'm past{days}.",
                    "action": "Kabinetdagi «Aksiyaga qo'shish» tugmasini bosmang.",
                    "money": money,
                })
        elif g["ok"] and g["rec"] and not g["in_offer"] and g["stock"] > 0:
            price, a = min(g["ok"], key=lambda x: x[0])
            unit_profit = price * (1 - a["commission_rate"] - profit.tax_rate()) - a["unit_cost"] - a["extra_cost"] - a["logistics"]
            findings.append({
                "key": f"aksiya:{key}", "source": "aksiya", "level": "green",
                "title": f"{name}: «{promo}» aksiyasi foydali",
                "text": f"Aksiya narxi {profit.fmt(price)} so'm, minimumdan yuqori — har dona ~{profit.fmt(unit_profit)} so'm foyda qoladi{days}.",
                "action": "Kabinet → Mahsulotlar: «Aksiyaga qo'shish» — sotuvni ko'paytirish uchun qo'shilish mumkin.",
                "money": 0,
            })
    return findings
