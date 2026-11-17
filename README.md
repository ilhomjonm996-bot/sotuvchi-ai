# Sotuvchi AI

**Uzum Market sotuvchilari uchun AI sotuv jamoasi** — do'konni ulaysiz, AI agentlar ishlaydi, egasi faqat tasdiqlaydi.

🔗 **Ochiq demo:** https://ilhomjon.pythonanywhere.com (namunaviy do'kon)

## Muammo
Marketpleys sotuvchisi tushumni ko'radi, lekin sof foydani bilmaydi: komissiya, logistika, ombor, reklama va jarimalar kabinetda turli joyda, tovar tannarxi esa umuman yo'q. Natijada "sotuv bor, pul yo'q".

## Hozir ishlaydigan agentlar
| Agent | Nima qiladi |
|---|---|
| **Moliyachi** | Kunlik/haftalik/oylik/yillik sof foyda: sotuv − komissiya − logistika − tannarx − soliq − Uzum xarajatlari. Har bir tovar bo'yicha foyda/zarar. Har kuni Telegram'ga hisobot. |
| **Narx menejeri** | Har bir SKU ning o'z sotuv tarixidagi komissiya va logistikadan zararsiz minimal va tavsiya narx. Egasi tasdiqlasa, narx Uzum Seller API orqali o'zgaradi. |
| **Kartochka dizayneri** | Rasm + qisqa ma'lumot → o'zbekcha va ruscha sarlavha, tavsif, xususiyatlar, kalit so'zlar, 1080×1440 infografika va tavsiya narx (Claude API). |

**Keyingi agentlar:** marketolog (sotuvi tushgan tovar uchun aksiya/reklama/chegirma tavsiyasi), strateg (aylanma maqsadi va reja), sharhlarga javob, bozor tahlilchisi (raqobatchilar, nishalar).

## Texnologiya
- Python, Flask (veb-panel), Telegram Bot API (long polling, faqat `requests`), SQLite, Pillow
- Uzum Seller Open API (rasmiy), Claude API
- Haqiqiy Uzum do'konlarida sinalgan; token bo'lmasa demo ma'lumot bilan ishlaydi

## Ishga tushirish
```bash
pip install -r requirements.txt
cp .env.example .env      # kalitlarni to'ldiring (bo'sh bo'lsa — demo rejim)
python web.py             # http://127.0.0.1:5000
python bot.py             # Telegram bot
```
Windows uchun: `start_web.bat`, `start_bot.bat`. Batafsil: [README_UZ.md](README_UZ.md).

## Raqobat va bozor tahlili
- **Raqobatchi kuzatuvchisi** — Uzum'dagi raqobatchi tovar havolasini qo'shasiz, o'z tovaringizga bog'laysiz: narx farqi, 7 kunlik narx o'zgarishi, qoldig'i va sotuvi. Raqobatchi arzonlashsa, narxni tushirsa yoki tovari tugasa — «Qarorlar»ga signal (zararsiz minimum hisobga olinadi).
- **Bozor tahlili** — kalit so'z bo'yicha: narx oralig'i, talab, raqobat (top-3 ulushi), eng ko'p sotiladigan narx segmenti, nisha bahosi 1–10 va sizning narxingiz bozorga nisbatan.
- Ma'lumot manbasi `market.py` da: demo rejimda namunaviy bozor, haqiqiy do'konda raqobatchi narxi qo'lda kiritiladi. Uzum'da raqobatchilar uchun rasmiy API yo'q — ruxsat etilgan manba ulansa, faqat `_live_search` va `_live_product` yoziladi.

## Ko'p mijozli rejim
Bitta bot va bitta veb-panel ko'p sotuvchiga xizmat qiladi, har birining ma'lumoti alohida:
1. Sotuvchi botga `/start` yozadi → `/ulash` → Uzum API kalitini yuboradi (xabar darhol o'chiriladi, kalit shifrlanib saqlanadi) → do'konini tanlaydi.
2. `/panel` — veb-panelga 15 daqiqalik bir martalik kirish havolasi.
3. `/demo` — namunaviy do'kon bilan sinab ko'rish, `/uzish` — hamma ma'lumotini o'chirish.

Har bir so'rov joriy sotuvchi bilan bog'lanadi (`tenant.py`), bazadagi har bir jadval `seller_id` bo'yicha ajratilgan (`db.py`), Uzum kalitlari Fernet bilan shifrlangan (`secure.py`).

Ajratish testlari:
```bash
python -m unittest discover -s tests -v
```

## Xavfsizlik
- Server kalitlari faqat `.env` da, repoga kirmaydi; sotuvchilarning Uzum kalitlari bazada shifrlangan.
- Bir sotuvchi boshqasining tannarxi, takliflari, kartochkalari va fayllarini ko'ra olmaydi (testlar bilan tekshirilgan).
- Narx hech qachon egasining tasdig'isiz o'zgarmaydi; haqiqiy do'konda ikki marta so'raladi.
