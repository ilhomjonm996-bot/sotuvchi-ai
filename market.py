"""
Bozor tahlili va raqobatchilarni kuzatish.

Ma'lumot manbasi (SOURCE):
  - demo   — namunaviy bozor (demo rejimda, hech qayerga so'rov ketmaydi)
  - manual — raqobatchi narxini sotuvchi o'zi kiritadi (haqiqiy do'konda hozircha shu)
  - Uzum vitrinasidan avtomatik olish hali ulanmagan: Uzum'da raqobatchilar uchun rasmiy API yo'q.
    Rasmiy yoki ruxsat etilgan manba paydo bo'lsa, faqat `_live_search` va `_live_product` ni yozish kifoya.

Raqobatchi qo'shish: Uzum'dagi tovar havolasi (…/product/nomi-2203614) yoki raqami (2203614).
Har kuni bitta holat (snapshot) saqlanadi: narx, chizilgan narx, reyting, sharhlar, buyurtmalar, qoldiq.
"""
import re
import statistics
import zlib
from datetime import date, timedelta
from random import Random

import db
import profit
import tenant


class MarketUnavailable(Exception):
    pass


LIVE_MSG = ("Uzum vitrinasidan avtomatik ma'lumot olish hali ulanmagan (Uzum'da buning uchun rasmiy API yo'q). "
            "Hozircha raqobatchi narxini qo'lda kiriting.")


def source():
    return "demo" if tenant.is_demo() else "manual"


def live():
    """Avtomatik manba bormi (demo yoki ulangan haqiqiy manba)."""
    return source() == "demo"


def today():
    return date.today().isoformat()


def parse_product_id(text):
    """Havola yoki raqamdan Uzum tovar raqamini ajratadi."""
    t = (text or "").strip()
    m = re.search(r"/product/[^?#\s]*?-(\d{4,})(?:[/?#]|$)", t) or re.fullmatch(r"(?:um)?(\d{4,})", t)
    return int(m.group(1)) if m else None


# ======================================================================
# Demo bozor — barqaror (har safar bir xil) namunaviy ma'lumot
# ======================================================================
_SHOPS = ["TexnoUz", "Mega Savdo", "Shahzoda Shop", "OptomBozor", "Comfort Home", "SmartTrend", "Asia Market",
          "Sifat Plus", "Bek Store", "Lola Market", "Navro'z", "Urban Style"]
_ADJ = ["sifatli", "arzon", "original", "premium", "yangi model", "kafolatli", "chegirmali", "sovg'abop"]

# Demo do'kon tovarlariga bog'langan raqobatchilar (ssenariylar)
_SCENARIOS = {
    7004001: dict(sku=9004, title="Termos 1 L, ikki qavatli po'lat, 24 soat issiq", shop="ThermoPro",
                  base=84000, full=150000, stock=140, orders=1200, rating=4.8, reviews=310),
    7006001: dict(sku=9006, title="Erkaklar uchun charm kamar, avtomatik to'qa", shop="Mega Savdo",
                  base=85000, full=140000, stock=60, orders=480, rating=4.6, reviews=95, drop_day=3, drop_to=69000),
    7008001: dict(sku=9008, title="iPhone 15 uchun silikon g'ilof, MagSafe", shop="SmartTrend",
                  base=52000, full=99000, stock=35, orders=2600, rating=4.7, reviews=540, out_day=2),
    7005001: dict(sku=9005, title="TWS simsiz quloqchin, shovqin bosuvchi", shop="TexnoUz",
                  base=139000, full=220000, stock=80, orders=900, rating=4.5, reviews=210),
}


def _rng(*parts):
    return Random(zlib.crc32("|".join(map(str, parts)).encode()))


