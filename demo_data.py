"""
Namunaviy (demo) ma'lumotlar.

Uzum tokeni ulanmaguncha dastur shu ma'lumotlar bilan ishlaydi.
Ma'lumotlar Uzum API javoblari bilan bir xil tuzilishda.
"""
import random
import time
from datetime import datetime, timedelta

_DAY_MS = 24 * 3600 * 1000

SHOPS = [{"id": 100001, "name": "Demo Do'kon"}]

# (productId, skuId, nomi, sotuv narxi, tannarx, komissiya %, kunlik o'rtacha sotuv, logistika)
_CATALOG = [
    (5001, 9001, "Ayollar ko'ylagi, yozgi, paxta", 189000, 72000, 0.20, 3.2, 7000),
    (5002, 9002, "Bolalar sport kostyumi", 159000, 61000, 0.20, 2.1, 7000),
    (5003, 9003, "Oshxona pichoqlari to'plami, 6 dona", 129000, 58000, 0.15, 1.8, 6000),
    (5004, 9004, "Termos 1 litr, zanglamaydigan po'lat", 99000, 41000, 0.15, 2.6, 6000),
    (5005, 9005, "Simsiz quloqchin TWS", 119000, 79000, 0.10, 4.0, 5000),
    (5006, 9006, "Erkaklar charm kamari", 79000, 52000, 0.20, 1.1, 5000),
    (5007, 9007, "Yostiq jildi, atlas, 2 dona", 69000, 49000, 0.15, 0.9, 6000),
    (5008, 9008, "Telefon g'ilofi, iPhone 15", 49000, 14000, 0.20, 5.5, 4000),
]

PRODUCTS = []
for pid, sku, title, price, cost, comm, daily, logi in _CATALOG:
    PRODUCTS.append({
        "productId": pid,
        "title": title,
        "skuList": [{
            "skuId": sku,
            "skuTitle": title,
            "barcode": f"478{sku:010d}",
            "price": price,
            "fullPrice": int(price * 1.35 // 1000 * 1000),
            "purchasePrice": cost,
            "quantityActive": random.Random(sku).randint(3, 120),
            "quantityFbs": 0,
        }],
        "_commission_rate": comm,
        "_daily": daily,
        "_logistics": logi,
    })


# Tekshiruvlar (checks/) uchun namunaviy signallar
PRODUCTS[0].update(returnedPercentage=41.0, quantitySold=350, quantityReturned=240)  # ko'ylak — o'lcham muammosi
PRODUCTS[4]["skuList"][0]["quantityActive"] = 0    # quloqchin — tugagan
PRODUCTS[7]["skuList"][0]["quantityActive"] = 12   # g'ilof — 2–3 kunda tugaydi
_now = int(time.time() * 1000)
PRODUCTS[5]["skuList"][0]["specialOffer"] = {      # kamar — zarar narxdagi aksiyada turibdi
    "inOffer": True, "hasRecommendation": True, "mechanicType": "UZUM_PROMO", "mechanicPrice": 69000,
    "endDate": _now + 5 * _DAY_MS, "promoName": "Qora juma"}
PRODUCTS[2]["skuList"][0]["specialOffer"] = {      # pichoqlar — foydali aksiya, hali qo'shilmagan
    "inOffer": False, "hasRecommendation": True, "mechanicType": "UZUM_PROMO", "mechanicPrice": 109000,
    "endDate": _now + 9 * _DAY_MS, "promoName": "Qishki chegirmalar"}
PRODUCTS[6].update(rating="3.2", feedbackQuantity=14)                       # yostiq jildi — past reyting
PRODUCTS[1]["moderationStatus"] = {"value": "HAS_COMPLAINTS", "title": "Izohlar bor"}
PRODUCTS[3].update(viewers=1240, conversion=0.4)                            # termos — past konversiya
for _i in (1, 4, 6):
    PRODUCTS[_i]["allFiltersFilled"] = False


def _build_orders(days: int = 400):
    rng = random.Random(42)
    now = int(time.time() * 1000)
    rows = []
    oid = 700000
    today = datetime.now()
    nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)  # keyingi oy
    for d in range(days, -1, -1):
        day_ts = now - d * _DAY_MS
        day = datetime.fromtimestamp(day_ts / 1000)
        season = 1.0 + 0.35 * (1 if (d % 365) in range(0, 20) else 0)  # mavsumiy cho'qqi
        for p in PRODUCTS:
            sku = p["skuList"][0]
            boost = season
            if p["productId"] == 5004 and (day.year, day.month) == (nxt.year - 1, nxt.month):
                boost *= 3  # termos: o'tgan yili keyingi oyda mavsum bo'lgan (mavsum agenti uchun)
            n = int(rng.gauss(p["_daily"] * boost, p["_daily"] * 0.5))
            for _ in range(max(0, n)):
                oid += 1
                amount = 1
                sell = sku["price"]
                if p["productId"] == 5008 and d > 60:
                    sell = 45000  # g'ilof: 60 kun oldin narx 45 000 → 49 000 ga ko'tarilgan (narx tajribasi uchun)
                commission = int(sell * amount * p["_commission_rate"])
                logistics = p["_logistics"] * amount
                status = rng.choices(["TO_WITHDRAW", "PROCESSING", "CANCELED"], [0.86, 0.08, 0.06])[0]
                if d < 3 and status == "TO_WITHDRAW":
                    status = "PROCESSING"
                rows.append({
                    "id": oid,
                    "orderId": oid,
                    "productId": p["productId"],
                    "skuId": sku["skuId"],
                    "skuTitle": sku["skuTitle"],
                    "productTitle": p["title"],
                    "sellPrice": sell,
                    "amount": amount,
                    "commission": commission,
                    "logisticDeliveryFee": logistics,
                    "sellerProfit": sell * amount - commission - logistics,
                    "purchasePrice": sku["purchasePrice"],
                    "amountReturns": 1 if rng.random() < 0.03 else 0,
                    "status": status,
                    "date": day_ts - rng.randint(0, 20 * 3600 * 1000),
                })
    return rows


