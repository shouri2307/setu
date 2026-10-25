"""One-off patch (batch 2 UI): evidence map layers with source popups (map.js), checklist card (reports.js), handlers (app.js), chips and legend (index.html), styles."""

def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, f"{path}: missing {old[:80]!r}"
        s = s.replace(old, new, 1)
    open(path, "w", encoding="utf-8").write(s)

# ------------------------------------------------------------------ map.js
EV = r'''
  /* ---------------- evidence layers: every feature opens a popup with source, period, resolution and confidence ---------------- */
  const escH = v => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const evPop = o => `<div class="evpop"><b>${escH(o.title)}</b><div class="v">${escH(o.value)}</div>${(o.rows || []).filter(r => r[1] != null && r[1] !== '').map(r => `<div class="r"><span>${escH(r[0])}</span><span>${escH(r[1])}</span></div>`).join('')}` +
    `<div class="m"><div><b>Source</b> ${escH(o.source)}</div><div><b>Data period</b> ${escH(o.period)}</div><div><b>Resolution</b> ${escH(o.res)}</div><div><b>Confidence</b> ${escH(o.conf)}</div>${o.caveat ? `<div class="cv">${escH(o.caveat)}</div>` : ''}</div></div>`;
  const REC_COL = { NIL: '#7f1d1d', POOR: '#f97316', LIMITED: '#eab308', MODERATE: '#84cc16', GOOD: '#22c55e' };
  const recKey = a => { const v = String((a && a[5]) || '').toUpperCase(); return Object.keys(REC_COL).find(k => v.indexOf(k) === 0) || null; };
  const depthCol = d => d == null ? '#64748b' : d < 5 ? '#38bdf8' : d < 10 ? '#22c55e' : d < 20 ? '#eab308' : '#ef4444';
  const TKCOL = { L: '#22c55e', P: '#f97316', T: '#ef4444', D: '#94a3b8' }, TKLAB = { L: 'live', P: 'partially encroached', T: 'totally encroached', D: 'dead (no storage)' };
  const GWPF = ['geom', 'landform', 'rock', 'depth_to_water', 'wells_observed', 'recharge', 'aquifer', 'well_type', 'well_depth', 'yield', 'success', 'water_quality', 'recharge_structures', 'remarks'];
  const mons = (a, n = 4) => a && a.length ? (a.length > n ? a.slice(0, n).join(', ') + ' and ' + (a.length - n) + ' more' : a.join(', ')) : 'n/a';
  // pure: the popup content for one feature of one layer (also used by the tests)
  function popupFor(kind, f, D) {
    const lm = (D && D.land && D.land.meta) || {};
    if (kind === 'ev_wells') return evPop({ title: `Groundwater well · ${f.village || 'unnamed'}${f.mandal ? ', ' + f.mandal : ''}`, value: `${f.latest != null ? f.latest.toFixed(1) : 'n/a'} m below ground in ${f.month || 'latest month'}`,
      rows: [['Dry season (Apr-May mean)', f.pre != null ? f.pre.toFixed(1) + ' m' : null], ['After monsoon (Oct-Nov mean)', f.post != null ? f.post.toFixed(1) + ' m' : null], ['Rebound', f.rec != null ? (f.rec >= 0 ? '+' : '') + f.rec.toFixed(1) + ' m' : null], ['Trend 2021-25', f.trend != null ? (f.trend >= 0 ? '+' : '') + f.trend.toFixed(2) + ' m/yr (positive = falling)' : 'not enough years']],
      source: 'Telangana Ground Water Department monthly piezometer readings (Open Data Telangana)', period: `${f.y0}-${f.y1}, ${f.months} monthly readings, latest ${f.month}`, res: 'one well', conf: 'medium for this well; nearby wells can differ by metres', caveat: 'Depth is metres below ground level: larger means deeper and worse. A neighbouring well is not your borewell.' });
    if (kind === 'ev_gwp') { const a = f.attrs || [], g = Object.fromEntries(GWPF.map((k, i) => [k, a[i]]));
      return evPop({ title: `Hydrogeology unit · ${(g.landform || 'landform n/a').replace(/\s*\(.*\)/, '')}`, value: `${g.recharge ? String(g.recharge).toLowerCase() + ' recharge' : 'recharge not stated'} · ${(g.rock || 'rock n/a').replace(/\s*\(\d+\)/, '').toLowerCase()}`,
        rows: [['Depth to water level', g.depth_to_water], ['Suggested well depth', g.well_depth], ['Typical yield', g.yield], ['Success rate', g.success], ['Water quality', g.water_quality], ['Remarks', g.remarks]],
        source: 'Telangana State GIS groundwater-potential (hydro-geomorphological) map', period: 'undated regional survey', res: 'map unit, about 1:50,000', conf: 'low', caveat: 'Describes what wells usually yield in this kind of ground. It is not a promise for any one plot.' }); }
    if (kind === 'ev_hv') return f.sub
      ? evPop({ title: `Substation · ${f.sub.name}`, value: f.sub.volt || 'voltage n/a', source: 'Telangana State GIS substations (TCUR layer)', period: 'undated', res: 'point', conf: 'medium', caveat: 'A nearby substation can mean a robust supply but also noise and hum.' })
      : evPop({ title: `High-voltage line · ${f.line.name || 'unnamed'}`, value: f.line.kv ? f.line.kv + ' kV' : 'voltage n/a', rows: [['Length (km)', f.line.len]], source: 'Telangana State GIS electric transmission layer (TCUR)', period: 'undated', res: 'line, positional accuracy not published', conf: 'medium', caveat: 'Proximity to a line does not by itself mean a no-build corridor applies.' });
    if (kind === 'ev_lost') return evPop({ title: 'Water body recorded as disappeared', value: f.a && f.a[1] != null ? Number(f.a[1]).toFixed(1) + ' ha mapped extent' : 'size n/a', rows: [['Type', f.a && f.a[0]]],
      source: 'HMDA / TGRAC water-body assessment, "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon', conf: 'medium', caveat: 'A map record of a tank that no longer exists on the ground. It is not a legal finding and does not itself prove encroachment or a restriction.' });
    if (kind === 'ev_streams') return evPop({ title: `Natural stream · ${f.n || 'unnamed'}`, value: `stream order ${f.o != null ? f.o : '?'} (higher = larger catchment)`,
      source: 'Telangana State GIS stream-order layer (terrain-derived network)', period: 'undated', res: 'line, positional accuracy not published', conf: 'low', caveat: 'Shows where the terrain model puts a natural channel. It does not prove an open or buried channel crosses a plot, or that a plot floods.' });
    if (kind === 'ev_tankcap') { const a = f.a || [];
      return evPop({ title: `Tank · ${a[0] || 'unnamed'}${a[9] ? ', ' + a[9] : ''}`, value: `2023 status: ${TKLAB[a[5]] || 'not classified'} (2011: ${TKLAB[a[4]] || 'not classified'})`,
        rows: [['Mapped area', a[1] != null ? (a[1] / 1e4).toFixed(1) + ' ha' : null], ['Bund height', a[2] != null ? a[2] + ' m' : null], ['Estimated design capacity', a[3] != null ? (a[3] / 1e6).toFixed(2) + ' million m³ (area × bund height ÷ 2)' : 'not available: no bund height in the source'], ['Mapped from', a[6]], ['Origin period', a[7]], ['Type', a[8]]],
        source: 'TGRAC / HMDA water-body layer (HMDA-ORR-GHMC)', period: 'extent from topo sheet or revenue map; status classes 2011 and 2023', res: 'polygon', conf: 'low', caveat: 'The outline is a mapped extent, not a legal boundary, and the status is a satellite classification, not verified encroachment. Capacity is the source\'s estimate, not measured storage.' }); }
    if (kind === 'ev_tankhy') return evPop({ title: `Tank · ${f.name || 'unnamed'}${f.village ? ', ' + f.village : ''}`, value: `satellite status 2023: ${HYLAB[f.s23] || 'not classified'} (2014: ${HYLAB[f.s14] || 'not classified'})`,
      source: 'TGRAC / HYDRAA water-body assessment', period: 'imagery 2014 and 2023', res: 'polygon', conf: 'medium', caveat: 'A satellite classification, not a legal notification or a verified encroachment finding.' });
    if (kind === 'ev_heat') return evPop({ title: 'Dry-season surface heat', value: `${f.lst.toFixed(1)} °C land-surface · NDVI ${f.ndvi != null ? f.ndvi.toFixed(2) : 'n/a'}`, rows: [['Hotter than', f.pct != null ? Math.round(f.pct * 100) + '% of the city' : null]],
      source: 'Landsat 8/9 Collection 2 Level-2 (USGS) via Microsoft Planetary Computer', period: `${(D && D.heat && D.heat.meta && D.heat.meta.window) || 'Mar-May 2024-26'}, ${(D && D.heat && D.heat.meta && D.heat.meta.scenes) || '?'} scenes`, res: '150 m cell (30 m source)', conf: 'medium', caveat: 'Surface temperature of roofs, roads and soil, not the air temperature a resident feels.' });
    return '';
  }
  const EVINFO = {
    ev_wells: D => ({ title: 'Groundwater wells', swatch: [['#38bdf8', '< 5 m'], ['#22c55e', '5-10 m'], ['#eab308', '10-20 m'], ['#ef4444', '> 20 m']], unit: 'depth below ground, latest month', note: `Ground Water Dept monthly readings, latest ${((D.gwSt || []).reduce((m, x) => x.month > m ? x.month : m, '')) || 'n/a'}. One well ≠ your borewell.` }),
    ev_gwp: D => ({ title: 'Groundwater potential zones', swatch: [['#7f1d1d', 'nil'], ['#f97316', 'poor'], ['#eab308', 'limited'], ['#84cc16', 'moderate'], ['#22c55e', 'good'], ['#64748b', 'not stated']], unit: 'recharge condition', note: 'Regional hydrogeology map, undated, about 1:50,000. Low confidence at plot level.' }),
    ev_heat: D => ({ title: 'Dry-season surface heat', swatch: [['rgb(49,130,189)', 'cooler'], ['rgb(250,220,90)', 'median'], ['rgb(215,48,39)', 'hotter']], unit: 'land-surface temperature', note: `Landsat ${D.heat && D.heat.meta ? D.heat.meta.scenes : '?'} clear scenes, Mar-May 2024-26. Click for the value.` }),
    ev_hv: D => ({ title: 'High-voltage lines and substations', swatch: [['#f43f5e', 'transmission line'], ['#fb923c', 'substation']], unit: '', note: 'State GIS (TCUR layer), undated. Proximity is not a legal corridor.' }),
    ev_lost: D => ({ title: 'Water bodies recorded as disappeared', swatch: [['#ef4444', 'recorded as disappeared']], unit: '', note: 'HMDA / TGRAC map record, undated. Not a legal finding.' }),
    ev_streams: D => ({ title: 'Natural streams (order)', swatch: [['#93c5fd', 'order 2'], ['#3b82f6', 'order 4'], ['#1d4ed8', 'order 6']], unit: 'line weight rises with order', note: 'Terrain-derived network, undated. Does not prove a buried channel.' }),
    ev_tankcap: D => ({ title: 'Tanks: 2023 status and design capacity', swatch: [['#22c55e', 'live'], ['#f97316', 'partially encroached'], ['#ef4444', 'totally encroached'], ['#94a3b8', 'dead (no storage)']], unit: 'satellite class; capacity is an estimate', note: 'TGRAC / HMDA layer, status 2011 and 2023. Classification, not verified encroachment.' })
  };
'''
patch("web/platform/map.js", [
    # helpers before the Leaflet engine
    ("  /* ---------------- Leaflet ---------------- */", EV + "\n  /* ---------------- Leaflet ---------------- */"),
    # leaflet engine: layers
    ("    let pin = null, ring = null, sel = null; const poi = {}, govL = {};\n    return {\n      setPin(lat, lon, wid, fly) {\n        if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring);\n        pin = L.marker(",
     """    let pin = null, ring = null, sel = null; const poi = {}, govL = {}, evL = {};
    const heatLookup = (D, lat, lon) => { const h = D.heat; if (!h || !h.lst) return null; const m = h.meta, i = Math.floor((lon - m.bbox[0]) / m.cell_deg), j = Math.floor((m.bbox[3] - lat) / m.cell_deg); if (i < 0 || j < 0 || i >= m.nx || j >= m.ny) return null; const v = h.lst[j * m.nx + i]; if (v == null) return null; const n = h.ndvi[j * m.nx + i]; const below = D.heatSorted ? D.heatSorted.filter(x => x <= v).length / D.heatSorted.length : null; return { lst: v / 10, ndvi: n == null ? null : n / 100, pct: below }; };
    const heatCanvas = D => { const h = D.heat, m = h.meta, c = document.createElement('canvas'); c.width = m.nx; c.height = m.ny; const x = c.getContext('2d'), im = x.createImageData(m.nx, m.ny); const s = D.heatSorted, lo = s[Math.floor(s.length * .02)], hi = s[Math.floor(s.length * .98)], mid = s[s.length >> 1];
      const col = v => { const t = v <= mid ? (v - lo) / Math.max(1, mid - lo) : 1 + (v - mid) / Math.max(1, hi - mid); const k = Math.max(0, Math.min(2, t)); const A = [49, 130, 189], B = [250, 220, 90], C = [215, 48, 39]; return k < 1 ? A.map((a, i) => a + (B[i] - a) * k) : B.map((b, i) => b + (C[i] - b) * (k - 1)); };
      for (let i = 0; i < h.lst.length; i++) { const v = h.lst[i]; if (v == null) { im.data[i * 4 + 3] = 0; continue; } const c3 = col(v); im.data[i * 4] = c3[0]; im.data[i * 4 + 1] = c3[1]; im.data[i * 4 + 2] = c3[2]; im.data[i * 4 + 3] = 150; }
      x.putImageData(im, 0, 0); return c.toDataURL(); };
    map.on('click', e => { if (evL.ev_heat && cfg.D) { const f = heatLookup(cfg.D, e.latlng.lat, e.latlng.lng); if (f) L.popup({ maxWidth: 300 }).setLatLng(e.latlng).setContent(popupFor('ev_heat', f, cfg.D)).openOn(map); } });
    return {
      showEv(kind, on) {
        if (evL[kind]) { map.removeLayer(evL[kind]); evL[kind] = null; }
        if (!on || !cfg.D) return;
        const D = cfg.D, g = L.layerGroup(), pop = (layer, html) => layer.bindPopup(html, { maxWidth: 300 });
        if (kind === 'ev_wells') for (const w of D.gwSt || []) pop(L.circleMarker([w.lat, w.lon], { radius: 5, color: '#fff', weight: 1, fillColor: depthCol(w.latest), fillOpacity: .95 }), popupFor(kind, w, D)).addTo(g);
        if (kind === 'ev_gwp') for (const u of (D.landL && D.landL.gwp) || []) { const a = (D.land.gwp_attrs || [])[u.i] || [], c = REC_COL[recKey(a)] || '#64748b'; for (const r of u.r) pop(L.polygon(r, { color: c, weight: .6, fillColor: c, fillOpacity: .38 }), popupFor(kind, { attrs: a }, D)).addTo(g); }
        if (kind === 'ev_hv') { for (const t of (D.landL && D.landL.tx) || []) for (const p of t.p) pop(L.polyline(p, { color: '#f43f5e', weight: 2.5, opacity: .9 }), popupFor(kind, { line: { name: t.a[0], kv: t.a[3], len: t.a[4] } }, D)).addTo(g); for (const q of (D.landL && D.landL.sub) || []) pop(L.circleMarker(q.ll, { radius: 7, color: '#fff', weight: 1.5, fillColor: '#fb923c', fillOpacity: 1 }), popupFor(kind, { sub: { name: q.a[0], volt: q.a[1] } }, D)).addTo(g); }
        if (kind === 'ev_lost') for (const u of (D.landL && D.landL.lost) || []) for (const r of u.r) pop(L.polygon(r, { color: '#ef4444', weight: 1.4, dashArray: '5 4', fillColor: '#ef4444', fillOpacity: .25 }), popupFor(kind, { a: u.a }, D)).addTo(g);
        if (kind === 'ev_streams') for (const s of (D.tankL && D.tankL.streams) || []) { const o = s.o || 2, c = o >= 5 ? '#1d4ed8' : o >= 3 ? '#3b82f6' : '#93c5fd'; for (const p of s.p) pop(L.polyline(p, { color: c, weight: .8 + o * .45, opacity: .85 }), popupFor(kind, s, D)).addTo(g); }
        if (kind === 'ev_tankcap') for (const t of (D.tankL && D.tankL.tanks) || []) { const c = TKCOL[t.a[5]] || '#94a3b8'; pop(L.polygon(t.r[0], { color: c, weight: 1, fillColor: c, fillOpacity: .5 }), popupFor(kind, t, D)).addTo(g); }
        if (kind === 'ev_heat' && D.heat && D.heat.lst) { const m = D.heat.meta, ov = L.imageOverlay(heatCanvas(D), [[m.bbox[1], m.bbox[0]], [m.bbox[3], m.bbox[2]]], { opacity: .62, interactive: false }); g.addLayer(ov); }
        g.addTo(map); evL[kind] = g;
      },
      setPin(lat, lon, wid, fly) {
        if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring);
        pin = L.marker("""),
    # existing tank layer: popup with dataset age and the "classification, not verified encroachment" caveat
    ("if (kind === 'tanks') for (const t of cfg.hy.tanks) for (const rg of t.rings) L.polygon(rg, { color: HYCOL[t.s23] || '#94a3b8', weight: 1, fillColor: HYCOL[t.s23] || '#94a3b8', fillOpacity: .55 }).bindTooltip((t.name || 'Tank') + ' · ' + HYLAB[t.s23]).addTo(g);",
     "if (kind === 'tanks') for (const t of cfg.hy.tanks) for (const rg of t.rings) L.polygon(rg, { color: HYCOL[t.s23] || '#94a3b8', weight: 1, fillColor: HYCOL[t.s23] || '#94a3b8', fillOpacity: .55 }).bindPopup(popupFor('ev_tankhy', t, cfg.D), { maxWidth: 300 }).addTo(g);"),
    # google engine: not supported, ignore quietly
    ("      setSatellite(on) { map.setMapTypeId(on ? 'hybrid' : 'roadmap'); },", "      showEv() { /* evidence layers are drawn on the OpenStreetMap engine only */ },\n      setSatellite(on) { map.setMapTypeId(on ? 'hybrid' : 'roadmap'); },"),
    # shared state + public API
    ("const st = { pin: null, layers: { wards: true, lakes: true }, poi: {}, sat: false, mode: 'flood', gov: {} };", "const st = { pin: null, layers: { wards: true, lakes: true }, poi: {}, sat: false, mode: 'flood', gov: {}, ev: {} };"),
    ("    for (const k in st.gov) if (st.gov[k]) impl.showGov(k, true);", "    for (const k in st.gov) if (st.gov[k]) impl.showGov(k, true);\n    for (const k in st.ev) if (st.ev[k]) impl.showEv(k, true);"),
    ("    showGov(kind, on) { st.gov[kind] = on; call('showGov', kind, on); },", "    showGov(kind, on) { st.gov[kind] = on; call('showGov', kind, on); },\n    showEv(kind, on) { st.ev[kind] = on; call('showEv', kind, on); },\n    popupFor, evInfo: (kind, D) => EVINFO[kind] ? EVINFO[kind](D) : null, EV_KINDS: Object.keys(EVINFO),"),
])

