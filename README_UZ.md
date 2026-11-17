# Sotuvchi AI — Uzum sotuvchilari uchun AI yordamchi

Uchta asosiy qism:
1. **Sof foyda hisoboti** — bugun / hafta / oy / yil. Komissiya, logistika, tannarx, soliq va Uzum xarajatlari (saqlash, reklama, jarimalar) ayrilgandagi haqiqiy foyda. Har bir tovar bo'yicha foyda/zarar.
2. **Aqlli narx maslahati** — zararsiz minimal narx va tavsiya narx. Siz tasdiqlasangiz, narx Uzum'da o'zgaradi.
3. **AI kartochka** — rasm + qisqa ma'lumot → o'zbekcha va ruscha matn, kalit so'zlar, infografika (1080×1440), tavsiya narx.

Ikki xil ishlatish mumkin: **veb-panel** (brauzerda) va **Telegram bot**.

---

## 1. Ishga tushirish (demo rejim)

Kerak: Python 3.10 yoki yangisi (python.org dan, o'rnatishda **"Add python.exe to PATH"** belgisini qo'ying).

- **Veb-panel:** `start_web.bat` ni ikki marta bosing → brauzerda http://127.0.0.1:5000 ochiladi.
- **Telegram bot:** `start_bot.bat` (avval 3-bo'limdagi tokenni qo'ying).

Uzum tokeni qo'yilmaguncha dastur **demo ma'lumotlar** (8 ta namunaviy tovar) bilan ishlaydi.

## 2. Sozlamalar fayli `.env`

`.env.example` faylidan nusxa oling va nomini `.env` qiling (Bloknot bilan oching). Barcha maxfiy kalitlar faqat shu faylda turadi — uni hech kimga yubormang.

## 3. Telegram bot ulash

1. Telegram'da **@BotFather** ga yozing → `/newbot` → bot nomi va `..._bot` bilan tugaydigan username bering.
2. BotFather bergan tokenni `.env` dagi `TELEGRAM_BOT_TOKEN=` dan keyin qo'ying.
3. `start_bot.bat` ni ishga tushiring, botingizga `/start` yozing — siz ega bo'lasiz, bot boshqalarga javob bermaydi.

## 4. Uzum do'konini ulash

1. **seller.uzum.uz** → Sozlamalar → **API kalitlari** → yangi kalit yarating.
2. Kalitni `.env` dagi `UZUM_API_TOKEN=` dan keyin qo'ying ("Bearer" so'zisiz).
3. Panel va botni qayta ishga tushiring. Sariq "Demo rejim" yozuvi yo'qolsa — ulangan.
4. **Tovarlar** sahifasida har bir tovarning tannarxini kiriting.

> ⚠️ Narxni **Tasdiqlash** tugmasi haqiqiy do'konda narxni darhol o'zgartiradi.

## 5. AI ulash (ixtiyoriy)

console.anthropic.com → API Keys → kalit yarating → `.env` dagi `ANTHROPIC_API_KEY=` ga qo'ying.
Kalit bo'lmasa, kartochka shablon matn bilan tayyorlanadi.

## 6. Serverga (Linux VPS) ko'chirish

```bash
pip install -r requirements.txt
WEB_HOST=0.0.0.0 python3 web.py      # panel
python3 bot.py                       # bot
```
Tashqaridan kirilsa, `.env` da `PUBLIC_URL=` (saytingiz manzili) ni yozing — sotuvchilar panelga botdagi `/panel` havolasi orqali kiradi.
`data/secret.key` faylini (yoki `SECRET_ENC_KEY`) albatta zaxiralang: usiz sotuvchilarning saqlangan kalitlarini ochib bo'lmaydi.

## 7. Boshqa sotuvchilarni ulash (ko'p mijozli rejim)

Siz (birinchi foydalanuvchi) — ega. Boshqa sotuvchilar shu botning o'zidan foydalanadi:

| Buyruq | Nima qiladi |
|---|---|
| `/start` | ro'yxatdan o'tish |
| `/ulash` | Uzum API kalitini yuborish (xabar o'chiriladi, kalit shifrlanadi) |
| `/demo` | namunaviy do'kon bilan sinab ko'rish |
| `/panel` | veb-panelga bir martalik kirish havolasi (15 daqiqa) |
| `/raqobat` | raqobatchilar; `/raqobat havola` — qo'shish (yoki Uzum havolasini shunchaki yuboring) |
| `/bozor so'z` | bozor tahlili, masalan `/bozor termos` |
| `/dokon` | do'konni almashtirish |
| `/uzish` | o'z ma'lumotlarini butunlay o'chirish |
| `/statistika` | (faqat ega) nechta sotuvchi ulangan |

Har bir sotuvchi faqat o'z ma'lumotini ko'radi. Tekshirish: `py -m unittest discover -s tests -v`.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `config.py` | sozlamalar (`.env` dan) |
| `uzum_client.py` | Uzum Open API bilan ishlash |
| `demo_data.py` | namunaviy ma'lumotlar |
| `db.py` | mahalliy baza (`data/sotuvchi.db`), har bir sotuvchi alohida |
| `tenant.py` | joriy sotuvchi va uning Uzum klienti |
| `secure.py` | kalitlarni shifrlash |
| `market.py` | raqobatchilar kuzatuvi va bozor tahlili |
| `profit.py` | foyda hisobi va narx maslahati |
| `ai_card.py`, `infographic.py` | AI kartochka va infografika |
| `web.py` | veb-panel |
| `bot.py` | Telegram bot |