def _build_expenses(days: int = 400):
    rng = random.Random(7)
    now = int(time.time() * 1000)
    rows = []
    for d in range(days, -1, -1):
        ts = now - d * _DAY_MS
        if d % 7 == 0:
            rows.append({"name": "Saqlash xizmati", "source": "STORAGE", "amount": rng.randint(15, 40) * 1000,
                         "type": "OUTCOME", "dateCreated": ts})
        if d % 3 == 0:
            rows.append({"name": "Reklama (CPO)", "source": "ADVERTISING", "amount": rng.randint(20, 90) * 1000,
                         "type": "OUTCOME", "dateCreated": ts})
        if d < 92:  # qaytgan tovar omborda yotibdi — har kuni pullik saqlash
            rows.append({"name": "5004417 - sonli yukxat boʻyicha yigʻilgan qaytarishni saqlash xizmatlari uchun toʻlov",
                         "source": "Ombor", "amount": 1, "paymentPrice": 1000, "type": "OUTCOME", "dateCreated": ts})
        if rng.random() < 0.02:
            rows.append({"name": "Jarima: kechikkan topshirish", "source": "PENALTY", "amount": 50000,
                         "type": "OUTCOME", "dateCreated": ts})
    return rows


FINANCE_ORDERS = _build_orders()
EXPENSES = _build_expenses()

# Kompensatsiya radari uchun: bekor qilingan buyurtmalar logistikasi qaytarilmagan + bitta takroriy yechish
PRODUCTS[0]["quantityDefected"] = 2
for _o in [o for o in FINANCE_ORDERS if o["status"] == "CANCELED"][-6:]:
    EXPENSES.append({"name": f"Buyurtma № {_o['orderId']} uchun logistika xizmatlari uchun to'lov.", "source": "Logistika",
                     "amount": 1, "paymentPrice": 6000, "type": "OUTCOME", "dateCreated": _o["date"]})
_dup = [o for o in FINANCE_ORDERS if o["status"] == "TO_WITHDRAW"][-1]
for _ in range(3):
    EXPENSES.append({"name": f"Buyurtma № {_dup['orderId']} uchun logistika xizmatlari uchun to'lov.", "source": "Logistika",
                     "amount": 1, "paymentPrice": 7000, "type": "OUTCOME", "dateCreated": _dup["date"]})


def apply_price(product_id: int, sku_id: int, sell_price: int, full_price: int) -> None:
    """Demo rejimda narx o'zgarishini xotirada saqlaydi."""
    for p in PRODUCTS:
        if p["productId"] == product_id:
            for s in p["skuList"]:
                if s["skuId"] == sku_id:
                    s["price"] = sell_price
                    s["fullPrice"] = full_price
