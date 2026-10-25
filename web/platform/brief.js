/* SETHU brief: the short, tappable answer that sits beside the map.
 *   1. who is asking (buyer, renter, investor, agent, lender, insurer): the same evidence, a different question and a different set of tiles
 *   2. one answer to that question, in a sentence, with the flagged topics as buttons
 *   3. topic tiles: a verdict per topic (the most serious result in it, never an average), tap to open the few facts behind it
 *   4. "How we know" on every fact: source, how recent, how local, confidence. Nothing is hidden, but nothing is shown until asked.
 * No combined score. Status is always an icon AND a word. The long evidence report stays one tap away. */
const Brief = (() => {
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const clip = (t, n) => { t = String(t == null ? '' : t); return t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t; };
  const ST = View.STATUS;
  const TST = { concern: ST.concern, watch: ST.watch, good: ST.good, partial: { word: 'Partly checked', k: 'info', glyph: '≈' }, info: ST.info, unknown: ST.unknown };
  const SEV = { concern: 4, watch: 3, unknown: 2, info: 1, good: 0 };
  const badge = lv => `<i class="v-badge b-${TST[lv].k}"><span class="v-ic">${TST[lv].glyph}</span>${TST[lv].word}</i>`;

  /* who is asking: one question each, and the topics that answer it, most important first */
  const PERSONAS = {
    buyer: { name: 'Home buyer', icon: '🏠', ask: 'Is it safe to buy here?', lens: 'customer', tiles: ['legal', 'lake', 'flood', 'water', 'move', 'life'],
      say: { bad: 'Settle these before you pay', warn: 'Worth checking before you pay', ok: 'No red flags in the public data', mute: 'Too little data to say' } },
    renter: { name: 'Renter or family', icon: '👨‍👩‍👧', ask: 'Is it a good place to live?', lens: 'customer', tiles: ['flood', 'life', 'move', 'help', 'env', 'water'],
      say: { bad: 'Think twice about these', warn: 'Fine to consider: check these first', ok: 'No red flags for living here', mute: 'Too little data to say' } },
    investor: { name: 'Investor', icon: '📈', ask: 'Does it hold up as an investment?', lens: 'customer', tiles: ['price', 'legal', 'lake', 'flood', 'growth', 'move'],
      say: { bad: 'Risks that could hurt the value', warn: 'Some risks to price in', ok: 'No big risk flags in the public data', mute: 'Too little data to say' } },
    agent: { name: 'Real estate agent', icon: '🏷️', ask: 'What will the buyer ask me?', lens: 'agent', tiles: ['pitch', 'flood', 'lake', 'legal', 'price', 'life'],
      say: { bad: 'Buyers will ask about these', warn: 'Be ready for these questions', ok: 'Few awkward questions expected', mute: 'Too little data to say' } },
    lender: { name: 'Lender or bank', icon: '🏦', ask: 'Is this sound collateral?', lens: 'customer', tiles: ['legal', 'lake', 'flood', 'price', 'help', 'env'],
      say: { bad: 'Collateral risks to resolve first', warn: 'Conditions worth attaching', ok: 'No red flags in the public data', mute: 'Too little data to say' } },
    insurer: { name: 'Insurer', icon: '🛡️', ask: 'How exposed is this location?', lens: 'insurer', tiles: ['exposure', 'flood', 'lake', 'help', 'env', 'water'],
      say: { bad: 'Higher exposure here', warn: 'Moderate exposure', ok: 'Lower exposure on public data', mute: 'Too little data to say' } }
  };
  const DEFAULT_P = 'buyer';
  const persona = S => PERSONAS[S.persona] || PERSONAS[DEFAULT_P];

  /* topics: the findings that answer each one, and the map layers worth showing when it is opened */
  const TILES = {
    flood: { icon: '🌊', title: 'Flooding', q: 'Will water get in?', layers: ['nalas', 'spots'], ids: ['sus', 'depth', 'storms', 'pocket', 'heavyrain', 'analog', 'inund', 'nala', 'nalaenc', 'stream', 'shelter'] },
    lake: { icon: '🏞️', title: 'Lakes and tanks', q: 'Is a lake or tank in the way?', layers: ['lakes', 'tanks'], ids: ['lake', 'hy', 'hmda', 'ftl', 'lost'] },
    legal: { icon: '⚖️', title: 'Land and legal', q: 'Can it be bought and built on?', layers: ['ev_lost'], ids: ['plot', 'prohib', 'overlap', 'tank_survey', 'forest', 'endow', 'planauth', 'zoning', 'perm'] },
    water: { icon: '🚰', title: 'Water and sewer', q: 'Will there be water?', layers: ['ev_wells'], ids: ['gwdepth', 'gwpre', 'gwtrend', 'gwrec', 'gwf', 'gwno3', 'gwtds', 'supply', 'supplynet', 'sewernet', 'gwp', 'tankstore'] },
    move: { icon: '🛣️', title: 'Getting around', q: 'How easy is it to get anywhere?', layers: ['metro'], ids: ['acc_hospital', 'acc_metro', 'acc_bus', 'acc_school', 'acc_market', 'road', 'choke', 'junc'] },
    life: { icon: '🏫', title: 'Everyday life', q: 'What is within reach?', layers: ['hospital', 'school'], ids: ['f_hospital', 'f_school', 'f_market', 'f_metro', 'f_bus', 'f_park', 'f_bank', 'f_jobs'] },
    help: { icon: '🚑', title: 'Emergency help', q: 'How fast can help reach you?', layers: ['hospital', 'fire'], ids: ['f_hospital', 'f_amb', 'f_fire', 'f_police', 'fire_gis', 'shelter'] },
    env: { icon: '🌡️', title: 'Air, noise and surroundings', q: 'What is it like to be there?', layers: ['ev_heat'], ids: ['air', 'noise', 'heat', 'green', 'landfill', 'tx', 'sub', 'power', 'seismic', 'seismic_gis'] },
    growth: { icon: '🏙️', title: 'What supports demand', q: 'What is being built around it?', layers: ['metro'], ids: ['f_jobs', 'acc_metro', 'f_metro', 'junc', 'road'] },
    price: { icon: '₹', title: 'Price', q: 'What do people ask here?', special: 'price' },
    pitch: { icon: '🗣️', title: 'Your pitch', q: 'What to say, and what to expect', special: 'pitch' },
    exposure: { icon: '📊', title: 'Exposure tiers', q: 'How risky is it to insure?', special: 'exposure' }
  };

  const state = (r, S) => {
    const all = View.flat(r), byId = new Map(all.map(f => [f.id, f])), T = View.tally(r, S);
    return { all, byId, loading: new Set(T.loading), T };
  };

  /* verdict of a topic = the most serious result inside it. "No issue found" needs at least as many clean checks as unanswered ones. */
  function verdict(fs, loading) {
    const live = fs.filter(f => !(loading.has(f.id) && f.level === 'unknown'));
    const n = lv => live.filter(f => f.level === lv).length, c = n('concern'), w = n('watch'), g = n('good'), u = n('unknown'), i = n('info');
    const level = c ? 'concern' : w ? 'watch' : g && u <= g ? 'good' : (g || i) && u ? 'partial' : g ? 'good' : i ? 'info' : 'unknown';
    return { level, c, w, g, u, i, n: live.length, loading: fs.length - live.length, live };
  }
  const pickTop = (list) => list.slice().sort((a, b) => (SEV[b.level] - SEV[a.level]) || (View.HIGHSET(b) - View.HIGHSET(a)))[0];

  function tileData(id, r, S, ctx) {
    const def = TILES[id];
    if (def.special === 'price') return priceTile(def, r);
    if (def.special === 'exposure') return exposureTile(def, r);
    if (def.special === 'pitch') return pitchTile(def, r, ctx);
    const fs = def.ids.map(i => ctx.byId.get(i)).filter(Boolean), v = verdict(fs, ctx.loading), known = v.live.filter(f => f.level !== 'unknown'), top = pickTop(known.length ? known : v.live);
    const line = !fs.length ? 'No checks in this topic for this address' : !v.live.length ? 'Still loading…' : `${View.title(top)}: ${clip(top.value, 64)}`;
    return { id, def, kind: 'generic', ...v, line, fs, top };
  }

  /* ---------- special topics ---------- */
  function priceTile(def, r) {
    const m = SETUE.market(r.lat, r.lon, r.wid, 'apt'), f = x => '₹' + Math.round(x).toLocaleString('en-IN');
    if (!m) return { id: 'price', def, kind: 'price', level: 'unknown', line: 'No priced locality within 4 km', body: `<p class="b-p">No portal price band within 4 km of this spot, so no price check is possible.</p>` };
    const L = m.loc, ai = L.origin === 'llm-compiled';
    return { id: 'price', def, kind: 'price', level: 'info', line: `${f(L.low)}–${f(L.high)} per sq ft · ${L.name}`, m,
      body: `<p class="b-p"><b>${f(L.low)}–${f(L.high)} per sq ft</b> is what portals ask for apartments around ${esc(L.name)} (about ${(m.d / 1000).toFixed(1)} km from this spot${L.typical ? '; typical ' + f(L.typical) : ''}).</p>
        <p class="b-p b-muted">These are asking prices, not registered deal prices${ai ? ', and this band is an AI-compiled estimate: verify it' : ''}. Confidence: ${esc(L.conf || 'low')}.</p>
        <button class="v-btn ghost sm" data-act="open-full" data-p="agent">Check a quoted price →</button>` };
  }
  const TIERLV = { A: 'good', B: 'good', C: 'watch', D: 'concern', E: 'concern' };
  function exposureTile(def, r) {
    const T = r.tiers; if (!T) return { id: 'exposure', def, kind: 'exposure', level: 'unknown', line: 'Not available here', body: '' };
    const rows = [['Motor', T.motor], ['Property', T.prop], ['Health-care access', T.health]].filter(x => x[1]);
    const lv = ['concern', 'watch', 'good'].find(l => rows.some(x => TIERLV[x[1].letter] === l)) || 'unknown';
    const L = SETUE.LOADING || {};
    return { id: 'exposure', def, kind: 'exposure', level: lv, line: rows.map(x => `${x[0]} ${x[1].letter}`).join(' · '),
      body: `<div class="b-tiers">${rows.map(x => `<div class="b-tier t${x[1].letter}"><span>${x[0]}</span><b>${x[1].letter}</b><small>${esc(L[x[1].letter] || x[1].label || '')}</small></div>`).join('')}</div>
        <p class="b-p b-muted">Tiers A (low) to E (severe), from the ward flood ranking and nearby features. Loadings are illustrative: calibrate on your own claims before pricing.</p>
        <button class="v-btn ghost sm" data-act="open-full" data-p="insurer">Open the rain-claim check →</button>` };
  }
  function pitchTile(def, r, ctx) {
    const GOODIDS = ['f_hospital', 'f_school', 'f_metro', 'acc_metro', 'f_park', 'f_jobs', 'f_market', 'air', 'heat', 'green', 'sus', 'pocket', 'lake'];
    const say = GOODIDS.map(i => ctx.byId.get(i)).filter(f => f && f.level === 'good').slice(0, 3);
    const ask = ctx.all.filter(f => (f.level === 'concern' || f.level === 'watch') && !ctx.loading.has(f.id)).sort((a, b) => SEV[b.level] - SEV[a.level]).slice(0, 4);
    const li = (f, tone) => `<li><span class="v-ic b-${tone}">${tone === 'ok' ? '✓' : '!'}</span><span><b>${esc(View.title(f))}</b><br>${esc(clip(f.value, 90))}</span></li>`;
    return { id: 'pitch', def, kind: 'pitch', level: ask.length ? (ask.some(f => f.level === 'concern') ? 'concern' : 'watch') : 'good', line: ask.length ? `${ask.length} question${ask.length > 1 ? 's' : ''} to be ready for` : 'No awkward questions in the public data',
      body: `<div class="b-two"><div><div class="b-sub">Say this</div>${say.length ? `<ul class="b-ul">${say.map(f => li(f, 'ok')).join('')}</ul>` : '<p class="b-p b-muted">No clear strengths in the data: sell on what you can show.</p>'}</div>
        <div><div class="b-sub">Be ready for</div>${ask.length ? `<ul class="b-ul">${ask.map(f => li(f, 'warn')).join('')}</ul>` : '<p class="b-p b-muted">Nothing flagged.</p>'}</div></div>
        <button class="v-btn ghost sm" data-act="open-full" data-p="agent">Open the listing brief →</button>` };
  }

  /* ---------- one fact, with its reasoning one tap away ---------- */
  function fact(f, S, tid) {
    const st = ST[f.level] || ST.info, key = `why_${tid}_${f.id}`, open = !!(S.open && (S.open[key] || S.open.b_allwhy));
    const dl = [['What this rests on', f.source], ['How recent', f.period], ['How local', f.res], ['Applies to', f.scope ? View.SCOPE_WORD[f.scope] + (f.scopeText ? ' — ' + f.scopeText : '') : ''], ['Type of evidence', View.KIND_SHORT[f.kind] || f.kind], ['Confidence', f.conf]].filter(x => x[1]);
    const links = f.links && f.links.length ? `<p class="b-p">${f.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join(' · ')}</p>` : '';
    return `<div class="b-fact lv-${f.level}"><span class="v-ic b-${st.k}" aria-hidden="true">${st.glyph}</span><div class="b-ft"><div class="b-fh"><b>${esc(View.title(f))}</b><em class="s-${st.k}">${st.word}</em></div><div class="b-fv">${esc(clip(f.value, 150))}</div>
      <details class="b-why" data-id="${key}"${open ? ' open' : ''}><summary>How we know</summary><div class="b-whyb">${f.note ? `<p class="b-p">${esc(f.note)}</p>` : ''}${links}<dl class="v-dl">${dl.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${f.next ? `<p class="b-do"><b>What to do:</b> ${esc(f.next)}</p>` : ''}</div></details></div></div>`;
  }

  function seg(t) {
    const n = Math.max(t.n || 0, 1), part = (c, k) => c ? `<i class="sg-${k}" style="flex:${c}"></i>` : '';
    return `<span class="b-seg" aria-hidden="true">${part(t.c, 'bad')}${part(t.w, 'warn')}${part(t.g, 'ok')}${part(t.u + (t.i || 0), 'mute')}</span>`;
  }

  /* ---------- a topic tile ---------- */
  function tile(t, S) {
    const def = t.def, st = TST[t.level], key = 'bt_' + t.id, open = !!(S.open && S.open[key]);
    let body;
    if (t.kind === 'generic') {
      const order = ['concern', 'watch', 'unknown', 'info', 'good'], sorted = t.fs.filter(f => !(S.loadingIds && S.loadingIds.has(f.id) && f.level === 'unknown')).sort((a, b) => order.indexOf(a.level) - order.indexOf(b.level) || (View.HIGHSET(b) - View.HIGHSET(a)));
      const main = sorted.filter(f => f.level !== 'good' || sorted.length <= 4).slice(0, 4), rest = sorted.filter(f => !main.includes(f));
      const todo = sorted.filter(f => (f.level === 'concern' || f.level === 'watch') && f.next).slice(0, 2);
      body = `<p class="b-why-t"><b>Why “${esc(st.word)}”?</b> It is the most serious result among ${t.n} checks: ${t.c} need attention, ${t.w} look into, ${t.g} came back clean, ${t.u} couldn’t be checked. A red flag is never averaged away by good results.</p>
        <div class="b-facts">${main.map(f => fact(f, S, t.id)).join('')}</div>
        ${rest.length ? `<details class="b-rest" data-id="rest_${t.id}"${S.open && S.open['rest_' + t.id] ? ' open' : ''}><summary>${rest.length} more check${rest.length > 1 ? 's' : ''} in this topic</summary><div class="b-facts">${rest.map(f => fact(f, S, t.id)).join('')}</div></details>` : ''}
        ${todo.length ? `<div class="b-act"><div class="b-sub">Do this</div>${todo.map(f => `<p>${esc(f.next)}</p>`).join('')}</div>` : ''}`;
    } else body = t.body;
    return `<details class="b-tile tl-${st.k}" data-id="${key}" data-tile="${t.id}"${open ? ' open' : ''}><summary><span class="b-tic" aria-hidden="true">${def.icon}</span><span class="b-tt"><b>${esc(def.title)}</b><small>${esc(def.q)}</small></span>${badge(t.level)}
      <span class="b-line">${esc(t.line)}</span>${t.kind === 'generic' ? seg(t) : ''}</summary><div class="b-panel">${body}</div></details>`;
  }

  /* ---------- the answer to the persona's question ---------- */
  function headline(P, tiles, S) {
    const bad = tiles.filter(t => t.level === 'concern'), warn = tiles.filter(t => t.level === 'watch'), good = tiles.filter(t => t.level === 'good'), checked = tiles.filter(t => !['unknown'].includes(t.level));
    const k = bad.length ? 'bad' : warn.length ? 'warn' : checked.length >= Math.ceil(tiles.length / 2) && good.length >= 1 ? 'ok' : 'mute';
    const flagged = (bad.length ? bad : warn).map(t => `<button type="button" class="b-flag f-${bad.length ? 'bad' : 'warn'}" data-act="b-open" data-tile="${t.id}">${esc(TILES[t.id].title)}</button>`).join('');
    const sub = k === 'bad' || k === 'warn' ? '' : k === 'ok' ? 'That is not a clearance: public data cannot show title, ownership or what a seller has not shown you.' : 'Many checks could not run here, so this says very little. Tap a topic to see what is missing.';
    return `<section class="b-head h-${k}" aria-label="The answer"><div class="v-eyebrow">${esc(P.ask)}</div><h2>${esc(P.say[k])}</h2>${flagged ? `<div class="b-flags">${flagged}</div>` : ''}${sub ? `<p class="b-p">${esc(sub)}</p>` : ''}</section>`;
  }

  /* ---------- three things to do first ---------- */
  function todo(r, S) {
    let c; try { c = SETUE.checklist(r); } catch (e) { return ''; } if (!c) return '';
    const base = 'sethu.chk.' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) + '.', store = k => { try { return localStorage.getItem(k) === '1'; } catch (e) { return false; } };
    const top = [...c.items.filter(i => i.cat === 'legal'), ...c.items.filter(i => i.cat !== 'legal'), ...c.std].slice(0, 3);
    if (!top.length) return '';
    return `<section class="b-todo" aria-label="Do these first"><div class="v-eyebrow">Do these first</div>${top.map(it => { const k = base + it.key, done = store(k), w = it.where || {};
      return `<label class="b-chk${done ? ' done' : ''}"><input type="checkbox" data-chk="${esc(k)}"${done ? ' checked' : ''}><span><b>${esc(it.action)}</b>${it.doc ? `<small>Ask for: ${esc(it.doc)}</small>` : ''}${w.name ? `<small>${w.url ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a>` : esc(w.name)}</small>` : ''}</span></label>`; }).join('')}</section>`;
  }

  const SURE = `<details class="b-sure" data-id="b_sure"><summary>How sure are we?</summary><ul>
    <li><b>The flood ranking is modest.</b> It ranks wards, not streets: 0.69 on eight past floods (0.5 is a coin flip), 0.79 against GHMC’s own waterlogging list.</li>
    <li><b>Lake and plot outlines are drawn, not legal boundaries.</b> They cannot show title, ownership or whether a lake’s legal limit reaches the plot.</li>
    <li><b>Every fact shows its source and age</b> under “How we know”. “Couldn’t check” means verify, not unsafe.</li></ul></details>`;

  /* ---------- the card beside the map ---------- */
  function who(S) {
    return `<div class="b-who" role="tablist" aria-label="Who is asking">${Object.entries(PERSONAS).map(([id, p]) => `<button type="button" role="tab" aria-selected="${S.persona === id}" class="b-pill${S.persona === id ? ' on' : ''}" data-act="persona" data-p="${id}"><span aria-hidden="true">${p.icon}</span>${esc(p.name)}</button>`).join('')}</div>`;
  }
  /* ---------- the report page: the summary first, the full report one tap below ---------- */
  function page(S) {
    const r = S.r, P = persona(S), ctx = state(r, S);
    S.loadingIds = ctx.loading;
    const tiles = P.tiles.map(id => tileData(id, r, S, ctx)), idl = View.idLine(r), allWhy = !!(S.open && S.open.b_allwhy), full = !!(S.open && S.open.fullreport);
    return `<div class="b-page"><details class="b-id t-${idl.tone}" data-id="b_id"${S.open && S.open.b_id ? ' open' : ''}><summary><span class="v-ic">${idl.glyph}</span><span>${esc(idl.text)}</span><em>Match my survey number</em></summary>${View.identity(r, S)}</details>
      ${headline(P, tiles, S)}
      <div class="b-bar"><span>Tap a topic to see what is behind it</span><button type="button" class="b-toggle${allWhy ? ' on' : ''}" data-act="b-why" aria-pressed="${allWhy}">${allWhy ? 'Hide' : 'Show'} the reasoning</button></div>
      <div class="b-grid">${tiles.map(t => tile(t, S)).join('')}</div>
      ${todo(r, S)}
      ${full ? `<section class="b-full" id="fullreport" aria-label="Full report"><div class="b-fullh"><div><div class="v-eyebrow">Full report</div><h2>Every check, with its evidence</h2></div><button type="button" class="v-btn ghost sm" data-act="full">Hide the full report ↑</button></div>${Reports.render(P.lens, S)}</section>`
        : `<section class="b-fullcta"><button type="button" class="v-btn big" data-act="full">View the full report ↓</button><p class="v-small">Every check with its source, plus charts, official records and the cost calculator.</p></section>`}
      ${SURE}<p class="v-small">Built from public map data. Not legal, valuation or insurance advice.</p></div>`;
  }

  /* ---------- the card beside the map: just the place, and who is asking ---------- */
  function dock(S) {
    const r = S.r, P = persona(S), title = S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : r.ward.name, idl = View.idLine(r);
    return `<div class="v-panel scroll b-dock"><div class="v-eyebrow">Selected place</div><h2 class="v-dh">${esc(title)}</h2><div class="v-sub">${esc(r.ward.name)}${S.address ? ' · ' + esc(S.address) : ''}${r.outside ? ' · outside the 145 wards' : ''}</div>
      <div class="v-idchip t-${idl.tone}"><span class="v-ic">${idl.glyph}</span>${esc(idl.text)}</div>
      <div class="v-eyebrow b-iam">I am a…</div>${who(S)}
      <button class="v-btn big" data-act="open" data-lens="${S.persona}">View report →</button>
      ${S.cmpPending ? `<div class="v-wait"><b>Pick the second address.</b> Search above or click the map to compare it with ${esc(title)}. <button class="v-btn ghost sm" data-act="cmp-cancel">Cancel</button></div>` : `<div class="b-links"><button class="v-link" data-act="cmp-start">⇄ Compare with another address</button></div>`}
      <p class="v-small">${esc(P.ask)} Built from public map data. Not legal, valuation or insurance advice.</p></div>`;
  }

  /* ---------- before any place is picked: the goal, and who is asking ---------- */
  function landing(S) {
    return `<div class="v-panel scroll b-dock"><h1 class="v-h1">Check an address <em>before</em> you pay.</h1>
      <p class="v-lead">Flood, lake, land and legal flags for any Hyderabad address, from public data, in a few taps.</p>
      <div class="v-eyebrow">I am a…</div><div class="b-cards">${Object.entries(PERSONAS).map(([id, p]) => `<button type="button" class="b-card${S.persona === id ? ' on' : ''}" data-act="persona" data-p="${id}" aria-pressed="${S.persona === id}"><span class="b-ci" aria-hidden="true">${p.icon}</span><b>${esc(p.name)}</b><small>${esc(p.ask)}</small></button>`).join('')}</div>
      <div class="v-eyebrow">Now pick a spot</div><p class="v-small b-first">Search above, tap the map, or paste a Google Maps link. Or try:</p>
      <div class="v-ex">${(typeof PLACES !== 'undefined' ? PLACES : []).slice(0, 6).map((p, i) => `<button class="v-pill" data-act="place" data-i="${i}">${esc(p[0])}</button>`).join('')}</div>
      <details class="b-sure" data-id="b_can"><summary>What it can and can’t tell you</summary><ul>
        <li><b>It can</b> flag flooding, nearby lakes and tanks, land-record warnings, water, roads and what is within reach.</li>
        <li><b>It can’t</b> see title, ownership, loans or court cases, or say that a place is safe. Every answer shows how it was derived, when you ask.</li></ul></details>
      ${SURE}</div>`;
  }

  return { dock, page, landing, PERSONAS, TILES, DEFAULT_P, tileData, verdict, headline, state, who };
})();
