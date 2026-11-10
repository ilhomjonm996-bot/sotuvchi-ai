"""
Namunaviy (demo) ma'lumotlar.

Uzum tokeni ulanmaguncha dastur shu ma'lumotlar bilan ishlaydi.
Ma'lumotlar Uzum API javoblari bilan bir xil tuzilishda.
"""
import random
import time

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


def _build_orders(days: int = 400):
    rng = random.Random(42)
    now = int(time.time() * 1000)
    rows = []
    oid = 700000
    for d in range(days, -1, -1):
        day_ts = now - d * _DAY_MS
        season = 1.0 + 0.35 * (1 if (d % 365) in range(0, 20) else 0)  # mavsumiy cho'qqi
        for p in PRODUCTS:
            sku = p["skuList"][0]
            n = int(rng.gauss(p["_daily"] * season, p["_daily"] * 0.5))
            for _ in range(max(0, n)):
                oid += 1
                amount = 1
                sell = sku["price"]
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
        if rng.random() < 0.02:
            rows.append({"name": "Jarima: kechikkan topshirish", "source": "PENALTY", "amount": 50000,
                         "type": "OUTCOME", "dateCreated": ts})
    return rows


FINANCE_ORDERS = _build_orders()
EXPENSES = _build_expenses()


def apply_price(product_id: int, sku_id: int, sell_price: int, full_price: int) -> None:
    """Demo rejimda narx o'zgarishini xotirada saqlaydi."""
    for p in PRODUCTS:
        if p["productId"] == product_id:
            for s in p["skuList"]:
                if s["skuId"] == sku_id:
                    s["price"] = sell_price
                    s["fullPrice"] = full_price
