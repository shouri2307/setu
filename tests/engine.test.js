/* Engine test harness — run:  node tests/engine.test.js [--net] [--dist]
 * Loads web/platform/engine.js in a sandbox with local data files, then checks data integrity,
 * geometry, scoring invariants and golden locations. --net also hits the live APIs.
 * --dist prints the tier distribution (used to calibrate thresholds). */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', 'web');
const realFetch = fetch;
const sandbox = {
  console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => {
    if (/^https?:/.test(u)) return realFetch(u);
    const p = path.join(WEB, u);
    if (!fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => { throw new Error('404 ' + u); } });
    return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) });
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sandbox);
for (const f of ['charts.js', 'view.js', 'reports.js', 'brief.js'])
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', f), 'utf8') + '\n;globalThis.' + ({ 'charts.js': 'Charts = Charts', 'view.js': 'View = View', 'reports.js': 'Reports = Reports', 'brief.js': 'Brief = Brief' })[f] + ';', sandbox);
const E = sandbox.SETUE, Rep = sandbox.Reports, View = sandbox.View;

let pass = 0, fail = 0; const fails = [];
function ok(cond, name, detail) { if (cond) pass++; else { fail++; fails.push(name + (detail ? '  -> ' + detail : '')); } }
const argv = process.argv.slice(2);

