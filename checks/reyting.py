"""
Reyting va moderatsiya nazoratchisi:
  - past reyting (4.0 dan past, kamida 2 ta sharh) — qaytish va sotuv tushishining sababi
  - Uzum izohlari bor (HAS_COMPLAINTS) yoki tovar bloklangan (BLOCKED)
"""
import profit
from checks.util import short


def _status(p):
    st = p.get("status")
    return (st.get("value") if isinstance(st, dict) else st) or ""


def run():
    findings = []
    for p in profit.products_raw():
        if _status(p) == "ARCHIVED":
            continue
        pid = p.get("productId")
        name = short(p.get("title") or str(pid), 50)
        moder = (p.get("moderationStatus") or {}).get("value") if isinstance(p.get("moderationStatus"), dict) else None

        if _status(p) == "BLOCKED" or (p.get("blockingReasons") or []) or p.get("blockReason"):
            reason = p.get("blockReason") or ", ".join(map(str, p.get("blockingReasons") or [])) or "sabab ko'rsatilmagan"
            findings.append({
                "key": f"blok:{pid}", "source": "reyting", "level": "red", "urgent": True,
                "title": f"{name}: tovar bloklangan",
                "text": f"Uzum tovarni sotuvdan olib qo'ygan ({reason}). Bloklangan tovar ko'rinmaydi va sotilmaydi.",
                "action": "Kabinet → Mahsulotlar → Bloklanganlar: izohni o'qing, kartochkani tuzatib, qayta moderatsiyaga yuboring.",
                "money": 0,
            })
        elif moder == "HAS_COMPLAINTS":
            findings.append({
                "key": f"izoh:{pid}", "source": "reyting", "level": "red",
                "title": f"{name}: kartochkada Uzum izohlari bor",
                "text": "Moderatsiya kartochkada xato topgan. Tuzatilmasa, tovar bloklanishi mumkin.",
                "action": "Kabinet → Mahsulotlar: tovarni ochib, izohlarni tuzating.",
                "money": 0,
            })

        try:
            rating = float(p.get("rating") or 0)
        except (TypeError, ValueError):
            rating = 0
        reviews = int(profit._num(p, "feedbackQuantity"))
        if 0 < rating < 4.0 and reviews >= 2:
            findings.append({
                "key": f"reyting:{pid}", "source": "reyting", "level": "red" if rating < 3 else "orange",
                "title": f"{name}: reyting {rating:.1f} ({reviews} ta sharh)",
                "text": "Past reyting xaridorni qaytaradi va qidiruvda tovarni pastga tushiradi.",
                "action": "Kabinet → Sharhlar: salbiy sharhlarga javob yozing; sabab sifat bo'lsa, ta'minotchini yoki tovarni almashtiring.",
                "money": 0,
            })
    return findings
