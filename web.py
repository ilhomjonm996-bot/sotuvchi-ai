"""
Veb-panel (Flask). Ishga tushirish:  py web.py   →  brauzerda http://127.0.0.1:5000
"""
import functools
import logging
from pathlib import Path

import hmac
import secrets

from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from jinja2 import DictLoader

import ai_card
import checks
import config
import db
import market
import profit
import tenant
from uzum_client import UzumError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
def _secret_key():
    """Sessiya imzosi uchun kalit: .env dagi SECRET_KEY yoki data/flask.key (birinchi ishga tushishda yaratiladi)."""
    if config.SECRET_KEY and config.SECRET_KEY != "sotuvchi-ai-local-secret":
        return config.SECRET_KEY
    f = config.DATA_DIR / "flask.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


app.secret_key = _secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

# ======================================================================
# Shablonlar
# ======================================================================
BASE = r"""<!doctype html>
<html lang="uz"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}Sotuvchi AI{% endblock %} — Sotuvchi AI</title>
<style>
:root{--bg:#f6f5fb;--card:#fff;--ink:#1c1640;--muted:#6b6790;--line:#e7e4f3;--acc:#6c3cf0;--acc2:#efe9ff;
--ok:#14a05a;--okbg:#e6f7ee;--bad:#e0344b;--badbg:#fdeaed;--warn:#c27a00;--warnbg:#fff4dc}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink);font-size:15px}
a{color:var(--acc);text-decoration:none}
header{background:var(--ink);color:#fff;padding:0 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;position:sticky;top:0;z-index:5}
header .logo{font-weight:800;font-size:18px;padding:14px 0;color:#fff}.logo span{color:#b9a3ff}
nav{display:flex;gap:4px;flex-wrap:wrap}nav a{color:#cfc8f5;padding:16px 12px;border-bottom:3px solid transparent}
nav a.on,nav a:hover{color:#fff;border-color:#b9a3ff}
main{max-width:1180px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
.grid{display:grid;gap:14px}.g4{grid-template-columns:repeat(4,1fr)}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:2fr 1fr}
@media(max-width:860px){.g4{grid-template-columns:1fr 1fr}.g2,.g3{grid-template-columns:1fr}}
.kpi .l{color:var(--muted);font-size:13px}.kpi .v{font-size:26px;font-weight:800;margin-top:6px;white-space:nowrap}.kpi .s{font-size:12px;color:var(--muted);margin-top:4px}
.pos{color:var(--ok)}.neg{color:var(--bad)}
.tabs{display:inline-flex;background:#fff;border:1px solid var(--line);border-radius:12px;padding:4px;margin-bottom:18px;flex-wrap:wrap}
.tabs a{padding:8px 14px;border-radius:9px;color:var(--muted);font-weight:600}.tabs a.on{background:var(--acc);color:#fff}
table{width:100%;border-collapse:collapse}th,td{padding:10px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.03em}td.n,th.n{text-align:right;white-space:nowrap}
.tw{overflow-x:auto}
.btn{display:inline-block;border:0;border-radius:10px;padding:9px 16px;font-weight:600;cursor:pointer;font-size:14px;background:var(--acc);color:#fff;font-family:inherit}
.btn.sec{background:var(--acc2);color:var(--acc)}.btn.ok{background:var(--ok)}.btn.bad{background:#fff;color:var(--bad);border:1px solid #f3c1c8}.btn.sm{padding:6px 11px;font-size:13px}
input,select,textarea{font:inherit;padding:9px 11px;border:1px solid var(--line);border-radius:10px;background:#fff;color:var(--ink);width:100%}
input.sm{width:110px;padding:6px 8px}label{font-size:13px;color:var(--muted);display:block;margin:0 0 5px}
.form{display:grid;gap:12px;grid-template-columns:1fr 1fr}.form .full{grid-column:1/-1}@media(max-width:600px){.form{grid-template-columns:1fr}}
.pill{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700;white-space:nowrap}
.p-loss{background:var(--badbg);color:var(--bad)}.p-low{background:var(--warnbg);color:var(--warn)}.p-ok{background:var(--okbg);color:var(--ok)}
.p-high,.p-nocost{background:#eeeef4;color:var(--muted)}
.banner{background:var(--warnbg);color:#7a4c00;border-radius:12px;padding:10px 14px;margin-bottom:16px;font-size:14px}
.flash{background:var(--okbg);color:#0b6b3b;border-radius:12px;padding:10px 14px;margin-bottom:16px}
.flash.err{background:var(--badbg);color:var(--bad)}
.bar{height:10px;border-radius:6px;background:var(--acc2);overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
.wf{display:grid;grid-template-columns:118px minmax(40px,1fr) auto;gap:10px;align-items:center;margin:8px 0;font-size:14px}
.copy{position:relative;background:#faf9ff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;white-space:pre-wrap;margin-bottom:12px}
.copy h4{margin:0 0 6px;font-size:12px;color:var(--muted);text-transform:uppercase}
.copy button{position:absolute;top:8px;right:8px}
.muted{color:var(--muted)}.small{font-size:13px}
.chart svg{width:100%;height:220px;display:block}
.legend{display:flex;gap:16px;font-size:13px;color:var(--muted);margin-top:6px}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
</style></head><body>
<header><a class="logo" href="/">Sotuvchi <span>AI</span></a>
<nav>{% for href, name in [("/","Bosh sahifa"),("/qarorlar","Qarorlar"),("/products","Tovarlar"),("/prices","Narxlar"),("/raqobat","Raqobat"),("/bozor","Bozor"),("/card","AI kartochka"),("/settings","Sozlamalar")] %}
<a href="{{href}}" class="{{'on' if active==href}}">{{name}}</a>{% endfor %}{% if session.get('seller_id') %}<a href="/chiqish">Chiqish</a>{% endif %}</nav></header>
<main>
{% if demo %}<div class="banner">🧪 <b>Demo rejim:</b> namunaviy do'kon ma'lumotlari ko'rsatilmoqda. Haqiqiy do'kon Uzum Seller API kaliti orqali ulanadi.</div>{% endif %}
{% if est_costs and not demo and active in ('/', '/products', '/prices') %}<div class="banner" style="background:#eef3ff;color:#2a3f8f">ℹ️ Tannarxlar <b>taxminiy</b> (tovar turiga qarab sotuv narxining 25–45%). Aniq raqamni <a href="/products">Tovarlar</a> sahifasida yozsangiz, hisob avtomatik yangilanadi.</div>{% endif %}
{% with msgs = get_flashed_messages(with_categories=true) %}{% for cat, m in msgs %}<div class="flash {{'err' if cat=='error'}}">{{m}}</div>{% endfor %}{% endwith %}
{% block body %}{% endblock %}
</main>
<script>
function copyText(id,btn){const t=document.getElementById(id).innerText;navigator.clipboard.writeText(t).then(()=>{const o=btn.innerText;btn.innerText="✓ Nusxalandi";setTimeout(()=>btn.innerText=o,1500)})}
</script>
</body></html>"""

