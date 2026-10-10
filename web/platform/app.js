/* SETHU platform shell: search → pin → explore card → full-page report (Customer / Agent / Insurer). */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const PERILS = {
  rain_vehicle: { label: 'Vehicle damaged in rain flooding', rain: true, line: 'motor' },
  rain_home: { label: 'Home / shop water entry (rain flooding)', rain: true, line: 'prop' },
  collision: { label: 'Collision / accident', rain: false },
  theft: { label: 'Theft', rain: false },
  fire: { label: 'Fire', rain: false }
};
const PLACES = [
  ['Tolichowki', 17.4015, 78.4100], ['Jubilee Hills', 17.4325, 78.4071], ['Gachibowli', 17.4401, 78.3489], ['Hitec City', 17.4435, 78.3772],
  ['Kukatpally', 17.4948, 78.3996], ['LB Nagar', 17.3457, 78.5522], ['Secunderabad', 17.4399, 78.4983], ['Charminar', 17.3616, 78.4747], ['Hussain Sagar', 17.4235, 78.4745]
];
const LENS_NAME = { customer: 'Customer report', agent: 'Real estate agent report', insurer: 'Insurer report' };
const LENS_ICON = { customer: '🏠', agent: '🏷️', insurer: '🛡️' };
const LENS_SUB = { customer: 'Safe to buy? What it really costs.', agent: 'Price with evidence. Answer the flood question.', insurer: 'Risk tiers and a rain-evidence claim check.' };
// shown in the ⓘ hover cards: what the report shows, and why it is useful to that person
const LENS_INFO = {
  customer: { t: 'Customer report', w: 'A one-page check on a home you are thinking of buying or renting: how the area copes with heavy rain, how far the nearest hospital, mall, metro and school are, and the true cost with duties.', u: 'Helps a family spot a flooding or lake problem, or an overpriced quote, before paying an advance.' },
  agent: { t: 'Real estate agent report', w: 'A client-ready brief for a listing: the market price band from property portals, a price check against your own comparables, selling points, and what buyers will push back on.', u: 'Helps an agent price with evidence and answer the flood and lake question before the buyer asks it.' },
  insurer: { t: 'Insurer report', w: 'The underwriting view of an address: motor, property and health-access risk tiers, plus a check of whether the rain on a claim date supports a water-damage claim.', u: 'Helps an insurer price risk by location and fast-track genuine claims, sending only doubtful ones for review.' }
};
const infoIcon = lens => `<span class="info" tabindex="0" role="button" aria-label="What is the ${LENS_NAME[lens]}?" data-lens="${lens}">i</span>`;
const S = {
  r: null, label: '', address: '', gp: null, fc: null, air: null, terrain: null, lens: 'customer', line: 'motor', view: 'explore',
  unlocked: { customer: true, agent: true, insurer: true }, open: {},
  cust: { price: '9000000', area: '1200', brokerage: '1' }, agent: { ask: '9500', area: '1200', comps: '8800, 9200, 9600', guide: '', fee: '1' },
  claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false },
  ai: { q: '', a: '', think: false }, PERILS, cfg: { places: false, mapsKey: '' }, seq: 0, token: Math.random().toString(36).slice(2), busy: false
};

function toast(t, ms = 2800) { const e = $('toast'); e.textContent = t; e.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(() => e.classList.remove('show'), ms); }
const fmtKm = m => m == null ? '—' : m < 950 ? Math.round(m / 10) * 10 + ' m' : (m / 1000).toFixed(1) + ' km';
const api = async (path, ms = 7000) => { const c = new AbortController(), t = setTimeout(() => c.abort(), ms); try { return await fetch(path, { signal: c.signal }).then(r => r.json()); } finally { clearTimeout(t); } };

