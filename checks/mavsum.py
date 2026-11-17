"""
Mavsumiy zaxira rejalashtiruvchi: o'tgan yilgi oylik sotuvdan "cho'qqi oylar"ni topadi
(o'rtacha oydan kamida 2 barobar ko'p). Cho'qqi 60 kun ichida boshlansa yoki hozir davom etsa,
zaxirani oldindan olib kelishni tavsiya qiladi (Uzum omboriga yetkazish 1–2 hafta oladi).
"""
from collections import defaultdict
from datetime import datetime, timedelta

import profit
from checks.util import short

_DAY = 86400000
_OY = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def _stock(p):
    return sum(profit._num(s, "quantityActive") + profit._num(s, "quantityFbs")
               for s in (p.get("skuList") or []) if not s.get("archived"))


def run():
    now_dt = datetime.now(profit.TZ)
    now = profit.now_ms()
    orders = profit._orders(now - 2 * 365 * _DAY, now)
    monthly = defaultdict(lambda: defaultdict(float))  # productId -> "YYYY-MM" -> dona
    for o in orders:
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        ts = profit._to_ms(o.get("date") or o.get("dateIssued"))
        if ts:
            monthly[o.get("productId")][datetime.fromtimestamp(ts / 1000, profit.TZ).strftime("%Y-%m")] += profit._qty(o)

    products = {p.get("productId"): p for p in profit.products_raw()}
    findings = []
    for pid, months in monthly.items():
        if len(months) < 2:
            continue
        p = products.get(pid)
        if not p:
            continue
        total = sum(months.values())
        avg = total / 12  # yil bo'yicha o'rtacha oy (sotuv bo'lmagan oylar ham hisobga olinadi)
        # kelgusi 60 kun ichidagi oylar (o'tgan yilgi shu oylar bilan)
        for ahead in (0, 1, 2):
            target = (now_dt.replace(day=1) + timedelta(days=32 * ahead)).replace(day=1)
            last_year = f"{target.year - 1}-{target.month:02d}"
            units = months.get(last_year, 0)
            if units < 5 or units < 2 * avg:
                continue
            days_to = (target - now_dt).days
            stock = _stock(p)
            need = max(0, round(units - stock))
            name = short(p.get("title") or str(pid), 50)
            oy = _OY[target.month]
            when = "hozir davom etyapti" if days_to <= 0 else f"{days_to} kundan keyin boshlanadi"
            deadline = (target - timedelta(days=14)).strftime("%d.%m") if days_to > 14 else "imkon qadar tez"
            findings.append({
                "key": f"mavsum:{pid}:{last_year}", "source": "mavsum",
                "level": "orange" if need > 0 else "green",
                "title": f"{name}: {oy} — mavsum, {when}",
                "text": f"O'tgan yili {oy}da {units:.0f} dona sotilgan (o'rtacha oydan {units / avg:.1f} barobar ko'p). "
                        f"Hozirgi qoldiq: {stock:.0f} dona.",
                "action": (f"Taxminan {need} dona olib keling, omborga {deadline} gacha yetkazing."
                           if need > 0 else "Zaxira yetarli ko'rinadi — narx va reklamani mavsumga tayyorlang."),
                # mavsumda qo'ldan boy berilishi mumkin bo'lgan foyda (taxminan 20% marja), bir martalik
                "money": need * (profit._num((p.get("skuList") or [{}])[0], "sellPrice", "price")) * 0.2, "once": True,
            })
            break  # bitta tovar uchun eng yaqin mavsum
    return findings
