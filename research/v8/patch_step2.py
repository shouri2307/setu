"""Step 2: tank survey number near the pin (HYDRAA Base_Syno + the parcel carrying that number), as a separate land finding, registry entries, plain title."""
import json
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:90]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

patch("web/platform/engine.js", [
("'quality', 'fire', 'seismic'];\n    const paths", "'quality', 'fire', 'seismic', 'tanksyn'];\n    const paths"),
("'data/fire.json', 'data/seismic.json'];", "'data/fire.json', 'data/seismic.json', 'data/tank_syn.json'];"),
("quality: null, fire: null, seismic: null };", "quality: null, fire: null, seismic: null, tanksyn: null };"),
("    const grid = g => g && g.meta ? g : null;", """    D.tankPar = D.tanksyn && D.tanksyn.par ? new Map(Object.entries(D.tanksyn.par).map(([id, ps]) => [Number(id), ps.map(p => ({ ...p, _b: p.rings.map(bbLL) }))])) : null;
    const grid = g => g && g.meta ? g : null;"""),
("  // ---------- pasted Google Maps links ----------", r"""  // ---------- tank survey number near the pin (Step 2) ----------
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

  // ---------- pasted Google Maps links ----------"""),
("    add('land', { id: 'perm', label: 'Layout and building permissions'", r"""    const tsv = tankSurveyFacts(r.lat, r.lon), TSRC = 'Telangana State GIS: HYDRAA water-body layer (tank survey number) + Bhunaksha cadastral and HYDRAA parcel outlines', TPER = 'undated (cadastral service created 2025-04-19; tank layer undated)';
    if (miss('tank_syn.json')) notRun('land', 'tank_survey', 'Tank survey number near this pin', 'tank survey-number data');
    else if (tsv && tsv.tank) {
      const tk = tsv.tank, nm = tk.name || 'an unnamed tank', dist = tk.inside ? 'this pin is on the tank outline' : km(tk.d) + ' from the tank outline', syn = tk.syn.replace(/_/g, ' and ');
      if (!tk.syn) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · the state layer records no survey number for it`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'tank outline (satellite)',
        note: 'Only about a quarter of the 1,192 tank records carry a survey number, so a missing number says nothing about the tank. It means a survey-number check is not possible from this layer.', next: 'Ask the revenue office for the tank\'s survey number and compare it with the survey number on your deed.' });
      else if (!tsv.searched) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · parcel search incomplete`, level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: TSRC, period: TPER, res: '—',
        note: 'The tank\'s survey number is recorded, but the parcel carrying it could not be looked up.', next: 'Check that survey number on Bhu Bharati.' });
      else {
        const cov = p => p.touch ? Math.round(p.cov * 100) + '% of the tank outline is inside it' : 'it does not touch the outline';
        if (tsv.pinIn) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `this pin is inside survey parcel ${tsv.pinIn.no} (${tsv.pinIn.v}), the survey number the state layer records for ${nm}${tk.inside ? '' : ' · ' + dist}`, level: tsv.pinIn.touch ? 'watch' : 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'parcel outline (~1 m) vs tank outline',
          note: `A match of survey numbers: ${cov(tsv.pinIn)}. A survey parcel is often much larger than the water, so this does not say the plot is under water, inside the legal Full Tank Level or encroached. It is a reason to check the title, not a finding about it. In a 20-lake check a parcel with the tank's number touched the outline at 14 lakes and not at 6.`, next: 'Ask for the revenue record history of this survey number and for the FTL / buffer certificate from HYDRAA or the irrigation department.' });
        else if (tsv.nearest) add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · parcel ${tsv.nearest.p.no} is ${km(tsv.nearest.d)} from the pin`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'parcel outline (~1 m) vs tank outline',
          note: `Near the tank survey parcel, not on it (${cov(tsv.nearest.p)}). This is not the legal Full Tank Level and says nothing about whether the pin is inside it.`, next: 'Ask HYDRAA or the irrigation department for the FTL / buffer certificate of this tank.' });
        else add('land', { id: 'tank_survey', label: 'Tank survey number near this pin', value: `${nm} · ${dist} · recorded survey no. ${syn} · no parcel with that number found next to the outline`, level: 'info', kind: 'official', conf: 'low', source: TSRC, period: TPER, res: 'tank outline (satellite)',
          note: 'In a 20-lake check a parcel with the tank\'s number was found next to the outline at 16 lakes and not at 4: the number may belong to another village, another numbering, or be a typing error in the layer.', next: 'Ask the revenue office which survey number the tank is recorded under.' });
      }
    }
    add('land', { id: 'perm', label: 'Layout and building permissions'"""),
("return { load, report, evidence, checklist, HIGH, fireFacts, seismicFacts,", "return { load, report, evidence, checklist, HIGH, fireFacts, seismicFacts, tankSurveyFacts,"),
])
patch("web/platform/view.js", [("    fire_gis: 'Fire station on the state list',", "    tank_survey: 'Tank survey number near this pin', fire_gis: 'Fire station on the state list',")])

p = Path("web/data/quality.json"); q = json.loads(p.read_text(encoding="utf-8"))
q["sources"]["tgrac_tank_syn"] = {"name": "Tank survey numbers and the parcels carrying them", "provider": "Telangana State GIS (TGRAC): HYDRAA water-body layer 'Base_Syno', matched to Bhunaksha_Cadastral layer 0 and Hydra_Folder/Fourth_Window layer 0", "nature": "snapshot", "obs": None, "svc": "2025-04-19", "fetched": "2026-10-25",
    "res": "tank outline (satellite) and parcel outline (~1 m)", "coverage": "313 of 1,192 tank records carry a usable survey number (26%); for 271 of those a parcel with that number was found within 150 m of the outline, and for 253 it touches the outline",
    "licence": "verify", "licence_note": "no licence text is published for these services", "validation": "internal-check",
    "validation_note": "checked at 20 lakes chosen by a fixed rule (named tanks with a survey number, evenly spaced by size): a parcel with the tank's number was found nearby at 16 and touches the outline at 14 (cadastral layer alone: 13). The two parcel layers return the same parcels at 13 lakes; the HYDRAA layer has more at 4 and fewer at 3. The village spelling differs between layers at 6 of 16, so matching uses number and position, not names. Not checked against the revenue records themselves",
    "stale_months": None, "limits": "a parcel with the tank's number is not the legal Full Tank Level and is not evidence of encroachment; the official FTL polygons could not be retrieved; most tank records have no survey number", "files": ["tank_syn.json"]}
q["factors"]["tank_survey"] = {"sec": "land", "scope": "nearby", "scope_text": "the nearest tank within 600 m and the survey parcel carrying its recorded number; a survey parcel is not a house plot", "sources": ["tgrac_tank_syn", "hydraa"], "missing": "no tank within 600 m, the tank has no recorded survey number, or the file is not loaded", "label": "Tank survey number near this pin"}
p.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")
print("step 2 patched")
