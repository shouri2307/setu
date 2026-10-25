"""Brief flow: the side panel stays light; "View report" opens the summary page; the full report is one more tap below it."""
from pathlib import Path
p = Path("web/platform/brief.js"); s = p.read_text(encoding="utf-8")
a = s.index("  function dock(S) {"); b = s.index("  /* ---------- before any place is picked")
new = r"""  /* ---------- the report page: the summary first, the full report one tap below ---------- */
  function page(S) {
    const r = S.r, P = persona(S), ctx = state(r, S);
    S.loadingIds = ctx.loading;
    const tiles = P.tiles.map(id => tileData(id, r, S, ctx)), idl = View.idLine(r), allWhy = !!(S.open && S.open.b_allwhy), full = !!(S.open && S.open.fullreport);
    return `<div class="b-page"><details class="b-id t-${idl.tone}" data-id="b_id"${S.open && S.open.b_id ? ' open' : ''}><summary><span class="v-ic">${idl.glyph}</span><span>${esc(idl.text)}</span><em>Match my survey number</em></summary>${View.identity(r, S)}</details>
      ${headline(P, tiles, S)}
      <div class="b-bar"><span>Tap a topic to see what is behind it</span><button type="button" class="b-toggle${allWhy ? ' on' : ''}" data-act="b-why" aria-pressed="${allWhy}">${allWhy ? 'Hide' : 'Show'} the reasoning</button></div>
      <div class="b-grid">${tiles.map(t => tile(t, S)).join('')}</div>
      ${todo(r, S)}
      ${full ? `<section class="b-full" id="fullreport" aria-label="Full report"><div class="b-fullh"><div><div class="v-eyebrow">Full report</div><h2>Every check, with its evidence</h2></div><button type="button" class="v-btn ghost sm" data-act="full">Hide the full report ↑</button></div>${Reports.render(P.lens, S)}</section>`
        : `<section class="b-fullcta"><button type="button" class="v-btn big" data-act="full">View the full report ↓</button><p class="v-small">Every check with its source, plus charts, official records and the cost calculator.</p></section>`}
      ${SURE}<p class="v-small">Built from public map data. Not legal, valuation or insurance advice.</p></div>`;
  }

  /* ---------- the card beside the map: just the place, and who is asking ---------- */
  function dock(S) {
    const r = S.r, P = persona(S), title = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name, idl = View.idLine(r);
    return `<div class="v-panel scroll b-dock"><div class="v-eyebrow">Selected place</div><h2 class="v-dh">${esc(title)}</h2><div class="v-sub">${esc(r.ward.name)}${S.address ? ' · ' + esc(S.address) : ''}${r.outside ? ' · outside the 145 wards' : ''}</div>
      <div class="v-idchip t-${idl.tone}"><span class="v-ic">${idl.glyph}</span>${esc(idl.text)}</div>
      <div class="v-eyebrow b-iam">I am a…</div>${who(S)}
      <button class="v-btn big" data-act="open" data-lens="${S.persona}">View report →</button>
      ${S.cmpPending ? `<div class="v-wait"><b>Pick the second address.</b> Search above or click the map to compare it with ${esc(title)}. <button class="v-btn ghost sm" data-act="cmp-cancel">Cancel</button></div>` : `<div class="b-links"><button class="v-link" data-act="cmp-start">⇄ Compare with another address</button></div>`}
      <p class="v-small">${esc(P.ask)} Built from public map data. Not legal, valuation or insurance advice.</p></div>`;
  }

"""
s = s[:a] + new + s[b:]
s = s.replace("return { dock, landing, PERSONAS, TILES, DEFAULT_P, tileData, verdict, headline, state, who, showLayers };", "return { dock, page, landing, PERSONAS, TILES, DEFAULT_P, tileData, verdict, headline, state, who };")
# the report page covers the map, so opening a topic no longer switches map layers
a = s.index("  /* open a topic from the headline, and show its map layers"); b = s.index("  return { dock, page")
s = s[:a] + s[b:]
p.write_text(s, encoding="utf-8")

# ---- app.js ----
a_ = Path("web/platform/app.js"); t = a_.read_text(encoding="utf-8")
def rep(old, new):
    global t
    assert t.count(old) == 1, old[:70]; t = t.replace(old, new)