DASHBOARD = r"""{% extends "base.html" %}{% block title %}Bosh sahifa{% endblock %}{% block body %}
<h1>{{ r.shop_name }}</h1><p class="sub">Sof foyda hisoboti — Uzum komissiyasi, logistika, tannarx, soliq va xarajatlar hisobga olingan</p>
{% if decisions %}<div class="card" style="margin-bottom:16px;border-color:#cbb8ff"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><b>☀️ Bugungi qarorlar</b><a href="/qarorlar" class="small">Hammasi ({{ decisions_total }}) →</a></div>
{% for d in decisions %}<div style="display:flex;gap:12px;align-items:flex-start;margin-top:12px"><span style="font-size:18px">{{ d.icon }}</span><div style="flex:1"><b>{{ d.title }}</b>{% if d.money %} <span class="pill p-{{ 'loss' if d.level=='red' else 'low' if d.level=='orange' else 'ok' }}">~{{ f(d.money) }} so'm{{ ' bir martalik' if d.once else '/oy' }}</span>{% endif %}<div class="small muted">{{ d.text }}</div><div class="small">👉 {{ d.action }}</div></div></div>{% endfor %}</div>{% endif %}
<div class="tabs">{% for k, v in periods.items() %}<a href="/?p={{k}}" class="{{'on' if k==r.period}}">{{v}}</a>{% endfor %}</div>
<div class="grid g4">
 <div class="card kpi"><div class="l">Tushum</div><div class="v">{{ f(t.revenue) }}</div><div class="s">so'm · {{ t.qty|int }} dona sotildi</div></div>
 <div class="card kpi"><div class="l">Sof foyda</div><div class="v {{'pos' if t.profit>=0 else 'neg'}}">{{ f(t.profit) }}</div><div class="s">so'm · hamma xarajatlardan keyin</div></div>
 <div class="card kpi"><div class="l">Sof marja</div><div class="v">{{ '%.1f'|format(t.margin*100) }}%</div><div class="s">har 100 so'mdan {{ '%.0f'|format(t.margin*100) }} so'm foyda</div></div>
 <div class="card kpi"><div class="l">Buyurtmalar</div><div class="v">{{ t.orders }}</div><div class="s">bekor qilingan: {{ t.canceled }} · qaytgan: {{ t.returns|int }}</div></div>
</div>
<div class="grid g3" style="margin-top:14px">
 <div class="card chart"><b>{{ series.title }}</b>
  {% set mx = [series.revenue|max, 1]|max %}{% set n = series.labels|length %}
  <svg viewBox="0 0 {{ n*20 }} 200" preserveAspectRatio="none">
   {% for i in range(n) %}{% set rv = series.revenue[i] %}{% set pf = series.profit[i] %}
    <rect x="{{ i*20+3 }}" y="{{ 195 - rv/mx*185 }}" width="14" height="{{ rv/mx*185 }}" rx="2" fill="#e3daff"><title>{{series.labels[i]}}: tushum {{f(rv)}}</title></rect>
    {% if pf>0 %}<rect x="{{ i*20+6 }}" y="{{ 195 - pf/mx*185 }}" width="8" height="{{ pf/mx*185 }}" rx="2" fill="#6c3cf0"><title>{{series.labels[i]}}: foyda {{f(pf)}}</title></rect>{% endif %}
   {% endfor %}
  </svg>
  <div class="legend"><span><i style="background:#e3daff"></i>Tushum</span><span><i style="background:#6c3cf0"></i>Foyda (xarajatlargacha)</span><span>{{series.labels[0]}} — {{series.labels[-1]}}</span></div>
 </div>
 <div class="card"><b>Pul qayerga ketdi</b>
  {% set rows = [("Komissiya",t.commission),("Logistika",t.logistics),("Tannarx",t.cost),("Soliq",t.tax),("Uzum xarajatlari",t.expenses),("Sof foyda",t.profit)] %}
  {% for name, v in rows %}<div class="wf"><span>{{name}}</span><div class="bar"><i style="width:{{ [0,(v/t.revenue*100) if t.revenue else 0]|max }}%;{{'background:#14a05a' if name=='Sof foyda'}}"></i></div><span class="n" style="text-align:right">{{ f(v) }}</span></div>{% endfor %}
  {% if r.expenses_by %}<p class="small muted" style="margin:12px 0 0">Uzum xarajatlari: {% for n,v in r.expenses_by %}{{n}} {{f(v)}}{{ ', ' if not loop.last }}{% endfor %}</p>{% endif %}
 </div>
</div>
<div class="card" style="margin-top:14px"><b>Tovarlar bo'yicha foyda / zarar</b>
 {% if r.missing_costs %}<p class="small neg">❗ {{ r.missing_costs|length }} ta tovarga tannarx kiritilmagan — <a href="/products">Tovarlar</a> sahifasida kiriting.</p>{% endif %}
 <div class="tw"><table><tr><th>Tovar</th><th class="n">Sotildi</th><th class="n">Tushum</th><th class="n">Uzum (kom.+log.)</th><th class="n">Tannarx</th><th class="n">Sof foyda</th><th class="n">Marja</th></tr>
 {% for it in r["items"] %}<tr><td>{{ it.title }}</td><td class="n">{{ it.qty|int }}</td><td class="n">{{ f(it.revenue) }}</td><td class="n">{{ f(it.commission+it.logistics) }}</td><td class="n">{{ f(it.cost) }}</td>
 <td class="n {{'pos' if it.profit>=0 else 'neg'}}"><b>{{ f(it.profit) }}</b></td><td class="n">{{ '%.1f'|format(it.margin*100) }}%</td></tr>
 {% else %}<tr><td colspan="7" class="muted">Bu davrda sotuv yo'q</td></tr>{% endfor %}</table></div>
</div>
{% endblock %}"""