/* ------------------------------ search ------------------------------ */
let sugItems = [], sugTimer = null;
function localSearch(q) {
  q = q.trim().toLowerCase(); if (q.length < 2) return [];
  const out = [];
  for (const x of SETUE.D.index) { const n = x.name.toLowerCase(), i = n.indexOf(q); if (i >= 0) out.push({ main: x.name, sub: x.kind, lat: x.lat, lon: x.lon, s: i === 0 ? 0 : 1 }); }
  out.sort((a, b) => a.s - b.s || a.main.length - b.main.length); return out.slice(0, 5);
}
async function photonSearch(q, limit = 5) {
  try {
    const c = new AbortController(), t = setTimeout(() => c.abort(), 3500);
    const j = await fetch(`https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&lat=17.40&lon=78.45&limit=${limit}&lang=en`, { signal: c.signal }).then(r => r.json()); clearTimeout(t);
    return (j.features || []).filter(f => (f.properties.countrycode || '') === 'IN' && /telangana|andhra/i.test(f.properties.state || 'telangana')).map(f => {
      const p = f.properties, sub = [p.street, p.district || p.locality, p.city || p.county].filter(Boolean).slice(0, 3).join(', ');
      return { main: p.name || sub || q, sub, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] };
    }).filter(x => x.main);
  } catch (e) { return []; }
}
async function onlineSearch(q) {
  const ph = await photonSearch(q, 3); if (ph.length) return ph;
  try {
    const u = `https://nominatim.openstreetmap.org/search?format=json&limit=3&countrycodes=in&viewbox=78.20,17.66,78.72,17.18&q=${encodeURIComponent(/hyderabad/i.test(q) ? q : q + ', Hyderabad')}`;
    const c = new AbortController(), t = setTimeout(() => c.abort(), 4500);
    const j = await fetch(u, { signal: c.signal }).then(r => r.json()); clearTimeout(t);
    return j.map(x => ({ main: x.display_name.split(',').slice(0, 2).join(','), sub: x.display_name.split(',').slice(2, 4).join(','), lat: +x.lat, lon: +x.lon }));
  } catch (e) { return []; }
}
async function updateSuggestions(q) {
  const el = $('sug');
  if (!q.trim() || q.trim().length < 2) { el.classList.remove('show'); sugItems = []; return; }
  let items = [];
  if (S.cfg.suggest) { try { const j = await api(`/api/suggest?q=${encodeURIComponent(q)}&token=${S.token}`, 4000); items = (j.items || []).map(x => ({ id: x.id, main: x.main, sub: x.sub })); } catch (e) { } }
  const loc = localSearch(q); items = items.concat(loc.filter(l => !items.some(i => i.main.toLowerCase() === l.main.toLowerCase())));
  const STOP = new Set(['the', 'of', 'in', 'at', 'and', 'near', 'hyderabad']);
  const toks = q.toLowerCase().split(/[^a-z0-9]+/).filter(t => t.length >= 2 && !STOP.has(t));
  const hits = x => { const ws = (x.main + ' ' + (x.sub || '')).toLowerCase().split(/[^a-z0-9]+/); return toks.filter(t => ws.some(w => w.startsWith(t))).length; };
  const paint = () => {
    items.sort((p, r) => hits(r) - hits(p));
    sugItems = items.slice(0, 8);
    if ($('q').value !== q) return;
    const exact = sugItems.length && toks.length && hits(sugItems[0]) >= toks.length;
    const hint = !exact && toks.length >= 2 ? '<div class="sughint">No exact match for “' + esc(q) + '” — these are the closest. Building and apartment names are often missing from free map data: search the locality and click the map, or paste a Google Maps link.</div>' : '';
    el.innerHTML = hint + sugItems.map((x, i) => `<button data-i="${i}"><span class="m">${esc(x.main)}</span><span class="s">${esc(x.sub || '')}</span></button>`).join('') || '<button><span class="s">Searching…</span></button>';
    el.classList.add('show');
    el.querySelectorAll('button[data-i]').forEach(b => b.onmousedown = ev => { ev.preventDefault(); pickSuggestion(sugItems[+b.dataset.i]); });
  };
  paint();
  if (q.trim().length >= 3) {   // always add free online OpenStreetMap (Photon) results as a fallback layer
    const ph = await photonSearch(q, 5);
    if ($('q').value !== q) return;
    items = items.concat(ph.filter(x => !items.some(i => i.main.toLowerCase() === x.main.toLowerCase())));
    paint();
  }
}
async function pickSuggestion(x) {
  $('sug').classList.remove('show'); $('q').value = x.main;
  if (x.id) {
    toast('Locating…', 4000);
    const j = await api(`/api/place?id=${encodeURIComponent(x.id)}&token=${S.token}`).catch(() => ({}));
    S.token = Math.random().toString(36).slice(2);
    if (j.lat) { $('toast').classList.remove('show'); S.address = j.address || ''; return setPin(j.lat, j.lon, x.main); }
    toast('Could not resolve that place — try another.'); return;
  }
  S.address = ''; setPin(x.lat, x.lon, x.main);
}
function parseMapsLink(q) {   // full Google Maps URLs carry the pin's coordinates; short links cannot be resolved in the browser
  if (!/(google\.[a-z.]+\/maps|maps\.google|goo\.gl|maps\.app)/i.test(q)) return null;
  const pick = re => { const m = q.match(re); return m ? { lat: +m[1], lon: +m[2] } : null; };
  return pick(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/) || pick(/[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+)(?:,|%2C)(-?\d+\.\d+)/i) || pick(/@(-?\d+\.\d+),(-?\d+\.\d+)/) || { short: true };
}
async function doSearch(q) {
  q = q.trim(); if (!q) return; $('sug').classList.remove('show');
  const link = parseMapsLink(q);
  if (link && link.short) return toast('That is a short Google link. Open it in your browser first, then paste the full address-bar URL here.', 6000);
  if (link) return setPin(link.lat, link.lon, 'Pin from Google Maps link');
  const m = q.match(/^\s*(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)\s*$/);
  if (m) return setPin(+m[1], +m[2], 'Coordinates');
  if (sugItems.length && $('q').value === q) return pickSuggestion(sugItems[0]);
  const loc = localSearch(q); if (loc.length) return pickSuggestion(loc[0]);
  toast('Searching…', 5000); const on = await onlineSearch(q);
  if (on.length) { $('toast').classList.remove('show'); return pickSuggestion(on[0]); }
  toast('Could not find that place — try a nearby landmark, or click the map.');
}

