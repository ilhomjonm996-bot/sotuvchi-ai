"""
Raqobatchi kuzatuvchisi: kuzatuvdagi raqobatchilarni o'z tovarimiz bilan solishtiradi.

  - raqobatchi narxni keskin tushirdi (7 kunda ≥10%) → 🟠 ergashish yoki ergashmaslik (zararsiz minimum bilan)
  - raqobatchi ≥10% arzonroq va tovari bor          → 🟠 narxni ko'rib chiqing (minimumdan pastga tushmang)
  - raqobatchida tovar tugadi                         → 🟢 imkoniyat: talab sizga o'tadi, narxni biroz ko'tarish mumkin
Pul summasi ko'rsatilmaydi — raqobatchi ta'sirini aniq hisoblab bo'lmaydi.
"""
import market
import profit
from checks.util import short


def run():
    findings = []
    for c in market.overview():
        last, mine = c["last"], c["mine"]
        if not last or not mine or not last.get("price"):
            continue
        name, rival = short(mine["title"], 40), c.get("shop") or short(c["title"], 30)
        their, my, mn = last["price"], mine["price"], mine.get("min")
        key = f"raqobat:{c['id']}"
        floor = f" Sizning zararsiz minimumingiz {profit.fmt(mn)} so'm." if mn else ""

        if last.get("stock") == 0 and c.get("was_in_stock"):
            findings.append({
                "key": key, "source": "raqobat", "level": "green",
                "title": f"{name}: raqobatchida ({rival}) tovar tugadi",
                "text": f"{rival} da bu tovar qolmadi — xaridorlar boshqa sotuvchiga o'tadi. Sizning narxingiz {profit.fmt(my)} so'm.",
                "action": "Qoldig'ingiz yetarli ekanini tekshiring; narxni 3–5% ko'tarib ko'rish mumkin (Narxlar sahifasi).",
                "money": 0,
            })
            continue

        dropped = c.get("price_change") is not None and c["price_change"] <= -0.10
        if dropped:
            below = mn and their < mn
            findings.append({
                "key": key, "source": "raqobat", "level": "orange",
                "title": f"{name}: {rival} narxni {abs(c['price_change']) * 100:.0f}% tushirdi",
                "text": f"Raqobatchi narxi 7 kunda {profit.fmt(their / (1 + c['price_change']))} → {profit.fmt(their)} so'm. "
                        f"Sizniki {profit.fmt(my)} so'm.{floor}",
                "action": ("Ergashmang — bu narxda siz zarar ko'rasiz. Kartochka, rasm va sharhlar orqali raqobatlashing."
                           if below else
                           "Sotuvingiz tushsa, narxni minimumdan past bo'lmagan darajaga tushirishni ko'rib chiqing."),
                "money": 0,
            })
            continue

        if c.get("diff") is not None and c["diff"] <= -0.10 and (last.get("stock") is None or last["stock"] > 0):
            can_match = mn and their >= mn
            findings.append({
                "key": key, "source": "raqobat", "level": "orange",
                "title": f"{name}: {rival} {abs(c['diff']) * 100:.0f}% arzonroq sotyapti",
                "text": f"Raqobatchi {profit.fmt(their)} so'm, siz {profit.fmt(my)} so'm.{floor}",
                "action": (f"Narxni {profit.fmt(max(mn, their))} so'm atrofiga tushirish mumkin — Narxlar sahifasida taklif yarating."
                           if can_match else
                           "Narxni tushirmang (zarar bo'ladi) — tovarning afzalligini kartochkada ko'rsating."),
                "money": 0,
            })
    return findings
