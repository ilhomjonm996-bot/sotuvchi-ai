"""
Taxminiy tannarx kiritish (egasi aniq tannarxni eslay olmaganda).

Tovar turiga qarab sotuv narxining ma'lum ulushi olinadi:
  telefon g'ilofi/chexol      ~25%   (arzon xarid, yuqori ustama)
  kiyim, kolgotka, qo'lqop    ~40%
  oyoq kiyim                  ~45%
  gadjet, o'yinchoq, chiroq   ~45%
  boshqalar                   ~40%
Qo'shimcha (yetkazib kelish, qadoqlash) — tovar hajmiga qarab 1 000 – 8 000 so'm.

Faqat tannarxi hali KIRITILMAGAN SKU larga yoziladi (qo'lda kiritilganlar o'zgarmaydi).
Ishlatish:  py estimate_costs.py
"""
import db
import profit

RULES = [
    (("qopqo", "g'ilof", "gilof", "g‘ilof", "chexol", "tpu"), 0.25, 2000),
    (("botinka", "oyoq kiyim", "etik", "krasovka"), 0.45, 8000),
    (("pijama", "vodolaska", "kolgotka", "qo'lqop", "qolqop", "qo‘lqop", "paypoq", "shim"), 0.40, 3000),
    (("samolyot", "bumerang", "soat", "lampa", "chiroq", "zaryad", "dazmol", "namlagich", "gilamcha", "fonar"), 0.45, 5000),
]
DEFAULT = (0.40, 3000)


def rule_for(title):
    t = title.lower()
    for words, ratio, extra in RULES:
        if any(w in t for w in words):
            return ratio, extra
    return DEFAULT


def run():
    existing = db.get_costs()
    total = 0
    for shop in profit._cached("shops", profit.client.shops):
        db.set_setting("shop_id", shop["id"])
        profit.clear_cache()
        try:
            skus = profit.skus()
        except profit.UzumError as e:
            print(f"{shop['name']}: o'tkazib yuborildi ({e})")
            continue
        n = 0
        for s in skus:
            c = existing.get(s["sku_id"])
            if (c and (c["unit_cost"] or c["extra_cost"])) or not s["price"]:
                continue
            ratio, extra = rule_for(s["title"])
            if s["price"] < 30000:
                extra = min(extra, 1000)
            cost = round(s["price"] * ratio / 1000) * 1000 or 1000
            db.set_cost(s["sku_id"], cost, extra, s["title"])
            n += 1
        print(f"{shop['name']}: {n} ta SKU ga taxminiy tannarx yozildi")
        total += n
    db.set_setting("costs_estimated", "1")
    return total


if __name__ == "__main__":
    first = profit.shop()["id"]
    run()
    db.set_setting("shop_id", first)