/* ------------------------------ pin → report ------------------------------ */
async function setPin(lat, lon, label, opts = {}) {
  const seq = ++S.seq; S.busy = true;
  S.label = label || ''; S.gp = null; S.fc = null; S.air = null; S.terrain = null; S.ai = { q: '', a: '', think: false }; S.claim.out = null;
  const r = await SETUE.report(lat, lon);
  if (seq !== S.seq) return;
  S.r = r; S.busy = false;
  if (r.ok) MapKit.setPin(lat, lon, r.outside ? null : r.wid, true); else MapKit.clearPin();
  if (!opts.keepView && S.view === 'report') closeReport(true);
  refresh(true); syncHash();
  if (!r.ok) return;
  // enrich in the background; every step re-renders without disturbing typing
  SETUE.elevationProfile(lat, lon).then(t => { if (seq !== S.seq) return; S.terrain = t; S.r.terrain = t; SETUE.reanalyse(S.r); refresh(); });
  SETUE.forecast(lat, lon).then(f => { if (seq !== S.seq) return; S.fc = f; refresh(); }).catch(() => { });
  SETUE.airNow(lat, lon).then(a => { if (seq !== S.seq) return; S.air = a; if (S.r) { S.r.air = a; SETUE.reanalyse(S.r); } refresh(); });
  if (S.cfg.places) {
    api(`/api/places?lat=${lat}&lon=${lon}`, 9000).then(async gp => {
      if (seq !== S.seq) return;
      if (gp && gp.cats && Object.keys(gp.cats).length) {
        S.gp = gp; const r2 = await SETUE.report(lat, lon, gp); if (seq !== S.seq || !r2.ok) return;
        r2.terrain = S.terrain; r2.air = S.air; SETUE.reanalyse(r2); S.r = r2; refresh();
      } else if (gp && gp.error) console.warn('Places unavailable, using OSM backup:', gp.error);
    }).catch(e => console.warn('Places call failed, using OSM backup', e));
  }
}
function syncHash() {
  if (!S.r || !S.r.ok) return;
  const h = S.view === 'report' ? `#/r/${S.lens}/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}` : `#/l/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}`;
  if (location.hash !== h) { try { history.replaceState(null, '', h); } catch (e) { } }
}

