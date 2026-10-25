"""One-off: wire the new view layer (view.js + theme.css) into reports.js and app.js."""
from pathlib import Path
ROOT = Path(".")

# ---------------- reports.js ----------------
p = ROOT / "web/platform/reports.js"; s = p.read_text(encoding="utf-8")

# 1. identityCard + evidenceCard -> the new view layer (all three lenses share it)
a = s.index("  /* property identity: a map pin is never called a parcel."); b = s.index("  function gapsCard(r) {")
s = s[:a] + s[b:]                                   # drop the old identityCard (View.identity replaces it)
a = s.index("  function evidenceCard(r, S) {"); b = s.index("\n\n  /* ---------- evidence-driven due-diligence checklist")
s = s[:a] + "  function evidenceCard(r, S) { return r.ev ? View.identity(r, S) + View.shortVersion(r, S) + View.topics(r, S) : ''; }" + s[b:]

# 2. the old customer view becomes a parts provider; the new customer view is composed from the view layer
old_head = "  function customer(S) {\n    const r = S.r, w = r.tiers.water,"
assert s.count(old_head) == 1
s = s.replace(old_head, "  function customerParts(S) {\n    const r = S.r, w = r.tiers.water,")
a = s.index("    return `<div class=\"printonly\"><b>SETHU — Customer report</b>"); b = s.index("  /* ============================== REAL ESTATE AGENT")
s = s[:a] + "    return { cost, detail };\n  }\n  function aboutCard(r) {\n    const g = (r.ev && r.ev.gaps) || [];\n    return `<section class=\"v-card v-about\"><div class=\"v-eyebrow\">About this check</div><h2>How to read it, and what it cannot tell you</h2>\n      <ul class=\"v-ul\"><li><b>Needs attention / look into / looks fine / couldn't check.</b> Every finding carries one of these four words and an icon. There is deliberately no single score: a serious flag is never averaged away by good amenities.</li>\n        <li><b>\"Couldn't check\" means verify, not unsafe.</b> It means no public data answered the question.</li>\n        <li><b>Public map data only.</b> Outlines are drawn, not legal boundaries. SETHU cannot see title, ownership, loans, court cases or what a seller has not shown you.</li>\n        <li><b>How local is each result?</b> Every finding says whether it applies to the pin, a nearby area, the whole ward or the whole city.</li></ul>\n      ${g.length ? `<details class=\"more v-more\" data-id=\"gaps_all\"><summary>Everything we couldn't check, and why (${g.length})</summary>${g.map(x => `<div class=\"v-gap\"><b>${esc(x.label)}</b><i>${esc(x.section)}</i><span>${esc(x.why)}</span></div>`).join('')}</details>` : ''}\n      <p class=\"v-small\">Where each number comes from, how recent it is and how far it was checked: <a href=\"quality.html\" target=\"_blank\" rel=\"noopener\">data quality dashboard</a>. Generated ${new Date().toLocaleString('en-IN')}. Not legal, valuation or insurance advice.</p>\n      <div class=\"noprint\"><button class=\"v-btn ghost\" data-act=\"print\">Print or save as PDF</button></div></section>`;\n  }\n  function customer(S) {\n    const r = S.r, P = customerParts(S);\n    return `<div class=\"printonly\"><b>SETHU — Buyer check</b> · ${esc(S.label || r.ward.name)} · ${new Date().toLocaleDateString('en-IN')}</div>\n      <div class=\"v-page\">${View.identity(r, S)}${View.shortVersion(r, S)}${View.beforePay(r, S)}${View.topics(r, S)}\n        <details class=\"more v-topic t-mute\" data-id=\"tp_costs\"${S.open && S.open.tp_costs ? ' open' : ''}><summary><span class=\"v-ticon\" aria-hidden=\"true\">₹</span><span class=\"v-tt\"><b>What it will really cost</b><small>Duties and brokerage on your quoted price, and a check against typical asking prices.</small></span><span class=\"v-tr\"></span></summary><div class=\"v-tbody\">${P.cost}</div></details>\n        <details class=\"more v-topic t-mute\" data-id=\"tp_more\"${S.open && S.open.tp_more ? ' open' : ''}><summary><span class=\"v-ticon\" aria-hidden=\"true\">📊</span><span class=\"v-tt\"><b>Charts and official records</b><small>Rain-versus-water curve, official drainage and tank records, routes, every facility, insurance angle.</small></span><span class=\"v-tr\"></span></summary><div class=\"v-tbody\">${P.detail}</div></details>\n        ${aboutCard(r)}</div>`;\n  }\n\n" + s[b:]

# the old customer summary built a 'free' / 'hero' that are no longer shown; keep the function body but it is cheap
p.write_text(s, encoding="utf-8")

# ---------------- app.js ----------------
p = ROOT / "web/platform/app.js"; s = p.read_text(encoding="utf-8")
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]; s = s.replace(old, new)

# dock
a = s.index("function renderDock() {"); b = s.index("function renderReport() {")
s = s[:a] + """function renderDock() {
  const d = $('dock'), r = S.r;
  if (!r) { d.innerHTML = View.landing(S); return; }
  if (!r.ok) { d.innerHTML = `<div class="v-panel"><h1 class="v-h1">Outside our <em>coverage</em></h1><p class="v-lead">SETHU covers Hyderabad. Pick a point on the map, or search a Hyderabad locality.</p><button class="v-btn" data-act="clear">Back</button></div>`; return; }
  d.innerHTML = View.dock(S);
}
""" + s[b:]

