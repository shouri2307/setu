"""One-off patch: add evidence-layer tests to tests/engine.test.js (inserted before the claim-check section)."""
p = "tests/engine.test.js"
s = open(p, encoding="utf-8").read()
BLOCK = r'''
  // ---- evidence layers: data integrity, coordinate systems, units, missing values ----
  ok(D.gwSt.length >= 1000, 'groundwater stations loaded', D.gwSt.length);
  ok(D.gwSt.every(x => x.lat >= 15.5 && x.lat <= 20 && x.lon >= 77 && x.lon <= 82), 'every groundwater station has a plausible Telangana lat/lon (swapped coordinates were fixed)');
  ok(D.gwSt.every(x => x.latest != null && x.latest >= 0 && x.latest <= 120), 'groundwater depths are metres below ground, 0..120');
  const gwKey = new Set(); let gwDup = 0; for (const x of D.gwSt) { const k = x.lat.toFixed(3) + ',' + x.lon.toFixed(3); if (gwKey.has(k)) gwDup++; gwKey.add(k); }
  ok(gwDup === 0, 'no two groundwater stations share a placeholder coordinate', gwDup);
  ok(D.gwSt.filter(x => x.lat >= 17.2 && x.lat <= 17.65 && x.lon >= 78.2 && x.lon <= 78.7).length >= 80, 'at least 80 clean groundwater stations in the Hyderabad area');
  ok(D.gwSt.filter(x => x.district.toUpperCase() === 'HYDERABAD').every(x => x.lat >= 17.30 && x.lat <= 17.52 && x.lon >= 78.30 && x.lon <= 78.62), 'Hyderabad-district stations sit inside the city');
  ok(D.gwSt.every(x => x.trend == null || Math.abs(x.trend) < 15), 'groundwater trends are in a sane range (m/yr)');
  ok(D.gwSt.some(x => x.village === 'Bahadurpura' && x.latest != null), 'the shallow Bahadurpura reference well (matches the official report minimum) is present');
  ok(D.gwqS.length >= 5000 && D.gwqS.every(x => x.lat >= 15.5 && x.lat <= 20 && x.lon >= 77 && x.lon <= 82), 'groundwater-quality samples loaded with valid positions', D.gwqS.length);
  ok(D.gwqS.every(x => (x.f == null || (x.f >= 0 && x.f <= 20)) && (x.no3 == null || (x.no3 >= 0 && x.no3 <= 1500)) && (x.ph == null || (x.ph >= 3 && x.ph <= 12))), 'groundwater-quality values are physically possible (F, NO3, pH)');
  ok(D.landfill.length === 11 && D.landfill.filter(l => l.ha >= 20).length === 1, 'landfill list: 11 sites, exactly one large (the Malkaram legacy dump yard)', D.landfill.map(l => l.ha.toFixed(1)).join(','));
  ok((D.civic.power || []).reduce((a, c) => a + c[2], 0) > 3000 && (D.civic.choke || []).length >= 80 && (D.civic.rehab || []).length >= 90, 'civic layers loaded (power events, choke points, rehab centres)');
  ok(D.storm.events.length === 8 && Object.keys(D.storm.wards).length === 145, 'storm history covers 8 events x 145 wards');
  const oct20 = D.storm.events.find(e => e.id === '2020-10-13'); ok(oct20 && oct20.city_mean_mm >= 190 && oct20.city_mean_mm <= 230, 'Oct 2020 mandal rainfall averages about 190-230 mm (matches the reference storm)', oct20 && oct20.city_mean_mm);
  ok(D.heat && D.heat.lst.length === D.heat.meta.nx * D.heat.meta.ny, 'heat grid size matches its metadata');
  const hv = D.heat.lst.filter(x => x != null); ok(hv.length > 60000, 'heat grid has >60k valid cells', hv.length);
  const hm = hv[hv.length >> 1]; ok(D.heatSorted[D.heatSorted.length >> 1] / 10 > 36 && D.heatSorted[D.heatSorted.length >> 1] / 10 < 46, 'median dry-season surface temperature is 36-46 C', D.heatSorted[D.heatSorted.length >> 1] / 10);
  const hsLake = E.heatFacts(17.4235, 78.4745), hsCity = E.heatFacts(17.3616, 78.4747);
  ok(hsLake && hsCity && hsLake.lst < hsCity.lst - 5, 'physics check: Hussain Sagar water is much cooler than the old city', hsLake && hsCity && (hsLake.lst + ' vs ' + hsCity.lst));
  const kbr = E.heatFacts(17.4170, 78.4240); ok(kbr && kbr.ndvi > 0.28, 'physics check: KBR National Park is green (NDVI > 0.28)', kbr && kbr.ndvi);

  // ---- evidence report: five sections, honest fields, no NaN, severity rules ----
  const LV = new Set(['concern', 'watch', 'good', 'info', 'unknown']), KD = new Set(['observed', 'official', 'modelled', 'estimate', 'indicative', 'reference', 'unavailable']), CF = new Set(['high', 'medium', 'low', 'unavailable']);
  let evBad = 0, evN = 0, evGw = 0;
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]); if (!r.ok) continue;
    ok(r.ev && r.ev.sections.length === 5 && ['hazards', 'water', 'infra', 'live', 'land'].every((id, i) => r.ev.sections[i].id === id), `evidence has the five sections (ward ${w.id})`);
    for (const sec of r.ev.sections) {
      ok(['Concern', 'Watch', 'Good', 'Unknown'].includes(sec.rating), `section rating valid (${sec.id}, ward ${w.id})`);
      const hiConcern = sec.findings.some(f => f.level === 'concern' && ['sus', 'depth', 'storms', 'lake', 'nala', 'inund', 'hy', 'hmda', 'ftl', 'gwdepth', 'gwpre', 'gwtrend', 'gwf', 'gwno3', 'gwtds', 'acc_hospital', 'landfill'].includes(f.id));
      if (hiConcern) ok(sec.rating === 'Concern', `a high-severity concern is never averaged away (${sec.id}, ward ${w.id})`, sec.rating);
      for (const f of sec.findings) {
        evN++;
        const text = [f.label, f.value, f.note, f.next, f.source, f.period, f.res].join(' ');
        if (!LV.has(f.level) || !KD.has(f.kind) || !CF.has(f.conf) || !f.label || !f.value || /NaN|undefined|Infinity|\[object/.test(text)) { evBad++; if (evBad <= 5) fails.push(`bad evidence finding ${f.id} ward ${w.id}: ${f.level}/${f.kind}/${f.conf} ${text.slice(0, 80)}`); }
        if (['concern', 'watch', 'good'].includes(f.level) && f.conf === 'unavailable') { evBad++; fails.push(`rated finding with unavailable confidence: ${f.id} ward ${w.id}`); }
        if (f.level === 'unknown' && f.kind !== 'unavailable') { evBad++; fails.push(`unknown finding not marked unavailable: ${f.id} ward ${w.id}`); }
        if (f.id === 'gwdepth' && f.kind === 'estimate') { evGw++; const g = E.gwFacts(w.c[1], w.c[0]); if (!(g.n3 >= 3 && !g.wide)) { evBad++; fails.push(`groundwater area estimate shown with too few or disagreeing wells, ward ${w.id}`); } }
      }
    }
  }
  ok(evBad === 0, `all ${evN} evidence findings are well-formed (no NaN, valid level/kind/confidence, unknown never silently zero)`, evBad + ' bad');
  ok(evGw >= 30, 'groundwater area estimates are produced for a good share of wards (and only with >=3 agreeing wells)', evGw);
  const hs = await E.report(17.4235, 78.4745);
  ok(hs.ev.sections[0].findings.some(f => f.id === 'lake' && f.level === 'concern'), 'golden: a pin inside Hussain Sagar is a lake concern');
  ok(hs.ev.sections[4].findings.some(f => f.id === 'plot' && f.level === 'unknown' && f.kind === 'unavailable'), 'plot identity is reported as not available, never invented');
  const farGw = E.gwFacts(17.55, 78.69); ok(farGw && Number.isFinite(farGw.nearest.d) && ['medium', 'low', 'unavailable'].includes(farGw.conf), 'groundwater lookup returns a bounded confidence far from stations');
  const sparse = await E.report(17.2403, 78.4294); ok(sparse.ev.sections[1].findings.every(f => !(f.id === 'gwdepth' && f.kind === 'estimate' && E.gwFacts(17.2403, 78.4294).n3 < 3)), 'no groundwater area estimate where wells are sparse (Shamshabad)');
  ok(Rep.render('customer', { r: hs, label: '', unlocked: { customer: true, agent: true, insurer: true }, cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: null, line: 'motor', PERILS: PER, open: {} }).includes('Evidence report'), 'customer report page contains the evidence report');
'''
anchor = "  // ---- claim check logic ----"
assert anchor in s and "evidence layers" not in s
s = s.replace(anchor, BLOCK + "\n" + anchor, 1)
open(p, "w", encoding="utf-8").write(s)
print("tests added")