PRODUCTS = r"""{% extends "base.html" %}{% block title %}Tovarlar{% endblock %}{% block body %}
<h1>Tovarlar</h1><p class="sub">Har bir tovarning tannarxini kiriting — foyda shunga qarab hisoblanadi. «Qo'shimcha» = yetkazib kelish, qadoqlash va h.k. (1 dona uchun).</p>
<div class="card tw"><table><tr><th>SKU</th><th>Tovar</th><th class="n">Narx</th><th class="n">Qoldiq</th><th class="n">1 yilda sotildi</th><th class="n">1 yil foyda</th><th>Tannarx (1 dona)</th><th>Qo'shimcha</th><th></th></tr>
{% for s in skus %}{% set c = costs.get(s.sku_id) %}{% set pr = profits.get(s.sku_id) %}
<tr><form method="post" action="/products"><input type="hidden" name="sku_id" value="{{s.sku_id}}"><input type="hidden" name="title" value="{{s.title}}">
<td class="muted small">{{ s.sku_id }}</td><td>{{ s.title }}</td><td class="n">{{ f(s.price) }}</td><td class="n">{{ s.stock }}</td><td class="n">{{ pr.qty|int if pr else 0 }}</td>
<td class="n {{'pos' if pr and pr.profit>=0 else 'neg'}}">{{ f(pr.profit) if pr else '—' }}</td>
<td><input class="sm" name="unit_cost" type="number" min="0" step="100" value="{{ (c.unit_cost if c else s.purchase_price)|int }}">{% if not c and s.purchase_price %}<div class="small muted">Uzum'dan</div>{% endif %}</td>
<td><input class="sm" name="extra_cost" type="number" min="0" step="100" value="{{ (c.extra_cost if c else 0)|int }}"></td>
<td><button class="btn sm sec">Saqlash</button></td></form></tr>
{% endfor %}</table></div>
{% endblock %}"""

PRICES = r"""{% extends "base.html" %}{% block title %}Narxlar{% endblock %}{% block body %}
<h1>Aqlli narx maslahati</h1>
<p class="sub">Minimal narx — zararsiz chegara. Tavsiya narx — {{ '%.0f'|format(margin*100) }}% sof foyda beradi (soliq {{ '%.0f'|format(tax*100) }}%). Komissiya va logistika har bir tovarning o'z sotuv tarixidan olinadi.</p>
{% if pending %}<div class="card" style="margin-bottom:14px;border-color:#cbb8ff"><b>Tasdiqlashni kutayotgan takliflar ({{pending|length}})</b>
{% if not demo %}<p class="small neg">⚠️ «Tasdiqlash» bosilsa, narx haqiqiy do'koningizda DARHOL o'zgaradi.</p>{% endif %}
<div class="tw"><table><tr><th>Tovar</th><th class="n">Hozir</th><th class="n">Yangi narx</th><th class="n">Chizilgan narx</th><th>Sabab</th><th></th></tr>
{% for p in pending %}<tr><td>{{p.title}}</td><td class="n">{{f(p.old_price)}}</td><td class="n"><b>{{f(p.new_price)}}</b></td><td class="n muted">{{f(p.full_price)}}</td><td class="small muted">{{p.reason}}</td>
<td style="white-space:nowrap"><form method="post" action="/prices/{{p.id}}/approve" style="display:inline" {% if not demo %}onsubmit="return confirm('Haqiqiy do\'konda narx {{f(p.new_price)}} so\'mga o\'zgaradi. Davom etasizmi?')"{% endif %}><button class="btn sm ok">Tasdiqlash</button></form>
<form method="post" action="/prices/{{p.id}}/reject" style="display:inline"><button class="btn sm bad">Rad etish</button></form></td></tr>{% endfor %}
</table></div></div>{% endif %}
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px"><b>Barcha tovarlar</b>
<form method="post" action="/prices/generate"><button class="btn">🤖 Narx takliflarini yaratish</button></form></div>
<div class="tw"><table><tr><th>Tovar</th><th>Holat</th><th class="n">Hozirgi narx</th><th class="n">Minimal</th><th class="n">Tavsiya</th><th class="n">1 donadan foyda</th><th class="n">Komissiya</th><th class="n">Logistika</th></tr>
{% for a in advice %}<tr><td>{{a.title}}<div class="small muted">1 yilda {{a.sold90}} dona{{ '' if a.from_history else ' · taxminiy stavkalar' }}</div></td>
<td><span class="pill p-{{a.status}}">{{a.status_text}}</span></td><td class="n">{{f(a.price)}}</td>
<td class="n">{{ f(a.min) if a.min else '—' }}</td><td class="n"><b>{{ f(a.rec) if a.rec else '—' }}</b></td>
<td class="n {{ 'pos' if a.unit_profit is defined and a.unit_profit>=0 else 'neg' }}">{{ f(a.unit_profit) if a.unit_profit is defined else '—' }}</td>
<td class="n">{{ '%.0f'|format(a.commission_rate*100) }}%</td><td class="n">{{ f(a.logistics) }}</td></tr>{% endfor %}
</table></div></div>
{% if history %}<div class="card" style="margin-top:14px"><b>Tarix</b><div class="tw"><table><tr><th>Tovar</th><th class="n">Eski</th><th class="n">Yangi</th><th>Holat</th></tr>
{% for p in history %}<tr><td>{{p.title}}</td><td class="n">{{f(p.old_price)}}</td><td class="n">{{f(p.new_price)}}</td>
<td>{% if p.status=='approved' %}<span class="pill p-ok">Tasdiqlangan</span>{% elif p.status=='rejected' %}<span class="pill p-nocost">Rad etilgan</span>{% else %}<span class="pill p-loss">Xato</span> <span class="small muted">{{p.error}}</span>{% endif %}</td></tr>{% endfor %}
</table></div></div>{% endif %}
{% endblock %}"""

