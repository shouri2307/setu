/* SETHU location-intelligence engine.
 * Pure data + scoring — no DOM. Turns a lat/lon into a structured, explainable report.
 * Every factor carries its weight, a plain-language note and a status:
 *   validated  = comes from the flood model tested on floods it never saw
 *   modelled   = derived from the model under a stated assumption
 *   indicative = open-map proximity, not legal/official status
 */
const SETUE = (() => {
  const D = {};
  const R = 6371000;
  const rad = x => x * Math.PI / 180;
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const lerp = (x, x0, x1, y0, y1) => y0 + (y1 - y0) * clamp((x - x0) / (x1 - x0), 0, 1);

  function hav(la1, lo1, la2, lo2) {
    const dp = rad(la2 - la1), dl = rad(lo2 - lo1);
    const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  // ---------- loading ----------
  async function load(onProgress) {
    const get = p => fetch(p).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
    const names = ['zones', 'model', 'reco', 'wardfeat', 'geo', 'hospitals', 'meta', 'rates', 'gov', 'hmda', 'hy'];
    const paths = ['data/zones.json', 'data/model.json', 'data/reco.json', 'data/wardfeat.json',
      'data/geo.json', 'data/hospitals.json', 'data/meta.json', 'data/rates.json', 'data/gov.json', 'data/hmda_lakes.json', 'data/hydraa_tanks.json'];
    const res = await Promise.all(paths.map((p, i) => get(p).catch(e => {
      if (names[i] === 'geo') return { poi: {}, water: [] };
      if (names[i] === 'rates') return { localities: [] };
      if (names[i] === 'hmda') return { lakes: [] };
      if (names[i] === 'hy') return { tanks: [], legend: {} };
      if (names[i] === 'gov') return { nalas: [], segments: [], drains: [], tanks: [], rivers: [], inundation: [] };
      throw e;
    })));
    names.forEach((n, i) => D[n] = res[i]);
    prep();
    return D;
  }

  function prep() {
    // ward bboxes for fast point-in-polygon
    D.wards = D.zones.wards.map(w => {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, cx = 0, cy = 0, n = 0;
      for (const r of w.rings) for (const p of r) {
        x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]);
        cx += p[0]; cy += p[1]; n++;
      }
      return { ...w, bb: [x0, y0, x1, y1], c: [cx / n, cy / n] };
    });
    D.wardById = new Map(D.wards.map(w => [w.id, w]));
    // water bodies: classify by size, precompute bbox. Pools, sewers and fountains are not lakes.
    const NOT_WATER = new Set(['pool', 'swimming_pool', 'sewer', 'wastewater', 'fountain', 'basin', 'reflecting_pool', 'drain']);
    const ringArea = (ring, k) => {
      let a = 0;
      for (let i = 0; i < ring.length; i++) {
        const p = ring[i], q = ring[(i + 1) % ring.length];
        a += (p[0] * k * 111320) * (q[1] * 110540) - (q[0] * k * 111320) * (p[1] * 110540);
      }
      return Math.abs(a / 2);
    };
    const classify = wb => {
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      for (const ring of wb.rings) for (const p of ring) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
      wb.bb = [x0, y0, x1, y1];
      const k = Math.cos(rad((y0 + y1) / 2));
      wb.area = wb.rings.reduce((s, r) => s + ringArea(r, k), 0);
      wb.cls = NOT_WATER.has(wb.kind) ? 'tiny' : wb.area >= 20000 ? 'lake' : wb.area >= 500 ? 'pond' : 'tiny';
    };
    D.geo.water.forEach(classify);
    // Official tank outlines (Telangana GIS land-use layer): add the ones OpenStreetMap does not already cover.
    let addedTanks = 0;
    const osmWater = D.geo.water.filter(w => w.cls !== 'tiny');
    for (const t of D.gov.tanks) {
      const ring = t.rings[0]; if (!ring) continue;
      let cy = 0, cx = 0; for (const q of ring) { cy += q[0]; cx += q[1]; } cy /= ring.length; cx /= ring.length;
      const covered = osmWater.some(w => cx >= w.bb[0] && cx <= w.bb[2] && cy >= w.bb[1] && cy <= w.bb[3] && w.rings.some(r => r.length > 3 && pip(cx, cy, r)));
      if (covered) continue;
      const wb = { name: '', kind: 'tank', src: 'gov', rings: t.rings.map(r => r.map(q => [q[1], q[0]])) };
      classify(wb); if (wb.cls === 'tiny') continue;
      D.geo.water.push(wb); addedTanks++;
    }
    D.addedTanks = addedTanks;
    D.lakes = D.geo.water.filter(w => w.cls === 'lake');
    D.ponds = D.geo.water.filter(w => w.cls === 'pond');
    const bb = pts => { let a = 1e9, b = 1e9, c = -1e9, d = -1e9; for (const q of pts) { if (q[0] < a) a = q[0]; if (q[0] > c) c = q[0]; if (q[1] < b) b = q[1]; if (q[1] > d) d = q[1]; } return [a, b, c, d]; };
    const G = D.gov;
    for (const n of G.nalas) n._b = n.paths.map(bb);
    for (const sg of G.segments) sg._b = sg.paths.map(bb);
    G._drainB = G.drains.map(bb);
    for (const t of G.tanks.concat(G.rivers)) t._b = t.rings.map(bb);
    // HMDA notified-lake list, keyed by exact normalised name. A status is only attached when the name is unambiguous:
    // unique across the whole list, or unique within Hyderabad district. Names repeat widely, so we never guess.
    D.hmdaIdx = new Map();
    for (const l of D.hmda.lakes) { const k = (l.name || '').toLowerCase().replace(/[^a-z0-9]/g, ''); if (k) { if (!D.hmdaIdx.has(k)) D.hmdaIdx.set(k, []); D.hmdaIdx.get(k).push(l); } }
    for (const t of D.hy.tanks) t._b = t.rings.map(bb);
    D.scen = D.model.scenarios_mm;
    D.thr = D.model.flood_threshold_m;
    // searchable names (offline geosearch)
    D.index = [];
    // featured landmark: the event venue, so it is always one search away
    D.index.push({ name: 'Cyber Gardens Convention Centre', kind: 'Landmark · HITEC City', lat: 17.4547214, lon: 78.3779507 });
    for (const w of D.wards) D.index.push({ name: w.name.replace(/^Ward \d+ /, ''), kind: 'Ward', lat: w.c[1], lon: w.c[0], ward: w.id });
    const searchCats = ['hospital', 'college', 'school', 'metro', 'market', 'park'];
    for (const c of searchCats) for (const p of (D.geo.poi[c] || [])) if (p[2]) D.index.push({ name: p[2], kind: c, lat: p[0], lon: p[1] });
    for (const wb of D.lakes) if (wb.name) {
      const r = wb.rings[0]; let cx = 0, cy = 0; r.forEach(p => { cx += p[0]; cy += p[1]; });
      D.index.push({ name: wb.name, kind: 'lake', lat: cy / r.length, lon: cx / r.length });
    }
  }

  // ---------- geometry ----------
  function pip(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if (((yi > lat) !== (yj > lat)) && (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }
  function segDist(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    let t = l2 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0; t = clamp(t);
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }
  function distToRing(lat, lon, ring) {
    const k = Math.cos(rad(lat)), X = p => (p[0] - lon) * k * 111320, Y = p => (p[1] - lat) * 110540;
    let m = 1e12;
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      m = Math.min(m, segDist(0, 0, X(a), Y(a), X(b), Y(b)));
    }
    return m;
  }

  function inBounds(lat, lon) {
    const b = D.zones.bounds; return lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
  }
  function locate(lat, lon) {
    for (const w of D.wards) {
      if (lon < w.bb[0] || lon > w.bb[2] || lat < w.bb[1] || lat > w.bb[3]) continue;
      let ins = false;
      for (const r of w.rings) if (pip(lon, lat, r)) ins = !ins;
      if (ins) return { id: w.id, name: w.name, exact: true };
    }
    // fall back to nearest ward centroid if inside the overall box (gaps between polygons)
    if (!inBounds(lat, lon)) return null;
    let best = null, bd = 1e12;
    for (const w of D.wards) { const d = hav(lat, lon, w.c[1], w.c[0]); if (d < bd) { bd = d; best = w; } }
    return bd < 3500 ? { id: best.id, name: best.name, exact: false } : null;
  }

  // Peripheral addresses (Medchal, Shamshabad, Patancheru...) lie outside the 145 wards the flood model covers.
  // We still build a report for them (facilities, lakes, terrain, air) but never apply the ward flood model.
  function locateExtended(lat, lon) {
    let best = null, bd = 1e12;
    for (const w of D.wards) { const d = hav(lat, lon, w.c[1], w.c[0]); if (d < bd) { bd = d; best = w; } }
    return bd <= 22000 ? { id: best.id, name: 'Outside the 145 GHMC wards', nearest: best.name, exact: false, outside: true, km: bd / 1000 } : null;
  }

  function nearest(cat, lat, lon, k = 3, rowsOverride) {
    const rows = rowsOverride || D.geo.poi[cat] || [];
    const out = [];
    for (const p of rows) {
      const d = hav(lat, lon, p[0], p[1]);
      if (out.length < k || d < out[out.length - 1].d) {
        out.push({ name: p[2], lat: p[0], lon: p[1], d });
        out.sort((a, b) => a.d - b.d); if (out.length > k) out.pop();
      }
    }
    return out;
  }
  function countWithin(cat, lat, lon, r, rowsOverride) {
    let n = 0; for (const p of (rowsOverride || D.geo.poi[cat] || [])) if (hav(lat, lon, p[0], p[1]) <= r) n++; return n;
  }
  function poisWithin(cat, lat, lon, r) {
    return (D.geo.poi[cat] || []).filter(p => hav(lat, lon, p[0], p[1]) <= r).map(p => ({ name: p[2], lat: p[0], lon: p[1] }));
  }

  // ---------- official drainage records (Telangana GIS: GHMC nalas & vulnerability map) ----------
  function distToPathLL(lat, lon, path) {   // open polyline stored as [lat, lon] points
    const k = Math.cos(rad(lat)); let m = 1e12;
    for (let i = 0; i < path.length - 1; i++) {
      const ax = (path[i][1] - lon) * k * 111320, ay = (path[i][0] - lat) * 110540, bx = (path[i + 1][1] - lon) * k * 111320, by = (path[i + 1][0] - lat) * 110540;
      const d = segDist(0, 0, ax, ay, bx, by); if (d < m) m = d;
    }
    return m;
  }
  function pipLL(lat, lon, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const yi = ring[i][0], xi = ring[i][1], yj = ring[j][0], xj = ring[j][1];
      if (((yi > lat) !== (yj > lat)) && (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }
  const near = (b, lat, lon, padDeg) => lat >= b[0] - padDeg && lat <= b[2] + padDeg && lon >= b[1] - padDeg && lon <= b[3] + padDeg;
  function govFacts(lat, lon) {
    const G = D.gov, pad = .006; let nala = null, seg = null, drainNear = null, drains150 = 0, tank = null, river = null, inund = null, in5 = 0, in10 = 0;
    for (const n of G.nalas) n.paths.forEach((p, i) => { if (!near(n._b[i], lat, lon, pad)) return; const d = distToPathLL(lat, lon, p); if (!nala || d < nala.d) nala = { d, n }; });
    for (const sg of G.segments) sg.paths.forEach((p, i) => { if (!near(sg._b[i], lat, lon, pad)) return; const d = distToPathLL(lat, lon, p); if (!seg || d < seg.d) seg = { d, s: sg }; });
    G.drains.forEach((p, i) => { if (!near(G._drainB[i], lat, lon, pad)) return; const d = distToPathLL(lat, lon, p); if (drainNear == null || d < drainNear) drainNear = d; if (d <= 150) drains150++; });
    const poly = (list, cur) => { let best = cur; for (const t of list) t.rings.forEach((r, i) => { if (!near(t._b[i], lat, lon, .012)) return; const inside = pipLL(lat, lon, r), d = inside ? 0 : distToPathLL(lat, lon, r); if (!best || d < best.d) best = { d, inside, name: t.name }; }); return best; };
    tank = poly(G.tanks, null); river = poly(G.rivers, null);
    for (const q of G.inundation) { const d = hav(lat, lon, q[0], q[1]); if (!inund || d < inund.d) inund = { d, name: q[2] }; if (d <= 500) in5++; if (d <= 1000) in10++; }
    return { nala: nala && nala.d <= 1500 ? { d: nala.d, name: nala.n.name, circle: nala.n.circle, len_m: nala.n.len_m } : null,
      seg: seg && seg.d <= 300 ? { d: seg.d, nala: seg.s.nala, prop_w: seg.s.prop_w, ext_w: seg.s.ext_w } : null,
      drainNearM: drainNear, drains150, tank, river, inund: inund && inund.d <= 3000 ? inund : null, inund500: in5, inund1k: in10 };
  }

  const HY_LABEL = { L: 'Live (water present)', PB: 'Partially encroached — built-up', TB: 'Totally encroached — built-up', PA: 'Partially encroached — agriculture', TA: 'Totally encroached — agriculture', '?': 'not classified' };
  // Nearest HYDRAA / TGRAC water-body polygon (named tanks, 2014 vs 2023 satellite status)
  function hyFacts(lat, lon) {
    let best = null, enc500 = 0;
    for (const t of D.hy.tanks) t.rings.forEach((r, i) => {
      if (!near(t._b[i], lat, lon, .03)) return;
      const inside = pipLL(lat, lon, r), d = inside ? 0 : distToPathLL(lat, lon, r);
      if (d <= 500 && t.s23 !== 'L' && t.s23 !== '?') enc500++;
      if (!best || d < best.d) best = { d, inside, t };
    });
    if (!best || best.d > 3000) return null;
    const t = best.t;
    return { d: best.d, inside: best.inside, name: t.name, village: t.village, mandal: t.mandal, admin: t.admin, origin: t.origin, s14: t.s14, s23: t.s23, enc500 };
  }
  const loose = s => (s || '').toLowerCase().replace(/[^a-z]/g, '');
  const sameArea = (a, b) => { a = loose(a); b = loose(b); return !!a && !!b && (a.includes(b) || b.includes(a)); };
  function hmdaFor(name, hint) {
    const k = (name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    let list = D.hmdaIdx.get(k);
    if (!list) return null;
    if (hint && (hint.village || hint.mandal)) {     // a government tank name is only trusted if the area agrees
      list = list.filter(x => sameArea(x.village, hint.village) || sameArea(x.mandal, hint.village) || sameArea(x.mandal, hint.mandal) || sameArea(x.village, hint.mandal));
      if (!list.length) return null;
    }
    if (list.length === 1) return list[0];
    const hyd = list.filter(x => x.district === 'Hyderabad');
    return hyd.length === 1 ? hyd[0] : null;
  }
  const hmdaLink = h => h && h.ftl_url ? h.ftl_url.replace(/^http:/, 'https:') : null;
  const hmdaText = h => !h ? null : `HMDA's lake portal lists ${h.name} (${h.district}, ${h.mandal}) — ${h.final ? 'final notification ' + h.final + (h.prelim ? ' (preliminary ' + h.prelim + ')' : '') : h.prelim ? 'preliminary notification ' + h.prelim + '; no final notification date shown' : 'no notification dates shown'}`;

  function waterInfo(lat, lon) {
    const one = (list) => {
      let best = null;
      for (const wb of list) {
        const pad = 0.012; // ~1.3 km prefilter
        const bb = wb.bb; if (lon < bb[0] - pad || lon > bb[2] + pad || lat < bb[1] - pad || lat > bb[3] + pad) continue;
        const inside = wb.rings.some(r => r.length > 3 && pip(lon, lat, r));
        const d = inside ? 0 : Math.min(...wb.rings.map(r => distToRing(lat, lon, r)));
        if (!best || d < best.d - 40 || (d < best.d + 40 && wb.name && !best.name)) best = { name: wb.name || '', d, inside, area: wb.area, ref: wb, gov: wb.src === 'gov' };
      }
      return best;
    };
    const lake = one(D.lakes), pond = one(D.ponds);
    let pondsNear = 0;
    for (const wb of D.ponds) {
      const bb = wb.bb; if (lon < bb[0] - .006 || lon > bb[2] + .006 || lat < bb[1] - .006 || lat > bb[3] + .006) continue;
      if (Math.min(...wb.rings.map(r => distToRing(lat, lon, r))) <= 500) pondsNear++;
    }
    return { lake, pond, pondsNear };
  }

  // ---------- model lookups ----------
  function depthAt(wid, mm) {
    if (mm <= 0) return 0;
    const sc = D.scen, dep = k => (D.model.depths[String(k)] || {})[String(wid)] || 0;
    if (mm <= sc[0]) return dep(sc[0]) * mm / sc[0];
    for (let i = 1; i < sc.length; i++) if (mm <= sc[i]) return lerp(mm, sc[i - 1], sc[i], dep(sc[i - 1]), dep(sc[i]));
    return dep(sc[sc.length - 1]);
  }
  const cutAt = (wid, mm) => (D.model.cutoffs[String(mm)] || []).includes(wid);
  function floodsAtMm(wid) {
    for (const mm of D.scen) if ((D.model.depths[String(mm)] || {})[String(wid)] >= D.thr) return mm;
    return null;
  }

  // ---------- live APIs (free, keyless) ----------
  async function elevationProfile(lat, lon) {
    const pts = [[lat, lon]];
    for (const r of [300, 600]) for (let a = 0; a < 360; a += 45) {
      const dy = r * Math.cos(rad(a)) / 110540, dx = r * Math.sin(rad(a)) / (111320 * Math.cos(rad(lat)));
      pts.push([lat + dy, lon + dx]);
    }
    try {
      const u = `https://api.open-meteo.com/v1/elevation?latitude=${pts.map(p => p[0].toFixed(5)).join(',')}&longitude=${pts.map(p => p[1].toFixed(5)).join(',')}`;
      const j = await fetch(u).then(r => r.json());
      const e = j.elevation; if (!e || e.length < pts.length) return null;
      const ring = e.slice(1), mean = ring.reduce((a, b) => a + b, 0) / ring.length;
      return { center: e[0], ringMean: mean, ringMin: Math.min(...ring), ringMax: Math.max(...ring), relief: e[0] - mean };
    } catch (e) { return null; }
  }
  async function rainOn(lat, lon, date) { // date 'YYYY-MM-DD' -> {days:[{date,mm}], max, sum3}
    const d = new Date(date + 'T00:00:00Z'), f = x => new Date(d.getTime() + x * 864e5).toISOString().slice(0, 10);
    const u = `https://archive-api.open-meteo.com/v1/archive?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&start_date=${f(-1)}&end_date=${f(1)}&daily=precipitation_sum&timezone=Asia%2FKolkata`;
    const j = await fetch(u).then(r => r.json());
    const t = j.daily.time, v = j.daily.precipitation_sum;
    const days = t.map((x, i) => ({ date: x, mm: v[i] == null ? 0 : v[i] }));
    return { days, onDay: (days.find(x => x.date === date) || {}).mm || 0, max: Math.max(...days.map(x => x.mm)), sum3: days.reduce((a, b) => a + b.mm, 0) };
  }
  async function forecast(lat, lon) {
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&daily=precipitation_sum,precipitation_probability_max&forecast_days=7&timezone=Asia%2FKolkata`;
    const j = await fetch(u).then(r => r.json());
    return j.daily.time.map((t, i) => ({ date: t, mm: j.daily.precipitation_sum[i] || 0, prob: j.daily.precipitation_probability_max ? j.daily.precipitation_probability_max[i] : null }));
  }
  const imd = mm => mm < 2.5 ? 'none/trace' : mm < 15.6 ? 'light' : mm < 64.5 ? 'moderate' : mm < 115.6 ? 'heavy' : mm < 204.5 ? 'very heavy' : 'extremely heavy';

  // ---------- the report ----------
  const FAC = [ // key, label, km at full score, km at zero score, weight  (scales tuned for the denser OSM + Overture data)
    ['hospital', 'Hospital', 0.3, 3, .20], ['school', 'School', 0.15, 1.5, .15], ['metro', 'Metro / rail station', 0.5, 6, .20],
    ['market', 'Market / supermarket', 0.2, 2, .15], ['bank', 'Bank', 0.15, 1.5, .05], ['park', 'Park', 0.15, 1.5, .10],
    ['bus', 'Bus station', 0.5, 5, .05], ['fire', 'Fire station', 1, 6, .05], ['police', 'Police station', 0.5, 4, .05]];

  function build(lat, lon, gp) {
    let ward = locate(lat, lon);
    if (!ward) ward = locateExtended(lat, lon);
    if (!ward) return { ok: false, lat, lon, reason: 'outside' };
    const outside = !!ward.outside;
    const wid = ward.id, wf = D.wardfeat[String(wid)] || {}, prof = (D.reco.recommendations[String(wid)] || {}).profile || {};
    const depth = {}; [100, 192, 300].forEach(m => depth[m] = depthAt(wid, m));
    const setu = {
      pct: wf.pct ?? 0, S: wf.S ?? 0, depth, floodsAtMm: floodsAtMm(wid), cut192: cutAt(wid, 192),
      baselineHosp: (D.model.baseline_hospital || {})[String(wid)] || null, upstream: wf.upstream_km2 || 0,
      lowFrac: wf.hand_low_frac || 0, builtup: wf.builtup_frac ?? null, area: wf.area_km2 || 0
    };
    const water = waterInfo(lat, lon);
    const fac = {}, gcats = (gp && gp.cats) || {};
    let usedGoogle = 0;
    for (const [k] of FAC) {
      const g = gcats[k] && gcats[k].length ? gcats[k] : null;   // Google results for this category, if any
      if (g) usedGoogle++;
      const n = nearest(k, lat, lon, 3, g);
      fac[k] = {
        nearest: n[0] || null, list: n, src: g ? 'google' : 'open',
        n1km: countWithin(k, lat, lon, 1000, g), n2km: countWithin(k, lat, lon, 2000, g), n3km: countWithin(k, lat, lon, 3000, g),
        capped: !!(g && g.length >= 15 && hav(lat, lon, g[g.length - 1][0], g[g.length - 1][1]) < 2000)
      };
    }
    const roadNear = {};   // distance (m) to the nearest sample point of each main-road class
    for (const cls of ['motorway', 'trunk', 'primary']) {
      let best = null;
      for (const p of ((D.geo.roads || {})[cls] || [])) { const d = hav(lat, lon, p[0], p[1]); if (best == null || d < best) best = d; }
      roadNear[cls] = best;
    }
    const arterial = [roadNear.motorway, roadNear.trunk, roadNear.primary].filter(x => x != null);
    const hubs = {
      work3: countWithin('work', lat, lon, 3000), work5: countWithin('work', lat, lon, 5000), nearestWork: nearest('work', lat, lon, 1)[0] || null,
      mall3: countWithin('mall', lat, lon, 3000), nearestMall: nearest('mall', lat, lon, 1)[0] || null, cinema3: countWithin('cinema', lat, lon, 3000)
    };
    const hospAll = nearest('hospital', lat, lon, 1)[0];
    const hy = hyFacts(lat, lon);
    // The government layer's labels are not always right (it names the Hussain Sagar polygon "Fox Sagar"), so when the
    // OpenStreetMap lake and the official polygon coincide we show the OSM name and keep the official label alongside.
    const osmNm = water.lake && water.lake.name && water.lake.d <= 150 ? water.lake.name : null;
    const hyShown = hy ? { ...hy, display: (osmNm && hy.d <= 150) ? osmNm : hy.name, govLabel: hy.name } : null;
    if (hyShown && osmNm && hyShown.d <= 150 && loose(osmNm) !== loose(hy.name)) hyShown.nameDiffers = true;
    const hmdaPick = (osmNm && hmdaFor(osmNm)) || (hy && hy.name && hy.d <= 400 && hmdaFor(hy.name, { village: hy.village, mandal: hy.mandal })) || null;
    const amb = nearest('ambulance', lat, lon, 1)[0] || null, amb3 = countWithin('ambulance', lat, lon, 3000);
    const industryNear = nearest('industry', lat, lon, 1)[0];
    const underpass1k = countWithin('underpass', lat, lon, 1000);
    const clinics1k = countWithin('clinic', lat, lon, 1000);
    const r = {
      ok: true, outside, lat, lon, ward, wid, setu, water, fac, prof, underpass1k, clinics1k, roadNear, hubs, gov: govFacts(lat, lon), hy: hyShown, amb, amb3, hmda: hmdaPick, arterialM: arterial.length ? Math.min(...arterial) : null,
      clinics15: countWithin('clinic', lat, lon, 1500),
      industry: industryNear || null, terrain: null, hospAll,
      source: usedGoogle >= 4 ? 'google' : 'open'
    };
    return r;
  }

  // ---------- scoring (every part exposes weight + note + status) ----------
  function normalize(parts) {
    const av = parts.filter(p => p.v != null), tw = av.reduce((a, p) => a + p.w, 0) || 1;
    let s = 0; for (const p of av) { p.wn = p.w / tw; p.pts = p.v * p.wn * 100; s += p.pts; }
    return { score: Math.round(s), parts };
  }
  function lakeV(w) { // proximity of the nearest mapped lake/tank
    if (!w.lake) return 0;
    const d = w.lake.d; return d <= 30 ? 1 : d <= 100 ? lerp(d, 30, 100, 1, .75) : d <= 300 ? lerp(d, 100, 300, .75, .3) : d <= 800 ? lerp(d, 300, 800, .3, 0) : 0;
  }
  function lakeBand(w) {
    if (!w.lake) return { band: 'clear', text: 'No mapped lake/tank within ~1.3 km' };
    const d = w.lake.d, nm = w.lake.name || (w.lake.gov ? 'an official tank outline (unnamed in the GIS layer)' : 'an unnamed water body');
    if (w.lake.inside) return { band: 'inside', text: `Pin falls inside the mapped water spread of ${nm}` };
    if (d <= 100) return { band: 'very close', text: `${Math.round(d)} m from ${nm}` };
    if (d <= 300) return { band: 'near', text: `${Math.round(d)} m from ${nm}` };
    if (d <= 800) return { band: 'moderate', text: `${Math.round(d)} m from ${nm}` };
    return { band: 'clear', text: `${Math.round(d)} m from ${nm}` };
  }
  const pocketV = t => !t ? null : t.relief <= -8 ? 1 : t.relief <= -2 ? lerp(t.relief, -2, -8, .15, 1) : t.relief < 2 ? lerp(t.relief, 2, -2, 0, .15) : 0;
  const pocketNote = t => !t ? 'Elevation service unavailable — not used' :
    `Pin ${t.center.toFixed(0)} m vs ${t.ringMean.toFixed(0)} m average within 600 m (${t.relief >= 0 ? '+' : ''}${t.relief.toFixed(1)} m)`;
  const depthV = d => clamp(d / 1.0);

  const nalaV = (g => g == null ? 0 : g <= 50 ? 1 : g <= 150 ? lerp(g, 50, 150, 1, .7) : g <= 400 ? lerp(g, 150, 400, .7, .2) : g <= 800 ? lerp(g, 400, 800, .2, 0) : 0);
  const inundV = (g => g == null ? 0 : g <= 300 ? 1 : g <= 800 ? lerp(g, 300, 800, 1, .3) : g <= 1500 ? lerp(g, 800, 1500, .3, 0) : 0);
  const nalaNote = r => r.gov.nala ? `${r.gov.nala.name} runs ${Math.round(r.gov.nala.d)} m away (GHMC nala records)` : 'No GHMC-mapped nala within 1.5 km';
  const inundNote = r => r.gov.inund ? `${r.gov.inund.name} · ${Math.round(r.gov.inund.d)} m (official inundation list)` : 'No listed inundation area within 3 km';
  function waterRisk(r) {
    const s = r.setu, w = r.water, t = r.terrain, lb = lakeBand(w);
    return normalize([
      { id: 'sus', label: 'Flood-susceptibility rank (SETHU model)', w: .40, v: r.outside ? null : s.pct, status: 'validated', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : `${Math.round(s.pct * 100)}th percentile of Hyderabad's 145 wards (higher floods earlier). Tested on floods it never saw.` },
      { id: 'depth', label: 'Modelled depth in a 192 mm storm', w: .18, v: r.outside ? null : depthV(s.depth[192]), status: 'modelled', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : s.depth[192] >= D.thr ? `${s.depth[192].toFixed(2)} m at ${r.ward.name} (Oct-2020-size rain)` : 'Ward stays dry at 192 mm' },
      { id: 'lake', label: 'Lake / tank proximity', w: .12, v: lakeV(w), status: 'indicative', note: lb.text },
      { id: 'pocket', label: 'Low pocket vs surroundings', w: .10, v: pocketV(t), status: 'indicative', note: pocketNote(t) },
      { id: 'up', label: 'Upstream catchment draining here', w: .06, v: r.outside ? null : clamp(Math.log1p(s.upstream) / Math.log1p(200)), status: 'validated', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : `${s.upstream.toFixed(0)} km² of neighbouring wards drain through this ward` },
      { id: 'nala', label: 'Mapped nala nearby', w: .08, v: nalaV(r.gov.nala && r.gov.nala.d), status: 'official', note: nalaNote(r) },
      { id: 'inund', label: 'Officially listed inundation areas', w: .06, v: inundV(r.gov.inund && r.gov.inund.d), status: 'official', note: inundNote(r) }
    ]);
  }
  // Tier cut-points per score (A..E). Calibrated on the distribution of all 145 ward centroids so that
  // roughly a quarter of the city sits in A, a quarter in B, and the top ~8-10% in E.
  const CUTS = { water: [18, 32, 46, 60], motor: [20, 30, 42, 54], prop: [16, 26, 38, 50], health: [20, 32, 44, 56] };
  const TIER_NAMES = [['A', 'Low'], ['B', 'Guarded'], ['C', 'Moderate'], ['D', 'High'], ['E', 'Severe']];
  function tier(score, line = 'water') {
    const c = CUTS[line] || CUTS.water; let i = 0; while (i < c.length && score >= c[i]) i++;
    return { letter: TIER_NAMES[i][0], label: TIER_NAMES[i][1], score };
  }

  function development(r) {
    const parts = FAC.map(([k, label, near, far, w]) => {
      const f = r.fac[k], d = f.nearest ? f.nearest.d / 1000 : null;
      const v = d == null ? 0 : 1 - clamp((d - near) / (far - near));
      return { id: k, label, w, v, status: 'indicative', note: f.nearest ? `${f.nearest.name || 'nearest'} · ${(d).toFixed(1)} km · ${f.n1km} within 1 km` : 'none mapped nearby' };
    });
    const tw = parts.reduce((a, p) => a + p.w, 0);
    return { score: Math.round(parts.reduce((a, p) => a + p.v * p.w, 0) / tw * 100), parts };
  }

  function motorRisk(r) {
    const s = r.setu, t = r.terrain, dens = r.prof.density_class === 'dense' ? 1 : .55;
    return normalize([
      { id: 'sus', label: 'Waterlogging susceptibility (SETHU)', w: .22, v: r.outside ? null : s.pct, status: 'validated', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : `${Math.round(s.pct * 100)}th percentile of 145 wards` },
      { id: 'depth', label: 'Water depth a car would meet (192 mm)', w: .26, v: r.outside ? null : clamp(s.depth[192] / 0.6), status: 'modelled', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : s.depth[192] >= D.thr ? `${s.depth[192].toFixed(2)} m — vehicles stall near 0.3–0.5 m` : 'Dry at 192 mm' },
      { id: 'underpass', label: 'Underpasses / culvert roads within 1 km', w: .13, v: clamp(r.underpass1k / 3), status: 'indicative', note: `${r.underpass1k} mapped (they fill first and trap vehicles)` },
      { id: 'pocket', label: 'Low pocket (parking / road dips)', w: .12, v: pocketV(t), status: 'indicative', note: pocketNote(t) },
      { id: 'dens', label: 'Traffic & parking density', w: .12, v: dens, status: 'indicative', note: `${r.prof.density_class || 'mixed'} built-up ward` },
      { id: 'inund', label: 'Officially listed inundation areas nearby', w: .15, v: inundV(r.gov.inund && r.gov.inund.d), status: 'official', note: inundNote(r) }
    ]);
  }
  function propertyRisk(r) {
    const s = r.setu, w = r.water, t = r.terrain, lb = lakeBand(w);
    const fire = r.fac.fire.nearest ? r.fac.fire.nearest.d / 1000 : 9;
    const ind = r.industry ? r.industry.d : 9999;
    return normalize([
      { id: 'sus', label: 'Flood susceptibility (SETHU)', w: .22, v: r.outside ? null : s.pct, status: 'validated', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : `${Math.round(s.pct * 100)}th percentile of 145 wards` },
      { id: 'depth', label: 'Modelled depth in a 192 mm storm', w: .18, v: r.outside ? null : depthV(s.depth[192]), status: 'modelled', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : s.depth[192] >= D.thr ? `${s.depth[192].toFixed(2)} m ground-floor water` : 'Dry at 192 mm' },
      { id: 'lake', label: 'Lake / tank proximity', w: .12, v: lakeV(w), status: 'indicative', note: lb.text },
      { id: 'pocket', label: 'Low pocket vs surroundings', w: .08, v: pocketV(t), status: 'indicative', note: pocketNote(t) },
      { id: 'fire', label: 'Fire-service reach', w: .12, v: clamp((fire - 2) / 5), status: 'indicative', note: r.fac.fire.nearest ? `Nearest fire station ${fire.toFixed(1)} km` : 'No fire station mapped nearby' },
      { id: 'dens', label: 'Dense building (fire spread)', w: .05, v: r.prof.density_class === 'dense' ? 1 : .5, status: 'indicative', note: `${r.prof.density_class || 'mixed'} ward` },
      { id: 'ind', label: 'Industrial land nearby', w: .08, v: ind < 500 ? 1 : ind < 1500 ? lerp(ind, 500, 1500, 1, .2) : ind < 3000 ? lerp(ind, 1500, 3000, .2, 0) : 0, status: 'indicative', note: r.industry ? `Industrial zone ${(ind / 1000).toFixed(1)} km away` : 'None mapped within the area' },
      { id: 'nala', label: 'Mapped nala nearby (flood / widening)', w: .15, v: nalaV(r.gov.nala && r.gov.nala.d), status: 'official', note: nalaNote(r) }
    ]);
  }
  function healthRisk(r) {
    const hd = r.fac.hospital.nearest ? r.fac.hospital.nearest.d / 1000 : 12;
    const h3 = r.fac.hospital.n3km;
    return normalize([
      { id: 'dist', label: 'Distance to nearest hospital', w: .30, v: clamp((hd - 1) / 7), status: 'indicative', note: r.fac.hospital.nearest ? `${r.fac.hospital.nearest.name || 'Nearest hospital'} · ${hd.toFixed(1)} km` : 'No hospital mapped nearby' },
      { id: 'cnt', label: 'Hospitals within 3 km', w: .22, v: clamp(1 - h3 / 6), status: 'indicative', note: `${h3}${r.fac.hospital.capped ? '+' : ''} mapped within 3 km (${r.source === 'google' ? 'Google Places' : 'OpenStreetMap + Overture Maps'})` },
      { id: 'amb', label: 'Nearest 108 / government ambulance station', w: .10, v: r.amb ? clamp((r.amb.d / 1000 - 1.5) / 6.5) : 1, status: 'official', note: r.amb ? `${r.amb.name || 'Ambulance station'} · ${(r.amb.d / 1000).toFixed(1)} km · ${r.amb3} within 3 km (Telangana health GIS)` : 'No government ambulance station mapped nearby' },
      { id: 'clin', label: 'Clinics within 1.5 km', w: .13, v: clamp(1 - r.clinics15 / 5), status: 'indicative', note: `${r.clinics15} mapped (OpenStreetMap + Overture Maps)` },
      { id: 'cut', label: 'Hospital road cut in a 192 mm storm', w: .15, v: r.outside ? null : r.setu.cut192 ? 1 : 0, status: 'modelled', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : r.setu.cut192 ? 'Modelled road to the nearest hospital is blocked' : 'Road stays open in the model' },
      { id: 'sus', label: 'Waterlogging on the way (SETHU rank)', w: .10, v: r.outside ? null : r.setu.pct, status: 'validated', note: r.outside ? 'Flood model covers the 145 GHMC wards only — not applied at this address' : `${Math.round(r.setu.pct * 100)}th percentile of 145 wards` }
    ]);
  }
  const LOADING = { A: 'no loading', B: '+3–6%', C: '+8–12%', D: '+15–25%', E: '+30–45% or refer' };

  // ---------- Location Score: seven pillars, water/flood is only one of them ----------
  const PILLAR_W = { water: .22, health: .14, daily: .14, transit: .14, green: .09, air: .09, services: .08, jobs: .10 };
  function pillars(r) {
    const part = (arr, id) => arr.find(p => p.id === id), dev = r.scores.dev.parts, f = r.fac;
    const dn = k => f[k].nearest ? f[k].nearest.d / 1000 : null;
    const devV = (id) => (part(dev, id) || { v: 0 }).v;
    const lk = r.water.lake ? r.water.lake.d : null;
    const lakeAmenity = lk == null ? .3 : lk < 100 ? .5 : lk < 200 ? .75 : lk <= 1500 ? 1 : .3;
    const parkScore = clamp(f.park.n1km / 3);
    const aq = r.air ? r.air.aqi : null;
    const aqScore = aq == null ? null : aq <= 50 ? 1 : aq <= 100 ? lerp(aq, 50, 100, 1, .65) : aq <= 150 ? lerp(aq, 100, 150, .65, .4) : aq <= 200 ? lerp(aq, 150, 200, .4, .2) : lerp(aq, 200, 300, .2, 0);
    const fire = dn('fire'), pol = dn('police');
    const svc = (fire == null ? 0 : 1 - clamp((fire - 2) / 5)) * .5 + (pol == null ? 0 : 1 - clamp((pol - 1) / 3)) * .5;
    const km = x => x == null ? 'none found' : x < .95 ? Math.round(x * 100) * 10 + ' m' : x.toFixed(1) + ' km';
    const items = [
      { id: 'water', label: 'Water & flood safety', v: r.outside ? null : 1 - r.scores.water.score / 100, status: r.outside ? 'indicative' : 'validated', note: r.outside ? 'Not scored — outside the 145 GHMC wards the flood model covers' : `Water-risk tier ${r.tiers.water.letter} · ${r.setu.depth[192] >= D.thr ? '~' + r.setu.depth[192].toFixed(1) + ' m in a 192 mm storm' : 'dry at 192 mm'}` },
      { id: 'health', label: 'Health-care access', v: 1 - r.scores.health.score / 100, status: 'indicative', note: `Nearest hospital ${km(dn('hospital'))} · ${f.hospital.n3km}${f.hospital.capped ? '+' : ''} within 3 km` },
      { id: 'daily', label: 'Schools & daily needs', v: (devV('school') * .4 + devV('market') * .35 + devV('bank') * .25), status: 'indicative', note: `School ${km(dn('school'))} · market ${km(dn('market'))} · bank ${km(dn('bank'))}` },
      { id: 'transit', label: 'Transit & main roads', v: r.arterialM == null ? (devV('metro') * .65 + devV('bus') * .35) : (devV('metro') * .45 + devV('bus') * .2 + (1 - clamp((r.arterialM / 1000 - .2) / 2.8)) * .35), status: 'indicative', note: `Metro / rail ${km(dn('metro'))} · bus ${km(dn('bus'))} · main road ${r.arterialM == null ? 'n/a' : km(r.arterialM / 1000)}` },
      { id: 'green', label: 'Parks & lakes', v: parkScore * .7 + lakeAmenity * .3, status: 'indicative', note: `${f.park.n1km}${f.park.capped ? '+' : ''} parks within 1 km · ${r.water.lake ? (r.water.lake.inside ? 'inside a lake outline' : 'lake ' + km(lk / 1000)) : 'no lake within ~1.3 km'}` },
      { id: 'air', label: 'Air quality (live)', v: aqScore, status: 'indicative', note: aq == null ? 'Live reading unavailable — pillar not scored' : `US AQI ${aq} · ${r.air.band}` },
      { id: 'jobs', label: 'Jobs & lifestyle hubs', v: clamp(r.hubs.work5 / 60) * .6 + clamp(r.hubs.mall3 / 3) * .25 + clamp(r.hubs.cinema3 / 2) * .15, status: 'indicative', note: `${r.hubs.work5}${r.hubs.work5 >= 1 ? '' : ''} IT / office places within 5 km · ${r.hubs.mall3} malls and ${r.hubs.cinema3} cinemas within 3 km` },
      { id: 'services', label: 'Fire & police reach', v: svc, status: 'indicative', note: `Fire station ${km(fire)} · police ${km(pol)}` }
    ];
    let tw = 0, sum = 0;
    for (const it of items) { it.w = PILLAR_W[it.id]; if (it.v != null) { tw += it.w; sum += it.v * it.w; } }
    const score = Math.round(sum / tw * 100), label = score >= 90 ? 'Excellent' : score >= 80 ? 'Good' : score >= 70 ? 'Fair' : 'Challenged';
    for (const it of items) if (it.v != null) { it.wn = it.w / tw; it.pts = it.v * it.wn * 100; }
    const ranked = items.filter(i => i.v != null).sort((a, b) => b.v - a.v);
    return { items, score, label, best: ranked.slice(0, 2), worst: ranked.slice(-2).reverse() };
  }

  function buyerVerdict(r) {
    const wr = r.scores.water, dev = r.scores.dev, lb = lakeBand(r.water);
    const flags = [];
    if (['inside', 'very close'].includes(lb.band)) flags.push({ lvl: 'red', t: 'Very close to a lake/tank', d: `${lb.text}. In Hyderabad, plots near lake full-tank-level (FTL) and buffer zones can face demolition. ${r.hmda ? hmdaText(r.hmda) + '. ' : ''}Get the FTL/buffer status confirmed in writing (HMDA lakes portal: lakes.hmda.gov.in) before paying anything.` });
    else if (lb.band === 'near') flags.push({ lvl: 'amber', t: 'Near a lake/tank', d: `${lb.text}. Check the FTL/buffer certificate and the approved layout.` });
    if (r.outside) flags.push({ lvl: 'amber', t: 'Outside the validated flood model', d: `This address is about ${r.ward.km.toFixed(1)} km beyond the 145 GHMC wards the flood model covers, so no flood depth or ranking is shown. Lakes, terrain, facilities and air quality below still apply — ask locally about waterlogging.` });
    else if (r.setu.depth[192] >= .5) flags.push({ lvl: 'red', t: 'Heavy flooding in a storm like Oct 2020', d: `Modelled ~${r.setu.depth[192].toFixed(1)} m of water in this ward at 192 mm. Ask about past waterlogging and where the nearest nala runs.` });
    else if (r.setu.depth[192] >= D.thr) flags.push({ lvl: 'amber', t: 'Floods in a 2020-size storm', d: `Modelled ~${r.setu.depth[192].toFixed(1)} m in this ward at 192 mm.` });
    if (r.hy && r.hy.s23 !== 'L' && r.hy.s23 !== '?' && r.hy.d <= 250) {
      const who = `${r.hy.display || 'An unnamed tank'}${r.hy.village ? ' (' + r.hy.village + (r.hy.mandal ? ', ' + r.hy.mandal : '') + ')' : ''}`;
      flags.push({ lvl: (r.hy.inside || r.hy.d <= 60) && (r.hy.s23 === 'TB' || r.hy.s23 === 'PB') ? 'red' : 'amber', t: 'Nearby tank is flagged as encroached', d: `${who} is classed "${HY_LABEL[r.hy.s23]}" in the TGRAC / HYDRAA 2023 satellite assessment (2014: ${HY_LABEL[r.hy.s14]}) and lies ${r.hy.inside ? 'under this pin' : Math.round(r.hy.d) + ' m away'}. ${r.hmda ? hmdaText(r.hmda) + '. ' : ''}This is a satellite classification, not a legal order — verify FTL and buffer with HMDA / HYDRAA before paying.` });
    }
    if (r.gov.nala && r.gov.nala.d <= 150) {
      const sg = r.gov.seg, widen = sg && sg.prop_w > (sg.ext_w || 0) * 1.5 && sg.d <= 150;
      flags.push({ lvl: r.gov.nala.d <= 60 ? 'red' : 'amber', t: `Mapped nala close by: ${r.gov.nala.name}`, d: `GHMC's nala records place ${r.gov.nala.name} about ${Math.round(r.gov.nala.d)} m away.${widen ? ` The nearest segment shows an existing width of ${sg.ext_w} m against a proposed width of ${sg.prop_w} m — ask GHMC whether widening could touch this plot.` : ''} Check the plot against the nala buffer before paying.` });
    }
    if (r.gov.inund && r.gov.inund.d <= 500) flags.push({ lvl: r.gov.inund.d <= 250 ? 'red' : 'amber', t: 'Officially listed inundation area nearby', d: `${r.gov.inund.name} is on GHMC's inundation list, about ${Math.round(r.gov.inund.d)} m away.` });
    if (r.terrain && r.terrain.relief <= -4) flags.push({ lvl: 'amber', t: 'Sits lower than its surroundings', d: pocketNote(r.terrain) + '. Water tends to collect in low pockets.' });
    if (!r.outside && r.setu.cut192) flags.push({ lvl: 'amber', t: 'Hospital road can be cut in a big storm', d: 'The modelled road to the nearest hospital is blocked at 192 mm.' });
    if (dev.score < 35) flags.push({ lvl: 'amber', t: 'Thin facilities nearby', d: 'Few mapped hospitals, schools or transit stops close by.' });
    if (!flags.length) flags.push({ lvl: 'green', t: 'No major water red flags in the open data', d: 'Still verify documents and ground reality.' });
    const worst = flags.some(f => f.lvl === 'red') ? 'red' : flags.some(f => f.lvl === 'amber') ? 'amber' : 'green';
    return { flags, worst, headline: r.outside && worst !== 'red' ? 'Judge on surroundings' : worst === 'red' ? 'High caution' : worst === 'amber' ? 'Proceed carefully' : 'Looks reasonable' };
  }

  function analyse(r) {
    r.scores = { water: waterRisk(r), dev: development(r), motor: motorRisk(r), prop: propertyRisk(r), health: healthRisk(r) };
    r.tiers = { water: tier(r.scores.water.score, 'water'), motor: tier(r.scores.motor.score, 'motor'), prop: tier(r.scores.prop.score, 'prop'), health: tier(r.scores.health.score, 'health') };
    r.buyer = buyerVerdict(r);
    r.pillars = pillars(r);
    return r;
  }
  async function report(lat, lon, gp) {
    const r = build(lat, lon, gp); if (!r.ok) return r;
    analyse(r);
    return r;
  }
  async function airNow(lat, lon) {
    try {
      const j = await fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=us_aqi,pm2_5&timezone=Asia%2FKolkata`).then(r => r.json());
      const c = j.current; if (!c || c.us_aqi == null) return null;
      const a = c.us_aqi, band = a <= 50 ? 'Good' : a <= 100 ? 'Moderate' : a <= 150 ? 'Unhealthy for sensitive groups' : a <= 200 ? 'Unhealthy' : 'Very unhealthy';
      return { aqi: a, pm25: c.pm2_5, band, time: c.time };
    } catch (e) { return null; }
  }
  // Rate lookup: nearest locality within 2.5 km, else a locality in the same ward, else nearest within 4 km.
  // kind 'apt' = Rs/sq ft apartments, 'plot' = Rs/sq yd land. Asking prices only — see rates.json caution.
  function market(lat, lon, wid, kind = 'apt') {
    const has = l => kind === 'plot' ? l.plot && l.plot.low != null : l.low != null;
    const L = (D.rates.localities || []).filter(has);
    let best = null, inWard = null;
    for (const l of L) {
      const d = hav(lat, lon, l.lat, l.lon);
      if (!best || d < best.d) best = { loc: l, d };
      if (wid != null && l.ward === wid && (!inWard || d < inWard.d)) inWard = { loc: l, d };
    }
    if (best && best.d <= 2500) return best;
    if (inWard) return inWard;
    return best && best.d <= 4000 ? best : null;
  }
  function priceBand(m, sqft) { return m && sqft > 0 ? { low: m.loc.low * sqft, high: m.loc.high * sqft, tLow: m.loc.typical[0] * sqft, tHigh: m.loc.typical[1] * sqft } : null; }
  function curve(wid) { return D.scen.map(mm => ({ mm, depth: depthAt(wid, mm) })); }
  // Telangana urban residential duties (secondary sources: 4% stamp + 1.5% transfer + 0.5% registration).
  function totalCost({ price, brokeragePct = 0, stampPct = 4, transferPct = 1.5, regPct = 0.5 }) {
    const stamp = price * stampPct / 100, transfer = price * transferPct / 100, reg = price * regPct / 100, brokerage = price * brokeragePct / 100;
    return { price, stamp, transfer, reg, brokerage, govt: stamp + transfer + reg, total: price + stamp + transfer + reg + brokerage };
  }
  async function addTerrain(r) { // elevation lookup is a network call, so it fills in after the instant report
    r.terrain = await elevationProfile(r.lat, r.lon);
    analyse(r); return r;
  }

  // ---------- claim plausibility (rain-related perils only) ----------
  function claimCheck(r, rain, peril) {
    const out = { peril, checks: [], verdict: null, level: null };
    const lvl = imd(rain.max);
    const sus = r.outside ? null : r.setu.pct, dep = r.outside ? 0 : depthAt(r.wid, Math.min(300, Math.max(0, rain.max)));
    out.checks.push({ k: 'Rain around the date', v: `${rain.onDay.toFixed(1)} mm on the day · peak ${rain.max.toFixed(1)} mm (±1 day) → ${lvl}`, ok: rain.max >= 15.6 });
    out.checks.push({ k: 'Location susceptibility', v: sus == null ? 'not modelled outside the 145 GHMC wards' : `${Math.round(sus * 100)}th percentile of 145 wards`, ok: sus != null && sus >= .5 });
    out.checks.push({ k: 'Official inundation list', v: r.gov.inund && r.gov.inund.d <= 1000 ? `${r.gov.inund.name}, ${Math.round(r.gov.inund.d)} m away` : 'no listed inundation area within 1 km', ok: !!(r.gov.inund && r.gov.inund.d <= 1000) });
    out.checks.push({ k: 'Modelled depth at that rain', v: dep >= D.thr ? `${dep.toFixed(2)} m` : 'dry at the grid rainfall (which understates local peaks)', ok: dep >= D.thr });
    let score = 0;
    score += rain.max >= 64.5 ? 3 : rain.max >= 15.6 ? 2 : rain.max >= 2.5 ? 1 : 0;
    score += sus == null ? 1 : sus >= .7 ? 2 : sus >= .4 ? 1 : 0;
    score += dep >= D.thr ? 1 : 0;
    score += (r.gov.inund && r.gov.inund.d <= 1000) ? 1 : 0;
    if (rain.max < 2.5) { out.level = 'red'; out.verdict = 'Not supported by weather evidence — investigate'; }
    else if (score >= 5) { out.level = 'green'; out.verdict = 'Consistent — fast-track candidate'; }
    else if (score >= 3) { out.level = 'amber'; out.verdict = 'Partly supported — manual review'; }
    else { out.level = 'red'; out.verdict = 'Weakly supported — investigate'; }
    out.rain = rain;
    out.caveat = 'Rain data is a ~10–25 km reanalysis grid and understates local peaks (it shows ~80–90 mm for the real Oct-2020 night against a 192 mm reference figure for that storm). Use as an evidence tier, not an exact reading. This is triage, not an accusation.';
    return out;
  }

  // ---------- plain-language narrative (also the offline fallback for the AI box) ----------
  function narrate(r, lens) {
    const L = [];
    const w = r.tiers.water;
    if (r.outside) { L.push(`This address is about ${r.ward.km.toFixed(1)} km outside the 145 GHMC wards the flood model covers, so no flood depth is given. Location score ${r.pillars.score}/100 (${r.pillars.label}) from facilities, lakes, terrain and air quality.`); return L.join(' '); }
    L.push(`${r.ward.name}: water-risk tier ${w.letter} (${w.label}, ${w.score}/100). This ward ranks in the ${Math.round(r.setu.pct * 100)}th percentile for flood susceptibility among 145 wards; the model puts about ${r.setu.depth[192].toFixed(2)} m of water here in a 192 mm storm.`);
    const lb = lakeBand(r.water); if (r.water.lake) L.push(lb.text + ' (indicative, from OpenStreetMap — not the legal lake boundary).');
    if (lens === 'insurer') L.push(`Motor tier ${r.tiers.motor.letter} (${LOADING[r.tiers.motor.letter]} illustrative loading); Property tier ${r.tiers.prop.letter} (${LOADING[r.tiers.prop.letter]}).`);
    else if (lens === 'agent') L.push(`Development score ${r.scores.dev.score}/100 from mapped hospitals, schools, transit and markets nearby.`);
    else L.push(`Overall: ${r.buyer.headline}. ${r.buyer.flags[0].t}.`);
    return L.join(' ');
  }

  return { load, report, HY_LABEL, hmdaText, hmdaLink, pillars, addTerrain, elevationProfile, reanalyse: analyse, airNow, curve, totalCost, market, priceBand, claimCheck, rainOn, forecast, depthAt, imd, narrate, locate, lakeBand, nearest, poisWithin, hav, inBounds, tier, LOADING, FAC, get D() { return D; }, get data() { return D; } };
})();