/* ------------------------------ rendering ------------------------------ */
function renderDock() {
  const d = $('dock'), r = S.r;
  if (!r) {
    const poi = (SETUE.D.geo && SETUE.D.geo.poi) || {}, n = k => (poi[k] || []).length;
    const stat = (v, l) => `<div><b>${v}</b><span>${l}</span></div>`;
    d.innerHTML = `<div class="panel scroll intro"><h1>Check any Hyderabad address <em>before</em> you buy, sell or insure it.</h1>
      <p>Search a place or tap the map, then pick the report that fits you.</p>
      <div class="who">${['customer', 'agent', 'insurer'].map(l => `<div class="wrow"><span class="e">${LENS_ICON[l]}</span><span><b>${LENS_NAME[l]}</b><span>${LENS_SUB[l]}</span></span>${infoIcon(l)}</div>`).join('')}</div>
      <div class="proof">${stat('145', 'wards')}${stat(Math.floor(n('hospital') / 100) * 100 + '+', 'hospitals')}${stat(Math.floor(n('school') / 100) * 100 + '+', 'schools')}${stat('8', 'real floods tested')}</div>
      <div class="chips">${PLACES.slice(0, 6).map((p, i) => `<button class="chip" data-act="place" data-i="${i}">${esc(p[0])}</button>`).join('')}</div></div>`;
    return;
  }
  if (!r.ok) { d.innerHTML = `<div class="panel intro"><h1>Outside our <em>coverage</em></h1><p>SETHU covers Hyderabad. Pick a point on the map, or search a Hyderabad locality.</p><button class="btn" data-act="clear">Back</button></div>`; return; }
  const d192 = r.outside ? null : r.setu.depth[192], thr = SETUE.D.thr, top = r.buyer.flags[0], out = r.outside;
  const title = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name;
  d.innerHTML = `<div class="panel scroll lc"><div class="eyebrow">Location</div><h2>${esc(title)}</h2>
    <div class="sub">${esc(r.ward.name)}${S.address ? ' · ' + esc(S.address) : ''}</div>
    <div class="row"><div class="kpi"><div class="l">Location score</div><div class="v">${r.pillars.score}</div><div class="t">${r.pillars.label}</div></div>
      <div class="kpi"><div class="l">${out ? 'Flood model' : '2020 storm'}</div><div class="v sm" style="color:${out ? 'var(--muted)' : d192 >= .5 ? 'var(--e)' : d192 >= thr ? 'var(--c)' : 'var(--a)'}">${out ? 'n/a' : d192 >= thr ? d192.toFixed(2) + ' m' : 'Dry'}</div><div class="t">${out ? 'outside wards' : 'modelled depth'}</div></div>
      <div class="kpi"><div class="l">Facilities</div><div class="v">${r.scores.dev.score}</div><div class="t">out of 100</div></div></div>
    <div class="callout" style="margin-bottom:18px"><b>${esc(top.t)}.</b> ${esc(top.d.length > 120 ? top.d.slice(0, 117) + '…' : top.d)}</div>
    <div class="reports">${['customer', 'agent', 'insurer'].map(l => `<button class="rbtn" data-act="open" data-lens="${l}"><span class="e">${LENS_ICON[l]}</span><span><b>${LENS_NAME[l]}</b><span>${LENS_SUB[l]}</span></span>${infoIcon(l)}</button>`).join('')}</div></div>`;
}
function renderReport() {
  const v = $('report'), r = S.r; if (!r || !r.ok) return;
  const sc = v.scrollTop;
  const title = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name;
  v.innerHTML = `<div class="rhead"><div class="rin"><button class="btn ghost sm back" data-act="back">← Map</button>
    <div><h1>${esc(title)}</h1><div class="loc">${esc(r.ward.name)} · ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div></div>
    <div class="tabs">${['customer', 'agent', 'insurer'].map(l => `<button data-act="tab" data-lens="${l}" class="${S.lens === l ? 'on' : ''}">${LENS_ICON[l]} ${l === 'customer' ? 'Customer' : l === 'agent' ? '<span class="lg">Real estate agent</span><span class="sm">Real estate</span>' : 'Insurer'}${infoIcon(l)}</button>`).join('')}</div>
    <button class="btn ghost sm noprint" data-act="print">🖨 PDF</button><button class="btn ghost sm noprint" data-act="share">🔗 Share</button></div></div>
    <div class="rbody">${Reports.render(S.lens, S)}</div>`;
  v.scrollTop = sc;
}
function refresh(fresh) {
  if (S.view === 'report') {
    const a = document.activeElement;
    if (!fresh && a && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) && $('report').contains(a)) { clearTimeout(refresh._t); refresh._t = setTimeout(() => refresh(), 1200); return; }
    renderReport();
  } else renderDock();
}
function openReport(lens) {
  if (!S.r || !S.r.ok) return;
  S.lens = lens; S.view = 'report'; $('report').classList.remove('hide'); $('report').scrollTop = 0; renderReport(); syncHash();
}
function closeReport(silent) { S.view = 'explore'; $('report').classList.add('hide'); if (!silent) { renderDock(); syncHash(); } }