rep("""  else if (a === 'persona') { S.persona = Brief.PERSONAS[t.dataset.p] ? t.dataset.p : Brief.DEFAULT_P; try { localStorage.setItem('sethu.persona', S.persona); } catch (x) { } renderDock(); }
  else if (a === 'b-open') { const d = document.querySelector(`details.b-tile[data-tile="${t.dataset.tile}"]`); if (d) { d.open = true; S.open[d.dataset.id] = true; Brief.showLayers(d.dataset.tile); d.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } }
  else if (a === 'b-why') { S.open.b_allwhy = !S.open.b_allwhy; renderDock(); }""",
"""  else if (a === 'persona') { setPersona(t.dataset.p); }
  else if (a === 'b-open') { const d = document.querySelector(`details.b-tile[data-tile="${t.dataset.tile}"]`); if (d) { d.open = true; S.open[d.dataset.id] = true; d.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }
  else if (a === 'b-why') { S.open.b_allwhy = !S.open.b_allwhy; renderReport(); }
  else if (a === 'full') { S.open.fullreport = !S.open.fullreport; renderReport(); if (S.open.fullreport) { const e = document.getElementById('fullreport'); if (e) e.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }
  else if (a === 'open-full') { setPersona(t.dataset.p, true); S.open.fullreport = true; renderReport(); const e = document.getElementById('fullreport'); if (e) e.scrollIntoView({ behavior: 'smooth', block: 'start' }); }""")
rep("""if (d.open && d.matches('details.b-tile') && !S._lay.has(d.dataset.tile)) { S._lay.add(d.dataset.tile); Brief.showLayers(d.dataset.tile); } } }, true);""", """} }, true);""")
rep("""const loadPersona = () =>""", """const LENS_PERSONA = { customer: 'buyer', agent: 'agent', insurer: 'insurer' };   // old links said customer / agent / insurer
function setPersona(p, keepView) { S.persona = Brief.PERSONAS[p] ? p : Brief.DEFAULT_P; S.lens = Brief.PERSONAS[S.persona].lens; try { localStorage.setItem('sethu.persona', S.persona); } catch (x) { } if (S.view === 'report') { renderReport(); syncHash(); } else if (!keepView) renderDock(); }
const loadPersona = () =>""")
rep("""const VIEW_TABS = [['customer', 'Buyer check'], ['agent', 'For agents'], ['insurer', 'For insurers']];\n""", "")
rep("""    <div class="v-views noprint" role="tablist">${VIEW_TABS.map(([l, n]) => `<button role="tab" aria-selected="${S.lens === l}" data-act="tab" data-lens="${l}" class="${S.lens === l ? 'on' : ''}">${n}</button>`).join('')}</div></div></div>
    <div class="rbody${S.lens === 'customer' ? '' : ' wide'}">${Reports.render(S.lens, S)}</div>`;""",
"""    <div class="v-views noprint">${Brief.who(S)}</div></div></div>
    <div class="rbody${S.open.fullreport && S.lens !== 'customer' ? ' wide' : ''}">${Brief.page(S)}</div>`;""")
rep("""function openReport(lens) {
  if (!S.r || !S.r.ok) return;
  S.lens = lens; S.view = 'report';""", """function openReport(who) {
  if (!S.r || !S.r.ok) return;
  S.persona = Brief.PERSONAS[who] ? who : (LENS_PERSONA[who] || S.persona); S.lens = Brief.PERSONAS[S.persona].lens; S.view = 'report';""")
rep("""`#/r/${S.lens}/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}`""", """`#/r/${S.persona}/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}`""")
rep("""if ((m = h.match(/^#\\/r\\/(customer|agent|insurer)\\/(-?[\\d.]+),(-?[\\d.]+)/))) {
    S.lens = m[1]; const lat = +m[2], lon = +m[3];
    if (!S.r || Math.abs(S.r.lat - lat) > 1e-5 || Math.abs(S.r.lon - lon) > 1e-5) await setPin(lat, lon, '', { keepView: true });
    if (S.r && S.r.ok) openReport(S.lens);""", """if ((m = h.match(/^#\\/r\\/(customer|agent|insurer|buyer|renter|investor|lender)\\/(-?[\\d.]+),(-?[\\d.]+)/))) {
    const lat = +m[2], lon = +m[3];
    if (!S.r || Math.abs(S.r.lat - lat) > 1e-5 || Math.abs(S.r.lon - lon) > 1e-5) await setPin(lat, lon, '', { keepView: true });
    if (S.r && S.r.ok) openReport(m[1]);""")
rep("""  else if (a === 'print') window.print();""", """  else if (a === 'print') { if (S.view === 'report' && !S.open.fullreport) { S.open.fullreport = true; renderReport(); } window.print(); }""")
rep("""MapKit.setPin(S.r.lat, S.r.lon, S.r.outside ? null : S.r.wid, false); openReport('customer'); } }""", """MapKit.setPin(S.r.lat, S.r.lon, S.r.outside ? null : S.r.wid, false); openReport(S.persona); } }""")
a_.write_text(t, encoding="utf-8")
print("flow patched")