# report header
a = s.index("function renderReport() {"); b = s.index("function renderCompare() {")
s = s[:a] + """const VIEW_TABS = [['customer', 'Buyer check'], ['agent', 'For agents'], ['insurer', 'For insurers']];
function renderReport() {
  const v = $('report'), r = S.r; if (!r || !r.ok) return;
  const sc = v.scrollTop;
  const title = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name;
  v.innerHTML = `<div class="v-rhead"><div class="v-rin"><button class="v-btn ghost sm v-back" data-act="back">← Map</button>
    <div><h1>${esc(title)}</h1><div class="v-loc">${esc(r.ward.name)} · ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div></div>
    <div class="v-rtools noprint"><button class="v-btn ghost sm" data-act="cmp-start">⇄ Compare</button><button class="v-btn ghost sm" data-act="print">Print / PDF</button><button class="v-btn ghost sm" data-act="share">Copy link</button></div>
    <div class="v-views noprint" role="tablist">${VIEW_TABS.map(([l, n]) => `<button role="tab" aria-selected="${S.lens === l}" data-act="tab" data-lens="${l}" class="${S.lens === l ? 'on' : ''}">${n}</button>`).join('')}</div></div></div>
    <div class="rbody${S.lens === 'customer' ? '' : ' wide'}">${Reports.render(S.lens, S)}</div>`;
  v.scrollTop = sc;
}
""" + s[b:]
rep("  v.innerHTML = `<div class=\"rhead\"><div class=\"rin\"><button class=\"btn ghost sm back\" data-act=\"back\">← Map</button>\n    <div><h1>Compare two addresses</h1><div class=\"loc\">${esc(S.cmp.la || S.cmp.a.ward.name)} vs ${esc(S.cmp.lb || S.cmp.b.ward.name)}</div></div>\n    <button class=\"btn ghost sm noprint\" data-act=\"print\">🖨 PDF</button><button class=\"btn ghost sm noprint\" data-act=\"share\">🔗 Share</button></div></div>\n    <div class=\"rbody\">${Reports.compare(S)}</div>`;",
    "  v.innerHTML = `<div class=\"v-rhead\"><div class=\"v-rin\"><button class=\"v-btn ghost sm v-back\" data-act=\"back\">← Map</button>\n    <div><h1>Compare two addresses</h1><div class=\"v-loc\">${esc(S.cmp.la || S.cmp.a.ward.name)} vs ${esc(S.cmp.lb || S.cmp.b.ward.name)}</div></div>\n    <div class=\"v-rtools noprint\"><button class=\"v-btn ghost sm\" data-act=\"print\">Print / PDF</button><button class=\"v-btn ghost sm\" data-act=\"share\">Copy link</button></div></div></div>\n    <div class=\"rbody wide\">${Reports.compare(S)}</div>`;")

# jump to a finding from the short version
rep("  else if (a === 'parcel-match') applyRef();",
    """  else if (a === 'jump') {
    const id = t.dataset.id, el = document.getElementById('f_' + id); if (!el) return;
    const tp = el.closest('details.v-topic'); if (tp && !tp.open) { tp.open = true; S.open[tp.dataset.id] = true; }
    const fd = el.querySelector('details.v-fd'); if (fd) { fd.open = true; S.open['fd_' + id] = true; }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1800);
  }
  else if (a === 'open-topic') { const e = document.querySelector('.v-topics'); if (e) e.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  else if (a === 'parcel-match') applyRef();""")
rep("  $('dock').innerHTML = '<div class=\"panel intro\"><p><span class=\"spin\"></span> &nbsp;Loading the SETHU engine…</p></div>';", "  $('dock').innerHTML = '<div class=\"v-panel\"><p class=\"v-lead\"><span class=\"spin\"></span> &nbsp;Loading the SETHU engine…</p></div>';")
rep("Could not load data files. Serve the site from the <code>web/</code> folder.</p></div>';", "Could not load data files. Serve the site from the <code>web/</code> folder.</p></div>';")
p.write_text(s, encoding="utf-8")

# ---------------- view.js small fixes ----------------
p = ROOT / "web/platform/view.js"; s = p.read_text(encoding="utf-8")
s = s.replace("${S.places.slice(0, 6).map(", "${PLACES.slice(0, 6).map(")
s = s.replace("${stat('73', 'checks per address')}", "${stat(String(Object.keys((SETUE.D.quality || { factors: {} }).factors).length || '70'), 'checks per address')}")
p.write_text(s, encoding="utf-8")

# ---------------- engine export + theme additions ----------------
p = ROOT / "web/platform/engine.js"; s = p.read_text(encoding="utf-8")
assert s.count("return { load, report, evidence, checklist,") == 1
s = s.replace("return { load, report, evidence, checklist,", "return { load, report, evidence, checklist, HIGH,")
p.write_text(s, encoding="utf-8")
p = ROOT / "web/platform/theme.css"; s = p.read_text(encoding="utf-8")
s += """
.panel{background:#fff;color:var(--text);border-color:var(--line);box-shadow:var(--shadow)}
.v-f{transition:background .3s}.v-f.flash{background:var(--infobg);border-radius:10px}
.v-ul{margin:8px 0 12px 20px;display:grid;gap:8px;font-size:15.5px;line-height:1.5;color:var(--text2)}.v-ul b{color:var(--text)}
.v-gap{padding:8px 0;border-bottom:1px solid var(--line);font-size:14.5px;display:flex;flex-direction:column;gap:2px}.v-gap i{font-style:normal;color:var(--muted);font-size:12.5px}.v-gap span{color:var(--text2)}
.v-about .v-more{margin:8px 0}
"""
p.write_text(s, encoding="utf-8")
print("overhaul wired")