/* ------------------------------ actions ------------------------------ */
document.addEventListener('click', e => {
  const inf = e.target.closest('.info'); if (inf) { e.preventDefault(); e.stopPropagation(); showTip(inf, true); return; }
  if (!e.target.closest('#tip')) hideTip();
  const t = e.target.closest('[data-act]'); if (!t) return;
  const a = t.dataset.act;
  if (a === 'place') { const p = PLACES[+t.dataset.i]; $('q').value = p[0]; S.address = ''; setPin(p[1], p[2], p[0]); }
  else if (a === 'open') openReport(t.dataset.lens);
  else if (a === 'back') closeReport();
  else if (a === 'tab') { S.lens = t.dataset.lens; S.ai = { q: '', a: '', think: false }; renderReport(); $('report').scrollTop = 0; syncHash(); }
  else if (a === 'clear') { S.r = null; MapKit.clearPin(); renderDock(); history.replaceState(null, '', '#/'); }
  else if (a === 'print') window.print();
  else if (a === 'toggle-detail') { S.open.detail = !S.open.detail; renderReport(); }
  else if (a === 'share') { navigator.clipboard && navigator.clipboard.writeText(location.href).then(() => toast('Link copied')).catch(() => toast('Copy the address bar link to share')); }
  else if (a === 'line') { S.line = t.dataset.line; renderReport(); }
  else if (a === 'cust-calc' || a === 'agent-calc') renderReport();
  else if (a === 'cust-example') { S.cust = { price: '9000000', area: '1200', brokerage: '1' }; renderReport(); }
  else if (a === 'agent-example') { S.agent = { ask: '9500', area: '1200', comps: '8800, 9200, 9600', guide: '', fee: '1' }; renderReport(); }
  else if (a === 'claim-run') runClaim();
  else if (a === 'claim-demo') demoClaim(+t.dataset.d);
});
document.addEventListener('input', e => {
  const b = e.target.closest('[data-bind]'); if (!b) return;
  const [grp, key] = b.dataset.bind.split('.'); S[grp][key] = b.value;
});
document.addEventListener('change', e => {
  const b = e.target.closest('[data-bind]'); if (!b) return;
  const [grp, key] = b.dataset.bind.split('.'); S[grp][key] = b.value;
  if (b.dataset.bind === 'claim.peril') { S.claim.out = null; if (PERILS[b.value].line) S.line = PERILS[b.value].line; renderReport(); }
});

