"""
Telegram bot — ko'p mijozli (faqat `requests`, long polling). Ishga tushirish:  py bot.py

Har bir Telegram foydalanuvchisi — alohida sotuvchi. Har bir xabar o'sha sotuvchining
kontekstida (tenant.use) qayta ishlanadi, shuning uchun hech kim boshqaning ma'lumotini ko'rmaydi.

Ulanish:
  /start   — ro'yxatdan o'tish
  /ulash   — Uzum API kalitini ulash (xabar darhol o'chiriladi, kalit shifrlanadi)
  /demo    — namunaviy do'kon bilan sinab ko'rish
  /dokon   — bir nechta do'kon bo'lsa, tanlash
  /panel   — veb-panelga bir martalik kirish havolasi
  /uzish   — kalit va barcha ma'lumotni o'chirish
Ish:
  /qarorlar, /hisobot, /tovarlar, /narx, /tannarx SKU narx [qo'shimcha], rasm + izoh → kartochka
Har kuni ertalab (MORNING_REPORT_HOUR) qarorlar, kechqurun (DAILY_REPORT_HOUR) hisobot — har bir sotuvchiga.
"""
import html
import logging
import time
from datetime import datetime

import requests

import ai_card
import checks
import config
import db
import profit
import secure
import tenant
from uzum_client import UzumClient, UzumError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/"
FILE_API = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/"
http = requests.Session()

WELCOME = (
    "👋 <b>Sotuvchi AI</b> — Uzum do'koningiz uchun AI sotuv jamoasi.\n\n"
    "Har kuni ertalab sizga yozaman: pul qayerda ketyapti va bugun nima qilish kerak — "
    "zararli narxlar, aksiyalar, qaytishlar, omborda yotgan tovar, reklama va boshqalar.\n\n"
    "Boshlash uchun:\n"
    "🔑 /ulash — o'z do'koningizni ulang (2 daqiqa)\n"
    "🧪 /demo — avval namunaviy do'konda sinab ko'ring"
)

CONNECT = (
    "🔑 <b>Do'konni ulash</b>\n\n"
    "1. <b>seller.uzum.uz</b> ga kiring\n"
    "2. Sozlamalar → <b>API kalitlari</b> → yangi kalit yarating\n"
    "3. Kalitni nusxalab, <b>shu chatga yuboring</b>\n\n"
    "🔒 Kalitni olgan zahoti xabarni chatdan o'chiraman va kalitni shifrlangan holda saqlayman. "
    "Narxlar sizning tasdig'ingizsiz hech qachon o'zgarmaydi. /uzish — istalgan payt hammasini o'chirish."
)

HELP = (
    "🤖 <b>Sotuvchi AI</b>\n\n"
    "/qarorlar — bugungi qarorlar: pul qayerda ketyapti va nima qilish kerak\n"
    "/hisobot — sof foyda (bugun / hafta / oy / yil)\n"
    "/tovarlar — eng foydali va zararli tovarlar\n"
    "/narx — narx takliflari, tasdiqlash\n"
    "/tannarx SKU narx [qo'shimcha] — tannarx kiritish\n"
    "   masalan: <code>/tannarx 9001 72000 3000</code>\n"
    "/panel — veb-panelga kirish havolasi\n"
    "/dokon — do'konni almashtirish · /uzish — uzish\n\n"
    "📸 <b>Kartochka:</b> tovar rasmini yuboring, izohiga yozing:\n"
    "<code>Termos 1 litr\nrang: qora\no'lcham: 1 L\ntannarx: 40000\nyetkazish: 3000</code>"
)


# ---------- Telegram API ----------
def tg(method, **params):
    files = params.pop("files", None)
    try:
        r = http.post(API + method, data=params if files else None, json=None if files else params,
                      files=files, timeout=70)
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("Telegram %s: %s", method, e)
        return None
    if not data.get("ok"):
        log.warning("Telegram %s xato: %s", method, data.get("description"))
        return None
    return data.get("result")


def send(chat_id, text, kb=None):
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("sendMessage", **p)


def edit(chat_id, msg_id, text, kb=None):
    p = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if kb:
        p["reply_markup"] = {"inline_keyboard": kb}
    return tg("editMessageText", **p)


def esc(s):
    return html.escape(str(s or ""), quote=False)


# ---------- sotuvchi ----------
def seller_for(chat_id, user=None, create=False):
    s = db.get_seller_by_chat(chat_id)
    if not s and create:
        name = " ".join(x for x in ((user or {}).get("first_name"), (user or {}).get("last_name")) if x) or None
        db.create_seller(chat_id=chat_id, name=name)
        s = db.get_seller_by_chat(chat_id)
    if s:
        db.update_seller(s["id"], last_seen=int(time.time()))
    return s