def _demo_point(pid, day):
    """Raqobatchi tovarning berilgan kundagi holati (demo)."""
    d = date.fromisoformat(day) if isinstance(day, str) else day
    ago = (date.today() - d).days
    sc = _SCENARIOS.get(pid)
    if not sc:
        r = _rng("p", pid)
        sc = dict(title=f"Tovar #{pid}", shop=r.choice(_SHOPS), base=r.randrange(30, 300) * 1000,
                  stock=r.randrange(5, 300), orders=r.randrange(50, 3000), rating=round(r.uniform(4.0, 4.9), 1),
                  reviews=r.randrange(5, 600))
        sc["full"] = int(sc["base"] * 1.7 // 1000 * 1000)
    r = _rng("d", pid, d.isoformat())
    price = sc["base"]
    if sc.get("drop_day") is not None and ago < sc["drop_day"]:
        price = sc["drop_to"]
    elif r.random() < 0.08:
        price = int(price * 1.05 // 1000 * 1000)  # vaqti-vaqti bilan kichik tebranish
    daily = max(1, sc["orders"] // 300)
    stock = max(0, sc["stock"] + ago * daily // 2)
    if sc.get("out_day") is not None and ago < sc["out_day"]:
        stock = 0
    return dict(title=sc["title"], shop=sc["shop"], price=price, full_price=sc["full"],
                rating=sc["rating"], reviews=max(0, sc["reviews"] - ago // 3),
                orders=max(0, sc["orders"] - ago * daily), stock=stock)


def _demo_search(query, limit=40):
    q = (query or "").strip().lower()
    base_title, base_price = q.capitalize() or "Tovar", 90000
    for a in profit.price_advice():
        first = a["title"].split(",")[0]
        if q and (q in a["title"].lower() or a["title"].lower().split()[0] in q):
            base_title, base_price = first, a["price"] or base_price
            break
    r = _rng("s", q)
    items = []
    for i in range(limit):
        price = max(5000, int(base_price * r.lognormvariate(-0.1, 0.35) // 1000 * 1000))
        orders = int(r.paretovariate(1.3) * 40)
        items.append(dict(product_id=8000000 + zlib.crc32(q.encode()) % 900000 * 10 + i,
                          title=f"{base_title}, {r.choice(_ADJ)}", shop=r.choice(_SHOPS),
                          price=price, full_price=int(price * r.uniform(1.3, 2.2) // 1000 * 1000),
                          rating=round(r.uniform(3.9, 5.0), 1), reviews=int(orders * r.uniform(0.05, 0.25)),
                          orders=orders, stock=r.choice([0, r.randrange(3, 400)]) if i % 7 == 6 else r.randrange(3, 400)))
    return items


# ======================================================================
# Manba orqali o'qish
# ======================================================================
SEARCH_MSG = ("Bozor tahlili uchun Uzum vitrinasidan avtomatik ma'lumot kerak — u hali ulanmagan "
              "(Uzum'da rasmiy API yo'q). Hozircha bu bo'limni demo rejimda ko'rish mumkin (botda /demo).")


def _live_search(query):
    raise MarketUnavailable(SEARCH_MSG)


def _live_product(pid):
    raise MarketUnavailable(LIVE_MSG)


def search(query):
    return _demo_search(query) if source() == "demo" else _live_search(query)


def fetch_product(pid):
    return _demo_point(pid, today()) if source() == "demo" else _live_product(pid)


# ======================================================================
# Raqobatchilar
# ======================================================================
def add(link, my_sku_id=None, title=None, price=None, stock=None):
    """Raqobatchini qo'shadi. Avtomatik manba bo'lmasa — nom va narx qo'lda beriladi."""
    pid = parse_product_id(link)
    if not pid:
        raise ValueError("Havoladan tovar raqamini topib bo'lmadi. Uzum'dagi tovar sahifasi havolasini yuboring.")
    if any(c["product_id"] == pid for c in db.list_competitors()):
        raise ValueError("Bu raqobatchi allaqachon ro'yxatda.")
    url = link if str(link).startswith("http") else f"https://uzum.uz/uz/product/{pid}"
    if live():
        info = fetch_product(pid)
        cid = db.add_competitor(pid, info["title"], info["shop"], url, my_sku_id, manual=0)
        _backfill(cid, pid)
        return cid
    if not title or not price:
        raise ValueError("Raqobatchi nomi va narxini kiriting.")
    cid = db.add_competitor(pid, title.strip()[:200], "", url, my_sku_id, manual=1)
    record_price(cid, price, stock)
    return cid


def record_price(cid, price, stock=None):
    """Qo'lda kiritilgan narx (bugungi kun uchun)."""
    price = float(price)
    if price <= 0:
        raise ValueError("Narx musbat bo'lishi kerak.")
    return db.add_snapshot(cid, today(), price=price, stock=None if stock in (None, "") else int(stock))


def _backfill(cid, pid, days=30):
    if source() != "demo":
        return
    for ago in range(days, -1, -1):
        day = (date.today() - timedelta(days=ago)).isoformat()
        p = _demo_point(pid, day)
        db.add_snapshot(cid, day, **{k: p[k] for k in ("price", "full_price", "rating", "reviews", "orders", "stock")})


def ensure_demo():
    """Demo do'konda birinchi kirishda namunaviy raqobatchilarni qo'shib qo'yadi."""
    if source() != "demo" or db.get_setting("demo_competitors"):
        return
    db.set_setting("demo_competitors", "1")
    for pid, sc in _SCENARIOS.items():
        cid = db.add_competitor(pid, sc["title"], sc["shop"], "", sc["sku"])  # namunaviy — tashqi havola yo'q
        _backfill(cid, pid)


def refresh_all():
    """Har kuni: avtomatik manbadan bugungi holatni yozadi. Qaytaradi: yangilangan soni."""
    if not live():
        return 0
    n = 0
    for c in db.list_competitors():
        if c["manual"]:
            continue
        try:
            p = fetch_product(c["product_id"])
        except MarketUnavailable:
            return n
        db.add_snapshot(c["id"], today(), **{k: p.get(k) for k in ("price", "full_price", "rating", "reviews", "orders", "stock")})
        n += 1
    return n


def _at(snaps, days_ago):
    """`days_ago` kun oldingi (yoki undan oldingi eng yaqin) holat."""
    target = (date.today() - timedelta(days=days_ago)).isoformat()
    older = [s for s in snaps if s["day"] <= target]
    return older[-1] if older else None


def overview():
    """Panel va agent uchun: har bir raqobatchi + oxirgi holat + o'zgarishlar + o'z narxim."""
    ensure_demo()
    advice = {a["sku_id"]: a for a in profit.price_advice()}
    out = []
    for c in db.list_competitors():
        snaps = db.snapshots(c["id"], 60)
        last = snaps[-1] if snaps else None
        week = _at(snaps, 7)
        mine = advice.get(c["my_sku_id"]) if c["my_sku_id"] else None
        row = dict(c, last=last, snaps=snaps, mine=mine, price_change=None, sold7=None, diff=None, was_in_stock=None)
        if last and week and week["price"] and last["price"]:
            row["price_change"] = (last["price"] - week["price"]) / week["price"]
        if last and week and last.get("orders") is not None and week.get("orders") is not None:
            row["sold7"] = max(0, last["orders"] - week["orders"])
        if last and mine and mine.get("price") and last.get("price"):
            row["diff"] = (last["price"] - mine["price"]) / mine["price"]  # manfiy = raqobatchi arzonroq
        if len(snaps) >= 2:
            row["was_in_stock"] = any((s.get("stock") or 0) > 0 for s in snaps[-8:-1])
        out.append(row)
    return out


def my_products():
    """Raqobatchini bog'lash uchun o'z tovarlarim ro'yxati."""
    return [{"sku_id": a["sku_id"], "title": a["title"], "price": a["price"]} for a in profit.price_advice()]


# ======================================================================
# Bozor (nisha) tahlili
# ======================================================================
def _pct(vals, q):
    if not vals:
        return 0
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def analyze(query):
    """Kalit so'z bo'yicha bozor: narx oralig'i, talab, raqobat, eng yaxshi narx segmenti, mening o'rnim."""
    items = [i for i in search(query) if i.get("price")]
    if not items:
        return None
    prices = [i["price"] for i in items]
    orders = [i.get("orders") or 0 for i in items]
    total = sum(orders) or 1
    top = sorted(items, key=lambda i: -(i.get("orders") or 0))
    top3_share = sum(i.get("orders") or 0 for i in top[:3]) / total
    shops = {i.get("shop") for i in items}

    # narx segmentlari (kvartillar): har bir tovarga o'rtacha qancha buyurtma to'g'ri keladi
    edges = [min(prices) - 1, _pct(prices, .25), _pct(prices, .5), _pct(prices, .75), max(prices)]
    segments = []
    for lo, hi in zip(edges, edges[1:]):
        seg = [i for i in items if lo < i["price"] <= hi]
        if seg:
            so = sum(i.get("orders") or 0 for i in seg)
            segments.append(dict(lo=lo + 1, hi=hi, count=len(seg), orders=so, per_item=so / len(seg)))
    best = max(segments, key=lambda s: s["per_item"]) if segments else None

    avg_orders = total / len(items)
    demand = "yuqori" if avg_orders >= 150 else "o'rtacha" if avg_orders >= 50 else "past"
    competition = "kuchli" if top3_share >= 0.6 or len(items) >= 35 and avg_orders < 50 else \
                  "o'rtacha" if top3_share >= 0.35 else "past"
    # nisha bahosi 1–10: talab (5 ballgacha) + raqobat erkinligi (5 ballgacha)
    score = max(1, min(10, round(min(5, avg_orders / 40) + 5 * (1 - top3_share))))

    mine = None
    q = (query or "").lower()
    for a in profit.price_advice():
        if q and q in a["title"].lower():
            med = statistics.median(prices)
            mine = dict(a, median=med, vs=(a["price"] - med) / med if med else 0)
            break

    if best:
        advice = (f"Eng ko'p buyurtma {profit.fmt(best['lo'])}–{profit.fmt(best['hi'])} so'm oralig'ida "
                  f"(har tovarga o'rtacha {best['per_item']:.0f} ta). ")
    else:
        advice = ""
    if competition == "kuchli":
        advice += "Bozorni bir nechta yirik sotuvchi egallagan — kirish uchun aniq farq (sifat, to'plam, rasm) kerak."
    elif demand == "past":
        advice += "Talab past — katta partiya olib kelishdan oldin kichik miqdorda sinab ko'ring."
    else:
        advice += "Talab bor va raqobat haddan tashqari emas — kirish yoki assortimentni kengaytirish mumkin."

    return dict(query=query, count=len(items), shops=len(shops), source=source(),
                price_min=min(prices), price_max=max(prices), price_median=statistics.median(prices),
                p25=_pct(prices, .25), p75=_pct(prices, .75),
                orders_total=sum(orders), avg_orders=avg_orders, top3_share=top3_share,
                avg_rating=statistics.mean(i.get("rating") or 0 for i in items),
                out_of_stock=sum(1 for i in items if i.get("stock") == 0),
                segments=segments, best=best, demand=demand, competition=competition, score=score,
                top=top[:10], mine=mine, advice=advice)