async function runClaim() {
  const r = S.r, cl = S.claim; if (!cl.date) return toast('Pick the date of loss first');
  if (!PERILS[cl.peril].rain) { cl.out = { noEvidence: true }; return renderReport(); }
  cl.busy = true; cl.out = null; renderReport();
  try { const rain = await SETUE.rainOn(r.lat, r.lon, cl.date); cl.out = SETUE.claimCheck(r, rain, cl.peril); }
  catch (e) { cl.out = { error: 'Could not fetch rainfall for that date. Check your connection and try again.' }; }
  cl.busy = false; renderReport();
}
async function demoClaim(n) {
  const d = n === 1 ? [17.4015, 78.4100, 'Tolichowki', '2020-10-13'] : [17.4138, 78.4390, 'Banjara Hills', '2020-03-02'];
  await setPin(d[0], d[1], d[2], { keepView: true });
  S.view = 'report'; S.claim = { peril: 'rain_vehicle', date: d[3], amount: '', out: null, busy: false }; S.line = 'motor'; S.lens = 'insurer';
  $('report').classList.remove('hide'); renderReport(); runClaim();
}
/* ------------------------------ ⓘ hover cards ------------------------------ */
function showTip(el, pin) {
  const i = LENS_INFO[el.dataset.lens]; if (!i) return;
  let tip = $('tip'); if (!tip) { tip = document.createElement('div'); tip.id = 'tip'; document.body.appendChild(tip); }
  if (pin && tip.classList.contains('show') && tip._for === el) { hideTip(); return; }
  tip._for = el;
  tip.innerHTML = `<b>${i.t}</b><p><em>Shows</em> ${i.w}</p><p><em>Useful because</em> ${i.u}</p>`;
  tip.classList.add('show');
  const b = el.getBoundingClientRect(), w = Math.min(330, innerWidth - 20);
  tip.style.width = w + 'px';
  tip.style.left = Math.max(10, Math.min(b.left + b.width / 2 - w / 2, innerWidth - w - 10)) + 'px';
  const h = tip.offsetHeight; tip.style.top = (b.bottom + 10 + h > innerHeight ? Math.max(10, b.top - h - 10) : b.bottom + 10) + 'px';
}
function hideTip() { const t = $('tip'); if (t) { t.classList.remove('show'); t._for = null; } }
document.addEventListener('mouseover', e => { const i = e.target.closest('.info'); if (i) showTip(i); });
document.addEventListener('mouseout', e => { if (e.target.closest('.info') && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('#tip'))) hideTip(); });
document.addEventListener('focusin', e => { const i = e.target.closest && e.target.closest('.info'); if (i) showTip(i); });
document.addEventListener('focusout', e => { if (e.target.closest && e.target.closest('.info')) hideTip(); });
// keep collapsible sections open across re-renders, and open them all when printing
document.addEventListener('toggle', e => { const d = e.target; if (d.matches && d.matches('details.more') && d.dataset.id) S.open[d.dataset.id] = d.open; }, true);
window.addEventListener('beforeprint', () => document.querySelectorAll('details.more,details.mini').forEach(d => { d.open = true; }));

