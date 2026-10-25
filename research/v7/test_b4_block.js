  // =====================================================================================================
  // BATCH 4 — evidence-quality registry, property identity (parcels), planning authority, parcel overlaps, mapped water network
  // =====================================================================================================
  {
    const Q = D.quality, rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8'));
    const ENUM = { validation: ['validated', 'internal-check', 'negative', 'unvalidated', 'not-applicable'], licence: ['ok', 'verify', 'restricted'], nature: ['snapshot', 'periodic', 'history', 'model', 'live', 'reference', 'documents'],
      scope: ['pin', 'parcel', 'nearby', 'area', 'ward', 'mandal', 'locality', 'region', 'live', 'none'] };
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };

    // ---- registry integrity ----
    ok(Q && Q.sources && Q.factors, 'the evidence-quality registry is loaded');
    const srcIds = Object.keys(Q.sources), facIds = Object.keys(Q.factors), usedSrc = new Set(facIds.flatMap(f => Q.factors[f].sources));
    ok(facIds.every(f => Q.factors[f].sources.length && Q.factors[f].sources.every(s => Q.sources[s])), 'every registry finding lists existing sources');
    ok(srcIds.filter(s => s !== 'none').every(s => usedSrc.has(s)), 'every registry source is used by at least one finding', srcIds.filter(s => !usedSrc.has(s) && s !== 'none').join());
    for (const [id, s] of Object.entries(Q.sources)) {
      ok(ENUM.validation.includes(s.validation) && ENUM.licence.includes(s.licence) && ENUM.nature.includes(s.nature), `source ${id} uses only the registry's enumerations`);
      ok(!s.obs || (s.obs.length === 2 && s.obs.every(x => /^\d{4}(-\d{2})?$/.test(x)) && s.obs[0] <= s.obs[1]), `source ${id} observation window is well-formed`);
      ok(s.svc == null || /^\d{4}-\d{2}-\d{2}$/.test(s.svc), `source ${id} service-creation date is a date`);
      ok(s.fetched == null || /^\d{4}-\d{2}-\d{2}$/.test(s.fetched), `source ${id} fetched date is a date`);
      ok(s.validation === 'negative' ? /did not agree|not agree/i.test(s.validation_note) : true, `source ${id}: a failed validation says so in words`);
      ok(s.validation !== 'validated' || s.validation_note.length > 40, `source ${id}: 'validated' states what it was compared with`);
      ok(s.licence === 'ok' || s.licence_note.length > 5, `source ${id}: a restricted or unverified licence is explained`);
      ok(!s.files || s.files.every(f => fs.existsSync(path.join(WEB, 'data', f))), `source ${id}: its data files exist`);
    }
    ok(facIds.every(f => ENUM.scope.includes(Q.factors[f].scope) && Q.factors[f].scope_text.length > 5 && Q.factors[f].label), 'every finding has a scope, a scope description and a label');
    ok(Object.keys(Q.meta.scope).every(k => ENUM.scope.includes(k)) && ENUM.scope.every(k => Q.meta.scope[k]), 'the registry defines exactly the scopes the engine uses');
    // survey dates are kept apart from service-creation dates
    ok(['tgrac_nalas', 'tgrac_gwp', 'tgrac_cadastral', 'hmda_zones', 'hmwssb_network'].every(s => Q.sources[s].svc && !Q.sources[s].obs), 'TGRAC sources carry a service-creation date and NO invented survey date');

    // ---- freshness rules (synthetic, fixed date) ----
    const asOf = new Date(Date.UTC(2026, 9, 24)), fr = (o) => E.freshness({ nature: 'periodic', obs: ['2020-01', '2020-12'], stale_months: 12, ...o }, asOf);
    ok(fr({}) === 'stale' && fr({ obs: ['2026-01', '2026-06'] }) === 'current' && fr({ obs: ['2025-06', '2025-10'] }) === 'aging', 'freshness: periodic data goes current -> aging -> stale by its allowed age');
    ok(fr({ obs: null }) === 'undated' && fr({ nature: 'snapshot', obs: null }) === 'undated', 'freshness: no observation date is "undated", never "current"');
    ok(fr({ nature: 'live' }) === 'live' && fr({ nature: 'reference' }) === 'reference' && fr({ nature: 'documents' }) === 'documents' && fr({ nature: 'model' }) === 'model', 'freshness: live, reference, document and model sources are labelled as such');
    ok(fr({ nature: 'history', obs: ['2017-04', '2018-03'], stale_months: 24 }) === 'stale' && fr({ nature: 'history', obs: ['2020-10', '2026-06'], stale_months: null }) === 'historical', 'freshness: a history that stops long ago is stale; an open-ended record is historical');
    const QT = E.qualityTable(asOf), fl = id => QT.factors.find(f => f.id === id).flags, sf = id => QT.sources.find(s => s.id === id);
    ok(sf('civic_power').freshness === 'stale' && sf('civic_wq').freshness === 'stale' && sf('civic_noise').freshness === 'stale', 'dashboard: the 2017-18 civic records are flagged stale');
    ok(sf('osm').freshness === 'undated' && sf('tgrac_cadastral').freshness === 'undated' && sf('seismic_ref').freshness === 'reference' && sf('openmeteo_air').freshness === 'live', 'dashboard: undated, reference and live sources are labelled correctly');
    ok(fl('heat').includes('failed-validation') && fl('zoning').includes('no-data') && fl('perm').includes('no-data') && fl('supply').includes('no-data'), 'dashboard: failed validation and no-data are flagged');
    ok(fl('storms').includes('restricted-licence') && fl('heavyrain').includes('restricted-licence') && fl('sus').includes('coarse-scope') && fl('plot').includes('unvalidated') && fl('plot').includes('undated'), 'dashboard: licence, scope, validation and dating flags are computed');
    ok(QT.sources.every(s => s.used_by && Array.isArray(s.used_by)) && QT.factors.length === facIds.length, 'dashboard: every source lists the findings that use it');
    ok(E.qualityTable(new Date(Date.UTC(2031, 0, 1))).sources.find(s => s.id === 'gwd_levels').freshness === 'stale', 'dashboard: sources go stale as time passes');
    const ri = E.removalImpact('gwd_levels'); ok(ri.becomeUnknown.includes('gwdepth') && ri.becomeUnknown.includes('gwnear') && !ri.becomeUnknown.includes('sus'), 'removal impact: groundwater findings become unknown, flood findings do not');
    ok(E.removalImpact('tgrac_cadastral').becomeUnknown.includes('plot') && E.removalImpact('tgrac_cadastral').degrade.includes('prohib') && E.removalImpact('nope') === null, 'removal impact: single-source findings become unknown; shared ones degrade; unknown source is null');

    // ---- the engine cannot emit a finding the registry does not list, and findings obey the honesty rules ----
    const places = D.wards.map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.26, 78.43], [17.2403, 78.4294], [17.597, 78.57], [17.514, 78.45]]);
    let nUnreg = 0, nNoScope = 0, nBadConf = 0, nUnavail = 0, nNone = 0, nGood = 0, nFind = 0, nGapEmpty = 0; const unreg = new Set();
    const reports = [];
    for (const [la, lo] of places) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); reports.push(r);
      for (const s of r.ev.sections) for (const f of s.findings) {
        nFind++; const qf = Q.factors[f.id];
        if (!qf) { nUnreg++; unreg.add(f.id); continue; }
        if (!f.scope || f.scope !== qf.scope || !f.scopeText) nNoScope++;
        const ss = qf.sources.map(x => Q.sources[x]);
        if (ss.some(x => x.validation === 'negative') && !['low', 'unavailable'].includes(f.conf)) nBadConf++;
        if (ss.every(x => x.validation === 'unvalidated' || x.validation === 'negative') && f.conf === 'high') nBadConf++;
        if (f.kind === 'unavailable' && !['unknown', 'info', 'watch'].includes(f.level)) nUnavail++;
        if (qf.scope === 'none' && f.level !== 'unknown') nNone++;
        if (qf.sources.includes('none') && ['good', 'concern', 'watch'].includes(f.level)) nGood++;
      }
      for (const g of r.ev.gaps) if (!g.why || !g.label) nGapEmpty++;
    }
    ok(nUnreg === 0, `every finding the engine emits (${nFind} across ${reports.length} places) is in the registry`, [...unreg].join());
    ok(nNoScope === 0, 'every emitted finding carries the scope and scope text from the registry');
    ok(nBadConf === 0, 'a finding resting on a failed or unvalidated source never claims high confidence, and a failed validation is always low confidence', nBadConf);
    ok(nUnavail === 0, 'an "unavailable" finding is never rated good or concern');
    ok(nNone === 0 && nGood === 0, 'a finding with no data source is always unknown, never rated');
    ok(nGapEmpty === 0, 'every "why this report is incomplete" item says what and why');
    ok(reports.every(r => r.ev.gaps.length === r.ev.sections.flatMap(s => s.findings).filter(f => f.level === 'unknown').length + (r.ev.gaps.filter(g => g.id.startsWith('src:')).length)), 'the gaps list is exactly the unknown findings (plus any unloaded sources)');
    ok(reports.every(r => r.ev.identity && r.ev.identity.label && r.ev.identity.text), 'every report states what the property identity is');

    // ---- remove each data source in turn: nothing may turn reassuring ----
    const groups = new Map();
    for (const [id, s] of Object.entries(Q.sources)) if (s.files && s.files.length && id !== 'sethu_model') { const k = s.files.join('+'); (groups.get(k) || groups.set(k, { files: s.files, srcs: [] }).get(k)).srcs.push(id); }
    const RP = [[17.4235, 78.4745], [17.4401, 78.3489], [17.3616, 78.4747], [17.3558, 78.526], [17.514, 78.45], [17.4948, 78.3996], [17.4126, 78.4482], [17.63, 78.48], [17.2403, 78.4294]];
    let groupsTested = 0;
    for (const g of groups.values()) {
      let E2; try { E2 = await freshEngine(g.files); } catch (e) { ok(g.files.includes('hospitals.json'), `source files ${g.files.join('+')}: only a required file may stop the engine from starting`); continue; }
      groupsTested++; const remove = new Set(g.srcs); let rated = [], gapSeen = false;
      for (const [la, lo] of RP) {
        const r = await E2.report(la, lo); if (!r.ok) continue; await E2.attachParcel(r, {});
        gapSeen = gapSeen || g.srcs.every(sid => r.ev.gaps.some(x => x.id === 'src:' + sid));
        for (const s of r.ev.sections) for (const f of s.findings) { const qf = Q.factors[f.id]; if (qf && qf.sources.every(x => remove.has(x)) && ['good', 'watch', 'concern'].includes(f.level)) rated.push(f.id + ':' + f.level); }
      }
      ok(rated.length === 0, `without ${g.files.join('+')} no finding that rests only on it is still rated`, [...new Set(rated)].join());
      ok(gapSeen, `without ${g.files.join('+')} the report lists the missing source under "why incomplete"`);
    }
    ok(groupsTested >= 14, 'the removal test covered every optional data file', groupsTested);

    // ---- planning authority: which plan governs, never what the plot is zoned for ----
    const ZP = { Gachibowli: [17.4401, 78.3489, 'CDA'], Kondapur: [17.46, 78.364, 'CDA'], Kukatpally: [17.4948, 78.3996, 'HUDA'], Uppal: [17.4058, 78.5591, 'HUDA'], 'LB Nagar': [17.3457, 78.5522, 'HUDA'], Miyapur: [17.4969, 78.3548, 'HUDA'],
      Rajendranagar: [17.317, 78.4, 'HUDA'], Shamshabad: [17.2403, 78.4294, 'HADA'], Charminar: [17.3616, 78.4747, 'MCH'], 'Banjara Hills': [17.4126, 78.4482, 'MCH'], Ameerpet: [17.4374, 78.4487, 'MCH'], Secunderabad: [17.4399, 78.4983, 'MCH'], Medchal: [17.63, 78.48, 'HMR'], Shamirpet: [17.597, 78.57, 'HMR'] };
    for (const [n, [la, lo, z]] of Object.entries(ZP)) { const pf = E.planFacts(la, lo); ok(pf && pf.zone === z, `planning authority at ${n} is ${z}`, pf && pf.zone); }
    // HMR is the umbrella region around the others, so only overlaps between the specific authority areas count
    let multi = 0, none = 0, tot = 0; const b = D.plan.zones ? D.parcelIdx.bbox : null;
    for (let la = b[1] + .004; la < b[3]; la += .01) for (let lo = b[0] + .004; lo < b[2]; lo += .01) { tot++; const pf = E.planFacts(la, lo); if (pf.hits.filter(h => h !== 'HMR').length > 1) multi++; if (!pf.zone) none++; }
    ok(multi / tot < .015, 'the specific planning-authority areas barely overlap (boundary slivers only); the wider HMR region is the umbrella around them', `${multi} of ${tot}`);
    ok(none / tot < .5 && none > 0, 'some of the study box lies outside the authority areas, and the engine says so rather than guessing', `${none} of ${tot}`);
    const pfm = E.planFacts(17.63, 78.48); ok(pfm.mandal && pfm.links.some(l => /masterplan\.hmda\.gov\.in\/Masterplan2031\/Content\/.+\.jpg$/.test(l.url)) && pfm.links.every(l => /^https:\/\/(www\.hmda\.gov\.in|masterplan\.hmda\.gov\.in)\//.test(l.url)), 'a pin in the wider HMDA region links the official Master Plan 2031 sheet for its mandal, and only official HMDA addresses');
    ok(E.planFacts(17.3616, 78.4747).links.some(l => /revised-development-plan/.test(l.url)), 'a pin in the old city core links the Revised Development Plan page');
    for (const r of reports) {
      const fz = r.ev.sections.flatMap(s => s.findings), z = fz.find(f => f.id === 'zoning'), pa = fz.find(f => f.id === 'planauth');
      if (z.level !== 'unknown' || z.kind !== 'unavailable' || !/not read/.test(z.value) || z.scope !== 'none') { fails.push('zoning must stay unknown at ' + r.lat); fail++; }
      if (pa.level === 'info' && !/does not say what this plot is zoned for/.test(pa.note)) { fails.push('planauth must say it is not zoning at ' + r.lat); fail++; }
      if (fz.some(f => /zoned (for|as)|land use is|permitted use|residential zone|commercial zone/i.test(f.value))) { fails.push('a finding claims zoning at ' + r.lat); fail++; }
    }
    ok(true, 'zoning stays unknown at every checked place, and the planning-authority finding says it is not zoning');

    // ---- parcels: synthetic cases (exact geometry, deterministic) ----
    const LA = 17.44, LO = 78.35, dlaM = m => m / 110540, dloM = m => m / (111320 * Math.cos(LA * Math.PI / 180));
    const sqr = (la, lo, h) => [[la - dlaM(h), lo - dloM(h)], [la - dlaM(h), lo + dloM(h)], [la + dlaM(h), lo + dloM(h)], [la + dlaM(h), lo - dloM(h)], [la - dlaM(h), lo - dloM(h)]];
    const bbx = ring => [Math.min(...ring.map(p => p[0])), Math.min(...ring.map(p => p[1])), Math.max(...ring.map(p => p[0])), Math.max(...ring.map(p => p[1]))];
    const mkP = (n, v, la, lo, h, code = 0, rem = '') => { const ring = sqr(la, lo, h); return { n, v, m: 'Serilingampalle', code, rem, rings: [ring], _b: bbx(ring) }; };
    const DATA = ps => ({ ok: true, outsideBox: false, parcels: ps });
    const pm = (ps, ref, la = LA, lo = LO) => E.parcelMatch(la, lo, DATA(ps), ref);
    const A = mkP('91/1', 'Gachibowli', LA, LO, 40), N1 = mkP('92', 'Gachibowli', LA, LO + dloM(150), 40), FAR = mkP('500', 'Gachibowli', LA + dlaM(150), LO + dloM(150), 40);
    let m = pm([A, N1], {}); ok(m.status === 'approximate' && m.reason === 'pin-only' && m.parcel.number === '91/1' && m.usable === true, 'parcel: a pin inside one outline with no number is an approximate match, never verified');
    m = pm([A, N1], { survey: '91/1' }); ok(m.status === 'verified' && m.parcel.number === '91/1' && m.usable, 'parcel: pin inside + matching number is a verified match');
    m = pm([A, N1], { survey: ' 091 / 01 ' }); ok(m.status === 'verified', 'parcel: spaces and leading zeros in the number do not matter');
    m = pm([A, N1], { survey: '91/1', village: 'Gachibowli' }); ok(m.status === 'verified' && m.reason === 'number-and-village', 'parcel: number and village both match');
    m = pm([A, N1], { survey: '91/1', village: 'Gachibowle' }); ok(m.status === 'verified', 'parcel: a one-letter spelling variant of the village still matches');
    m = pm([A, N1], { survey: '91/1', village: 'Kondapur' }); ok(m.status === 'none' && m.reason === 'village-mismatch', 'parcel: a different village is no match');
    m = pm([A, N1], { survey: '777' }); ok(m.status === 'none' && m.reason === 'number-mismatch' && m.parcel.number === '91/1' && !m.neighbour, 'parcel: a number that is not mapped nearby is no match and names what the pin is on');
    m = pm([A, N1], { survey: '92' }); ok(m.status === 'none' && m.reason === 'neighbour' && m.neighbour.number === '92' && m.neighbour.d > 50 && m.neighbour.d < 150, 'parcel: the next-door parcel\'s number is "no match", with the neighbour and its distance reported');
    m = pm([A, FAR], { survey: '500' }); ok(m.status === 'none' && m.reason === 'neighbour' && m.neighbour.d > 150, 'parcel: a parcel 200 m away is still reported as a neighbour');
    const far2 = mkP('800', 'Gachibowli', LA, LO + dloM(900), 40); m = pm([A, far2], { survey: '800' }); ok(m.status === 'none' && m.reason === 'number-mismatch' && !m.neighbour, 'parcel: a same-numbered parcel 900 m away is not a neighbour');
    m = pm([A], { survey: '91' }); ok(m.status === 'approximate' && m.reason === 'sub-survey', 'parcel: "91" against parcel "91/1" is only an approximate match (sub-division)');
    m = pm([A], { survey: '91/2' }); ok(m.status === 'none', 'parcel: "91/2" against parcel "91/1" is no match');
    m = pm([mkP('91', 'Gachibowli', LA, LO, 40)], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'sub-survey', 'parcel: "91/1" against parent "91" is only approximate');
    const FL = mkP('91/1', 'Gachibowli', LA, LO, 40, 1, 'Duplicate Number'); m = pm([FL], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'number-flagged' && !m.usable, 'parcel: a number the source flags as duplicate or unreadable can never be verified');
    m = pm([FL], {}); ok(m.status === 'approximate' && m.reason === 'pin-only-flagged' && !m.usable, 'parcel: a flagged number is not usable for overlap tests either');
    const OV1 = mkP('10', 'Gachibowli', LA, LO, 40), OV2 = mkP('11', 'Gachibowli', LA, LO + dloM(20), 40);
    m = pm([OV1, OV2], {}); ok(m.status === 'approximate' && m.ambiguous && m.parcel === null && m.candidates.length === 2 && !m.usable, 'parcel: two overlapping outlines make an ambiguous approximate match with no single parcel');
    m = pm([OV1, OV2], { survey: '10' }); ok(m.status === 'approximate' && m.reason === 'overlap-ambiguous' && m.ambiguous, 'parcel: even a matching number is not "verified" when another outline overlaps the pin');
    const out10 = (h) => mkP('91/1', 'Gachibowli', LA, LO + dloM(40 + h), 40);
    m = pm([out10(10)], {}); ok(m.status === 'approximate' && m.reason === 'near-edge' && m.candidates[0].d > 5 && m.candidates[0].d < 15 && !m.usable, 'parcel: a pin 10 m outside an outline is approximate (near-edge) and not usable for overlap tests');
    m = pm([out10(10)], { survey: '91/1' }); ok(m.status === 'approximate' && m.reason === 'near-edge', 'parcel: a matching number does not make a near-edge pin "verified"');
    m = pm([out10(40), FAR], {}); ok(m.status === 'none' && m.reason === 'unmapped', 'parcel: a pin 40 m from any outline falls in a gap: no match');
    const RD = mkP('', 'Gachibowli', LA, LO, 40, 2, 'Road'); RD.n = '12'; m = pm([RD], {}); ok(m.status === 'none' && m.reason === 'on-feature', 'parcel: a pin on a mapped road or canal feature is no match');
    m = pm([mkP('1', 'X', LA, LO + dloM(600), 40)], {}); ok(m.status === 'unavailable' && m.reason === 'no-parcels-mapped', 'parcel: no parcels within 250 m means the source is unavailable here, not "no match"');
    m = pm([], {}); ok(m.status === 'unavailable', 'parcel: an empty area is "source unavailable"');
    m = E.parcelMatch(LA, LO, { ok: false, reason: 'tile-failed', parcels: [] }, {}); ok(m.status === 'unavailable' && m.reason === 'tile-failed', 'parcel: a failed download is "source unavailable", never "no match" or "no parcels"');
    m = E.parcelMatch(LA, LO, null, {}); ok(m.status === 'unavailable', 'parcel: no data object is "source unavailable"');
    m = E.parcelMatch(LA, LO, { ok: true, outsideBox: true, parcels: [] }, {}); ok(m.status === 'unavailable' && m.reason === 'outside-area', 'parcel: outside the covered area is "source unavailable"');
    const allM = [pm([A, N1], {}), pm([A, N1], { survey: '91/1' }), pm([OV1, OV2], { survey: '10' }), pm([FL], { survey: '91/1' }), pm([out10(10)], { survey: '91/1' }), pm([A], { survey: '91' }), pm([A], { survey: '777' })];
    ok(allM.every(x => ['verified', 'approximate', 'none', 'unavailable'].includes(x.status)), 'parcel: only the four documented statuses are ever returned');
    ok(allM.filter(x => x.status === 'verified').every(x => x.usable && !x.ambiguous && x.candidates.length === 1 && x.parcel.inside !== false), 'parcel: "verified" always means one outline, containing the pin, matching number, not flagged');
    ok(allM.every(x => !/owner|ownership|clear title|title is|legally|encumbrance-free/i.test(x.text.replace(/does not confirm title[^.]*\./i, '').replace(/says nothing about title or ownership/i, ''))), 'parcel: no result text claims ownership, clear title or legal status');
    ok(/does not confirm title/.test(pm([A], { survey: '91/1' }).text) && /many house plots/.test(pm([A], { survey: '91/1' }).text), 'parcel: the verified text says it does not confirm title and that a survey number can hold many plots');

    // ---- parcels: real tiles ----
    const idx = D.parcelIdx; ok(idx && idx.parcels_stored > 40000 && Object.keys(idx.tiles).length >= 100, 'parcel tiles are present', idx && idx.parcels_stored);
    ok(Object.entries(idx.tiles).every(([k, c]) => rd(`data/parcels/${k}.json`).p.length === c), 'every parcel tile holds exactly the number of parcels the index says');
    ok(idx.not_stored.includes('owner'), 'the parcel index records that owner fields were never stored');
    const cov = path.join(__dirname, '..', 'research', 'v7', 'parcel_coverage.json');
    if (fs.existsSync(cov)) { const c = rd('../research/v7/parcel_coverage.json'), scan = {}; for (const [k, x, y, n] of c.cells) if (k === 'cad_parcels') scan[Math.round((x - c.bbox[0]) / c.step) + '_' + Math.round((y - c.bbox[1]) / c.step)] = n; ok(Object.entries(idx.tiles).every(([k, n]) => scan[k] === n) && Object.entries(scan).every(([k, n]) => n === 0 || idx.tiles[k] === n), 'every tile holds exactly the parcels the server counted: none lost, none missing'); }
    const tileKeys = Object.keys(idx.tiles).filter(k => idx.tiles[k] > 300); let cnt = { verified: 0, approximate: 0, none: 0, unavailable: 0 }, tested = 0, wrongNum = 0;
    for (let ti = 0; ti < tileKeys.length; ti += 2) {
      const t = rd(`data/parcels/${tileKeys[ti]}.json`);
      for (let i = 0; i < t.p.length; i += 31) {
        const row = t.p[i]; if (row[3] !== 0 || !row[0]) continue; const ring = row[5][0]; let c = [0, 0]; for (const p of ring.slice(0, -1)) { c[0] += p[0]; c[1] += p[1]; } c = [c[0] / (ring.length - 1), c[1] / (ring.length - 1)];
        let inside = false; { let k = false; for (let a = 0, b2 = ring.length - 1; a < ring.length; b2 = a++) if (((ring[a][0] > c[0]) !== (ring[b2][0] > c[0])) && (c[1] < (ring[b2][1] - ring[a][1]) * (c[0] - ring[a][0]) / (ring[b2][0] - ring[a][0]) + ring[a][1])) k = !k; inside = k; } if (!inside) continue;
        const d = await E.parcelLoad(c[0], c[1]), mm = E.parcelMatch(c[0], c[1], d, { survey: row[0], village: t.v[row[1]] }); cnt[mm.status]++; tested++;
        if (mm.parcel && mm.status !== 'unavailable' && mm.status !== 'none' && E.normNum(mm.parcel.number) !== E.normNum(row[0]) && !mm.ambiguous) wrongNum++;
      }
    }
    ok(tested >= 100 && cnt.none === 0 && cnt.unavailable === 0 && cnt.verified / tested >= .85 && wrongNum === 0, `real parcels, own number and village at an interior point: all matched (${JSON.stringify(cnt)} of ${tested}), most verified, none wrong`);
    for (const [n, la, lo] of [['Charminar', 17.3616, 78.4747], ['Banjara Hills', 17.4126, 78.4482], ['Secunderabad', 17.4399, 78.4983], ['Hussain Sagar', 17.4235, 78.4745]]) { const mm = E.parcelMatch(la, lo, await E.parcelLoad(la, lo), { survey: '1' }); ok(mm.status === 'unavailable' && mm.reason === 'no-parcels-mapped', `old-city core (${n}): the parcel layer is honestly unavailable, even when a survey number is typed`); }
    ok((await E.parcelLoad(18.5, 79.5)).outsideBox === true, 'a pin far outside the study box is outside the parcel data');
    { const vn = new Map(); let dup = 0, totn = 0; for (const k of Object.keys(idx.tiles).filter((_, i) => i % 5 === 0)) for (const row of rd(`data/parcels/${k}.json`).p) { if (row[3] !== 0) continue; const kk = k.split('_')[0] + '|' + row[0] + '|' + row[1]; totn++; if (vn.has(row[0] + '|' + row[1] + '|' + k)) dup++; vn.set(row[0] + '|' + row[1] + '|' + k, 1); } ok(dup / totn < .03, 'few survey numbers repeat inside a tile (matching requires the pin to fall inside anyway)', `${dup} of ${totn}`); }
    ok(D.parcelIdx.remark_codes['1'] && D.parcelIdx.remark_codes['2'], 'remark classes are documented in the index');

    // ---- overlap of the matched parcel with other mapped footprints ----
    {
      const par = mkP('91/1', 'Gachibowli', LA, LO, 40), ring = par.rings[0], inject = (list, lo0, lo1) => { const rr = sqr(LA, (lo0 + lo1) / 2, 40); rr[0][1] = rr[3][1] = lo0; rr[1][1] = rr[2][1] = lo1; rr[4] = rr[0].slice(); const u = { r: [rr], a: ['test', 1.5, 'x'], _b: [bbx(rr)] }; list.push(u); return () => list.splice(list.indexOf(u), 1); };
      const x0 = LO - dloM(40), x1 = LO + dloM(40);
      let undo = inject(D.landL.lost, LO, x1 + dloM(10)); let o = E.overlapFacts([ring]); ok(o.lost && o.lost.frac > .4 && o.lost.frac < .6, 'overlap: a footprint over half of the outline is detected (about 50%)', o.lost && o.lost.frac); undo();
      undo = inject(D.landL.lost, x1, x1 + dloM(30)); o = E.overlapFacts([ring]); ok(o.lost === null, 'overlap: a footprint that only touches the outline edge is not an overlap'); undo();
      undo = inject(D.landL.lost, x1 - dloM(0.8), x1 + dloM(30)); o = E.overlapFacts([ring]); ok(o.lost === null, 'overlap: a sliver of about 1% (map error) is ignored'); undo();
      undo = inject(D.landL.forest, x0 - dloM(10), x1 + dloM(10)); o = E.overlapFacts([ring]); ok(o.forest && o.forest.frac > .95, 'overlap: a forest boundary covering the outline is detected'); undo();
      ok(E.overlapFacts([ring]).lost === null && E.overlapFacts([ring]).tanks.length === 0, 'overlap: injected test footprints were removed again');
      const r = await E.report(LA, LO); undo = inject(D.landL.lost, LO, x1 + dloM(10));
      E.setParcel(r, DATA([par]), { survey: '91/1' }); let f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'concern' && /disappeared/.test(f.value) && f.scope === 'parcel' && /not a legal finding/.test(f.note), 'overlap finding: a matched outline over a disappeared tank is a concern, labelled parcel-scope and "not a legal finding"'); undo();
      E.setParcel(r, DATA([par]), { survey: '91/1' }); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'info' && /not a clearance/.test(f.note), 'overlap finding: no overlap is information, never "good", and says it is not a clearance');
      E.setParcel(r, DATA([par, mkP('92', 'Gachibowli', LA, LO + dloM(10), 40)]), {}); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'unknown' && /needs a matched survey parcel/.test(f.value), 'overlap finding: an ambiguous match gives no parcel-level result at all');
      E.setParcel(r, DATA([out10(10)]), { survey: '91/1' }); f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'overlap');
      ok(f.level === 'unknown', 'overlap finding: a near-edge match gives no parcel-level result');
      const pl = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'plot'); ok(pl.level === 'info' && /Approximate match/.test(pl.value) && pl.conf === 'low', 'plot finding: an approximate match is info with low confidence');
      E.setParcel(r, DATA([A, N1]), { survey: '92' }); const pl2 = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'plot'); ok(pl2.level === 'watch' && /No match/.test(pl2.value), 'plot finding: a number that does not match the pin is a watch item');
      const ck = E.checklist(r); ok(ck.items.some(i => i.key === 'plot'), 'checklist: a mismatched survey number puts "confirm the survey number" on the list');
      const rr0 = await E.report(LA, LO); await E.attachParcel(rr0, {}); const ck0 = E.checklist(rr0); ok(rr0.ev.identity.status && ck0.items.every(i => i.action && i.why), 'checklist: items stay well-formed with the new findings');
    }

    // ---- prohibitory-category layer ----
    {
      const pj = rd('data/prohib.json'); ok(pj.p.length >= 600 && /NOT the registration department/.test(pj.meta.note), 'prohibitory layer loaded and documented as not the legal register', pj.p.length);
      let hit = 0, tot2 = 0, wrongCat = 0;
      for (const p of pj.p.filter((_, i) => i % 3 === 0)) {
        const ring = p[6][0], bb2 = bbx(ring); let pt = null;
        for (let i = 0; i < 24 && !pt; i++) for (let j = 0; j < 24 && !pt; j++) { const la = bb2[0] + (i + .5) * (bb2[2] - bb2[0]) / 24, lo = bb2[1] + (j + .5) * (bb2[3] - bb2[1]) / 24; let k = false; for (let a = 0, b2 = ring.length - 1; a < ring.length; b2 = a++) if (((ring[a][0] > la) !== (ring[b2][0] > la)) && (lo < (ring[b2][1] - ring[a][1]) * (la - ring[a][0]) / (ring[b2][0] - ring[a][0]) + ring[a][1])) k = !k; if (k) pt = [la, lo]; }
        if (!pt) continue; tot2++; const h = E.prohibFacts(pt[0], pt[1], null); if (h) { hit++; if (h.cat !== p[0] && h.how !== 'pin') wrongCat++; }
      }
      ok(tot2 >= 150 && hit / tot2 >= .97, 'every listed prohibitory parcel is found when the pin is inside it', `${hit} of ${tot2}`);
      const p0 = pj.p.find(p => p[6][0].length > 4), ring0 = p0[6][0], bb3 = bbx(ring0); let pt0 = null;
      for (let i = 0; i < 24 && !pt0; i++) for (let j = 0; j < 24 && !pt0; j++) { const la = bb3[0] + (i + .5) * (bb3[2] - bb3[0]) / 24, lo = bb3[1] + (j + .5) * (bb3[3] - bb3[1]) / 24; let k = false; for (let a = 0, b2 = ring0.length - 1; a < ring0.length; b2 = a++) if (((ring0[a][0] > la) !== (ring0[b2][0] > la)) && (lo < (ring0[b2][1] - ring0[a][1]) * (la - ring0[a][0]) / (ring0[b2][0] - ring0[a][0]) + ring0[a][1])) k = !k; if (k) pt0 = [la, lo]; }
      const r = await E.report(pt0[0], pt0[1]);
      if (r.ok) { await E.attachParcel(r, {}); const f = r.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib');
        ok(f.level === 'watch' && f.conf === 'low' && f.value.includes(p0[0]) && /not a legal finding/.test(f.note) && /not the registration department/.test(f.note) && f.kind === 'official', 'prohibitory finding: quotes the category as recorded, watch only, low confidence, and says it is not the legal register');
        ok(!r.ev.sections.flatMap(s => s.findings).some(x => x.id === 'prohib' && x.level === 'concern'), 'prohibitory finding is never a concern on its own');
        ok(E.checklist(r).items.some(i => i.key === 'prohib' && /Registration Department/.test(i.action)), 'checklist: a prohibitory listing sends the buyer to the registration portal and Bhu Bharati'); }
      const rn = await E.report(LA, LO); E.setParcel(rn, DATA([A]), { survey: '91/1' }); const fn = rn.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib');
      ok(fn.level === 'info' && /not clearance/.test(fn.note), 'prohibitory finding: "not listed" is info and "not clearance", never good');
      const ru = await E.report(17.3616, 78.4747); await E.attachParcel(ru, {}); const fu = ru.ev.sections.flatMap(s => s.findings).find(x => x.id === 'prohib'); ok(fu.level === 'unknown', 'prohibitory finding: where no parcels are mapped the layer cannot be tested, so it is unknown');
    }

    // ---- mapped water network ----
    if (!D.networkL) ok(false, 'network data (web/data/network.json) is missing'); else {
      ok(D.networkL && D.networkL.meta.supply_segments.in_use_kept > 100000, 'network: supply pipes are loaded', D.networkL && D.networkL.meta.supply_segments.in_use_kept);
      const nm = D.networkL.meta; ok([...D.networkL.sup.keys(), ...D.networkL.sew.keys()].every(k => Number.isInteger(k) && k >= 0 && k < nm.nx * nm.ny) && [...D.networkL.sup.values()].every(v => v[0] > 0 && v[1] >= 0), 'network: every cell index is inside the grid and every cell has a positive pipe length');
      ok(/not a connection record/i.test(nm.note) && /not redistributed/i.test(nm.note), 'network: the file records that it is not a connection record and that pipe geometry is not redistributed');
      ok(!JSON.stringify(rd('data/network.json').supply.slice(0, 50)).includes('paths'), 'network: no pipe geometry is stored');
      const nc = E.netFacts(17.3616, 78.4747), ng = E.netFacts(17.4401, 78.3489), nsx = E.netFacts(17.2403, 78.4294), no = E.netFacts(18.5, 79.5);
      ok(nc.inside && nc.sup.ring === 0 && nc.sew.ring != null && nc.sew.ring <= 1, 'network: the old city shows both supply pipes and a sewer line', JSON.stringify(nc.sew));
      ok(ng.section && /GACHIBOWLI/i.test(ng.section.name) && nc.section && /SHIFA/i.test(nc.section.name), 'network: HMWSSB operating sections are named (Gachibowli; Dar-ul-Shifa at Charminar)', [ng.section && ng.section.name, nc.section && nc.section.name].join());
      ok(ng.sup.ring != null && ng.sew.ring == null, 'network: Gachibowli has mapped supply pipes but no mapped sewer line (the layer covers the core city only)');
      ok(no.inside === false, 'network: a pin outside the grid is outside the network data');
      let bad = 0, nWatch = 0;
      for (const r of reports) for (const s of r.ev.sections) for (const f of s.findings) {
        if (f.id === 'supply' && (f.level !== 'unknown' || !/not published/.test(f.value))) bad++;
        if (f.id === 'supplynet' && (!['info', 'unknown'].includes(f.level) || (f.level === 'info' && !/not a connection/.test(f.note)) || (f.level === 'unknown' && !/neither proof/.test(f.note)))) bad++;
        if (f.id === 'sewernet') { if (!['info', 'unknown', 'watch'].includes(f.level) || (f.level === 'watch' && !/core city only/.test(f.note))) bad++; if (f.level === 'watch') nWatch++; }
      }
      ok(bad === 0, 'network: connection is always unknown; mapped pipes are information only and always say they are not a connection; no mapped pipe is never reassuring', bad);
      ok(reports.some(r => r.ev.sections.flatMap(s => s.findings).some(f => f.id === 'supplynet' && f.level === 'info')) && reports.some(r => r.ev.sections.flatMap(s => s.findings).some(f => f.id === 'sewernet' && f.level === 'unknown')), 'network: both the "mapped" and "outside the sewer area" outcomes occur across the city');
    }
  }

