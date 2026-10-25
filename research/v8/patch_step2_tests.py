"""Step 2: add the tank-survey tests to tests/engine.test.js (before the optional live-API block)."""
from pathlib import Path
t = Path("tests/engine.test.js"); s = t.read_text(encoding="utf-8"); anchor = "  // ---- live APIs (optional) ----"; assert s.count(anchor) == 1
blk = r"""  // ---- Step 2: tank survey numbers and the parcels carrying them ----
  {
    const rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8')), Q = D.quality;
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };
    const hyj = rd('data/hydraa_tanks.json'), tsj = rd('data/tank_syn.json'), TK = hyj.tanks, withSyn = TK.filter(x => x.syn);
    ok(TK.length === 1192 && tsj.meta.tanks_total === 1192 && withSyn.length === 313 && tsj.meta.tanks_with_survey_number === 313, 'all 1,192 tank records are kept and 313 carry a usable survey number');
    ok(TK.every(x => !x.syn || x.syn.split('_').every(n => /^\d+(\/\d+)?$/.test(n) && Number(n.split('/')[0]) < 10000)), 'placeholder survey numbers (88805, 99905, "Not Visible") are never kept as survey numbers');
    ok(new Set(TK.map(x => x.id)).size === TK.length, 'tank ids are unique');
    const ids = Object.keys(tsj.par), byId = new Map(TK.map(x => [String(x.id), x]));
    ok(ids.length === tsj.meta.queried_ok && ids.every(i => byId.get(i) && byId.get(i).syn), 'parcels are stored only for tanks that record a survey number');
    ok(ids.every(i => tsj.par[i].every(p => { const bases = byId.get(i).syn.split('_').map(n => n.split('/')[0]); return bases.includes(String(p.no).split('/')[0].toUpperCase()) && p.rings.length && Object.keys(p).every(k => ['no', 'v', 'src', 'touch', 'cov', 'rings'].includes(k)); })), 'every stored parcel carries the tank\'s own survey number and only survey-record fields (no owner or personal data)');
    ok(tsj.meta.with_matching_parcel === ids.filter(i => tsj.par[i].length).length && tsj.meta.touching_outline === ids.filter(i => tsj.par[i].some(p => p.touch)).length && tsj.meta.failed === 0, 'the counts in the file header match the file');
    ok(/not the legal Full Tank Level/.test(tsj.meta.note) || /not the legal Full Tank Level/.test(Q.sources.tgrac_tank_syn.limits), 'the data file or the registry says a numbered parcel is not the legal Full Tank Level');
    // findings over many positions
    const pts = []; const num = TK.filter(x => x.syn && (tsj.par[x.id] || []).length);
    for (const x of num.slice(0, 60)) { const rg = x.rings[0]; pts.push([rg[0][0] + .0006, rg[0][1], 'near-outline']); const tp = (tsj.par[x.id] || []).find(p => p.touch); if (tp) { const c = tp.rings[0].reduce((a, q) => [a[0] + q[0] / tp.rings[0].length, a[1] + q[1] / tp.rings[0].length], [0, 0]); pts.push([c[0], c[1], 'parcel-centre', x, tp]); } }
    for (const x of TK.filter(y => !y.syn && y.name).slice(0, 15)) pts.push([x.rings[0][0][0] + .0004, x.rings[0][0][1], 'no-number']);
    let nF = 0, bad = 0, nWatch = 0, nIn = 0, nNone = 0;
    for (const [la, lo, kind, x, tp] of pts) {
      const r = await E.report(la, lo); if (!r.ok) continue;
      const fl = r.ev.sections.flatMap(z => z.findings), f = fl.find(z => z.id === 'tank_survey'), tf = E.tankSurveyFacts(la, lo);
      if (!f) { if (tf && tf.tank) bad++; else nNone++; continue; }
      nF++;
      if (!['info', 'watch', 'unknown'].includes(f.level) || !['official', 'unavailable'].includes(f.kind) || !['low', 'unavailable'].includes(f.conf) || f.sec !== 'land') bad++;
      if (/\b(inside|within|in) the (legal )?(FTL|full tank level)|encroach|illegal|unauthori[sz]ed|safe to buy|clear(ed|ance)? (title|to buy)/i.test(f.value)) bad++;
      if (f.level === 'info' && !/legal Full Tank Level|records no survey number|no parcel with that number|parcel search/.test(f.note + ' ' + f.value) ) bad++;
      if (f.level === 'watch') { nWatch++; if (!/not the legal|legal Full Tank Level/.test(f.note) || !/inside survey parcel/.test(f.value)) bad++; }
      if (kind === 'parcel-centre') { if (/^this pin is inside survey parcel/.test(f.value)) nIn++; }
      if (kind === 'no-number' && f.level === 'info' && !/records no survey number/.test(f.value)) bad++;
    }
    ok(nF > 40 && bad === 0, 'the tank-survey finding is only info, watch or unknown, always low confidence, in the land section, and never says legal FTL, encroachment or safe to buy', `${nF} findings, ${bad} bad`);
    ok(nIn > 20, 'standing in the middle of a parcel that carries a tank\'s number says so', `${nIn} of ${pts.filter(p => p[2] === 'parcel-centre').length}`);
    ok(nWatch > 0, 'being inside such a parcel close to the tank is raised as something to check, not hidden');
    ok(pts.filter(p => p[2] === 'no-number').length > 5, 'tanks with no recorded number were tested');
    // a tank with a number but no completed parcel search must read as unknown, never "none found"
    const tnum = num[0], saveP = D.tankPar.get(tnum.id); D.tankPar.delete(tnum.id);
    const ru = await E.report(tnum.rings[0][0][0] + .0006, tnum.rings[0][0][1]), fu = ru.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey');
    ok(fu && (fu.level === 'unknown' || !/no parcel with that number/.test(fu.value)), 'a tank whose parcel search did not complete reads as unknown or is not described as "none found"', fu && fu.value);
    D.tankPar.set(tnum.id, saveP);
    const rFar = await E.report(17.2403, 78.4294); const fFar = rFar.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey'), tfFar = E.tankSurveyFacts(17.2403, 78.4294);
    ok(!!fFar === !!(tfFar && tfFar.tank), 'a finding appears only when a tank is within 600 m: absence is never reported as a clean result');
    ok(Q.sources.tgrac_tank_syn.licence === 'verify' && /no licence text/.test(Q.sources.tgrac_tank_syn.licence_note) && /not the legal Full Tank Level/.test(Q.sources.tgrac_tank_syn.limits), 'the source is registered with licence unverified and the not-FTL limit stated');
    ok(Q.sources.tgrac_tank_syn.validation === 'internal-check' && /20 lakes/.test(Q.sources.tgrac_tank_syn.validation_note) && /not checked against the revenue records/i.test(Q.sources.tgrac_tank_syn.validation_note), 'the registry states the 20-lake check and what was not checked');
    ok(E.removalImpact('tgrac_tank_syn').becomeUnknown.includes('tank_survey'), 'removing the source makes its finding unknown in the dashboard impact view');
    const E2 = await freshEngine(['tank_syn.json']), r2 = await E2.report(tnum.rings[0][0][0] + .0006, tnum.rings[0][0][1]), g2 = r2.ev.sections.flatMap(z => z.findings).find(z => z.id === 'tank_survey');
    ok(g2 && g2.level === 'unknown' && /not loaded/.test(g2.value), 'with the tank-survey file missing, the finding reads "data not loaded", never a reassuring result');
  }
"""
s = s.replace(anchor, blk + anchor); t.write_text(s, encoding="utf-8"); print("ok")
