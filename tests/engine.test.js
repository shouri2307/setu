/* Engine test harness — run:  node tests/engine.test.js [--net] [--dist]
 * Loads web/platform/engine.js in a sandbox with local data files, then checks data integrity,
 * geometry, scoring invariants and golden locations. --net also hits the live APIs.
 * --dist prints the tier distribution (used to calibrate thresholds). */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', 'web');
const realFetch = fetch;
const sandbox = {
  console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout,
  fetch: u => {
    if (/^https?:/.test(u)) return realFetch(u);
    const p = path.join(WEB, u);
    if (!fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => { throw new Error('404 ' + u); } });
    return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) });
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sandbox);
for (const f of ['charts.js', 'reports.js'])
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', f), 'utf8') + '\n;globalThis.' + (f === 'charts.js' ? 'Charts = Charts' : 'Reports = Reports') + ';', sandbox);
const E = sandbox.SETUE, Rep = sandbox.Reports;

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
