"""
Veb-panel (Flask). Ishga tushirish:  py web.py   →  brauzerda http://127.0.0.1:5000
"""
import functools
import logging
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from jinja2 import DictLoader

import ai_card
import config
import db
import profit
from uzum_client import UzumError, client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
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
<nav>{% for href, name in [("/","Bosh sahifa"),("/products","Tovarlar"),("/prices","Narxlar"),("/card","AI kartochka"),("/settings","Sozlamalar")] %}
<a href="{{href}}" class="{{'on' if active==href}}">{{name}}</a>{% endfor %}</nav></header>
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
</table><p class="small muted">Kalitlar faqat loyiha papkasidagi <code>.env</code> faylida saqlanadi. O'zgartirgandan keyin dasturni qayta ishga tushiring.</p></div></div>
{% endblock %}"""

LOGIN = r"""{% extends "base.html" %}{% block body %}<form class="card" method="post" style="max-width:360px;margin:60px auto">
<h1>Kirish</h1><p class="sub">Panel paroli</p><input type="password" name="password" autofocus><p><button class="btn">Kirish</button></p></form>{% endblock %}"""

ERROR = r"""{% extends "base.html" %}{% block body %}<div class="card"><h1>Xatolik</h1><p>{{ msg }}</p><p class="muted small">Uzum tokenini va internetni tekshiring. Muammo davom etsa, <code>.env</code> faylida <code>DEMO_MODE=1</code> qilib demo rejimda ishlating.</p></div>{% endblock %}"""

app.jinja_loader = DictLoader({
    "base.html": BASE, "dashboard.html": DASHBOARD, "products.html": PRODUCTS, "prices.html": PRICES,
    "card_form.html": CARD_FORM, "card_view.html": CARD_VIEW, "settings.html": SETTINGS,
    "login.html": LOGIN, "error.html": ERROR,
})
app.jinja_env.filters["basename"] = lambda p: Path(p or "").name


@app.context_processor
def _ctx():
    return {"f": profit.fmt, "demo": client.demo, "active": "/" + request.path.strip("/").split("/")[0],
            "est_costs": db.get_setting("costs_estimated") == "1"}


# ======================================================================
# Kirish (ixtiyoriy parol)
# ======================================================================
@app.before_request
def _auth():
    if not config.WEB_PASSWORD or request.endpoint in ("login", "static"):
        return None
    if not session.get("ok"):
        return redirect(url_for("login"))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == config.WEB_PASSWORD:
            session["ok"] = True
            return redirect("/")
        flash("Parol noto'g'ri", "error")
    return render_template("login.html")


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
    return render_template("dashboard.html", r=r, t=r["totals"], periods=profit.PERIODS,
                           series=profit.series(period))


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
            if request.form.get("shop_id"):
                db.set_setting("shop_id", request.form["shop_id"])
            profit.clear_cache()
            flash("Saqlandi")
        except (ValueError, KeyError):
            flash("Qiymat noto'g'ri", "error")
        return redirect("/settings")
    shops = profit._cached("shops", client.shops)
    return render_template("settings.html", tax=profit.tax_rate(), margin=profit.target_margin(),
                           shops=shops, shop=profit.shop(), ai=bool(config.ANTHROPIC_API_KEY),
                           model=config.AI_MODEL, tg=bool(config.TELEGRAM_BOT_TOKEN))


if __name__ == "__main__":
    print(f"\n  Sotuvchi AI paneli: http://{config.WEB_HOST}:{config.WEB_PORT}"
          f"  ({'DEMO rejim' if client.demo else 'haqiqiy do`kon'})\n")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)
