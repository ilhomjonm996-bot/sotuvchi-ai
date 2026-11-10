"""
AI kartochka: rasm + qisqa ma'lumot → o'zbekcha va ruscha matn, kalit so'zlar,
infografika va tavsiya narx.

Claude API'ga to'g'ridan-to'g'ri `requests` bilan murojaat qilinadi.
ANTHROPIC_API_KEY bo'lmasa (yoki xato bo'lsa) shablon asosidagi zaxira matn ishlatiladi.
"""
import base64
import io
import json
import logging
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageOps

import config
import db
import infographic
import profit

log = logging.getLogger("ai_card")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"

PROMPT = """Sen Uzum Market uchun tajribali kartochka mutaxassisisan.
Quyidagi tovar uchun sotuvchi kartochkasini tayyorla. Rasm bo'lsa, undan tovar turini, rangini va xususiyatlarini aniqla.

Sotuvchi ma'lumoti:
{info}

Qoidalar:
- Sarlavha: Uzum uslubida, aniq, 60-110 belgi: tovar turi + asosiy xususiyat + rang/o'lcham. Spam so'zlarsiz.
- Tavsif: 500-900 belgi, xaridorga foyda tilida, qisqa paragraflar. To'qima xususiyat qo'shma — faqat rasm va ma'lumotdan bilinadiganini yoz.
- Xususiyatlar: 5-8 ta "Nomi: qiymati" ko'rinishida.
- Kalit so'zlar: 10-15 ta, xaridor qidiradigan so'zlar (lotin o'zbekcha uchun, kirill ruscha uchun).
- Infografika uchun 3-4 ta juda qisqa afzallik (har biri 2-5 so'z, o'zbekcha).
- O'zbekcha matn lotin alifbosida bo'lsin.

FAQAT quyidagi tuzilishdagi JSON qaytar, boshqa hech narsa yozma:
{{
  "title_uz": "...", "title_ru": "...",
  "description_uz": "...", "description_ru": "...",
  "features_uz": ["Material: ...", "..."], "features_ru": ["Материал: ...", "..."],
  "keywords_uz": ["..."], "keywords_ru": ["..."],
  "infographic_bullets": ["...", "...", "..."],
  "category_hint": "Uzum'dagi taxminiy kategoriya"
}}"""


def _image_block(photo_path):
    """Rasmni kichraytirib base64 ga o'giradi (API limiti uchun)."""
    im = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
    im.thumbnail((1568, 1568))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.b64encode(buf.getvalue()).decode()}}


def _info_text(info):
    labels = [("name", "Nomi"), ("color", "Rangi"), ("size", "O'lchami"), ("quantity", "Soni / to'plam"),
              ("material", "Materiali"), ("notes", "Qo'shimcha")]
    lines = [f"- {lbl}: {info[k]}" for k, lbl in labels if info.get(k)]
    return "\n".join(lines) or "- (faqat rasm berilgan)"


def _parse_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI javobida JSON topilmadi")
    return json.loads(text[start:end + 1])


def _call_claude(info, photo_path):
    content = []
    if photo_path:
        content.append(_image_block(photo_path))
    content.append({"type": "text", "text": PROMPT.format(info=_info_text(info))})
    body = {
        "model": config.AI_MODEL,
        "max_tokens": 8000,
        "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": content}],
    }
    headers = {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": API_VERSION,
               "content-type": "application/json"}
    # Xavfsizlik filtri noto'g'ri rad etsa, server boshqa modelga avtomatik o'tadi
    fb_headers = dict(headers, **{"anthropic-beta": "server-side-fallback-2026-07-01"})
    r = requests.post(API_URL, json=dict(body, fallbacks="default"), headers=fb_headers, timeout=180)
    if r.status_code == 400 and "fallback" in r.text.lower():
        r = requests.post(API_URL, json=body, headers=headers, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"AI xatosi {r.status_code}: {r.text[:300]}")
    data = r.json()
    if data.get("stop_reason") == "refusal":
        raise RuntimeError("AI bu so'rovni rad etdi")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return _parse_json(text)