def is_admin(chat_id):
    s = db.get_seller_by_chat(chat_id)
    return str(chat_id) == str(config.TELEGRAM_OWNER_ID) or (s and s["id"] == tenant.OWNER_ID)


# ---------- ulash ----------
def looks_like_token(text):
    t = (text or "").strip()
    return len(t) >= 24 and " " not in t and not t.startswith("/")


def handle_token(chat_id, msg):
    raw = (msg.get("text") or "").strip().replace("Bearer ", "")
    tg("deleteMessage", chat_id=chat_id, message_id=msg["message_id"])  # kalit chatda qolmasin
    send(chat_id, "⏳ Kalitni tekshiryapman...")
    try:
        shops = UzumClient(token=raw, demo=False).shops()
    except UzumError as e:
        return send(chat_id, f"❌ Kalit ishlamadi: {esc(e)}\n\nQayta urinib ko'ring: /ulash")
    if not shops:
        return send(chat_id, "❌ Bu kalit bilan birorta do'kon topilmadi. Boshqa kalit bilan urinib ko'ring: /ulash")
    sid = tenant.current_id()
    db.update_seller(sid, token_enc=secure.encrypt(raw), demo=0)
    db.set_setting("state", "")
    tenant.forget(sid)
    profit.clear_cache()
    log.info("Sotuvchi #%s ulandi (%s ta do'kon, kalit %s)", sid, len(shops), secure.mask(raw))
    if len(shops) == 1:
        return shop_chosen(chat_id, shops[0]["id"])
    send(chat_id, f"✅ Kalit ishladi. {len(shops)} ta do'kon topildi — qaysi biri bilan ishlaymiz?", shops_kb(shops))


def shops_kb(shops):
    return [[{"text": s.get("name") or str(s["id"]), "callback_data": f"shop:{s['id']}"}] for s in shops[:20]]


def shop_chosen(chat_id, shop_id, msg_id=None):
    db.set_setting("shop_id", shop_id)
    profit.clear_cache()
    try:
        name = profit.shop().get("name", "")
        text = f"✅ <b>{esc(name)}</b> ulandi! Tahlil qilyapman..."
        (edit(chat_id, msg_id, text) if msg_id else send(chat_id, text))
        send(chat_id, decisions_message())
        send(chat_id, "Boshqa buyruqlar: /hisobot /tovarlar /narx /panel\n"
                      "Har kuni ertalab qarorlarni o'zim yuboraman.")
    except UzumError as e:
        send(chat_id, f"❌ Do'kon ma'lumotini olib bo'lmadi: {esc(e)}\nBoshqa do'konni tanlang: /dokon")


# ---------- ish buyruqlari ----------
PERIOD_KB = [[{"text": "Bugun", "callback_data": "rep:today"}, {"text": "Hafta", "callback_data": "rep:week"},
              {"text": "Oy", "callback_data": "rep:month"}, {"text": "Yil", "callback_data": "rep:year"},
              {"text": "Hammasi", "callback_data": "rep:all"}]]


def cmd_tovarlar(chat_id):
    period = profit.default_period()
    r = profit.report(period)
    items = r["items"]
    if not items:
        return send(chat_id, f"{r['period_name']}: sotuv yo'q.")
    lines = [f"🏆 <b>Eng foydali ({r['period_name'].lower()})</b>"]
    for it in items[:5]:
        lines.append(f"• {esc(it['title'])} — <b>{profit.fmt(it['profit'])}</b> ({it['margin'] * 100:.0f}%)")
    bad = [it for it in items if it["profit"] < 0 or it["margin"] < 0.05]
    if bad:
        lines += ["", "⚠️ <b>Zararli yoki foydasi juda kam</b>"]
        for it in bad[-5:]:
            lines.append(f"• {esc(it['title'])} — {profit.fmt(it['profit'])} ({it['margin'] * 100:.0f}%)")
        lines.append("\nNarxni ko'rish: /narx")
    send(chat_id, "\n".join(lines))


def _proposal_text(p):
    return (f"💡 <b>{esc(p['title'])}</b>\nHozir: {profit.fmt(p['old_price'])} → Yangi: <b>{profit.fmt(p['new_price'])}</b> so'm\n"
            f"Chizilgan narx: {profit.fmt(p['full_price'])}\n<i>{esc(p['reason'])}</i>")