/* ------------------------------ modals ------------------------------ */
async function showEngine() {
  const D = SETUE.D, p = D.geo.poi, t = (D.meta || {}).tests || {}, n = k => (p[k] || []).length.toLocaleString('en-IN');
  $('mc').innerHTML = `<button class="x" data-close>×</button><h2>The SETHU engine</h2>
    <p>The three reports are use-cases. SETHU is the layer underneath: <b>a location-intelligence engine for Indian cities, built on open and commercial map data.</b></p>
    <h4>What it knows about any point</h4><ul>
    <li>Flood susceptibility of its ward — learned from 8 real Hyderabad floods and tested on floods it never saw</li>
    <li>Modelled water depth at any rainfall, and whether the road to a hospital gets cut</li>
    <li>${D.geo.water.length.toLocaleString('en-IN')} mapped lakes, tanks and ponds, and ground level against the surroundings</li>
    <li><b>HYDRAA / TGRAC tank assessment:</b> ${D.hy.tanks.length} water bodies classified Live or Partially / Totally Encroached (2014 vs 2023 satellite status), plus ${(D.geo.poi.ambulance || []).length} government ambulance stations from the Telangana health GIS</li>
    <li><b>Official GHMC drainage records</b> from the Telangana State GIS service: ${D.gov.nalas.length} named nalas, ${D.gov.segments.length} nala segments with existing and proposed widths, ${D.gov.drains.length.toLocaleString('en-IN')} drain and canal lines, ${D.gov.tanks.length} tank outlines and ${D.gov.inundation.length} listed inundation areas</li>
    <li>${n('hospital')} hospitals · ${n('clinic')} clinics · ${n('school')} schools · ${n('college')} colleges · ${n('bank')} banks · ${n('market')} markets · ${n('park')} parks · transit, fire and police — merged from OpenStreetMap and the Overture Maps open dataset (Meta, Microsoft, Foursquare), optionally upgraded live by Google Places</li>
    <li>Live rain: 7-day forecast and rainfall on any past date · air quality · local asking-price bands</li></ul>
    <h4>Honest validation</h4><ul><li>Held-out floods: mean AUC <b>${t.mean != null ? t.mean.toFixed(2) : '0.69'}</b> (0.5 = coin flip) · GHMC waterlogging list: <b>${t.independent_ghmc != null ? t.independent_ghmc.toFixed(2) : '0.79'}</b> · first version: ${t.old_model != null ? t.old_model.toFixed(2) : '0.49'}</li>
    <li>Against GHMC's 23 official inundation spots, 43% sit in our top-quartile wards (25% by chance) — modest, because many are underpasses and junctions a ward-level terrain model cannot see. That is why the official spot list is scored alongside the model, not instead of it.</li>
    <li>Ward-level, not street-level. Lake distance, terrain pocket, facilities and fire reach are indicators, not validated predictions.</li></ul>
    <h4>System status</h4><div id="health" class="callout">Checking…</div>
    <p style="margin-top:14px"><a href="planner.html">Open the government Flood Planner →</a></p>`;
  $('modal').classList.add('show');
  try {
    const h = await api('/api/health', 12000), row = (ok, label, extra) => `<div class="kv"><span class="k">${label}</span><span class="v" style="color:${ok ? 'var(--a)' : 'var(--e)'}">${ok ? '● ready' : '● ' + (extra || 'not configured')}</span></div>`;
    $('health').innerHTML = row(h.browser_key_present, 'Google Maps key', 'missing — OpenStreetMap map is used') + row(h.server_key_present, 'Google Places key', 'not used — open facility data is in use')
      + (h.server_key_present ? row(h.places_nearby && h.places_nearby.ok, 'Places · nearby search', h.places_nearby && h.places_nearby.error) + row(h.places_autocomplete && h.places_autocomplete.ok, 'Places · address search', h.places_autocomplete && h.places_autocomplete.error) : '')
      + (h.tomtom_key_present ? row(h.tomtom_search && h.tomtom_search.ok, 'TomTom address search', h.tomtom_search && h.tomtom_search.error) : '') + `<div class="kv"><span class="k">Map engine in use</span><span class="v">${MapKit.engine}</span></div>`;
  } catch (e) { $('health').textContent = 'Status endpoint unreachable (static hosting?) — the app still works with its built-in backup data.'; }
}
function showQR() {
  const url = location.href.split('#')[0];
  $('mc').innerHTML = `<button class="x" data-close>×</button><h2>Try it on your phone</h2><p>Scan to check your own address.</p><div id="qrbox"></div><p style="text-align:center;font-size:14px;color:var(--muted)">${esc(url)}</p>`;
  try { const q = qrcode(0, 'M'); q.addData(url); q.make(); $('qrbox').innerHTML = q.createImgTag(7, 10); const im = $('qrbox').querySelector('img'); im.style.cssText = 'display:block;margin:12px auto;background:#fff;border-radius:12px'; } catch (e) { $('qrbox').textContent = 'QR unavailable'; }
  $('modal').classList.add('show');
}