CARD_FORM = r"""{% extends "base.html" %}{% block title %}AI kartochka{% endblock %}{% block body %}
<h1>AI kartochka</h1><p class="sub">Tovar rasmini va qisqa ma'lumotni yuboring — AI o'zbekcha va ruscha sarlavha, tavsif, xususiyatlar, kalit so'zlar, infografika va tavsiya narx tayyorlaydi.</p>
{% if not ai %}<div class="banner">AI kaliti (ANTHROPIC_API_KEY) kiritilmagan — hozircha shablon matn ishlatiladi. Infografika va narx baribir tayyorlanadi.</div>{% endif %}
<div class="grid g2"><form class="card form" method="post" action="/card" enctype="multipart/form-data" onsubmit="this.querySelector('button').innerText='⏳ AI tayyorlamoqda... (20-40 soniya)'">
<div class="full"><label>Tovar rasmi</label><input type="file" name="photo" accept="image/*"></div>
<div class="full"><label>Nomi *</label><input name="name" required placeholder="Masalan: Termos 1 litr"></div>
<div><label>Rangi</label><input name="color" placeholder="qora"></div><div><label>O'lchami</label><input name="size" placeholder="1 L / 42 / 30×40 sm"></div>
<div><label>Soni / to'plam</label><input name="quantity" placeholder="1 dona"></div><div><label>Materiali</label><input name="material" placeholder="zanglamaydigan po'lat"></div>
<div><label>Tannarx (1 dona, so'm)</label><input name="cost" type="number" min="0" placeholder="40000"></div><div><label>Yetkazib kelish (1 dona, so'm)</label><input name="extra_cost" type="number" min="0" placeholder="3000"></div>
<div class="full"><label>Qo'shimcha izoh</label><textarea name="notes" rows="2" placeholder="Masalan: 24 soat issiq saqlaydi"></textarea></div>
<div class="full"><button class="btn">✨ Kartochka yaratish</button></div></form>
<div class="card"><b>Oldingi kartochkalar</b>{% for c in cards %}<div style="display:flex;gap:10px;align-items:center;margin-top:10px">
<img src="/files/{{ c.infographic_path|basename }}" style="width:48px;height:64px;object-fit:cover;border-radius:6px"><a href="/card/{{c.id}}">{{ c.name }}</a></div>{% else %}<p class="muted">Hali yo'q</p>{% endfor %}</div></div>
{% endblock %}"""

CARD_VIEW = r"""{% extends "base.html" %}{% block title %}{{ c.name }}{% endblock %}{% block body %}
<p><a href="/card">← Yangi kartochka</a></p><h1>{{ res.title_uz }}</h1>
<p class="sub">{% if res.ai_used %}🤖 AI tayyorladi{% else %}📝 Shablon matn{% if res.ai_error %} ({{res.ai_error}}){% endif %}{% endif %}{% if res.category_hint %} · Kategoriya: {{res.category_hint}}{% endif %}.
Uzum Open API kartochka yaratishga ruxsat bermaydi — matnlarni nusxalab, seller.uzum.uz kabinetiga qo'ying.</p>
<div class="grid g3"><div>
{% set blocks = [("title_uz","Sarlavha (UZ)",res.title_uz),("title_ru","Sarlavha (RU)",res.title_ru),("description_uz","Tavsif (UZ)",res.description_uz),("description_ru","Tavsif (RU)",res.description_ru),
("features_uz","Xususiyatlar (UZ)",(res.features_uz or [])|join("\n")),("features_ru","Xususiyatlar (RU)",(res.features_ru or [])|join("\n")),
("keywords_uz","Kalit so'zlar (UZ)",(res.keywords_uz or [])|join(", ")),("keywords_ru","Kalit so'zlar (RU)",(res.keywords_ru or [])|join(", "))] %}
{% for id, name, text in blocks %}<div class="copy"><h4>{{name}}</h4><div id="{{id}}">{{text}}</div><button class="btn sm sec" onclick="copyText('{{id}}',this)">Nusxalash</button></div>{% endfor %}
</div><div>
<div class="card"><b>Infografika (1080×1440)</b><img src="/files/{{ c.infographic_path|basename }}" style="width:100%;border-radius:10px;margin-top:10px"><a class="btn sec" style="margin-top:10px" href="/files/{{ c.infographic_path|basename }}" download>⬇ Yuklab olish</a></div>
<div class="card" style="margin-top:14px"><b>Narx tavsiyasi</b>{% if res.price %}
<div class="wf" style="grid-template-columns:1fr auto"><span>Zararsiz minimum</span><b>{{f(res.price.min)}} so'm</b></div>
<div class="wf" style="grid-template-columns:1fr auto"><span>Tavsiya narx</span><b class="pos">{{f(res.price.rec)}} so'm</b></div>
<div class="wf" style="grid-template-columns:1fr auto"><span>Chizilgan narx</span><b class="muted">{{f(res.price.full)}} so'm</b></div>
<p class="small muted">Komissiya {{ '%.0f'|format(comm*100) }}% va logistika {{f(logi)}} so'm taxminiy olindi.</p>
{% else %}<p class="muted">Tannarx kiritilmagani uchun hisoblanmadi.</p>{% endif %}</div>
</div></div>
{% endblock %}"""

