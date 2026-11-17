"""
Ko'p mijozli rejim: ajratish testlari — "A sotuvchi B ning ma'lumotini ko'ra olmaydi".

Ishga tushirish (loyiha papkasidan):   py -m unittest discover -s tests -v
Testlar vaqtinchalik bazada ishlaydi, haqiqiy data/sotuvchi.db ga tegmaydi.
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet  # noqa: E402

os.environ["SECRET_ENC_KEY"] = Fernet.generate_key().decode()
_tmp = tempfile.mkdtemp(prefix="sotuvchi_test_")

import config  # noqa: E402

config.DB_PATH = Path(_tmp) / "test.db"
config.DEMO_MODE = False
config.WEB_PASSWORD = ""

import db  # noqa: E402
import profit  # noqa: E402
import secure  # noqa: E402
import tenant  # noqa: E402


class MultiTenantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init()
        cls.A = db.create_seller(chat_id="1001", name="A", demo=1)
        cls.B = db.create_seller(chat_id="1002", name="B", demo=1)

    def test_costs_isolated(self):
        with tenant.use(self.A):
            db.set_cost(9001, 50000, 2000, "A tovari")
        with tenant.use(self.B):
            self.assertEqual(db.get_costs(), {})
            db.set_cost(9001, 99999, 0, "B tovari")  # bir xil SKU — boshqa sotuvchi
        with tenant.use(self.A):
            self.assertEqual(db.get_costs()[9001]["unit_cost"], 50000)

    def test_settings_isolated(self):
        with tenant.use(self.A):
            db.set_setting("tax_rate", "0.12")
        with tenant.use(self.B):
            self.assertIsNone(db.get_setting("tax_rate"))

    def test_proposals_isolated(self):
        with tenant.use(self.A):
            pid = db.add_proposal(shop_id=1, product_id=1, sku_id=1, title="A", old_price=1, new_price=2,
                                  full_price=3, min_price=1, reason="test")
        with tenant.use(self.B):
            self.assertIsNone(db.get_proposal(pid))
            self.assertEqual(db.list_proposals(), [])
            db.set_proposal_status(pid, "approved")  # B o'zgartirishga urinadi
            ok, _ = profit.approve_proposal(pid)
            self.assertFalse(ok)
        with tenant.use(self.A):
            self.assertEqual(db.get_proposal(pid)["status"], "pending")

    def test_cards_isolated(self):
        with tenant.use(self.A):
            cid = db.add_card("A kartochka", {}, {}, None, str(Path(_tmp) / "card_A_test.jpg"))
        with tenant.use(self.B):
            self.assertIsNone(db.get_card(cid))
            self.assertEqual(db.list_cards(), [])
        self.assertEqual(db.card_file_owner("card_A_test.jpg"), self.A)

    def test_token_encrypted(self):
        raw = "uzum-test-token-1234567890abcdef"
        db.update_seller(self.A, token_enc=secure.encrypt(raw))
        stored = db.get_seller(self.A)["token_enc"]
        self.assertNotIn(raw, stored)
        self.assertEqual(tenant.token(self.A), raw)
        self.assertNotEqual(tenant.token(self.B), raw)
        self.assertIsNot(tenant.client(self.A), tenant.client(self.B))
        db.update_seller(self.A, token_enc=None)
        tenant.forget(self.A)

    def test_cache_isolated(self):
        with tenant.use(self.A):
            self.assertEqual(profit._cached("t", lambda: "A"), "A")
        with tenant.use(self.B):
            self.assertEqual(profit._cached("t", lambda: "B"), "B")

    def test_login_token_one_time(self):
        tok = db.create_login_token(self.A)
        self.assertEqual(db.use_login_token(tok), self.A)
        self.assertIsNone(db.use_login_token(tok))  # ikkinchi marta ishlamaydi
        old = db.create_login_token(self.A, ttl=-1)
        self.assertIsNone(db.use_login_token(old))  # muddati o'tgan
        self.assertIsNone(db.use_login_token("tasodifiy-soxta"))

    def test_wipe_only_own(self):
        C = db.create_seller(chat_id="1003", name="C", demo=1)
        with tenant.use(C):
            db.set_cost(1, 1, 0, "C")
            ccid = db.add_competitor(1, "C raqobatchisi")
            db.add_snapshot(ccid, "2026-01-01", price=1)
        with tenant.use(self.B):
            db.set_cost(2, 2, 0, "B2")
        db.wipe_seller(C)
        self.assertIsNone(db.get_seller(C))
        with db.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM comp_snapshots WHERE competitor_id=?", (ccid,)).fetchone()[0], 0)
        with tenant.use(self.B):
            self.assertIn(2, db.get_costs())

    def test_competitors_isolated(self):
        with tenant.use(self.A):
            cid = db.add_competitor(2203614, "A raqobatchisi", manual=1)
            self.assertTrue(db.add_snapshot(cid, "2026-01-01", price=50000))
        with tenant.use(self.B):
            self.assertEqual(db.list_competitors(), [])
            self.assertIsNone(db.get_competitor(cid))
            self.assertEqual(db.snapshots(cid), [])
            self.assertFalse(db.add_snapshot(cid, "2026-01-02", price=1))  # begona raqobatchiga yozolmaydi
            self.assertFalse(db.delete_competitor(cid))
            self.assertFalse(db.link_competitor(cid, 1))
        with tenant.use(self.A):
            self.assertEqual([s["price"] for s in db.snapshots(cid)], [50000])

    def test_web_isolation(self):
        import web
        web.app.config["TESTING"] = True
        remote = {"REMOTE_ADDR": "203.0.113.5"}  # lokal emas — kirish talab qilinadi
        c = web.app.test_client()
        r = c.get("/", environ_base=remote)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/kirish", r.headers["Location"])

        with tenant.use(self.B):
            db.add_card("B kartochka", {}, {}, None, str(Path(_tmp) / "card_B_secret.jpg"))
        (Path(_tmp) / "card_B_secret.jpg").write_bytes(b"x")
        tok = db.create_login_token(self.A)
        r = c.get(f"/kirish/{tok}", environ_base=remote)
        self.assertEqual(r.status_code, 302)
        with c.session_transaction() as s:
            self.assertEqual(s["seller_id"], self.A)
        self.assertEqual(c.get("/files/card_B_secret.jpg", environ_base=remote).status_code, 404)
        self.assertEqual(c.get(f"/kirish/{tok}", environ_base=remote).status_code, 403)  # qayta ishlatib bo'lmaydi


if __name__ == "__main__":
    unittest.main(verbosity=2)
