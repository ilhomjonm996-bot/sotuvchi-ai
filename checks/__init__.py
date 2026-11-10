"""
Tekshiruvchilar (agentlar) — har biri do'kon ma'lumotini o'qib, "topilma" qaytaradi.

Topilma formati (dict):
    key     — noyob kalit (masalan "saqlash:6725297")
    level   — "red" (pul hozir ketyapti) | "orange" (e'tibor kerak) | "green" (imkoniyat)
    title   — qisqa sarlavha
    text    — tushuntirish (raqamlar bilan)
    action  — nima qilish kerak
    money   — oyiga taxminiy pul ta'siri (so'm), saralash uchun
    source  — qaysi tekshiruvchi

Yangi tekshiruvchi qo'shish: checks/ ichida run() funksiyali fayl yozing va CHECKS ga qo'shing.
"""
import logging
from html import escape as _esc

from . import qaytish, saqlash, tugagan

log = logging.getLogger("checks")

CHECKS = [saqlash.run, qaytish.run, tugagan.run]
LEVEL_ORDER = {"red": 0, "orange": 1, "green": 2}
ICONS = {"red": "🔴", "orange": "🟠", "green": "🟢"}


def escape(s):
    return _esc(str(s or ""), quote=False)


def run_all():
    """Barcha tekshiruvlar natijasi: avval qizil, keyin pul ta'siri katta bo'lganlar."""
    out = []
    for check in CHECKS:
        try:
            out.extend(check())
        except Exception as e:  # bitta tekshiruv xatosi boshqalarini to'xtatmasin
            log.exception("Tekshiruv xatosi (%s): %s", getattr(check, "__module__", check), e)
    # pul hozir ketayotgan va darhol to'xtatsa bo'ladigan topilmalar (urgent) birinchi
    out.sort(key=lambda f: (LEVEL_ORDER.get(f["level"], 9), not f.get("urgent"), -(f.get("money") or 0)))
    for f in out:
        f["icon"] = ICONS.get(f["level"], "•")
    return out


def decisions_text(shop_name="", limit=3, fmt=lambda x: f"{x:,.0f}"):
    """Telegram uchun 'bugungi qarorlar' xabari (HTML)."""
    found = run_all()
    if not found:
        return f"☀️ <b>Bugungi qarorlar</b> — {escape(shop_name)}\n\n✅ Muhim muammo topilmadi."
    lines = [f"☀️ <b>Bugungi qarorlar</b> — {escape(shop_name)}", ""]
    for i, f in enumerate(found[:limit], 1):
        money = f" · ~{fmt(f['money'])} so'm/oy" if f.get("money") else ""
        lines += [f"{i}) {f['icon']} <b>{escape(f['title'])}</b>{money}",
                  f"   {escape(f['text'])}",
                  f"   👉 {escape(f['action'])}", ""]
    if len(found) > limit:
        lines.append(f"Yana {len(found) - limit} ta topilma — veb-paneldagi «Qarorlar» sahifasida.")
    return "\n".join(lines)