SETTINGS = r"""{% extends "base.html" %}{% block title %}Sozlamalar{% endblock %}{% block body %}
<h1>Sozlamalar</h1><p class="sub">Biznes parametrlari va ulanishlar holati</p>
<div class="grid g2"><form class="card form" method="post">
<div><label>Soliq stavkasi, %</label><input name="tax" type="number" step="0.1" min="0" max="50" value="{{ '%g'|format(tax*100) }}"></div>
<div><label>Maqsadli sof foyda (marja), %</label><input name="margin" type="number" step="0.5" min="0" max="70" value="{{ '%g'|format(margin*100) }}"></div>
{% if shops|length > 1 %}<div class="full"><label>Do'kon</label><select name="shop_id">{% for s in shops %}<option value="{{s.id}}" {{'selected' if s.id==shop.id}}>{{s.name}}</option>{% endfor %}</select></div>{% endif %}
<div class="full"><button class="btn">Saqlash</button></div></form>
<div class="card"><b>Ulanishlar</b><table>
<tr><td>Uzum do'koni</td><td>{% if demo %}<span class="pill p-low">Demo</span>{% else %}<span class="pill p-ok">Ulangan</span> {{shop.name}}{% endif %}</td></tr>
<tr><td>AI (Claude)</td><td>{% if ai %}<span class="pill p-ok">Ulangan</span> <span class="small muted">{{model}}</span>{% else %}<span class="pill p-nocost">Kalit yo'q</span>{% endif %}</td></tr>
<tr><td>Telegram bot</td><td>{% if tg %}<span class="pill p-ok">Token bor</span>{% else %}<span class="pill p-nocost">Token yo'q</span>{% endif %}</td></tr>
</table><p class="small muted">Uzum kalitingiz shifrlangan holda saqlanadi va faqat sizning do'koningiz uchun ishlatiladi. Kalitni almashtirish — botda /ulash, butunlay o'chirish — /uzish.</p></div></div>
{% endblock %}"""

QARORLAR = r"""{% extends "base.html" %}{% block title %}Qarorlar{% endblock %}{% block body %}
<h1>Qarorlar</h1><p class="sub">AI agentlar do'koningizni tekshirib topgan muammolar va imkoniyatlar — avval pul hozir ketayotganlari. Summalar taxminiy.</p>
{% for d in items %}<div class="card" style="margin-bottom:12px;display:flex;gap:14px;align-items:flex-start;{{ 'border-color:#f3c1c8' if d.level=='red' }}">
<span style="font-size:22px">{{ d.icon }}</span><div style="flex:1"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><b>{{ d.title }}</b>{% if d.money %}<span class="pill p-{{ 'loss' if d.level=='red' else 'low' if d.level=='orange' else 'ok' }}">~{{ f(d.money) }} so'm{{ ' bir martalik' if d.once else '/oy' }}</span>{% endif %}</div>
<p style="margin:6px 0" class="muted">{{ d.text }}</p><p style="margin:0">👉 {{ d.action }}</p><p class="small muted" style="margin:6px 0 0">Agent: {{ names.get(d.source, d.source) }}</p></div></div>
{% else %}<div class="card"><p>✅ Hozircha muhim muammo topilmadi.</p></div>{% endfor %}
{% endblock %}"""

RAQOBAT = r"""{% extends "base.html" %}{% block title %}Raqobat{% endblock %}{% block body %}
<h1>Raqobatchilar</h1><p class="sub">Raqobatchi tovarlarini kuzating: narxi, qoldig'i va sotuvi o'z tovaringiz bilan solishtiriladi. Muhim o'zgarishlar «Qarorlar»ga tushadi.</p>
{% if not live %}<div class="banner" style="background:#eef3ff;color:#2a3f8f">ℹ️ {{ live_msg }}</div>{% endif %}
<div class="card tw" style="margin-bottom:14px"><table><tr><th>Raqobatchi</th><th>Mening tovarim</th><th class="n">Uning narxi</th><th class="n">Mening narxim</th><th class="n">Farq</th><th class="n">7 kunda narx</th><th class="n">Qoldiq</th><th class="n">7 kunda sotuv</th><th></th></tr>
{% for c in rows %}{% set l = c.last %}<tr>
<td>{% if c.url %}<a href="{{ c.url }}" target="_blank" rel="noopener noreferrer">{{ c.title }}</a>{% else %}{{ c.title }}{% endif %}<div class="small muted">{{ c.shop or ('qo\'lda kiritiladi' if c.manual else '') }}{% if l %} · {{ l.day }}{% endif %}{% if l and l.rating %} · ⭐ {{ l.rating }}{% endif %}</div></td>
<td class="small"><form method="post" action="/raqobat/{{c.id}}/bogla"><select name="my_sku_id" onchange="this.form.submit()" style="padding:5px 8px;font-size:13px;max-width:220px"><option value="">— bog'lanmagan —</option>{% for p in mine %}<option value="{{p.sku_id}}" {{ 'selected' if p.sku_id == c.my_sku_id }}>{{p.title}}</option>{% endfor %}</select></form></td>
<td class="n"><b>{{ f(l.price) if l and l.price else '—' }}</b></td><td class="n">{{ f(c.mine.price) if c.mine else '—' }}</td>
<td class="n">{% if c.diff is not none %}<span class="pill {{ 'p-loss' if c.diff <= -0.1 else 'p-ok' if c.diff >= 0.05 else 'p-nocost' }}">{{ '%+.0f'|format(c.diff*100) }}%</span>{% else %}—{% endif %}</td>
<td class="n {{ 'neg' if c.price_change is not none and c.price_change < 0 }}">{% if c.price_change is none %}—{% elif c.price_change|abs < 0.005 %}0%{% else %}{{ '%+.0f%%'|format(c.price_change*100) }}{% endif %}</td>
<td class="n">{% if l and l.stock is not none %}{% if l.stock == 0 %}<span class="pill p-ok">tugagan</span>{% else %}{{ l.stock }}{% endif %}{% else %}—{% endif %}</td>
<td class="n">{{ c.sold7 if c.sold7 is not none else '—' }}</td>
<td style="white-space:nowrap">{% if c.manual %}<form method="post" action="/raqobat/{{c.id}}/narx" style="display:inline-flex;gap:4px"><input class="sm" name="price" type="number" min="1" step="100" placeholder="yangi narx" required><button class="btn sm sec">✓</button></form>{% endif %}
<form method="post" action="/raqobat/{{c.id}}/ochir" style="display:inline" onsubmit="return confirm('Kuzatuvdan olib tashlansinmi?')"><button class="btn sm bad">✕</button></form></td></tr>
{% else %}<tr><td colspan="9" class="muted">Hali raqobatchi qo'shilmagan.</td></tr>{% endfor %}</table>
<p class="small muted" style="margin:10px 0 0">Farq — raqobatchi narxi siznikidan necha foiz past (−) yoki baland (+). «7 kunda sotuv» — buyurtmalar sonining o'sishi (taxminiy).</p></div>
<form class="card form" method="post" action="/raqobat">
<div class="full"><b>Raqobatchi qo'shish</b></div>
<div class="full"><label>Uzum'dagi tovar havolasi *</label><input name="link" required placeholder="https://uzum.uz/uz/product/termos-...-2203614"></div>
<div><label>Qaysi tovarim bilan solishtirish</label><select name="my_sku_id"><option value="">— tanlang —</option>{% for p in mine %}<option value="{{p.sku_id}}">{{p.title}} ({{ f(p.price) }})</option>{% endfor %}</select></div>
{% if not live %}<div><label>Raqobatchi tovar nomi *</label><input name="title" placeholder="Masalan: ThermoPro termos 1 L"></div>
<div><label>Uning hozirgi narxi, so'm *</label><input name="price" type="number" min="1" step="100"></div>
<div><label>Qoldig'i (bilsangiz)</label><input name="stock" type="number" min="0"></div>{% endif %}
<div class="full"><button class="btn">+ Kuzatuvga qo'shish</button></div></form>
{% endblock %}"""

