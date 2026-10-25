"""Step 1: fire stations (state list) and seismic zone (state layer) as separate evidence findings, registry entries, plain titles."""
import json
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:90]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

patch("web/platform/engine.js", [
("'plan', 'prohib', 'network', 'parcelIdx', 'quality'];\n    const paths", "'plan', 'prohib', 'network', 'parcelIdx', 'quality', 'fire', 'seismic'];\n    const paths"),
("'data/parcels/index.json', 'data/quality.json'];", "'data/parcels/index.json', 'data/quality.json', 'data/fire.json', 'data/seismic.json'];"),
("network: null, parcelIdx: null, quality: null };", "network: null, parcelIdx: null, quality: null, fire: null, seismic: null };"),
("    const grid = g => g && g.meta ? g : null;", """    D.fireL = D.fire && D.fire.stations ? D.fire.stations.map(s => ({ lat: s[0], lon: s[1], name: s[2], district: s[3], status: s[4], remark: s[5], id: s[6] })) : null;
    D.seismicL = D.seismic && D.seismic.zones ? D.seismic.zones.map(z => ({ ...z, _b: z.rings.map(bbLL) })) : null;
    const grid = g => g && g.meta ? g : null;"""),
("  // ---------- pasted Google Maps links ----------", r"""  // ---------- state fire-station list and state seismic layer (Step 1) ----------
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

  // ---------- pasted Google Maps links ----------"""),
# seismic: separate finding; the old reference line says so when the state layer disagrees
("    add('hazards', { id: 'seismic', label: 'Earthquake zone', value: 'Zone II (low hazard) under IS 1893 (Part 1):2016, per secondary sources — reference only',",
 "    const szG = seismicFacts(r.lat, r.lon), szConflict = szG && szG.zone && szG.zone !== 'Zone II';\n    add('hazards', { id: 'seismic', label: 'Earthquake zone', value: szConflict ? `Zone II is the usual reference for Hyderabad city, but the state GIS layer puts this spot in ${szG.zone}: the two sources disagree here (see the next finding)` : 'Zone II (low hazard) under IS 1893 (Part 1):2016, per secondary sources — reference only',"),
("    const cv = civicFacts(r.lat, r.lon);\n    add('hazards', { id: 'shelter'", r"""    if (miss('seismic.json')) notRun('hazards', 'seismic_gis', 'Earthquake zone (state GIS layer)', 'state seismic-zone layer');
    else if (!szG || !szG.zone) add('hazards', { id: 'seismic_gis', label: 'Earthquake zone (state GIS layer)', value: 'outside the zones mapped in the state layer', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) seismic-zone layer', period: '—', res: '—', note: 'No zone could be read for this location.', next: 'Check the seismic zone for the exact location in IS 1893.' });
    else {
      const nearB = szG.other && szG.other.d <= 2000;
      add('hazards', { id: 'seismic_gis', label: 'Earthquake zone (state GIS layer)', value: `${szG.zone} · ${szG.intensity || 'intensity not stated'}${szG.other && szG.other.d <= 5000 ? ` · ${(szG.other.d / 1000).toFixed(1)} km from the ${szG.other.zone} boundary` : ''}`, level: 'info', kind: 'official', conf: nearB ? 'low' : 'medium',
        source: 'Telangana State GIS (TCUR) seismic-zone layer, 3 polygons', period: 'undated (service document created 2025-05-24); the edition of the zoning behind it is not published', res: 'regional zone polygon (~50 m simplification)',
        note: 'A regional hazard zone. It says nothing about whether a particular building is structurally safe: that depends on how and when it was built and needs an engineer. ' + (nearB ? `This spot is close to the ${szG.other.zone} boundary and zone maps are coarse, so treat the zone as approximate. ` : '') + 'It agrees with the Zone II reference for the whole city except where noted above; neither source is the BIS standard itself.', next: 'Ask for the building\'s structural design certificate and, for an older building, a structural audit by a licensed engineer.' });
    }
    const cv = civicFacts(r.lat, r.lon);
    add('hazards', { id: 'shelter'"""),
# fire: state list, separate from the OSM-based finding
("    const nz = cv.noise;", r"""    const ff = fireFacts(r.lat, r.lon);
    if (miss('fire.json')) notRun('infra', 'fire_gis', 'Fire station on the state list', 'state fire-station list');
    else if (!ff || !ff.nearest || ff.nearest.d > 10000) add('infra', { id: 'fire_gis', label: 'Fire station on the state list', value: 'no station listed as Existing within 10 km', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) fire-station list', period: '—', res: '—',
      note: `The state list holds only ${ff ? ff.nExisting : 'a few'} Existing stations for the whole region, so this does not mean none is near. See the OpenStreetMap-based fire-station finding under Everyday life.`, next: 'Ask the local fire station or the municipality which station covers the address.' });
    else add('infra', { id: 'fire_gis', label: 'Fire station on the state list', value: `${ff.nearest.s.name || 'unnamed'} · ${km(ff.nearest.d)} · listed as Existing (source remark: ${ff.nearest.s.remark || 'none'})${ff.proposed3.length ? ` · ${ff.proposed3.length} more listed as Proposed within 3 km (not operating)` : ''}`,
      level: 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS (TCUR) fire-station list: ' + ff.nExisting + ' Existing and ' + ff.nProposed + ' Proposed records', period: 'undated (service document created 2025-05-24)', res: 'point; positional accuracy not published',
      note: `Status and remark are the source's own words. Of ${ff.nExisting} Existing stations, ${ff.nMoved} carry the remark "Moved" and ${ff.nInaccurate} "not found accurate" (the list does not explain these), and only ${ff.nCorrect} says "Correct", so positions are uncertain. Checked against OpenStreetMap at 10 places the nearest station agreed at 4; OpenStreetMap maps only 10 stations here, so it cannot confirm the rest. This is a straight-line distance to a listed point, not a response time, and it does not confirm that any station is operating.`,
      next: 'Ask the nearest fire station or the municipality for the response area of the station that covers this address.' });
    const nz = cv.noise;"""),
("return { load, report, evidence, checklist, HIGH, parseMapsLink,", "return { load, report, evidence, checklist, HIGH, fireFacts, seismicFacts, parseMapsLink,"),
])

