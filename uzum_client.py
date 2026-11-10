"""
Uzum Seller Open API bilan ishlovchi modul.

Rasmiy manzil: https://api-seller.uzum.uz/api/seller-openapi
Kalit sarlavhaga "Bearer" so'zisiz yoziladi: Authorization: <token>

Token bo'lmasa (DEMO_MODE), hamma so'rovlar demo_data.py dan javob qaytaradi.
"""
import time
import logging

import requests

import config
import demo_data

log = logging.getLogger("uzum")


class UzumError(Exception):
    pass


class UzumClient:
    def __init__(self, token: str = None, base: str = None, demo: bool = None):
        self.token = (token if token is not None else config.UZUM_API_TOKEN).replace("Bearer ", "").strip()
        self.base = (base or config.UZUM_API_BASE).rstrip("/")
        self.demo = config.DEMO_MODE if demo is None else demo
        self._last_call = 0.0
        self.session = requests.Session()

    # ---------- past darajadagi so'rov ----------
    def _request(self, method: str, path: str, params=None, json=None, retries: int = 4):
        # Uzum sekundiga cheklov qo'yadi: so'rovlar orasida kamida 0.5 soniya
        wait = 0.5 - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        url = f"{self.base}{path}"
        headers = {"Authorization": self.token, "Accept": "application/json"}
        for attempt in range(retries + 1):
            self._last_call = time.time()
            try:
                r = self.session.request(method, url, params=params, json=json, headers=headers, timeout=30)
            except requests.RequestException as e:
                if attempt == retries:
                    raise UzumError(f"Tarmoq xatosi: {e}")
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429:
                if "day" in r.text.lower():
                    raise UzumError("Uzum kunlik so'rov limiti tugadi. Ertaga qayta urinib ko'ring.")
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (401, 403):
                raise UzumError("Uzum tokeni noto'g'ri yoki bekor qilingan (401/403). .env faylini tekshiring.")
            if r.status_code >= 400:
                raise UzumError(f"Uzum xatosi {r.status_code}: {r.text[:300]}")
            data = r.json() if r.content else {}
            if isinstance(data, dict) and "payload" in data:
                data = data["payload"]
            return data
        raise UzumError("Uzum javob bermadi (ko'p marta 429).")

    def _paged(self, path: str, key: str, params: dict, size: int):
        """Sahifalab hamma qatorlarni yig'adi (sahifalar 0 dan boshlanadi)."""
        out, page = [], 0
        while True:
            p = dict(params, page=page, size=size)
            data = self._request("GET", path, params=p)
            items = data.get(key, []) if isinstance(data, dict) else (data or [])
            out.extend(items)
            if len(items) < size or page > 500:
                break
            page += 1
        return out

    # ---------- yuqori darajadagi funksiyalar ----------
    def shops(self):
        if self.demo:
            return demo_data.SHOPS
        data = self._request("GET", "/v1/shops")
        return data if isinstance(data, list) else data.get("shops", [])

    def products(self, shop_id: int):
        """Do'kondagi barcha tovarlar va ularning SKU lari."""
        if self.demo:
            return demo_data.PRODUCTS
        return self._paged(f"/v1/product/shop/{shop_id}", "productList", {}, size=100)

    def finance_orders(self, shop_ids, date_from_ms: int, date_to_ms: int = None):
        """Sotilgan tovarlar: narx, soni, komissiya, logistika, holati."""
        if self.demo:
            to = date_to_ms or int(time.time() * 1000)
            return [o for o in demo_data.FINANCE_ORDERS if date_from_ms <= o["date"] <= to]
        params = {"shopIds": shop_ids, "group": "false", "dateFrom": date_from_ms}
        if date_to_ms:
            params["dateTo"] = date_to_ms
        return self._paged("/v1/finance/orders", "orderItems", params, size=1000)

    def expenses(self, shop_ids, date_from_ms: int, date_to_ms: int = None):
        """Uzum ushlab qolgan xarajatlar: saqlash, reklama, jarimalar va h.k."""
        if self.demo:
            to = date_to_ms or int(time.time() * 1000)
            return [e for e in demo_data.EXPENSES if date_from_ms <= e["dateCreated"] <= to]
        params = {"shopIds": shop_ids, "dateFrom": date_from_ms}
        if date_to_ms:
            params["dateTo"] = date_to_ms
        return self._paged("/v1/finance/expenses", "payments", params, size=1000)

    def send_price(self, shop_id: int, product_id: int, sku_id: int, sell_price: int, full_price: int):
        """SKU narxini o'zgartiradi. DIQQAT: haqiqiy do'konda narx darhol o'zgaradi."""
        if self.demo:
            demo_data.apply_price(product_id, sku_id, sell_price, full_price)
            return {"demo": True}
        body = {"productId": product_id,
                "skuList": [{"skuId": sku_id, "fullPrice": int(full_price), "sellPrice": int(sell_price)}]}
        return self._request("POST", f"/v1/product/{shop_id}/sendPriceData", json=body)


client = UzumClient()
