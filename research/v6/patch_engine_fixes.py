"""One-off patch: groundwater estimate rules, landfill size classes, severity-aware section ratings (applied to web/platform/engine.js)."""
p = "web/platform/engine.js"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, "missing: " + old[:80]
    s = s.replace(old, new, 1)

# 1) groundwater: an area estimate needs >= 3 wells; flag wide disagreement
rep("latest: near3.length >= 2 ? median(vals) : null, pre: near3.length >= 2 ? median(near3.map(x => x.s.pre)) : null, rec: near3.length >= 2 ? median(near3.map(x => x.s.rec)) : null,",
    "latest: near3.length >= 3 ? median(vals) : null, pre: near3.length >= 3 ? median(near3.map(x => x.s.pre)) : null, rec: near3.length >= 3 ? median(near3.map(x => x.s.rec)) : null,")
rep("spread: vals.length >= 2 ? Math.max(...vals) - Math.min(...vals) : null, near3 };",
    "spread: vals.length >= 2 ? Math.max(...vals) - Math.min(...vals) : null, wide: vals.length >= 2 && (Math.max(...vals) - Math.min(...vals)) > 20, near3 };")
old_depth = "      if (gw.latest != null) add('water', { id: 'gwdepth', label: 'Groundwater depth around here (median of nearby wells)', value: `${gw.latest.toFixed(1)} m below ground (${gw.n3} wells within 3 km, range ${gw.spread != null ? gw.spread.toFixed(0) : '?'} m)`, level: gw.latest > 20 ? 'concern' : gw.latest > 8 ? 'watch' : 'good', kind: 'estimate', conf: gw.conf, source: gwSrc,"
new_depth = (
    "      if (gw.latest == null) add('water', { id: 'gwdepth', label: 'Groundwater depth around here', value: `only ${gw.n3} monitoring well${gw.n3 === 1 ? '' : 's'} within 3 km — too few for an area estimate`, level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: gwSrc, note: 'We need at least three wells within 3 km before quoting a neighbourhood value.', next: 'Use the nearest-well reading above only as a rough hint, and ask local borewell operators.' });\n"
    "      else if (gw.wide) add('water', { id: 'gwdepth', label: 'Groundwater depth around here', value: `wells nearby disagree widely: ${Math.min(...gw.near3.map(x => x.s.latest)).toFixed(0)}–${Math.max(...gw.near3.map(x => x.s.latest)).toFixed(0)} m below ground (${gw.n3} wells)`, level: 'info', kind: 'observed', conf: 'low', source: gwSrc, period: 'latest month in the data', res: 'wells within 3 km', note: 'Hard-rock aquifers vary a lot over short distances. We do not rate this location because the nearby wells do not agree.', next: 'Ask owners nearby how deep their borewells go and how often they run dry.' });\n"
    "      else add('water', { id: 'gwdepth', label: 'Groundwater depth around here (median of nearby wells)', value: `${gw.latest.toFixed(1)} m below ground (${gw.n3} wells within 3 km, range ${gw.spread != null ? gw.spread.toFixed(0) : '?'} m)`, level: gw.latest > 20 ? 'concern' : gw.latest > 8 ? 'watch' : 'good', kind: 'estimate', conf: gw.conf, source: gwSrc,")
rep(old_depth, new_depth)
rep("      if (gw.pre != null) add('water', { id: 'gwpre',", "      if (gw.pre != null && !gw.wide) add('water', { id: 'gwpre',")
rep("      if (gw.rec != null) add('water', { id: 'gwrec', label: 'Rebound after the monsoon', value: `${gw.rec >= 0 ? '+' : ''}${gw.rec.toFixed(1)} m (pre minus post, Oct–Nov)`, level: gw.rec < 1 ? 'watch' : 'good',",
    "      if (gw.rec != null && !gw.wide) add('water', { id: 'gwrec', label: 'Rebound after the monsoon', value: `${gw.rec >= 0 ? '+' : ''}${gw.rec.toFixed(1)} m (pre minus post, Oct–Nov)`, level: gw.rec > 15 ? 'info' : gw.rec < 1 ? 'watch' : 'good',")