# ------------------------------------------------------------------ reports.js
CHK = r'''
  /* ---------- evidence-driven due-diligence checklist: one action per concern or data gap; ticks are remembered on this device ---------- */
  const chkStore = (key, set) => { try { if (set === undefined) return localStorage.getItem(key) === '1'; localStorage.setItem(key, set ? '1' : '0'); } catch (e) { return false; } };
  function checklistCard(r) {
    const c = SETUE.checklist(r); if (!c) return '';
    const base = 'sethu.chk.' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) + '.';
    const TAG = { concern: 'concern', watch: 'watch', unknown: 'data gap', standard: 'every purchase' };
    const all = [...c.items, ...c.std], ticked = all.filter(it => chkStore(base + it.key)).length;
    const row = it => { const k = base + it.key, done = chkStore(k), w = it.where || {};
      return `<label class="chk${done ? ' done' : ''}"><input type="checkbox" data-chk="${esc(k)}"${done ? ' checked' : ''}><span class="cb"><span class="ct"><b>${esc(it.trigger.label)}</b><i class="lvtag lt-${it.trigger.level}">${TAG[it.trigger.level] || ''}</i></span>
        ${it.trigger.value ? `<span class="cs">${esc(it.trigger.value)}</span>` : ''}<span class="cw">${esc(it.why)}</span><span class="ca"><b>Do:</b> ${esc(it.action)}</span>
        <span class="cwh"><b>Where:</b> ${w.url ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a>` : esc(w.name || '')}${w.status ? ` <small>(${esc(w.status)})</small>` : ''}</span>${it.doc ? `<span class="cd"><b>Ask for:</b> ${esc(it.doc)}</span>` : ''}</span></label>`; };
    const groups = Object.entries(c.cats).map(([cat, name]) => { const its = [...c.items, ...c.std].filter(i => i.cat === cat); return its.length ? `<div class="chkgrp"><h4>${esc(name)}</h4>${its.map(row).join('')}</div>` : ''; }).join('');
    return `<div class="card chkcard"><h3>Due-diligence checklist <span class="chkprog" style="color:var(--muted);font-weight:600">${ticked} of ${all.length} ticked</span></h3>
      <div class="lead">Built from what this report found: one step for every concern, watch item and data gap, plus two checks that apply to every purchase. Legal and land-record checks are kept apart from flood, water and infrastructure ones.</div>${groups}
      <div class="legend-note"><b>Unknown means "verify", not "unsafe".</b> A missing record is not a finding. SETU has not verified any office's process unless the line says so; where it says "not verified", ask the office what it needs. Ticks are saved on this device only.</div></div>`;
  }
'''
patch("web/platform/reports.js", [
    ("  /* ---------- compact-report helpers ---------- */", CHK + "\n  /* ---------- compact-report helpers ---------- */"),
])
s = open("web/platform/reports.js", encoding="utf-8").read()
assert s.count("${evidenceCard(r, S)}") == 3
s = s.replace("${evidenceCard(r, S)}", "${evidenceCard(r, S)}\n      ${checklistCard(r)}")
open("web/platform/reports.js", "w", encoding="utf-8").write(s)

