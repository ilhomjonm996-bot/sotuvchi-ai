"""
Reklama samaradorligi (marketolog agentining birinchi qismi).

Uzum xarajatlarida reklama har kampaniya va har kun bo'yicha keladi:
  "Marketpleysda pulli targʻibot boʻyicha xizmatlar - 2026-02-10 - 254732"
Tekshiruvlar:
  1) Oxirgi 30 kun: reklama sarfi reklamagacha bo'lgan foydadan oshyaptimi (DRR > marja)?
  2) Kampaniya ishlagan kunlarda umuman sotuv bo'lmagan bo'lsa — pul bekorga ketgan.
  3) Oxirgi 12 oy: reklama foydani yeb qo'yganmi (tarixiy saboq).
"""
import re
from collections import defaultdict
from datetime import datetime

import profit

_DAY = 86400000
_CAMPAIGN = re.compile(r"(\d{4}-\d{2}-\d{2})\s*-\s*(\d+)\s*$")


def _is_ad(e):
    src = (e.get("source") or "").lower()
    name = (e.get("name") or "").lower().replace("ʻ", "'")
    return src in ("marketing", "advertising") or "targ'ibot" in name or "reklama" in name


def _day(ts):
    return datetime.fromtimestamp(ts / 1000, profit.TZ).strftime("%Y-%m-%d")


def run():
    now = profit.now_ms()
    exps = [e for e in profit._expenses(now - 365 * _DAY, now)
            if _is_ad(e) and (e.get("type") or "").upper() != "INCOME"]
    if not exps:
        return []
    orders = profit._orders(now - 365 * _DAY, now)
    idx = profit._sku_index()
    tax = profit.tax_rate()

    # kunlik tushum va reklamagacha foyda
    rev_day, prof_day = defaultdict(float), defaultdict(float)
    for o in orders:
        if (o.get("status") or "").upper() == "CANCELED":
            continue
        ts = profit._to_ms(o.get("date") or o.get("dateIssued"))
        if ts is None:
            continue
        _, _, _, rev, comm, logi, cost, _ = profit._row_profit(o, idx, tax)
        rev_day[_day(ts)] += rev
        prof_day[_day(ts)] += rev - comm - logi - cost - rev * tax

    ad_day = defaultdict(float)
    campaigns = defaultdict(lambda: {"cost": 0.0, "days": set()})
    for e in exps:
        amt = profit.expense_amount(e)
        m = _CAMPAIGN.search(e.get("name") or "")
        ts = profit._to_ms(e.get("dateService") or e.get("dateCreated"))
        day = m.group(1) if m else (_day(ts) if ts else None)
        if not day:
            continue
        ad_day[day] += amt
        if m:
            c = campaigns[m.group(2)]
            c["cost"] += amt
            c["days"].add(day)

    findings = []
    # 1) oxirgi 30 kun
    last30 = {_day(now - i * _DAY) for i in range(30)}
    ads30 = sum(ad_day[d] for d in last30)
    if ads30 > 0:
        rev30 = sum(rev_day[d] for d in last30)
        prof30 = sum(prof_day[d] for d in last30)
        drr = ads30 / rev30 if rev30 else 1
        if ads30 >= prof30:
            findings.append({
                "key": "reklama:30", "source": "reklama", "level": "red", "urgent": True,
                "title": f"Reklama foydadan katta: oxirgi 30 kunda {profit.fmt(ads30)} so'm",
                "text": f"Reklamagacha foyda {profit.fmt(prof30)} so'm, reklama {profit.fmt(ads30)} so'm "
                        f"(tushumning {drr * 100:.0f}%). Ya'ni reklama sotuvni zararga aylantiryapti.",
                "action": "Kabinet → Targ'ib qilish: stavkalarni pasaytiring yoki eng kam sotilayotgan tovarlar reklamasini to'xtating.",
                "money": ads30 - max(prof30, 0),
            })
        elif drr > 0.15:
            findings.append({
                "key": "reklama:30", "source": "reklama", "level": "orange",
                "title": f"Reklama tushumning {drr * 100:.0f}% ini olyapti",
                "text": f"Oxirgi 30 kunda reklama {profit.fmt(ads30)} so'm, reklamagacha foyda {profit.fmt(prof30)} so'm — "
                        f"foydaning {ads30 / prof30 * 100:.0f}% i reklamaga ketyapti.",
                "action": "Qaysi kampaniya sotuv olib kelayotganini tekshiring; 15% dan yuqori ulush odatda qimmat.",
                "money": ads30 - rev30 * 0.15,
            })

    # 2) sotuvsiz kampaniyalar (oxirgi 90 kun, kamida 3 kun ishlagan)
    recent = {_day(now - i * _DAY) for i in range(90)}
    for cid, c in campaigns.items():
        days = c["days"] & recent
        if len(days) >= 3 and c["cost"] > 0 and sum(rev_day[d] for d in days) == 0:
            findings.append({
                "key": f"kampaniya:{cid}", "source": "reklama", "level": "red",
                "title": f"Kampaniya #{cid}: {profit.fmt(c['cost'])} so'm sarflandi, sotuv yo'q",
                "text": f"Kampaniya ishlagan {len(days)} kun davomida birorta ham sotuv bo'lmagan.",
                "action": "Kampaniyani to'xtating yoki tovar kartochkasi va narxini qayta ko'rib chiqing.",
                "money": c["cost"] / max(1, len(days)) * 30,
            })

    # 3) tarixiy saboq (reklama bo'lgan oylar, oxirgi 12 oy)
    if ads30 == 0:
        months = defaultdict(lambda: [0.0, 0.0, 0.0])  # reklama, tushum, reklamagacha foyda
        for d, v in ad_day.items():
            months[d[:7]][0] += v
        for d, v in rev_day.items():
            if d[:7] in months:
                months[d[:7]][1] += v
                months[d[:7]][2] += prof_day[d]
        ads, rev, prof = (sum(m[i] for m in months.values()) for i in range(3))
        if ads > 0:
            worst = max(months.items(), key=lambda kv: kv[1][0] - kv[1][2])
            findings.append({
                "key": "reklama:tarix", "source": "reklama", "level": "green",
                "title": f"O'tgan reklama: {profit.fmt(ads)} so'm, tushumning {ads / rev * 100 if rev else 100:.0f}%",
                "text": f"Reklama bo'lgan oylarda reklamagacha foyda {profit.fmt(prof)} so'm edi. "
                        f"Eng og'ir oy — {worst[0]}: reklama {profit.fmt(worst[1][0])}, foyda {profit.fmt(worst[1][2])}.",
                "action": "Reklamani qayta yoqsangiz, biz har kuni DRR ni kuzatamiz va foydadan oshsa ogohlantiramiz.",
                "money": 0,
            })
    return findings