# 2) landfill size classes
rep("    D.landfill = (C.landfill || []).map(l => ({ name: l.name, rings: l.rings, _b: l.rings.map(bbLL) }));",
    "    const ringHa = ring => { let a = 0; const k = Math.cos(rad(ring[0][0])); for (let i = 0; i < ring.length; i++) { const p = ring[i], q = ring[(i + 1) % ring.length]; a += (p[1] * k * 111320) * (q[0] * 110540) - (q[1] * k * 111320) * (p[0] * 110540); } return Math.abs(a / 2) / 1e4; };\n"
    "    D.landfill = (C.landfill || []).map(l => ({ name: l.name, rings: l.rings, _b: l.rings.map(bbLL), ha: l.rings.reduce((s, r) => s + ringHa(r), 0) }));")
rep("if (!near(l._b[i], lat, lon, .05)) return; const ins = pipLL(lat, lon, ring), d = ins ? 0 : distToPathLL(lat, lon, ring); if (!lf || d < lf.d) lf = { d, name: l.name, inside: ins }; });",
    "if (!near(l._b[i], lat, lon, .06)) return; const ins = pipLL(lat, lon, ring), d = ins ? 0 : distToPathLL(lat, lon, ring); if (!lf || d < lf.d) lf = { d, name: l.name, inside: ins, ha: l.ha }; });")
i0 = s.index("    add('infra', { id: 'landfill'")
i1 = s.index("\n", s.index("next: 'Visit on a hot afternoon with the wind blowing from the site.' });", i0))
new_lf = (
    "    const major = lf && lf.ha >= 20;   // only one listed site is large (the 92 ha Malkaram legacy dump yard); the rest are small garbage transfer points under 5 ha\n"
    "    add('infra', { id: 'landfill', label: 'Landfill / dump yard', value: lf ? `${lf.name} (${lf.ha.toFixed(lf.ha < 1 ? 1 : 0)} ha) · ${lf.inside ? 'inside' : km(lf.d)}` : 'none listed nearby', level: lf ? (major ? (lf.d <= 2000 ? 'concern' : lf.d <= 5000 ? 'watch' : 'good') : (lf.d <= 300 ? 'watch' : 'good')) : 'good', kind: 'official', conf: 'medium', source: 'Telangana open-data list of landfills and dump yards (11 sites)', period: 'undated', res: 'polygon',\n"
    "      note: major ? 'A large dump yard: odour, smoke and leachate can reach a few kilometres.' : 'A small garbage transfer or processing point; the one large dump yard in the list is further away.', next: 'Visit on a hot afternoon with the wind blowing from the site.' });")
s = s[:i0] + new_lf + s[i1:]

# 3) severity-aware section ratings
rep("      const rating = counts.concern ? 'Concern' : counts.watch ? 'Watch' : counts.good ? 'Good' : 'Unknown';",
    "      // 'Concern' needs a high-severity finding (flood, lake/encroachment, water quality or depth, hospital access, large landfill) or three ordinary concerns,\n"
    "      // so one weak amenity cannot turn a section red, and a severe flag can never be averaged away by good amenities.\n"
    "      const hi = fs.some(x => x.level === 'concern' && HIGH.has(x.id));\n"
    "      const rating = (hi || counts.concern >= 3) ? 'Concern' : (counts.concern || counts.watch) ? 'Watch' : counts.good ? 'Good' : 'Unknown';")
rep("  const KIND_LABEL = {", "  const HIGH = new Set(['sus', 'depth', 'storms', 'lake', 'nala', 'inund', 'hy', 'hmda', 'ftl', 'gwdepth', 'gwpre', 'gwtrend', 'gwf', 'gwno3', 'gwtds', 'acc_hospital', 'landfill']);\n  const KIND_LABEL = {")
open(p, "w", encoding="utf-8").write(s)
print("patched")