# ------------------------------------------------------------------ app.js
patch("web/platform/app.js", [
    ("    bounds: D.zones.bounds, wards, water: D.geo.water, gov: D.gov, hy: D.hy, googleKey:", "    bounds: D.zones.bounds, wards, water: D.geo.water, gov: D.gov, hy: D.hy, D, googleKey:"),
    ("    else if (t === 'nalas' || t === 'spots' || t === 'drains' || t === 'tanks') MapKit.showGov(t, on);",
     "    else if (t === 'nalas' || t === 'spots' || t === 'drains' || t === 'tanks') MapKit.showGov(t, on);\n    else if (t.indexOf('ev_') === 0) { MapKit.showEv(t, on); renderEvLegend(); }"),
    ("function applyMapEngine(engine, why) {", """// legend for the evidence layers: swatches plus the age and caveat of each active dataset
function renderEvLegend() {
  const box = $('evlegend'), on = [...document.querySelectorAll('#maptools .chip.on[data-t^="ev_"]')].map(c => c.dataset.t);
  if (!box) return;
  box.innerHTML = on.map(k => { const i = MapKit.evInfo(k, SETUE.D); return i ? `<div class="evl"><b>${esc(i.title)}</b>${i.unit ? ` <span>${esc(i.unit)}</span>` : ''}<div class="sw">${i.swatch.map(s => `<i><u style="background:${s[0]}"></u>${esc(s[1])}</i>`).join('')}</div><small>${esc(i.note)}</small></div>` : ''; }).join('');
  box.classList.toggle('show', on.length > 0);
}
// due-diligence checklist ticks are remembered on this device
document.addEventListener('change', e => {
  const t = e.target; if (!t.matches || !t.matches('input[data-chk]')) return;
  try { localStorage.setItem(t.dataset.chk, t.checked ? '1' : '0'); } catch (x) { }
  const lab = t.closest('label'); if (lab) lab.classList.toggle('done', t.checked);
  const card = t.closest('.chkcard'); if (card) { const p = card.querySelector('.chkprog'); if (p) p.textContent = card.querySelectorAll('input[data-chk]:checked').length + ' of ' + card.querySelectorAll('input[data-chk]').length + ' ticked'; }
});
function applyMapEngine(engine, why) {"""),
])

