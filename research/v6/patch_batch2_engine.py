"""One-off patch (batch 2): heavy-rain frequency, storm analogs, tank capacity, stream order and the due-diligence checklist in web/platform/engine.js."""
p = "web/platform/engine.js"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, "missing: " + old[:90]
    s = s.replace(old, new, 1)

# ---- loading ----
rep("'data/stormhist.json', 'data/heat.json', 'data/access.json', 'data/land.json'];", "'data/stormhist.json', 'data/heat.json', 'data/access.json', 'data/land.json', 'data/tanks.json', 'data/rainstats.json'];")
rep("'gw', 'gwq', 'civic', 'storm', 'heat', 'access', 'land'];", "'gw', 'gwq', 'civic', 'storm', 'heat', 'access', 'land', 'tanks', 'rainstats'];")
rep("land: { meta: {}, gwp: [], gwp_attrs: [], lost: [], forest: [], tx: [], sub: [], endow: [] } };",
    "land: { meta: {}, gwp: [], gwp_attrs: [], lost: [], forest: [], tx: [], sub: [], endow: [] }, tanks: { meta: {}, tanks: [], streams: [] }, rainstats: { meta: {}, mandals: {} } };")

# ---- prep: bounding boxes ----
rep("    const grid = g => g && g.meta ? g : null;",
    """    const TK = D.tanks || {}; D.tankL = { tanks: (TK.tanks || []).map(t => ({ ...t, _b: bbLL(t.r[0]) })), streams: (TK.streams || []).map(t => ({ ...t, _b: t.p.map(bbLL) })) };
    const grid = g => g && g.meta ? g : null;""")

# ---- fact functions, placed before the SECTIONS table ----
rep("  const SECTIONS = [",
r'''  // Heavy-rain counts: from the rainfall months we hold (event months, NOT a full year). The mandal key is the upper-cased mandal name used in the rainfall table.
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

  const SECTIONS = [''')

# ---- evidence findings ----
# hazards: heavy rain + analog, placed right after the 'storms' finding block (inside the non-outside branch)
rep("""          note: ev.map((e, i) => `${e.label}: ${sh.r[i] == null ? 'n/a' : sh.r[i] + ' mm'}${sh.n[i] ? ' · named' : ''}`).join('  |  ') + '. "Named" means a news report named this ward; absence does not prove it stayed dry.', next: 'Ask which of these storms put water on your street. Research-layer data (rainfall source is non-commercial).' });
      }""",
"""          note: ev.map((e, i) => `${e.label}: ${sh.r[i] == null ? 'n/a' : sh.r[i] + ' mm'}${sh.n[i] ? ' · named' : ''}`).join('  |  ') + '. "Named" means a news report named this ward; absence does not prove it stayed dry. Sept 2016 is dated only to the month and June 2025 has an incomplete rainfall month, so their rainfall is approximate. Rain is the mandal gauge value, not rain at the plot.', next: 'Ask which of these storms put water on your street. Research-layer data (rainfall source is non-commercial).' });
      }
      const rf = rainFacts(r.wid), mUsed = rf ? rf.meta.months_used : [];
      if (rf) add('hazards', { id: 'heavyrain', label: 'Heavy-rain days recorded by this mandal (months we hold)', value: `${rf.days_over} day${rf.days_over === 1 ? '' : 's'} above ${rf.meta.threshold_mm} mm in ${rf.days_obs} observed days (${mUsed.length} months, not an annual count) · wettest ${rf.wettest[0]} mm on ${rf.wettest[1]}`, level: 'info', kind: 'observed', conf: 'medium',
        source: 'Open Data Telangana (TSDPS) mandal daily rainfall', period: `${mUsed.length} months: ${mUsed.join(', ')}`, res: `mandal (${rf.mandal}), not the plot`,
        note: `Only these months are held, and they were the months with documented floods, so the count runs higher than a full-year frequency would. ${rf.meta.months_excluded.length} further months were excluded because under 90% of their days are present. Top days: ${rf.top.slice(0, 4).map(t => t[0] + ' ' + t[1] + ' mm').join(', ') || 'none above the threshold'}. Rain-day is 08:30 to 08:30 IST. 64.5 mm is the IMD heavy-rain threshold.`, next: 'Ask residents how the street behaves after a downpour, not only after the very biggest storms.' });
      else add('hazards', { id: 'heavyrain', label: 'Heavy-rain days recorded by this mandal', value: 'no rainfall record matched to this ward', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Open Data Telangana (TSDPS)', note: 'The ward could not be matched to a mandal with enough days of data.', next: '' });
      const an = analogFacts(r.wid);
      if (an) add('hazards', { id: 'analog', label: 'Storm analogs (preliminary historical association)', value: an.n < 3 ? `only ${an.n} documented storm${an.n === 1 ? '' : 's'} with at least ${an.mm} mm in this mandal — too few to say anything` : `${an.k} of ${an.n} documented storms with at least ${an.mm} mm in this mandal had this ward named in news`, level: 'info', kind: 'observed', conf: 'low',
        source: 'TSDPS mandal rainfall + news-sourced ward labels', period: 'storms Oct 2020 – Jun 2026', res: 'mandal (rain) vs ward (naming)',
        note: an.rows.map(x => `${x.label}: ${x.mm} mm${x.named ? ' · named' : ''}${x.mm < an.mm ? ' (below threshold)' : ''}`).join('  |  ') + '. A news mention is not a flood measurement, mandal rain is not rain at this plot, and a handful of storms cannot establish a pattern. This is an association, not a forecast.', next: 'Use it only to ask better questions of neighbours; do not read it as a probability.' });""")

