"""
Infografika (Uzum kartochkasi uchun asosiy rasm): 1080×1440 (3:4).

Yuqorida tovar rasmi, pastda sarlavha va 3-4 ta afzallik.
Shriftlar: Windows (Arial) yoki Linux (DejaVu), topilmasa Pillow standart shrifti.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1440
BG = (246, 244, 255)
DARK = (28, 22, 64)
ACCENT = (108, 60, 240)
ACCENT_LIGHT = (232, 224, 255)
WHITE = (255, 255, 255)

_FONT_CANDIDATES = {
    "regular": [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"],
    "bold": [r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
}


def font(size, bold=False):
    for path in _FONT_CANDIDATES["bold" if bold else "regular"]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw, text, fnt, max_w):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make(photo_path, title, bullets, out_path, badge=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # --- rasm maydoni ---
    box_top, box_h = 40, 820
    d.rounded_rectangle((40, box_top, W - 40, box_top + box_h), radius=48, fill=WHITE)
    if photo_path and Path(photo_path).exists():
        try:
            ph = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
            ph = ImageOps.contain(ph, (W - 120, box_h - 80))
            img.paste(ph, ((W - ph.width) // 2, box_top + (box_h - ph.height) // 2))
        except Exception:
            pass
    else:
        f = font(48, True)
        msg = "Rasm yo'q"
        d.text(((W - d.textlength(msg, font=f)) / 2, box_top + box_h / 2 - 30), msg, font=f, fill=(180, 170, 210))

    if badge:
        fb = font(36, True)
        bw = d.textlength(badge, font=fb) + 56
        d.rounded_rectangle((70, box_top + 30, 70 + bw, box_top + 100), radius=35, fill=ACCENT)
        d.text((98, box_top + 45), badge, font=fb, fill=WHITE)

    # --- sarlavha ---
    y = box_top + box_h + 40
    ft = font(54, True)
    for line in _wrap(d, title, ft, W - 120)[:2]:
        d.text((60, y), line, font=ft, fill=DARK)
        y += 66
    y += 20

    # --- afzalliklar ---
    fbul = font(38)
    for b in [x for x in bullets if x][:4]:
        lines = _wrap(d, b, fbul, W - 220)[:2]
        h = 34 + 48 * len(lines)
        if y + h > H - 30:
            break
        d.rounded_rectangle((60, y, W - 60, y + h), radius=28, fill=ACCENT_LIGHT)
        d.ellipse((88, y + h / 2 - 18, 124, y + h / 2 + 18), fill=ACCENT)
        d.text((106, y + h / 2), "+", font=font(34, True), fill=WHITE, anchor="mm")
        ty = y + 17
        for line in lines:
            d.text((150, ty), line, font=fbul, fill=DARK)
            ty += 48
        y += h + 18

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92)
    return str(out_path)
