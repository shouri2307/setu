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
    if (lat < b[1] - padD || lat > b[3] + padD || lon < b[0] - padD || lon > b[2] + padD) return { ok: true, outsideBox: true, parcels: [] };
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

  // ---------- evidence-quality registry helpers ----------
  const Q = () => (D.quality && D.quality.sources) ? D.quality : null;
  const monthsBetween = (ym, asOf) => { const [y, mo] = String(ym).split('-').map(Number); return (asOf.getUTCFullYear() - y) * 12 + (asOf.getUTCMonth() + 1 - (mo || 12)); };
  function freshness(src, asOf) {   // live | current | aging | stale | undated | historical | reference | documents | model
    asOf = asOf || new Date();
    if (src.nature === 'live') return 'live';
    if (src.nature === 'reference') return 'reference';
    if (src.nature === 'documents') return 'documents';
    if (!src.obs) return 'undated';
    if (src.nature === 'history') return 'historical';
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