BOZOR = r"""{% extends "base.html" %}{% block title %}Bozor tahlili{% endblock %}{% block body %}
<h1>Bozor tahlili</h1><p class="sub">Kalit so'z bo'yicha Uzum'dagi o'xshash tovarlar: narx oralig'i, talab, raqobat va qaysi narxda ko'proq sotilishi.</p>
<form class="card" method="get" action="/bozor" style="display:flex;gap:10px;margin-bottom:14px"><input name="q" value="{{ q }}" placeholder="Masalan: termos, charm kamar, iPhone g'ilof" required><button class="btn" style="white-space:nowrap">🔍 Tahlil</button></form>
{% if error %}<div class="banner" style="background:#eef3ff;color:#2a3f8f">ℹ️ {{ error }}</div>{% endif %}
{% if a %}
{% if a.source == 'demo' %}<p class="small muted">Namunaviy bozor ma'lumoti (demo).</p>{% endif %}
<div class="grid g4">
 <div class="card kpi"><div class="l">Nisha bahosi</div><div class="v">{{ a.score }}/10</div><div class="s">talab: {{ a.demand }} · raqobat: {{ a.competition }}</div></div>
 <div class="card kpi"><div class="l">O'rtacha narx (mediana)</div><div class="v">{{ f(a.price_median) }}</div><div class="s">ko'pchilik {{ f(a.p25) }} – {{ f(a.p75) }} so'm</div></div>
 <div class="card kpi"><div class="l">Tovarlar / sotuvchilar</div><div class="v">{{ a.count }} / {{ a.shops }}</div><div class="s">tugaganlar: {{ a.out_of_stock }}</div></div>
 <div class="card kpi"><div class="l">Buyurtmalar (jami)</div><div class="v">{{ f(a.orders_total) }}</div><div class="s">top-3 ulushi {{ '%.0f'|format(a.top3_share*100) }}% · ⭐ {{ '%.1f'|format(a.avg_rating) }}</div></div>
</div>
<div class="card" style="margin-top:14px;border-color:#cbb8ff"><b>💡 Xulosa</b><p style="margin:8px 0 0">{{ a.advice }}</p>
{% if a.mine %}<p style="margin:8px 0 0">Sizning «{{ a.mine.title }}» narxingiz {{ f(a.mine.price) }} so'm — bozor medianasidan <b class="{{ 'neg' if a.mine.vs > 0.15 else '' }}">{{ '%+.0f'|format(a.mine.vs*100) }}%</b>.{% if a.mine.min %} Zararsiz minimumingiz {{ f(a.mine.min) }} so'm.{% endif %}</p>{% endif %}</div>
<div class="grid g2" style="margin-top:14px">
<div class="card"><b>Narx segmentlari</b>{% set mx = [a.segments|map(attribute='per_item')|max, 1]|max %}
{% for s in a.segments %}<div class="wf" style="grid-template-columns:150px 1fr auto"><span>{{ f(s.lo) }}–{{ f(s.hi) }}</span><div class="bar"><i style="width:{{ s.per_item/mx*100 }}%;{{ 'background:#14a05a' if a.best and s.lo==a.best.lo }}"></i></div><span class="small">{{ s.count }} tovar · {{ '%.0f'|format(s.per_item) }}/tovar</span></div>{% endfor %}
<p class="small muted" style="margin:8px 0 0">Yashil — har bir tovarga eng ko'p buyurtma to'g'ri keladigan oraliq.</p></div>
<div class="card tw"><b>Eng ko'p sotilganlar</b><table><tr><th>Tovar</th><th class="n">Narx</th><th class="n">Buyurtma</th><th class="n">⭐</th></tr>
{% for i in a.top %}<tr><td class="small">{{ i.title }}<div class="muted">{{ i.shop }}</div></td><td class="n">{{ f(i.price) }}</td><td class="n">{{ f(i.orders) }}</td><td class="n">{{ i.rating }}</td></tr>{% endfor %}</table></div>
</div>{% endif %}
{% endblock %}"""