# hazards: stream order (after the nala finding) — find an anchor that always runs
rep("    add('hazards', { id: 'inund', label: 'Officially listed inundation area'",
    """    const sf = streamFacts(r.lat, r.lon);
    if (!sf) add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: 'stream layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'TGRAC stream order', note: '', next: '' });
    else if (sf.nearest) add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: `${sf.nearest.name || 'unnamed stream'} (stream order ${sf.nearest.o ?? '?'}) · ${km(sf.nearest.d)} · ${sf.n300} segment${sf.n300 === 1 ? '' : 's'} within 300 m`, level: sf.nearest.d <= 50 && (sf.nearest.o || 0) >= 3 ? 'watch' : 'info', kind: 'estimate', conf: 'low',
      source: 'Telangana State GIS stream-order layer (terrain-derived network)', period: 'undated', res: 'line, positional accuracy not published',
      note: 'Stream order only says where the terrain model puts a natural channel. It does not prove that a channel (open or buried) crosses the plot, or that the plot floods. Higher order means a larger catchment.', next: 'Look at the old village or revenue map for a stream on the survey number, and check where water runs on the street.' });
    else add('hazards', { id: 'stream', label: 'Natural stream channel nearby', value: 'no mapped stream within 500 m', level: 'info', kind: 'estimate', conf: 'low', source: 'Telangana State GIS stream-order layer', period: 'undated', res: 'line', note: 'The network is terrain-derived: small or buried channels may not appear, so this is not a clearance.', next: '' });
    add('hazards', { id: 'inund', label: 'Officially listed inundation area'""")

# water: tank capacity (place right before the groundwater potential block; landFacts 'ld' is defined there, so put it before 'supply' using tankFacts directly)
rep("    add('water', { id: 'supply', label: 'Piped water and sewerage coverage'",
    """    const tf = tankFacts(r.lat, r.lon);
    if (!tf) add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: 'tank layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'TGRAC water-body layer', note: '', next: '' });
    else if (!tf.n2) add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: 'no mapped tank within 2 km', level: 'info', kind: 'official', conf: 'low', source: 'TGRAC / HMDA water-body layer (2,048 records, de-duplicated)', period: 'undated, status classes 2011 and 2023', res: 'polygon', note: 'Absence from this layer does not prove there is no tank or pond.', next: '' });
    else add('water', { id: 'tankstore', label: 'Mapped tank storage nearby', value: `${tf.n2} mapped tank${tf.n2 === 1 ? '' : 's'} within 2 km · estimated design capacity ${(tf.capM3 / 1e6).toFixed(2)} million m³ for the ${tf.nCap} with a bund height (${tf.nNoCap} have no capacity figure)${tf.nearest ? ` · nearest ${tf.nearest.t.a[0] || 'unnamed tank'}, ${tf.nearest.inside ? 'under this pin' : km(tf.nearest.d)}, 2023 status ${ST_LABEL[tf.nearest.t.a[5]] || 'not classified'}` : ''}`, level: 'info', kind: 'official', conf: 'low',
      source: 'TGRAC / HMDA water-body layer (2,048 records after removing overlaps; an identical second layer was ignored)', period: 'topo-sheet and revenue-map extents; status classes 2011 and 2023', res: 'polygon',
      note: `Capacity is the source's own formula (area x bund height / 2), an estimate of the original design capacity, not measured water. Present-day storage is not measured here. By count, ${tf.enc2023} of these ${tf.n2} tanks are classed partially or totally encroached in 2023 (${tf.enc2011} in 2011). Status is a satellite classification, not a legal finding, and capacity is missing for most tanks.`, next: 'Ask the irrigation department or HYDRAA whether the tank nearest your plot still holds water in the monsoon.' });
    add('water', { id: 'supply', label: 'Piped water and sewerage coverage'""")

