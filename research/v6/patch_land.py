"""One-off patch: TGRAC land/geology/utility layers (land.json) into the engine and the evidence report."""
p = "web/platform/engine.js"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, "missing: " + old[:90]
    s = s.replace(old, new, 1)

# 1) loading
rep("'data/groundwater.json', 'data/gwquality.json', 'data/civic.json', 'data/stormhist.json', 'data/heat.json', 'data/access.json'];",
    "'data/groundwater.json', 'data/gwquality.json', 'data/civic.json', 'data/stormhist.json', 'data/heat.json', 'data/access.json', 'data/land.json'];")
rep("'gw', 'gwq', 'civic', 'storm', 'heat', 'access'];", "'gw', 'gwq', 'civic', 'storm', 'heat', 'access', 'land'];")
rep("storm: { events: [], wards: {} }, heat: null, access: null };", "storm: { events: [], wards: {} }, heat: null, access: null, land: { meta: {}, gwp: [], gwp_attrs: [], lost: [], forest: [], tx: [], sub: [], endow: [] } };")

# 2) prep: bounding boxes
rep("    const grid = g => g && g.meta ? g : null;",
    """    const Ld = D.land || {}; D.landL = { gwp: (Ld.gwp || []).map(u => ({ ...u, _b: u.r.map(bbLL) })), lost: (Ld.lost || []).map(u => ({ ...u, _b: u.r.map(bbLL) })), forest: (Ld.forest || []).map(u => ({ ...u, _b: u.r.map(bbLL) })),
      tx: (Ld.tx || []).map(u => ({ ...u, _b: u.p.map(bbLL) })), sub: Ld.sub || [], endow: Ld.endow || [] };
    const grid = g => g && g.meta ? g : null;""")

# 3) land facts
rep("  const gridIdx = (g, lat, lon) =>",
    """  const GWF = ['geom', 'landform', 'rock', 'depth_to_water', 'wells_observed', 'recharge', 'aquifer', 'well_type', 'well_depth', 'yield', 'success', 'water_quality', 'recharge_structures', 'remarks'];
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
  const gridIdx = (g, lat, lon) =>""")

# 4) evidence findings
HIGH_OLD = "'acc_hospital', 'landfill']);"
rep(HIGH_OLD, "'acc_hospital', 'landfill', 'lost', 'forest', 'gwp']);")
# water: groundwater potential (after the lake water-quality block, before 'supply')
rep("    add('water', { id: 'supply', label: 'Piped water and sewerage coverage'",
    """    const ld = landFacts(r.lat, r.lon);
    if (ld.gwp && (ld.gwp.recharge || ld.gwp.well_depth || ld.gwp.yield)) {
      const rc = (ld.gwp.recharge || '').toUpperCase(), bits = [ld.gwp.well_depth && `suggested well depth ${ld.gwp.well_depth}`, ld.gwp.yield && `typical yield ${ld.gwp.yield}`, ld.gwp.success && `success rate ${String(ld.gwp.success).toLowerCase()}`, ld.gwp.water_quality && String(ld.gwp.water_quality).toLowerCase()].filter(Boolean);
      add('water', { id: 'gwp', label: 'Hydrogeology of the ground here (regional map)', value: `${rc ? rc.toLowerCase() + ' recharge' : 'recharge not stated'} · ${(ld.gwp.landform || 'landform n/a').replace(/\\s*\\(.*\\)/, '')} · ${(ld.gwp.rock || 'rock n/a').replace(/\\s*\\(\\d+\\)/, '').toLowerCase()}`,
        level: /NIL/.test(rc) ? 'concern' : /POOR/.test(rc) ? 'watch' : /MODERATE|GOOD/.test(rc) ? 'good' : 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS groundwater-potential (hydro-geomorphological) map', period: 'undated regional survey', res: 'map unit (about 1:50,000)',
        note: (bits.length ? bits.join(' · ') + '. ' : '') + (ld.gwp.remarks ? ld.gwp.remarks + ' ' : '') + 'This describes the type of ground and what wells usually yield in it. It is not a promise for any one plot.', next: 'Ask a borewell contractor who has drilled within a few hundred metres.' });
    } else add('water', { id: 'gwp', label: 'Hydrogeology of the ground here (regional map)', value: ld.gwp ? 'unit has no hydrogeology attributes' : 'no mapped unit under this pin', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS groundwater-potential map', note: 'Built-up and water-body units carry no groundwater attributes in this map.', next: '' });
    add('water', { id: 'supply', label: 'Piped water and sewerage coverage'""")
