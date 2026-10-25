"""Findings must never turn reassuring (or misleadingly 'concern') because their data file failed to load: they become 'unknown / data not loaded'."""
from pathlib import Path
P = Path("web/platform/engine.js"); s = P.read_text(encoding="utf-8")
def once(old, new):
    global s
    assert s.count(old) == 1, f"anchor count {s.count(old)}: {old[:70]!r}"; s = s.replace(old, new)
# record which optional files fell back
once("const res = await Promise.all(paths.map((p, i) => get(p).catch(e => {\n      if (names[i] in optional)", "D.loadFailed = [];\n    const res = await Promise.all(paths.map((p, i) => get(p).catch(e => {\n      D.loadFailed.push(p);\n      if (names[i] in optional)")
# helpers at the top of evidence()
once("    const lvlHi = (v, w, c) => v >= c ? 'concern' : v >= w ? 'watch' : 'good';\n    // ---------- HAZARDS ----------",
"""    const lvlHi = (v, w, c) => v >= c ? 'concern' : v >= w ? 'watch' : 'good';
    const miss = f => (D.loadFailed || []).includes('data/' + f);   // a data file that failed to load: its findings say so instead of reading as "nothing found"
    const notRun = (sec, id, label, srcName) => add(sec, { id, label, value: 'data not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: srcName, period: '—', res: '—', note: `The ${srcName} data could not be loaded, so this check was not run. That is not a clean result.`, next: 'Reload the page; if it persists, this demo is missing that data file.' });
    // ---------- HAZARDS ----------""")
once("    else add('hazards', { id: 'nala', label: 'Mapped nala nearby', value: 'none within 1.5 km in the GHMC layer'", "    else if (miss('gov.json')) notRun('hazards', 'nala', 'Mapped nala nearby', 'TGRAC / GHMC nala layer');\n    else add('hazards', { id: 'nala', label: 'Mapped nala nearby', value: 'none within 1.5 km in the GHMC layer'")
once("    add('hazards', { id: 'inund', label: 'Officially listed inundation area',", "    if (miss('gov.json')) notRun('hazards', 'inund', 'Officially listed inundation area', 'GHMC water-logging list');\n    else add('hazards', { id: 'inund', label: 'Officially listed inundation area',")
once("    add('infra', { id: 'choke', label: 'Traffic congestion points within 1 km',", "    if (miss('civic.json')) notRun('infra', 'choke', 'Traffic congestion points within 1 km', 'Hyderabad Traffic Police congestion list');\n    else add('infra', { id: 'choke', label: 'Traffic congestion points within 1 km',")
once("    add('infra', { id: 'landfill', label: 'Landfill / dump yard',", "    if (miss('civic.json')) notRun('infra', 'landfill', 'Landfill / dump yard', 'landfill list');\n    else add('infra', { id: 'landfill', label: 'Landfill / dump yard',")
once("    add('live', { id: 'f_jobs', label: 'Jobs and lifestyle hubs',", "    if (miss('geo.json')) notRun('live', 'f_jobs', 'Jobs and lifestyle hubs', 'OpenStreetMap places');\n    else add('live', { id: 'f_jobs', label: 'Jobs and lifestyle hubs',")
once("    else add('land', { id: 'lost', label: 'Disappeared water body', value: 'none recorded within 400 m'", "    else if (miss('land.json')) notRun('land', 'lost', 'Disappeared water body', 'TGRAC disappeared-water-body layer');\n    else add('land', { id: 'lost', label: 'Disappeared water body', value: 'none recorded within 400 m'")
# source-level gaps in ev.gaps
once("    const gaps = sections.flatMap(", "    const gapsSrc = QQ ? Object.entries(QQ.sources).filter(([, sr]) => sr.files && sr.files.length && sr.files.every(f => (D.loadFailed || []).includes('data/' + f))).map(([id, sr]) => ({ id: 'src:' + id, label: sr.name, section: 'Data sources', value: 'data not loaded', why: 'its data file could not be loaded, so every finding that rests only on it is unavailable' })) : [];\n    const gaps0 = sections.flatMap(")
once("why: (QQ && QQ.factors[f.id] && QQ.factors[f.id].missing) || f.note || 'no data' })));", "why: (QQ && QQ.factors[f.id] && QQ.factors[f.id].missing) || f.note || 'no data' })));\n    const gaps = [...gapsSrc, ...gaps0];")
P.write_text(s, encoding="utf-8"); print("guards patched")