/* ------------------------------ routing + boot ------------------------------ */
async function route() {
  const h = location.hash; let m;
  if ((m = h.match(/^#\/r\/(customer|agent|insurer)\/(-?[\d.]+),(-?[\d.]+)/))) {
    S.lens = m[1]; const lat = +m[2], lon = +m[3];
    if (!S.r || Math.abs(S.r.lat - lat) > 1e-5 || Math.abs(S.r.lon - lon) > 1e-5) await setPin(lat, lon, '', { keepView: true });
    if (S.r && S.r.ok) openReport(S.lens);
  } else if ((m = h.match(/^#\/l\/(-?[\d.]+),(-?[\d.]+)/)) || (m = h.match(/^#(-?[\d.]+),(-?[\d.]+)/))) {
    if (!S.r) await setPin(+m[1], +m[2], '');
  }
}
function applyMapEngine(engine, why) { if (why) toast(why + ' — using the OpenStreetMap map instead', 4500); }
async function boot() {
  $('dock').innerHTML = '<div class="panel intro"><p><span class="spin"></span> &nbsp;Loading the SETHU engine…</p></div>';
  try { await SETUE.load(); } catch (e) { $('dock').innerHTML = '<div class="panel intro"><p>Could not load data files. Serve the site from the <code>web/</code> folder.</p></div>'; return; }
  try { S.cfg = await api('/api/config', 4000); } catch (e) { S.cfg = { places: false, suggest: false, mapsKey: '' }; }
  const D = SETUE.D;
  let wl = {};   // precomputed ward-level Location Score (pipeline/p16_wardloc.js) so the map appears instantly
  try { wl = await fetch('data/wardloc.json').then(r => r.json()); } catch (e) { }
  const wards = D.wards.map(w => ({ id: w.id, name: w.name, rings: w.rings, pct: (D.wardfeat[String(w.id)] || {}).pct || 0, loc: wl[w.id] != null ? wl[w.id] : null }));
  await MapKit.init($('map'), {
    bounds: D.zones.bounds, wards, water: D.geo.water, gov: D.gov, hy: D.hy, googleKey: S.cfg.mapsKey || '', onPick: (lat, lon) => { S.address = ''; $('q').value = ''; setPin(lat, lon, ''); },
    poiRows: c => (S.gp && S.gp.cats && S.gp.cats[c] && S.gp.cats[c].length) ? S.gp.cats[c] : (D.geo.poi[c] || []), onEngine: applyMapEngine
  });
  $('maptools').onclick = e => {
    const c = e.target.closest('.chip'); if (!c) return; const t = c.dataset.t;
    if (t === 'more') { const mb = $('morebox'), open = !mb.classList.contains('show'); mb.classList.toggle('show', open); c.classList.toggle('on', open); return; }
    const on = !c.classList.contains('on'); c.classList.toggle('on', on);
    if (t === 'wards' || t === 'lakes') { MapKit.setLayer(t, on); if (t === 'wards') $('maplegend').style.display = on ? '' : 'none'; }
    else if (t === 'sat') MapKit.setSatellite(on);
    else if (t === 'nalas' || t === 'spots' || t === 'drains' || t === 'tanks') MapKit.showGov(t, on);
    else if (t === 'mode') {
      const loc = c.dataset.mode !== 'loc'; c.dataset.mode = loc ? 'loc' : 'flood'; c.classList.remove('on');
      c.textContent = loc ? 'Colour: location score' : 'Colour: flood rank';
      MapKit.setColorMode(c.dataset.mode);
      $('maplegend').innerHTML = loc ? '<b>Location score (ward average)</b><div class="ramp" style="background:linear-gradient(90deg,#f43f5e,#facc15,#2dd4bf)"></div><div class="rr"><span>weaker</span><span>stronger</span></div>' : '<b>Flood-susceptibility rank</b><div class="ramp"></div><div class="rr"><span>lower</span><span>higher</span></div>';
    }
    else MapKit.showPoi(t, on);
  };
  $('q').oninput = e => { clearTimeout(sugTimer); const v = e.target.value; sugTimer = setTimeout(() => updateSuggestions(v), S.cfg.suggest ? 260 : 90); };
  $('q').onkeydown = e => { if (e.key === 'Enter') doSearch(e.target.value); if (e.key === 'Escape') $('sug').classList.remove('show'); };
  $('q').onblur = () => setTimeout(() => $('sug').classList.remove('show'), 160);
  $('goBtn').onclick = () => doSearch($('q').value);
  $('locBtn').onclick = () => {
    if (!navigator.geolocation) return toast('Location is not available in this browser');
    toast('Finding you…', 7000);
    navigator.geolocation.getCurrentPosition(p => { $('q').value = 'My location'; S.address = ''; setPin(p.coords.latitude, p.coords.longitude, 'My location'); },
      () => toast('Could not get your location — search or click the map instead.'), { enableHighAccuracy: true, timeout: 8000 });
  };
  $('engBtn').onclick = showEngine; $('qrBtn').onclick = showQR;
  $('logo').onclick = () => { if (S.view === 'report') closeReport(); else { S.r = null; MapKit.clearPin(); MapKit.fitCity(); renderDock(); history.replaceState(null, '', '#/'); } };
  $('modal').onclick = e => { if (e.target === $('modal') || e.target.closest('[data-close]')) $('modal').classList.remove('show'); };
  window.addEventListener('hashchange', route);
  renderDock(); await route();
  window.__booted = Math.round(performance.now());   // for load-time checks
}
boot();
