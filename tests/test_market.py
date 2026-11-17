"""
Bozor tahlili va raqobatchi kuzatuvi testlari (demo va qo'lda kiritish rejimlari).

Ishga tushirish:   py -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("SECRET_ENC_KEY", Fernet.generate_key().decode())

import config  # noqa: E402

if not str(config.DB_PATH).startswith(tempfile.gettempdir()):
    config.DB_PATH = Path(tempfile.mkdtemp(prefix="sotuvchi_mtest_")) / "test.db"
config.DEMO_MODE = False

import db  # noqa: E402
import market  # noqa: E402
import tenant  # noqa: E402
from checks import raqobat  # noqa: E402


class MarketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init()
        cls.D = db.create_seller(chat_id="2001", name="Demo", demo=1)

    def test_parse_link(self):
        self.assertEqual(market.parse_product_id("https://uzum.uz/uz/product/termos-qahva-va-2203614?skuId=7896029"), 2203614)
        self.assertEqual(market.parse_product_id("2203614"), 2203614)
        self.assertEqual(market.parse_product_id("um2203614"), 2203614)
        self.assertIsNone(market.parse_product_id("salom dunyo"))

    def test_demo_competitors_and_signals(self):
        with tenant.use(self.D):
            rows = market.overview()
            self.assertEqual(len(rows), 4)
            found = {f["title"] for f in raqobat.run()}
            self.assertTrue(any("arzonroq" in t for t in found))
            self.assertTrue(any("tushirdi" in t for t in found))
            self.assertTrue(any("tugadi" in t for t in found))
            self.assertEqual(len(market.overview()), 4)  # ikkinchi marta qayta qo'shilmaydi

    def test_demo_analysis(self):
        with tenant.use(self.D):
            a = market.analyze("termos")
            self.assertGreater(a["count"], 10)
            self.assertTrue(1 <= a["score"] <= 10)
            self.assertLessEqual(a["p25"], a["price_median"])
            self.assertLessEqual(a["price_median"], a["p75"])
            self.assertIsNotNone(a["mine"])  # demo do'konda termos bor

    def test_manual_mode(self):
        M = db.create_seller(chat_id="2002", name="Real")
        db.update_seller(M, token_enc="x")  # haqiqiy do'kon (demo emas) belgisi
        with tenant.use(M):
            self.assertFalse(market.live())
            with self.assertRaises(market.MarketUnavailable):
                market.analyze("termos")
            with self.assertRaises(ValueError):
                market.add("https://uzum.uz/uz/product/x-1234567")  # nom va narxsiz
            cid = market.add("https://uzum.uz/uz/product/x-1234567", title="Raqib", price=50000)
            with self.assertRaises(ValueError):
                market.add("1234567", title="Raqib", price=1)  # takror
            self.assertTrue(market.record_price(cid, 45000))
            self.assertEqual(db.snapshots(cid)[-1]["price"], 45000)
            with self.assertRaises(ValueError):
                market.record_price(cid, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