# infra: HT lines / substation (before landfill line)
rep("    const major = lf && lf.ha >= 20;",
    """    if (ld.tx && ld.tx.d <= 600) add('infra', { id: 'tx', label: 'High-voltage transmission line nearby', value: `${ld.tx.name || 'line'}${ld.tx.kv ? ' (' + ld.tx.kv + ' kV)' : ''} · ${km(ld.tx.d)}`, level: ld.tx.d <= 100 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS electric transmission layer (TCUR)', period: 'undated', res: 'line', note: 'Buyers sometimes discount plots under or beside high-voltage lines; the line may also carry a no-build corridor.', next: 'Ask the seller whether the plot is under a transmission corridor.' });
    if (ld.sub && ld.sub.d <= 1000) add('infra', { id: 'sub', label: 'Electricity substation nearby', value: `${ld.sub.name} (${ld.sub.volt}) · ${km(ld.sub.d)}`, level: 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS substations (TCUR)', period: 'undated', res: 'point', note: 'A nearby substation usually means a robust supply, but can mean noise and hum.', next: '' });
    const major = lf && lf.ha >= 20;""")
# land: lost tank, forest, endowment (before the 'plot' finding)
rep("    add('land', { id: 'plot', label: 'Plot identity'",
    """    if (ld.lost) add('land', { id: 'lost', label: 'Disappeared water body', value: ld.lost.inside ? `this pin is on the footprint of a tank recorded as disappeared (${ld.lost.ha != null ? Number(ld.lost.ha).toFixed(1) + ' ha' : 'size n/a'})` : `a tank recorded as disappeared lies ${km(ld.lost.d)} away (${ld.lost.ha != null ? Number(ld.lost.ha).toFixed(1) + ' ha' : 'size n/a'})`, level: ld.lost.inside ? 'concern' : ld.lost.d <= 150 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'HMDA / TGRAC water-body assessment, "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon',
      note: 'Land built over a former tank tends to flood and can carry legal issues over the lake bed or buffer. This is a map record, not a legal finding.', next: 'Ask for the revenue record history of the survey number and check the old tank map.' });
    else add('land', { id: 'lost', label: 'Disappeared water body', value: 'none recorded within 400 m', level: 'good', kind: 'official', conf: 'medium', source: 'HMDA / TGRAC "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon', note: 'Absence from this layer does not prove a plot was never a tank.', next: '' });
    if (ld.forest) add('land', { id: 'forest', label: 'Forest land boundary', value: ld.forest.inside ? `inside ${ld.forest.name || 'a forest boundary'}` : `${ld.forest.name || 'forest boundary'} · ${km(ld.forest.d)}`, level: ld.forest.inside ? 'concern' : ld.forest.d <= 300 ? 'watch' : 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS forest boundary (TCUR)', period: 'undated', res: 'polygon', note: 'Forest land generally cannot be built on or sold for development, and a plot near the boundary may be affected by buffer rules.', next: 'Get the Forest Department boundary certificate for the survey number.' });
    if (ld.endow.length) add('land', { id: 'endow', label: 'Endowment (temple) properties nearby', value: `${ld.endow.length} recorded within 400 m · nearest ${km(ld.endow[0].d)} (${ld.endow[0].mandal || 'mandal n/a'})`, level: ld.endow[0].d <= 150 ? 'watch' : 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS endowment properties (Hyderabad)', period: 'undated', res: 'point, location approximate',
      note: 'Points mark recorded endowment properties, not their boundaries. Endowment land cannot normally be sold and encroachment disputes are common.', next: 'Check the title chain for any link to the Endowments Department.' });
    add('land', { id: 'plot', label: 'Plot identity'""")
open(p, "w", encoding="utf-8").write(s)
print("land patched")
