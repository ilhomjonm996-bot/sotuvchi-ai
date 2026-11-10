"""
Telegram bot (faqat `requests`, long polling). Ishga tushirish:  py bot.py

Buyruqlar:
  /start                   — egani ro'yxatdan o'tkazish
  /hisobot                 — sof foyda hisoboti (bugun / hafta / oy / yil)
  /tovarlar                — eng foydali va zararli tovarlar
  /narx                    — narx takliflari (Tasdiqlash / Rad etish)
  /tannarx SKU narx [qo'shimcha] — tannarx kiritish
  Rasm + izoh              — AI kartochka
Har kuni DAILY_REPORT_HOUR da (Toshkent vaqti) kunlik hisobot yuboriladi.
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
from uzum_client import client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/"
FILE_API = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/"
http = requests.Session()

HELP = (
    "🤖 <b>Sotuvchi AI</b> — Uzum do'koningiz uchun AI yordamchi\n\n"
    "/qarorlar — bugungi qarorlar: pul qayerda ketyapti va nima qilish kerak\n"
    "/hisobot — sof foyda (bugun / hafta / oy / yil)\n"
    "/tovarlar — eng foydali va zararli tovarlar\n"
    "/narx — narx takliflari, tasdiqlash\n"
    "/tannarx SKU narx [qo'shimcha] — tannarx kiritish\n"
    "   masalan: <code>/tannarx 9001 72000 3000</code>\n\n"
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


# ---------- ega ----------
def owner_id():
    return config.TELEGRAM_OWNER_ID or db.get_setting("tg_owner")


def is_owner(chat_id):
    return str(chat_id) == str(owner_id())


# ---------- buyruqlar ----------
PERIOD_KB = [[{"text": "Bugun", "callback_data": "rep:today"}, {"text": "Hafta", "callback_data": "rep:week"},
              {"text": "Oy", "callback_data": "rep:month"}, {"text": "Yil", "callback_data": "rep:year"},
              {"text": "Hammasi", "callback_data": "rep:all"}]]


def cmd_start(chat_id, user):
    if not owner_id():
        db.set_setting("tg_owner", chat_id)
        send(chat_id, f"✅ Siz do'kon egasi sifatida ro'yxatdan o'tdingiz (ID: <code>{chat_id}</code>).\n"
                      f"Endi bot faqat sizga javob beradi.\n\n" + HELP)
    elif is_owner(chat_id):
        send(chat_id, HELP)
    else:
        send(chat_id, "Bu bot shaxsiy. Kechirasiz.")


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
    n = profit.create_proposals()
    pending = profit.proposals("pending")
    if not pending:
        return send(chat_id, "✅ Hamma narxlar joyida, taklif yo'q.")
    note = "" if client.demo else "\n⚠️ Tasdiqlansa, narx haqiqiy do'konda o'zgaradi."
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
        return send(chat_id, f"SKU {sku} topilmadi. SKU raqamlari veb-paneldagi «Tovarlar» sahifasida.")
    db.set_cost(sku, cost, extra, title)
    profit.clear_cache()
    send(chat_id, f"✅ {esc(title)}: tannarx {profit.fmt(cost)} + {profit.fmt(extra)} so'm saqlandi.")


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


def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if not is_owner(chat_id):
        return
    if data.startswith("rep:"):
        edit(chat_id, msg_id, profit.report_text(data[4:]), PERIOD_KB)
    elif data.startswith("ap:"):
        pid = int(data[3:])
        p = db.get_proposal(pid)
        if not p:
            return
        if client.demo:
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


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        return cmd_start(chat_id, msg.get("from", {}))
    if not is_owner(chat_id):
        return send(chat_id, "Bu bot shaxsiy. Kechirasiz.")
    if msg.get("photo"):
        return handle_photo(chat_id, msg)
    cmd, _, args = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
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


# ---------- kunlik hisobot ----------
def decisions_message():
    return checks.decisions_text(profit.shop().get("name", ""), limit=3, fmt=profit.fmt)


def daily_check():
    oid = owner_id()
    if not oid:
        return
    now = datetime.now(profit.TZ)
    today = now.strftime("%Y-%m-%d")
    if now.hour >= config.MORNING_REPORT_HOUR and db.get_setting("last_morning") != today:
        db.set_setting("last_morning", today)
        try:
            send(oid, decisions_message())
        except Exception as e:
            log.exception("Ertalabki qarorlar xatosi: %s", e)
    if now.hour >= config.DAILY_REPORT_HOUR and db.get_setting("last_daily") != today:
        db.set_setting("last_daily", today)
        try:
            send(oid, "🌙 <b>Kunlik hisobot</b>\n\n" + profit.report_text("today"), PERIOD_KB)
        except Exception as e:
            log.exception("Kunlik hisobot xatosi: %s", e)


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
    ])
    print(f"\n  Bot ishga tushdi: @{me['username']}  ({'DEMO rejim' if client.demo else 'haqiqiy do`kon'})")
    print("  Telegram'da botga /start yozing. To'xtatish: Ctrl+C\n")
    offset = None
    while True:
        try:
            daily_check()
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
                        send(chat["id"], f"❌ Xatolik: {esc(e)}")
        except KeyboardInterrupt:
            print("To'xtatildi.")
            break
        except Exception as e:
            log.exception("Asosiy siklda xato: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