def _fallback(info):
    """AI kaliti bo'lmaganda shablon matn (demo uchun)."""
    name = (info.get("name") or "Tovar").strip()
    color = (info.get("color") or "").strip()
    size = (info.get("size") or "").strip()
    qty = (info.get("quantity") or "").strip()
    extras = ", ".join(x for x in (color, size, qty) if x)
    title_uz = f"{name}" + (f", {extras}" if extras else "")
    feats_uz = [f"Nomi: {name}"] + ([f"Rangi: {color}"] if color else []) + \
               ([f"O'lchami: {size}"] if size else []) + ([f"To'plamda: {qty}"] if qty else []) + \
               ["Holati: yangi", "Yetkazib berish: Uzum orqali, 1-3 kun"]
    feats_ru = [f"Название: {name}"] + ([f"Цвет: {color}"] if color else []) + \
               ([f"Размер: {size}"] if size else []) + ([f"Комплект: {qty}"] if qty else []) + \
               ["Состояние: новый", "Доставка: через Uzum, 1-3 дня"]
    return {
        "title_uz": title_uz,
        "title_ru": title_uz,
        "description_uz": (f"{name} — kundalik foydalanish uchun qulay va sifatli tovar. "
                           f"{'Rangi: ' + color + '. ' if color else ''}{"O'lchami: " + size + '. ' if size else ''}"
                           "Mahsulot puxta qadoqlangan holda yetkaziladi. Buyurtma bering — Uzum orqali tez yetkazib beramiz!"),
        "description_ru": (f"{name} — удобный и качественный товар для повседневного использования. "
                           "Товар доставляется в надёжной упаковке. Заказывайте — быстрая доставка через Uzum!"),
        "features_uz": feats_uz,
        "features_ru": feats_ru,
        "keywords_uz": [w for w in [name.lower(), color.lower(), "sifatli", "arzon", "sovg'a", "uzum"] if w],
        "keywords_ru": ["качественный", "недорого", "подарок", "доставка"],
        "infographic_bullets": [x for x in ["Yuqori sifat", f"Rang: {color}" if color else "", f"O'lcham: {size}" if size else "",
                                            "Tez yetkazib berish"] if x][:4],
        "category_hint": "",
    }


def generate(info: dict, photo_path: str = None):
    """Kartochka yaratadi va bazaga saqlaydi. Natija: kartochka dict."""
    ai_used, ai_error = False, None
    if config.ANTHROPIC_API_KEY:
        try:
            result = _call_claude(info, photo_path)
            ai_used = True
        except Exception as e:  # tarmoq, JSON, API xatolari — demo to'xtamasin
            log.warning("AI xatosi: %s", e)
            ai_error = str(e)
            result = _fallback(info)
    else:
        ai_error = "ANTHROPIC_API_KEY kiritilmagan — shablon matn ishlatildi"
        result = _fallback(info)

    # tavsiya narx
    try:
        cost = float(info.get("cost") or 0)
        extra = float(info.get("extra_cost") or 0)
    except ValueError:
        cost, extra = 0, 0
    result["price"] = profit.price_for_cost(cost, extra) if cost > 0 else None
    result["ai_used"] = ai_used
    result["ai_error"] = ai_error

    out = config.OUTPUT_DIR / f"card_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    infographic.make(photo_path, result.get("title_uz") or info.get("name", ""),
                     result.get("infographic_bullets") or [], out)
    cid = db.add_card(info.get("name") or result.get("title_uz", ""), info, result,
                      str(photo_path) if photo_path else None, str(out))
    return db.get_card(cid)


def save_upload(data: bytes, ext: str = ".jpg") -> str:
    ext = ext if ext.lower() in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
    path = config.UPLOAD_DIR / f"{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    Path(path).write_bytes(data)
    return str(path)
