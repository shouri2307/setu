"""One-off patch: live road routing (OSRM table API) for hospital / metro / bus / school / market, plus its use in the evidence report and app."""
p = "web/platform/engine.js"
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert old in s, "missing: " + old[:90]
    s = s.replace(old, new, 1)

# 1) the live routing function, placed after accessFacts
rep("  const SECTIONS = [",
r'''  // Live road routing: one OSRM "table" request returns drive time and distance from the pin to the nearest few facilities of each kind.
  // OSRM runs on OpenStreetMap roads including residential streets, with typical car speeds and no live traffic. Public demo server: fine for a demo only.
  async function roadAccess(lat, lon) {
    const cats = ['hospital', 'metro', 'bus', 'school', 'market'], cand = [];
    for (const k of cats) for (const n of nearest(k, lat, lon, 3)) cand.push({ k, ...n });
    if (!cand.length) return null;
    const coords = [[lon, lat], ...cand.map(c => [c.lon, c.lat])].map(c => c[0].toFixed(5) + ',' + c[1].toFixed(5)).join(';');
    const u = `https://router.project-osrm.org/table/v1/driving/${coords}?sources=0&destinations=${cand.map((_, i) => i + 1).join(';')}&annotations=duration,distance`;
    const c = new AbortController(), t = setTimeout(() => c.abort(), 9000);
    try {
      const j = await fetch(u, { signal: c.signal }).then(r => r.json()); clearTimeout(t);
      if (j.code !== 'Ok') return null;
      const out = {};
      cand.forEach((cd, i) => {
        const dur = j.durations && j.durations[0][i], dist = j.distances && j.distances[0][i];
        if (dur == null || dist == null) return;
        if (!out[cd.k] || dur < out[cd.k].min * 60) out[cd.k] = { road_m: Math.round(dist), min: dur / 60, name: cd.name, straight: cd.d, src: 'osrm' };
      });
      return Object.keys(out).length ? out : null;
    } catch (e) { clearTimeout(t); return null; }
  }

  const SECTIONS = [''')

# 2) evidence: prefer live routing, then the offline grid
rep("    const ac = accessFacts(r.lat, r.lon);", "    const ac = r.access || accessFacts(r.lat, r.lon);")
rep("""      const a = ac && ac[k], sl = r.fac[fk] && r.fac[fk].nearest ? r.fac[fk].nearest.d : null;
      if (!a) { add('infra', { id: 'acc_' + k, label: `${lab}: road travel`, value: 'not computed for this location', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'OpenStreetMap road network', note: ac ? 'No road within ~400 m of this point in the routing grid.' : 'The road-access grid is not loaded.', next: '' }); continue; }""",
"""      const a = ac && ac[k], sl = r.fac[fk] && r.fac[fk].nearest ? r.fac[fk].nearest.d : null;
      if (!a) { add('infra', { id: 'acc_' + k, label: `${lab}: road travel`, value: ac ? 'no route found' : 'routing lookup pending or unavailable', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'OSRM routing on OpenStreetMap roads', note: ac ? 'No drivable route was returned for this facility.' : 'The live routing service has not answered (it needs a network connection).', next: 'Check the route on any maps app.' }); continue; }""")
rep("""kind: 'estimate', conf: 'low', source: 'OpenStreetMap drivable roads, shortest path to the nearest mapped ' + lab.toLowerCase(), period: 'road network Oct 2026', res: '~200 m grid',
        note: 'Estimated at typical urban speeds with no traffic or one-way rules, so real times, especially at peak hours or in an emergency, will differ.', next: 'Drive it at 9 am and 6 pm once.' });""",
"""kind: 'estimate', conf: a.src === 'osrm' ? 'medium' : 'low', source: a.src === 'osrm' ? `OSRM routing on OpenStreetMap roads (public demo server) to ${a.name || 'the nearest ' + lab.toLowerCase()}` : 'OpenStreetMap main/collector roads, shortest path to the nearest mapped ' + lab.toLowerCase(), period: 'live lookup, road network as of now', res: a.src === 'osrm' ? 'street network' : '~220 m grid',
        note: 'Driving time at typical car speeds with no live traffic, so peak-hour and emergency times will differ. Compared with the straight-line distance it shows how winding the access is.', next: 'Drive it at 9 am and 6 pm once.' });""")
rep("return { load, report, evidence, gwFacts,", "return { load, report, evidence, roadAccess, gwFacts,")
open(p, "w", encoding="utf-8").write(s)

a = "web/platform/app.js"
t = open(a, encoding="utf-8").read()
old = "  SETUE.forecast(lat, lon).then(f => { if (seq !== S.seq) return; S.fc = f; refresh(); }).catch(() => { });"
assert old in t
new = old + "\n  SETUE.roadAccess(lat, lon).then(ac => { if (seq !== S.seq) return; S.access = ac; if (S.r && ac) { S.r.access = ac; SETUE.reanalyse(S.r); } refresh(); }).catch(() => { });"
t = t.replace(old, new, 1)
old = "S.label = label || ''; S.gp = null; S.fc = null; S.air = null; S.terrain = null;"
assert old in t
t = t.replace(old, "S.label = label || ''; S.gp = null; S.fc = null; S.air = null; S.terrain = null; S.access = null;", 1)
old = "r2.terrain = S.terrain; r2.air = S.air; SETUE.reanalyse(r2);"
assert old in t
t = t.replace(old, "r2.terrain = S.terrain; r2.air = S.air; r2.access = S.access; SETUE.reanalyse(r2);", 1)
open(a, "w", encoding="utf-8").write(t)
print("patched engine + app")