patch("web/platform/view.js", [
("    lost: 'Built where a lake used to be?',", "    fire_gis: 'Fire station on the state list', seismic_gis: 'Earthquake zone on the state map',\n    lost: 'Built where a lake used to be?',"),
])

# ---- registry ----
p = Path("web/data/quality.json"); q = json.loads(p.read_text(encoding="utf-8"))
q["sources"]["tgrac_fire"] = {"name": "State fire-station list", "provider": "Telangana State GIS (TGRAC) TCUR layer 61 'Fire Stations'", "nature": "snapshot", "obs": None, "svc": "2025-05-24", "fetched": "2026-10-25", "res": "point (positional accuracy not published)", "coverage": "71 records for the Hyderabad metro districts: 32 Existing and 39 Proposed", "licence": "verify", "licence_note": "no licence text is published for this service", "validation": "unvalidated",
    "validation_note": "compared with OpenStreetMap at 10 places: the nearest Existing station matched at 4; OSM maps only 10 stations in the area so it cannot confirm the rest; 6 of the 8 OSM stations inside the study box sit on a listed station, 2 do not; the source's remarks (Moved, not found accurate) did not separate matching from non-matching stations", "stale_months": None, "limits": "status and remark are the source's words and are not explained; Proposed and Moved are never treated as confirmed; distances are straight-line and do not confirm a station operates", "files": ["fire.json"]}
q["sources"]["tgrac_seismic"] = {"name": "State seismic-zone layer", "provider": "Telangana State GIS (TGRAC) TCUR layer 90 'Sesismic Zones'", "nature": "snapshot", "obs": None, "svc": "2025-05-24", "fetched": "2026-10-25", "res": "regional zone polygon (~50 m simplification)", "coverage": "3 polygons: Zone II (two areas) and Zone III; the whole Hyderabad study box is Zone II and Zone III begins about 450 m east of it", "licence": "verify", "licence_note": "no licence text is published for this service", "validation": "internal-check",
    "validation_note": "agrees with the Zone II reference at all 1,353 grid points of the study box and at the 14 test places; the edition of the zoning behind the layer is not published and neither source is the BIS standard itself", "stale_months": None, "limits": "a regional hazard zone; says nothing about the structural safety of a building", "files": ["seismic.json"]}
q["sources"]["seismic_ref"]["validation_note"] = "not checked against the BIS standard itself; a newer edition may change zones. The state GIS seismic layer (separate finding) puts the whole study box in Zone II, which agrees, but its own zoning edition is not published"
q["factors"]["fire_gis"] = {"sec": "infra", "scope": "nearby", "scope_text": "listed points within 10 km; straight line, not response time", "sources": ["tgrac_fire"], "missing": "no station listed as Existing within 10 km, or the list is not loaded", "label": "Fire station on the state list"}
q["factors"]["seismic_gis"] = {"sec": "hazards", "scope": "area", "scope_text": "the regional zone polygon the pin is in, not a building", "sources": ["tgrac_seismic"], "missing": "outside the zones mapped in the state layer, or the layer is not loaded", "label": "Earthquake zone (state GIS layer)"}
p.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")
print("step 1 patched")