def cmd_narx(chat_id):
    profit.create_proposals()
    pending = profit.proposals("pending")
    if not pending:
        return send(chat_id, "✅ Hamma narxlar joyida, taklif yo'q.")
    note = "" if tenant.is_demo() else "\n⚠️ Tasdiqlansa, narx haqiqiy do'konda o'zgaradi."
    send(chat_id, f"Narx takliflari: {len(pending)} ta{note}")
    for p in pending[:10]:
        send(chat_id, _proposal_text(p), [[{"text": "✅ Tasdiqlash", "callback_data": f"ap:{p['id']}"},
                                           {"text": "❌ Rad etish", "callback_data": f"rj:{p['id']}"}]])


def cmd_tannarx(chat_id, args):
    parts = args.replace(",", ".").split()
    if len(parts) < 2:
        return send(chat_id, "Format: <code>/tannarx SKU narx [qo'shimcha]</code>\nMasalan: <code>/tannarx 9001 72000 3000</code>")
    try:
        sku, cost = int(parts[0]), float(parts[1])
        extra = float(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return send(chat_id, "Raqamlarni to'g'ri kiriting.")
    title = next((s["title"] for s in profit.skus() if s["sku_id"] == sku), None)
    if not title:
        return send(chat_id, f"SKU {sku} topilmadi. SKU raqamlari veb-paneldagi «Tovarlar» sahifasida (/panel).")
    db.set_cost(sku, cost, extra, title)
    profit.clear_cache()
    send(chat_id, f"✅ {esc(title)}: tannarx {profit.fmt(cost)} + {profit.fmt(extra)} so'm saqlandi.")


def cmd_panel(chat_id):
    tok = db.create_login_token(tenant.current_id())
    url = f"{config.PUBLIC_URL}/kirish/{tok}"
    send(chat_id, f"🖥 Veb-panelga kirish havolasi (15 daqiqa, bir martalik):\n{url}")


def cmd_stat(chat_id):
    sellers = db.list_sellers()
    con = sum(1 for s in sellers if s.get("token_enc"))
    demo = sum(1 for s in sellers if s.get("demo") and not s.get("token_enc"))
    week = sum(1 for s in sellers if (s.get("last_seen") or 0) > time.time() - 7 * 86400)
    send(chat_id, f"📊 Sotuvchilar: {len(sellers)}\n🔑 Ulangan: {con}\n🧪 Demo: {demo}\n🟢 7 kunda faol: {week}")


CAPTION_KEYS = {
    "rang": "color", "rangi": "color", "o'lcham": "size", "o'lchami": "size", "olcham": "size", "razmer": "size",
    "soni": "quantity", "to'plam": "quantity", "material": "material", "materiali": "material",
    "tannarx": "cost", "narx": "cost", "yetkazish": "extra_cost", "yetkazib kelish": "extra_cost",
    "qo'shimcha": "extra_cost", "nomi": "name", "nom": "name", "izoh": "notes",
}


def parse_caption(text):
    info = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            key = CAPTION_KEYS.get(k.strip().lower().replace("‘", "'").replace("`", "'"))
            if key:
                v = v.strip()
                if key in ("cost", "extra_cost"):
                    v = "".join(ch for ch in v if ch.isdigit())
                info[key] = v
                continue
        if "name" not in info:
            info["name"] = line
        else:
            info["notes"] = (info.get("notes", "") + " " + line).strip()
    return info


def handle_photo(chat_id, msg):
    info = parse_caption(msg.get("caption"))
    if not info.get("name"):
        info["name"] = "Tovar"
    send(chat_id, "⏳ AI kartochka tayyorlamoqda... (20-40 soniya)")
    file_id = msg["photo"][-1]["file_id"]
    f = tg("getFile", file_id=file_id)
    photo_path = None
    if f:
        r = http.get(FILE_API + f["file_path"], timeout=60)
        if r.ok:
            photo_path = ai_card.save_upload(r.content, ".jpg")
    card = ai_card.generate(info, photo_path)
    res = card["result"]
    with open(card["infographic_path"], "rb") as fh:
        tg("sendPhoto", chat_id=chat_id, caption=f"Infografika: {res.get('title_uz', '')[:900]}",
           files={"photo": ("card.jpg", fh, "image/jpeg")})
    price = res.get("price")
    price_txt = (f"\n\n💰 <b>Narx:</b> minimum {profit.fmt(price['min'])}, tavsiya <b>{profit.fmt(price['rec'])}</b>, "
                 f"chizilgan {profit.fmt(price['full'])} so'm") if price else ""
    src = "🤖 AI tayyorladi" if res.get("ai_used") else "📝 Shablon matn (AI kaliti yo'q)"
    send(chat_id, f"{src}{price_txt}\n\nQuyidagi xabarlarni bosib nusxalang va Uzum kabinetiga qo'ying 👇")
    for label, key, joiner in [("Sarlavha UZ", "title_uz", None), ("Sarlavha RU", "title_ru", None),
                               ("Tavsif UZ", "description_uz", None), ("Tavsif RU", "description_ru", None),
                               ("Xususiyatlar UZ", "features_uz", "\n"), ("Xususiyatlar RU", "features_ru", "\n"),
                               ("Kalit so'zlar UZ", "keywords_uz", ", "), ("Kalit so'zlar RU", "keywords_ru", ", ")]:
        val = res.get(key)
        if joiner and isinstance(val, list):
            val = joiner.join(val)
        if val:
            send(chat_id, f"<b>{label}:</b>\n<code>{esc(val)[:3800]}</code>")


# ---------- yo'naltirish ----------
def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    s = seller_for(chat_id)
    if not s:
        return
    with tenant.use(s["id"]):
        if data.startswith("shop:"):
            shops = {str(x["id"]) for x in profit.client().shops()}
            if data[5:] in shops:  # faqat o'z kaliti ko'rsatadigan do'kon
                shop_chosen(chat_id, data[5:], msg_id)
        elif data == "uzish:ha":
            db.wipe_seller(s["id"])
            tenant.forget(s["id"])
            profit.clear_cache()
            edit(chat_id, msg_id, "🗑 Kalit va barcha ma'lumotlaringiz o'chirildi. Qaytmoqchi bo'lsangiz: /start")
        elif data == "uzish:yoq":
            edit(chat_id, msg_id, "Bekor qilindi.")
        elif not tenant.connected():
            send(chat_id, CONNECT)
        elif data.startswith("rep:"):
            edit(chat_id, msg_id, profit.report_text(data[4:]), PERIOD_KB)
        elif data.startswith("ap:"):
            pid = int(data[3:])
            p = db.get_proposal(pid)  # faqat shu sotuvchining taklifi
            if not p:
                return
            if tenant.is_demo():
                ok, m = profit.approve_proposal(pid)
                edit(chat_id, msg_id, ("✅ " if ok else "❌ ") + esc(m))
            else:  # haqiqiy do'kon — ikkinchi marta so'raymiz
                edit(chat_id, msg_id, _proposal_text(p) + "\n\n⚠️ <b>Narx haqiqiy do'konda darhol o'zgaradi. Ishonchingiz komilmi?</b>",
                     [[{"text": "✅ Ha, o'zgartir", "callback_data": f"apc:{pid}"},
                       {"text": "❌ Yo'q", "callback_data": f"rj:{pid}"}]])
        elif data.startswith("apc:"):
            ok, m = profit.approve_proposal(int(data[4:]))
            edit(chat_id, msg_id, ("✅ " if ok else "❌ ") + esc(m))
        elif data.startswith("rj:"):
            ok, m = profit.reject_proposal(int(data[3:]))
            edit(chat_id, msg_id, "❌ Rad etildi" if ok else esc(m))


NEEDS_SHOP = {"/qarorlar", "/hisobot", "/tovarlar", "/narx", "/tannarx"}


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    if msg.get("chat", {}).get("type") != "private":
        return  # guruhlarda ishlamaymiz — kalit va hisobotlar faqat shaxsiy chatda
    text = (msg.get("text") or "").strip()
    cmd, _, args = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    s = seller_for(chat_id, msg.get("from"), create=(cmd == "/start"))
    if not s:
        return send(chat_id, WELCOME)
    with tenant.use(s["id"]):
        if cmd == "/start":
            return send(chat_id, HELP if tenant.connected() and not tenant.is_demo() else WELCOME)
        if cmd == "/ulash":
            db.set_setting("state", "token")
            return send(chat_id, CONNECT)
        if looks_like_token(text) and (db.get_setting("state") == "token" or not s.get("token_enc")):
            return handle_token(chat_id, msg)
        if cmd == "/demo":
            if s.get("token_enc"):
                return send(chat_id, "Sizda haqiqiy do'kon ulangan. Demo uchun avval /uzish qiling.")
            db.update_seller(s["id"], demo=1)
            tenant.forget(s["id"])
            profit.clear_cache()
            send(chat_id, "🧪 Namunaviy do'kon yoqildi.")
            return send(chat_id, decisions_message())
        if cmd == "/uzish":
            return send(chat_id, "⚠️ Uzum kaliti, tannarxlar, takliflar va kartochkalar butunlay o'chiriladi. Davom etamizmi?",
                        [[{"text": "🗑 Ha, o'chirish", "callback_data": "uzish:ha"},
                          {"text": "Yo'q", "callback_data": "uzish:yoq"}]])
        if cmd == "/statistika" and is_admin(chat_id):
            return cmd_stat(chat_id)
        if not tenant.connected():
            return send(chat_id, CONNECT if cmd in NEEDS_SHOP or msg.get("photo") else WELCOME)
        if cmd == "/panel":
            return cmd_panel(chat_id)
        if cmd == "/dokon":
            return send(chat_id, "Qaysi do'kon bilan ishlaymiz?", shops_kb(profit.client().shops()))
        if msg.get("photo"):
            return handle_photo(chat_id, msg)
        if cmd == "/qarorlar":
            send(chat_id, decisions_message())
        elif cmd == "/hisobot":
            send(chat_id, profit.report_text("today"), PERIOD_KB)
        elif cmd == "/tovarlar":
            cmd_tovarlar(chat_id)
        elif cmd == "/narx":
            cmd_narx(chat_id)
        elif cmd == "/tannarx":
            cmd_tannarx(chat_id, args)
        else:
            send(chat_id, HELP)


# ---------- kunlik xabarlar (har bir sotuvchiga) ----------
def decisions_message():
    return checks.decisions_text(profit.shop().get("name", ""), limit=3, fmt=profit.fmt)


def daily_check():
    now = datetime.now(profit.TZ)
    today = now.strftime("%Y-%m-%d")
    for s in db.list_sellers():
        if not s.get("tg_chat_id"):
            continue
        with tenant.use(s["id"]):
            if not tenant.connected():
                continue
            try:
                if now.hour >= config.MORNING_REPORT_HOUR and db.get_setting("last_morning") != today:
                    db.set_setting("last_morning", today)
                    send(s["tg_chat_id"], decisions_message())
                if now.hour >= config.DAILY_REPORT_HOUR and db.get_setting("last_daily") != today:
                    db.set_setting("last_daily", today)
                    send(s["tg_chat_id"], "🌙 <b>Kunlik hisobot</b>\n\n" + profit.report_text("today"), PERIOD_KB)
            except Exception as e:  # bitta sotuvchidagi xato boshqalarni to'xtatmasin
                log.exception("Sotuvchi #%s kunlik xabar xatosi: %s", s["id"], e)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN .env faylida yo'q. README_UZ.md dagi ko'rsatmaga qarang.")
        return
    me = tg("getMe")
    if not me:
        print("Bot tokeni noto'g'ri yoki internet yo'q.")
        return
    tg("setMyCommands", commands=[
        {"command": "qarorlar", "description": "Bugungi qarorlar: pul qayerda ketyapti"},
        {"command": "hisobot", "description": "Sof foyda hisoboti"},
        {"command": "tovarlar", "description": "Foydali va zararli tovarlar"},
        {"command": "narx", "description": "Narx takliflari"},
        {"command": "tannarx", "description": "Tannarx kiritish: SKU narx [qo'shimcha]"},
        {"command": "panel", "description": "Veb-panelga kirish havolasi"},
        {"command": "ulash", "description": "Uzum do'konini ulash"},
        {"command": "demo", "description": "Namunaviy do'konda sinab ko'rish"},
        {"command": "dokon", "description": "Do'konni almashtirish"},
        {"command": "uzish", "description": "Kalit va ma'lumotni o'chirish"},
    ])
    print(f"\n  Bot ishga tushdi: @{me['username']} (ko'p mijozli rejim, sotuvchilar: {len(db.list_sellers())})")
    print("  To'xtatish: Ctrl+C\n")
    offset = None
    last_daily = 0.0
    while True:
        try:
            if time.time() - last_daily > 60:
                daily_check()
                last_daily = time.time()
            params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
            if offset:
                params["offset"] = offset
            updates = tg("getUpdates", **params) or []
            for u in updates:
                offset = u["update_id"] + 1
                try:
                    if "message" in u:
                        handle_message(u["message"])
                    elif "callback_query" in u:
                        handle_callback(u["callback_query"])
                except Exception as e:
                    log.exception("Xabarni qayta ishlashda xato: %s", e)
                    chat = (u.get("message") or u.get("callback_query", {}).get("message") or {}).get("chat", {})
                    if chat.get("id"):
                        send(chat["id"], "❌ Xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.")
        except KeyboardInterrupt:
            print("To'xtatildi.")
            break
        except Exception as e:
            log.exception("Asosiy siklda xato: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