KIRISH = r"""{% extends "base.html" %}{% block title %}Kirish{% endblock %}{% block body %}<div class="card" style="max-width:520px;margin:50px auto">
<h1>Panelga kirish</h1>
{% if expired %}<p class="neg">Bu havola eskirgan yoki allaqachon ishlatilgan.</p>{% endif %}
<p>Har bir sotuvchi faqat o'z paneliga kiradi. Kirish uchun:</p>
<ol><li>Telegram'da Sotuvchi AI botini oching</li><li><code>/panel</code> deb yozing</li><li>Bot yuborgan havolani bosing (15 daqiqa amal qiladi, bir martalik)</li></ol>
<p class="small muted">Do'kon hali ulanmagan bo'lsa, botda /ulash yoki /demo.</p></div>{% endblock %}"""

LOGIN = r"""{% extends "base.html" %}{% block body %}<form class="card" method="post" style="max-width:360px;margin:60px auto">
<h1>Kirish</h1><p class="sub">Panel paroli</p><input type="password" name="password" autofocus><p><button class="btn">Kirish</button></p></form>{% endblock %}"""

ERROR = r"""{% extends "base.html" %}{% block body %}<div class="card"><h1>Xatolik</h1><p>{{ msg }}</p><p class="muted small">Uzum tokenini va internetni tekshiring. Muammo davom etsa, <code>.env</code> faylida <code>DEMO_MODE=1</code> qilib demo rejimda ishlating.</p></div>{% endblock %}"""

app.jinja_loader = DictLoader({
    "base.html": BASE, "dashboard.html": DASHBOARD, "products.html": PRODUCTS, "prices.html": PRICES,
    "card_form.html": CARD_FORM, "card_view.html": CARD_VIEW, "settings.html": SETTINGS,
    "login.html": LOGIN, "error.html": ERROR, "qarorlar.html": QARORLAR, "kirish.html": KIRISH,
    "raqobat.html": RAQOBAT, "bozor.html": BOZOR,
})
app.jinja_env.filters["basename"] = lambda p: Path(p or "").name


@app.context_processor
def _ctx():
    if g.get("tenant_token") is None:
        return {"f": profit.fmt, "demo": False, "active": "", "est_costs": False, "seller": None}
    return {"f": profit.fmt, "demo": tenant.is_demo(), "active": "/" + request.path.strip("/").split("/")[0],
            "est_costs": db.get_setting("costs_estimated") == "1", "seller": tenant.seller()}


# ======================================================================
# Kirish: har bir sotuvchi faqat o'z paneliga
#   - botdagi /panel → bir martalik havola /kirish/<token> → sessiya
#   - ochiq demo sayt (DEMO_MODE) va lokal kompyuter (parolsiz) → ega (#1)
#   - WEB_PASSWORD → eski parol bilan ega (#1)
# ======================================================================
_PUBLIC = {"login", "kirish", "kirish_info", "static"}


def _local():
    return request.remote_addr in ("127.0.0.1", "::1")


@app.before_request
def _auth():
    g.tenant_token = None
    if request.endpoint in _PUBLIC:
        return None
    sid = session.get("seller_id")
    if sid and db.get_seller(sid):
        g.tenant_token = tenant.set_current(sid)
        return None
    if config.DEMO_MODE or (_local() and not config.WEB_PASSWORD):
        g.tenant_token = tenant.set_current(tenant.OWNER_ID)
        return None
    if config.WEB_PASSWORD:
        return redirect(url_for("login"))
    return redirect(url_for("kirish_info"))


@app.teardown_request
def _reset_tenant(exc=None):
    tok = g.pop("tenant_token", None)
    if tok is not None:
        tenant.reset(tok)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if config.WEB_PASSWORD and hmac.compare_digest(request.form.get("password", ""), config.WEB_PASSWORD):
            session.clear()
            session["seller_id"] = tenant.OWNER_ID
            return redirect("/")
        flash("Parol noto'g'ri", "error")
    return render_template("login.html")


@app.route("/kirish")
def kirish_info():
    return render_template("kirish.html", ok=False)


@app.route("/kirish/<tok>")
def kirish(tok):
    sid = db.use_login_token(tok)
    if not sid:
        return render_template("kirish.html", ok=False, expired=True), 403
    session.clear()
    session["seller_id"] = sid
    session.permanent = True
    return redirect("/")


@app.route("/chiqish")
def chiqish():
    session.clear()
    return redirect(url_for("kirish_info"))


@app.errorhandler(UzumError)
def _uzum_error(e):
    return render_template("error.html", msg=str(e)), 502


# ======================================================================
# Sahifalar
# ======================================================================
@app.route("/")
def dashboard():
    period = request.args.get("p") or profit.default_period()
    if period not in profit.PERIODS:
        period = profit.default_period()
    r = profit.report(period)
    found = checks.run_all()
    return render_template("dashboard.html", r=r, t=r["totals"], periods=profit.PERIODS,
                           series=profit.series(period), decisions=found[:3], decisions_total=len(found))


@app.route("/qarorlar")
def qarorlar():
    return render_template("qarorlar.html", items=checks.run_all(), names=checks.AGENT_NAMES)


@app.route("/raqobat", methods=["GET", "POST"])
def raqobat():
    if request.method == "POST":
        try:
            sku = request.form.get("my_sku_id")
            if sku and (not sku.isdigit() or int(sku) not in {p["sku_id"] for p in market.my_products()}):
                raise ValueError("Bunday tovar sizda yo'q.")
            market.add(request.form.get("link", ""), my_sku_id=int(sku) if sku else None,
                       title=request.form.get("title"), price=request.form.get("price") or None,
                       stock=request.form.get("stock"))
            flash("Raqobatchi kuzatuvga qo'shildi")
        except (ValueError, market.MarketUnavailable) as e:
            flash(str(e), "error")
        return redirect("/raqobat")
    return render_template("raqobat.html", rows=market.overview(), mine=market.my_products(),
                           live=market.live(), live_msg=market.LIVE_MSG)


