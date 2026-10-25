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
    const names = ['zones', 'model', 'reco', 'wardfeat', 'geo', 'hospitals', 'meta', 'rates', 'gov', 'hmda', 'hy', 'gw', 'gwq', 'civic', 'storm', 'heat', 'access', 'land', 'tanks', 'rainstats', 'plan', 'prohib', 'network', 'parcelIdx', 'quality', 'fire', 'seismic', 'tanksyn'];
    const paths = ['data/zones.json', 'data/model.json', 'data/reco.json', 'data/wardfeat.json',
      'data/geo.json', 'data/hospitals.json', 'data/meta.json', 'data/rates.json', 'data/gov.json', 'data/hmda_lakes.json', 'data/hydraa_tanks.json',
      'data/groundwater.json', 'data/gwquality.json', 'data/civic.json', 'data/stormhist.json', 'data/heat.json', 'data/access.json', 'data/land.json', 'data/tanks.json', 'data/rainstats.json', 'data/plan.json', 'data/prohib.json', 'data/network.json', 'data/parcels/index.json', 'data/quality.json', 'data/fire.json', 'data/seismic.json', 'data/tank_syn.json'];
    // the evidence layers added later are optional: if one is missing the report says "unavailable" instead of failing
    const optional = { gw: { meta: {}, stations: [] }, gwq: { meta: {}, samples: [] }, civic: { meta: {} }, storm: { events: [], wards: {} }, heat: null, access: null, land: { meta: {}, gwp: [], gwp_attrs: [], lost: [], forest: [], tx: [], sub: [], endow: [] }, tanks: { meta: {}, tanks: [], streams: [] }, rainstats: { meta: {}, mandals: {} }, plan: null, prohib: null, network: null, parcelIdx: null, quality: null, fire: null, seismic: null, tanksyn: null };
    D.loadFailed = [];
    const res = await Promise.all(paths.map((p, i) => get(p).catch(e => {
      D.loadFailed.push(p);
      if (names[i] in optional) return optional[names[i]];
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
    prepEvidence();
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

  // =====================================================================================================
  // EVIDENCE REPORT — five sections, no combined score. Every finding carries its source, period, spatial resolution, confidence,
  // a kind (observed / official / modelled / estimate / indicative / reference / unavailable) and a next verification step.
  // A finding is 'unknown' (never zero) when the data cannot support an answer. Section ratings follow the WORST scored finding,
  // so a severe flag is never averaged away by good amenities.
  // =====================================================================================================
  const median = a => { const s = a.filter(x => x != null && isFinite(x)).sort((x, y) => x - y); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const bbLL = pts => { let a = 1e9, b = 1e9, c = -1e9, d = -1e9; for (const q of pts) { if (q[0] < a) a = q[0]; if (q[0] > c) c = q[0]; if (q[1] < b) b = q[1]; if (q[1] > d) d = q[1]; } return [a, b, c, d]; };
  function prepEvidence() {
    D.gwSt = (D.gw.stations || []).map(s => ({ lat: s[0], lon: s[1], village: s[2], mandal: s[3], district: s[4], latest: s[5], month: s[6], pre: s[7], post: s[8], rec: s[9], trend: s[10], months: s[11], y0: s[12], y1: s[13] }));
    D.gwqS = (D.gwq.samples || []).map(s => ({ lat: s[0], lon: s[1], village: s[2], mandal: s[3], year: s[4], season: s[5], tds: s[6], f: s[7], no3: s[8], ph: s[9], cl: s[10], aq: s[11] }));
    D.gwqMaxYear = D.gwqS.reduce((m, s) => Math.max(m, s.year), 0);
    const C = D.civic || {};
    const ringHa = ring => { let a = 0; const k = Math.cos(rad(ring[0][0])); for (let i = 0; i < ring.length; i++) { const p = ring[i], q = ring[(i + 1) % ring.length]; a += (p[1] * k * 111320) * (q[0] * 110540) - (q[1] * k * 111320) * (p[0] * 110540); } return Math.abs(a / 2) / 1e4; };
    D.landfill = (C.landfill || []).map(l => ({ name: l.name, rings: l.rings, _b: l.rings.map(bbLL), ha: l.rings.reduce((s, r) => s + ringHa(r), 0) }));
    const Ld = D.land || {}; D.landL = { gwp: (Ld.gwp || []).map(u => ({ ...u, _b: u.r.map(bbLL) })), lost: (Ld.lost || []).map(u => ({ ...u, _b: u.r.map(bbLL) })), forest: (Ld.forest || []).map(u => ({ ...u, _b: u.r.map(bbLL) })),
      tx: (Ld.tx || []).map(u => ({ ...u, _b: u.p.map(bbLL) })), sub: Ld.sub || [], endow: Ld.endow || [] };
    const TK = D.tanks || {}; D.tankL = { tanks: (TK.tanks || []).map(t => ({ ...t, _b: bbLL(t.r[0]) })), streams: (TK.streams || []).map(t => ({ ...t, _b: t.p.map(bbLL) })) };
    const polysBB = ps => (ps || []).map(p => ({ ...p, _b: bbLL(p.o) }));
    D.planL = D.plan && D.plan.zones ? { zones: D.plan.zones.map(z => ({ z: z.z, polys: polysBB(z.polys) })), mandals: D.plan.mandals.map(m => ({ ...m, polys: polysBB(m.polys) })) } : null;
    D.prohibL = D.prohib && D.prohib.p ? D.prohib.p.map(p => ({ cat: p[0], sy: p[1], part: p[2], extent: p[3], village: p[4], mandal: p[5], rings: p[6], _b: bbLL(p[6][0]) })) : null;
    D.networkL = D.network && D.network.meta ? { meta: D.network.meta, sup: new Map(D.network.supply.map(c => [c[0], [c[1], c[2]]])), sew: new Map(D.network.sewer.map(c => [c[0], [c[1], c[2]]])), sections: D.network.sections.map(x => ({ ...x, _b: x.rings.map(bbLL) })) } : null;
    D.fireL = D.fire && D.fire.stations ? D.fire.stations.map(s => ({ lat: s[0], lon: s[1], name: s[2], district: s[3], status: s[4], remark: s[5], id: s[6] })) : null;
    D.seismicL = D.seismic && D.seismic.zones ? D.seismic.zones.map(z => ({ ...z, _b: z.rings.map(bbLL) })) : null;
    D.tankPar = D.tanksyn && D.tanksyn.par ? new Map(Object.entries(D.tanksyn.par).map(([id, ps]) => [Number(id), ps.map(p => ({ ...p, _b: p.rings.map(bbLL) }))])) : null;
    const grid = g => g && g.meta ? g : null;
    D.access = grid(D.access);
    if (D.heat && D.heat.lst) {
      const v = D.heat.lst.filter(x => x != null).sort((a, b) => a - b); D.heatSorted = v;
      D.ndviSorted = D.heat.ndvi.filter(x => x != null).sort((a, b) => a - b);
    }
  }
  const pctOf = (sorted, v) => { if (!sorted || !sorted.length) return null; let lo = 0, hi = sorted.length; while (lo < hi) { const m = (lo + hi) >> 1; if (sorted[m] <= v) lo = m + 1; else hi = m; } return lo / sorted.length; };

  function gwFacts(lat, lon) {
    const all = D.gwSt.map(s => ({ s, d: hav(lat, lon, s.lat, s.lon) })).sort((a, b) => a.d - b.d);
    if (!all.length) return null;
    const near3 = all.filter(x => x.d <= 3000).slice(0, 8), nearest = all[0];
    const vals = near3.map(x => x.s.latest).filter(x => x != null);
    const conf = nearest.d > 6000 ? 'unavailable' : (near3.length >= 3 && nearest.d <= 1500) ? 'medium' : 'low';   // never 'high': wells 1.5 km apart differ by metres
    return { nearest, n2: all.filter(x => x.d <= 2000).length, n3: near3.length, n5: all.filter(x => x.d <= 5000).length, conf,
      latest: near3.length >= 3 ? median(vals) : null, pre: near3.length >= 3 ? median(near3.map(x => x.s.pre)) : null, rec: near3.length >= 3 ? median(near3.map(x => x.s.rec)) : null,
      trend: median(near3.map(x => x.s.trend)), nTrend: near3.filter(x => x.s.trend != null).length,
      spread: vals.length >= 2 ? Math.max(...vals) - Math.min(...vals) : null, wide: vals.length >= 2 && (Math.max(...vals) - Math.min(...vals)) > 20, near3 };
  }
  function gwqFacts(lat, lon) {
    const recent = D.gwqS.filter(s => s.year >= D.gwqMaxYear - 1).map(s => ({ s, d: hav(lat, lon, s.lat, s.lon) })).sort((a, b) => a.d - b.d);
    if (!recent.length) return null;
    let use = recent.filter(x => x.d <= 3000), radius = 3000;
    if (use.length < 4) { use = recent.filter(x => x.d <= 5000); radius = 5000; }
    const par = (k, lim) => { const v = use.map(x => x.s[k]).filter(x => x != null); return { n: v.length, med: median(v), over: v.length ? v.filter(x => x > lim).length / v.length : null }; };
    const aqs = {}; for (const x of use) if (x.s.aq) aqs[x.s.aq] = (aqs[x.s.aq] || 0) + 1;
    const aq = Object.entries(aqs).sort((a, b) => b[1] - a[1])[0];
    return { n: use.length, radius, nearestD: recent[0].d, f: par('f', 1.5), f1: par('f', 1.0), no3: par('no3', 45), tds: par('tds', 2000), tds500: par('tds', 500), aquifer: aq ? aq[0] : null,
      conf: use.length >= 6 ? 'medium' : use.length >= 2 ? 'low' : 'unavailable', years: D.gwqMaxYear - 1 + '–' + D.gwqMaxYear };
  }
  function civicFacts(lat, lon) {
    const C = D.civic || {}, out = {};
    let lf = null;
    for (const l of D.landfill) l.rings.forEach((ring, i) => { if (!near(l._b[i], lat, lon, .06)) return; const ins = pipLL(lat, lon, ring), d = ins ? 0 : distToPathLL(lat, lon, ring); if (!lf || d < lf.d) lf = { d, name: l.name, inside: ins, ha: l.ha }; });
    out.landfill = lf;
    let pe = 0, pm = []; for (const c of (C.power || [])) if (hav(lat, lon, c[0], c[1]) <= 1500) { pe += c[2]; if (c[3] != null) pm.push(c[3]); }
    out.power = { events: pe, medMin: median(pm), cells: (C.power || []).length };
    const nn = (list, k = 1) => list.map(p => ({ p, d: hav(lat, lon, p[0], p[1]) })).sort((a, b) => a.d - b.d).slice(0, k);
    out.choke = nn(C.choke || [], 3); out.choke1k = (C.choke || []).filter(p => hav(lat, lon, p[0], p[1]) <= 1000).length;
    out.junction = nn(C.junctions || [], 1)[0] || null; out.rehab = nn(C.rehab || [], 3); out.rehab2k = (C.rehab || []).filter(p => hav(lat, lon, p[0], p[1]) <= 2000).length;
    out.lakewq = nn(C.lakewq || [], 1)[0] || null; out.stp = nn(C.stp || [], 1)[0] || null; out.noise = nn(C.noise || [], 1)[0] || null;
    return out;
  }
  const GWF = ['geom', 'landform', 'rock', 'depth_to_water', 'wells_observed', 'recharge', 'aquifer', 'well_type', 'well_depth', 'yield', 'success', 'water_quality', 'recharge_structures', 'remarks'];
  function landFacts(lat, lon) {
    const L = D.landL, out = { gwp: null, lost: null, forest: null, tx: null, sub: null, endow: [] };
    const polyHit = (list, pad) => { let best = null; for (const u of list) u.r.forEach((ring, i) => { if (!near(u._b[i], lat, lon, pad)) return; const ins = pipLL(lat, lon, ring), d = ins ? 0 : distToPathLL(lat, lon, ring); if (!best || d < best.d) best = { d, inside: ins, u }; }); return best; };
    const g = polyHit(L.gwp, 0.0005);
    if (g && g.inside) { const a = (D.land.gwp_attrs || [])[g.u.i] || []; out.gwp = Object.fromEntries(GWF.map((k, j) => [k, a[j]])); }
    const lo = polyHit(L.lost, 0.004); if (lo && lo.d <= 400) out.lost = { d: lo.d, inside: lo.inside, ha: lo.u.a[1], type: lo.u.a[0] };
    const fo = polyHit(L.forest, 0.004); if (fo && fo.d <= 600) out.forest = { d: fo.d, inside: fo.inside, name: fo.u.a[1] || fo.u.a[2], type: fo.u.a[0] };
    for (const t of L.tx) t.p.forEach((path, i) => { if (!near(t._b[i], lat, lon, 0.006)) return; const d = distToPathLL(lat, lon, path); if (!out.tx || d < out.tx.d) out.tx = { d, name: t.a[0], kv: t.a[3] }; });
    for (const q of L.sub) { const d = hav(lat, lon, q.ll[0], q.ll[1]); if (d <= 3000 && (!out.sub || d < out.sub.d)) out.sub = { d, name: q.a[0], volt: q.a[1] }; }
    for (const q of L.endow) { const d = hav(lat, lon, q.ll[0], q.ll[1]); if (d <= 400) out.endow.push({ d, village: q.a[0], mandal: q.a[1] }); }
    out.endow.sort((a, b) => a.d - b.d);
    return out;
  }
  const gridIdx = (g, lat, lon) => { const i = Math.floor((lon - g.bbox[0]) / g.cell), j = Math.floor((g.bbox[3] - lat) / g.cell); return i < 0 || j < 0 || i >= g.nx || j >= g.ny ? -1 : j * g.nx + i; };
  function heatFacts(lat, lon) {
    const h = D.heat; if (!h || !h.lst) return null;
    const g = { bbox: h.meta.bbox, cell: h.meta.cell_deg, nx: h.meta.nx, ny: h.meta.ny };
    const idx = gridIdx(g, lat, lon); if (idx < 0) return null;
    let l = h.lst[idx], n = h.ndvi[idx];
    if (l == null) {   // gap in the clear-sky composite: use the median of the 8 neighbours, flagged as filled
      const nb = [-1, 0, 1].flatMap(dj => [-1, 0, 1].map(di => idx + dj * g.nx + di)).filter(k => k >= 0 && k < h.lst.length && k !== idx);
      l = median(nb.map(k => h.lst[k])); n = median(nb.map(k => h.ndvi[k])); if (l == null) return null; return { lst: l / 10, ndvi: n == null ? null : n / 100, pct: pctOf(D.heatSorted, l), npct: n == null ? null : pctOf(D.ndviSorted, n), filled: true };
    }
    return { lst: l / 10, ndvi: n == null ? null : n / 100, pct: pctOf(D.heatSorted, l), npct: n == null ? null : pctOf(D.ndviSorted, n), filled: false };
  }
  function accessFacts(lat, lon) {
    const a = D.access; if (!a) return null;
    const idx = gridIdx({ bbox: a.meta.bbox, cell: a.meta.cell_deg, nx: a.meta.nx, ny: a.meta.ny }, lat, lon); if (idx < 0) return null;
    const out = {};
    for (const [k, c] of Object.entries(a.cats)) { const d = c.d[idx], t = c.t[idx]; out[k] = d == null ? null : { road_m: d, min: t == null ? null : t / 10 }; }
    return out;
  }

  // Live road routing: one OSRM "table" request returns drive time and distance from the pin to the nearest few facilities of each kind.
  // OSRM runs on OpenStreetMap roads including residential streets, with typical car speeds and no live traffic. Public demo server: fine for a demo only.
  const ROUTE_HOSTS = ['https://router.project-osrm.org', 'https://routing.openstreetmap.de/routed-car'];   // same engine and data, two public hosts: a failover, not an independent check
  const routeCache = new Map();
  async function roadAccess(lat, lon) {
    const ck = lat.toFixed(4) + ',' + lon.toFixed(4); if (routeCache.has(ck)) return routeCache.get(ck);
    const cats = ['hospital', 'metro', 'bus', 'school', 'market'], cand = [];
    for (const k of cats) for (const n of nearest(k, lat, lon, 3)) cand.push({ k, ...n });
    if (!cand.length) return null;
    const coords = [[lon, lat], ...cand.map(c => [c.lon, c.lat])].map(c => c[0].toFixed(5) + ',' + c[1].toFixed(5)).join(';');
    const q = `/table/v1/driving/${coords}?sources=0&destinations=${cand.map((_, i) => i + 1).join(';')}&annotations=duration,distance`;
    for (const host of ROUTE_HOSTS) {
      const c = new AbortController(), t = setTimeout(() => c.abort(), 9000);
      try {
        const res = await fetch(host + q, { signal: c.signal }); clearTimeout(t);
        if (!res.ok) continue;
        const j = await res.json(); if (j.code !== 'Ok' || !j.durations) continue;
        const out = {};
        cand.forEach((cd, i) => {
          const dur = j.durations[0][i], dist = j.distances && j.distances[0][i];
          if (dur == null || dist == null) return;
          if (!out[cd.k] || dur < out[cd.k].min * 60) out[cd.k] = { road_m: Math.round(dist), min: dur / 60, name: cd.name, straight: cd.d, src: 'osrm', host: host.split('/')[2] };
        });
        if (Object.keys(out).length) { routeCache.set(ck, out); return out; }
      } catch (e) { clearTimeout(t); }
    }
    return null;   // both hosts failed: the report says "routing unavailable" instead of inventing a number
  }

  // Heavy-rain counts: from the rainfall months we hold (event months, NOT a full year). The mandal key is the upper-cased mandal name used in the rainfall table.
  function rainFacts(wid) {
    const sh = D.storm.wards && D.storm.wards[String(wid)]; if (!sh) return null;
    const m = D.rainstats.mandals && D.rainstats.mandals[sh.m.toUpperCase()]; if (!m) return null;
    return { mandal: sh.m, ...m, meta: D.rainstats.meta };
  }
  // Storm analogs: only for storms with a specific documented date AND a complete rainfall month. Sept 2016 is known to the month only and June 2025 has a partial rainfall month, so both are left out.
  const ANALOG_EVENTS = ['2020-10-13', '2021-07-14', '2023-07-27', '2025-07-18', '2025-09-18', '2026-06-09'], ANALOG_MM = 60;
  function analogFacts(wid) {
    const sh = D.storm.wards && D.storm.wards[String(wid)]; if (!sh) return null;
    const ev = D.storm.events, rows = ANALOG_EVENTS.map(id => { const i = ev.findIndex(e => e.id === id); return i < 0 ? null : { id, label: ev[i].label, mm: sh.r[i], named: !!sh.n[i] }; }).filter(x => x && x.mm != null);
    const hit = rows.filter(x => x.mm >= ANALOG_MM);
    return { mm: ANALOG_MM, n: hit.length, k: hit.filter(x => x.named).length, hit, rows };
  }
  // Tank capacity: summed over de-duplicated TGRAC water-body records within 2 km. Capacity exists only where the source has a bund height, and is the source's own area x bund / 2 estimate.
  function tankFacts(lat, lon) {
    const TKS = D.tankL && D.tankL.tanks; if (!TKS || !TKS.length) return null;
    const list = [];
    for (const t of TKS) { if (!near(t._b, lat, lon, .021)) continue; const ins = pipLL(lat, lon, t.r[0]), d = ins ? 0 : distToPathLL(lat, lon, t.r[0]); if (d <= 2000) list.push({ t, d, inside: ins }); }
    list.sort((a, b) => a.d - b.d);
    const within = r => list.filter(x => x.d <= r), withCap = list.filter(x => x.t.a[3] != null);
    const enc = (arr, i) => arr.filter(x => x.t.a[i] === 'P' || x.t.a[i] === 'T').length;
    return { n2: list.length, n1: within(1000).length, nCap: withCap.length, nNoCap: list.length - withCap.length, capM3: withCap.reduce((a, x) => a + x.t.a[3], 0),
      enc2023: enc(list, 5), enc2011: enc(list, 4), nearest: list[0] || null, list };
  }
  const ST_LABEL = { L: 'live', P: 'partially encroached', T: 'totally encroached', D: 'dead (no storage)' };
  // Natural streams: terrain-derived stream-order network. Proximity only; it does not prove a buried channel or plot-level flood risk.
  function streamFacts(lat, lon) {
    const S = D.tankL && D.tankL.streams; if (!S || !S.length) return null;
    let best = null, n300 = 0;
    for (const st of S) st.p.forEach((path, i) => { if (!near(st._b[i], lat, lon, .006)) return; const d = distToPathLL(lat, lon, path); if (d <= 300) n300++; if (!best || d < best.d) best = { d, o: st.o, name: st.n }; });
    return { nearest: best && best.d <= 500 ? best : null, n300 };
  }

  // =====================================================================================================
  // BATCH 4 — property identity, planning authority, parcel overlaps, mapped water network, evidence-quality registry.
  // Honesty rules: a map pin is never called a parcel; a mapped overlap is never called a legal restriction; a mapped pipe is never called a connection;
  // "no data" is never "safe"; a failed or missing source is "unavailable", never zero.
  // =====================================================================================================
  const normTxt = s => String(s == null ? '' : s).toLowerCase().replace(/[^a-z0-9]/g, '');
  const normNum = s => String(s == null ? '' : s).toLowerCase().replace(/\s+/g, '').split('/').map(p => p.replace(/^0+(?=\d)/, '')).join('/');   // "091 / 01" -> "91/1"
  const baseNum = s => normNum(s).split('/')[0];
  function editSim(a, b) {   // 1 = same after dropping case and punctuation; spelling variants of a village name score high
    a = normTxt(a); b = normTxt(b); if (!a || !b) return 0; if (a === b) return 1;
    let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
    for (let i = 1; i <= a.length; i++) { const cur = [i]; for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); prev = cur; }
    return 1 - prev[b.length] / Math.max(a.length, b.length);
  }
  const evenOdd = (lat, lon, rings) => { let c = 0; for (const r of rings) if (pipLL(lat, lon, r)) c++; return c % 2 === 1; };   // handles holes and multi-part outlines
  const distToRings = (lat, lon, rings) => Math.min(...rings.map(r => distToPathLL(lat, lon, r)));
  const areaM2 = rings => { let s = 0; for (const r of rings) { const k = Math.cos(rad(r[0][0])); for (let i = 0; i < r.length - 1; i++) s += (r[i][1] * k * 111320) * (r[i + 1][0] * 110540) - (r[i + 1][1] * k * 111320) * (r[i][0] * 110540); } return Math.abs(s / 2); };
  const inPoly = (p, lat, lon) => pipLL(lat, lon, p.o) && !p.h.some(h => pipLL(lat, lon, h));

  // ---------- which official plan governs the area ----------
  const ZONE_ORDER = ['MCH', 'CDA', 'HADA', 'HUDA', 'HMR_ORR_GROWTH', 'HMR'];   // the layer's own zone names; precedence only matters if polygons overlap
  const PLAN_INFO = {
    MCH: { label: 'old city core (MCH)', area: 'the erstwhile Municipal Corporation of Hyderabad area (HMDA core area)', plan: 'Revised Development Plan of the erstwhile Municipal Corporation of Hyderabad area', how: 'published by HMDA as seven circle-wise PDFs plus a zoning-regulations PDF', page: 'revised_development_plan' },
    HUDA: { label: 'HUDA', area: 'the HUDA area', plan: 'HUDA area master plan', how: 'listed on HMDA\'s Master Plan page', page: 'master_plan' },
    CDA: { label: 'CDA', area: 'the CDA area', plan: 'CDA master plan', how: 'listed on HMDA\'s Master Plan page', page: 'master_plan' },
    HADA: { label: 'HADA', area: 'the HADA area', plan: 'HADA master plan', how: 'listed on HMDA\'s Master Plan page', page: 'master_plan' },
    HMR: { label: 'wider HMDA region', area: 'the wider HMDA region', plan: 'HMDA Master Plan 2031', how: 'published by HMDA as one image sheet per mandal', page: 'master_plan_2031', sheet: true },
    HMR_ORR_GROWTH: { label: 'ORR growth corridor', area: 'the HMDA growth corridor along the Outer Ring Road', plan: 'HMDA Master Plan 2031', how: 'published by HMDA as one image sheet per mandal', page: 'master_plan_2031', sheet: true }
  };
  function planFacts(lat, lon) {
    const P = D.planL; if (!P || !P.zones.length) return null;
    const hits = ZONE_ORDER.filter(zn => { const z = P.zones.find(x => x.z === zn); return z && z.polys.some(p => near(p._b, lat, lon, 0) && inPoly(p, lat, lon)); });
    const zone = hits[0] || null;
    let mandal = null; for (const m of P.mandals) if (m.polys.some(p => near(p._b, lat, lon, 0) && inPoly(p, lat, lon))) { mandal = m; break; }
    const info = zone ? PLAN_INFO[zone] : null, M = D.plan.meta || {};
    const links = [];
    if (info) links.push({ label: info.plan + ' (HMDA)', url: (M.pages || {})[info.page] });
    if (info && info.sheet && mandal && mandal.sheet) links.push({ label: `Master Plan 2031 sheet: ${mandal.sheet.replace(/_/g, ' ')} (large image)`, url: (M.sheet_base || '') + encodeURIComponent(mandal.sheet) + '.jpg' });
    if (zone === 'MCH' && (M.pages || {}).zoning_regulations) links.push({ label: 'Zoning regulations and master-plan G.O.s (PDF)', url: M.pages.zoning_regulations });
    return { zone, hits, info, mandal, links: links.filter(l => l.url), overlap: hits.length > 1 };
  }

  // ---------- survey parcels: load, match, overlap ----------
  const PARCEL_TOL = 25, PARCEL_COVER = 250, PARCEL_NEIGH = 300;   // metres. TOL is an assumption about map-vs-pin offset, not a published accuracy.
  const PARCEL_LABEL = { verified: 'Verified match', approximate: 'Approximate match', none: 'No match', unavailable: 'Source unavailable' };
  const parcelTiles = new Map();
  async function loadTile(key) {
    if (parcelTiles.has(key)) return parcelTiles.get(key);
    try {
      const j = await fetch('data/parcels/' + key + '.json').then(r => { if (!r.ok) throw new Error(key); return r.json(); });
      const t = j.p.map(row => ({ n: row[0], v: j.v[row[1]], m: j.m[row[2]], code: row[3], rem: row[4], rings: row[5], _b: bbLL(row[5][0]) }));
      parcelTiles.set(key, t); return t;
    } catch (e) { return null; }   // a failed tile is never cached and never read as "no parcels"
  }
  async function parcelLoad(lat, lon) {
    const M = D.parcelIdx; if (!M || !M.tiles) return { ok: false, reason: 'no-index', parcels: [] };
    const b = M.bbox, padD = 400 / 110540;
    const maxLon = b[0] + M.nx * M.step, maxLat = b[1] + M.ny * M.step;   // the tile grid is rounded up, so it reaches a little past the study box
    if (lat < b[1] - padD || lat > maxLat + padD || lon < b[0] - padD || lon > maxLon + padD) return { ok: true, outsideBox: true, parcels: [] };
    const padLon = padD / Math.cos(rad(lat)), keys = new Set();
    for (const la of [lat - padD, lat + padD]) for (const lo of [lon - padLon, lon + padLon]) keys.add(Math.floor((lo - b[0]) / M.step) + '_' + Math.floor((la - b[1]) / M.step));
    const have = [...keys].filter(x => M.tiles[x]);   // a tile missing from the index holds no real parcels
    const got = await Promise.all(have.map(loadTile));
    if (got.some(x => x === null)) return { ok: false, reason: 'tile-failed', parcels: [] };
    const seen = new Set(), parcels = [];
    for (const t of got) for (const p of t) { const id = p.v + '|' + p.n + '|' + p.rings[0][0][0] + ',' + p.rings[0][0][1]; if (!seen.has(id)) { seen.add(id); parcels.push(p); } }
    return { ok: true, outsideBox: false, parcels, tiles: have.length };
  }
  function parcelMatch(lat, lon, data, ref) {
    ref = ref || {};
    const want = normNum(ref.survey), hasWant = !!want, vill = String(ref.village || '').trim();
    const out = { status: 'unavailable', reason: '', text: '', parcel: null, candidates: [], ambiguous: false, usable: false, tolerance: PARCEL_TOL, wanted: hasWant ? String(ref.survey).trim() : '', neighbour: null };
    const finish = (status, reason, text) => { out.status = status; out.reason = reason; out.text = text; return out; };
    if (!data || !data.ok) return finish('unavailable', (data && data.reason) || 'not-loaded', 'The parcel layer could not be loaded, so the pin was not matched to a surveyed parcel.');
    if (data.outsideBox) return finish('unavailable', 'outside-area', 'This location is outside the area the parcel data covers.');
    const P = data.parcels, padC = PARCEL_COVER / 110540;
    const mk = p => ({ number: p.n, village: p.v, mandal: p.m, remark: p.rem || '', flagged: p.code === 1, feature: p.code === 2, areaM2: Math.round(areaM2(p.rings)), rings: p.rings });
    const around = P.filter(p => near(p._b, lat, lon, padC));
    const dOf = p => evenOdd(lat, lon, p.rings) ? 0 : distToRings(lat, lon, p.rings);
    if (!around.length || Math.min(...around.map(dOf)) > PARCEL_COVER) return finish('unavailable', 'no-parcels-mapped', 'No surveyed parcels are mapped around this pin. In much of the old city the state layer holds only one placeholder polygon without survey numbers.');
    const inside = around.filter(p => dOf(p) === 0);
    let cands = inside.filter(p => p.code !== 2).map(p => ({ p, d: 0 }));
    if (!cands.length) {
      const feat = inside.find(p => p.code === 2);
      if (feat) { out.parcel = mk(feat); return finish('none', 'on-feature', `The pin falls on a mapped ${feat.rem || 'road, canal, stream or tank'} feature, not on a survey plot.`); }
      cands = around.filter(p => p.code !== 2).map(p => ({ p, d: distToRings(lat, lon, p.rings) })).filter(x => x.d <= PARCEL_TOL).sort((a, b) => a.d - b.d);
      if (!cands.length) return finish('none', 'unmapped', 'The pin falls in a gap between mapped survey parcels (a road, open land or an unmapped area).');
    }
    const rel = n => !hasWant ? null : normNum(n) === want ? 'exact' : (baseNum(n) === baseNum(want) && (normNum(n).includes('/') !== want.includes('/'))) ? 'base' : 'none';
    const info = cands.slice(0, 5).map(x => ({ ...mk(x.p), d: Math.round(x.d), inside: x.d === 0, numMatch: rel(x.p.n), villageOK: vill ? editSim(vill, x.p.v) >= .8 : null }));
    out.candidates = info; const single = cands.length === 1, c0 = info[0];
    const ident = c => `survey no. ${c.number} (${c.village}${c.mandal ? ', ' + c.mandal : ''})`;
    const setParcel = c => { out.parcel = c; out.usable = !!c && c.inside && !c.flagged && !c.feature; };
    const LAYOUT = ' A survey number can hold many house plots, so this does not identify the individual plot or flat.';
    if (!hasWant) {
      out.ambiguous = !single; if (single) setParcel(c0);
      if (single && c0.inside) return finish('approximate', c0.flagged ? 'pin-only-flagged' : 'pin-only', `The pin falls inside the mapped outline of ${ident(c0)}. You have not entered a survey number, so this is only the map's reading; confirm it against your sale deed.` + (c0.flagged ? ' The source flags this number as duplicate or unreadable.' : '') + LAYOUT);
      if (single) return finish('approximate', 'near-edge', `The pin is about ${c0.d} m outside the mapped outline of ${ident(c0)}, within the ${PARCEL_TOL} m allowance for map and pin error. Confirm the survey number against your sale deed.` + LAYOUT);
      return finish('approximate', inside.length > 1 ? 'overlap-ambiguous' : 'near-edge-ambiguous', `The pin could belong to ${cands.length} neighbouring or overlapping parcels (${info.map(c => c.number).join(', ')}). Enter your survey number to narrow it down.`);
    }
    const ex = info.filter(c => c.numMatch === 'exact'), bs = info.filter(c => c.numMatch === 'base');
    if (ex.length) {
      const c = ex[0]; out.ambiguous = !single; setParcel(c);
      if (c.villageOK === false) return finish('none', 'village-mismatch', `The pin is on survey no. ${c.number}, but in village ${c.village}, not ${vill}. Check the village on your documents.`);
      if (single && c.inside && !c.flagged) return finish('verified', vill ? 'number-and-village' : 'number', `The pin is inside the mapped outline of ${ident(c)} and the survey number matches the one you entered. This matches the pin to a drawn outline in the state GIS. It does not confirm title, where the boundary lies on the ground, or which plot you are buying.` + LAYOUT);
      if (c.flagged) return finish('approximate', 'number-flagged', `The pin is on ${ident(c)}, but the source flags this number as duplicate or unreadable, so the match cannot be called verified.`);
      if (!c.inside) return finish('approximate', 'near-edge', `Survey no. ${c.number} is about ${c.d} m from the pin, within the ${PARCEL_TOL} m allowance, but the pin is not inside its outline.`);
      return finish('approximate', 'overlap-ambiguous', `Survey no. ${c.number} contains the pin, but ${cands.length - 1} other mapped outline(s) overlap the same spot, so the match is not exact.`);
    }
    if (bs.length) { const c = bs[0]; setParcel(c); out.ambiguous = !single; return finish('approximate', 'sub-survey', `You entered survey no. ${out.wanted}; the pin is on ${ident(c)}, a sub-division or parent number of it. Ask which sub-division your deed refers to.`); }
    // the entered number is not at the pin: is it a neighbour?
    const nb = P.filter(p => p.code !== 2 && normNum(p.n) === want && (!vill || editSim(vill, p.v) >= .8) && near(p._b, lat, lon, PARCEL_NEIGH / 110540)).map(p => ({ p, d: dOf(p) })).filter(x => x.d <= PARCEL_NEIGH).sort((a, b) => a.d - b.d);
    if (single) setParcel(c0); out.ambiguous = !single;
    if (nb.length) { out.neighbour = { number: nb[0].p.n, village: nb[0].p.v, d: Math.round(nb[0].d) }; return finish('none', 'neighbour', `Survey no. ${out.wanted} is mapped about ${out.neighbour.d} m from the pin, but the pin falls on ${single ? ident(c0) : 'other parcels'}. Move the pin or check which parcel your deed describes.`); }
    return finish('none', 'number-mismatch', `The pin falls on ${single ? ident(c0) : 'other parcels'}, not on survey no. ${out.wanted}, and no parcel with that number is mapped within ${PARCEL_NEIGH} m.`);
  }
  function setParcel(r, data, ref) { r.parcel = { data, ref: ref || {}, match: parcelMatch(r.lat, r.lon, data, ref) }; r.ev = evidence(r); return r; }
  async function attachParcel(r, ref) { return setParcel(r, await parcelLoad(r.lat, r.lon), ref); }

  // overlap of the matched parcel outline with other mapped footprints. Sampled on a 20 x 20 grid inside the parcel so that outlines that merely touch (a few metres of map error) do not count.
  function overlapFrac(rings, other) {   // `other` is a list of rings (even-odd, so holes work)
    const bb = ringsBB(rings), ob = ringsBB(other); if (bb[0] > ob[2] || bb[2] < ob[0] || bb[1] > ob[3] || bb[3] < ob[1]) return { n: 0, frac: 0 };
    let n = 0, h = 0; const G = 20;
    for (let i = 0; i < G; i++) for (let j = 0; j < G; j++) {
      const la = bb[0] + (i + .5) * (bb[2] - bb[0]) / G, lo = bb[1] + (j + .5) * (bb[3] - bb[1]) / G;
      if (!evenOdd(la, lo, rings)) continue; n++; if (evenOdd(la, lo, other)) h++;
    }
    return { n, frac: n ? h / n : 0 };
  }
  const ringsBB = rings => bbLL(rings.flat());
  const OVERLAP_MIN = 0.03;   // at least 3% of the sampled outline must sit inside the other footprint
  function overlapFacts(rings) {
    const out = { lost: null, forest: null, tanks: [], layers: 3 };
    for (const u of D.landL.lost) { const f = overlapFrac(rings, u.r); if (f.frac >= OVERLAP_MIN && (!out.lost || f.frac > out.lost.frac)) out.lost = { frac: f.frac, type: u.a[0], ha: u.a[1] }; }
    for (const u of D.landL.forest) { const f = overlapFrac(rings, u.r); if (f.frac >= OVERLAP_MIN && (!out.forest || f.frac > out.forest.frac)) out.forest = { frac: f.frac, name: u.a[1] || u.a[2], type: u.a[0] }; }
    for (const t of (D.tankL && D.tankL.tanks) || []) { const f = overlapFrac(rings, t.r); if (f.frac >= OVERLAP_MIN) out.tanks.push({ frac: f.frac, name: t.a[0], status: t.a[5], status2011: t.a[4] }); }
    out.tanks.sort((a, b) => b.frac - a.frac);
    return out;
  }
  // the prohibitory-category layer: tested at the pin, and by survey number once a parcel is matched. Free-text category is quoted as recorded. NEVER the legal register.
  function prohibFacts(lat, lon, parcel) {
    const Pl = D.prohibL; if (!Pl || !Pl.length) return null;
    let hit = null;
    for (const p of Pl) { if (!near(p._b, lat, lon, 0)) continue; if (evenOdd(lat, lon, p.rings)) { hit = { ...p, how: 'pin' }; break; } }
    if (!hit && parcel) { const pv = normTxt(parcel.village), pn = normNum(parcel.number); const q = Pl.find(p => normTxt(p.village) === pv && normNum(p.sy) === pn); if (q) hit = { ...q, how: 'survey-number' }; }
    return hit;
  }

  // ---------- HMWSSB mapped network (coarse cells) ----------
  function netFacts(lat, lon) {
    const N = D.networkL; if (!N) return null;
    const m = N.meta, i = Math.floor((lon - m.bbox[0]) / m.cell_deg), j = Math.floor((lat - m.bbox[1]) / m.cell_deg);
    if (i < 0 || j < 0 || i >= m.nx || j >= m.ny) return { inside: false };
    const scan = (map, R) => {   // rings of cells outwards from the pin's cell
      let first = null, cells = 0, len = { 0: 0, 1: 0, 3: 0 }, dia = { 0: 0, 1: 0, 3: 0 };
      for (let dj = -R; dj <= R; dj++) for (let di = -R; di <= R; di++) {
        const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= m.nx || jj >= m.ny) continue;
        const v = map.get(jj * m.nx + ii); if (!v) continue; const ring = Math.max(Math.abs(di), Math.abs(dj));
        cells++; if (first == null || ring < first) first = ring;
        for (const k of [0, 1, 3]) if (ring <= k) { len[k] += v[0]; dia[k] = Math.max(dia[k], v[1]); }
      }
      return { ring: first, cells, len, dia };
    };
    const sup = scan(N.sup, 3), sew = scan(N.sew, 10);
    let section = null; for (const s of N.sections) if (s.rings.some((rg, k) => near(s._b[k], lat, lon, 0) && pipLL(lat, lon, rg))) { section = { name: s.n, division: s.d, code: s.c }; break; }
    return { inside: true, sup, sew, section, cellM: Math.round(m.cell_deg * 110540) };
  }

  // ---------- state fire-station list and state seismic layer (Step 1) ----------
  // Fire: the source's own words (Existing / Proposed, plus a remark such as "Moved") are kept. A Proposed station is never counted as present, and nothing here says a station is operating.
  function fireFacts(lat, lon) {
    const F = D.fireL; if (!F || !F.length) return null;
    const all = F.map(s => ({ s, d: hav(lat, lon, s.lat, s.lon) })).sort((a, b) => a.d - b.d);
    const ex = all.filter(x => x.s.status === 'Existing'), pr = all.filter(x => x.s.status === 'Proposed');
    return { nearest: ex[0] || null, n5: ex.filter(x => x.d <= 5000).length, proposed3: pr.filter(x => x.d <= 3000), nExisting: ex.length, nProposed: pr.length, nMoved: ex.filter(x => /moved/i.test(x.s.remark)).length, nInaccurate: ex.filter(x => /not found accurate/i.test(x.s.remark)).length, nCorrect: ex.filter(x => /^correct$/i.test(x.s.remark)).length };
  }
  // Seismic: the zone polygon the point is in, and how far the nearest boundary with a DIFFERENT zone is (zone maps are coarse).
  function seismicFacts(lat, lon) {
    const Z = D.seismicL; if (!Z || !Z.length) return null;
    const hit = Z.find(z => evenOdd(lat, lon, z.rings)); if (!hit) return { zone: null };
    let other = null;
    for (const z of Z) { if (z.zone === hit.zone) continue; z.rings.forEach((rg, i) => { if (!near(z._b[i], lat, lon, .06)) return; const d = distToPathLL(lat, lon, rg); if (!other || d < other.d) other = { zone: z.zone, d }; }); }
    return { zone: hit.zone, intensity: hit.intensity, other };
  }

  // ---------- tank survey number near the pin (Step 2) ----------
  // The state water-body layer records some tanks' own survey number ('Base_Syno'). This finds the nearest such tank and the parcel carrying that number next to its outline.
  // A parcel with the tank's number is a survey-record fact. It is NOT the legal Full Tank Level and says nothing about encroachment.
  function tankSurveyFacts(lat, lon) {
    if (!D.tankPar || !D.hy || !D.hy.tanks.length) return null;
    let best = null;
    for (const t of D.hy.tanks) t.rings.forEach((r, i) => {
      if (!near(t._b[i], lat, lon, .01)) return;
      const inside = pipLL(lat, lon, r), d = inside ? 0 : distToPathLL(lat, lon, r);
      if (d <= 600 && (!best || d < best.d || (d === best.d && t.syn && !best.t.syn))) best = { d, inside, t };
    });
    if (!best) return { tank: null };
    const t = best.t, out = { tank: { name: t.name, village: t.village, mandal: t.mandal, syn: t.syn, s23: t.s23, d: best.d, inside: best.inside }, searched: false, parcels: [], pinIn: null, nearest: null };
    if (!t.syn) return out;
    const ps = D.tankPar.get(t.id);
    if (!ps) return out;                                   // the parcel search for this tank did not complete: say so, never "none found"
    out.searched = true; out.parcels = ps;
    out.pinIn = ps.find(p => evenOdd(lat, lon, p.rings)) || null;
    for (const p of ps) p.rings.forEach(rg => { const d = distToPathLL(lat, lon, rg); if (!out.nearest || d < out.nearest.d) out.nearest = { d, p }; });
    return out;
  }

  // ---------- pasted Google Maps links ----------
  // Returns {lat, lon} when the link carries coordinates; {text} when it carries an address or place name (to be looked up); {short, url} for a short link; null when it is not a Google Maps link.
  function parseMapsLink(q) {
    q = String(q || '').trim();
    if (!/(google\.[a-z.]+\/maps|maps\.google|goo\.gl|maps\.app|g\.co\/kgs)/i.test(q)) return null;
    const num = (re) => { const m = q.match(re); return m ? { lat: +m[1], lon: +m[2] } : null; };
    const ll = num(/!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/) || num(/[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)/i) || num(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
    const dec0 = s => { try { return decodeURIComponent(s.replace(/\+/g, ' ')).replace(/\s+/g, ' ').trim(); } catch (e) { return s.replace(/\+/g, ' ').trim(); } };
    if (ll) { const pn = q.match(/\/maps\/place\/([^/@?#]+)/i); if (pn && dec0(pn[1]).length >= 3 && !/^-?\d/.test(dec0(pn[1]))) ll.name = dec0(pn[1]); return ll; }
    const dec = s => { try { return decodeURIComponent(s.replace(/\+/g, ' ')).replace(/\s+/g, ' ').trim(); } catch (e) { return s.replace(/\+/g, ' ').trim(); } };
    const tq = q.match(/[?&](?:query|q|destination)=([^&#]+)/i);
    if (tq && dec(tq[1]).length >= 3) return { text: dec(tq[1]) };
    const pl = q.match(/\/maps\/place\/([^/@?#]+)/i);
    if (pl && dec(pl[1]).length >= 3) return { text: dec(pl[1]) };
    if (/(goo\.gl|maps\.app|g\.co\/kgs)/i.test(q)) return { short: true, url: (q.match(/https?:\/\/\S+/) || [q])[0] };
    return { short: true, url: '' };
  }

  // ---------- evidence-quality registry helpers ----------
  const Q = () => (D.quality && D.quality.sources) ? D.quality : null;
  const monthsBetween = (ym, asOf) => { const [y, mo] = String(ym).split('-').map(Number); return (asOf.getUTCFullYear() - y) * 12 + (asOf.getUTCMonth() + 1 - (mo || 12)); };
  function freshness(src, asOf) {   // live | current | aging | stale | undated | historical | reference | documents | model
    asOf = asOf || new Date();
    if (src.nature === 'live') return 'live';
    if (src.nature === 'reference') return 'reference';
    if (src.nature === 'documents') return 'documents';
    if (!src.obs) return 'undated';
    if (src.nature === 'history') return src.stale_months != null && monthsBetween(src.obs[1], asOf) > src.stale_months ? 'stale' : 'historical';   // a record that stops long ago cannot describe today
    if (src.nature === 'model') return 'model';
    const age = monthsBetween(src.obs[1], asOf), lim = src.stale_months;
    if (lim == null) return 'current';
    return age <= lim / 2 ? 'current' : age <= lim ? 'aging' : 'stale';
  }
  function qualityTable(asOf) {
    const q = Q(); if (!q) return null; asOf = asOf || new Date();
    const sources = Object.entries(q.sources).map(([id, s]) => ({ id, ...s, freshness: freshness(s, asOf), used_by: Object.entries(q.factors).filter(([, f]) => f.sources.includes(id)).map(([fid]) => fid) }));
    const factors = Object.entries(q.factors).map(([id, f]) => {
      const ss = f.sources.map(s => q.sources[s]).filter(Boolean), fr = f.sources.map(s => freshness(q.sources[s], asOf));
      const flags = [];
      if (fr.some(x => x === 'stale')) flags.push('stale'); if (fr.some(x => x === 'undated')) flags.push('undated'); if (ss.some(s => s.validation === 'unvalidated')) flags.push('unvalidated');
      if (ss.some(s => s.validation === 'negative')) flags.push('failed-validation'); if (ss.some(s => s.licence === 'restricted')) flags.push('restricted-licence'); if (ss.some(s => s.licence === 'verify')) flags.push('licence-unverified');
      if (f.scope === 'none') flags.push('no-data'); if (['ward', 'mandal', 'locality', 'region'].includes(f.scope)) flags.push('coarse-scope');
      return { id, ...f, freshness: fr, flags };
    });
    return { asOf: asOf.toISOString().slice(0, 10), sources, factors };
  }
  function removalImpact(srcId) {   // which findings lose evidence if this source goes away: a finding resting only on it becomes unknown, the others lose a supporting source
    const q = Q(); if (!q || !q.sources[srcId]) return null;
    const used = Object.entries(q.factors).filter(([, f]) => f.sources.includes(srcId));
    return { source: srcId, becomeUnknown: used.filter(([, f]) => f.sources.length === 1).map(([id]) => id), degrade: used.filter(([, f]) => f.sources.length > 1).map(([id]) => id) };
  }

  const SECTIONS = [
    ['hazards', 'Hazards', 'What can go wrong here: flood, heat and other natural or civic hazards.'],
    ['water', 'Water security', 'Whether water is likely to be there, and what it contains: groundwater depth, trend and quality.'],
    ['infra', 'Infrastructure', 'Roads, travel time by road, power, traffic and waste around the address.'],
    ['live', 'Liveability', 'Everyday facilities within reach, from mapped open data.'],
    ['land', 'Land & planning', 'What a map pin cannot tell you: plot identity, zoning, restrictions and price evidence.']
  ];
  const HIGH = new Set(['sus', 'depth', 'storms', 'lake', 'nala', 'inund', 'hy', 'hmda', 'ftl', 'gwdepth', 'gwpre', 'gwtrend', 'gwf', 'gwno3', 'gwtds', 'acc_hospital', 'landfill', 'lost', 'forest', 'gwp', 'overlap']);
  const KIND_LABEL = { observed: 'Observed', official: 'Official record', modelled: 'Model', estimate: 'Estimate from nearby data', indicative: 'Open-map indicator', reference: 'Reference', unavailable: 'Not available' };
  function evidence(r) {
    const F = { hazards: [], water: [], infra: [], live: [], land: [] };
    const add = (sec, o) => F[sec].push(Object.assign({ level: 'info', kind: 'indicative', conf: 'medium', value: '', note: '', next: '', source: '', period: '', res: '', sec }, o));
    const km = x => x == null ? 'n/a' : x < 950 ? Math.round(x / 10) * 10 + ' m' : (x / 1000).toFixed(1) + ' km';
    const wardRes = r.outside ? 'n/a' : `ward (${r.setu.area.toFixed(1)} km²)`;
    const lvlHi = (v, w, c) => v >= c ? 'concern' : v >= w ? 'watch' : 'good';
    const miss = f => (D.loadFailed || []).includes('data/' + f);   // a data file that failed to load: its findings say so instead of reading as "nothing found"
    const notRun = (sec, id, label, srcName) => add(sec, { id, label, value: 'data not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: srcName, period: '—', res: '—', note: `The ${srcName} data could not be loaded, so this check was not run. That is not a clean result.`, next: 'Reload the page; if it persists, this demo is missing that data file.' });
    // ---------- HAZARDS ----------
    if (r.outside) add('hazards', { id: 'sus', label: 'Flood susceptibility (SETHU model)', value: 'Not modelled here', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'SETHU ward model', note: `This address is ${r.ward.km.toFixed(1)} km outside the 145 GHMC wards the model covers.`, next: 'Ask locally about waterlogging; use the lake, terrain and rainfall evidence below.' });
    else {
      const p = r.setu.pct;
      add('hazards', { id: 'sus', label: 'Flood susceptibility (SETHU model)', value: `${Math.round(p * 100)}th percentile of 145 wards`, level: lvlHi(p, .55, .8), kind: 'modelled', conf: 'medium', source: 'SETHU ward model, trained on 8 documented floods', period: 'floods 2016–2026', res: wardRes,
        note: `Higher floods earlier. Tested on floods it never saw: AUC about 0.69 on held-out events (0.5 = chance). It ranks wards, it does not see street-level drains.`, next: 'Ask neighbours or the resident association which streets waterlogged in 2020 and 2025.' });
      const dep = r.setu.depth[192];
      add('hazards', { id: 'depth', label: 'Modelled water depth in a 192 mm storm', value: dep >= D.thr ? `about ${dep.toFixed(2)} m of water in this ward, in a storm the size of October 2020 (modelled, rough)` : 'stays dry in the model, even in a storm the size of October 2020', level: dep >= .5 ? 'concern' : dep >= D.thr ? 'watch' : 'good', kind: 'modelled', conf: 'low', source: 'SETHU rain-to-depth curve (anchored to three documented reference points)', period: 'scenario', res: wardRes,
        note: 'The rain-to-depth step is an assumption, not a learned result. Treat as an order of magnitude.', next: 'Check the street-level flood history rather than relying on the depth number.' });
      const sh = D.storm.wards && D.storm.wards[String(r.wid)];
      if (sh) {
        const ev = D.storm.events, named = sh.n.reduce((a, b) => a + b, 0), top = sh.r.map((mm, i) => ({ mm, i })).filter(x => x.mm != null).sort((a, b) => b.mm - a.mm)[0];
        add('hazards', { id: 'storms', label: 'What this ward\'s mandal recorded in 8 documented floods', value: top ? `${top.mm} mm in ${ev[top.i].label} (${sh.m} mandal) · named in news for flooding in ${named} of 8` : 'no readings', level: named >= 3 ? 'concern' : named >= 1 ? 'watch' : 'good', kind: 'observed', conf: 'medium',
          source: 'Open Data Telangana (TSDPS) mandal rainfall + news-named wards', period: 'Sep 2016 – Jun 2026', res: 'mandal (rain) · ward (naming)',
          note: ev.map((e, i) => `${e.label}: ${sh.r[i] == null ? 'n/a' : sh.r[i] + ' mm'}${sh.n[i] ? ' · named' : ''}`).join('  |  ') + '. "Named" means a news report named this ward; absence does not prove it stayed dry. Sept 2016 is dated only to the month and June 2025 has an incomplete rainfall month, so their rainfall is approximate. Rain is the mandal gauge value, not rain at the plot.', next: 'Ask which of these storms put water on your street. Research-layer data (rainfall source is non-commercial).' });
      }
      const rf = rainFacts(r.wid);
      if (rf) { const ys = rf.years, perY = rf.per_year.map(x => `${x[0]}: ${x[1]}`).join(', '), exY = rf.excluded_years.map(x => x[0]).join(', ');
        add('hazards', { id: 'heavyrain', label: 'Heavy-rain days per monsoon in this mandal', value: `${rf.mean_over.toFixed(1)} days a year above ${rf.meta.threshold_mm} mm on average (range ${rf.min_over}–${rf.max_over}) over ${ys.length} complete monsoons, ${ys[0]}–${ys[ys.length - 1]} · wettest day ${rf.wettest[0]} mm on ${rf.wettest[1]}`, level: 'info', kind: 'observed', conf: ys.length >= 6 ? 'medium' : 'low',
          source: 'Open Data Telangana (TSDPS) mandal daily weather files', period: `June–October, ${ys.length} complete seasons (${ys.join(', ')})`, res: `mandal (${rf.mandal}), not the plot`,
          note: `A heavy-rain day is above ${rf.meta.threshold_mm} mm (IMD heavy-rain threshold; rain-day 08:30 to 08:30 IST). Heavy days per year: ${perY}.${exY ? ` ${exY} was left out because the file has under 90% of its days.` : ''} Seven or so seasons are far too few to give a return period, and mandal rainfall is not rain at the plot. The big 2025 storms are not in these counts.`, next: 'Ask residents how the street behaves after a downpour, not only after the very biggest storms.' }); }
      else add('hazards', { id: 'heavyrain', label: 'Heavy-rain days per monsoon in this mandal', value: 'no complete monsoon record matched to this ward', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Open Data Telangana (TSDPS)', note: 'The ward could not be matched to a mandal with at least one complete June–October season.', next: '' });
      const an = analogFacts(r.wid);
      if (an) add('hazards', { id: 'analog', label: 'Storm analogs (preliminary historical association)', value: an.n < 3 ? `only ${an.n} documented storm${an.n === 1 ? '' : 's'} with at least ${an.mm} mm in this mandal — too few to say anything` : `${an.k} of ${an.n} documented storms with at least ${an.mm} mm in this mandal had this ward named in news`, level: 'info', kind: 'observed', conf: 'low',
        source: 'TSDPS mandal rainfall + news-sourced ward labels', period: 'storms Oct 2020 – Jun 2026', res: 'mandal (rain) vs ward (naming)',
        note: an.rows.map(x => `${x.label}: ${x.mm} mm${x.named ? ' · named' : ''}${x.mm < an.mm ? ' (below threshold)' : ''}`).join('  |  ') + '. A news mention is not a flood measurement, mandal rain is not rain at this plot, and a handful of storms cannot establish a pattern. This is an association, not a forecast.', next: 'Use it only to ask better questions of neighbours; do not read it as a probability.' });
    }
    const t = r.terrain;
    if (t) add('hazards', { id: 'pocket', label: 'Low pocket vs surroundings', value: `${t.relief >= 0 ? '+' : ''}${t.relief.toFixed(1)} m vs the 600 m ring`, level: t.relief <= -4 ? 'watch' : 'good', kind: 'estimate', conf: 'medium', source: 'Open-Meteo elevation (Copernicus DEM, 90 m)', period: 'static terrain', res: '~90 m', note: pocketNote(t), next: 'Look at where water would run on the actual street.' });
    else add('hazards', { id: 'pocket', label: 'Low pocket vs surroundings', value: 'Elevation lookup pending', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Open-Meteo elevation', note: 'The live elevation service has not answered yet.', next: '' });
    const lb = lakeBand(r.water);
    add('hazards', { id: 'lake', label: 'Lake / tank proximity', value: lb.text, level: ['inside', 'very close'].includes(lb.band) ? 'concern' : lb.band === 'near' ? 'watch' : 'good', kind: 'indicative', conf: 'medium', source: 'OpenStreetMap water polygons + official TGRAC tank outlines', period: 'undated', res: 'polygon',
      note: 'This is the visible water outline, not the legal Full Tank Level or buffer.', next: 'Get the FTL / buffer status confirmed in writing from HMDA or HYDRAA.' });
    if (r.gov.nala) add('hazards', { id: 'nala', label: 'Mapped nala nearby', value: `${r.gov.nala.name} · ${km(r.gov.nala.d)}`, level: r.gov.nala.d <= 60 ? 'concern' : r.gov.nala.d <= 150 ? 'watch' : 'good', kind: 'official', conf: 'medium', source: 'TGRAC / GHMC nala layer (96 named nalas)', period: 'undated', res: 'line (positional accuracy not published)',
      note: 'Only 96 named nalas are in this layer, so a missing nala here does not mean none exists.', next: 'Check the plot against the nala buffer and any widening proposal.' });
    else if (miss('gov.json')) notRun('hazards', 'nala', 'Mapped nala nearby', 'TGRAC / GHMC nala layer');
    else add('hazards', { id: 'nala', label: 'Mapped nala nearby', value: 'none within 1.5 km in the GHMC layer', level: 'good', kind: 'official', conf: 'low', source: 'TGRAC / GHMC nala layer (96 named nalas)', period: 'undated', res: 'line', note: 'The layer is incomplete (96 nalas); underground and culverted drains are not in it.', next: 'Ask GHMC / neighbours about drains on this street.' });
    if (r.gov.nala && r.gov.nala.d <= 500) add('hazards', { id: 'nalaenc', label: 'Recorded encroachment on this nala', value: 'blank in the source', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'TGRAC nala layer fields Govt_Encr / Pvt_Encr / Court_Case', period: '—', res: '—',
      note: 'Our audit found these fields are 0 for every one of the 96 nalas and 1,162 segments, which means "not filled in", not "no encroachment".', next: 'Ask GHMC for the nala encroachment survey for this segment.' });
    const sf = streamFacts(r.lat, r.lon);
    if (!sf) add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: 'stream layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'TGRAC stream order', note: '', next: '' });
    else if (sf.nearest) add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: `${sf.nearest.name || 'unnamed stream'} (stream order ${sf.nearest.o ?? '?'}) · ${km(sf.nearest.d)} · ${sf.n300} segment${sf.n300 === 1 ? '' : 's'} within 300 m`, level: sf.nearest.d <= 50 && (sf.nearest.o || 0) >= 3 ? 'watch' : 'info', kind: 'estimate', conf: 'low',
      source: 'Telangana State GIS stream-order layer (terrain-derived network)', period: 'undated', res: 'line, positional accuracy not published',
      note: 'Stream order only says where the terrain model puts a natural channel. It does not prove that a channel (open or buried) crosses the plot, or that the plot floods. Higher order means a larger catchment.', next: 'Look at the old village or revenue map for a stream on the survey number, and check where water runs on the street.' });
    else add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: 'no mapped stream within 500 m', level: 'info', kind: 'estimate', conf: 'low', source: 'Telangana State GIS stream-order layer', period: 'undated', res: 'line', note: 'The network is terrain-derived: small or buried channels may not appear, so this is not a clearance.', next: '' });
    if (miss('gov.json')) notRun('hazards', 'inund', 'Officially listed inundation area', 'GHMC water-logging list');
    else add('hazards', { id: 'inund', label: 'Officially listed inundation area', value: r.gov.inund ? `${r.gov.inund.name} · ${km(r.gov.inund.d)}` : 'none within 3 km on the list', level: r.gov.inund && r.gov.inund.d <= 250 ? 'concern' : r.gov.inund && r.gov.inund.d <= 500 ? 'watch' : 'good', kind: 'official', conf: 'medium', source: 'GHMC major water-logging places (23 points)', period: 'undated', res: 'point',
      note: 'Only 23 points. Our audit found 7 of them have no mapped drain within 600 m, so the list shows where water collected, not necessarily where a drain is missing.', next: 'Treat absence from this short list as unknown, not safe.' });
    const hy = r.hy;
    if (hy && hy.d <= 3000) {
      const bad = hy.s23 !== 'L' && hy.s23 !== '?';
      add('hazards', { id: 'hy', label: 'Nearest tank: 2014 vs 2023 satellite status', value: `${hy.display || 'unnamed tank'} · ${hy.inside ? 'under this pin' : km(hy.d)} · ${HY_LABEL[hy.s23]}`, level: bad && hy.d <= 250 ? ((hy.inside || hy.d <= 60) && (hy.s23 === 'TB' || hy.s23 === 'PB') ? 'concern' : 'watch') : 'good', kind: 'official', conf: 'medium', source: 'TGRAC / HYDRAA water-body assessment', period: '2014 vs 2023 imagery', res: 'polygon',
        note: `2014 status: ${HY_LABEL[hy.s14]}. ${hy.enc500 ? hy.enc500 + ' encroached tank(s) within 500 m. ' : ''}A satellite classification, not a legal order.`, next: 'Verify FTL and buffer with HMDA / HYDRAA before paying anything.' });
    }
    const hm = r.hmda;
    if (hm) add('hazards', { id: 'hmda', label: 'HMDA lake notification', value: hm.final ? `final notification ${hm.final}` : hm.prelim ? `preliminary only (${hm.prelim})` : 'no dates shown', level: hm.final ? 'good' : 'watch', kind: 'official', conf: 'low', source: 'HMDA lakes portal (name-matched)', period: 'portal list, fetched Oct 2026', res: 'lake',
      note: hmdaText(hm) + '. Matched by name only, so double-check it is the same lake.', next: 'Open the FTL PDF from the HMDA portal and compare with the layout.' });
    const heat = heatFacts(r.lat, r.lon);
    if (heat) {
      add('hazards', { id: 'heat', label: 'Surface heat in the dry season', value: `${heat.lst.toFixed(0)} °C land-surface · hotter than ${Math.round(heat.pct * 100)}% of the city`, level: heat.pct >= .95 ? 'concern' : heat.pct >= .8 ? 'watch' : 'good', kind: 'observed', conf: 'low', source: 'Landsat 8/9 thermal band (USGS), median of clear scenes', period: `Mar–May 2024–26, ${D.heat.meta.scenes} scenes`, res: '150 m grid (30 m source)',
        note: 'Surface temperature of roofs, roads and soil, not the air temperature a resident feels. Not yet validated: across 27 mandals its ranking did not agree with weather-station air temperatures (rank correlation about 0, 15 scene dates). Stations differ by only about 2 °C and measure a different quantity, so that test neither confirms nor refutes it. Treat it as a hint about hotter and cooler spots.' + (heat.filled ? ' This cell was filled from its neighbours.' : ''), next: 'Check shade, roof type and green cover on site.' });
      if (heat.ndvi != null) add('hazards', { id: 'green', label: 'Vegetation cover (dry-season greenness)', value: `NDVI ${heat.ndvi.toFixed(2)} · greener than ${Math.round(heat.npct * 100)}% of the city`, level: (r.water.lake && r.water.lake.inside) ? 'info' : heat.npct < .15 ? 'watch' : 'good', kind: 'observed', conf: heat.filled ? 'low' : 'medium', source: 'Landsat 8/9 red and near-infrared bands', period: `Mar–May 2024–26`, res: '150 m grid',
        note: (r.water.lake && r.water.lake.inside) ? 'This pin is on open water, so low greenness is expected and is not rated.' : 'In the dry season this mostly picks up trees and irrigated parks.', next: 'Compare with the parks list under Liveability.' });
    } else add('hazards', { id: 'heat', label: 'Surface heat in the dry season', value: 'not computed for this location', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Landsat 8/9', note: 'The heat layer is missing or does not cover this point.', next: '' });
    const szG = seismicFacts(r.lat, r.lon), szConflict = szG && szG.zone && szG.zone !== 'Zone II';
    add('hazards', { id: 'seismic', label: 'Earthquake zone', value: szConflict ? `Zone II is the usual reference for Hyderabad city, but the state GIS layer puts this spot in ${szG.zone}: the two sources disagree here (see the next finding)` : 'Zone II (low hazard) under IS 1893 (Part 1):2016, per secondary sources — reference only', level: 'info', kind: 'reference', conf: 'low', source: 'BIS IS 1893 (Part 1):2016 seismic zone map as listed by secondary sources; not checked against the standard itself', period: 'standard of 2016; a newer edition may exist', res: 'regional',
      note: 'A regional hazard class, not a prediction, and a newer edition of the code may change the zones. It says nothing about how a particular building was built.', next: 'Confirm the zone in the current BIS standard, and ask for the structural certificate and building-permission documents.' });
    if (miss('seismic.json')) notRun('hazards', 'seismic_gis', 'Earthquake zone (state GIS layer)', 'state seismic-zone layer');
    else if (!szG || !szG.zone) add('hazards', { id: 'seismic_gis', label: 'Earthquake zone (state GIS layer)', value: 'outside the zones mapped in the state layer', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) seismic-zone layer', period: '—', res: '—', note: 'No zone could be read for this location.', next: 'Check the seismic zone for the exact location in IS 1893.' });
    else {
      const nearB = szG.other && szG.other.d <= 2000;
      add('hazards', { id: 'seismic_gis', label: 'Earthquake zone (state GIS layer)', value: `${szG.zone} · ${szG.intensity || 'intensity not stated'}${szG.other && szG.other.d <= 5000 ? ` · ${(szG.other.d / 1000).toFixed(1)} km from the ${szG.other.zone} boundary` : ''}`, level: 'info', kind: 'official', conf: nearB ? 'low' : 'medium',
        source: 'Telangana State GIS (TCUR) seismic-zone layer, 3 polygons', period: 'undated (service document created 2025-05-24); the edition of the zoning behind it is not published', res: 'regional zone polygon (~50 m simplification)',
        note: 'A regional hazard zone. It says nothing about whether a particular building is structurally safe: that depends on how and when it was built and needs an engineer. ' + (nearB ? `This spot is close to the ${szG.other.zone} boundary and zone maps are coarse, so treat the zone as approximate. ` : '') + 'It agrees with the Zone II reference for the whole city except where noted above; neither source is the BIS standard itself.', next: 'Ask for the building\'s structural design certificate and, for an older building, a structural audit by a licensed engineer.' });
    }
    const cv = civicFacts(r.lat, r.lon);
    add('hazards', { id: 'shelter', label: 'Flood rehabilitation centres nearby', value: cv.rehab[0] ? `${cv.rehab2k} within 2 km · nearest ${km(cv.rehab[0].d)} (${cv.rehab[0].p[2] || 'centre'})` : 'none listed nearby', level: cv.rehab[0] && cv.rehab[0].d <= 1500 ? 'good' : 'info', kind: 'official', conf: 'medium', source: 'GHMC vulnerable-localities list (101 centres)', period: 'undated', res: 'point', note: 'Centres were identified for specific vulnerable localities, so many areas simply are not on the list.', next: 'Ask the ward office which centre serves this street.' });
    // ---------- WATER SECURITY ----------
    const gw = gwFacts(r.lat, r.lon);
    const gwSrc = 'Telangana Ground Water Department monthly piezometer readings (Open Data Telangana)';
    if (!gw || gw.conf === 'unavailable') add('water', { id: 'gw', label: 'Groundwater depth', value: 'no monitoring well within 6 km', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: gwSrc, note: '', next: 'Ask local borewell operators for depths and yields.' });
    else {
      const n = gw.nearest;
      add('water', { id: 'gwnear', label: 'Nearest monitoring well (observed)', value: `${n.s.village}${n.s.mandal ? ', ' + n.s.mandal : ''} · ${km(n.d)} · ${n.s.latest.toFixed(1)} m below ground in ${n.s.month}`, level: 'info', kind: 'observed', conf: n.d <= 1500 ? 'medium' : 'low', source: gwSrc, period: `monthly, ${n.s.y0}–${n.s.y1} (${n.s.months} readings)`, res: 'single well',
        note: 'A reading from one well. It is not your plot\'s borewell.', next: 'Compare with the depth borewells are drilled to in the area.' });
      if (gw.latest == null) add('water', { id: 'gwdepth', label: 'Groundwater depth around here', value: `only ${gw.n3} monitoring well${gw.n3 === 1 ? '' : 's'} within 3 km — too few for an area estimate`, level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: gwSrc, note: 'We need at least three wells within 3 km before quoting a neighbourhood value.', next: 'Use the nearest-well reading above only as a rough hint, and ask local borewell operators.' });
      else if (gw.wide) add('water', { id: 'gwdepth', label: 'Groundwater depth around here', value: `wells nearby disagree widely: ${Math.min(...gw.near3.map(x => x.s.latest)).toFixed(0)}–${Math.max(...gw.near3.map(x => x.s.latest)).toFixed(0)} m below ground (${gw.n3} wells)`, level: 'info', kind: 'observed', conf: 'low', source: gwSrc, period: 'latest month in the data', res: 'wells within 3 km', note: 'Hard-rock aquifers vary a lot over short distances. We do not rate this location because the nearby wells do not agree.', next: 'Ask owners nearby how deep their borewells go and how often they run dry.' });
      else add('water', { id: 'gwdepth', label: 'Groundwater depth around here (median of nearby wells)', value: `${gw.latest.toFixed(1)} m below ground (${gw.n3} wells within 3 km, range ${gw.spread != null ? gw.spread.toFixed(0) : '?'} m)`, level: gw.latest > 20 ? 'concern' : gw.latest > 8 ? 'watch' : 'good', kind: 'estimate', conf: gw.conf, source: gwSrc, period: 'latest month in the data', res: `median of up to 8 wells within 3 km`,
        note: 'Rule of thumb used here: under 8 m good, 8–20 m watch, over 20 m concern. Wells within 1.5 km of each other differ by about 5 m at the median, so this is a neighbourhood indicator, not a plot value.', next: 'Ask owners nearby how deep their borewells go and how often they run dry.' });
      if (gw.pre != null && !gw.wide) add('water', { id: 'gwpre', label: 'Depth at the end of the dry season (Apr–May)', value: `${gw.pre.toFixed(1)} m below ground`, level: gw.pre > 25 ? 'concern' : gw.pre > 12 ? 'watch' : 'good', kind: 'estimate', conf: gw.conf, source: gwSrc, period: 'Apr–May mean 2021–2026', res: 'median of nearby wells', note: 'The deepest the water table usually gets before the rains.', next: 'Ask about summer tanker dependence.' });
      if (gw.rec != null && !gw.wide) add('water', { id: 'gwrec', label: 'Rebound after the monsoon', value: `${gw.rec >= 0 ? '+' : ''}${gw.rec.toFixed(1)} m (pre minus post, Oct–Nov)`, level: gw.rec > 15 ? 'info' : gw.rec < 1 ? 'watch' : 'good', kind: 'estimate', conf: gw.conf, source: gwSrc, period: '2021–2025 seasons', res: 'median of nearby wells', note: 'How far the water table rises after the rains. A small rebound suggests weak recharge.', next: '' });
      add('water', { id: 'gwtrend', label: 'Multi-year trend', value: gw.trend == null ? 'not enough years of data nearby' : `${gw.trend >= 0 ? '+' : ''}${gw.trend.toFixed(2)} m per year (${gw.trend > 0 ? 'water table falling' : 'water table rising'})`, level: gw.trend == null ? 'unknown' : gw.trend >= 1 ? 'concern' : gw.trend >= .5 ? 'watch' : 'good', kind: gw.trend == null ? 'unavailable' : 'estimate', conf: gw.trend == null ? 'unavailable' : gw.nTrend >= 3 ? 'medium' : 'low', source: gwSrc, period: 'annual means 2021–2025', res: `${gw.nTrend} well(s) with a trend`,
        note: '2021 and 2022 were very wet years, which exaggerates the apparent fall. Treat as direction, not rate.', next: 'Look for recent bore failures or tanker supply in the area.' });
      add('water', { id: 'gwcov', label: 'How well monitored is this spot?', value: `${gw.n2} wells within 2 km · ${gw.n5} within 5 km · nearest ${km(gw.nearest.d)}`, level: 'info', kind: 'observed', conf: gw.conf, source: gwSrc, period: '2021–2026', res: 'wells', note: 'Positions in the source file are partly unreliable; 589 of 2,119 stations were dropped for placeholder or impossible coordinates.', next: '' });
    }
    const q = gwqFacts(r.lat, r.lon);
    const qSrc = 'Telangana Ground Water Department pre/post-monsoon water-quality samples';
    if (!q || q.conf === 'unavailable') add('water', { id: 'gwq', label: 'Groundwater quality', value: 'no recent samples within 5 km', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: qSrc, note: '', next: 'Test the actual borewell water at a lab.' });
    else {
      const pc = o => o.over == null ? 'n/a' : Math.round(o.over * 100) + '%';
      add('water', { id: 'gwf', label: 'Fluoride in nearby groundwater', value: q.f.med == null ? 'n/a' : `median ${q.f.med.toFixed(2)} mg/L · ${pc(q.f)} of ${q.f.n} samples above 1.5`, level: q.f.med == null ? 'unknown' : (q.f.med > 1.5 || (q.f.over || 0) >= .3) ? 'concern' : (q.f.over || 0) > 0 ? 'watch' : 'good', kind: 'observed', conf: q.conf, source: qSrc, period: q.years, res: `${q.n} wells within ${q.radius / 1000} km`, note: 'Indian drinking-water standard (BIS IS 10500): 1.0 mg/L acceptable, 1.5 mg/L permissible. These are other wells\' results, not a test of your water.', next: 'Test the actual water; fluoride can vary well to well.' });
      add('water', { id: 'gwno3', label: 'Nitrate in nearby groundwater', value: q.no3.med == null ? 'n/a' : `median ${q.no3.med.toFixed(0)} mg/L · ${pc(q.no3)} above 45`, level: q.no3.med == null ? 'unknown' : (q.no3.med > 45 || (q.no3.over || 0) >= .3) ? 'concern' : (q.no3.over || 0) > 0 ? 'watch' : 'good', kind: 'observed', conf: q.conf, source: qSrc, period: q.years, res: `${q.n} wells within ${q.radius / 1000} km`, note: 'BIS limit 45 mg/L.', next: 'Test the actual water.' });
      add('water', { id: 'gwtds', label: 'Salinity (TDS) in nearby groundwater', value: q.tds.med == null ? 'n/a' : `median ${Math.round(q.tds.med)} mg/L · ${pc(q.tds500)} of samples above the 500 desirable limit · ${pc(q.tds)} above the 2,000 permissible limit`, level: q.tds.med == null ? 'unknown' : q.tds.med > 2000 ? 'concern' : q.tds.med > 1000 ? 'watch' : 'good', kind: 'observed', conf: q.conf, source: qSrc, period: q.years, res: `${q.n} wells within ${q.radius / 1000} km`, note: 'BIS: 500 mg/L acceptable, 2000 mg/L permissible where no alternative exists. Most Hyderabad hard-rock groundwater is above 500.', next: 'Ask whether residents use RO purifiers.' });
      if (q.aquifer) add('water', { id: 'aq', label: 'Principal aquifer type (nearby sample records)', value: q.aquifer, level: 'info', kind: 'official', conf: 'low', source: qSrc, period: '2024–25 files', res: 'nearby wells', note: 'Geology context only. Hard-rock aquifers hold less water than alluvial ones.', next: '' });
    }
    if (cv.lakewq) add('water', { id: 'lakewq', label: 'Nearest lake / river water-quality station', value: `${cv.lakewq.p[2]} · ${km(cv.lakewq.d)} · class ${cv.lakewq.p[3] || '?'}, DO ${cv.lakewq.p[4] ?? '?'} mg/L, BOD ${cv.lakewq.p[5] ?? '?'} mg/L`, level: cv.lakewq.d > 3000 ? 'info' : ((cv.lakewq.p[4] != null && cv.lakewq.p[4] < 4) || (cv.lakewq.p[5] != null && cv.lakewq.p[5] > 6)) ? 'watch' : 'good', kind: 'observed', conf: 'low', source: 'TSPCB monitoring (via Lakeer open-GIS)', period: 'annual average 2017 — dated', res: 'station', note: 'Eight-plus years old. Low oxygen or high BOD means a polluted water body (smell, mosquitoes).', next: 'Visit the lake in summer and judge by eye and nose.' });
    if (cv.stp && cv.stp.d <= 3000) add('water', { id: 'stp', label: 'Sewage treatment plant outlet nearby', value: `${(cv.stp.p[2] || 'STP').slice(0, 50)} · ${km(cv.stp.d)}`, level: cv.stp.d <= 1000 ? 'watch' : 'info', kind: 'official', conf: 'low', source: 'TSPCB (via Lakeer open-GIS)', period: '2017 — dated', res: 'point', note: 'Treated effluent often flows into nearby channels.', next: 'Check where the outlet drains.' });
    const ld = landFacts(r.lat, r.lon);
    if (ld.gwp && (ld.gwp.recharge || ld.gwp.well_depth || ld.gwp.yield)) {
      const rc = (ld.gwp.recharge || '').toUpperCase(), bits = [ld.gwp.well_depth && `suggested well depth ${ld.gwp.well_depth}`, ld.gwp.yield && `typical yield ${ld.gwp.yield}`, ld.gwp.success && `success rate ${String(ld.gwp.success).toLowerCase()}`, ld.gwp.water_quality && String(ld.gwp.water_quality).toLowerCase()].filter(Boolean);
      add('water', { id: 'gwp', label: 'Hydrogeology of the ground here (regional map)', value: `${rc ? rc.toLowerCase() + ' recharge' : 'recharge not stated'} · ${(ld.gwp.landform || 'landform n/a').replace(/\s*\(.*\)/, '')} · ${(ld.gwp.rock || 'rock n/a').replace(/\s*\(\d+\)/, '').toLowerCase()}`,
        level: /NIL/.test(rc) ? 'concern' : /POOR/.test(rc) ? 'watch' : /MODERATE|GOOD/.test(rc) ? 'good' : 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS groundwater-potential (hydro-geomorphological) map', period: 'undated regional survey', res: 'map unit (about 1:50,000)',
        note: (bits.length ? bits.join(' · ') + '. ' : '') + (ld.gwp.remarks ? ld.gwp.remarks + ' ' : '') + 'This describes the type of ground and what wells usually yield in it. It is not a promise for any one plot.', next: 'Ask a borewell contractor who has drilled within a few hundred metres.' });
    } else add('water', { id: 'gwp', label: 'Hydrogeology of the ground here (regional map)', value: ld.gwp ? 'unit has no hydrogeology attributes' : 'no mapped unit under this pin', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS groundwater-potential map', note: 'Built-up and water-body units carry no groundwater attributes in this map.', next: '' });
    const tf = tankFacts(r.lat, r.lon);
    if (!tf) add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: 'tank layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'TGRAC water-body layer', note: '', next: '' });
    else if (!tf.n2) add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: 'no mapped tank within 2 km', level: 'info', kind: 'official', conf: 'low', source: 'TGRAC / HMDA water-body layer (2,048 records, de-duplicated)', period: 'undated, status classes 2011 and 2023', res: 'polygon', note: 'Absence from this layer does not prove there is no tank or pond.', next: '' });
    else add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: `${tf.n2} mapped tank${tf.n2 === 1 ? '' : 's'} within 2 km · estimated design capacity ${(tf.capM3 / 1e6).toFixed(2)} million m³ for the ${tf.nCap} with a bund height (${tf.nNoCap} have no capacity figure)${tf.nearest ? ` · nearest ${tf.nearest.t.a[0] || 'unnamed tank'}, ${tf.nearest.inside ? 'under this pin' : km(tf.nearest.d)}, 2023 status ${ST_LABEL[tf.nearest.t.a[5]] || 'not classified'}` : ''}`, level: 'info', kind: 'official', conf: 'low',
      source: 'TGRAC / HMDA water-body layer (2,048 records after removing overlaps; an identical second layer was ignored)', period: 'topo-sheet and revenue-map extents; status classes 2011 and 2023', res: 'polygon',
      note: `Capacity is the source's own formula (area x bund height / 2), an estimate of the original design capacity, not measured water. Present-day storage is not measured here. By count, ${tf.enc2023} of these ${tf.n2} tanks are classed partially or totally encroached in 2023 (${tf.enc2011} in 2011). Status is a satellite classification, not a legal finding, and capacity is missing for most tanks.`, next: 'Ask the irrigation department or HYDRAA whether the tank nearest your plot still holds water in the monsoon.' });
    // mapped HMWSSB network: where the state GIS MAPS a pipe, in coarse cells. A mapped pipe is not a connection; no mapped pipe is not "no supply".
    const nf = netFacts(r.lat, r.lon), secName = nf && nf.section ? nf.section.name : null;
    add('water', { id: 'supply', label: 'Water connection, supply hours and tanker dependence', value: 'not published per address' + (secName ? ` · HMWSSB operating section: ${secName}` : ''), level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'HMWSSB (no public per-address record found)', period: '—', res: '—',
      note: 'Whether a property has a tap connection, how many hours water comes and whether tankers are needed is not in any public dataset we reached. The operating section only says which HMWSSB office area this is, not that a connection exists.', next: 'Ask for the water and sewerage connection papers and recent bills, and ask neighbours how often water comes and whether they buy tankers.' });
    if (nf && nf.inside) {
      const cm = nf.cellM, sup = nf.sup, sew = nf.sew;
      const NB = { kind: 'official', conf: 'low', period: 'undated (service document created 2025-05-24)', res: `${cm} m cell` };
      if (sup.ring != null) add('water', { id: 'supplynet', label: 'Mapped HMWSSB supply pipe near the pin', value: `a supply pipe is mapped within about ${(sup.ring + 1) * cm} m · ${Math.round(sup.len[3])} m of pipe within about ${4 * cm} m, largest ${sup.dia[3]} mm`, level: 'info', source: 'Telangana State GIS (TCUR) HMWSSB supply-line layer', ...NB,
        note: 'A pipe on the map is not a connection: it does not show that this property is connected, that water flows, or how often. Pipes are shown as coarse cells; the GIS does not say when they were surveyed.', next: 'Ask HMWSSB whether the property has a registered connection (CAN number).' });
      else add('water', { id: 'supplynet', label: 'Mapped HMWSSB supply pipe near the pin', value: `no supply pipe mapped within about ${4 * cm} m`, level: 'unknown', source: 'Telangana State GIS (TCUR) HMWSSB supply-line layer', ...NB, kind: 'unavailable', conf: 'unavailable',
        note: 'Mapping is uneven, so this is neither proof of no supply nor a clean result. Newer colonies and the outer wards are often missing from the map.', next: 'Ask the seller and neighbours how water is supplied.' });
      if (sew.ring != null) add('water', { id: 'sewernet', label: 'Mapped sewer line near the pin', value: `a sewer line is mapped within about ${(sew.ring + 1) * cm} m` + (sew.dia[3] ? ` (largest ${sew.dia[3]} mm within about ${4 * cm} m)` : ''), level: sew.ring > 3 && sew.cells >= 20 ? 'watch' : 'info', source: 'Telangana State GIS (TCUR) core-city sewer-line layer', ...NB,
        note: sew.ring > 3 && sew.cells >= 20 ? 'Sewer lines are mapped within about 1 km but none close by, which may mean no public sewer here. The layer covers the core city only and its survey date is unknown.' : 'A sewer line on the map is not a connection. The layer covers the core city only.', next: 'Ask HMWSSB or the seller whether the property is connected to the public sewer or uses a septic tank.' });
      else add('water', { id: 'sewernet', label: 'Mapped sewer line near the pin', value: 'outside the area where sewer lines are mapped (core city only)', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) core-city sewer-line layer', period: 'undated', res: `${cm} m cell`,
        note: 'The state layer maps sewer lines for the core city only. No line here does not mean there is no sewer.', next: 'Ask whether the property uses the public sewer or a septic tank.' });
    }
    // ---------- INFRASTRUCTURE ----------
    add('infra', { id: 'road', label: 'Distance to a main road', value: r.arterialM == null ? 'none mapped' : km(r.arterialM), level: r.arterialM == null ? 'unknown' : r.arterialM > 2500 ? 'watch' : 'good', kind: 'indicative', conf: 'medium', source: 'OpenStreetMap (motorway/trunk/primary)', period: 'undated', res: 'road sample points', note: 'Straight-line distance to the nearest sampled point on a main road.', next: 'Check the approach road width to the plot.' });
    const ac = r.access || accessFacts(r.lat, r.lon);
    const ACN = { hospital: ['Hospital', 'hospital'], metro: ['Metro / rail station', 'metro'], bus: ['Bus stop', 'bus'], school: ['School', 'school'], market: ['Market / supermarket', 'market'] };
    for (const [k, [lab, fk]] of Object.entries(ACN)) {
      const a = ac && ac[k], sl = r.fac[fk] && r.fac[fk].nearest ? r.fac[fk].nearest.d : null;
      if (!a) { add('infra', { id: 'acc_' + k, label: `${lab}: road travel`, value: ac ? 'no route found' : 'routing lookup pending or unavailable', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'OSRM routing on OpenStreetMap roads', note: ac ? 'No drivable route was returned for this facility.' : 'The live routing service has not answered (it needs a network connection).', next: 'Check the route on any maps app.' }); continue; }
      const lim = k === 'hospital' ? [10, 20] : k === 'metro' ? [20, 40] : [12, 25];
      add('infra', { id: 'acc_' + k, label: `${lab}: road travel`, value: `${a.min != null ? Math.round(a.min) + ' min' : '?'} · ${km(a.road_m)} by road${sl ? ` (${km(sl)} straight line, ×${(a.road_m / Math.max(sl, 50)).toFixed(1)})` : ''}`, level: a.min == null ? 'unknown' : a.min > lim[1] ? 'concern' : a.min > lim[0] ? 'watch' : 'good', kind: 'estimate', conf: a.src === 'osrm' ? 'medium' : 'low', source: a.src === 'osrm' ? `OSRM routing on OpenStreetMap roads (public demo server) to ${a.name || 'the nearest ' + lab.toLowerCase()}` : 'OpenStreetMap main/collector roads, shortest path to the nearest mapped ' + lab.toLowerCase(), period: 'live lookup, road network as of now', res: a.src === 'osrm' ? 'street network' : '~220 m grid',
        note: 'Driving time at typical car speeds with no live traffic, so peak-hour and emergency times will differ. Compared with the straight-line distance it shows how winding the access is.', next: 'Drive it at 9 am and 6 pm once.' });
    }
    if (miss('civic.json')) notRun('infra', 'choke', 'Traffic congestion points within 1 km', 'Hyderabad Traffic Police congestion list');
    else add('infra', { id: 'choke', label: 'Traffic congestion points within 1 km', value: `${cv.choke1k}${cv.choke[0] ? ` · nearest ${cv.choke[0].p[2]} (${km(cv.choke[0].d)})` : ''}`, level: cv.choke1k >= 2 ? 'watch' : 'good', kind: 'official', conf: 'low', source: 'Hyderabad Traffic Police congestion list (89 points)', period: 'undated', res: 'point', note: 'A short list of the worst junctions only.', next: 'Check the commute at peak hours.' });
    if (cv.junction && cv.junction.d <= 1500) add('infra', { id: 'junc', label: 'GHMC junction improvement planned nearby', value: `${cv.junction.p[2]} · ${km(cv.junction.d)}`, level: 'info', kind: 'official', conf: 'low', source: 'GHMC urban junction improvement plan (33 junctions)', period: 'undated', res: 'point', note: 'Planned works can mean construction disruption first and better flow later.', next: 'Ask GHMC for the timeline.' });
    const pw = cv.power;
    add('infra', { id: 'power', label: 'Power breakdown history (dated)', value: `${pw.events} feeder breakdowns within 1.5 km in FY2017–18${pw.medMin != null ? `, median ${Math.round(pw.medMin)} min` : ''}`, level: 'info', kind: 'observed', conf: 'low', source: 'TSSPDCL/TSNPDCL feeder breakdown log', period: '1 Apr 2017 – 31 Mar 2018 only', res: '~550 m cells', note: 'This is eight years old and not scored. It shows which feeders were fragile then; the network has changed since.', next: 'Ask residents about current outages and inverter use.' });
    const lf = cv.landfill;
    if (ld.tx && ld.tx.d <= 600) add('infra', { id: 'tx', label: 'High-voltage transmission line nearby', value: `${ld.tx.name || 'line'}${ld.tx.kv ? ' (' + ld.tx.kv + ' kV)' : ''} · ${km(ld.tx.d)}`, level: ld.tx.d <= 100 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS electric transmission layer (TCUR)', period: 'undated', res: 'line', note: 'Buyers sometimes discount plots under or beside high-voltage lines; the line may also carry a no-build corridor.', next: 'Ask the seller whether the plot is under a transmission corridor.' });
    if (ld.sub && ld.sub.d <= 1000) add('infra', { id: 'sub', label: 'Electricity substation nearby', value: `${ld.sub.name} (${ld.sub.volt}) · ${km(ld.sub.d)}`, level: 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS substations (TCUR)', period: 'undated', res: 'point', note: 'A nearby substation usually means a robust supply, but can mean noise and hum.', next: '' });
    const major = lf && lf.ha >= 20;   // only one listed site is large (the 92 ha Malkaram legacy dump yard); the rest are small garbage transfer points under 5 ha
    if (miss('civic.json')) notRun('infra', 'landfill', 'Landfill / dump yard', 'landfill list');
    else add('infra', { id: 'landfill', label: 'Landfill / dump yard', value: lf ? `${lf.name} (${lf.ha.toFixed(lf.ha < 1 ? 1 : 0)} ha) · ${lf.inside ? 'inside' : km(lf.d)}` : 'none listed nearby', level: lf ? (major ? (lf.d <= 2000 ? 'concern' : lf.d <= 5000 ? 'watch' : 'good') : (lf.d <= 300 ? 'watch' : 'good')) : 'good', kind: 'official', conf: 'medium', source: 'Telangana open-data list of landfills and dump yards (11 sites)', period: 'undated', res: 'polygon',
      note: major ? 'A large dump yard: odour, smoke and leachate can reach a few kilometres.' : 'A small garbage transfer or processing point; the one large dump yard in the list is further away.', next: 'Visit on a hot afternoon with the wind blowing from the site.' });
    const ff = fireFacts(r.lat, r.lon);
    if (miss('fire.json')) notRun('infra', 'fire_gis', 'Fire station on the state list', 'state fire-station list');
    else if (!ff || !ff.nearest || ff.nearest.d > 10000) add('infra', { id: 'fire_gis', label: 'Fire station on the state list', value: 'no station listed as Existing within 10 km', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) fire-station list', period: '—', res: '—',
      note: `The state list holds only ${ff ? ff.nExisting : 'a few'} Existing stations for the whole region, so this does not mean none is near. See the OpenStreetMap-based fire-station finding under Everyday life.`, next: 'Ask the local fire station or the municipality which station covers the address.' });
    else add('infra', { id: 'fire_gis', label: 'Fire station on the state list', value: `${ff.nearest.s.name || 'unnamed'} · ${km(ff.nearest.d)} · listed as Existing (source remark: ${ff.nearest.s.remark || 'none'})${ff.proposed3.length ? ` · ${ff.proposed3.length} more listed as Proposed within 3 km (not operating)` : ''}`,
      level: 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS (TCUR) fire-station list: ' + ff.nExisting + ' Existing and ' + ff.nProposed + ' Proposed records', period: 'undated (service document created 2025-05-24)', res: 'point; positional accuracy not published',
      note: `Status and remark are the source's own words. Of ${ff.nExisting} Existing stations, ${ff.nMoved} carry the remark "Moved" and ${ff.nInaccurate} "not found accurate" (the list does not explain these), and only ${ff.nCorrect} says "Correct", so positions are uncertain. Checked against OpenStreetMap at 10 places the nearest station agreed at 4; OpenStreetMap maps only 10 stations here, so it cannot confirm the rest. This is a straight-line distance to a listed point, not a response time, and it does not confirm that any station is operating.`,
      next: 'Ask the nearest fire station or the municipality for the response area of the station that covers this address.' });
    const nz = cv.noise;
    if (nz && nz.d <= 2500) add('infra', { id: 'noise', label: 'Nearest noise monitor (dated)', value: `${nz.p[2]} (${nz.p[3]}) · ${km(nz.d)} · day ${nz.p[4] ?? '?'} dB, night ${nz.p[5] ?? '?'} dB`, level: (nz.p[6] === 'Over-limit' || nz.p[7] === 'Over-limit') ? 'watch' : 'good', kind: 'observed', conf: 'low', source: 'TSPCB noise monitoring', period: 'Jan–Jun 2018 — dated', res: '10 sites citywide', note: 'Only ten monitors in the whole city.', next: 'Stand on the street at night.' });
    if (r.air) add('infra', { id: 'air', label: 'Air quality right now', value: `US AQI ${r.air.aqi} · ${r.air.band}`, level: r.air.aqi > 150 ? 'concern' : r.air.aqi > 100 ? 'watch' : 'good', kind: 'observed', conf: 'medium', source: 'Open-Meteo air-quality model', period: r.air.time, res: '~11 km model grid', note: 'A live modelled value, not a long-term average.', next: '' });
    else add('infra', { id: 'air', label: 'Air quality right now', value: 'live reading unavailable', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Open-Meteo', note: '', next: '' });
    // ---------- LIVEABILITY ----------
    const devp = id => r.scores.dev.parts.find(p => p.id === id);
    for (const [k, lab] of [['hospital', 'Hospital'], ['school', 'School'], ['market', 'Market / supermarket'], ['metro', 'Metro / rail station'], ['bus', 'Bus station'], ['park', 'Park'], ['bank', 'Bank'], ['police', 'Police station'], ['fire', 'Fire station']]) {
      const f = r.fac[k], p = devp(k); if (!p) continue;
      add('live', { id: 'f_' + k, label: lab, value: f.nearest ? `${f.nearest.name || 'nearest'} · ${km(f.nearest.d)} · ${f.n1km} within 1 km` : 'none mapped nearby', level: !f.nearest ? 'unknown' : p.v >= .65 ? 'good' : p.v >= .3 ? 'watch' : 'concern', kind: 'indicative', conf: 'medium', source: 'OpenStreetMap + Overture Maps', period: 'undated, can lag openings/closures', res: 'point', note: 'Straight-line distance. See Infrastructure for road travel time.', next: '' });
    }
    add('live', { id: 'f_amb', label: 'Government ambulance (108) station', value: r.amb ? `${r.amb.name || 'station'} · ${km(r.amb.d)} · ${r.amb3} within 3 km` : 'none mapped nearby', level: !r.amb ? 'unknown' : r.amb.d <= 3000 ? 'good' : r.amb.d <= 6000 ? 'watch' : 'concern', kind: 'official', conf: 'medium', source: 'Telangana health GIS', period: 'undated', res: 'point', note: '', next: '' });
    if (miss('geo.json')) notRun('live', 'f_jobs', 'Jobs and lifestyle hubs', 'OpenStreetMap places');
    else add('live', { id: 'f_jobs', label: 'Jobs and lifestyle hubs', value: `${r.hubs.work5} office / IT places within 5 km · ${r.hubs.mall3} malls and ${r.hubs.cinema3} cinemas within 3 km`, level: r.hubs.work5 >= 20 ? 'good' : r.hubs.work5 >= 5 ? 'watch' : 'concern', kind: 'indicative', conf: 'medium', source: 'OpenStreetMap + Overture Maps', period: 'undated', res: 'point', note: '', next: '' });
    // ---------- LAND & PLANNING ----------
    if (ld.lost) add('land', { id: 'lost', label: 'Disappeared water body', value: ld.lost.inside ? `this pin is on the footprint of a tank recorded as disappeared (${ld.lost.ha != null ? Number(ld.lost.ha).toFixed(1) + ' ha' : 'size n/a'})` : `a tank recorded as disappeared lies ${km(ld.lost.d)} away (${ld.lost.ha != null ? Number(ld.lost.ha).toFixed(1) + ' ha' : 'size n/a'})`, level: ld.lost.inside ? 'concern' : ld.lost.d <= 150 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'HMDA / TGRAC water-body assessment, "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon',
      note: 'Land built over a former tank tends to flood and can carry legal issues over the lake bed or buffer. This is a map record, not a legal finding.', next: 'Ask for the revenue record history of the survey number and check the old tank map.' });
    else if (miss('land.json')) notRun('land', 'lost', 'Disappeared water body', 'TGRAC disappeared-water-body layer');
    else add('land', { id: 'lost', label: 'Disappeared water body', value: 'none recorded within 400 m', level: 'good', kind: 'official', conf: 'medium', source: 'HMDA / TGRAC "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon', note: 'Absence from this layer does not prove a plot was never a tank.', next: '' });
    if (ld.forest) add('land', { id: 'forest', label: 'Forest land boundary', value: ld.forest.inside ? `inside ${ld.forest.name || 'a forest boundary'}` : `${ld.forest.name || 'forest boundary'} · ${km(ld.forest.d)}`, level: ld.forest.inside ? 'concern' : ld.forest.d <= 300 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS forest boundary (TCUR)', period: 'undated', res: 'polygon', note: 'Forest land generally cannot be built on or sold for development, and a plot near the boundary may be affected by buffer rules.', next: 'Get the Forest Department boundary certificate for the survey number.' });
    if (ld.endow.length) add('land', { id: 'endow', label: 'Endowment (temple) properties nearby', value: `${ld.endow.length} recorded within 400 m · nearest ${km(ld.endow[0].d)} (${ld.endow[0].mandal || 'mandal n/a'})`, level: ld.endow[0].d <= 150 ? 'watch' : 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS endowment properties (Hyderabad)', period: 'undated', res: 'point, location approximate',
      note: 'Points mark recorded endowment properties, not their boundaries. Endowment land cannot normally be sold and encroachment disputes are common.', next: 'Check the title chain for any link to the Endowments Department.' });
    // ---------- property identity, planning authority, parcel overlaps (batch 4) ----------
    const pc = r.parcel ? r.parcel.match : null, pf = planFacts(r.lat, r.lon);
    const PSRC = 'Telangana State GIS (TGRAC) Bhunaksha cadastral layer', PPER = 'undated (service document created 2025-04-19)';
    if (!pc) add('land', { id: 'plot', label: 'Plot identity (survey parcel)', value: 'not matched yet', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: PSRC, period: '—', res: '—',
      note: 'A map pin is not a plot. The pin has not been matched to a surveyed parcel in this view.', next: 'Get the survey number from the sale deed and check it on the Bhu Bharati portal.' });
    else add('land', { id: 'plot', label: 'Plot identity (survey parcel)', value: PARCEL_LABEL[pc.status] + (pc.parcel && pc.status !== 'unavailable' ? ` · survey no. ${pc.parcel.number}, ${pc.parcel.village}` : ''),
      level: pc.status === 'none' && ['number-mismatch', 'neighbour', 'village-mismatch'].includes(pc.reason) ? 'watch' : (pc.status === 'verified' || pc.status === 'approximate') ? 'info' : 'unknown', kind: pc.status === 'unavailable' ? 'unavailable' : 'official',
      conf: pc.status === 'verified' ? 'medium' : pc.status === 'approximate' ? 'low' : 'unavailable', source: PSRC, period: PPER, res: 'parcel outline (~1 m)',
      note: pc.text + ' A drawn outline is not a legal boundary and says nothing about title or ownership.', next: 'Get the survey number from the sale deed, check it on the Bhu Bharati portal, and compare the extent and boundaries with the deed.' });
    if (pf && pf.zone) add('land', { id: 'planauth', label: 'Which official plan governs this area', value: `${pf.info.label} area · ${pf.info.plan}`, level: 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS (TGRAC) HMDA planning-authority layer', period: 'undated (service document created 2025-04-17)', res: 'authority-area polygon (~22 m)',
      note: `This says which plan governs the area. It does not say what this plot is zoned for. HMDA publishes this plan ${pf.info.how}, and SETU does not read it. The boundaries are undated and HMDA's jurisdiction was reportedly widened in 2025 (secondary source), so confirm which plan applies.`, next: 'Open the plan below, find the survey number, and ask HMDA for the land-use certificate.', links: pf.links });
    else add('land', { id: 'planauth', label: 'Which official plan governs this area', value: pf ? 'outside the HMDA authority areas held' : 'planning-authority layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TGRAC) HMDA planning-authority layer', period: '—', res: '—',
      note: 'The governing plan could not be identified for this location.', next: 'Ask HMDA or the local municipality which master plan applies.' });
    add('land', { id: 'zoning', label: 'Master-plan land use and zoning', value: 'not read by SETU', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'HMDA master plans (PDF / image sheets)', period: '—', res: '—',
      note: 'HMDA publishes its plans as static PDF and image sheets; no queryable land-use layer was found, and SETU does not read the sheets. It cannot say whether this plot is residential, commercial, green or reserved for a road.', next: 'Ask HMDA for the land-use certificate for the survey number in writing.', links: pf && pf.zone ? pf.links : [] });
    const ph = prohibFacts(r.lat, r.lon, pc && pc.parcel), phTested = pc ? pc.status !== 'unavailable' : false;
    if (ph) add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: `listed in a state GIS layer as "${ph.cat}"${ph.how === 'survey-number' ? ' (matched by survey number, not by the pin position)' : ''}`, level: 'watch', kind: 'official', conf: 'low', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: 'undated (service document created 2025-04-19)', res: 'parcel outline',
      note: `Survey no. ${ph.sy}${ph.part === 'Y' ? ' (part of the number)' : ''}${ph.extent ? ', extent ' + ph.extent : ''}. This is a mapped overlap with a state GIS list, not a legal finding, and not the registration department's prohibited-property register, which has reportedly contained wrongly listed parcels and is being revised. This layer's date and basis are not documented.`, next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati, and ask for the removal order if it was listed in error.' });
    else if (phTested) add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: 'not listed in this state GIS layer', level: 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: 'undated (service document created 2025-04-19)', res: 'parcel outline',
      note: 'This layer\'s date, basis and completeness are not documented and the official prohibited-property register may differ. Absence here is not clearance.', next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati before paying any advance.' });
    else add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: 'cannot be tested here', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: '—', res: '—',
      note: 'No survey parcels are mapped here, so the layer cannot be tested. That says nothing about whether the property is restricted.', next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati.' });
    if (pc && pc.usable && pc.parcel) {
      const o = overlapFacts(pc.parcel.rings), parts = [], pctx = f => Math.round(f * 100) + '% of the outline';
      if (o.lost) parts.push(`a tank recorded as disappeared (${pctx(o.lost.frac)})`);
      if (o.forest) parts.push(`${o.forest.name || 'a forest boundary'} (${pctx(o.forest.frac)})`);
      for (const t of o.tanks.slice(0, 2)) parts.push(`a mapped tank${t.name ? ' "' + t.name + '"' : ''}, status ${ST_LABEL[t.status] || 'unknown'} in 2023 (${pctx(t.frac)})`);
      add('land', { id: 'overlap', label: 'Mapped features overlapping the parcel outline', value: parts.length ? 'the matched outline overlaps ' + parts.join('; ') : 'no overlap with the 3 layers checked (disappeared water bodies, forest boundary, tank outlines)', level: parts.length ? 'watch' : 'info', kind: 'official', conf: 'low',
        source: 'TGRAC cadastral outline tested against TGRAC water-body, disappeared-tank and forest layers', period: 'undated', res: 'parcel outline vs polygon',
        note: parts.length ? 'Two map layers disagree about the same ground. That is a reason to investigate, not proof of encroachment or of any legal restriction; either outline can be off by metres, and a survey number can be much larger than a house plot.' : 'Only three layers were tested, and a drawn outline can be off by metres. This is not a clearance.', next: 'Ask for a boundary demarcation (FMB sketch) and the revenue record history of the survey number.' });
    } else add('land', { id: 'overlap', label: 'Mapped features overlapping the parcel outline', value: 'needs a matched survey parcel', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: '—', period: '—', res: '—',
      note: 'Pin-based findings above test the pin position only. Tests against the whole parcel outline need a pin that matches exactly one survey parcel.', next: 'Enter the survey number from your deed so the pin can be matched to its outline.' });
    const tsv = tankSurveyFacts(r.lat, r.lon), TSRC = 'Telangana State GIS: HYDRAA water-body layer (tank survey number) + Bhunaksha cadastral and HYDRAA parcel outlines', TPER = 'undated (cadastral service created 2025-04-19; tank layer undated)';
    if (miss('tank_syn.json')) notRun('land', 'tank_survey', 'Tank survey number near this pin', 'tank survey-number data');
    else if (tsv && tsv.tank) {
      const tk = tsv.tank, nm = tk.name || 'an unnamed tank', dist = tk.inside ? 'this pin is on the tank outline' : km(tk.d) + ' from the tank outline', syn = tk.syn.replace(/_/g, ' and ');
      if (!tk.syn) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · the state layer records no survey number for it`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'tank outline (satellite)',
        note: 'Only about a quarter of the 1,192 tank records carry a survey number, so a missing number says nothing about the tank. It means a survey-number check is not possible from this layer.', next: 'Ask the revenue office for the tank\'s survey number and compare it with the survey number on your deed.' });
      else if (!tsv.searched) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · parcel search incomplete`, level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: TSRC, period: TPER, res: '—',
        note: 'The tank\'s survey number is recorded, but the parcel carrying it could not be looked up.', next: 'Check that survey number on Bhu Bharati.' });
      else {
        const cov = p => p.touch ? Math.round(p.cov * 100) + '% of the tank outline is inside it' : 'it does not touch the outline';
        if (tsv.pinIn) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `this pin is inside survey parcel ${tsv.pinIn.no} (${tsv.pinIn.v}), the survey number the state layer records for ${nm}${tk.inside ? '' : ' · ' + dist}`, level: tsv.pinIn.touch && tk.d <= 300 ? 'watch' : 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'parcel outline (~1 m) vs tank outline',
          note: `A match of survey numbers: ${cov(tsv.pinIn)}. A survey parcel is often much larger than the water, so this does not say the plot is under water, inside the legal Full Tank Level or encroached. It is a reason to check the title, not a finding about it. In a 20-lake check a parcel with the tank's number touched the outline at 14 lakes and not at 6.`, next: 'Ask for the revenue record history of this survey number and for the FTL / buffer certificate from HYDRAA or the irrigation department.' });
        else if (tsv.nearest) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · parcel ${tsv.nearest.p.no} is ${km(tsv.nearest.d)} from the pin`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'parcel outline (~1 m) vs tank outline',
          note: `${tsv.nearest.d <= 300 ? 'Close to' : 'Away from'} the tank survey parcel, not on it (${cov(tsv.nearest.p)}). This is not the legal Full Tank Level and says nothing about whether the pin is inside it.`, next: 'Ask HYDRAA or the irrigation department for the FTL / buffer certificate of this tank.' });
        else add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · no parcel with that number found next to the outline`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'tank outline (satellite)',
          note: 'In a 20-lake check a parcel with the tank\'s number was found next to the outline at 16 lakes and not at 4: the number may belong to another village, another numbering, or be a typing error in the layer.', next: 'Ask the revenue office which survey number the tank is recorded under.' });
      }
    }
    add('land', { id: 'perm', label: 'Layout and building permissions', value: 'not integrated', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'HMDA / DTCP', note: '', next: 'Ask for the approved layout (LP number) and building permission, and check them online.' });
    const lbd = lakeBand(r.water);
    add('land', { id: 'ftl', label: 'Lake buffer / FTL risk', value: ['inside', 'very close', 'near'].includes(lbd.band) ? lbd.text : 'no mapped lake or tank close by', level: ['inside', 'very close'].includes(lbd.band) ? 'concern' : lbd.band === 'near' ? 'watch' : 'good', kind: 'indicative', conf: 'medium', source: 'OpenStreetMap + TGRAC outlines', period: 'undated', res: 'polygon', note: 'Plots near a lake\'s Full Tank Level or buffer can face demolition. The outline above is not the legal boundary.', next: 'Get the FTL / buffer confirmation in writing.' });
    if (r.gov.seg && r.gov.seg.d <= 150) { const sg = r.gov.seg; add('land', { id: 'widen', label: 'Nala widening near the plot', value: `existing ${sg.ext_w ?? '?'} m, proposed ${sg.prop_w ?? '?'} m, segment ${km(sg.d)} away`, level: sg.prop_w > (sg.ext_w || 0) * 1.5 ? 'watch' : 'info', kind: 'official', conf: 'low', source: 'TGRAC nala segment widths', period: 'undated', res: 'segment', note: 'Width fields are partly blank (zero) in the source.', next: 'Ask GHMC whether widening could touch this plot.' }); }
    const m = market(r.lat, r.lon, r.wid, 'apt');
    add('land', { id: 'price', label: 'Typical asking price (apartments)', value: m ? `Rs ${m.loc.low.toLocaleString('en-IN')}–${m.loc.high.toLocaleString('en-IN')} per sq ft · ${m.loc.name} · ${km(m.d)} away` : 'no priced locality within 4 km', level: 'info', kind: m ? 'indicative' : 'unavailable', conf: m ? (m.loc.conf || 'low') : 'unavailable', source: 'published portal price-trend pages, compiled in this project', period: m ? m.loc.asOf || 'Oct 2026' : '—', res: 'locality', note: 'Asking prices, not registered sale values. Provenance is indirect and needs a licensed source before any commercial use.', next: 'Compare with the registered market value for the survey number.' });
    const sections = SECTIONS.map(([id, title, blurb]) => {
      const fs = F[id], scored = fs.filter(x => ['concern', 'watch', 'good'].includes(x.level));
      const counts = { concern: 0, watch: 0, good: 0, info: 0, unknown: 0 }; fs.forEach(x => counts[x.level]++);
      // 'Concern' needs a high-severity finding (flood, lake/encroachment, water quality or depth, hospital access, large landfill) or three ordinary concerns,
      // so one weak amenity cannot turn a section red, and a severe flag can never be averaged away by good amenities.
      const hi = fs.some(x => x.level === 'concern' && HIGH.has(x.id));
      const rating = (hi || counts.concern >= 3) ? 'Concern' : (counts.concern || counts.watch) ? 'Watch' : counts.good ? 'Good' : 'Unknown';
      return { id, title, blurb, rating, counts, findings: fs, scored: scored.length };
    });
    const QQ = Q();
    for (const sec of sections) for (const f of sec.findings) { const qf = QQ && QQ.factors[f.id]; f.scope = qf ? qf.scope : null; f.scopeText = qf ? qf.scope_text : ''; f.sourceIds = qf ? qf.sources : []; }
    const identity = pc ? { status: pc.status, reason: pc.reason, label: PARCEL_LABEL[pc.status], text: pc.text, usable: pc.usable, parcel: pc.parcel ? { number: pc.parcel.number, village: pc.parcel.village, mandal: pc.parcel.mandal, areaM2: pc.parcel.areaM2 } : null }
      : { status: 'pending', reason: '', label: 'Not matched yet', text: 'This report describes a map pin, not a surveyed plot.', usable: false, parcel: null };
    const gapsSrc = QQ ? Object.entries(QQ.sources).filter(([, sr]) => sr.files && sr.files.length && sr.files.every(f => (D.loadFailed || []).includes('data/' + f))).map(([id, sr]) => ({ id: 'src:' + id, label: sr.name, section: 'Data sources', value: 'data not loaded', why: 'its data file could not be loaded, so every finding that rests only on it is unavailable' })) : [];
    const gaps0 = sections.flatMap(sec => sec.findings.filter(f => f.level === 'unknown').map(f => ({ id: f.id, label: f.label, section: sec.title, value: f.value, why: (QQ && QQ.factors[f.id] && QQ.factors[f.id].missing) || f.note || 'no data' })));
    const gaps = [...gapsSrc, ...gaps0];
    return { sections, kinds: KIND_LABEL, total: sections.reduce((a, s) => a + s.findings.length, 0), identity, gaps };
  }

  // =====================================================================================================
  // DUE-DILIGENCE CHECKLIST — one action per concerning or unknown finding, grouped by what kind of check it is.
  // "unknown" means "verify", never "unsafe". A portal is marked verified only if we actually reached it or already use it; the rest say so.
  // =====================================================================================================
  const WH = {
    bhu: { name: 'Bhu Bharati land-records portal', url: 'https://bhubharati.telangana.gov.in/', status: 'reachable when we checked; search steps and coverage not verified by SETU' },
    hmdaLakes: { name: 'HMDA lakes portal (FTL and buffer maps)', url: 'https://lakes.hmda.gov.in/', status: 'the lake list in this app comes from it; per-lake PDFs vary' },
    hmda: { name: 'HMDA master-plan pages', url: 'https://www.hmda.gov.in/planning-2/', status: 'website reached on 24 Oct 2026 (master-plan PDFs and image sheets); the office process for a land-use certificate is not verified by SETU' },
    hmdaPerm: { name: 'HMDA DPMS (online layout and building permissions)', url: 'https://www.hmda.gov.in/dpms/', status: 'website reached on 24 Oct 2026; whether it covers this property is not verified by SETU' },
    ghmc: { name: 'GHMC circle office (town planning / engineering)', url: null, status: 'process not verified by SETU' },
    hydraa: { name: 'HYDRAA', url: null, status: 'process not verified by SETU' },
    rev: { name: 'Mandal revenue office (Tahsildar)', url: null, status: 'process not verified by SETU' },
    forest: { name: 'Forest Department divisional office', url: null, status: 'process not verified by SETU' },
    endow: { name: 'Endowments Department', url: null, status: 'process not verified by SETU' },
    util: { name: 'The electricity distribution company', url: null, status: 'process not verified by SETU' },
    gwd: { name: 'Telangana Ground Water Department / a licensed borewell contractor', url: null, status: 'process not verified by SETU' },
    lab: { name: 'A NABL-accredited water-testing laboratory', url: null, status: 'pick any accredited lab' },
    srq: { name: 'Sub-Registrar office (registration and market value)', url: null, status: 'process not verified by SETU' },
    site: { name: 'You, on site', url: null, status: '' },
    water: { name: 'HMWSSB (water and sewerage board)', url: null, status: 'process not verified by SETU' }
  };
  const CHK_TPL = {
    plot: { cat: 'legal', why: 'A map pin is not a plot boundary. Every claim about a plot depends on its survey number.', action: 'Get the survey number (Sy. No.) from the seller\'s sale deed and revenue records, then look it up and compare the extent with the deed.', where: 'bhu', doc: 'Sale deed, Pahani / ROR-1B record, Encumbrance Certificate' },
    prohib: { cat: 'legal', why: 'A state GIS layer lists this survey number under a prohibitory category. That is a mapped overlap, not a legal finding, but property on the official prohibited list is reported to be blocked from registration until it is removed.', action: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati, and ask the seller for the removal order if it was listed in error.', where: 'srq', doc: 'Prohibited-property search result; removal order if it was ever listed' },
    overlap: { cat: 'legal', why: 'The matched survey outline overlaps a mapped tank, disappeared water body or forest boundary. Two map layers disagree about the same ground.', action: 'Ask for a boundary demarcation (FMB sketch) and the revenue record history of the survey number.', where: 'rev', doc: 'FMB sketch / demarcation, revenue record history of the survey number' },
    zoning: { cat: 'legal', why: 'Land use decides what can legally be built or sold. Proximity to other land says nothing about it.', action: 'Ask for the master-plan land-use zone of the survey number in writing.', where: 'hmda', doc: 'Land-use / zoning certificate for the survey number' },
    perm: { cat: 'legal', why: 'Unapproved layouts and buildings can be regularised, penalised or demolished.', action: 'Ask for the approved layout and building permission numbers and check that they match this plot or flat.', where: 'hmdaPerm', doc: 'Approved layout (LP number), building permission, occupancy certificate if built' },
    ftl: { cat: 'legal', why: 'Plots near a lake\'s Full Tank Level or buffer can face restrictions or demolition. The map outline is not the legal boundary.', action: 'Get the Full Tank Level and buffer status for the survey number confirmed in writing.', where: 'hmdaLakes', doc: 'FTL / buffer certificate or letter for the survey number' },
    hy: { cat: 'legal', why: 'The satellite assessment classes a nearby tank as encroached. That is a classification, not a legal order, but it is a reason to check.', action: 'Ask whether the survey number touches the tank\'s mapped extent or buffer, and whether any notice exists.', where: 'hydraa', doc: 'Any HYDRAA / revenue notice, FTL map for the tank' },
    hmda: { cat: 'legal', why: 'The lake is matched by name only, and the notification may be preliminary.', action: 'Open the lake\'s FTL map and confirm it is the same lake, and whether a final notification exists.', where: 'hmdaLakes', doc: 'FTL PDF for the lake' },
    lost: { cat: 'legal', why: 'Land on a former tank bed can flood and can carry disputes over the tank bed or buffer.', action: 'Trace the history of the survey number and check the old village or topo map for a tank on it.', where: 'rev', doc: 'Revenue record history of the survey number, old village map extract' },
    forest: { cat: 'legal', why: 'Forest land generally cannot be built on or sold for development.', action: 'Get a boundary confirmation for the survey number.', where: 'forest', doc: 'Forest boundary / no-objection certificate' },
    endow: { cat: 'legal', why: 'Endowment land cannot normally be sold, and disputes are common. The points here are approximate.', action: 'Check that the title chain has no link to an endowment property.', where: 'endow', doc: 'Title chain, Endowments Department clearance if relevant' },
    nala: { cat: 'flood', why: 'A mapped nala nearby can bring a buffer, widening or flooding.', action: 'Check the plot against the nala buffer and any widening proposal.', where: 'ghmc', doc: 'Nala buffer / widening plan for the segment' },
    nalaenc: { cat: 'flood', why: 'The nala encroachment fields are blank in the public data, so we cannot tell.', action: 'Ask whether an encroachment survey exists for this nala segment.', where: 'ghmc', doc: 'Nala encroachment survey for the segment' },
    widen: { cat: 'legal', why: 'A proposed nala width greater than today\'s can take land.', action: 'Ask whether the widening could touch this plot.', where: 'ghmc', doc: 'Proposed nala widening alignment' },
    sus: { cat: 'flood', why: 'The ward ranks high for flood susceptibility.', action: 'Ask neighbours and the resident association which streets waterlogged in 2020 and 2025, and visit during heavy rain.', where: 'site', doc: 'Insurance quote and past claim history for the area' },
    depth: { cat: 'flood', why: 'The model puts water in this ward in a big storm (an order-of-magnitude assumption).', action: 'Check the street level against the road and nearest drain.', where: 'site', doc: '' },
    storms: { cat: 'flood', why: 'News named this ward in several of the documented floods.', action: 'Ask which of those storms put water on your street or building.', where: 'site', doc: '' },
    inund: { cat: 'flood', why: 'A GHMC-listed waterlogging point is close.', action: 'Look at the spot after rain and ask how long water stays.', where: 'site', doc: '' },
    lake: { cat: 'flood', why: 'The pin is close to a lake or tank outline.', action: 'Check whether the approach road floods when the lake is full.', where: 'site', doc: '' },
    pocket: { cat: 'flood', why: 'The pin sits lower than its surroundings.', action: 'Ask whether water has ever entered the ground floor.', where: 'site', doc: '' },
    stream: { cat: 'flood', why: 'A mapped natural stream channel is close. This only shows where terrain puts a channel.', action: 'Check the old map for a stream on the survey number and look at where water runs on the street.', where: 'rev', doc: 'Old village map or revenue map extract' },
    gwdepth: { cat: 'water', why: 'We could not give a reliable neighbourhood groundwater depth.', action: 'Ask owners nearby how deep their borewells go, how often they fail, and whether they buy tanker water.', where: 'gwd', doc: 'Recent borewell log or yield test nearby' },
    gwpre: { cat: 'water', why: 'The water table is deep at the end of the dry season.', action: 'Ask about summer tanker dependence.', where: 'gwd', doc: '' },
    gwtrend: { cat: 'water', why: 'The nearby water table is falling.', action: 'Look for recent borewell failures in the area.', where: 'gwd', doc: '' },
    gwrec: { cat: 'water', why: 'Little rebound after the monsoon suggests weak recharge.', action: 'Ask whether borewells recover after the rains.', where: 'gwd', doc: '' },
    gwf: { cat: 'water', why: 'Nearby wells show fluoride above the permissible limit. These are other wells, not your water.', action: 'Test the actual borewell or supply water before you rely on it.', where: 'lab', doc: 'Lab report for fluoride, nitrate, TDS and pH' },
    gwno3: { cat: 'water', why: 'Nearby wells show nitrate above the limit. These are other wells, not your water.', action: 'Test the actual water before you rely on it.', where: 'lab', doc: 'Lab report for fluoride, nitrate, TDS and pH' },
    gwtds: { cat: 'water', why: 'Nearby groundwater is salty. These are other wells, not your water.', action: 'Ask whether residents use RO purifiers and test the actual water.', where: 'lab', doc: 'Lab report for TDS' },
    gwq: { cat: 'water', why: 'No recent groundwater-quality sample is near this location.', action: 'Test the actual water at a lab.', where: 'lab', doc: 'Lab report for fluoride, nitrate, TDS and pH' },
    gwp: { cat: 'water', why: 'The regional map suggests weak recharge or low well yields here, or has no unit for this spot.', action: 'Ask a borewell contractor who has drilled within a few hundred metres.', where: 'gwd', doc: 'Borewell log: depth and yield' },
    supply: { cat: 'infra', why: 'We could not see whether the property has a municipal water and sewer connection.', action: 'Ask for the water and sewerage connection papers and the latest bills.', where: 'water', doc: 'Water and sewerage connection papers, recent bills' },
    landfill: { cat: 'infra', why: 'A dump yard is close enough to affect smell or air.', action: 'Visit on a hot afternoon with the wind blowing from the site.', where: 'site', doc: '' },
    tx: { cat: 'infra', why: 'A high-voltage line runs close by and may carry a no-build corridor.', action: 'Ask whether the plot lies under a transmission corridor.', where: 'util', doc: 'Any corridor or right-of-way letter' },
    choke: { cat: 'infra', why: 'Traffic congestion points are near.', action: 'Drive the commute at peak hours.', where: 'site', doc: '' },
    acc_hospital: { cat: 'infra', why: 'The estimated drive to a hospital is long.', action: 'Drive the route once at a busy time.', where: 'site', doc: '' },
    acc_metro: { cat: 'infra', why: 'The estimated drive to a metro or rail station is long.', action: 'Check how you would really get there.', where: 'site', doc: '' },
    heat: { cat: 'infra', why: 'The area runs hot in the dry season.', action: 'Check shade, roof type and green cover on site.', where: 'site', doc: '' },
    price: { cat: 'legal', why: 'Asking prices from portals are not registered sale values.', action: 'Compare with the registered market value for the survey number.', where: 'srq', doc: 'Registered market value (guidance value) for the survey number' }
  };
  const CHK_CAT = { legal: 'Legal and land records', flood: 'Flood and drainage', water: 'Water supply and quality', infra: 'Infrastructure and access' };
  function checklist(r) {
    const items = [], seen = new Set(), ev = r.ev || evidence(r);
    const rank = { concern: 0, watch: 1, unknown: 2, info: 3 };
    // Only real data gaps become 'verify' items. Transient gaps (elevation or routing lookup pending, heat not covering a point) are not checklist items.
    const UNK_OK = new Set(['plot', 'zoning', 'perm', 'nalaenc', 'gwdepth', 'gwq', 'gwp', 'supply', 'prohib']);
    const fs = ev.sections.flatMap(sec => sec.findings).filter(f => rank[f.level] != null).sort((a, b) => rank[a.level] - rank[b.level]);
    for (const f of fs) {
      const key = (f.id.startsWith('acc_') && f.id !== 'acc_hospital' && f.id !== 'acc_metro') ? null : f.id, tpl = key && CHK_TPL[key];
      if (!tpl || seen.has(key)) continue;
      const lv = f.level, include = lv === 'concern' || lv === 'watch' || (lv === 'unknown' && UNK_OK.has(key)) || (lv === 'info' && (key === 'gwdepth' || key === 'price' || key === 'plot'));
      if (!include) continue;
      seen.add(key);
      items.push({ key, cat: tpl.cat, trigger: { id: f.id, label: f.label, level: lv === 'info' ? 'unknown' : lv, value: f.value }, gap: lv === 'unknown' || (lv === 'info' && key === 'gwdepth'), why: tpl.why, action: tpl.action, where: WH[tpl.where], doc: tpl.doc });
    }
    // checks that apply to every purchase, kept separate so they are never mistaken for data-driven findings
    const std = [
      { key: 'std_ec', cat: 'legal', trigger: { id: 'std_ec', label: 'Encumbrance Certificate and clean title chain', level: 'standard', value: '' }, why: 'Shows loans, mortgages and transfers recorded against the property.', action: 'Get an Encumbrance Certificate for at least the last 30 years and a clean title chain.', where: WH.srq, doc: 'Encumbrance Certificate, title chain' },
      { key: 'std_rera', cat: 'legal', trigger: { id: 'std_rera', label: 'RERA registration (if the project is under construction)', level: 'standard', value: '' }, why: 'Under-construction projects should be registered.', action: 'If the project is under construction, confirm its RERA registration and the promised completion date.', where: { name: 'Telangana RERA', url: null, status: 'process not verified by SETU' }, doc: 'RERA registration number' }
    ];
    return { items, std, cats: CHK_CAT, nData: items.length };
  }

  // =====================================================================================================
  // COMPARE TWO ADDRESSES. Same evidence engine for both. It states where findings differ and how much evidence each address has.
  // It never names a winner and never sums a score: "unknown on one side" is NOT COMPARABLE, not better or worse, and unknown never means safe.
  // =====================================================================================================
  const CMP_SEV = { concern: 3, watch: 2, good: 1 };
  function coverage(r) {
    const secs = r.ev.sections.map(sec => { const c = sec.counts, total = sec.findings.length, unknown = c.unknown; return { id: sec.id, title: sec.title, total, unknown, known: total - unknown, rated: c.concern + c.watch + c.good, pct: total ? (total - unknown) / total : 0 }; });
    const total = secs.reduce((a, x) => a + x.total, 0), unknown = secs.reduce((a, x) => a + x.unknown, 0), rated = secs.reduce((a, x) => a + x.rated, 0);
    return { sections: secs, total, unknown, known: total - unknown, rated, pct: total ? (total - unknown) / total : 0 };
  }
  function cmpKind(x, y) {
    if (!x) return 'only-b';
    if (!y) return 'only-a';
    const ux = x.level === 'unknown', uy = y.level === 'unknown';
    if (ux && uy) return 'both-unknown';
    if (ux || uy) return 'not-comparable';
    const sx = CMP_SEV[x.level], sy = CMP_SEV[y.level];
    if (sx && sy) return sx === sy ? 'same' : sx > sy ? 'a-more-severe' : 'b-more-severe';
    if (!sx && !sy) return x.value === y.value ? 'same' : 'differs-unrated';
    return 'not-comparable';   // one side is rated, the other is information only
  }
  function compare(a, b) {
    const ca = coverage(a), cb = coverage(b);
    const sections = SECTIONS.map(([id, title], si) => {
      const fa = a.ev.sections[si].findings, fb = b.ev.sections[si].findings, ia = new Map(fa.map(f => [f.id, f])), ib = new Map(fb.map(f => [f.id, f]));
      const ids = [...fa.map(f => f.id), ...fb.map(f => f.id).filter(id => !ia.has(id))];
      const rows = ids.map(rid => { const x = ia.get(rid) || null, y = ib.get(rid) || null; return { id: rid, label: (x || y).label, a: x, b: y, cmp: cmpKind(x, y), high: HIGH.has(rid) }; });
      const tally = k => rows.filter(rw => rw.cmp === k).length;
      return { id, title, ratingA: a.ev.sections[si].rating, ratingB: b.ev.sections[si].rating, covA: ca.sections[si], covB: cb.sections[si], rows,
        counts: { aMore: tally('a-more-severe'), bMore: tally('b-more-severe'), same: tally('same'), notComparable: tally('not-comparable'), bothUnknown: tally('both-unknown'), onlyA: tally('only-a'), onlyB: tally('only-b'), differsUnrated: tally('differs-unrated') } };
    });
    const all = sections.flatMap(sec => sec.rows.map(rw => ({ ...rw, section: sec.title })));
    const gap = rw => Math.abs(CMP_SEV[rw.a.level] - CMP_SEV[rw.b.level]);
    const bigger = all.filter(rw => rw.cmp === 'a-more-severe' || rw.cmp === 'b-more-severe').sort((p, q) => (q.high - p.high) || (gap(q) - gap(p)));
    return { sections, coverage: { a: ca, b: cb }, biggest: bigger, notComparable: all.filter(rw => rw.cmp === 'not-comparable'),
      checklist: { a: checklist(a).items.length, b: checklist(b).items.length },
      note: `This compares evidence; it does not say which address is safer or better. Evidence coverage differs (${Math.round(ca.pct * 100)}% of findings have data for A, ${Math.round(cb.pct * 100)}% for B), and a finding with no data is never a clean bill of health.` };
  }

  function analyse(r) {
    r.scores = { water: waterRisk(r), dev: development(r), motor: motorRisk(r), prop: propertyRisk(r), health: healthRisk(r) };
    r.tiers = { water: tier(r.scores.water.score, 'water'), motor: tier(r.scores.motor.score, 'motor'), prop: tier(r.scores.prop.score, 'prop'), health: tier(r.scores.health.score, 'health') };
    r.buyer = buyerVerdict(r);
    r.pillars = pillars(r);
    r.ev = evidence(r);
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

  return { load, report, evidence, checklist, HIGH, fireFacts, seismicFacts, tankSurveyFacts, parseMapsLink, compare, coverage, parcelLoad, parcelMatch, attachParcel, setParcel, planFacts, netFacts, prohibFacts, overlapFacts, freshness, qualityTable, removalImpact, PARCEL_LABEL, normNum, editSim, rainFacts, analogFacts, tankFacts, streamFacts, ANALOG_EVENTS, roadAccess, gwFacts, gwqFacts, civicFacts, heatFacts, accessFacts, SECTIONS, KIND_LABEL, HY_LABEL, hmdaText, hmdaLink, pillars, addTerrain, elevationProfile, reanalyse: analyse, airNow, curve, totalCost, market, priceBand, claimCheck, rainOn, forecast, depthAt, imd, narrate, locate, lakeBand, nearest, poisWithin, hav, inBounds, tier, LOADING, FAC, get D() { return D; }, get data() { return D; } };
})();