(async () => {
  await E.load();
  const D = E.D;

  // ---- data integrity ----
  ok(D.wards.length === 145, 'ward count is 145', D.wards.length);
  ok(Object.keys(D.wardfeat).length === 145, 'wardfeat covers 145 wards');
  ok(D.scen.length >= 10, 'rain scenarios present');
  for (const [cat, min] of [['hospital', 1500], ['clinic', 800], ['school', 2500], ['college', 200], ['metro', 50], ['market', 800], ['bank', 1500], ['park', 500]])
    ok((D.geo.poi[cat] || []).length >= min, `POI ${cat} >= ${min}`, (D.geo.poi[cat] || []).length);
  ok(D.geo.water.length > 100, 'water bodies loaded', D.geo.water.length);
  ok(D.hy.tanks.length >= 1000 && D.hy.tanks.filter(x => x.name).length >= 500, 'HYDRAA / TGRAC tank assessment loaded', D.hy.tanks.length);
  ok((D.geo.poi.ambulance || []).length >= 80, 'ambulance stations loaded', (D.geo.poi.ambulance || []).length);
  ok(D.addedTanks > 100, 'official tank outlines added to the lake layer', D.addedTanks);
  ok(D.hmda.lakes.filter(l => l.district === 'Hyderabad' && l.ftl_url).length >= 25, 'verified HMDA FTL PDF links for Hyderabad-district lakes');
  ok(D.hmda.lakes.length > 2500 && D.hmda.lakes.filter(l => l.district === 'Hyderabad').length >= 25, 'HMDA lake list loaded', D.hmda.lakes.length);
  ok(D.gov.nalas.length >= 90 && D.gov.segments.length >= 1000 && D.gov.drains.length >= 3000 && D.gov.tanks.length >= 800 && D.gov.inundation.length >= 20, 'official GHMC drainage records loaded', [D.gov.nalas.length, D.gov.segments.length, D.gov.drains.length, D.gov.tanks.length, D.gov.inundation.length].join('/'));
  ok(D.lakes.length >= 20, 'at least 20 lakes/tanks classified', D.lakes.length);
  const b = D.zones.bounds;
  let outside = 0;
  for (const cat in D.geo.poi) for (const p of D.geo.poi[cat]) if (p[0] < b[1] - .3 || p[0] > b[3] + .3 || p[1] < b[0] - .3 || p[1] > b[2] + .3) outside++;
  ok(outside === 0, 'all POIs inside the study box', outside);

  // ---- geometry ----
  let selfHit = 0;
  for (const w of D.wards) { const l = E.locate(w.c[1], w.c[0]); if (l && l.id === w.id) selfHit++; }
  ok(selfHit >= 120, 'ward centroids resolve to their own ward (>=120/145)', selfHit);
  ok(E.locate(18.5, 79.5) === null, 'point far outside coverage returns null');
  ok(E.locate(17.40, 78.45) !== null, 'central Hyderabad resolves');
  ok(Math.abs(E.hav(17.4, 78.4, 17.4, 78.5) - 10600) < 300, 'haversine ~10.6 km per 0.1 deg lon at 17.4N');

  // ---- model lookups ----
  for (const w of D.wards.slice(0, 20)) {
    const d100 = E.depthAt(w.id, 100), d192 = E.depthAt(w.id, 192), d300 = E.depthAt(w.id, 300);
    ok(d100 <= d192 + 1e-9 && d192 <= d300 + 1e-9, `depth monotonic in rain (ward ${w.id})`, [d100, d192, d300].join('/'));
    ok(E.depthAt(w.id, 0) === 0, 'depth is 0 at 0 mm');
  }

  // ---- reports at every ward centroid: no NaN, sensible ranges ----
  const rows = [];
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]);
    ok(r.ok, `report ok @ ward ${w.id}`);
    if (!r.ok) continue;
    for (const k of ['water', 'motor', 'prop']) {
      const s = r.scores[k].score;
      ok(Number.isFinite(s) && s >= 0 && s <= 100, `${k} score in 0..100 (ward ${w.id})`, s);
    }
    ok(Number.isFinite(r.scores.dev.score) && r.scores.dev.score >= 0 && r.scores.dev.score <= 100, `dev score in range (ward ${w.id})`, r.scores.dev.score);
    ok(r.buyer.flags.length >= 1, 'buyer has at least one flag');
    for (const p of r.scores.water.parts) if (p.v != null) ok(p.v >= 0 && p.v <= 1, `factor ${p.id} value in 0..1`, p.v);
    ok(r.pillars && Number.isFinite(r.pillars.score) && r.pillars.score >= 0 && r.pillars.score <= 100, `location score in range (ward ${w.id})`, r.pillars && r.pillars.score);
    for (const it of r.pillars.items) if (it.v != null) ok(it.v >= -1e-9 && it.v <= 1 + 1e-9, `pillar ${it.id} in 0..1 (ward ${w.id})`, it.v);
    rows.push({ loc: r.pillars.score, id: w.id, name: w.name, pct: r.setu.pct, water: r.scores.water.score, motor: r.scores.motor.score, prop: r.scores.prop.score, dev: r.scores.dev.score, wt: r.tiers.water.letter, mt: r.tiers.motor.letter, pt: r.tiers.prop.letter, hosp: r.fac.hospital.nearest ? r.fac.hospital.nearest.d : null });
  }
  // water score should rise with susceptibility percentile
  const sorted = [...rows].sort((a, b) => a.pct - b.pct), lo = sorted.slice(0, 30), hi = sorted.slice(-30);
  const avg = (a, k) => a.reduce((s, x) => s + x[k], 0) / a.length;
  ok(avg(hi, 'water') > avg(lo, 'water') + 15, 'high-susceptibility wards score clearly riskier than low ones', avg(hi, 'water').toFixed(0) + ' vs ' + avg(lo, 'water').toFixed(0));
  const farHosp = rows.filter(r => r.hosp != null && r.hosp > 5000).length;
  ok(farHosp <= 10, 'at most 10 ward centroids > 5 km from any mapped hospital', farHosp);

  // ---- golden locations ----
  const G = JSON.parse(fs.readFileSync(path.join(__dirname, 'golden.json'), 'utf8'));
  for (const g of G) {
    const r = await E.report(g.lat, g.lon);
    ok(r.ok === !g.outside, `golden ${g.name}: coverage`);
    if (g.extended) ok(r.ok && r.outside === true && r.pillars.score > 0, `golden ${g.name}: peripheral report is built and flagged outside the flood model`);
    if (g.extended && r.ok) { ok(r.scores.water.parts.filter(p => p.id === 'sus')[0].v == null, `golden ${g.name}: flood-susceptibility not applied outside wards`); ok(!r.buyer.flags.some(f => /flood/i.test(f.t) && f.t.startsWith('Heavy')), `golden ${g.name}: no flood-depth flag outside wards`); }
    if (!r.ok) continue;
    if (g.minPct != null) ok(r.setu.pct >= g.minPct, `golden ${g.name}: susceptibility pct >= ${g.minPct}`, r.setu.pct);
    if (g.maxPct != null) ok(r.setu.pct <= g.maxPct, `golden ${g.name}: susceptibility pct <= ${g.maxPct}`, r.setu.pct);
    if (g.lakeBand) ok(g.lakeBand.includes(E.lakeBand(r.water).band), `golden ${g.name}: lake band in [${g.lakeBand}]`, E.lakeBand(r.water).band + ' ' + (r.water.lake ? Math.round(r.water.lake.d) + 'm ' + r.water.lake.name : ''));
    if (g.inundWithinM) ok(r.gov.inund && r.gov.inund.d <= g.inundWithinM, `golden ${g.name}: listed inundation area within ${g.inundWithinM} m`, r.gov.inund && Math.round(r.gov.inund.d));
    if (g.nalaWithinM) ok(r.gov.nala && r.gov.nala.d <= g.nalaWithinM, `golden ${g.name}: mapped nala within ${g.nalaWithinM} m`, r.gov.nala && Math.round(r.gov.nala.d));
    if (g.nearHospitalM) ok(r.fac.hospital.nearest && r.fac.hospital.nearest.d <= g.nearHospitalM, `golden ${g.name}: hospital within ${g.nearHospitalM} m`, r.fac.hospital.nearest && Math.round(r.fac.hospital.nearest.d));
  }

  // ---- report pages render cleanly for every ward and every lens ----
  const PER = { rain_vehicle: { label: 'Vehicle damaged in rain flooding', rain: true }, rain_home: { label: 'Home', rain: true }, collision: { label: 'Collision', rain: false }, theft: { label: 'Theft', rain: false }, fire: { label: 'Fire', rain: false } };
  const fcFake = Array.from({ length: 7 }, (_, i) => ({ date: '2026-10-1' + i, mm: i * 20, prob: 50 }));
  let renderBad = 0, rendered = 0;
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]); if (!r.ok) continue;
    for (const lens of ['customer', 'agent', 'insurer']) for (const unlocked of [false, true]) for (const withData of [false, true]) {
      const S = { r, label: '', unlocked: { customer: unlocked, agent: unlocked, insurer: true }, cust: withData ? { price: '9000000', area: '1200', brokerage: '1' } : { price: '', area: '', brokerage: '' },
        agent: withData ? { ask: '9500', area: '1200', comps: '8800, 9200', guide: '60000', fee: '1' } : { ask: '', area: '', comps: '', guide: '', fee: '' },
        claim: { peril: 'rain_vehicle', date: '2020-10-13', amount: '', out: withData ? E.claimCheck(r, { onDay: 90, max: 90, sum3: 100, days: [{ date: '2020-10-12', mm: 9 }, { date: '2020-10-13', mm: 90 }, { date: '2020-10-14', mm: 13 }] }, 'rain_vehicle') : null, busy: false },
        ai: { q: '', a: '', think: false }, fc: withData ? fcFake : null, air: withData ? { aqi: 80, band: 'Moderate' } : null, line: ['motor', 'prop', 'health'][w.id % 3], PERILS: PER };
      let html; try { html = Rep.render(lens, S); } catch (e) { html = 'THROW ' + e.message; }
      rendered++;
      if (/undefined|NaN|\[object|Infinity|THROW/.test(html.replace(/[^>]*aria-label="[^"]*"/g, ''))) { renderBad++; if (renderBad <= 5) fails.push(`report ${lens} ward ${w.id} unlocked=${unlocked} data=${withData} has bad token: ` + (html.match(/.{40}(undefined|NaN|\[object|Infinity|THROW).{40}/) || [''])[0]); }
    }
  }
  // peripheral addresses (outside the 145 wards) must also render cleanly in every lens
  for (const [la, lo] of [[17.5656, 78.4514], [17.2403, 78.4294], [17.5322, 78.2644], [17.6, 78.55]]) {
    const r = await E.report(la, lo); if (!r.ok) continue;
    for (const lens of ['customer', 'agent', 'insurer']) for (const unlocked of [false, true]) {
      const S = { r, label: 'x', unlocked: { customer: unlocked, agent: unlocked, insurer: true }, cust: { price: '9000000', area: '1200', brokerage: '1' }, agent: { ask: '9500', area: '1200', comps: '8800, 9200', guide: '', fee: '1' },
        claim: { peril: 'rain_vehicle', date: '2020-10-13', amount: '', out: E.claimCheck(r, { onDay: 90, max: 90, sum3: 100, days: [{ date: '2020-10-13', mm: 90 }] }, 'rain_vehicle'), busy: false }, ai: { q: '', a: '', think: false }, fc: fcFake, air: { aqi: 80, band: 'Moderate' }, line: 'motor', PERILS: PER };
      let html; try { html = Rep.render(lens, S); } catch (e) { html = 'THROW ' + e.message; }
      rendered++;
      if (/undefined|NaN|\[object|Infinity|THROW/.test(html.replace(/[^>]*aria-label="[^"]*"/g, ''))) { renderBad++; fails.push(`outside report ${lens} (${la},${lo}) has bad token: ` + (html.match(/.{40}(undefined|NaN|\[object|Infinity|THROW).{40}/) || [''])[0]); }
    }
  }
  ok(renderBad === 0, `all ${rendered} rendered report variants are free of undefined/NaN/[object]`, renderBad + ' bad');


  // ---- evidence layers: data integrity, coordinate systems, units, missing values ----
  ok(D.gwSt.length >= 1000, 'groundwater stations loaded', D.gwSt.length);
  ok(D.gwSt.every(x => x.lat >= 15.5 && x.lat <= 20 && x.lon >= 77 && x.lon <= 82), 'every groundwater station has a plausible Telangana lat/lon (swapped coordinates were fixed)');
  ok(D.gwSt.every(x => x.latest != null && x.latest >= 0 && x.latest <= 120), 'groundwater depths are metres below ground, 0..120');
  const gwKey = new Set(); let gwDup = 0; for (const x of D.gwSt) { const k = x.lat.toFixed(3) + ',' + x.lon.toFixed(3); if (gwKey.has(k)) gwDup++; gwKey.add(k); }
  ok(gwDup === 0, 'no two groundwater stations share a placeholder coordinate', gwDup);
  ok(D.gwSt.filter(x => x.lat >= 17.2 && x.lat <= 17.65 && x.lon >= 78.2 && x.lon <= 78.7).length >= 80, 'at least 80 clean groundwater stations in the Hyderabad area');
  ok(D.gwSt.filter(x => x.district.toUpperCase() === 'HYDERABAD').every(x => x.lat >= 17.30 && x.lat <= 17.52 && x.lon >= 78.30 && x.lon <= 78.62), 'Hyderabad-district stations sit inside the city');
  ok(D.gwSt.every(x => x.trend == null || Math.abs(x.trend) < 15), 'groundwater trends are in a sane range (m/yr)');
  ok(D.gwSt.some(x => x.village === 'Bahadurpura' && x.latest != null), 'the shallow Bahadurpura reference well (matches the official report minimum) is present');
  ok(D.gwqS.length >= 5000 && D.gwqS.every(x => x.lat >= 15.5 && x.lat <= 20 && x.lon >= 77 && x.lon <= 82), 'groundwater-quality samples loaded with valid positions', D.gwqS.length);
  ok(D.gwqS.every(x => (x.f == null || (x.f >= 0 && x.f <= 20)) && (x.no3 == null || (x.no3 >= 0 && x.no3 <= 1500)) && (x.ph == null || (x.ph >= 3 && x.ph <= 12))), 'groundwater-quality values are physically possible (F, NO3, pH)');
  ok(D.landfill.length === 11 && D.landfill.filter(l => l.ha >= 20).length === 1, 'landfill list: 11 sites, exactly one large (the Malkaram legacy dump yard)', D.landfill.map(l => l.ha.toFixed(1)).join(','));
  ok((D.civic.power || []).reduce((a, c) => a + c[2], 0) > 3000 && (D.civic.choke || []).length >= 80 && (D.civic.rehab || []).length >= 90, 'civic layers loaded (power events, choke points, rehab centres)');
  ok(D.storm.events.length === 8 && Object.keys(D.storm.wards).length === 145, 'storm history covers 8 events x 145 wards');
  const oct20 = D.storm.events.find(e => e.id === '2020-10-13'); ok(oct20 && oct20.city_mean_mm >= 190 && oct20.city_mean_mm <= 230, 'Oct 2020 mandal rainfall averages about 190-230 mm (matches the reference storm)', oct20 && oct20.city_mean_mm);
  ok(D.heat && D.heat.lst.length === D.heat.meta.nx * D.heat.meta.ny, 'heat grid size matches its metadata');
  const hv = D.heat.lst.filter(x => x != null); ok(hv.length > 60000, 'heat grid has >60k valid cells', hv.length);
  const hm = hv[hv.length >> 1]; ok(D.heatSorted[D.heatSorted.length >> 1] / 10 > 36 && D.heatSorted[D.heatSorted.length >> 1] / 10 < 46, 'median dry-season surface temperature is 36-46 C', D.heatSorted[D.heatSorted.length >> 1] / 10);
  const hsLake = E.heatFacts(17.4235, 78.4745), hsCity = E.heatFacts(17.3616, 78.4747);
  ok(hsLake && hsCity && hsLake.lst < hsCity.lst - 5, 'physics check: Hussain Sagar water is much cooler than the old city', hsLake && hsCity && (hsLake.lst + ' vs ' + hsCity.lst));
  const kbr = E.heatFacts(17.4170, 78.4240); ok(kbr && kbr.ndvi > 0.28, 'physics check: KBR National Park is green (NDVI > 0.28)', kbr && kbr.ndvi);

  // ---- TGRAC land / geology / utility layers ----
  ok(D.land.gwp.length >= 1500 && (D.land.gwp_attrs || []).length >= 50 && D.land.gwp.every(u => Number.isInteger(u.i) && D.land.gwp_attrs[u.i]), 'groundwater-potential units loaded and every unit points at a valid attribute row', D.land.gwp.length);
  ok(D.land.gwp.every(u => u.r.every(ring => ring.length >= 4 && ring.every(p => p[0] > 17 && p[0] < 18 && p[1] > 78 && p[1] < 79))), 'land polygons are [lat, lon] inside the study box (coordinate order check)');
  ok(D.land.lost.length >= 250 && D.land.forest.length >= 50 && D.land.tx.length >= 100 && D.land.sub.length >= 40 && D.land.endow.length >= 300, 'lost-tank, forest, transmission, substation and endowment layers loaded');
  const lf1 = E.evidence(await E.report(17.2403, 78.4294)); ok(lf1.sections[4].findings.some(f => f.id === 'lost' && f.level === 'concern'), 'golden: the Shamshabad pin sits on a recorded disappeared tank (matches the live service probe)');
  const lf2 = E.evidence(await E.report(17.4401, 78.3489)); ok(lf2.sections[1].findings.some(f => f.id === 'gwp' && f.kind === 'official'), 'golden: Gachibowli has a groundwater-potential unit');
  ok(lf2.sections[2].findings.some(f => f.id === 'tx' && /220/.test(f.value)), 'golden: a 220 kV line is found near Gachibowli');

  // ---- evidence report: five sections, honest fields, no NaN, severity rules ----
  const LV = new Set(['concern', 'watch', 'good', 'info', 'unknown']), KD = new Set(['observed', 'official', 'modelled', 'estimate', 'indicative', 'reference', 'unavailable']), CF = new Set(['high', 'medium', 'low', 'unavailable']);
  let evBad = 0, evN = 0, evGw = 0;
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]); if (!r.ok) continue;
    ok(r.ev && r.ev.sections.length === 5 && ['hazards', 'water', 'infra', 'live', 'land'].every((id, i) => r.ev.sections[i].id === id), `evidence has the five sections (ward ${w.id})`);
    for (const sec of r.ev.sections) {
      ok(['Concern', 'Watch', 'Good', 'Unknown'].includes(sec.rating), `section rating valid (${sec.id}, ward ${w.id})`);
      const hiConcern = sec.findings.some(f => f.level === 'concern' && ['sus', 'depth', 'storms', 'lake', 'nala', 'inund', 'hy', 'hmda', 'ftl', 'gwdepth', 'gwpre', 'gwtrend', 'gwf', 'gwno3', 'gwtds', 'acc_hospital', 'landfill'].includes(f.id));
      if (hiConcern) ok(sec.rating === 'Concern', `a high-severity concern is never averaged away (${sec.id}, ward ${w.id})`, sec.rating);
      for (const f of sec.findings) {
        evN++;
        const text = [f.label, f.value, f.note, f.next, f.source, f.period, f.res].join(' ');
        if (!LV.has(f.level) || !KD.has(f.kind) || !CF.has(f.conf) || !f.label || !f.value || /NaN|undefined|Infinity|\[object/.test(text)) { evBad++; if (evBad <= 5) fails.push(`bad evidence finding ${f.id} ward ${w.id}: ${f.level}/${f.kind}/${f.conf} ${text.slice(0, 80)}`); }
        if (['concern', 'watch', 'good'].includes(f.level) && f.conf === 'unavailable') { evBad++; fails.push(`rated finding with unavailable confidence: ${f.id} ward ${w.id}`); }
        if (f.level === 'unknown' && f.kind !== 'unavailable') { evBad++; fails.push(`unknown finding not marked unavailable: ${f.id} ward ${w.id}`); }
        if (f.id === 'gwdepth' && f.kind === 'estimate') { evGw++; const g = E.gwFacts(w.c[1], w.c[0]); if (!(g.n3 >= 3 && !g.wide)) { evBad++; fails.push(`groundwater area estimate shown with too few or disagreeing wells, ward ${w.id}`); } }
      }
    }
  }
  ok(evBad === 0, `all ${evN} evidence findings are well-formed (no NaN, valid level/kind/confidence, unknown never silently zero)`, evBad + ' bad');
  ok(evGw >= 30, 'groundwater area estimates are produced for a good share of wards (and only with >=3 agreeing wells)', evGw);
  const hs = await E.report(17.4235, 78.4745);
  ok(hs.ev.sections[0].findings.some(f => f.id === 'lake' && f.level === 'concern'), 'golden: a pin inside Hussain Sagar is a lake concern');
  ok(hs.ev.sections[4].findings.some(f => f.id === 'plot' && f.level === 'unknown' && f.kind === 'unavailable'), 'plot identity is reported as not available, never invented');
  const farGw = E.gwFacts(17.55, 78.69); ok(farGw && Number.isFinite(farGw.nearest.d) && ['medium', 'low', 'unavailable'].includes(farGw.conf), 'groundwater lookup returns a bounded confidence far from stations');
  const sparse = await E.report(17.2403, 78.4294); ok(sparse.ev.sections[1].findings.every(f => !(f.id === 'gwdepth' && f.kind === 'estimate' && E.gwFacts(17.2403, 78.4294).n3 < 3)), 'no groundwater area estimate where wells are sparse (Shamshabad)');
  ok(Rep.render('customer', { r: hs, label: '', unlocked: { customer: true, agent: true, insurer: true }, cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: null, line: 'motor', PERILS: PER, open: {} }).includes('Details by topic'), 'customer report page contains the evidence report (details by topic)');


  // ---- batch 2: exports exist (guards against a function being lost in an edit) ----
  for (const fn of ['rainFacts', 'analogFacts', 'tankFacts', 'streamFacts', 'checklist', 'roadAccess', 'evidence', 'gwFacts', 'gwqFacts', 'civicFacts', 'heatFacts'])
    ok(typeof E[fn] === 'function', `engine exports ${fn}`);

  // ---- tanks and streams: integrity, units, duplicates, coordinates ----
  const TKS = D.tankL.tanks, STR = D.tankL.streams, inBox = p => p[0] > 17 && p[0] < 18 && p[1] > 78 && p[1] < 79;
  ok(TKS.length >= 2000 && STR.length >= 1000, 'tank and stream layers loaded', TKS.length + '/' + STR.length);
  ok(TKS.every(t => t.r[0].length >= 4 && t.r[0].every(inBox)), 'tank polygons are [lat, lon] inside the study box');
  ok(new Set(TKS.map(t => t.id)).size === TKS.length, 'tank record ids are unique (no duplicated records)');
  const bbKey = new Set(); let dupBox = 0; for (const t of TKS) { const k = t._b.map(v => v.toFixed(5)).join(',') + '|' + t.a[1]; if (bbKey.has(k)) dupBox++; bbKey.add(k); }
  ok(dupBox === 0, 'no two tank records share the same outline and area', dupBox);
  ok(TKS.every(t => ['L', 'P', 'T', 'D', null].includes(t.a[4]) && ['L', 'P', 'T', 'D', null].includes(t.a[5])), 'tank status codes are valid');
  ok(TKS.filter(t => t.a[3] != null).every(t => t.a[1] > 0 && t.a[2] > 0 && Math.abs(t.a[3] - t.a[1] * t.a[2] / 2) / t.a[3] < .02), 'every stored capacity follows the source formula area x bund / 2 (units: m2, m, m3)');
  ok(TKS.filter(t => t.a[3] == null).length > 1000, 'most tanks correctly have no capacity figure (not invented)', TKS.filter(t => t.a[3] == null).length);
  ok(STR.every(x => (x.o == null || (x.o >= 2 && x.o <= 6)) && x.p.every(path => path.length >= 2 && path.every(inBox))), 'stream orders 2..6 and positions inside the box');

  // ---- tank capacity ----
  const tfHS = E.tankFacts(17.4235, 78.4745);
  ok(tfHS.nearest && tfHS.nearest.inside && Math.abs(tfHS.capM3 / 1e6 - 22.95) < 1.2 && tfHS.nCap + tfHS.nNoCap === tfHS.n2, 'Hussain Sagar pin: inside its tank record, capacity about 22.95 million m3, counts consistent', JSON.stringify([tfHS.n2, tfHS.nCap, tfHS.nNoCap, tfHS.capM3]));
  const tfNone = E.tankFacts(18.5, 79.5); ok(tfNone.n2 === 0 && tfNone.nearest === null && tfNone.capM3 === 0, 'missing-data case: no tank within 2 km gives zero counts and no nearest, not a crash');
  let tfBad = 0; for (const w of D.wards) { const t = E.tankFacts(w.c[1], w.c[0]); const ids2 = t.list.map(x => x.t.id); if (new Set(ids2).size !== ids2.length || t.nCap + t.nNoCap !== t.n2 || t.enc2023 > t.n2 || t.capM3 < 0 || Math.abs(t.capM3 - t.list.filter(x => x.t.a[3] != null).reduce((a, x) => a + x.t.a[3], 0)) > 1) tfBad++; }
  ok(tfBad === 0, 'for every ward: no tank counted twice, capacity equals the sum of listed capacities, counts consistent', tfBad);

  // ---- stream order ----
  const sfHS = E.streamFacts(17.4235, 78.4745); ok(sfHS.nearest && sfHS.nearest.o >= 2, 'Hussain Sagar vicinity has a mapped stream with an order');
  const sfNone = E.streamFacts(18.5, 79.5); ok(sfNone.nearest === null && sfNone.n300 === 0, 'missing-data case: no stream far from the network');
  const evHS = (await E.report(17.4235, 78.4745)).ev;
  const stF = evHS.sections[0].findings.find(f => f.id === 'stream'); ok(stF && /does not prove|not prove|terrain/.test(stF.note + ' ' + stF.value), 'stream finding states that stream order does not prove a buried channel');
  const tkF = evHS.sections[1].findings.find(f => f.id === 'tankstore'); ok(tkF && !/\blost\b/i.test(tkF.value + tkF.note) && /not measured|estimate/i.test(tkF.note), 'tank-storage finding never says storage is "lost" and says capacity is an estimate');

  // ---- heavy rain and analogs ----
  const RS = D.rainstats;
  ok(RS.meta.threshold_mm === 64.5 && /complete monsoon/.test(RS.meta.scope) && RS.meta.min_month_coverage === 0.9 && RS.meta.years_considered[0] === 2018 && RS.meta.cleaning.stray_out_of_month_rows > 0, 'rain statistics are complete-monsoon statistics with the cleaning counts recorded');
  ok(Object.values(RS.mandals).every(m => m.years.length >= 5 && m.per_year.length === m.years.length && m.per_year.every(x => x[0] >= 2018 && x[0] <= 2025 && x[1] >= 0 && x[2] > 100 && x[3] > 0) && Math.abs(m.mean_over - m.per_year.reduce((a, x) => a + x[1], 0) / m.per_year.length) < 0.01 && m.min_over <= m.mean_over && m.mean_over <= m.max_over && m.top.length <= 8 && (!m.top.length || m.wettest[0] >= m.top[0][1]) && m.excluded_years.every(x => x[1] < 0.9)), 'rain statistics are internally consistent: per-year rows, mean, range, wettest day, and every excluded year really is under 90% coverage');
  const khai = RS.mandals['KHAIRATABAD']; ok(khai && khai.wettest[0] === 174.5 && khai.wettest[1] === '2020-10-14' && !khai.years.includes(2025) && khai.mean_over > 0.5 && khai.mean_over < 4, 'golden: Khairatabad wettest day is 174.5 mm on 2020-10-14; 2025 is excluded (incomplete June file); about 1-3 heavy days a monsoon, not the 8 an event-months-only count would suggest');
  ok(E.rainFacts(91) && E.rainFacts(91).mean_over > 0 && E.rainFacts(91).years.length >= 5, 'rainFacts returns a record for a normal ward'); ok(E.rainFacts(99999) === null, 'rainFacts is null for an unknown ward'); ok(Object.keys(RS.mandals).length === 27, 'every one of the 27 ward-matched mandals has at least one complete monsoon');
  ok(!E.ANALOG_EVENTS.includes('2016-09') && !E.ANALOG_EVENTS.includes('2025-06-12'), 'analogs exclude the month-only 2016 date and the incomplete June 2025 rainfall month');
  let anBad = 0, anTooFew = 0; for (const w of D.wards) { const a = E.analogFacts(w.id); if (!a) continue; if (a.n > 6 || a.k > a.n || a.hit.some(x => x.mm < a.mm)) anBad++; if (a.n < 3) anTooFew++; }
  ok(anBad === 0, 'analog counts are consistent for every ward (k <= n <= 6, only storms at or above the threshold)', anBad);
  let anWording = 0; for (const w of D.wards.slice(0, 60)) { const r = await E.report(w.c[1], w.c[0]); const f = r.ev.sections[0].findings.find(x => x.id === 'analog'); const a = r.outside ? null : E.analogFacts(r.wid); if (f && a && ((a.n < 3 && !/too few/.test(f.value)) || (a.n >= 3 && /too few/.test(f.value)) || /\d+ ?% (chance|probability|likely)|probability of|will flood|likely to flood|chance of flood/i.test(f.value + f.note))) anWording++; }
  ok(anWording === 0, 'analog wording: "too few" exactly when under 3 storms, and never a probability claim', anWording);

  // ---- checklist ----
  const KNOWN = new Set(Object.keys({ plot: 1, zoning: 1, perm: 1, ftl: 1, hy: 1, hmda: 1, lost: 1, forest: 1, endow: 1, nala: 1, nalaenc: 1, widen: 1, sus: 1, depth: 1, storms: 1, inund: 1, lake: 1, pocket: 1, stream: 1, gwdepth: 1, gwpre: 1, gwtrend: 1, gwrec: 1, gwf: 1, gwno3: 1, gwtds: 1, gwq: 1, gwp: 1, supply: 1, landfill: 1, tx: 1, choke: 1, acc_hospital: 1, acc_metro: 1, heat: 1, price: 1 }));
  let ckBad = 0, ckN = 0, ckMissing = 0;
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]); const c = E.checklist(r); ckN += c.items.length;
    const keys = c.items.map(i => i.key); if (new Set(keys).size !== keys.length) { ckBad++; fails.push('duplicate checklist item ward ' + w.id); }
    ok(c.std.length === 2 && c.std.every(i => i.trigger.level === 'standard'), `two standard checks are present and labelled as such (ward ${w.id})`);
    for (const it of [...c.items, ...c.std]) {
      const miss = !it.action || !it.why || !it.where || !it.where.name || !['legal', 'flood', 'water', 'infra'].includes(it.cat);
      const lie = it.where && it.where.url && !['https://bhubharati.telangana.gov.in/', 'https://lakes.hmda.gov.in/', 'https://www.hmda.gov.in/planning-2/', 'https://www.hmda.gov.in/dpms/'].includes(it.where.url);
      const unsafe = /unsafe|dangerous|illegal/i.test(it.why + it.action + it.trigger.label);
      if (miss || lie || unsafe) { ckBad++; fails.push(`bad checklist item ${it.key} ward ${w.id}: miss=${miss} unverifiedUrl=${lie} alarmist=${unsafe}`); }
    }
    // every concern / watch finding that has a template must be in the checklist, and no 'good' finding may be
    const fs = r.ev.sections.flatMap(sec => sec.findings);
    for (const f of fs) { const inC = c.items.some(i => i.trigger.id === f.id || i.key === f.id); if ((f.level === 'concern' || f.level === 'watch') && KNOWN.has(f.id) && !inC && !(f.id === 'acc_hospital' && false)) { ckMissing++; if (ckMissing < 4) fails.push(`concern/watch finding missing from checklist: ${f.id} ward ${w.id}`); } if (f.level === 'good' && c.items.some(i => i.trigger.id === f.id)) { ckBad++; fails.push(`good finding in checklist: ${f.id} ward ${w.id}`); } }
    // transient gaps (elevation or routing still loading) must never become action items
    if (c.items.some(i => ['pocket', 'acc_hospital', 'acc_metro', 'acc_bus', 'acc_school', 'acc_market', 'stream', 'heat'].includes(i.key) && i.gap)) { ckBad++; fails.push('transient gap became a checklist item ward ' + w.id); }
  }
  ok(ckBad === 0 && ckMissing === 0, `all ${ckN} checklist items are well-formed, complete for concerns/watch items, never for good findings, and never alarmist`, ckBad + ' bad, ' + ckMissing + ' missing');
  const sh = await E.report(17.2403, 78.4294); const shC = E.checklist(sh); ok(shC.items.some(i => i.key === 'lost' && i.trigger.level === 'concern') && shC.items.some(i => i.key === 'plot' && i.gap), 'golden: Shamshabad gets a disappeared-tank action and a plot-identity data-gap action');
  const healthy = await E.report(17.4170, 78.4240); ok(E.checklist(healthy).items.every(i => i.trigger.level !== 'good'), 'checklist never carries a good finding');

  // ---- map popups: every layer's popup shows source, data period, resolution and confidence; text is escaped ----
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'map.js'), 'utf8') + '\n;globalThis.MapKit = MapKit;', sandbox);
  const MK = sandbox.MapKit, need = h => ['Source', 'Data period', 'Resolution', 'Confidence'].every(k => h.includes(k));
  const sample = {
    ev_wells: D.gwSt[0], ev_gwp: { attrs: D.land.gwp_attrs[0] }, ev_hv: { line: { name: 'X <b>KV', kv: '220', len: '3' } }, ev_lost: { a: ['Tank', 1.2] }, ev_streams: { o: 3, n: 'T <i>' },
    ev_tankcap: { a: ['A & B', 10000, null, null, 'L', 'P', 'SOI Toposheet', '1940', 'Tank', 'V', 'M'] }, ev_tankhy: { name: 'N', village: 'V', s14: 'L', s23: 'TB' }, ev_heat: { lst: 41.2, ndvi: .2, pct: .5 }
  };
  for (const [k, f] of Object.entries(sample)) { const h = MK.popupFor(k, f, D); ok(h && need(h), `map popup for ${k} shows source, data period, resolution and confidence`); }
  ok(!MK.popupFor('ev_hv', sample.ev_hv, D).includes('X <b>KV') && MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('A &amp; B') && MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('not available'), 'map popups escape HTML and say "not available" when capacity is missing');
  ok(MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('not verified encroachment') && MK.popupFor('ev_tankhy', sample.ev_tankhy, D).includes('not a legal'), 'tank popups separate a mapped outline / satellite class from verified or legal encroachment');
  ok(MK.EV_KINDS.length === 7 && MK.EV_KINDS.every(k => MK.evInfo(k, D) && MK.evInfo(k, D).note && MK.evInfo(k, D).swatch.length), 'every evidence layer has a legend with swatches and a dataset-age note');

  // ---- routing: failover between hosts, caching, and honest failure ----
  const realFetch2 = sandbox.fetch; let calls = [];
  const okTable = u => ({ ok: true, json: async () => { const n = (u.match(/destinations=([\d;]+)/) || [0, '1'])[1].split(';').length; return { code: 'Ok', durations: [Array.from({ length: n }, (_, i) => 120 + i * 30)], distances: [Array.from({ length: n }, (_, i) => 1500 + i * 400)] }; } });
  sandbox.fetch = u => { calls.push(u); return /router\.project-osrm\.org/.test(u) ? Promise.reject(new Error('down')) : Promise.resolve(okTable(u)); };
  const acc1 = await E.roadAccess(17.4101, 78.4101); ok(acc1 && acc1.hospital && acc1.hospital.host === 'routing.openstreetmap.de' && calls.length === 2, 'routing fails over to the second host when the first is down');
  const nCalls = calls.length; const acc2 = await E.roadAccess(17.4101, 78.4101); ok(calls.length === nCalls && acc2 === acc1, 'routing result is cached for repeat lookups');
  sandbox.fetch = () => Promise.resolve({ ok: false, status: 503, json: async () => ({}) }); const acc3 = await E.roadAccess(17.4301, 78.4301); ok(acc3 === null, 'both routing hosts down returns null (the report then says unavailable, no invented time)');
  sandbox.fetch = () => Promise.resolve({ ok: true, json: async () => ({ code: 'NoRoute' }) }); ok(await E.roadAccess(17.4501, 78.4501) === null, 'a routing error code returns null');
  sandbox.fetch = realFetch2;
  const noAcc = await E.report(17.4601, 78.4601); ok(noAcc.ev.sections[2].findings.filter(f => f.id.startsWith('acc_')).every(f => f.level === 'unknown' && f.kind === 'unavailable'), 'without routing data, road-travel findings are unknown/unavailable, never a made-up time');
  ok(Rep.render('customer', { r: noAcc, label: '', unlocked: { customer: true, agent: true, insurer: true }, cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: null, line: 'motor', PERILS: PER, open: {} }).includes('Before you pay'), 'customer report page contains the due-diligence checklist');


  // ---- compare two addresses: evidence only, symmetric, honest about gaps ----
  const cA = await E.report(17.4235, 78.4745), cB = await E.report(17.4401, 78.3489), cC = await E.report(17.63, 78.48), cD = await E.report(17.3616, 78.4747);
  const same = E.compare(cA, cA);
  ok(same.sections.every(sec => sec.rows.every(rw => rw.cmp === 'same' || rw.cmp === 'both-unknown')) && same.biggest.length === 0 && same.notComparable.length === 0, 'comparing an address with itself finds no differences and no gaps');
  const ab = E.compare(cA, cB), ba = E.compare(cB, cA);
  const flipK = k => ({ 'a-more-severe': 'b-more-severe', 'b-more-severe': 'a-more-severe', 'only-a': 'only-b', 'only-b': 'only-a' }[k] || k);
  ok(ab.sections.every((sec, i) => sec.rows.length === ba.sections[i].rows.length && sec.rows.every(rw => ba.sections[i].rows.some(r2 => r2.id === rw.id && r2.cmp === flipK(rw.cmp)))), 'comparison is symmetric: swapping A and B flips every verdict and nothing else');
  ok(ab.notComparable.length === ba.notComparable.length && ab.biggest.length === ba.biggest.length, 'swap keeps the counts of gaps and differences');
  const nc = ab.notComparable.find(rw => (rw.a.level === 'unknown') !== (rw.b.level === 'unknown'));
  ok(nc && ['concern', 'watch', 'good', 'info'].includes((nc.a.level === 'unknown' ? nc.b : nc.a).level), 'one-sided gaps (unknown vs known) are labelled not comparable, not better or worse', nc && nc.id);
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'not-comparable').every(rw => rw.a.level === 'unknown' || rw.b.level === 'unknown' || (rw.a.level === 'info') !== (rw.b.level === 'info')), 'only unknown or unrated-vs-rated rows are marked not comparable');
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'a-more-severe').every(rw => ({ concern: 3, watch: 2, good: 1 })[rw.a.level] > ({ concern: 3, watch: 2, good: 1 })[rw.b.level]), 'a-more-severe is only used when both are rated and A is the more severe');
  ok(ab.sections.flatMap(sec => sec.rows).filter(rw => rw.cmp === 'both-unknown').every(rw => rw.a.level === 'unknown' && rw.b.level === 'unknown'), 'both-unknown is only used when both sides are unknown');
  const jsonKeys = o => o && typeof o === 'object' ? Object.entries(o).flatMap(([k, v]) => [k, ...jsonKeys(v)]) : [];
  ok(!jsonKeys(ab).some(k => /winner|best|safer|better|score|rank|total_?points/i.test(k)), 'the comparison result has no winner, rank or score field');
  ok(/does not say which address is safer or better/.test(ab.note) && /never a clean bill of health/.test(ab.note), 'the comparison note states it is evidence only and that a gap is not safety');
  const cov = E.coverage(cA); ok(cov.known + cov.unknown === cov.total && cov.pct >= 0 && cov.pct <= 1 && cov.sections.length === 5 && cov.total === cA.ev.total, 'coverage is consistent with the evidence report');
  ok(Math.abs(ab.coverage.a.pct - cov.pct) < 1e-9, 'comparison reports each address\'s own evidence coverage');
  ok(E.compare(cA, cC).sections.flatMap(sec => sec.rows).some(rw => rw.cmp === 'only-a' || rw.cmp === 'only-b'), 'findings shown for only one address (a different ward vs outside the wards) are marked as such');
  let cmpBad = 0, cmpRendered = 0;
  const pairs = []; for (let i = 0; i < 24; i++) pairs.push([D.wards[(i * 7) % 145], D.wards[(i * 11 + 3) % 145]]);
  for (const [wa, wb] of pairs) {
    const ra = await E.report(wa.c[1], wa.c[0]), rb = await E.report(wb.c[1], wb.c[0]); if (!ra.ok || !rb.ok) continue;
    const html = Rep.compare({ cmp: { a: ra, b: rb, la: wa.name, lb: wb.name }, open: {} }); cmpRendered++;
    if (/undefined|NaN|\[object|Infinity/.test(html) || /winner|safer address|better address|recommended/i.test(html.replace(/does not say which address is safer or better/g, '')) || !/Only one address could be checked/.test(html) || !/Where one address is rated worse/.test(html) || !/need attention/.test(html) || (html.match(/class="v-cmphead"|v-card v-cmphead/g) || []).length !== 2) { cmpBad++; fails.push(`compare render problem for wards ${wa.id} vs ${wb.id}: ` + (html.match(/.{30}(undefined|NaN|\[object|Infinity|winner|safer address|better address).{30}/) || [''])[0]); }
  }
  ok(cmpBad === 0 && cmpRendered >= 20, `${cmpRendered} comparison pages render cleanly with no winner wording`, cmpBad + ' bad');
  const sw = E.compare(cD, cD); ok(sw.coverage.a.total === sw.coverage.b.total && sw.checklist.a === sw.checklist.b, 'self-comparison has identical coverage and checklist sizes');

  // ---- validation outcomes are reflected in the report wording ----
  const hz = (await E.report(17.4401, 78.3489)).ev.sections[0].findings;
  const hf = hz.find(f => f.id === 'heat'), sm = hz.find(f => f.id === 'seismic');
  ok(hf && hf.conf === 'low' && /not yet validated/i.test(hf.note), 'heat finding is low confidence and says it is not yet validated against stations');
  ok(sm && sm.level === 'info' && /secondary sources/.test(sm.value) && /newer edition/.test(sm.note), 'seismic line says secondary sources, and that a newer code edition may change the zones');

  // ---- claim check logic ----
  const r0 = await E.report(17.4015, 78.4100);
  const dry = E.claimCheck(r0, { onDay: 0, max: 0.5, sum3: .5, days: [] }, 'rain_vehicle');
  ok(dry.level === 'red', 'dry-day claim is flagged red', dry.verdict);
  const wet = E.claimCheck(r0, { onDay: 90, max: 90, sum3: 100, days: [] }, 'rain_vehicle');
  ok(wet.level === 'green', 'heavy-rain claim in susceptible ward is green', wet.verdict);
  const lowWard = [...rows].sort((a, b) => a.pct - b.pct)[0];
  const rl = await E.report(D.wardById.get(lowWard.id).c[1], D.wardById.get(lowWard.id).c[0]);
  const wl = E.claimCheck(rl, { onDay: 20, max: 20, sum3: 20, days: [] }, 'rain_vehicle');
  ok(wl.level !== 'green', 'moderate rain in least-susceptible ward is not fast-tracked', wl.verdict);

  // =====================================================================================================
  // BATCH 4 — evidence-quality registry, property identity (parcels), planning authority, parcel overlaps, mapped water network
  // =====================================================================================================
  {
    const Q = D.quality, rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8'));
    const ENUM = { validation: ['validated', 'internal-check', 'negative', 'unvalidated', 'not-applicable'], licence: ['ok', 'verify', 'restricted'], nature: ['snapshot', 'periodic', 'history', 'model', 'live', 'reference', 'documents'],
      scope: ['pin', 'parcel', 'nearby', 'area', 'ward', 'mandal', 'locality', 'region', 'live', 'none'] };
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };

    // ---- registry integrity ----
    ok(Q && Q.sources && Q.factors, 'the evidence-quality registry is loaded');
    const srcIds = Object.keys(Q.sources), facIds = Object.keys(Q.factors), usedSrc = new Set(facIds.flatMap(f => Q.factors[f].sources));
    ok(facIds.every(f => Q.factors[f].sources.length && Q.factors[f].sources.every(s => Q.sources[s])), 'every registry finding lists existing sources');
    ok(srcIds.filter(s => s !== 'none').every(s => usedSrc.has(s)), 'every registry source is used by at least one finding', srcIds.filter(s => !usedSrc.has(s) && s !== 'none').join());
    for (const [id, s] of Object.entries(Q.sources)) {
      ok(ENUM.validation.includes(s.validation) && ENUM.licence.includes(s.licence) && ENUM.nature.includes(s.nature), `source ${id} uses only the registry's enumerations`);
      ok(!s.obs || (s.obs.length === 2 && s.obs.every(x => /^\d{4}(-\d{2})?$/.test(x)) && s.obs[0] <= s.obs[1]), `source ${id} observation window is well-formed`);
      ok(s.svc == null || /^\d{4}-\d{2}-\d{2}$/.test(s.svc), `source ${id} service-creation date is a date`);
      ok(s.fetched == null || /^\d{4}-\d{2}-\d{2}$/.test(s.fetched), `source ${id} fetched date is a date`);
      ok(s.validation === 'negative' ? /did not agree|not agree/i.test(s.validation_note) : true, `source ${id}: a failed validation says so in words`);
      ok(s.validation !== 'validated' || s.validation_note.length > 40, `source ${id}: 'validated' states what it was compared with`);
      ok(s.licence === 'ok' || s.licence_note.length > 5, `source ${id}: a restricted or unverified licence is explained`);
      ok(!s.files || s.files.every(f => fs.existsSync(path.join(WEB, 'data', f))), `source ${id}: its data files exist`);
    }
    ok(facIds.every(f => ENUM.scope.includes(Q.factors[f].scope) && Q.factors[f].scope_text.length > 5 && Q.factors[f].label), 'every finding has a scope, a scope description and a label');
    ok(Object.keys(Q.meta.scope).every(k => ENUM.scope.includes(k)) && ENUM.scope.every(k => Q.meta.scope[k]), 'the registry defines exactly the scopes the engine uses');
    // survey dates are kept apart from service-creation dates
    ok(['tgrac_nalas', 'tgrac_gwp', 'tgrac_cadastral', 'hmda_zones', 'hmwssb_network'].every(s => Q.sources[s].svc && !Q.sources[s].obs), 'TGRAC sources carry a service-creation date and NO invented survey date');

    // ---- freshness rules (synthetic, fixed date) ----
    const asOf = new Date(Date.UTC(2026, 9, 24)), fr = (o) => E.freshness({ nature: 'periodic', obs: ['2020-01', '2020-12'], stale_months: 12, ...o }, asOf);
    ok(fr({}) === 'stale' && fr({ obs: ['2026-01', '2026-06'] }) === 'current' && fr({ obs: ['2025-06', '2025-10'] }) === 'aging', 'freshness: periodic data goes current -> aging -> stale by its allowed age');
    ok(fr({ obs: null }) === 'undated' && fr({ nature: 'snapshot', obs: null }) === 'undated', 'freshness: no observation date is "undated", never "current"');
    ok(fr({ nature: 'live' }) === 'live' && fr({ nature: 'reference' }) === 'reference' && fr({ nature: 'documents' }) === 'documents' && fr({ nature: 'model' }) === 'model', 'freshness: live, reference, document and model sources are labelled as such');
    ok(fr({ nature: 'history', obs: ['2017-04', '2018-03'], stale_months: 24 }) === 'stale' && fr({ nature: 'history', obs: ['2020-10', '2026-06'], stale_months: null }) === 'historical', 'freshness: a history that stops long ago is stale; an open-ended record is historical');
    const QT = E.qualityTable(asOf), fl = id => QT.factors.find(f => f.id === id).flags, sf = id => QT.sources.find(s => s.id === id);
    ok(sf('civic_power').freshness === 'stale' && sf('civic_wq').freshness === 'stale' && sf('civic_noise').freshness === 'stale', 'dashboard: the 2017-18 civic records are flagged stale');
    ok(sf('osm').freshness === 'undated' && sf('tgrac_cadastral').freshness === 'undated' && sf('seismic_ref').freshness === 'reference' && sf('openmeteo_air').freshness === 'live', 'dashboard: undated, reference and live sources are labelled correctly');
    ok(fl('heat').includes('failed-validation') && fl('zoning').includes('no-data') && fl('perm').includes('no-data') && fl('supply').includes('no-data'), 'dashboard: failed validation and no-data are flagged');
    ok(fl('storms').includes('restricted-licence') && fl('heavyrain').includes('restricted-licence') && fl('sus').includes('coarse-scope') && fl('plot').includes('unvalidated') && fl('plot').includes('undated'), 'dashboard: licence, scope, validation and dating flags are computed');
    ok(QT.sources.every(s => s.used_by && Array.isArray(s.used_by)) && QT.factors.length === facIds.length, 'dashboard: every source lists the findings that use it');
    ok(E.qualityTable(new Date(Date.UTC(2031, 0, 1))).sources.find(s => s.id === 'gwd_levels').freshness === 'stale', 'dashboard: sources go stale as time passes');
    const ri = E.removalImpact('gwd_levels'); ok(ri.becomeUnknown.includes('gwdepth') && ri.becomeUnknown.includes('gwnear') && !ri.becomeUnknown.includes('sus'), 'removal impact: groundwater findings become unknown, flood findings do not');
    ok(E.removalImpact('tgrac_cadastral').becomeUnknown.includes('plot') && E.removalImpact('tgrac_cadastral').degrade.includes('prohib') && E.removalImpact('nope') === null, 'removal impact: single-source findings become unknown; shared ones degrade; unknown source is null');

    // ---- the engine cannot emit a finding the registry does not list, and findings obey the honesty rules ----
    const places = D.wards.map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.26, 78.43], [17.2403, 78.4294], [17.597, 78.57], [17.514, 78.45]]);
    let nUnreg = 0, nNoScope = 0, nBadConf = 0, nUnavail = 0, nNone = 0, nGood = 0, nFind = 0, nGapEmpty = 0; const unreg = new Set();
    const reports = [];
    for (const [la, lo] of places) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); reports.push(r);
      for (const s of r.ev.sections) for (const f of s.findings) {
        nFind++; const qf = Q.factors[f.id];
        if (!qf) { nUnreg++; unreg.add(f.id); continue; }
        if (!f.scope || f.scope !== qf.scope || !f.scopeText) nNoScope++;
        const ss = qf.sources.map(x => Q.sources[x]);
        if (ss.some(x => x.validation === 'negative') && !['low', 'unavailable'].includes(f.conf)) nBadConf++;
        if (ss.every(x => x.validation === 'unvalidated' || x.validation === 'negative') && f.conf === 'high') nBadConf++;
        if (f.kind === 'unavailable' && !['unknown', 'info', 'watch'].includes(f.level)) nUnavail++;
        if (qf.scope === 'none' && f.level !== 'unknown') nNone++;
        if (qf.sources.includes('none') && ['good', 'concern', 'watch'].includes(f.level)) nGood++;
      }
      for (const g of r.ev.gaps) if (!g.why || !g.label) nGapEmpty++;
    }
    ok(nUnreg === 0, `every finding the engine emits (${nFind} across ${reports.length} places) is in the registry`, [...unreg].join());
    ok(nNoScope === 0, 'every emitted finding carries the scope and scope text from the registry');
    ok(nBadConf === 0, 'a finding resting on a failed or unvalidated source never claims high confidence, and a failed validation is always low confidence', nBadConf);
    ok(nUnavail === 0, 'an "unavailable" finding is never rated good or concern');
    ok(nNone === 0 && nGood === 0, 'a finding with no data source is always unknown, never rated');
    ok(nGapEmpty === 0, 'every "why this report is incomplete" item says what and why');
    ok(reports.every(r => r.ev.gaps.length === r.ev.sections.flatMap(s => s.findings).filter(f => f.level === 'unknown').length + (r.ev.gaps.filter(g => g.id.startsWith('src:')).length)), 'the gaps list is exactly the unknown findings (plus any unloaded sources)');
    ok(reports.every(r => r.ev.identity && r.ev.identity.label && r.ev.identity.text), 'every report states what the property identity is');

    // ---- remove each data source in turn: nothing may turn reassuring ----
    const groups = new Map();
    for (const [id, s] of Object.entries(Q.sources)) if (s.files && s.files.length && id !== 'sethu_model') { const k = s.files.join('+'); (groups.get(k) || groups.set(k, { files: s.files, srcs: [] }).get(k)).srcs.push(id); }
    const RP = [[17.4235, 78.4745], [17.4401, 78.3489], [17.3616, 78.4747], [17.3558, 78.526], [17.514, 78.45], [17.4948, 78.3996], [17.4126, 78.4482], [17.63, 78.48], [17.2403, 78.4294]];
    let groupsTested = 0;
    for (const g of groups.values()) {
      let E2; try { E2 = await freshEngine(g.files); } catch (e) { ok(g.files.includes('hospitals.json'), `source files ${g.files.join('+')}: only a required file may stop the engine from starting`); continue; }
      groupsTested++; const remove = new Set(g.srcs); let rated = [], gapSeen = false;
      for (const [la, lo] of RP) {
        const r = await E2.report(la, lo); if (!r.ok) continue; await E2.attachParcel(r, {});
        gapSeen = gapSeen || g.srcs.every(sid => r.ev.gaps.some(x => x.id === 'src:' + sid));
        for (const s of r.ev.sections) for (const f of s.findings) { const qf = Q.factors[f.id]; if (qf && qf.sources.every(x => remove.has(x)) && ['good', 'watch', 'concern'].includes(f.level)) rated.push(f.id + ':' + f.level); }
      }
      ok(rated.length === 0, `without ${g.files.join('+')} no finding that rests only on it is still rated`, [...new Set(rated)].join());
      ok(gapSeen, `without ${g.files.join('+')} the report lists the missing source under "why incomplete"`);
    }
    ok(groupsTested >= 14, 'the removal test covered every optional data file', groupsTested);

    // ---- planning authority: which plan governs, never what the plot is zoned for ----
    const ZP = { Gachibowli: [17.4401, 78.3489, 'CDA'], Kondapur: [17.46, 78.364, 'CDA'], Kukatpally: [17.4948, 78.3996, 'HUDA'], Uppal: [17.4058, 78.5591, 'HUDA'], 'LB Nagar': [17.3457, 78.5522, 'HUDA'], Miyapur: [17.4969, 78.3548, 'HUDA'],
      Rajendranagar: [17.317, 78.4, 'HUDA'], Shamshabad: [17.2403, 78.4294, 'HADA'], Charminar: [17.3616, 78.4747, 'MCH'], 'Banjara Hills': [17.4126, 78.4482, 'MCH'], Ameerpet: [17.4374, 78.4487, 'MCH'], Secunderabad: [17.4399, 78.4983, 'MCH'], Medchal: [17.63, 78.48, 'HMR'], Shamirpet: [17.597, 78.57, 'HMR'] };
    for (const [n, [la, lo, z]] of Object.entries(ZP)) { const pf = E.planFacts(la, lo); ok(pf && pf.zone === z, `planning authority at ${n} is ${z}`, pf && pf.zone); }
    // HMR is the umbrella region around the others, so only overlaps between the specific authority areas count
    let multi = 0, none = 0, tot = 0; const b = D.plan.zones ? D.parcelIdx.bbox : null;
    for (let la = b[1] + .004; la < b[3]; la += .01) for (let lo = b[0] + .004; lo < b[2]; lo += .01) { tot++; const pf = E.planFacts(la, lo); if (pf.hits.filter(h => h !== 'HMR').length > 1) multi++; if (!pf.zone) none++; }
    ok(multi / tot < .015, 'the specific planning-authority areas barely overlap (boundary slivers only); the wider HMR region is the umbrella around them', `${multi} of ${tot}`);
    ok(none / tot < .5 && none > 0, 'some of the study box lies outside the authority areas, and the engine says so rather than guessing', `${none} of ${tot}`);
    const pfm = E.planFacts(17.63, 78.48); ok(pfm.mandal && pfm.links.some(l => /masterplan\.hmda\.gov\.in\/Masterplan2031\/Content\/.+\.jpg$/.test(l.url)) && pfm.links.every(l => /^https:\/\/(www\.hmda\.gov\.in|masterplan\.hmda\.gov\.in)\//.test(l.url)), 'a pin in the wider HMDA region links the official Master Plan 2031 sheet for its mandal, and only official HMDA addresses');
    ok(E.planFacts(17.3616, 78.4747).links.some(l => /revised-development-plan/.test(l.url)), 'a pin in the old city core links the Revised Development Plan page');
    for (const r of reports) {
      const fz = r.ev.sections.flatMap(s => s.findings), z = fz.find(f => f.id === 'zoning'), pa = fz.find(f => f.id === 'planauth');
      if (z.level !== 'unknown' || z.kind !== 'unavailable' || !/not read/.test(z.value) || z.scope !== 'none') { fails.push('zoning must stay unknown at ' + r.lat); fail++; }
      if (pa.level === 'info' && !/does not say what this plot is zoned for/.test(pa.note)) { fails.push('planauth must say it is not zoning at ' + r.lat); fail++; }
      if (fz.some(f => /zoned (for|as)|land use is|permitted use|residential zone|commercial zone/i.test(f.value))) { fails.push('a finding claims zoning at ' + r.lat); fail++; }
    }
    ok(true, 'zoning stays unknown at every checked place, and the planning-authority finding says it is not zoning');

    // ---- parcels: synthetic cases (exact geometry, deterministic) ----
    const LA = 17.44, LO = 78.35, dlaM = m => m / 110540, dloM = m => m / (111320 * Math.cos(LA * Math.PI / 180));
    const sqr = (la, lo, h) => [[la - dlaM(h), lo - dloM(h)], [la - dlaM(h), lo + dloM(h)], [la + dlaM(h), lo + dloM(h)], [la + dlaM(h), lo - dloM(h)], [la - dlaM(h), lo - dloM(h)]];
    const bbx = ring => [Math.min(...ring.map(p => p[0])), Math.min(...ring.map(p => p[1])), Math.max(...ring.map(p => p[0])), Math.max(...ring.map(p => p[1]))];
    const mkP = (n, v, la, lo, h, code = 0, rem = '') => { const ring = sqr(la, lo, h); return { n, v, m: 'Serilingampalle', code, rem, rings: [ring], _b: bbx(ring) }; };
    const DATA = ps => ({ ok: true, outsideBox: false, parcels: ps });
    const pm = (ps, ref, la = LA, lo = LO) => E.parcelMatch(la, lo, DATA(ps), ref);
    const A = mkP('91/1', 'Gachibowli', LA, LO, 40), N1 = mkP('92', 'Gachibowli', LA, LO + dloM(150), 40), FAR = mkP('500', 'Gachibowli', LA + dlaM(150), LO + dloM(150), 40);
    let m = pm([A, N1], {}); ok(m.status === 'approximate' && m.reason === 'pin-only' && m.parcel.number === '91/1' && m.usable === true, 'parcel: a pin inside one outline with no number is an approximate match, never verified');
    m = pm([A, N1], { survey: '91/1' }); ok(m.status === 'verified' && m.parcel.number === '91/1' && m.usable, 'parcel: pin inside + matching number is a verified match');
    m = pm([A, N1], { survey: ' 091 / 01 ' }); ok(m.status === 'verified', 'parcel: spaces and leading zeros in the number do not matter');
    m = pm([A, N1], { survey: '91/1', village: 'Gachibowli' }); ok(m.status === 'verified' && m.reason === 'number-and-village', 'parcel: number and village both match');
    m = pm([A, N1], { survey: '91/1', village: 'Gachibowle' }); ok(m.status === 'verified', 'parcel: a one-letter spelling variant of the village still matches');
    m = pm([A, N1], { survey: '91/1', village: 'Kondapur' }); ok(m.status === 'none' && m.reason === 'village-mismatch', 'parcel: a different village is no match');
    m = pm([A, N1], { survey: '777' }); ok(m.status === 'none' && m.reason === 'number-mismatch' && m.parcel.number === '91/1' && !m.neighbour, 'parcel: a number that is not mapped nearby is no match and names what the pin is on');
    m = pm([A, N1], { survey: '92' }); ok(m.status === 'none' && m.reason === 'neighbour' && m.neighbour.number === '92' && m.neighbour.d > 50 && m.neighbour.d < 150, 'parcel: the next-door parcel\'s number is "no match", with the neighbour and its distance reported');
    m = pm([A, FAR], { survey: '500' }); ok(m.status === 'none' && m.reason === 'neighbour' && m.neighbour.d > 150, 'parcel: a parcel 200 m away is still reported as a neighbour');
    const far2 = mkP('800', 'Gachibowli', LA, LO + dloM(900), 40); m = pm([A, far2], { survey: '800' }); ok(m.status === 'none' && m.reason === 'number-mismatch' && !m.neighbour, 'parcel: a same-numbered parcel 900 m away is not a neighbour');
    m = pm([A], { survey: '91' }); ok(m.status === 'approximate' && m.reason === 'sub-survey', 'parcel: "91" against parcel "91/1" is only an approximate match (sub-division)');
    m = pm([A], { survey: '91/2' }); ok(m.status === 'none', 'parcel: "91/2" against parcel "91/1" is no match');
    m = pm([mkP('91', 'Gachibowli', LA, LO, 40)], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'sub-survey', 'parcel: "91/1" against parent "91" is only approximate');
    const FL = mkP('91/1', 'Gachibowli', LA, LO, 40, 1, 'Duplicate Number'); m = pm([FL], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'number-flagged' && !m.usable, 'parcel: a number the source flags as duplicate or unreadable can never be verified');
    m = pm([FL], {}); ok(m.status === 'approximate' && m.reason === 'pin-only-flagged' && !m.usable, 'parcel: a flagged number is not usable for overlap tests either');
    const OV1 = mkP('10', 'Gachibowli', LA, LO, 40), OV2 = mkP('11', 'Gachibowli', LA, LO + dloM(20), 40);
    m = pm([OV1, OV2], {}); ok(m.status === 'approximate' && m.ambiguous && m.parcel === null && m.candidates.length === 2 && !m.usable, 'parcel: two overlapping outlines make an ambiguous approximate match with no single parcel');
    m = pm([OV1, OV2], { survey: '10' }); ok(m.status === 'approximate' && m.reason === 'overlap-ambiguous' && m.ambiguous, 'parcel: even a matching number is not "verified" when another outline overlaps the pin');
    const out10 = (h) => mkP('91/1', 'Gachibowli', LA, LO + dloM(40 + h), 40);
    m = pm([out10(10)], {}); ok(m.status === 'approximate' && m.reason === 'near-edge' && m.candidates[0].d > 5 && m.candidates[0].d < 15 && !m.usable, 'parcel: a pin 10 m outside an outline is approximate (near-edge) and not usable for overlap tests');
    m = pm([out10(10)], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'near-edge', 'parcel: a matching number does not make a near-edge pin "verified"');
    m = pm([out10(40), FAR], {}); ok(m.status === 'none' && m.reason === 'unmapped', 'parcel: a pin 40 m from any outline falls in a gap: no match');
    const RD = mkP('', 'Gachibowli', LA, LO, 40, 2, 'Road'); RD.n = '12'; m = pm([RD], {}); ok(m.status === 'none' && m.reason === 'on-feature', 'parcel: a pin on a mapped road or canal feature is no match');
    m = pm([mkP('1', 'X', LA, LO + dloM(600), 40)], {}); ok(m.status === 'unavailable' && m.reason === 'no-parcels-mapped', 'parcel: no parcels within 250 m means the source is unavailable here, not "no match"');
    m = pm([], {}); ok(m.status === 'unavailable', 'parcel: an empty area is "source unavailable"');
    m = E.parcelMatch(LA, LO, { ok: false, reason: 'tile-failed', parcels: [] }, {}); ok(m.status === 'unavailable' && m.reason === 'tile-failed', 'parcel: a failed download is "source unavailable", never "no match" or "no parcels"');
    m = E.parcelMatch(LA, LO, null, {}); ok(m.status === 'unavailable', 'parcel: no data object is "source unavailable"');
    m = E.parcelMatch(LA, LO, { ok: true, outsideBox: true, parcels: [] }, {}); ok(m.status === 'unavailable' && m.reason === 'outside-area', 'parcel: outside the covered area is "source unavailable"');
    const allM = [pm([A, N1], {}), pm([A, N1], { survey: '91/1' }), pm([OV1, OV2], { survey: '10' }), pm([FL], { survey: '91/1' }), pm([out10(10)], { survey: '91/1' }), pm([A], { survey: '91' }), pm([A], { survey: '777' })];
    ok(allM.every(x => ['verified', 'approximate', 'none', 'unavailable'].includes(x.status)), 'parcel: only the four documented statuses are ever returned');
    ok(allM.filter(x => x.status === 'verified').every(x => x.usable && !x.ambiguous && x.candidates.length === 1 && x.parcel.inside !== false), 'parcel: "verified" always means one outline, containing the pin, matching number, not flagged');
    ok(allM.every(x => !/owner|ownership|clear title|title is|legally|encumbrance-free/i.test(x.text.replace(/does not confirm title[^.]*\./i, '').replace(/says nothing about title or ownership/i, ''))), 'parcel: no result text claims ownership, clear title or legal status');
    ok(/does not confirm title/.test(pm([A], { survey: '91/1' }).text) && /many house plots/.test(pm([A], { survey: '91/1' }).text), 'parcel: the verified text says it does not confirm title and that a survey number can hold many plots');

    // ---- parcels: real tiles ----
    const idx = D.parcelIdx; ok(idx && idx.parcels_stored > 40000 && Object.keys(idx.tiles).length >= 100, 'parcel tiles are present', idx && idx.parcels_stored);
    ok(Object.entries(idx.tiles).every(([k, c]) => rd(`data/parcels/${k}.json`).p.length === c), 'every parcel tile holds exactly the number of parcels the index says');
    ok(idx.not_stored.includes('owner'), 'the parcel index records that owner fields were never stored');
    const cov = path.join(__dirname, '..', 'research', 'v7', 'parcel_coverage.json');
    if (fs.existsSync(cov)) { const c = rd('../research/v7/parcel_coverage.json'), scan = {}; for (const [k, x, y, n] of c.cells) if (k === 'cad_parcels') scan[Math.round((x - c.bbox[0]) / c.step) + '_' + Math.round((y - c.bbox[1]) / c.step)] = n; ok(Object.entries(idx.tiles).every(([k, n]) => scan[k] === n) && Object.entries(scan).every(([k, n]) => n === 0 || idx.tiles[k] === n), 'every tile holds exactly the parcels the server counted: none lost, none missing'); }
    const tileKeys = Object.keys(idx.tiles).filter(k => idx.tiles[k] > 300); let cnt = { verified: 0, approximate: 0, none: 0, unavailable: 0 }, tested = 0, wrongNum = 0;
    for (let ti = 0; ti < tileKeys.length; ti += 2) {
      const t = rd(`data/parcels/${tileKeys[ti]}.json`);
      for (let i = 0; i < t.p.length; i += 31) {
        const row = t.p[i]; if (row[3] !== 0 || !row[0]) continue; const ring = row[5][0]; let c = [0, 0]; for (const p of ring.slice(0, -1)) { c[0] += p[0]; c[1] += p[1]; } c = [c[0] / (ring.length - 1), c[1] / (ring.length - 1)];
        let inside = false; { let k = false; for (let a = 0, b2 = ring.length - 1; a < ring.length; b2 = a++) if (((ring[a][0] > c[0]) !== (ring[b2][0] > c[0])) && (c[1] < (ring[b2][1] - ring[a][1]) * (c[0] - ring[a][0]) / (ring[b2][0] - ring[a][0]) + ring[a][1])) k = !k; inside = k; } if (!inside) continue;
        const d = await E.parcelLoad(c[0], c[1]), mm = E.parcelMatch(c[0], c[1], d, { survey: row[0], village: t.v[row[1]] }); cnt[mm.status]++; tested++;
        if (mm.parcel && mm.status !== 'unavailable' && mm.status !== 'none' && E.normNum(mm.parcel.number) !== E.normNum(row[0]) && !mm.ambiguous) wrongNum++;
      }
    }
    ok(tested >= 100 && cnt.none === 0 && cnt.unavailable === 0 && cnt.verified / tested >= .85 && wrongNum === 0, `real parcels, own number and village at an interior point: all matched (${JSON.stringify(cnt)} of ${tested}), most verified, none wrong`);
    for (const [n, la, lo] of [['Charminar', 17.3616, 78.4747], ['Banjara Hills', 17.4126, 78.4482], ['Secunderabad', 17.4399, 78.4983], ['Hussain Sagar', 17.4235, 78.4745]]) { const mm = E.parcelMatch(la, lo, await E.parcelLoad(la, lo), { survey: '1' }); ok(mm.status === 'unavailable' && mm.reason === 'no-parcels-mapped', `old-city core (${n}): the parcel layer is honestly unavailable, even when a survey number is typed`); }
    ok((await E.parcelLoad(18.5, 79.5)).outsideBox === true, 'a pin far outside the study box is outside the parcel data');
    { const vn = new Map(); let dup = 0, totn = 0; for (const k of Object.keys(idx.tiles).filter((_, i) => i % 5 === 0)) for (const row of rd(`data/parcels/${k}.json`).p) { if (row[3] !== 0) continue; const kk = k.split('_')[0] + '|' + row[0] + '|' + row[1]; totn++; if (vn.has(row[0] + '|' + row[1] + '|' + k)) dup++; vn.set(row[0] + '|' + row[1] + '|' + k, 1); } ok(dup / totn < .03, 'few survey numbers repeat inside a tile (matching requires the pin to fall inside anyway)', `${dup} of ${totn}`); }
    ok(D.parcelIdx.remark_codes['1'] && D.parcelIdx.remark_codes['2'], 'remark classes are documented in the index');

    // ---- overlap of the matched parcel with other mapped footprints ----
    {
      const par = mkP('91/1', 'Gachibowli', LA, LO, 40), ring = par.rings[0], inject = (list, lo0, lo1) => { const rr = sqr(LA, (lo0 + lo1) / 2, 40); rr[0][1] = rr[3][1] = lo0; rr[1][1] = rr[2][1] = lo1; rr[4] = rr[0].slice(); const u = { r: [rr], a: ['test', 1.5, 'x'], _b: [bbx(rr)] }; list.push(u); return () => list.splice(list.indexOf(u), 1); };
      const x0 = LO - dloM(40), x1 = LO + dloM(40);
      let undo = inject(D.landL.lost, LO, x1 + dloM(10)); let o = E.overlapFacts([ring]); ok(o.lost && o.lost.frac > .4 && o.lost.frac < .6, 'overlap: a footprint over half of the outline is detected (about 50%)', o.lost && o.lost.frac); undo();
      undo = inject(D.landL.lost, x1, x1 + dloM(30)); o = E.overlapFacts([ring]); ok(o.lost === null, 'overlap: a footprint that only touches the outline edge is not an overlap'); undo();
      undo = inject(D.landL.lost, x1 - dloM(0.8), x1 + dloM(30)); o = E.overlapFacts([ring]); ok(o.lost === null, 'overlap: a sliver of about 1% (map error) is ignored'); undo();
      undo = inject(D.landL.forest, x0 - dloM(10), x1 + dloM(10)); o = E.overlapFacts([ring]); ok(o.forest && o.forest.frac > .95, 'overlap: a forest boundary covering the outline is detected'); undo();
      ok(E.overlapFacts([ring]).lost === null && E.overlapFacts([ring]).tanks.length === 0, 'overlap: injected test footprints were removed again');
      const r = await E.report(LA, LO); undo = inject(D.landL.lost, LO, x1 + dloM(10));
      E.setParcel(r, DATA([par]), { survey: '91/1' }); let f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'watch' && /disappeared/.test(f.value) && f.scope === 'parcel' && /not proof of encroachment or of any legal restriction/.test(f.note), 'overlap finding: a matched outline over a disappeared tank is a look-into item (never proof), labelled parcel-scope'); undo();
      E.setParcel(r, DATA([par]), { survey: '91/1' }); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'info' && /not a clearance/.test(f.note), 'overlap finding: no overlap is information, never "good", and says it is not a clearance');
      E.setParcel(r, DATA([par, mkP('92', 'Gachibowli', LA, LO + dloM(10), 40)]), {}); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'unknown' && /needs a matched survey parcel/.test(f.value), 'overlap finding: an ambiguous match gives no parcel-level result at all');
      E.setParcel(r, DATA([out10(10)]), { survey: '91/1' }); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'unknown', 'overlap finding: a near-edge match gives no parcel-level result');
      const pl = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'plot'); ok(pl.level === 'info' && /Approximate match/.test(pl.value) && pl.conf === 'low', 'plot finding: an approximate match is info with low confidence');
      E.setParcel(r, DATA([A, N1]), { survey: '92' }); const pl2 = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'plot'); ok(pl2.level === 'watch' && /No match/.test(pl2.value), 'plot finding: a number that does not match the pin is a watch item');
      const ck = E.checklist(r); ok(ck.items.some(i => i.key === 'plot'), 'checklist: a mismatched survey number puts "confirm the survey number" on the list');
      const rr0 = await E.report(LA, LO); await E.attachParcel(rr0, {}); const ck0 = E.checklist(rr0); ok(rr0.ev.identity.status && ck0.items.every(i => i.action && i.why), 'checklist: items stay well-formed with the new findings');
    }

    // ---- prohibitory-category layer ----
    {
      const pj = rd('data/prohib.json'); ok(pj.p.length >= 600 && /NOT the registration department/.test(pj.meta.note), 'prohibitory layer loaded and documented as not the legal register', pj.p.length);
      let hit = 0, tot2 = 0, wrongCat = 0;
      for (const p of pj.p.filter((_, i) => i % 3 === 0)) {
        const ring = p[6][0], bb2 = bbx(ring); let pt = null;
        for (let i = 0; i < 24 && !pt; i++) for (let j = 0; j < 24 && !pt; j++) { const la = bb2[0] + (i + .5) * (bb2[2] - bb2[0]) / 24, lo = bb2[1] + (j + .5) * (bb2[3] - bb2[1]) / 24; let k = false; for (let a = 0, b2 = ring.length - 1; a < ring.length; b2 = a++) if (((ring[a][0] > la) !== (ring[b2][0] > la)) && (lo < (ring[b2][1] - ring[a][1]) * (la - ring[a][0]) / (ring[b2][0] - ring[a][0]) + ring[a][1])) k = !k; if (k) pt = [la, lo]; }
        if (!pt) continue; tot2++; const h = E.prohibFacts(pt[0], pt[1], null); if (h) { hit++; if (h.cat !== p[0] && h.how !== 'pin') wrongCat++; }
      }
      ok(tot2 >= 150 && hit / tot2 >= .97, 'every listed prohibitory parcel is found when the pin is inside it', `${hit} of ${tot2}`);
      const p0 = pj.p.find(p => p[6][0].length > 4), ring0 = p0[6][0], bb3 = bbx(ring0); let pt0 = null;
      for (let i = 0; i < 24 && !pt0; i++) for (let j = 0; j < 24 && !pt0; j++) { const la = bb3[0] + (i + .5) * (bb3[2] - bb3[0]) / 24, lo = bb3[1] + (j + .5) * (bb3[3] - bb3[1]) / 24; let k = false; for (let a = 0, b2 = ring0.length - 1; a < ring0.length; b2 = a++) if (((ring0[a][0] > la) !== (ring0[b2][0] > la)) && (lo < (ring0[b2][1] - ring0[a][1]) * (la - ring0[a][0]) / (ring0[b2][0] - ring0[a][0]) + ring0[a][1])) k = !k; if (k) pt0 = [la, lo]; }
      const r = await E.report(pt0[0], pt0[1]);
      if (r.ok) { await E.attachParcel(r, {}); const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib');
        ok(f.level === 'watch' && f.conf === 'low' && f.value.includes(p0[0]) && /not a legal finding/.test(f.note) && /not the registration department/.test(f.note) && f.kind === 'official', 'prohibitory finding: quotes the category as recorded, watch only, low confidence, and says it is not the legal register');
        ok(!r.ev.sections.flatMap(s => s.findings).some(x => x.id === 'prohib' && x.level === 'concern'), 'prohibitory finding is never a concern on its own');
        ok(E.checklist(r).items.some(i => i.key === 'prohib' && /Registration Department/.test(i.action)), 'checklist: a prohibitory listing sends the buyer to the registration portal and Bhu Bharati'); }
      const rn = await E.report(LA, LO); E.setParcel(rn, DATA([A]), { survey: '91/1' }); const fn = rn.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib');
      ok(fn.level === 'info' && /not clearance/.test(fn.note), 'prohibitory finding: "not listed" is info and "not clearance", never good');
      const ru = await E.report(17.3616, 78.4747); await E.attachParcel(ru, {}); const fu = ru.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib'); ok(fu.level === 'unknown', 'prohibitory finding: where no parcels are mapped the layer cannot be tested, so it is unknown');
    }

    // ---- mapped water network ----
    if (!D.networkL) ok(false, 'network data (web/data/network.json) is missing'); else {
      ok(D.networkL && D.networkL.meta.supply_segments.in_use_kept > 100000, 'network: supply pipes are loaded', D.networkL && D.networkL.meta.supply_segments.in_use_kept);
      const nm = D.networkL.meta; ok([...D.networkL.sup.keys(), ...D.networkL.sew.keys()].every(k => Number.isInteger(k) && k >= 0 && k < nm.nx * nm.ny) && [...D.networkL.sup.values()].every(v => v[0] > 0 && v[1] >= 0), 'network: every cell index is inside the grid and every cell has a positive pipe length');
      ok(/not a connection record/i.test(nm.note) && /not redistributed/i.test(nm.note), 'network: the file records that it is not a connection record and that pipe geometry is not redistributed');
      ok(!JSON.stringify(rd('data/network.json').supply.slice(0, 50)).includes('paths'), 'network: no pipe geometry is stored');
      const nc = E.netFacts(17.3616, 78.4747), ng = E.netFacts(17.4401, 78.3489), nsx = E.netFacts(17.2403, 78.4294), no = E.netFacts(18.5, 79.5);
      ok(nc.inside && nc.sup.ring === 0 && nc.sew.ring != null && nc.sew.ring <= 1, 'network: the old city shows both supply pipes and a sewer line', JSON.stringify(nc.sew));
      ok(ng.section && /GACHIBOWLI/i.test(ng.section.name) && nc.section && /SHIFA/i.test(nc.section.name), 'network: HMWSSB operating sections are named (Gachibowli; Dar-ul-Shifa at Charminar)', [ng.section && ng.section.name, nc.section && nc.section.name].join());
      ok(ng.sup.ring != null && ng.sew.ring == null, 'network: Gachibowli has mapped supply pipes but no mapped sewer line (the layer covers the core city only)');
      ok(no.inside === false, 'network: a pin outside the grid is outside the network data');
      let bad = 0, nWatch = 0;
      for (const r of reports) for (const s of r.ev.sections) for (const f of s.findings) {
        if (f.id === 'supply' && (f.level !== 'unknown' || !/not published/.test(f.value))) bad++;
        if (f.id === 'supplynet' && (!['info', 'unknown'].includes(f.level) || (f.level === 'info' && !/not a connection/.test(f.note)) || (f.level === 'unknown' && !/neither proof/.test(f.note)))) bad++;
        if (f.id === 'sewernet') { if (!['info', 'unknown', 'watch'].includes(f.level) || (f.level === 'watch' && !/core city only/.test(f.note))) bad++; if (f.level === 'watch') nWatch++; }
      }
      ok(bad === 0, 'network: connection is always unknown; mapped pipes are information only and always say they are not a connection; no mapped pipe is never reassuring', bad);
      ok(reports.some(r => r.ev.sections.flatMap(s => s.findings).some(f => f.id === 'supplynet' && f.level === 'info')) && reports.some(r => r.ev.sections.flatMap(s => s.findings).some(f => f.id === 'sewernet' && f.level === 'unknown')), 'network: both the "mapped" and "outside the sewer area" outcomes occur across the city');
    }
  }

  // =====================================================================================================
  // UI — the buyer check is understandable, honest and complete
  // =====================================================================================================
  {
    const SB = r => ({ r, label: '', cust: { price: '', area: '', brokerage: '' }, agent: { ask: '', area: '', comps: '', guide: '', fee: '' }, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false },
      ai: { q: '', a: '', think: false }, fc: null, air: { aqi: 80, band: 'Moderate' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: { survey: '', village: '', plot: '', layout: '', doc: '' } });
    const placesUI = D.wards.filter((_, i) => i % 6 === 0).map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.2403, 78.4294], [17.3616, 78.4747]]);
    let nOrder = 0, nHero = 0, nCount = 0, nRow = 0, nStat = 0, nJump = 0, nClip = 0, nJargon = 0, nPlain = 0, checked = 0;
    const strip = h => h.replace(/<[^>]+>/g, ' ');
    for (const [la, lo] of placesUI) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); const S = SB(r); checked++;
      const html = Rep.render('customer', S), i1 = html.indexOf('What this check is about'), i2 = html.indexOf('The short version'), i3 = html.indexOf('Before you pay'), i4 = html.indexOf('Details by topic');
      if (!(i1 >= 0 && i1 < i2 && i2 < i3 && i3 < i4)) nOrder++;
      if (/Verdict for buyers|gaugebox|High caution/.test(html)) nHero++;
      const T = View.tally(r, S), m = k => { const x = html.match(new RegExp('<b>(\\d+)</b> ' + k)); return x ? +x[1] : -1; };
      if (m('need attention') !== T.concern.length || m('to look into') !== T.watch.length || m('no issue found') !== T.good.length || m("couldn't be checked") !== T.unknown.length) nCount++;
      const all = r.ev.sections.flatMap(s => s.findings);
      for (const f of all) if ((html.match(new RegExp('id="f_' + f.id + '"', 'g')) || []).length !== 1) nRow++;
      if ((html.match(/class="v-fstat/g) || []).length !== all.length) nStat++;
      for (const x of html.matchAll(/data-act="jump" data-id="([^"]+)"/g)) if (!html.includes('id="f_' + x[1] + '"')) nJump++;
      for (const x of html.matchAll(/<span class="v-iv">([^<]*)<\/span>/g)) if (x[1].length > 160) nClip++;
      const top = strip(View.shortVersion(r, S) + View.dock(S) + View.landing(S));
      if (/TGRAC|\bAUC\b|LOEO|OSRM|ArcGIS|JSON|\bAPI\b|SETHU model|GeoJSON/.test(top)) nJargon++;
      if (all.some(f => !View.PLAIN[f.id])) nPlain++;
    }
    ok(checked >= 20, 'UI tests ran on a spread of places', checked);
    ok(nOrder === 0, 'the buyer check reads in order: what this is about, the short version, before you pay, details by topic');
    ok(nHero === 0, 'the old contradictory verdict and score gauge are gone from the buyer check');
    ok(nCount === 0, 'the counts in the short version equal the findings in each state');
    ok(nRow === 0, 'every finding appears exactly once in the details');
    ok(nStat === 0, 'every finding row states its status in words, not only in colour');
    ok(nJump === 0, 'every item in the short version links to a finding that exists');
    ok(nClip === 0, 'items in the short version stay short');
    ok(nJargon === 0, 'the short version, map card and landing text avoid technical jargon');
    ok(nPlain === 0, 'every finding has a plain-language title', nPlain);
    ok(Object.keys(D.quality.factors).every(id => View.PLAIN[id]), 'every registry finding has a plain-language title');

    // escaping: a hostile value can never become markup
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, { survey: '<img src=x onerror=alert(1)>', village: '"><script>alert(1)</script>' }); r.ev.sections[0].findings[0].value = '<img src=x onerror=alert(1)>'; r.ev.sections[0].findings[0].note = '<script>alert(2)</script>';
      const S = SB(r); S.pref = { survey: '<img src=x onerror=alert(1)>', village: '"><script>alert(1)</script>', plot: '<b>p</b>', layout: '', doc: '' };
      const html = Rep.render('customer', S) + View.dock(S);
      ok(!/<img src=x|<script>alert|<b>p<\/b>/.test(html) && html.includes('&lt;img'), 'hostile text in findings and in the buyer\'s own references is escaped everywhere'); }

    // loading state: live lookups are "still loading", not "couldn't check"
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r); S.access = null; S.air = null; S.terrain = null;
      const t = View.tally(r, S); ok(t.loading.length >= 1 && !t.unknown.some(f => t.loading.includes(f.id)), 'findings still being fetched are listed as loading, not as unchecked');
      ok(Rep.render('customer', S).includes('Still loading'), 'the page says what is still loading'); ok(!Rep.render('customer', SB(r)).includes('Still loading'), 'nothing is "still loading" once the lookups are in'); }

    // map card and landing
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r), d = View.dock(S);
      ok(/See the full check/.test(d) && /need attention/.test(d) && /look into/.test(d) && /couldn't check/.test(d), 'the map card shows the three counts and a clear next step');
      ok(/Probably a survey number|A map pin, not a verified plot|Matched to a surveyed plot/.test(d), 'the map card always says whether the pin is matched to a plot');
      const rp = await E.report(17.3616, 78.4747); await E.attachParcel(rp, {}); ok(/A map pin, not a verified plot/.test(View.dock(SB(rp))), 'in the old city (no survey outlines) the map card says it is only a map pin');
      const L = View.landing(S); ok(/Try an example/.test(L) && /cannot see title/.test(L), 'the landing text offers examples and states what SETHU cannot see'); }

    // identity wording never overclaims
    { const r = await E.report(17.44, 78.35); const S = SB(r); ok(/not a verified plot/.test(View.identity(r, S)), 'before matching, the identity card says "map pin, not a verified plot"');
      await E.attachParcel(r, {}); const h = View.identity(r, S); ok(!/owner|clear title|legal boundary is/i.test(strip(h).replace(/says nothing about title or ownership/, '').replace(/not legal boundaries/, '')), 'the identity card never claims ownership or clear title'); }

    // agent / insurer / compare still render, with the shared evidence layer
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r), ra = await E.report(17.3616, 78.4747);
      for (const lens of ['agent', 'insurer']) { const h = Rep.render(lens, S); ok(h.includes('The short version') && h.includes('Details by topic') && h.includes('What this check is about'), `the ${lens} view shares the same plain-language evidence layer`); }
      S.cmp = { a: r, b: ra, la: 'A', lb: 'B' }; const c = Rep.compare(S); ok(c.includes('Comparing two addresses') && !/undefined|NaN/.test(c), 'the comparison view still renders'); }
  }


  // ---- guards added before release ----
  {
    const p31 = fs.readFileSync(path.join(__dirname, '..', 'pipeline', 'p31_parcels.py'), 'utf8'), eng = fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8');
    ok(!/CAD_FIELDS\s*=\s*"[^"]*\bSNo\b/.test(p31), 'the parcel download never requests SNo (a village serial number, not a survey number)');
    ok(!/\bSNo\b/.test(eng.replace(/\/\/.*$/gm, '')), 'the engine never reads SNo');
    const t0 = JSON.parse(fs.readFileSync(path.join(WEB, 'data', 'parcels', Object.keys(D.parcelIdx.tiles)[0] + '.json'), 'utf8'));
    ok(t0.p.every(row => row.length === 6 && typeof row[0] === 'string' && row[0].length > 0), 'every stored parcel row is [parcel number, village, mandal, remark class, remark, rings] with a non-empty parcel number');
    const html = Rep.render('customer', { r: await E.attachParcel(await E.report(17.4401, 78.3489), {}), label: '', cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: {} });
    ok(!/Looks fine/.test(html) && /No issue found/.test(html) && /never a clearance/.test(html), 'the report says "No issue found" (never "Looks fine") and states that it is not a clearance');
    const rr = await E.report(17.4401, 78.3489); await E.attachParcel(rr, {});
    const lvl = {}; for (const s of rr.ev.sections) for (const f of s.findings) lvl[f.id] = f.level;
    ok(!['overlap', 'prohib'].some(id => lvl[id] === 'concern'), 'a map overlap or a prohibitory-layer listing is never rated "needs attention" on its own');
  }
  // ---- pasted Google Maps links ----
  {
    const P = x => E.parseMapsLink(x);
    const mine = 'https://www.google.com/maps/search/?api=1&query=Shri+Ahobilam+Matt%2C+2-2-20%2FB%2C+Bagh+Amberpet%2C+Hyderabad%2C+Telangana+500013';
    ok(P(mine) && P(mine).text === 'Shri Ahobilam Matt, 2-2-20/B, Bagh Amberpet, Hyderabad, Telangana 500013', 'a Google "search?api=1&query=" link yields its address text (decoded, + as spaces, %2C as commas)');
    ok(P('https://www.google.com/maps/search/?api=1&query=17.4401%2C78.3489') && P('https://www.google.com/maps/search/?api=1&query=17.4401%2C78.3489').lat === 17.4401, 'a query that is coordinates yields coordinates, not text');
    ok(P('https://www.google.com/maps/place/Gachibowli,+Hyderabad/@17.4401,78.3489,15z').lat === 17.4401, 'a place link with @lat,lon yields coordinates');
    ok(P('https://www.google.com/maps/place/17.4%C2%B0N/data=!3d17.4235!4d78.4745').lat === 17.4235 && P('https://www.google.com/maps/place/x/data=!3d17.4235!4d78.4745!5m1').lon === 78.4745, '!3d!4d pin coordinates win');
    ok(P('https://www.google.com/maps/place/Hussain+Sagar+Lake/data=!4m2').text === 'Hussain Sagar Lake', 'a place link with a name and no coordinates yields the name');
    ok(P('https://maps.app.goo.gl/AbC123xyz').short === true && P('https://maps.app.goo.gl/AbC123xyz').url === 'https://maps.app.goo.gl/AbC123xyz', 'a short link is recognised and its URL kept for the server to resolve');
    ok(P('https://goo.gl/maps/AbC123').short === true, 'the older goo.gl/maps short links too');
    ok(P('Gachibowli') === null && P('17.44, 78.35') === null && P('https://example.com/maps?q=1,2') === null, 'ordinary search text, coordinates and non-Google links are not treated as Google links');
    ok(P('https://www.google.com/maps/search/?api=1&query=ab').short === true, 'a query shorter than 3 letters is not looked up');
    ok(typeof P('https://www.google.com/maps/search/?api=1&query=%3Cb%3Ex%3C%2Fb%3E+road').text === 'string', 'text from a link is returned as plain text; the app shows it only through input.value and textContent, never as HTML');
    const app = fs.readFileSync(path.join(WEB, 'platform', 'app.js'), 'utf8'); ok(!/innerHTML\s*=\s*[^;]*text/.test(app.slice(app.indexOf('async function searchText'), app.indexOf('async function doSearch'))), 'the link-search code never writes the pasted text into innerHTML');
  }
  // ---- wording must say what actually happened ----
  {
    const SBx = r => ({ r, label: '', cust: {}, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: {}, fc: null, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: { survey: '', village: '', plot: '', layout: '', doc: '' } });
    const r = await E.report(17.4401, 78.3489), mk = (la, lo, w) => ({ ok: true, outsideBox: false, parcels: w });
    const sq = (la, lo, h) => { const a = h / 110540, b = h / (111320 * Math.cos(la * Math.PI / 180)); return [[la - a, lo - b], [la - a, lo + b], [la + a, lo + b], [la + a, lo - b], [la - a, lo - a]]; };
    const bbox = ring => [Math.min(...ring.map(p => p[0])), Math.min(...ring.map(p => p[1])), Math.max(...ring.map(p => p[0])), Math.max(...ring.map(p => p[1]))];
    const P = (la, lo, n) => { const ring = sq(la, lo, 40); return { n, v: 'X', m: 'Y', code: 0, rem: '', rings: [ring], _b: bbox(ring) }; };
    // a pin in a gap between plots, with NO survey number typed
    E.setParcel(r, mk(0, 0, [P(17.4401 + 0.0009, 78.3489, '1'), P(17.4401 - 0.0009, 78.3489, '2')]), {});
    let d = View.dock(SBx(r)), id = View.identity(r, SBx(r));
    ok(r.ev.identity.status === 'none' && r.ev.identity.reason === 'unmapped', 'a pin in a gap between plots is "no match / unmapped"');
    ok(!/survey number (you )?entered/i.test(d.replace(/<[^>]+>/g, ' ')) && /Not on a mapped survey plot/.test(d), 'the map card does NOT claim a survey number was entered when none was');
    ok(!/does not match the survey number you entered/i.test(id) && /not on a mapped survey plot/i.test(id), 'the identity box says the pin is not on a mapped plot, not that a number mismatched');
    // the same status with a typed number that does not fit really is a mismatch
    E.setParcel(r, mk(0, 0, [P(17.4401, 78.3489, '7')]), { survey: '99' }); d = View.dock(SBx(r));
    ok(r.ev.identity.reason === 'number-mismatch' && /Does not match the survey number entered/.test(d), 'with a typed number that does not fit, the card says so');
    const pp = E.parseMapsLink('https://www.google.com/maps/place/Shri+Ahobilam+Matt/@17.4022667,78.5197988,17z/data=!3m1!4b1!4m6!3m5!1s0x0:0x0!8m2!3d17.4022667!4d78.5197988');
    ok(pp && pp.lat === 17.4022667 && pp.name === 'Shri Ahobilam Matt', 'a place link keeps its readable name next to the coordinates (used as the label)');
    ok(E.parseMapsLink('https://www.google.com/maps/@17.44,78.35,15z').name === undefined, 'a plain map link has no place name');
  }
  // ---- Step 1: state fire-station list and state seismic layer ----
  {
    const rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8')), Q = D.quality;
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };
    const reports = []; for (const [la, lo] of D.wards.map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.26, 78.43], [17.2403, 78.4294], [17.597, 78.57], [17.514, 78.45]])) { const r = await E.report(la, lo); if (r.ok) reports.push(r); }
    const fj = rd('data/fire.json'), st = fj.stations, sj = rd('data/seismic.json');
    ok(st.length === 71 && fj.meta.records === 71, 'all 71 fire-station records are kept');
    ok(st.every(x => x[4] === 'Existing' || x[4] === 'Proposed') && st.filter(x => x[4] === 'Existing').length === 32 && st.filter(x => x[4] === 'Proposed').length === 39, "the source's own status is preserved exactly (32 Existing, 39 Proposed)");
    const rem = {}; for (const x of st) rem[x[5]] = (rem[x[5]] || 0) + 1;
    ok(rem['Moved'] === 24 && rem['Correct'] === 1 && rem['Kept same not found accurate'] === 6 && rem['Moved not found accurate'] === 1 && rem['Proposed'] === 39, "the source's remarks are preserved verbatim (Moved 24, Correct 1, not found accurate 7, Proposed 39)");
    ok(st.every(x => x[0] > 16.9 && x[0] < 17.9 && x[1] > 78 && x[1] < 79.1), 'every fire record sits inside the Hyderabad region (no swapped or missing coordinates)');
    ok(/never treated as confirmed/.test(fj.meta.note) && /never treated as confirmed/.test(Q.sources.tgrac_fire.limits), 'the data file and the registry both state that Proposed and Moved records are never treated as confirmed');
    const pr = st.find(x => x[4] === 'Proposed'), ff = E.fireFacts(pr[0], pr[1]);
    ok(ff.nearest && ff.nearest.s.status === 'Existing' && ff.proposed3.every(x => x.s.status === 'Proposed'), 'standing on a Proposed site, the nearest station is still an Existing one and the Proposed site is listed separately');
    let badFire = 0, nInfo = 0, nUnk = 0;
    for (const r of reports) {
      const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'fire_gis'); if (!f) { badFire++; continue; }
      if (!['info', 'unknown'].includes(f.level) || (f.kind === 'official' && f.conf !== 'low') || /operating|operational|response time (of|is)|within \d+ minutes/i.test(f.value.replace(/\(not operating\)/g, '')) || (f.level === 'info' && !/does not confirm that any station is operating/.test(f.note)) || (f.level === 'info' && !/listed as Existing/.test(f.value))) badFire++;
      if (f.level === 'info') nInfo++; else nUnk++;
    }
    ok(badFire === 0 && nInfo > 50 && nUnk >= 1, 'the fire finding is only ever information or unknown, low confidence, says "listed as Existing", and never claims a station operates', `${badFire} bad, ${nInfo} info, ${nUnk} unknown`);
    ok(reports.every(r => { const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'fire_gis'); return f.level !== 'info' || !/^[^·]*· [^·]* · listed as Proposed/.test(f.value); }), 'the headline station is never a Proposed one');
    ok(sj.zones.length === 3 && sj.zones.map(z => z.zone).sort().join() === 'Zone II,Zone II,Zone III', 'all three seismic polygons are kept (two Zone II areas, one Zone III)');
    let zn = 0, zo = 0, badSz = 0;
    for (let la = 17.20; la <= 17.66; la += .02) for (let lo = 78.18; lo <= 78.70; lo += .02) { const z = E.seismicFacts(la, lo); zn++; if (z && z.zone === 'Zone II') zo++; }
    ok(zo === zn, 'the whole map region reads as Zone II in the state layer, agreeing with the reference', `${zo} of ${zn}`);
    for (const r of reports) {
      const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic_gis');
      if (!f || f.level !== 'info' || f.kind !== 'official' || /\b(safe|safety rating|earthquake[- ]proof|resistant)\b/i.test(f.value) || !/nothing about whether a particular building is structurally safe/.test(f.note) || f.scope !== 'area') badSz++;
    }
    ok(badSz === 0, 'the seismic finding is information only, never a safety claim, and says it cannot speak for a building', badSz);
    const refF = reports[0].ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic');
    ok(/Zone II/.test(refF.value) && !/disagree/.test(refF.value), 'where the sources agree the reference line is unchanged');
    const saved = D.seismicL;   // conflicting sources: pretend the state layer says Zone III here
    D.seismicL = [{ zone: 'Zone III', intensity: 'Moderate Risk Zone intensity VII', rings: [[[17.3, 78.3], [17.3, 78.6], [17.6, 78.6], [17.6, 78.3], [17.3, 78.3]]], _b: [[17.3, 78.3, 17.6, 78.6]] }];
    const rc = await E.report(17.4401, 78.3489), fc = rc.ev.sections.flatMap(s => s.findings), s1 = fc.find(x => x.id === 'seismic'), s2 = fc.find(x => x.id === 'seismic_gis');
    ok(/disagree/.test(s1.value) && /Zone III/.test(s1.value) && /Zone III/.test(s2.value), 'if the state layer disagrees with the Zone II reference, the report says the sources disagree and shows both');
    D.seismicL = [{ zone: 'Zone II', intensity: 'x', rings: [[[17.3, 78.3], [17.3, 78.6], [17.6, 78.6], [17.6, 78.3], [17.3, 78.3]]], _b: [[17.3, 78.3, 17.6, 78.6]] },
      { zone: 'Zone III', intensity: 'y', rings: [[[17.3, 78.6], [17.3, 78.7], [17.6, 78.7], [17.6, 78.6], [17.3, 78.6]]], _b: [[17.3, 78.6, 17.6, 78.7]] }];
    const rb = await E.report(17.45, 78.598), sb2 = rb.ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic_gis');
    ok(sb2.conf === 'low' && /boundary/.test(sb2.value) && /approximate/.test(sb2.note), 'close to a zone boundary the finding drops to low confidence and says the zone is approximate');
    D.seismicL = saved;
    ok(Q.sources.tgrac_fire.licence === 'verify' && Q.sources.tgrac_seismic.licence === 'verify' && /no licence text/.test(Q.sources.tgrac_fire.licence_note) && /no licence text/.test(Q.sources.tgrac_seismic.licence_note), 'both new sources are registered with licence unverified');
    ok(E.removalImpact('tgrac_fire').becomeUnknown.includes('fire_gis') && E.removalImpact('tgrac_seismic').becomeUnknown.includes('seismic_gis'), 'removing either source makes its finding unknown in the dashboard impact view');
    const E2 = await freshEngine(['fire.json', 'seismic.json']), r2 = await E2.report(17.4401, 78.3489), g2 = r2.ev.sections.flatMap(s => s.findings);
    ok(['fire_gis', 'seismic_gis'].every(id => { const f = g2.find(x => x.id === id); return f && f.level === 'unknown' && /not loaded/.test(f.value); }), 'with either file missing, the finding reads "data not loaded", never a reassuring result');
  }
  // ---- Step 2: tank survey numbers and the parcels carrying them ----
  {
    const rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8')), Q = D.quality;
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };
    const hyj = rd('data/hydraa_tanks.json'), tsj = rd('data/tank_syn.json'), TK = hyj.tanks, withSyn = TK.filter(x => x.syn);
    ok(TK.length === 1192 && tsj.meta.tanks_total === 1192 && withSyn.length === 313 && tsj.meta.tanks_with_survey_number === 313, 'all 1,192 tank records are kept and 313 carry a usable survey number');
    ok(TK.every(x => !x.syn || x.syn.split('_').every(n => /^\d+(\/\d+)?$/.test(n) && Number(n.split('/')[0]) < 10000)), 'placeholder survey numbers (88805, 99905, "Not Visible") are never kept as survey numbers');
    ok(new Set(TK.map(x => x.id)).size === TK.length, 'tank ids are unique');
    const ids = Object.keys(tsj.par), byId = new Map(TK.map(x => [String(x.id), x]));
    ok(ids.length === tsj.meta.queried_ok && ids.every(i => byId.get(i) && byId.get(i).syn), 'parcels are stored only for tanks that record a survey number');
    ok(ids.every(i => tsj.par[i].every(p => { const bases = byId.get(i).syn.split('_').map(n => n.split('/')[0]); return bases.includes(String(p.no).split('/')[0].toUpperCase()) && p.rings.length && Object.keys(p).every(k => ['no', 'v', 'src', 'touch', 'cov', 'rings'].includes(k)); })), 'every stored parcel carries the tank\'s own survey number and only survey-record fields (no owner or personal data)');
    ok(tsj.meta.with_matching_parcel === ids.filter(i => tsj.par[i].length).length && tsj.meta.touching_outline === ids.filter(i => tsj.par[i].some(p => p.touch)).length && tsj.meta.failed === 0, 'the counts in the file header match the file');
    ok(/not the legal Full Tank Level/.test(tsj.meta.note) || /not the legal Full Tank Level/.test(Q.sources.tgrac_tank_syn.limits), 'the data file or the registry says a numbered parcel is not the legal Full Tank Level');
    // findings over many positions
    const pts = []; const num = TK.filter(x => x.syn && (tsj.par[x.id] || []).length);
    for (const x of num.slice(0, 60)) { const rg = x.rings[0]; pts.push([rg[0][0] + .0006, rg[0][1], 'near-outline']); const tp = (tsj.par[x.id] || []).find(p => p.touch); if (tp) { const c = tp.rings[0].reduce((a, q) => [a[0] + q[0] / tp.rings[0].length, a[1] + q[1] / tp.rings[0].length], [0, 0]); pts.push([c[0], c[1], 'parcel-centre', x, tp]); } }
    for (const x of TK.filter(y => !y.syn && y.name).slice(0, 15)) pts.push([x.rings[0][0][0] + .0004, x.rings[0][0][1], 'no-number']);
    let nF = 0, bad = 0, nWatch = 0, nIn = 0, nNone = 0;
    for (const [la, lo, kind, x, tp] of pts) {
      const r = await E.report(la, lo); if (!r.ok) continue;
      const fl = r.ev.sections.flatMap(z => z.findings), f = fl.find(z => z.id === 'tank_survey'), tf = E.tankSurveyFacts(la, lo);
      if (!f) { if (tf && tf.tank) bad++; else nNone++; continue; }
      nF++;
      if (!['info', 'watch', 'unknown'].includes(f.level) || !['official', 'unavailable'].includes(f.kind) || !['low', 'unavailable'].includes(f.conf) || f.sec !== 'land') bad++;
      if (/\b(inside|within|in) the (legal )?(FTL|full tank level)|encroach|illegal|unauthori[sz]ed|safe to buy|clear(ed|ance)? (title|to buy)/i.test(f.value)) bad++;
      if (f.level === 'info' && !/legal Full Tank Level|records no survey number|no parcel with that number|parcel search/.test(f.note + ' ' + f.value) ) bad++;
      if (f.level === 'watch') { nWatch++; if (!/not the legal|legal Full Tank Level/.test(f.note) || !/inside survey parcel/.test(f.value)) bad++; }
      if (kind === 'parcel-centre') { if (/^this pin is inside survey parcel/.test(f.value)) nIn++; }
      if (kind === 'no-number' && f.level === 'info' && !/records no survey number/.test(f.value)) bad++;
    }
    ok(nF > 40 && bad === 0, 'the tank-survey finding is only info, watch or unknown, always low confidence, in the land section, and never says legal FTL, encroachment or safe to buy', `${nF} findings, ${bad} bad`);
    ok(nIn > 20, 'standing in the middle of a parcel that carries a tank\'s number says so', `${nIn} of ${pts.filter(p => p[2] === 'parcel-centre').length}`);
    ok(nWatch > 0, 'being inside such a parcel close to the tank is raised as something to check, not hidden');
    ok(pts.filter(p => p[2] === 'no-number').length > 5, 'tanks with no recorded number were tested');
    // a tank with a number but no completed parcel search must read as unknown, never "none found"
    const tnum = num[0], saveP = D.tankPar.get(tnum.id); D.tankPar.delete(tnum.id);
    const ru = await E.report(tnum.rings[0][0][0] + .0006, tnum.rings[0][0][1]), fu = ru.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey');
    ok(fu && (fu.level === 'unknown' || !/no parcel with that number/.test(fu.value)), 'a tank whose parcel search did not complete reads as unknown or is not described as "none found"', fu && fu.value);
    D.tankPar.set(tnum.id, saveP);
    const rFar = await E.report(17.2403, 78.4294); const fFar = rFar.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey'), tfFar = E.tankSurveyFacts(17.2403, 78.4294);
    ok(!!fFar === !!(tfFar && tfFar.tank), 'a finding appears only when a tank is within 600 m: absence is never reported as a clean result');
    ok(Q.sources.tgrac_tank_syn.licence === 'verify' && /no licence text/.test(Q.sources.tgrac_tank_syn.licence_note) && /not the legal Full Tank Level/.test(Q.sources.tgrac_tank_syn.limits), 'the source is registered with licence unverified and the not-FTL limit stated');
    ok(Q.sources.tgrac_tank_syn.validation === 'internal-check' && /20 lakes/.test(Q.sources.tgrac_tank_syn.validation_note) && /not checked against the revenue records/i.test(Q.sources.tgrac_tank_syn.validation_note), 'the registry states the 20-lake check and what was not checked');
    ok(E.removalImpact('tgrac_tank_syn').becomeUnknown.includes('tank_survey'), 'removing the source makes its finding unknown in the dashboard impact view');
    const E2 = await freshEngine(['tank_syn.json']), r2 = await E2.report(tnum.rings[0][0][0] + .0006, tnum.rings[0][0][1]), g2 = r2.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey');
    ok(g2 && g2.level === 'unknown' && /not loaded/.test(g2.value), 'with the tank-survey file missing, the finding reads "data not loaded", never a reassuring result');
  }
  // ---- the brief: a short, tappable answer instead of a long report ----
  {
    const Br = sandbox.Brief, strip = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' '), words = h => strip(h).trim().split(' ').length;
    const mk = (r, persona, open) => ({ r, persona, label: '', address: '', open: open || {}, cmpPending: false, pref: { survey: '', village: '', plot: '', layout: '', doc: '' }, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, cust: {}, agent: {}, claim: {} });
    const facs = Object.keys(D.quality.factors), P = Br.PERSONAS;
    ok(Object.keys(P).length === 6 && ['buyer', 'renter', 'investor', 'agent', 'lender', 'insurer'].every(k => P[k] && P[k].ask && P[k].tiles.length === 6 && P[k].say.bad && P[k].say.warn && P[k].say.ok && P[k].say.mute), 'six kinds of user, each with a question, six topics and an answer for every outcome');
    ok(Object.values(P).every(p => p.tiles.every(id => Br.TILES[id])), 'every topic a user is shown exists');
    ok(Object.values(Br.TILES).filter(t => t.ids).every(t => t.ids.every(id => facs.includes(id))), 'every finding a topic reads from exists in the evidence registry (no typos)', Object.values(Br.TILES).filter(t => t.ids).flatMap(t => t.ids.filter(id => !facs.includes(id))).join());
    // the verdict of a topic is the most serious result inside it, never an average
    const V = (lv, load) => Br.verdict(lv.map((l, i) => ({ id: 'x' + i, level: l })), new Set(load || [])).level;
    ok(V(['concern', 'good', 'good', 'good']) === 'concern' && V(['watch', 'good', 'good']) === 'watch', 'one red flag among many clean results still makes the topic red or amber');
    ok(V(['good', 'good', 'unknown']) === 'good' && V(['good', 'unknown', 'unknown']) === 'partial' && V(['unknown', 'unknown']) === 'unknown' && V(['info', 'unknown']) === 'partial' && V(['info']) === 'info', 'a topic reads "no issue found" only when clean checks at least match the unanswered ones; otherwise it says partly checked or couldn\'t check');
    ok(V(['unknown', 'good'], ['x0']) === 'good', 'a check still loading is not counted as a gap');
    const places = [[17.4401, 78.3489], [17.3616, 78.4747], [17.4948, 78.3996], [17.2403, 78.4294], [17.63, 78.48], [17.3457, 78.5522], [17.4325, 78.4071], [17.4399, 78.4983], [17.597, 78.57], [17.26, 78.43]];
    let nHead = 0, nWords = 0, nFace = 0, nFlag = 0, nTile = 0, nWhy = 0, nHonest = 0, nJar = 0, nPersona = 0, checked = 0, nOkNote = 0;
    for (const [la, lo] of places) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); checked++;
      for (const pid of Object.keys(P)) {
        const S0 = mk(r, pid), html = Br.page(S0), ctx = Br.state(r, S0), tiles = P[pid].tiles.map(id => Br.tileData(id, r, S0, ctx));
        const shown = (html.match(/<section class="b-head[\s\S]*?<\/section>/) || [''])[0] + [...html.matchAll(/<summary>([\s\S]*?)<\/summary>/g)].map(m => m[1]).join(' ') + (html.match(/<section class="b-todo[\s\S]*?<\/section>/) || [''])[0];   // what is visible before anything is tapped
        if (words(shown) > 600) nWords++;
        if ((html.match(/<details class="b-tile/g) || []).length !== 6 || (Br.who(S0).match(/aria-selected="true"/g) || []).length !== 1) nPersona++;
        const anyBad = tiles.some(t => t.level === 'concern'), anyWarn = tiles.some(t => t.level === 'watch'), cls = (html.match(/class="b-head h-(\w+)"/) || [])[1];
        if (anyBad ? cls !== 'bad' : anyWarn ? cls !== 'warn' : (cls === 'bad' || cls === 'warn')) nHead++;
        if (cls === 'ok' && !/not a clearance/.test(strip(html))) nOkNote++;
        for (const x of html.matchAll(/data-act="b-open" data-tile="(\w+)"/g)) { const t = tiles.find(q => q.id === x[1]); if (!t || !['concern', 'watch'].includes(t.level) || (anyBad && t.level !== 'concern')) nFlag++; }
        for (const t of tiles) if (t.kind === 'generic') { const lv = t.live.map(f => f.level); if ((lv.includes('concern') && t.level !== 'concern') || (!lv.includes('concern') && lv.includes('watch') && t.level !== 'watch') || (t.level === 'good' && (lv.includes('concern') || lv.includes('watch')))) nTile++; }
        const faces = [...html.matchAll(/<summary>([\s\S]*?)<\/summary>/g)].map(m => strip(m[1])).join(' ');
        if (/TGRAC|\bAUC\b|LOEO|OSRM|ArcGIS|JSON|\bAPI\b|GeoJSON|HYDRAA/.test(faces)) nJar++;
        if (/\b(is safe|are safe|guaranteed|cleared|clear title)\b/i.test(strip(html).replace(/Is it safe to buy here\?/g, '').replace(/not a clearance/g, '').replace(/not unsafe/g, ''))) nHonest++;
        // every fact shown carries its reasoning: open every topic and every drawer
        const open = { b_allwhy: true }; for (const id of P[pid].tiles) open['bt_' + id] = true;
        const full = Br.page(mk(r, pid, open)), nF = (full.match(/class="b-fact /g) || []).length, nW = (full.match(/<details class="b-why"/g) || []).length, nSrc = (full.match(/What this rests on/g) || []).length;
        if (nF !== nW || nF === 0 || nSrc < nF * 0.8) nWhy++;
      }
    }
    ok(checked >= 8, 'the brief was built for many places and all six kinds of user', checked);
    ok(nPersona === 0, 'every brief shows six topics and exactly one selected kind of user', nPersona);
    ok(nWords === 0, 'what is visible before anything is tapped stays short (under 600 words, against about 3,000 in the long report)', nWords);
    ok(nHead === 0, 'the one-line answer is red if any topic is red, amber if any is amber, and never green with a flag', nHead);
    ok(nOkNote === 0, 'a green answer always says it is not a clearance', nOkNote);
    ok(nFlag === 0, 'the flagged topics in the answer are real, flagged topics (red ones first)', nFlag);
    ok(nTile === 0, 'no topic reads green or amber while a more serious result sits inside it', nTile);
    ok(nWhy === 0, 'every fact has its "How we know" with source, age, locality and confidence', nWhy);
    ok(nJar === 0, 'the topic faces use plain words (no data-source jargon up front)', nJar);
    ok(nHonest === 0, 'the brief never says a place is safe or cleared', nHonest);
    // special topics
    const rr = await E.report(17.4401, 78.3489); await E.attachParcel(rr, {}); const Sx = mk(rr, 'insurer'), cx = Br.state(rr, Sx);
    const ex = Br.tileData('exposure', rr, Sx, cx), tiersLv = ['motor', 'prop', 'health'].map(k => rr.tiers[k].letter);
    ok(ex.level === (tiersLv.some(l => 'DE'.includes(l)) ? 'concern' : tiersLv.some(l => l === 'C') ? 'watch' : 'good') && /illustrative/.test(ex.body), 'the insurer\'s exposure topic follows the worst tier and says loadings are illustrative');
    const pr = Br.tileData('price', rr, mk(rr, 'agent'), cx); ok(pr.level === 'info' && /asking prices, not registered deal prices/.test(pr.body), 'the price topic is information only and says these are asking prices');
    const pt = Br.tileData('pitch', rr, mk(rr, 'agent'), cx); ok(['concern', 'watch', 'good'].includes(pt.level) && /Say this/.test(pt.body) && /Be ready for/.test(pt.body), 'the agent\'s pitch topic lists what to say and what to be ready for');
    // before a place is picked
    const L = Br.landing({ persona: 'buyer', open: {} }), Lt = strip(L);
    ok(Object.values(P).every(p => Lt.includes(p.name)) && /I am a/.test(Lt) && /before/.test(Lt) && /can’t tell you|can't tell you/.test(Lt) && !/real floods tested|wards\s+\d|hospitals mapped/.test(Lt), 'the landing states the goal, asks who you are, and drops the validation counters');
    ok(words(L) < 280, 'the landing is short', words(L));
    const dk = Br.dock(mk(rr, 'buyer')), pg = Br.page(mk(rr, 'buyer')), pgf = Br.page(mk(rr, 'buyer', { fullreport: true }));
    ok(words(dk) < 100 && !/b-tile/.test(dk) && /View report/.test(dk) && /I am a/.test(strip(dk)), 'the side panel is only the place, who you are and a "View report" button', words(dk));
    ok(/b-fullcta/.test(pg) && !/id="fullreport"/.test(pg) && !/The short version/.test(pg), 'the report page opens on the summary, with the full report one tap below');
    ok(/id="fullreport"/.test(pgf) && /The short version/.test(pgf) && /Details by topic/.test(pgf) && !/b-fullcta/.test(pgf), 'tapping "View the full report" adds the whole report under the summary');
  }
  // ---- live APIs (optional) ----
  if (argv.includes('--net')) {
    const el = await E.addTerrain(await E.report(17.4015, 78.4100));
    ok(el.terrain && Number.isFinite(el.terrain.center), 'elevation API returns data');
    const rn = await E.rainOn(17.385, 78.486, '2020-10-13');
    ok(rn.max > 40, 'archive rain for 13 Oct 2020 is heavy (>40 mm)', rn.max);
    const rd = await E.rainOn(17.385, 78.486, '2020-03-02');
    ok(rd.max < 5, 'archive rain for 2 Mar 2020 is dry (<5 mm)', rd.max);
    const fc = await E.forecast(17.385, 78.486);
    ok(fc.length === 7, 'forecast has 7 days', fc.length);
  }

  // ---- distribution (calibration aid) ----
  if (argv.includes('--dist')) {
    const cnt = k => rows.reduce((o, r) => (o[r[k]] = (o[r[k]] || 0) + 1, o), {});
    const q = (k, p) => { const s = rows.map(r => r[k]).sort((a, b) => a - b); return s[Math.floor(p * (s.length - 1))]; };
    for (const k of ['water', 'motor', 'prop', 'dev', 'loc']) console.log(k, 'min/p10/p25/p50/p75/p90/max', [0, .1, .25, .5, .75, .9, 1].map(p => q(k, p)).join(' / '));
    console.log('tiers water', cnt('wt'), 'motor', cnt('mt'), 'prop', cnt('pt'));
  }

  console.log(`\n${pass} passed, ${fail} failed`);
  fails.forEach(f => console.log('  FAIL:', f));
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(2); });