@app.route("/raqobat/<int:cid>/narx", methods=["POST"])
def raqobat_narx(cid):
    try:
        if not market.record_price(cid, request.form.get("price") or 0):
            abort(404)
        flash("Narx yangilandi")
    except ValueError as e:
        flash(str(e), "error")
    return redirect("/raqobat")


@app.route("/raqobat/<int:cid>/bogla", methods=["POST"])
def raqobat_bogla(cid):
    sku = request.form.get("my_sku_id")
    if sku and (not sku.isdigit() or int(sku) not in {p["sku_id"] for p in market.my_products()}):
        abort(400)  # faqat o'z tovarim bilan bog'lash mumkin
    if not db.link_competitor(cid, int(sku) if sku else None):
        abort(404)
    flash("Bog'landi")
    return redirect("/raqobat")


@app.route("/raqobat/<int:cid>/ochir", methods=["POST"])
def raqobat_ochir(cid):
    if not db.delete_competitor(cid):
        abort(404)
    flash("Kuzatuvdan olib tashlandi")
    return redirect("/raqobat")


@app.route("/bozor")
def bozor():
    q = (request.args.get("q") or "").strip()[:80]
    a = error = None
    if q:
        try:
            a = market.analyze(q)
            if not a:
                error = "Bu so'z bo'yicha tovar topilmadi."
        except market.MarketUnavailable as e:
            error = str(e)
    return render_template("bozor.html", q=q, a=a, error=error)


@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        try:
            db.set_cost(request.form["sku_id"], float(request.form.get("unit_cost") or 0),
                        float(request.form.get("extra_cost") or 0), request.form.get("title"))
            profit.clear_cache()
            flash("Tannarx saqlandi")
        except (ValueError, KeyError):
            flash("Raqam noto'g'ri kiritildi", "error")
        return redirect("/products")
    profits = {it["sku_id"]: it for it in profit.report("year")["items"] if it["sku_id"]}
    # sotilganlar tepada
    rows = sorted(profit.skus(), key=lambda s: -(profits[s["sku_id"]]["qty"] if s["sku_id"] in profits else 0))
    return render_template("products.html", skus=rows, costs=db.get_costs(), profits=profits)


@app.route("/prices")
def prices():
    hist = [p for p in profit.proposals(limit=50) if p["status"] != "pending"][:20]
    return render_template("prices.html", advice=profit.price_advice(), pending=profit.proposals("pending"),
                           history=hist, tax=profit.tax_rate(), margin=profit.target_margin())


@app.route("/prices/generate", methods=["POST"])
def prices_generate():
    n = profit.create_proposals()
    flash(f"{n} ta narx taklifi tayyorlandi. Ko'rib chiqing va tasdiqlang." if n else "Hamma narxlar joyida — taklif yo'q.")
    return redirect("/prices")


@app.route("/prices/<int:pid>/approve", methods=["POST"])
def prices_approve(pid):
    ok, msg = profit.approve_proposal(pid)
    flash(msg, None if ok else "error")
    return redirect("/prices")


@app.route("/prices/<int:pid>/reject", methods=["POST"])
def prices_reject(pid):
    ok, msg = profit.reject_proposal(pid)
    flash(msg, None if ok else "error")
    return redirect("/prices")


@app.route("/card", methods=["GET", "POST"])
def card():
    if request.method == "POST":
        info = {k: (request.form.get(k) or "").strip() for k in
                ("name", "color", "size", "quantity", "material", "cost", "extra_cost", "notes")}
        photo = request.files.get("photo")
        photo_path = None
        if photo and photo.filename:
            photo_path = ai_card.save_upload(photo.read(), Path(photo.filename).suffix)
        c = ai_card.generate(info, photo_path)
        return redirect(f"/card/{c['id']}")
    return render_template("card_form.html", cards=db.list_cards(12), ai=bool(config.ANTHROPIC_API_KEY))


@app.route("/card/<int:cid>")
def card_view(cid):
    c = db.get_card(cid)
    if not c:
        abort(404)
    return render_template("card_view.html", c=c, res=c["result"],
                           comm=config.DEFAULT_COMMISSION_RATE, logi=config.DEFAULT_LOGISTICS_FEE)


@app.route("/files/<name>")
def files(name):
    if db.card_file_owner(name) != tenant.current_id():  # faqat o'z kartochkasining rasmi
        abort(404)
    for d in (config.OUTPUT_DIR, config.UPLOAD_DIR):
        if (d / name).is_file():
            return send_from_directory(d, name)
    abort(404)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        try:
            db.set_setting("tax_rate", float(request.form["tax"]) / 100)
            db.set_setting("target_margin", float(request.form["margin"]) / 100)
            allowed = {str(s["id"]) for s in profit.client().shops()}
            if request.form.get("shop_id") in allowed:  # faqat o'z kaliti ko'rsatadigan do'kon
                db.set_setting("shop_id", request.form["shop_id"])
            profit.clear_cache()
            flash("Saqlandi")
        except (ValueError, KeyError):
            flash("Qiymat noto'g'ri", "error")
        return redirect("/settings")
    shops = profit._cached("shops", profit.client().shops)
    return render_template("settings.html", tax=profit.tax_rate(), margin=profit.target_margin(),
                           shops=shops, shop=profit.shop(), ai=bool(config.ANTHROPIC_API_KEY),
                           model=config.AI_MODEL, tg=bool(config.TELEGRAM_BOT_TOKEN))


if __name__ == "__main__":
    print(f"\n  Sotuvchi AI paneli: http://{config.WEB_HOST}:{config.WEB_PORT}"
          f"  (ko'p mijozli; sotuvchilar: {len(db.list_sellers())}{', DEMO' if config.DEMO_MODE else ''})\n")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)
