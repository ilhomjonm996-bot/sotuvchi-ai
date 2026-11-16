"""
Kartochka sog'lig'i auditi:
  - xususiyatlari (filtrlar) to'ldirilmagan tovarlar — qidiruv va filtrlarda ko'rinmaydi
  - VGX (o'lcham va og'irlik) to'ldirilmagan tovarlar
  - ko'p ko'riladi, kam sotib olinadi (past konversiya) — kartochka zaif
"""
import profit
from checks.util import short


def _active(p):
    st = p.get("status")
    st = (st.get("value") if isinstance(st, dict) else st) or ""
    return st != "ARCHIVED"


def run():
    prods = [p for p in profit.products_raw() if _active(p)]
    findings = []

    no_filters = [p for p in prods if p.get("allFiltersFilled") is False]
    if no_filters:
        names = ", ".join(short(p.get("title"), 30) for p in no_filters[:3])
        more = f" va yana {len(no_filters) - 3} ta" if len(no_filters) > 3 else ""
        findings.append({
            "key": "kartochka:filtrlar", "source": "kartochka", "level": "orange",
            "title": f"{len(no_filters)} ta tovarda xususiyatlar to'ldirilmagan",
            "text": f"Xaridor filtr bo'yicha qidirganda bu tovarlar chiqmaydi: {names}{more}.",
            "action": "Kabinet → Mahsulotlar → «Xususiyatlar to'ldirilmagan»: rang, material, o'lcham va boshqalarni kiriting.",
            "money": 0,
        })

    no_vgx = [p for p in prods if p.get("isWithoutWeightDimensional") is True]
    if no_vgx:
        findings.append({
            "key": "kartochka:vgx", "source": "kartochka", "level": "orange",
            "title": f"{len(no_vgx)} ta tovarda o'lcham va og'irlik (VGX) yo'q",
            "text": "VGX bo'lmasa logistika va saqlash noto'g'ri hisoblanadi, tovar omborga qabul qilinmasligi mumkin.",
            "action": "Kabinet → Mahsulotlar → «VGX to'ldirilmagan»: qadoq o'lchami va og'irligini kiriting.",
            "money": 0,
        })

    for p in prods:
        viewers = profit._num(p, "viewers")
        conv = profit._num(p, "conversion")  # foizda
        if viewers >= 100 and conv < 1.0:
            name = short(p.get("title") or str(p.get("productId")), 50)
            findings.append({
                "key": f"konversiya:{p.get('productId')}", "source": "kartochka", "level": "orange",
                "title": f"{name}: {viewers:.0f} kishi ko'rdi, {conv:.1f}% sotib oldi",
                "text": "Tovar ko'rinyapti, lekin kartochka xaridorni ishontirmayapti (rasm, narx, tavsif yoki sharhlar).",
                "action": "AI kartochka bo'limida yangi sarlavha, tavsif va infografika tayyorlang; narxni raqobatchilar bilan solishtiring.",
                "money": 0,
            })
    return findings
