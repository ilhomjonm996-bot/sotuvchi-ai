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

## Xavfsizlik
- Kalitlar faqat `.env` da, repoga kirmaydi.
- Narx hech qachon egasining tasdig'isiz o'zgarmaydi; haqiqiy do'konda ikki marta so'raladi.
