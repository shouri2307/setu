"""One-off patch: tests for batch 2 (rain frequency, analogs, tank capacity, stream order, checklist, map popups, routing failover)."""
p = "tests/engine.test.js"
s = open(p, encoding="utf-8").read()
BLOCK = r'''
  // ---- batch 2: exports exist (guards against a function being lost in an edit) ----
  for (const fn of ['rainFacts', 'analogFacts', 'tankFacts', 'streamFacts', 'checklist', 'roadAccess', 'evidence', 'gwFacts', 'gwqFacts', 'civicFacts', 'heatFacts'])
    ok(typeof E[fn] === 'function', `engine exports ${fn}`);

  // ---- tanks and streams: integrity, units, duplicates, coordinates ----
  const TKS = D.tankL.tanks, STR = D.tankL.streams, inBox = p => p[0] > 17 && p[0] < 18 && p[1] > 78 && p[1] < 79;
  ok(TKS.length >= 2000 && STR.length >= 1000, 'tank and stream layers loaded', TKS.length + '/' + STR.length);
  ok(TKS.every(t => t.r[0].length >= 4 && t.r[0].every(inBox)), 'tank polygons are [lat, lon] inside the study box');
  ok(new Set(TKS.map(t => t.id)).size === TKS.length, 'tank record ids are unique (no duplicated records)');
  const bbKey = new Set(); let dupBox = 0; for (const t of TKS) { const k = t._b.map(v => v.toFixed(5)).join(',') + '|' + t.a[1]; if (bbKey.has(k)) dupBox++; bbKey.add(k); }
  ok(dupBox === 0, 'no two tank records share the same outline and area', dupBox);
  ok(TKS.every(t => ['L', 'P', 'T', 'D', null].includes(t.a[4]) && ['L', 'P', 'T', 'D', null].includes(t.a[5])), 'tank status codes are valid');
  ok(TKS.filter(t => t.a[3] != null).every(t => t.a[1] > 0 && t.a[2] > 0 && Math.abs(t.a[3] - t.a[1] * t.a[2] / 2) / t.a[3] < .02), 'every stored capacity follows the source formula area x bund / 2 (units: m2, m, m3)');
  ok(TKS.filter(t => t.a[3] == null).length > 1000, 'most tanks correctly have no capacity figure (not invented)', TKS.filter(t => t.a[3] == null).length);
  ok(STR.every(x => (x.o == null || (x.o >= 2 && x.o <= 6)) && x.p.every(path => path.length >= 2 && path.every(inBox))), 'stream orders 2..6 and positions inside the box');

  // ---- tank capacity ----
  const tfHS = E.tankFacts(17.4235, 78.4745);
  ok(tfHS.nearest && tfHS.nearest.inside && Math.abs(tfHS.capM3 / 1e6 - 22.95) < 1.2 && tfHS.nCap + tfHS.nNoCap === tfHS.n2, 'Hussain Sagar pin: inside its tank record, capacity about 22.95 million m3, counts consistent', JSON.stringify([tfHS.n2, tfHS.nCap, tfHS.nNoCap, tfHS.capM3]));
  const tfNone = E.tankFacts(18.5, 79.5); ok(tfNone.n2 === 0 && tfNone.nearest === null && tfNone.capM3 === 0, 'missing-data case: no tank within 2 km gives zero counts and no nearest, not a crash');
  let tfBad = 0; for (const w of D.wards) { const t = E.tankFacts(w.c[1], w.c[0]); const ids2 = t.list.map(x => x.t.id); if (new Set(ids2).size !== ids2.length || t.nCap + t.nNoCap !== t.n2 || t.enc2023 > t.n2 || t.capM3 < 0 || Math.abs(t.capM3 - t.list.filter(x => x.t.a[3] != null).reduce((a, x) => a + x.t.a[3], 0)) > 1) tfBad++; }
  ok(tfBad === 0, 'for every ward: no tank counted twice, capacity equals the sum of listed capacities, counts consistent', tfBad);

  // ---- stream order ----
  const sfHS = E.streamFacts(17.4235, 78.4745); ok(sfHS.nearest && sfHS.nearest.o >= 2, 'Hussain Sagar vicinity has a mapped stream with an order');
  const sfNone = E.streamFacts(18.5, 79.5); ok(sfNone.nearest === null && sfNone.n300 === 0, 'missing-data case: no stream far from the network');
  const evHS = (await E.report(17.4235, 78.4745)).ev;
  const stF = evHS.sections[0].findings.find(f => f.id === 'stream'); ok(stF && /does not prove|not prove|terrain/.test(stF.note + ' ' + stF.value), 'stream finding states that stream order does not prove a buried channel');
  const tkF = evHS.sections[1].findings.find(f => f.id === 'tankstore'); ok(tkF && !/\blost\b/i.test(tkF.value + tkF.note) && /not measured|estimate/i.test(tkF.note), 'tank-storage finding never says storage is "lost" and says capacity is an estimate');

  // ---- heavy rain and analogs ----
  const RS = D.rainstats;
  ok(RS.meta.threshold_mm === 64.5 && !RS.meta.months_used.includes('2025-06') && RS.meta.months_excluded.every(m => m.coverage < 0.9) && RS.meta.months_used.length >= 8, 'rain statistics use only well-covered months and list what was excluded');
  ok(Object.values(RS.mandals).every(m => m.days_over <= m.days_obs && m.top.length <= m.days_over && (!m.top.length || m.wettest[0] >= m.top[0][1]) && m.days_obs >= 250), 'rain statistics are internally consistent (counts <= days, wettest >= top day)');
  const khai = RS.mandals['KHAIRATABAD']; ok(khai && khai.wettest[0] === 174.5 && khai.wettest[1] === '2020-10-14', 'golden: Khairatabad wettest day is 174.5 mm on 2020-10-14 (checked against the raw file)');
  ok(E.rainFacts(91) && E.rainFacts(91).days_over >= 1, 'rainFacts returns a record for a normal ward'); ok(E.rainFacts(99999) === null, 'rainFacts is null for an unknown ward');
  ok(!E.ANALOG_EVENTS.includes('2016-09') && !E.ANALOG_EVENTS.includes('2025-06-12'), 'analogs exclude the month-only 2016 date and the incomplete June 2025 rainfall month');
  let anBad = 0, anTooFew = 0; for (const w of D.wards) { const a = E.analogFacts(w.id); if (!a) continue; if (a.n > 6 || a.k > a.n || a.hit.some(x => x.mm < a.mm)) anBad++; if (a.n < 3) anTooFew++; }
  ok(anBad === 0, 'analog counts are consistent for every ward (k <= n <= 6, only storms at or above the threshold)', anBad);
  let anWording = 0; for (const w of D.wards.slice(0, 60)) { const r = await E.report(w.c[1], w.c[0]); const f = r.ev.sections[0].findings.find(x => x.id === 'analog'); const a = E.analogFacts(w.id); if (f && ((a.n < 3 && !/too few/.test(f.value)) || (a.n >= 3 && /too few/.test(f.value)) || /probab|will flood|likely to flood/i.test(f.value + f.note))) anWording++; }
  ok(anWording === 0, 'analog wording: "too few" exactly when under 3 storms, and never a probability claim', anWording);

  // ---- checklist ----
  const KNOWN = new Set(Object.keys({ plot: 1, zoning: 1, perm: 1, ftl: 1, hy: 1, hmda: 1, lost: 1, forest: 1, endow: 1, nala: 1, nalaenc: 1, widen: 1, sus: 1, depth: 1, storms: 1, inund: 1, lake: 1, pocket: 1, stream: 1, gwdepth: 1, gwpre: 1, gwtrend: 1, gwrec: 1, gwf: 1, gwno3: 1, gwtds: 1, gwq: 1, gwp: 1, supply: 1, landfill: 1, tx: 1, choke: 1, acc_hospital: 1, acc_metro: 1, heat: 1, price: 1 }));
  let ckBad = 0, ckN = 0, ckMissing = 0;
  for (const w of D.wards) {
    const r = await E.report(w.c[1], w.c[0]); const c = E.checklist(r); ckN += c.items.length;
    const keys = c.items.map(i => i.key); if (new Set(keys).size !== keys.length) { ckBad++; fails.push('duplicate checklist item ward ' + w.id); }
    ok(c.std.length === 2 && c.std.every(i => i.trigger.level === 'standard'), `two standard checks are present and labelled as such (ward ${w.id})`);
    for (const it of [...c.items, ...c.std]) {
      const miss = !it.action || !it.why || !it.where || !it.where.name || !['legal', 'flood', 'water', 'infra'].includes(it.cat);
      const lie = it.where && it.where.url && !['https://bhubharati.telangana.gov.in/', 'https://lakes.hmda.gov.in/'].includes(it.where.url);
      const unsafe = /unsafe|dangerous|illegal/i.test(it.why + it.action + it.trigger.label);
      if (miss || lie || unsafe) { ckBad++; fails.push(`bad checklist item ${it.key} ward ${w.id}: miss=${miss} unverifiedUrl=${lie} alarmist=${unsafe}`); }
    }
    // every concern / watch finding that has a template must be in the checklist, and no 'good' finding may be
    const fs = r.ev.sections.flatMap(sec => sec.findings);
    for (const f of fs) { const inC = c.items.some(i => i.trigger.id === f.id || i.key === f.id); if ((f.level === 'concern' || f.level === 'watch') && KNOWN.has(f.id) && !inC && !(f.id === 'acc_hospital' && false)) { ckMissing++; if (ckMissing < 4) fails.push(`concern/watch finding missing from checklist: ${f.id} ward ${w.id}`); } if (f.level === 'good' && c.items.some(i => i.trigger.id === f.id)) { ckBad++; fails.push(`good finding in checklist: ${f.id} ward ${w.id}`); } }
    // transient gaps (elevation or routing still loading) must never become action items
    if (c.items.some(i => ['pocket', 'acc_hospital', 'acc_metro', 'acc_bus', 'acc_school', 'acc_market', 'stream', 'heat'].includes(i.key) && i.gap)) { ckBad++; fails.push('transient gap became a checklist item ward ' + w.id); }
  }
  ok(ckBad === 0 && ckMissing === 0, `all ${ckN} checklist items are well-formed, complete for concerns/watch items, never for good findings, and never alarmist`, ckBad + ' bad, ' + ckMissing + ' missing');
  const sh = await E.report(17.2403, 78.4294); const shC = E.checklist(sh); ok(shC.items.some(i => i.key === 'lost' && i.trigger.level === 'concern') && shC.items.some(i => i.key === 'plot' && i.gap), 'golden: Shamshabad gets a disappeared-tank action and a plot-identity data-gap action');
  const healthy = await E.report(17.4170, 78.4240); ok(E.checklist(healthy).items.every(i => i.trigger.level !== 'good'), 'checklist never carries a good finding');

  // ---- map popups: every layer's popup shows source, data period, resolution and confidence; text is escaped ----
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'map.js'), 'utf8') + '\n;globalThis.MapKit = MapKit;', sandbox);
  const MK = sandbox.MapKit, need = h => ['Source', 'Data period', 'Resolution', 'Confidence'].every(k => h.includes(k));
  const sample = {
    ev_wells: D.gwSt[0], ev_gwp: { attrs: D.land.gwp_attrs[0] }, ev_hv: { line: { name: 'X <b>KV', kv: '220', len: '3' } }, ev_lost: { a: ['Tank', 1.2] }, ev_streams: { o: 3, n: 'T <i>' },
    ev_tankcap: { a: ['A & B', 10000, null, null, 'L', 'P', 'SOI Toposheet', '1940', 'Tank', 'V', 'M'] }, ev_tankhy: { name: 'N', village: 'V', s14: 'L', s23: 'TB' }, ev_heat: { lst: 41.2, ndvi: .2, pct: .5 }
  };
  for (const [k, f] of Object.entries(sample)) { const h = MK.popupFor(k, f, D); ok(h && need(h), `map popup for ${k} shows source, data period, resolution and confidence`); }
  ok(!MK.popupFor('ev_hv', sample.ev_hv, D).includes('X <b>KV') && MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('A &amp; B') && MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('not available'), 'map popups escape HTML and say "not available" when capacity is missing');
  ok(MK.popupFor('ev_tankcap', sample.ev_tankcap, D).includes('not verified encroachment') && MK.popupFor('ev_tankhy', sample.ev_tankhy, D).includes('not a legal'), 'tank popups separate a mapped outline / satellite class from verified or legal encroachment');
  ok(MK.EV_KINDS.length === 7 && MK.EV_KINDS.every(k => MK.evInfo(k, D) && MK.evInfo(k, D).note && MK.evInfo(k, D).swatch.length), 'every evidence layer has a legend with swatches and a dataset-age note');

  // ---- routing: failover between hosts, caching, and honest failure ----
  const realFetch2 = sandbox.fetch; let calls = [];
  const okTable = u => ({ ok: true, json: async () => { const n = (u.match(/destinations=([\d;]+)/) || [0, '1'])[1].split(';').length; return { code: 'Ok', durations: [Array.from({ length: n }, (_, i) => 120 + i * 30)], distances: [Array.from({ length: n }, (_, i) => 1500 + i * 400)] }; } });
  sandbox.fetch = u => { calls.push(u); return /router\.project-osrm\.org/.test(u) ? Promise.reject(new Error('down')) : Promise.resolve(okTable(u)); };
  const acc1 = await E.roadAccess(17.4101, 78.4101); ok(acc1 && acc1.hospital && acc1.hospital.host === 'routing.openstreetmap.de' && calls.length === 2, 'routing fails over to the second host when the first is down');
  const nCalls = calls.length; const acc2 = await E.roadAccess(17.4101, 78.4101); ok(calls.length === nCalls && acc2 === acc1, 'routing result is cached for repeat lookups');
  sandbox.fetch = () => Promise.resolve({ ok: false, status: 503, json: async () => ({}) }); const acc3 = await E.roadAccess(17.4301, 78.4301); ok(acc3 === null, 'both routing hosts down returns null (the report then says unavailable, no invented time)');
  sandbox.fetch = () => Promise.resolve({ ok: true, json: async () => ({ code: 'NoRoute' }) }); ok(await E.roadAccess(17.4501, 78.4501) === null, 'a routing error code returns null');
  sandbox.fetch = realFetch2;
  const noAcc = await E.report(17.4601, 78.4601); ok(noAcc.ev.sections[2].findings.filter(f => f.id.startsWith('acc_')).every(f => f.level === 'unknown' && f.kind === 'unavailable'), 'without routing data, road-travel findings are unknown/unavailable, never a made-up time');
  ok(Rep.render('customer', { r: noAcc, label: '', unlocked: { customer: true, agent: true, insurer: true }, cust: { price: '', area: '', brokerage: '' }, agent: {}, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false }, ai: { q: '', a: '', think: false }, fc: null, air: null, line: 'motor', PERILS: PER, open: {} }).includes('Due-diligence checklist'), 'customer report page contains the due-diligence checklist');
'''
anchor = "  // ---- claim check logic ----"
assert anchor in s and "batch 2: exports exist" not in s
s = s.replace(anchor, BLOCK + "\n" + anchor, 1)
open(p, "w", encoding="utf-8").write(s)
print("batch-2 tests added")
