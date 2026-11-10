"""Tekshiruvchilar uchun umumiy yordamchilar."""


def short(title, n=60):
    """Uzun tovar nomini so'z chegarasida qisqartiradi."""
    t = (title or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(" ,.;:-–") + "…"