# ------------------------------------------------------------------ index.html
patch("web/index.html", [
    ("      <button class=\"chip\" data-t=\"drains\">Drains</button>\n", """      <button class="chip" data-t="drains">Drains</button>
      <button class="chip" data-t="ev_wells">Groundwater wells</button>
      <button class="chip" data-t="ev_gwp">Groundwater zones</button>
      <button class="chip" data-t="ev_heat">Surface heat</button>
      <button class="chip" data-t="ev_hv">High-voltage lines</button>
      <button class="chip" data-t="ev_lost">Disappeared tanks</button>
      <button class="chip" data-t="ev_tankcap">Tank status &amp; capacity</button>
      <button class="chip" data-t="ev_streams">Natural streams</button>
"""),
    ("  <aside class=\"dock\" id=\"dock\"></aside>", "  <div class=\"evlegend\" id=\"evlegend\"></div>\n  <aside class=\"dock\" id=\"dock\"></aside>"),
])

# ------------------------------------------------------------------ styles
css = open("web/platform/styles.css", encoding="utf-8").read()
CSS = '''
/* evidence map layers + checklist */
.evlegend{position:absolute;right:14px;bottom:60px;z-index:450;max-width:270px;display:none;background:rgba(10,15,26,.92);border:1px solid var(--line2);border-radius:12px;padding:10px 12px;font-size:12px;color:var(--text2);backdrop-filter:blur(6px)}
.evlegend.show{display:block}
.evlegend .evl+.evl{margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}
.evlegend b{color:var(--text);font-size:12.5px}.evlegend span{color:var(--muted)}
.evlegend .sw{display:flex;flex-wrap:wrap;gap:3px 10px;margin:4px 0}.evlegend .sw i{font-style:normal;display:flex;align-items:center;gap:4px}
.evlegend .sw u{display:inline-block;width:11px;height:11px;border-radius:3px;border:1px solid rgba(255,255,255,.4)}
.evlegend small{display:block;color:var(--muted);line-height:1.35}
@media(max-width:1000px){.evlegend{left:10px;right:10px;max-width:none;bottom:70px}}
.evpop{font:13px/1.4 Inter,system-ui,sans-serif;color:#0f172a;min-width:210px}.evpop b{font-size:14px}
.evpop .v{margin:3px 0 6px;font-weight:600;color:#0c4a6e}
.evpop .r{display:flex;justify-content:space-between;gap:10px;border-top:1px solid #e2e8f0;padding:2px 0;font-size:12px}.evpop .r span:first-child{color:#475569}
.evpop .m{margin-top:7px;padding-top:6px;border-top:2px solid #cbd5e1;font-size:11.5px;color:#334155}.evpop .m b{font-size:11.5px;color:#0f172a}
.evpop .cv{margin-top:5px;color:#7c2d12;font-style:italic}
.chkgrp h4{margin:16px 0 4px;font-size:14px;color:var(--accent)}
label.chk{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-bottom:1px solid var(--line);cursor:pointer}
label.chk input{margin-top:4px;width:18px;height:18px;flex:none;accent-color:var(--accent)}
label.chk .cb{display:flex;flex-direction:column;gap:3px;font-size:13.5px;color:var(--text2);line-height:1.45}
label.chk .ct{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.label.chk .ct b,label.chk .ct b{color:var(--text);font-size:15px}
label.chk .cs{color:var(--text);font-size:13.5px}
label.chk.done .cb{opacity:.55}label.chk.done .ct b{text-decoration:line-through}
.lvtag{font-style:normal;font-size:10.5px;font-weight:700;padding:1px 8px;border-radius:999px;border:1px solid var(--line2);color:var(--muted)}
.lt-concern{color:var(--e);border-color:rgba(239,68,68,.6)}.lt-watch{color:var(--c);border-color:rgba(234,179,8,.6)}.lt-unknown{color:var(--muted);border-style:dashed}.lt-standard{color:var(--accent);border-color:rgba(56,189,248,.5)}
label.chk .cwh small{color:var(--muted)}label.chk .cd{color:#9bd8f7}
@media print{.evlegend{display:none!important}}
'''
if "/* evidence map layers + checklist */" not in css:
    open("web/platform/styles.css", "a", encoding="utf-8").write(CSS)
print("batch-2 UI patched")
