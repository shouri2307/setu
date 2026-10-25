/* SETHU view layer: what a buyer sees. One story per address:
 *   1. what this check is about (a map pin, or a matched survey outline)
 *   2. the short version: needs attention / look into / no issue found / could not be checked
 *   3. what to do before paying
 *   4. details by topic, each finding in plain words with its source one click away
 * No combined score. Status is always an icon AND a word, never colour alone. */
const View = (() => {
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  /* ---------- plain-language vocabulary ---------- */
  const STATUS = {
    concern: { word: 'Needs attention', k: 'bad', glyph: '!' }, watch: { word: 'Look into', k: 'warn', glyph: '!' }, good: { word: 'No issue found', k: 'ok', glyph: '✓' },
    info: { word: 'For your information', k: 'info', glyph: 'i' }, unknown: { word: "Couldn't check", k: 'mute', glyph: '?' }
  };
  const RATING = { Concern: 'concern', Watch: 'watch', Good: 'good', Unknown: 'unknown' };
  const TOPICS = [   // display order puts the legal and land questions first: they decide a purchase
    { id: 'land', icon: '⚖️', title: 'Land, legal & planning', blurb: 'Which plot this is, what plan applies, and whether a map flags a problem with the land.' },
    { id: 'hazards', icon: '🌊', title: 'Flooding & other hazards', blurb: 'How this spot behaves in heavy rain, plus heat, earthquakes and nearby lakes and drains.' },
    { id: 'water', icon: '💧', title: 'Water & sewer', blurb: 'Groundwater, water quality, and whether public water and sewer lines are mapped nearby.' },
    { id: 'infra', icon: '🛣️', title: 'Roads, power & getting around', blurb: 'Drive times, traffic points, power lines, noise, air and waste.' },
    { id: 'live', icon: '🏠', title: 'Everyday life', blurb: 'Hospitals, schools, shops, transit and parks within reach.' }
  ];
  const PLAIN = {
    sus: 'Flood risk of this ward', depth: 'Water depth in a very big storm', storms: 'Flooding named here in past storms', heavyrain: 'How often very heavy rain falls', analog: 'Past storms most like a major one', pocket: 'Is the spot lower than its surroundings?',
    lake: 'Lake or tank close by', nala: 'Drain (nala) close by', nalaenc: 'Encroachment on the nearest drain', stream: 'Natural stream channel nearby', inund: 'Officially listed waterlogging spot', hy: 'Nearest tank: encroached or not', hmda: 'Lake notification status',
    heat: 'How hot this area gets in summer', green: 'Trees and greenery', seismic: 'Earthquake zone', shelter: 'Flood relief centres nearby',
    gw: 'Groundwater depth', gwnear: 'Nearest groundwater well', gwdepth: 'Groundwater depth around here', gwpre: 'Groundwater at the end of summer', gwrec: 'Does groundwater recover after the rains?', gwtrend: 'Is groundwater falling over the years?', gwcov: 'How well groundwater is monitored here',
    gwq: 'Groundwater quality', gwf: 'Fluoride in nearby groundwater', gwno3: 'Nitrate in nearby groundwater', gwtds: 'Salt in nearby groundwater', aq: 'Rock type that holds the water', lakewq: 'Water quality of the nearest lake', stp: 'Sewage plant nearby',
    gwp: 'How well the ground here holds water', tankstore: 'Water stored in nearby tanks', supply: 'Tap water connection and supply hours', supplynet: 'Public water pipe on the map nearby', sewernet: 'Public sewer line on the map nearby',
    road: 'Distance to a main road', acc_hospital: 'Drive to a hospital', acc_metro: 'Drive to a metro or rail station', acc_bus: 'Drive to a bus stop', acc_school: 'Drive to a school', acc_market: 'Drive to a market',
    choke: 'Traffic jam points nearby', junc: 'Planned junction improvement', power: 'Power cuts (old record)', tx: 'High-voltage line nearby', sub: 'Electricity substation nearby', landfill: 'Garbage dump nearby', noise: 'Noise (old record)', air: 'Air quality right now',
    f_hospital: 'Hospital nearby', f_school: 'School nearby', f_market: 'Market nearby', f_metro: 'Metro or rail station nearby', f_bus: 'Bus station nearby', f_park: 'Park nearby', f_bank: 'Bank nearby', f_police: 'Police station nearby', f_fire: 'Fire station nearby', f_amb: '108 ambulance station', f_jobs: 'Jobs, malls and cinemas nearby',
    tank_survey: 'Tank survey number near this pin', fire_gis: 'Fire station on the state list', seismic_gis: 'Earthquake zone on the state map',
    lost: 'Built where a lake used to be?', forest: 'Forest land nearby', endow: 'Temple (endowment) land nearby', plot: 'Which plot is this?', prohib: 'Listed as restricted land?', planauth: 'Which official plan applies', zoning: 'What the land is zoned for',
    perm: 'Approved layout or building permission', overlap: 'Does the plot touch a lake, tank or forest?', ftl: 'Lake buffer (FTL) risk', widen: 'Planned drain widening', price: 'Typical asking price'
  };
  const SCOPE_WORD = { pin: 'the pin position', parcel: 'the matched plot outline', nearby: 'places near the pin', area: 'an area estimate', ward: 'the whole ward', mandal: 'the whole mandal', locality: 'the locality', region: 'the whole city', live: 'live data', none: 'nothing (no data)' };
  const KIND_SHORT = { observed: 'Measured', official: 'Official record', modelled: 'Model', estimate: 'Estimate', indicative: 'Open-map hint', reference: 'Reference', unavailable: 'Not available' };
  const LOADING_IDS = id => id.startsWith('acc_') ? 'travel times' : id === 'air' ? 'air quality' : id === 'pocket' ? 'terrain' : null;   // fetched live: unknown while loading is not a gap
  const title = f => PLAIN[f.id] || f.label;
  const badge = k => `<i class="v-badge b-${STATUS[k].k}"><span class="v-ic">${STATUS[k].glyph}</span>${STATUS[k].word}</i>`;
  const flat = r => r.ev.sections.flatMap(s => s.findings.map(f => ({ ...f, sec: s.id })));
  const isHigh = f => SETUE.HIGH.has(f.id);
  const byWeight = (a, b) => (isHigh(b) - isHigh(a)) || 0;
  const MISMATCH = new Set(['number-mismatch', 'neighbour', 'village-mismatch']);   // only these mean "your number does not fit the pin"
  const label = r => r.label || '';

  /* ---------- the counts that drive both the map card and the report summary ---------- */
  function tally(r, S) {
    const all = flat(r), loading = new Set();
    if (!S.access) all.forEach(f => { if (f.id.startsWith('acc_') && f.level === 'unknown') loading.add(f.id); });
    if (!S.air && all.some(f => f.id === 'air' && f.level === 'unknown')) loading.add('air');
    if (!S.terrain && !r.outside && all.some(f => f.id === 'pocket' && f.level === 'unknown')) loading.add('pocket');
    const pick = lv => all.filter(f => f.level === lv && !loading.has(f.id)).sort(byWeight);
    const T = { concern: pick('concern'), watch: pick('watch'), good: pick('good'), unknown: pick('unknown'), loading: [...loading], all };
    return T;
  }

  /* ---------- identity: a map pin is never called a plot ---------- */
  function identity(r, S) {
    const id = r.ev.identity, p = (S && S.pref) || {}, m = r.parcel && r.parcel.match;
    const tone = id.status === 'none' ? (MISMATCH.has(id.reason) ? 'bad' : 'mute') : ({ verified: 'ok', approximate: 'warn', unavailable: 'mute', pending: 'mute' }[id.status] || 'mute');   // red only for a real mismatch; a gap in the map is missing data
    const head = id.status === 'verified' ? 'Matched to a surveyed plot outline' : id.status === 'approximate' ? 'Probably this survey number: please confirm' : id.status === 'none' ? (MISMATCH.has(id.reason) ? 'The pin does not match the survey number you entered' : id.reason === 'on-feature' ? 'The pin is on a road, canal or tank, not on a plot' : 'The pin is not on a mapped survey plot')
      : id.status === 'unavailable' ? 'This report is about a map pin: survey outlines are not available here' : 'This report is about a map pin, not a verified plot';
    const cand = m && m.candidates && m.candidates.length > 1 ? `<div class="v-cand"><b>The pin could be on:</b> ${m.candidates.map(c => `<button type="button" class="v-pill" data-act="parcel-pick" data-n="${esc(c.number)}" data-v="${esc(c.village)}">Sy. ${esc(c.number)} · ${esc(c.village)}${c.d ? ' · ' + c.d + ' m away' : ''}</button>`).join(' ')}</div>` : '';
    const area = id.parcel && id.parcel.areaM2 ? ` The mapped outline covers about ${id.parcel.areaM2 >= 10000 ? (id.parcel.areaM2 / 10000).toFixed(2) + ' hectares' : id.parcel.areaM2.toLocaleString('en-IN') + ' m²'}.` : '';
    const field = (k, lab, ph) => `<label class="v-fld"><span>${lab}</span><input data-bind="pref.${k}" value="${esc(p[k] || '')}" placeholder="${esc(ph)}" autocomplete="off"></label>`;
    const rec = ['plot', 'layout', 'doc'].filter(k => p[k]).map(k => ({ plot: 'plot/flat', layout: 'layout (LP) no.', doc: 'document no.' }[k] + ' ' + esc(p[k]))).join(' · ');
    return `<section class="v-card v-id id-${tone}" aria-label="What this check is about">
      <div class="v-idtop"><span class="v-idic">${tone === 'ok' ? '✓' : tone === 'bad' ? '!' : tone === 'warn' ? '≈' : '📍'}</span><div><div class="v-eyebrow">What this check is about</div><h2>${esc(head)}</h2></div></div>
      <p class="v-lead">${esc(id.text)}${area}</p>${cand}
      <div class="v-idform"><div class="v-idrow">${field('survey', 'Survey number (Sy. No.)', 'e.g. 91/1')}${field('village', 'Village or colony', 'as written on your deed')}
        <div class="v-idbtn"><button type="button" class="v-btn" data-act="parcel-match">Match</button></div></div>
        <details class="more v-more" data-id="idmore"${rec || p.plot || p.layout || p.doc ? ' open' : ''}><summary>Add other references from your documents</summary>
          <div class="v-idrow">${field('plot', 'Plot or flat number', 'recorded only')}${field('layout', 'Layout (LP) number', 'recorded only')}${field('doc', 'Document number', 'deed / EC number')}<div class="v-idbtn"><button type="button" class="v-btn ghost" data-act="parcel-clear">Clear all</button></div></div>
          ${rec ? `<p class="v-small">You recorded: ${rec}. These are shown as you typed them. SETU does not check them.</p>` : ''}</details></div>
      <p class="v-small">Only the survey number and village are checked, against the state's drawn survey outlines. An outline is not a legal boundary and says nothing about title or ownership. Nothing you type leaves this device or goes into the link.</p></section>`;
  }

  /* ---------- the short version ---------- */
  const clip = (t, n = 140) => { t = String(t == null ? '' : t); return t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t; };
  function item(f, why) { return `<button type="button" class="v-item" data-act="jump" data-id="${esc(f.id)}" data-sec="${esc(f.sec)}"><span class="v-it">${esc(title(f))}</span><span class="v-iv">${esc(clip(why ? why : f.value))}</span></button>`; }
  function shortVersion(r, S) {
    const T = tally(r, S), nA = T.concern.length, nW = T.watch.length, nG = T.good.length, nU = T.unknown.length;
    const head = nA ? 'A few things need attention before you pay anything.' : nW ? 'Nothing alarming turned up, but some things are worth looking into.' : 'No red flags in the public data we could read.';
    const sub = nA || nW ? 'Each item below opens its details. None of this is a legal finding.' : 'That is not a clearance: the items we could not check still need checking, and public data cannot show title or ownership.';
    const col = (key, cls, hd, list, max, why) => `<div class="v-col c-${cls}"><div class="v-colh">${badge(key)}<b>${list.length}</b></div>${list.length ? list.slice(0, max).map(f => item(f, why && why(f))).join('') + (list.length > max ? `<button type="button" class="v-more-btn" data-act="open-topic" data-sec="all">+ ${list.length - max} more in the details below</button>` : '') : `<div class="v-none">${hd}</div>`}</div>`;
    const gapWhy = f => { const q = SETUE.D.quality && SETUE.D.quality.factors[f.id]; return (q && q.missing) || f.value; };
    return `<section class="v-card v-short" aria-label="The short version"><div class="v-eyebrow">The short version</div><h2>${esc(head)}</h2><p class="v-lead">${esc(sub)}</p>
      <div class="v-counts"><span class="n-bad"><b>${nA}</b> need attention</span><span class="n-warn"><b>${nW}</b> to look into</span><span class="n-ok"><b>${nG}</b> no issue found</span><span class="n-mute"><b>${nU}</b> couldn't be checked</span></div>
      <div class="v-cols">${col('concern', 'bad', 'Nothing flagged as needing attention.', T.concern, 5)}${col('watch', 'warn', 'Nothing to look into.', T.watch, 5)}${col('good', 'ok', 'No check has run clean yet.', T.good, 5)}${col('unknown', 'mute', 'Everything could be checked.', T.unknown, 5, gapWhy)}</div>
      ${T.loading.length ? `<p class="v-small"><span class="spin"></span> Still loading: ${esc(T.loading.map(LOADING_IDS).filter((x, i, a) => x && a.indexOf(x) === i).join(', '))}.</p>` : ''}</section>`;
  }

  /* ---------- before you pay ---------- */
  const chkStore = key => { try { return localStorage.getItem(key) === '1'; } catch (e) { return false; } };
  function beforePay(r, S) {
    const c = SETUE.checklist(r), base = 'sethu.chk.' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) + '.', all = [...c.items, ...c.std];
    const top = [...c.items.filter(i => i.cat === 'legal'), ...c.items.filter(i => i.cat !== 'legal'), ...c.std].slice(0, 5);
    const row = it => { const k = base + it.key, done = chkStore(k), w = it.where || {};
      return `<label class="v-chk${done ? ' done' : ''}"><input type="checkbox" data-chk="${esc(k)}"${done ? ' checked' : ''}><span class="v-cb"><b>${esc(it.action)}</b>
        <span class="v-cwhy">${esc(it.why)}</span>${it.doc ? `<span class="v-cdoc">Ask for: ${esc(it.doc)}</span>` : ''}
        <span class="v-cwh">${w.url ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a>` : esc(w.name || '')}${w.status ? ` <small>· ${esc(w.status)}</small>` : ''}</span></span></label>`; };
    const done = all.filter(it => chkStore(base + it.key)).length;
    return `<section class="v-card v-pay" aria-label="Before you pay"><div class="v-eyebrow">Before you pay</div><h2>${top.length} things to do first</h2>
      <p class="v-lead">Chosen from what this check found. Ticks are saved on this device only.</p><div class="v-chkprog">${done} of ${all.length} steps ticked</div>${top.map(row).join('')}
      ${all.length > top.length ? `<details class="more v-more" data-id="chk_all"><summary>Show all ${all.length} steps</summary>${all.filter(i => !top.includes(i)).map(row).join('')}</details>` : ''}
      <p class="v-small"><b>"Couldn't check" means verify, not unsafe.</b> We only name an office or portal when we actually reached it; otherwise it says "not verified".</p></section>`;
  }

  /* ---------- details by topic ---------- */
  function row(f, S) {
    const st = STATUS[f.level] || STATUS.info, open = S.open && S.open['fd_' + f.id];
    const links = f.links && f.links.length ? `<div class="v-links">${f.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join('<br>')}</div>` : '';
    const dl = [['What this rests on', f.source], ['How recent', f.period], ['How local', f.res], ['Applies to', f.scope ? SCOPE_WORD[f.scope] + (f.scopeText ? ' — ' + f.scopeText : '') : ''], ['Type of evidence', (SETUE.KIND_LABEL[f.kind] || f.kind)], ['Confidence', f.conf]].filter(x => x[1]);
    return `<div class="v-f lv-${f.level}" id="f_${esc(f.id)}"><span class="v-ic big b-${st.k}" aria-hidden="true">${st.glyph}</span>
      <div class="v-fm"><div class="v-fhead"><span class="v-ft">${esc(title(f))}</span><span class="v-fstat s-${st.k}">${st.word}</span></div>
        <div class="v-fv">${esc(f.value)}</div>
        <div class="v-chips"><span class="v-chip">${esc(KIND_SHORT[f.kind] || f.kind)}</span>${f.scope ? `<span class="v-chip sc-${f.scope}">${f.scope === 'none' ? 'No data available' : 'Applies to ' + esc(SCOPE_WORD[f.scope] || f.scope)}</span>` : ''}${f.conf === 'low' ? '<span class="v-chip warn">Low confidence</span>' : ''}</div>
        <details class="more v-fd" data-id="fd_${esc(f.id)}"${open ? ' open' : ''}><summary>Details and source</summary>
          ${f.note ? `<p class="v-fn">${esc(f.note)}</p>` : ''}${links}
          <dl class="v-dl">${dl.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
          ${f.next ? `<p class="v-next"><b>What to do:</b> ${esc(f.next)}</p>` : ''}</details></div></div>`;
  }
  function topics(r, S) {
    const ev = r.ev, secs = Object.fromEntries(ev.sections.map(s => [s.id, s]));
    return `<section class="v-topics" aria-label="Details by topic"><div class="v-eyebrow">Details by topic</div><h2>Everything we found, in order of what matters to a buyer</h2>
      ${TOPICS.map(t => {
        const s = secs[t.id]; if (!s) return '';
        const c = s.counts, lv = RATING[s.rating] || 'unknown', key = 'tp_' + t.id, def = !!(c.concern || c.watch), open = S.open && S.open[key] !== undefined ? S.open[key] : def;
        const fs = s.findings.slice().sort((a, b) => ['concern', 'watch', 'unknown', 'info', 'good'].indexOf(a.level) - ['concern', 'watch', 'unknown', 'info', 'good'].indexOf(b.level));
        const extra = t.id === 'live' ? lifeScore(r) : '';
        return `<details class="more v-topic t-${STATUS[lv].k}" data-id="${key}" id="topic_${t.id}"${open ? ' open' : ''}><summary><span class="v-ticon" aria-hidden="true">${t.icon}</span>
          <span class="v-tt"><b>${t.title}</b><small>${esc(t.blurb)}</small></span><span class="v-tr">${badge(lv)}<small>${c.concern} need attention · ${c.watch} look into · ${c.good} fine · ${c.unknown} couldn't check</small></span></summary>
          <div class="v-tbody">${fs.map(f => row({ ...f, sec: s.id }, S)).join('')}${extra}</div></details>`;
      }).join('')}</section>`;
  }
  function lifeScore(r) {
    const P = r.pillars; if (!P) return '';
    const nm = a => a.map(x => x.label.toLowerCase()).join(', ');
    return `<details class="more v-fd v-life" data-id="lifescore"><summary>Convenience score: ${P.score}/100 (${esc(P.label)}) — about everyday convenience, not safety</summary>
      <div class="v-bars">${P.items.filter(it => it.v != null).map(it => { const pct = Math.round(it.v * 100); return `<div class="v-bar"><span>${esc(it.label)}</span><div><i style="width:${pct}%" class="${it.v >= .75 ? 'ok' : it.v >= .5 ? 'warn' : 'bad'}"></i></div><b>${pct}</b></div>`; }).join('')}</div>
      <p class="v-small">Strongest: ${esc(nm(P.best))}. Weakest: ${esc(nm(P.worst))}. Higher is better. It describes the surroundings; it is not a valuation and not a flood or legal rating.</p></details>`;
  }

  /* ---------- the card beside the map ---------- */
  function dock(S) {
    const r = S.r, tl = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name, T = tally(r, S), id = r.ev.identity;
    const tone = id.status === 'none' ? (MISMATCH.has(id.reason) ? 'bad' : 'mute') : ({ verified: 'ok', approximate: 'warn' }[id.status] || 'mute');
    const idText = id.status === 'verified' ? 'Matched to a surveyed plot outline' : id.status === 'approximate' ? 'Probably a survey number: confirm in the check' : id.status === 'none' ? (MISMATCH.has(id.reason) ? 'Does not match the survey number entered' : id.reason === 'on-feature' ? 'On a road, canal or tank, not a plot' : 'Not on a mapped survey plot') : 'A map pin, not a verified plot';
    const top = [...T.concern, ...T.watch].slice(0, 3);
    return `<div class="v-panel scroll"><div class="v-eyebrow">Selected place</div><h2 class="v-dh">${esc(tl)}</h2><div class="v-sub">${esc(r.ward.name)}${S.address ? ' · ' + esc(S.address) : ''}${r.outside ? ' · outside the 145 wards' : ''}</div>
      <div class="v-idchip t-${tone}"><span class="v-ic">${tone === 'ok' ? '✓' : tone === 'bad' ? '!' : tone === 'warn' ? '≈' : '📍'}</span>${esc(idText)}</div>
      <div class="v-dcounts"><div class="n-bad"><b>${T.concern.length}</b><span>need attention</span></div><div class="n-warn"><b>${T.watch.length}</b><span>look into</span></div><div class="n-mute"><b>${T.unknown.length}</b><span>couldn't check</span></div></div>
      ${top.length ? `<div class="v-dtop"><div class="v-eyebrow">Biggest things to know</div>${top.map(f => `<div class="v-dline lv-${f.level}"><span class="v-ic b-${STATUS[f.level].k}">${STATUS[f.level].glyph}</span><span><b>${esc(title(f))}</b><br>${esc(f.value.length > 90 ? f.value.slice(0, 87) + '…' : f.value)}</span></div>`).join('')}</div>`
        : `<p class="v-lead">No red flags in the public data we could read. The things we couldn't check still need checking.</p>`}
      <button class="v-btn big" data-act="open" data-lens="customer">See the full check →</button>
      <div class="v-dalso">${S.cmpPending ? `<div class="v-wait"><b>Pick the second address.</b> Search above or click the map to compare it with ${esc(tl)}. <button class="v-btn ghost sm" data-act="cmp-cancel">Cancel</button></div>` : `<button class="v-btn ghost sm" data-act="cmp-start">⇄ Compare with another address</button>`}
        <span>Other views:</span><button class="v-link" data-act="open" data-lens="agent">For agents</button><button class="v-link" data-act="open" data-lens="insurer">For insurers</button></div>
      <p class="v-small">Built from public map data. Not legal, valuation or insurance advice.</p></div>`;
  }
  function landing(S) {
    const poi = (SETUE.D.geo && SETUE.D.geo.poi) || {}, n = k => (poi[k] || []).length;
    const stat = (v, l) => `<div><b>${v}</b><span>${l}</span></div>`;
    return `<div class="v-panel scroll"><h1 class="v-h1">Check an address <em>before</em> you buy it.</h1>
      <p class="v-lead big">Search a place or tap the map. You get a plain-language check of flooding, land and legal flags, water, roads and everyday life, plus what to do before you pay.</p>
      <ol class="v-steps"><li><b>Pick a spot</b><span>Search above, tap the map, or paste a Google Maps link.</span></li><li><b>Read the short version</b><span>What needs attention, what looks fine, what couldn't be checked.</span></li><li><b>Follow the checklist</b><span>The papers to ask for and the offices to ask.</span></li></ol>
      <div class="v-eyebrow">Try an example</div><div class="v-ex">${(typeof PLACES !== 'undefined' ? PLACES : []).slice(0, 6).map((p, i) => `<button class="v-pill" data-act="place" data-i="${i}">${esc(p[0])}</button>`).join('')}</div>
      <div class="v-proof">${stat('145', 'wards')}${stat(Math.floor(n('hospital') / 100) * 100 + '+', 'hospitals mapped')}${stat('8', 'real floods tested')}${stat(String(Object.keys((SETUE.D.quality || { factors: {} }).factors).length || '70'), 'checks per address')}</div>
      <p class="v-small">SETHU reads public data only. It cannot see title, ownership or what a seller has not shown you.</p></div>`;
  }
  /* the one-line "what is this check about" used by the brief */
  function idLine(r) {
    const id = r.ev.identity, tone = id.status === 'none' ? (MISMATCH.has(id.reason) ? 'bad' : 'mute') : ({ verified: 'ok', approximate: 'warn' }[id.status] || 'mute');
    const text = id.status === 'verified' ? 'Matched to a surveyed plot outline' : id.status === 'approximate' ? 'Probably this survey number: confirm it' : id.status === 'none' ? (MISMATCH.has(id.reason) ? 'Does not match the survey number entered' : id.reason === 'on-feature' ? 'On a road, canal or tank, not a plot' : 'Not on a mapped survey plot') : 'A map pin, not a verified plot';
    return { tone, text, glyph: tone === 'ok' ? '✓' : tone === 'bad' ? '!' : tone === 'warn' ? '≈' : '📍' };
  }
  const HIGHSET = f => isHigh(f) ? 1 : 0;
  return { dock, landing, identity, shortVersion, beforePay, topics, tally, title, badge, STATUS, TOPICS, PLAIN, flat, idLine, HIGHSET, SCOPE_WORD, KIND_SHORT };
})();
