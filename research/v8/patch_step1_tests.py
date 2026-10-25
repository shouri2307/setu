"""Step 1: correct the seismic coverage text and add the Step 1 tests."""
import json
from pathlib import Path
p = Path("web/data/quality.json"); q = json.loads(p.read_text(encoding="utf-8"))
q["sources"]["tgrac_seismic"]["coverage"] = "3 polygons: Zone II (two areas) and Zone III. The whole Hyderabad map region (17.20-17.66 N, 78.18-78.70 E, 2,392 grid points) is Zone II; the nearest Zone III boundary is at least 102 km away"
q["sources"]["tgrac_seismic"]["validation_note"] = "agrees with the Zone II reference at all 2,392 grid points of the map region and at the 14 test places; the edition of the zoning behind the layer is not published and neither source is the BIS standard itself"
p.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")

t = Path("tests/engine.test.js"); s = t.read_text(encoding="utf-8"); anchor = "  // ---- live APIs (optional) ----"; assert s.count(anchor) == 1
blk = r"""  // ---- Step 1: state fire-station list and state seismic layer ----
  {
    const fj = rd('data/fire.json'), st = fj.stations, sj = rd('data/seismic.json');
    ok(st.length === 71 && fj.meta.records === 71, 'all 71 fire-station records are kept');
    ok(st.every(x => x[4] === 'Existing' || x[4] === 'Proposed') && st.filter(x => x[4] === 'Existing').length === 32 && st.filter(x => x[4] === 'Proposed').length === 39, "the source's own status is preserved exactly (32 Existing, 39 Proposed)");
    const rem = {}; for (const x of st) rem[x[5]] = (rem[x[5]] || 0) + 1;
    ok(rem['Moved'] === 24 && rem['Correct'] === 1 && rem['Kept same not found accurate'] === 6 && rem['Moved not found accurate'] === 1 && rem['Proposed'] === 39, "the source's remarks are preserved verbatim (Moved 24, Correct 1, not found accurate 7, Proposed 39)");
    ok(st.every(x => x[0] > 16.9 && x[0] < 17.9 && x[1] > 78 && x[1] < 79.1), 'every fire record sits inside the Hyderabad region (no swapped or missing coordinates)');
    ok(/never treated as confirmed/.test(fj.meta.note) && /never treated as confirmed/.test(Q.sources.tgrac_fire.limits), 'the data file and the registry both state that Proposed and Moved records are never treated as confirmed');
    const pr = st.find(x => x[4] === 'Proposed'), ff = E.fireFacts(pr[0], pr[1]);
    ok(ff.nearest && ff.nearest.s.status === 'Existing' && ff.proposed3.every(x => x.s.status === 'Proposed'), 'standing on a Proposed site, the nearest station is still an Existing one and the Proposed site is listed separately');
    let badFire = 0, nInfo = 0, nUnk = 0;
    for (const r of reports) {
      const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'fire_gis'); if (!f) { badFire++; continue; }
      if (!['info', 'unknown'].includes(f.level) || (f.kind === 'official' && f.conf !== 'low') || /operating|operational|response time (of|is)|within \d+ minutes/i.test(f.value.replace(/\(not operating\)/g, '')) || (f.level === 'info' && !/does not confirm that any station is operating/.test(f.note)) || (f.level === 'info' && !/listed as Existing/.test(f.value))) badFire++;
      if (f.level === 'info') nInfo++; else nUnk++;
    }
    ok(badFire === 0 && nInfo > 50 && nUnk >= 1, 'the fire finding is only ever information or unknown, low confidence, says "listed as Existing", and never claims a station operates', `${badFire} bad, ${nInfo} info, ${nUnk} unknown`);
    ok(reports.every(r => { const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'fire_gis'); return f.level !== 'info' || !/^[^·]*· [^·]* · listed as Proposed/.test(f.value); }), 'the headline station is never a Proposed one');
    ok(sj.zones.length === 3 && sj.zones.map(z => z.zone).sort().join() === 'Zone II,Zone II,Zone III', 'all three seismic polygons are kept (two Zone II areas, one Zone III)');
    let zn = 0, zo = 0, badSz = 0;
    for (let la = 17.20; la <= 17.66; la += .02) for (let lo = 78.18; lo <= 78.70; lo += .02) { const z = E.seismicFacts(la, lo); zn++; if (z && z.zone === 'Zone II') zo++; }
    ok(zo === zn, 'the whole map region reads as Zone II in the state layer, agreeing with the reference', `${zo} of ${zn}`);
    for (const r of reports) {
      const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic_gis');
      if (!f || f.level !== 'info' || f.kind !== 'official' || /\b(safe|safety rating|earthquake[- ]proof|resistant)\b/i.test(f.value) || !/nothing about whether a particular building is structurally safe/.test(f.note) || f.scope !== 'area') badSz++;
    }
    ok(badSz === 0, 'the seismic finding is information only, never a safety claim, and says it cannot speak for a building', badSz);
    const refF = reports[0].ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic');
    ok(/Zone II/.test(refF.value) && !/disagree/.test(refF.value), 'where the sources agree the reference line is unchanged');
    const saved = D.seismicL;   // conflicting sources: pretend the state layer says Zone III here
    D.seismicL = [{ zone: 'Zone III', intensity: 'Moderate Risk Zone intensity VII', rings: [[[17.3, 78.3], [17.3, 78.6], [17.6, 78.6], [17.6, 78.3], [17.3, 78.3]]], _b: [[17.3, 78.3, 17.6, 78.6]] }];
    const rc = await E.report(17.4401, 78.3489), fc = rc.ev.sections.flatMap(s => s.findings), s1 = fc.find(x => x.id === 'seismic'), s2 = fc.find(x => x.id === 'seismic_gis');
    ok(/disagree/.test(s1.value) && /Zone III/.test(s1.value) && /Zone III/.test(s2.value), 'if the state layer disagrees with the Zone II reference, the report says the sources disagree and shows both');
    D.seismicL = [{ zone: 'Zone II', intensity: 'x', rings: [[[17.3, 78.3], [17.3, 78.6], [17.6, 78.6], [17.6, 78.3], [17.3, 78.3]]], _b: [[17.3, 78.3, 17.6, 78.6]] },
      { zone: 'Zone III', intensity: 'y', rings: [[[17.3, 78.6], [17.3, 78.7], [17.6, 78.7], [17.6, 78.6], [17.3, 78.6]]], _b: [[17.3, 78.6, 17.6, 78.7]] }];
    const rb = await E.report(17.45, 78.598), sb2 = rb.ev.sections.flatMap(s => s.findings).find(x => x.id === 'seismic_gis');
    ok(sb2.conf === 'low' && /boundary/.test(sb2.value) && /approximate/.test(sb2.note), 'close to a zone boundary the finding drops to low confidence and says the zone is approximate');
    D.seismicL = saved;
    ok(Q.sources.tgrac_fire.licence === 'verify' && Q.sources.tgrac_seismic.licence === 'verify' && /no licence text/.test(Q.sources.tgrac_fire.licence_note) && /no licence text/.test(Q.sources.tgrac_seismic.licence_note), 'both new sources are registered with licence unverified');
    ok(E.removalImpact('tgrac_fire').becomeUnknown.includes('fire_gis') && E.removalImpact('tgrac_seismic').becomeUnknown.includes('seismic_gis'), 'removing either source makes its finding unknown in the dashboard impact view');
    const E2 = await freshEngine(['fire.json', 'seismic.json']), r2 = await E2.report(17.4401, 78.3489), g2 = r2.ev.sections.flatMap(s => s.findings);
    ok(['fire_gis', 'seismic_gis'].every(id => { const f = g2.find(x => x.id === id); return f && f.level === 'unknown' && /not loaded/.test(f.value); }), 'with either file missing, the finding reads "data not loaded", never a reassuring result');
  }
"""
s = s.replace(anchor, blk + anchor); t.write_text(s, encoding="utf-8"); print("ok")
