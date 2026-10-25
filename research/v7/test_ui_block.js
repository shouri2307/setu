  // =====================================================================================================
  // UI — the buyer check is understandable, honest and complete
  // =====================================================================================================
  {
    const SB = r => ({ r, label: '', cust: { price: '', area: '', brokerage: '' }, agent: { ask: '', area: '', comps: '', guide: '', fee: '' }, claim: { peril: 'rain_vehicle', date: '', amount: '', out: null, busy: false },
      ai: { q: '', a: '', think: false }, fc: null, air: { aqi: 80, band: 'Moderate' }, access: {}, terrain: { relief: 0 }, line: 'motor', PERILS: PER, open: {}, pref: { survey: '', village: '', plot: '', layout: '', doc: '' } });
    const placesUI = D.wards.filter((_, i) => i % 6 === 0).map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.2403, 78.4294], [17.3616, 78.4747]]);
    let nOrder = 0, nHero = 0, nCount = 0, nRow = 0, nStat = 0, nJump = 0, nClip = 0, nJargon = 0, nPlain = 0, checked = 0;
    const strip = h => h.replace(/<[^>]+>/g, ' ');
    for (const [la, lo] of placesUI) {
      const r = await E.report(la, lo); if (!r.ok) continue; await E.attachParcel(r, {}); const S = SB(r); checked++;
      const html = Rep.render('customer', S), i1 = html.indexOf('What this check is about'), i2 = html.indexOf('The short version'), i3 = html.indexOf('Before you pay'), i4 = html.indexOf('Details by topic');
      if (!(i1 >= 0 && i1 < i2 && i2 < i3 && i3 < i4)) nOrder++;
      if (/Verdict for buyers|gaugebox|High caution/.test(html)) nHero++;
      const T = View.tally(r, S), m = k => { const x = html.match(new RegExp('<b>(\\d+)</b> ' + k)); return x ? +x[1] : -1; };
      if (m('need attention') !== T.concern.length || m('to look into') !== T.watch.length || m('look fine') !== T.good.length || m("couldn't be checked") !== T.unknown.length) nCount++;
      const all = r.ev.sections.flatMap(s => s.findings);
      for (const f of all) if ((html.match(new RegExp('id="f_' + f.id + '"', 'g')) || []).length !== 1) nRow++;
      if ((html.match(/class="v-fstat/g) || []).length !== all.length) nStat++;
      for (const x of html.matchAll(/data-act="jump" data-id="([^"]+)"/g)) if (!html.includes('id="f_' + x[1] + '"')) nJump++;
      for (const x of html.matchAll(/<span class="v-iv">([^<]*)<\/span>/g)) if (x[1].length > 160) nClip++;
      const top = strip(View.shortVersion(r, S) + View.dock(S) + View.landing(S));
      if (/TGRAC|\bAUC\b|LOEO|OSRM|ArcGIS|JSON|\bAPI\b|SETHU model|GeoJSON/.test(top)) nJargon++;
      if (all.some(f => !View.PLAIN[f.id])) nPlain++;
    }
    ok(checked >= 20, 'UI tests ran on a spread of places', checked);
    ok(nOrder === 0, 'the buyer check reads in order: what this is about, the short version, before you pay, details by topic');
    ok(nHero === 0, 'the old contradictory verdict and score gauge are gone from the buyer check');
    ok(nCount === 0, 'the counts in the short version equal the findings in each state');
    ok(nRow === 0, 'every finding appears exactly once in the details');
    ok(nStat === 0, 'every finding row states its status in words, not only in colour');
    ok(nJump === 0, 'every item in the short version links to a finding that exists');
    ok(nClip === 0, 'items in the short version stay short');
    ok(nJargon === 0, 'the short version, map card and landing text avoid technical jargon');
    ok(nPlain === 0, 'every finding has a plain-language title', nPlain);
    ok(Object.keys(D.quality.factors).every(id => View.PLAIN[id]), 'every registry finding has a plain-language title');

    // escaping: a hostile value can never become markup
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, { survey: '<img src=x onerror=alert(1)>', village: '"><script>alert(1)</script>' }); r.ev.sections[0].findings[0].value = '<img src=x onerror=alert(1)>'; r.ev.sections[0].findings[0].note = '<script>alert(2)</script>';
      const S = SB(r); S.pref = { survey: '<img src=x onerror=alert(1)>', village: '"><script>alert(1)</script>', plot: '<b>p</b>', layout: '', doc: '' };
      const html = Rep.render('customer', S) + View.dock(S);
      ok(!/<img src=x|<script>alert|<b>p<\/b>/.test(html) && html.includes('&lt;img'), 'hostile text in findings and in the buyer\'s own references is escaped everywhere'); }

    // loading state: live lookups are "still loading", not "couldn't check"
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r); S.access = null; S.air = null; S.terrain = null;
      const t = View.tally(r, S); ok(t.loading.length >= 1 && !t.unknown.some(f => t.loading.includes(f.id)), 'findings still being fetched are listed as loading, not as unchecked');
      ok(Rep.render('customer', S).includes('Still loading'), 'the page says what is still loading'); ok(!Rep.render('customer', SB(r)).includes('Still loading'), 'nothing is "still loading" once the lookups are in'); }

    // map card and landing
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r), d = View.dock(S);
      ok(/See the full check/.test(d) && /need attention/.test(d) && /look into/.test(d) && /couldn't check/.test(d), 'the map card shows the three counts and a clear next step');
      ok(/Probably a survey number|A map pin, not a verified plot|Matched to a surveyed plot/.test(d), 'the map card always says whether the pin is matched to a plot');
      const rp = await E.report(17.3616, 78.4747); await E.attachParcel(rp, {}); ok(/A map pin, not a verified plot/.test(View.dock(SB(rp))), 'in the old city (no survey outlines) the map card says it is only a map pin');
      const L = View.landing(S); ok(/Try an example/.test(L) && /cannot see title/.test(L), 'the landing text offers examples and states what SETHU cannot see'); }

    // identity wording never overclaims
    { const r = await E.report(17.44, 78.35); const S = SB(r); ok(/not a verified plot/.test(View.identity(r, S)), 'before matching, the identity card says "map pin, not a verified plot"');
      await E.attachParcel(r, {}); const h = View.identity(r, S); ok(!/owner|clear title|legal boundary is/i.test(strip(h).replace(/says nothing about title or ownership/, '').replace(/not legal boundaries/, '')), 'the identity card never claims ownership or clear title'); }

    // agent / insurer / compare still render, with the shared evidence layer
    { const r = await E.report(17.4401, 78.3489); await E.attachParcel(r, {}); const S = SB(r), ra = await E.report(17.3616, 78.4747);
      for (const lens of ['agent', 'insurer']) { const h = Rep.render(lens, S); ok(h.includes('The short version') && h.includes('Details by topic') && h.includes('What this check is about'), `the ${lens} view shares the same plain-language evidence layer`); }
      S.cmp = { a: r, b: ra, la: 'A', lb: 'B' }; const c = Rep.compare(S); ok(c.includes('Comparing two addresses') && !/undefined|NaN/.test(c), 'the comparison view still renders'); }
  }

