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
Tashqaridan kirilsa, `.env` da albatta `WEB_PASSWORD=` qo'ying.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `config.py` | sozlamalar (`.env` dan) |
| `uzum_client.py` | Uzum Open API bilan ishlash |
| `demo_data.py` | namunaviy ma'lumotlar |
| `db.py` | mahalliy baza (`data/sotuvchi.db`) |
| `profit.py` | foyda hisobi va narx maslahati |
| `ai_card.py`, `infographic.py` | AI kartochka va infografika |
| `web.py` | veb-panel |
| `bot.py` | Telegram bot |
