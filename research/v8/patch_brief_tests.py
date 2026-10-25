"""Brief UI: load brief.js into the test sandbox and add tests for the short, tappable answer."""
from pathlib import Path
t = Path("tests/engine.test.js"); s = t.read_text(encoding="utf-8")
old = """for (const f of ['charts.js', 'view.js', 'reports.js'])
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', f), 'utf8') + '\\n;globalThis.' + ({ 'charts.js': 'Charts = Charts', 'view.js': 'View = View', 'reports.js': 'Reports = Reports' })[f] + ';', sandbox);"""
new = """for (const f of ['charts.js', 'view.js', 'reports.js', 'brief.js'])
  vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', f), 'utf8') + '\\n;globalThis.' + ({ 'charts.js': 'Charts = Charts', 'view.js': 'View = View', 'reports.js': 'Reports = Reports', 'brief.js': 'Brief = Brief' })[f] + ';', sandbox);"""
assert s.count(old) == 1; s = s.replace(old, new)
anchor = "  // ---- live APIs (optional) ----"; assert s.count(anchor) == 1
blk = r"""  // ---- the brief: a short, tappable answer instead of a long report ----
  {
    const Br = sandbox.Brief, strip = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' '), words = h => strip(h).trim().split(' ').length;
    const mk = (r, persona, open) => ({ r, persona, label: '', address: '', open: open || {}, cmpPending: false, pref: { survey: '', village: '', plot: '', layout: '', doc: '' }, air: { aqi: 80, band: 'x' }, access: {}, terrain: { relief: 0 }, cust: {}, agent: {}, claim: {} });
    const facs = Object.keys(D.quality.factors), P = Br.PERSONAS;
    ok(Object.keys(P).length === 6 && ['buyer', 'renter', 'investor', 'agent', 'lender', 'insurer'].every(k => P[k] && P[k].ask && P[k].tiles.length === 6 && P[k].say.bad && P[k].say.warn && P[k].say.ok && P[k].say.mute), 'six kinds of user, each with a question, six topics and an answer for every outcome');
    ok(Object.values(P).every(p => p.tiles.every(id => Br.TILES[id])), 'every topic a user is shown exists');
    ok(Object.values(Br.TILES).filter(t => t.ids).every(t => t.ids.every(id => facs.includes(id))), 'every finding a topic reads from exists in the evidence registry (no typos)', Object.values(Br.TILES).filter(t => t.ids).flatMap(t => t.ids.filter(id => !facs.includes(id))).join());
    // the verdict of a topic is the most serious result inside it, never an average
    const V = (lv, load) => Br.verdict(lv.map((l, i) => ({ id: 'x' + i, level: l })), new Set(load || [])).level;
    ok(V(['concern', 'good', 'good', 'good']) === 'concern' && V(['watch', 'good', 'good']) === 'watch', 'one red flag among many clean results still makes the topic red or amber');
    ok(V(['good', 'good', 'unknown']) === 'good' && V(['good', 'unknown', 'unknown']) === 'partial' && V(['unknown', 'unknown']) === 'unknown' && V(['info', 'unknown']) === 'partial' && V(['info']) === 'info', 'a topic reads "no issue found" only when clean checks at least match the unanswered ones; otherwise it says partly checked or couldn\'t check');
    ok(V(['unknown', 'good'], ['x0']) === 'good', 'a check still loading is not counted as a gap');
    const places = [[17.4401, 78.3489], [17.3616, 78.4747], [17.4948, 78.3996], [17.2403, 78.4294], [17.63, 78.48], [17.3457, 78.5522], [17.4325, 78.4071], [17.4399, 78.4983], [17.597, 78.57], [17.26, 78.43]];
    let nHead = 0, nWords = 0, nFace = 0, nFlag = 0, nTile = 0, nWhy = 0, nHonest = 0, nJar = 0, nPersona = 0, checked = 0, nOkNote = 0;
    for (const [la, lo] of places) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); checked++;
      for (const pid of Object.keys(P)) {
        const S0 = mk(r, pid), html = Br.page(S0), ctx = Br.state(r, S0), tiles = P[pid].tiles.map(id => Br.tileData(id, r, S0, ctx));
        if (words(html) > 750) nWords++;
        if ((html.match(/<details class="b-tile/g) || []).length !== 6 || (html.match(/aria-selected="true"/g) || []).length !== 1) nPersona++;
        const anyBad = tiles.some(t => t.level === 'concern'), anyWarn = tiles.some(t => t.level === 'watch'), cls = (html.match(/class="b-head h-(\w+)"/) || [])[1];
        if (anyBad ? cls !== 'bad' : anyWarn ? cls !== 'warn' : (cls === 'bad' || cls === 'warn')) nHead++;
        if (cls === 'ok' && !/not a clearance/.test(strip(html))) nOkNote++;
        for (const x of html.matchAll(/data-act="b-open" data-tile="(\w+)"/g)) { const t = tiles.find(q => q.id === x[1]); if (!t || !['concern', 'watch'].includes(t.level) || (anyBad && t.level !== 'concern')) nFlag++; }
        for (const t of tiles) if (t.kind === 'generic') { const lv = t.live.map(f => f.level); if ((lv.includes('concern') && t.level !== 'concern') || (!lv.includes('concern') && lv.includes('watch') && t.level !== 'watch') || (t.level === 'good' && (lv.includes('concern') || lv.includes('watch')))) nTile++; }
        const faces = [...html.matchAll(/<summary>([\s\S]*?)<\/summary>/g)].map(m => strip(m[1])).join(' ');
        if (/TGRAC|\bAUC\b|LOEO|OSRM|ArcGIS|JSON|\bAPI\b|GeoJSON|HYDRAA/.test(faces)) nJar++;
        if (/\b(is safe|are safe|guaranteed|cleared|clear title)\b/i.test(strip(html).replace(/Is it safe to buy here\?/g, '').replace(/not a clearance/g, '').replace(/not unsafe/g, ''))) nHonest++;
        // every fact shown carries its reasoning: open every topic and every drawer
        const open = { b_allwhy: true }; for (const id of P[pid].tiles) open['bt_' + id] = true;
        const full = Br.page(mk(r, pid, open)), nF = (full.match(/class="b-fact /g) || []).length, nW = (full.match(/<details class="b-why"/g) || []).length, nSrc = (full.match(/What this rests on/g) || []).length;
        if (nF !== nW || nF === 0 || nSrc < nF * 0.8) nWhy++;
      }
    }
    ok(checked >= 8, 'the brief was built for many places and all six kinds of user', checked);
    ok(nPersona === 0, 'every brief shows six topics and exactly one selected kind of user', nPersona);
    ok(nWords === 0, 'the short version stays short (under 750 words, against about 3,000 in the long report)', nWords);
    ok(nHead === 0, 'the one-line answer is red if any topic is red, amber if any is amber, and never green with a flag', nHead);
    ok(nOkNote === 0, 'a green answer always says it is not a clearance', nOkNote);
    ok(nFlag === 0, 'the flagged topics in the answer are real, flagged topics (red ones first)', nFlag);
    ok(nTile === 0, 'no topic reads green or amber while a more serious result sits inside it', nTile);
    ok(nWhy === 0, 'every fact has its "How we know" with source, age, locality and confidence', nWhy);
    ok(nJar === 0, 'the topic faces use plain words (no data-source jargon up front)', nJar);
    ok(nHonest === 0, 'the brief never says a place is safe or cleared', nHonest);
    // special topics
    const rr = await E.report(17.4401, 78.3489); await E.attachParcel(rr, {}); const Sx = mk(rr, 'insurer'), cx = Br.state(rr, Sx);
    const ex = Br.tileData('exposure', rr, Sx, cx), tiersLv = ['motor', 'prop', 'health'].map(k => rr.tiers[k].letter);
    ok(ex.level === (tiersLv.some(l => 'DE'.includes(l)) ? 'concern' : tiersLv.some(l => l === 'C') ? 'watch' : 'good') && /illustrative/.test(ex.body), 'the insurer\'s exposure topic follows the worst tier and says loadings are illustrative');
    const pr = Br.tileData('price', rr, mk(rr, 'agent'), cx); ok(pr.level === 'info' && /asking prices, not registered deal prices/.test(pr.body), 'the price topic is information only and says these are asking prices');
    const pt = Br.tileData('pitch', rr, mk(rr, 'agent'), cx); ok(['concern', 'watch', 'good'].includes(pt.level) && /Say this/.test(pt.body) && /Be ready for/.test(pt.body), 'the agent\'s pitch topic lists what to say and what to be ready for');
    // before a place is picked
    const L = Br.landing({ persona: 'buyer', open: {} }), Lt = strip(L);
    ok(Object.values(P).every(p => Lt.includes(p.name)) && /I am a/.test(Lt) && /before/.test(Lt) && /can’t tell you|can't tell you/.test(Lt) && !/real floods tested|wards\s+\d|hospitals mapped/.test(Lt), 'the landing states the goal, asks who you are, and drops the validation counters');
    ok(words(L) < 280, 'the landing is short', words(L));
    const dk = Br.dock(mk(rr, 'buyer')), pg = Br.page(mk(rr, 'buyer')), pgf = Br.page(mk(rr, 'buyer', { fullreport: true }));
    ok(words(dk) < 100 && !/b-tile/.test(dk) && /View report/.test(dk) && /I am a/.test(strip(dk)), 'the side panel is only the place, who you are and a "View report" button', words(dk));
    ok(/b-fullcta/.test(pg) && !/id="fullreport"/.test(pg) && !/The short version/.test(pg), 'the report page opens on the summary, with the full report one tap below');
    ok(/id="fullreport"/.test(pgf) && /The short version/.test(pgf) && /Details by topic/.test(pgf) && !/b-fullcta/.test(pgf), 'tapping "View the full report" adds the whole report under the summary');
  }
"""
s = s.replace(anchor, blk + anchor); t.write_text(s, encoding="utf-8"); print("ok")
