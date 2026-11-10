"""
Qoldiq tekshiruvi:
  - Tugagan tovar, lekin oxirgi 60 kunda sotilgan → yo'qotilayotgan sotuv.
  - Tez orada tugaydigan tovar → qancha buyurtma berish kerak.
"""
from collections import defaultdict

import profit
from checks.util import short

_DAY = 86400000
_WINDOW = 60      # sotuv tezligi qaysi davrdan olinadi (kun)
_COVER = 30       # necha kunlik zaxira tavsiya qilinadi


def _stock(p):
    return sum(profit._num(s, "quantityActive") + profit._num(s, "quantityFbs")
               for s in (p.get("skuList") or []) if not s.get("archived"))


def run():
    now = profit.now_ms()
    orders = profit._orders(now - _WINDOW * _DAY, now)
    sold = defaultdict(float)
    revenue = defaultdict(float)
    for o in orders:
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        q = profit._qty(o)
        sold[o.get("productId")] += q
        revenue[o.get("productId")] += profit._num(o, "sellPrice") * q

    findings = []
    for p in profit.products_raw():
        pid = p.get("productId")
        if sold[pid] < 2:
            continue
        per_day = sold[pid] / _WINDOW
        avg_price = revenue[pid] / sold[pid]
        stock = _stock(p)
        title = short(p.get("title") or str(pid))
        if stock <= 0:
            lost = per_day * 30 * avg_price
            findings.append({
                "key": f"tugagan:{pid}", "source": "tugagan", "level": "orange",
                "title": f"{title}: tugagan, lekin talab bor",
                "text": f"Oxirgi {_WINDOW} kunda {sold[pid]:.0f} dona sotilgan (kuniga ~{per_day:.1f}). "
                        f"Tovar yo'qligi sababli oyiga ~{profit.fmt(lost)} so'm sotuv yo'qotilyapti.",
                "action": f"Kamida {round(per_day * _COVER)} dona olib keling ({_COVER} kunlik zaxira).",
                "money": lost * 0.2,  # yo'qotilgan foyda (taxminan 20% marja)
            })
        else:
            days_left = stock / per_day
            if days_left < 10:
                need = max(0, round(per_day * _COVER - stock))
                findings.append({
                    "key": f"tugayapti:{pid}", "source": "tugagan", "level": "orange" if days_left < 5 else "green",
                    "title": f"{title}: {days_left:.0f} kunda tugaydi",
                    "text": f"Qoldiq {stock:.0f} dona, kuniga ~{per_day:.1f} dona sotilyapti.",
                    "action": f"{need} dona buyurtma bering ({_COVER} kunlik zaxira uchun).",
                    "money": per_day * avg_price * 0.2 * max(0, 7 - days_left),
                })
    return findings
