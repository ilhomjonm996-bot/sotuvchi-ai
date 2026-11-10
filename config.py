"""
Sozlamalar.

Barcha maxfiy kalitlar (Uzum tokeni, AI kaliti, Telegram bot tokeni)
loyiha papkasidagi `.env` faylida saqlanadi. Bu fayl hech kimga yuborilmaydi.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "cards"
for _d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_env_file(path: Path) -> None:
    """`.env` faylidan KALIT=QIYMAT qatorlarini o'qiydi (qo'shimcha kutubxonasiz)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# --- Uzum ---
UZUM_API_TOKEN = os.environ.get("UZUM_API_TOKEN", "").strip()
UZUM_API_BASE = os.environ.get("UZUM_API_BASE", "https://api-seller.uzum.uz/api/seller-openapi")
# Token bo'lmasa yoki DEMO_MODE=1 bo'lsa, dastur namunaviy ma'lumotlar bilan ishlaydi
DEMO_MODE = os.environ.get("DEMO_MODE", "").strip() == "1" or not UZUM_API_TOKEN

# --- AI (Claude) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-5-5")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# Botdan faqat shu chat foydalana oladi. Bo'sh bo'lsa, /start bosgan birinchi odam egasi bo'ladi.
TELEGRAM_OWNER_ID = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
DAILY_REPORT_HOUR = int(_float("DAILY_REPORT_HOUR", 21))
MORNING_REPORT_HOUR = int(_float("MORNING_REPORT_HOUR", 9))  # ertalabki "bugungi qarorlar" xabari

# --- Biznes sozlamalari (standart qiymatlar, panelda o'zgartirsa bo'ladi) ---
DEFAULT_TAX_RATE = _float("TAX_RATE", 0.04)            # aylanma solig'i (4%)
DEFAULT_TARGET_MARGIN = _float("TARGET_MARGIN", 0.20)  # maqsadli sof foyda (20%)
DEFAULT_COMMISSION_RATE = _float("COMMISSION_RATE", 0.15)  # tarix bo'lmasa taxminiy komissiya
DEFAULT_LOGISTICS_FEE = _float("LOGISTICS_FEE", 6000)      # tarix bo'lmasa taxminiy logistika (so'm/dona)

WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")
WEB_PORT = int(_float("WEB_PORT", 5000))
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "").strip()
SECRET_KEY = os.environ.get("SECRET_KEY", "sotuvchi-ai-local-secret")

DB_PATH = DATA_DIR / "sotuvchi.db"