# HIGH set: stream is not high severity; analog/heavyrain/tankstore are info-only. Exports + checklist below.
rep("  function analyse(r) {",
r'''  // =====================================================================================================
  // DUE-DILIGENCE CHECKLIST — one action per concerning or unknown finding, grouped by what kind of check it is.
  // "unknown" means "verify", never "unsafe". A portal is marked verified only if we actually reached it or already use it; the rest say so.
  // =====================================================================================================
  const WH = {
    bhu: { name: 'Bhu Bharati land-records portal', url: 'https://bhubharati.telangana.gov.in/', status: 'reachable when we checked; search steps and coverage not verified by SETU' },
    hmdaLakes: { name: 'HMDA lakes portal (FTL and buffer maps)', url: 'https://lakes.hmda.gov.in/', status: 'the lake list in this app comes from it; per-lake PDFs vary' },
    hmda: { name: 'HMDA planning section', url: null, status: 'office process not verified by SETU (its website did not respond when we checked)' },
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
    zoning: { cat: 'legal', why: 'Land use decides what can legally be built or sold. Proximity to other land says nothing about it.', action: 'Ask for the master-plan land-use zone of the survey number in writing.', where: 'hmda', doc: 'Land-use / zoning certificate for the survey number' },
    perm: { cat: 'legal', why: 'Unapproved layouts and buildings can be regularised, penalised or demolished.', action: 'Ask for the approved layout and building permission numbers and check that they match this plot or flat.', where: 'hmda', doc: 'Approved layout (LP number), building permission, occupancy certificate if built' },
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
    const UNK_OK = new Set(['plot', 'zoning', 'perm', 'nalaenc', 'gwdepth', 'gwq', 'gwp', 'supply']);
    const fs = ev.sections.flatMap(sec => sec.findings).filter(f => rank[f.level] != null).sort((a, b) => rank[a.level] - rank[b.level]);
    for (const f of fs) {
      const key = (f.id.startsWith('acc_') && f.id !== 'acc_hospital' && f.id !== 'acc_metro') ? null : f.id, tpl = key && CHK_TPL[key];
      if (!tpl || seen.has(key)) continue;
      const lv = f.level, include = lv === 'concern' || lv === 'watch' || (lv === 'unknown' && UNK_OK.has(key)) || (lv === 'info' && (key === 'gwdepth' || key === 'price'));
      if (!include) continue;
      seen.add(key);
      items.push({ key, cat: tpl.cat, trigger: { id: f.id, label: f.label, level: lv === 'info' ? 'unknown' : lv, value: f.value }, gap: lv === 'unknown' || (lv === 'info' && key === 'gwdepth'), why: tpl.why, action: tpl.action, where: WH[tpl.where], doc: tpl.doc });
    }
    // checks that apply to every purchase, kept separate so they are never mistaken for data-driven findings
    const std = [
      { key: 'std_ec', cat: 'legal', trigger: { id: 'std', label: 'Standard check for every purchase', level: 'standard', value: '' }, why: 'Shows loans, mortgages and transfers recorded against the property.', action: 'Get an Encumbrance Certificate for at least the last 30 years and a clean title chain.', where: WH.srq, doc: 'Encumbrance Certificate, title chain' },
      { key: 'std_rera', cat: 'legal', trigger: { id: 'std', label: 'Standard check for every purchase', level: 'standard', value: '' }, why: 'Under-construction projects should be registered.', action: 'If the project is under construction, confirm its RERA registration and the promised completion date.', where: { name: 'Telangana RERA', url: null, status: 'process not verified by SETU' }, doc: 'RERA registration number' }
    ];
    return { items, std, cats: CHK_CAT, nData: items.length };
  }

  function analyse(r) {''')
rep("return { load, report, evidence, roadAccess,", "return { load, report, evidence, checklist, rainFacts, analogFacts, tankFacts, streamFacts, ANALOG_EVENTS, roadAccess,")
open(p, "w", encoding="utf-8").write(s)
print("batch-2 engine patched")
