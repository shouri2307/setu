/* Three separate, full-page reports built from the same engine report:
 *   customer  — "Is it safe to buy here, and what will it really cost?"
 *   agent     — real estate agent: "Market band, evidence and a client-ready brief"
 *   insurer   — "Exposure tiers, claim evidence check, API-ready JSON"            */
const Reports = (() => {
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const fmtKm = m => m == null ? '—' : m < 950 ? Math.round(m / 10) * 10 + ' m' : (m / 1000).toFixed(1) + ' km';
  const inr = n => n >= 1e7 ? '₹' + (n / 1e7).toFixed(2) + ' Cr' : n >= 1e5 ? '₹' + (n / 1e5).toFixed(1) + ' L' : '₹' + Math.round(n).toLocaleString('en-IN');
  const inrFull = n => '₹' + Math.round(n).toLocaleString('en-IN');
  const ICON = { hospital: '🏥', school: '🏫', metro: '🚇', market: '🛒', bank: '🏦', park: '🌳', bus: '🚌', fire: '🚒', police: '👮' };
  const CUTS = { water: [18, 32, 46, 60], motor: [20, 30, 42, 54], prop: [16, 26, 38, 50], health: [20, 32, 44, 56] };
  const TNAME = { A: 'Low', B: 'Guarded', C: 'Moderate', D: 'High', E: 'Severe' };

  const srcBadge = r => r.source === 'google'
    ? '<span class="srcbadge"><i></i>Facilities: Google Places</span>'
    : '<span class="srcbadge"><i></i>Facilities: OpenStreetMap + Overture Maps (open data)</span>';

  function factorRows(parts, good) {
    return parts.map(p => p.v == null
      ? `<div class="frow"><div class="t"><span>${esc(p.label)}</span><span class="st ${p.status}">${p.status}</span></div><div class="n">${esc(p.note)}</div></div>`
      : `<div class="frow"><div class="t"><span>${esc(p.label)}</span><span class="st ${p.status}">${p.status}</span></div>
         <div class="bar${good ? ' good' : ''}"><i style="width:${Math.round(p.v * 100)}%"></i></div>
         <div class="n">${esc(p.note)} · <em>weight ${Math.round(p.wn * 100)}% → ${p.pts.toFixed(0)} pts</em></div></div>`).join('') +
      `<div class="legend-note"><b>validated</b> = from the flood model tested on floods it never saw · <b>modelled</b> = model output under a stated assumption · <b>indicative</b> = map-data proximity, not an official or legal status · <b>official</b> = from public government GIS records (currency not stated).</div>`;
  }
  function flagList(flags) {
    const ic = { red: '⛔', amber: '⚠️', green: '✅' };
    return flags.map(f => `<div class="flag"><div class="ic ${f.lvl}">${ic[f.lvl]}</div><div><b>${esc(f.t)}</b><p>${esc(f.d)}</p></div></div>`).join('');
  }
  function facList(r) {
    return SETUE.FAC.map(([k, label]) => {
      const f = r.fac[k];
      if (!f.nearest) return `<div class="fac"><span class="ic">${ICON[k]}</span><span class="a">${label}</span><span class="d">—</span><span class="n">none found nearby</span></div>`;
      return `<div class="fac"><span class="ic">${ICON[k]}</span><span class="a">${esc(f.nearest.name || label)}</span><span class="d tnum">${fmtKm(f.nearest.d)}</span>
        <span class="n">${label} · ${f.n1km}${f.capped ? '+' : ''} within 1 km · ${f.n2km}${f.capped ? '+' : ''} within 2 km</span></div>`;
    }).join('');
  }
  const tierCard = (label, t, line, extra) => `<div class="tier"><div class="l">${label}</div><div class="big t${t.letter}">${t.letter}</div><div class="t">${t.label} · ${t.score}/100</div><div class="x">${extra || ''}</div></div>`;
  const kpi = (l, v, t, c) => `<div class="kpi"><div class="l">${l}</div><div class="v" style="${c ? 'color:' + c : ''}">${v}</div><small>${t || ''}</small></div>`;
  function govCard(r) {
    const G = r.gov, d = m => m == null ? '—' : fmtKm(m);
    const widen = G.seg ? (G.seg.prop_w > (G.seg.ext_w || 0) * 1.5 ? `${G.seg.ext_w} m now → ${G.seg.prop_w} m proposed` : `${G.seg.ext_w} m existing · ${G.seg.prop_w} m proposed`) : null;
    return `<div class="card"><h3>Official drainage records <span class="st official">government GIS</span></h3><div class="lead">From the Telangana State GIS service for GHMC nalas and the vulnerability map — the drains data the city publishes.</div>
      <div class="kv"><span class="k">Nearest mapped nala</span><span class="v">${G.nala ? esc(G.nala.name) + ' · ' + d(G.nala.d) : 'none within 1.5 km'}</span></div>
      ${G.nala && (String(G.nala.circle || '').trim() || G.nala.len_m) ? `<div class="kv"><span class="k">GHMC circle · nala length</span><span class="v">${[String(G.nala.circle || '').trim(), G.nala.len_m ? (G.nala.len_m / 1000).toFixed(1) + ' km' : ''].filter(Boolean).map(esc).join(' · ')}</span></div>` : ''}
      ${widen ? `<div class="kv"><span class="k">Nala width (nearest segment)</span><span class="v">${esc(widen)}</span></div>` : ''}
      <div class="kv"><span class="k">Nearest mapped drain / canal</span><span class="v">${d(G.drainNearM)}${G.drains150 ? ' · ' + G.drains150 + ' within 150 m' : ''}</span></div>
      <div class="kv"><span class="k">Official tank outline</span><span class="v">${G.tank ? (G.tank.inside ? 'inside a mapped tank' : d(G.tank.d)) : 'none nearby'}</span></div>
      <div class="kv"><span class="k">River / stream (e.g. Musi)</span><span class="v">${G.river ? (G.river.inside ? 'inside the mapped channel' : d(G.river.d)) : 'none nearby'}</span></div>
      <div class="kv"><span class="k">Nearest tank (HYDRAA / TGRAC)</span><span class="v">${r.hy ? esc(r.hy.display || 'unnamed tank') + (r.hy.village ? ' · ' + esc(r.hy.village) : '') + ' · ' + (r.hy.inside ? 'under this pin' : d(r.hy.d)) : 'none within 3 km'}</span></div>
      ${r.hy && r.hy.nameDiffers ? `<div class="kv"><span class="k">Name in the government layer</span><span class="v">${esc(r.hy.govLabel)} <span class="sub" style="font-size:12.5px">(differs from the map name — treat as a labelling quirk)</span></span></div>` : ''}
      ${r.hy ? `<div class="kv"><span class="k">Satellite status 2023 · 2014</span><span class="v" style="color:${r.hy.s23 === 'L' ? 'var(--a)' : r.hy.s23 === 'PA' || r.hy.s23 === 'PB' ? 'var(--d)' : 'var(--e)'}">${esc(SETUE.HY_LABEL[r.hy.s23])} · ${esc(SETUE.HY_LABEL[r.hy.s14])}</span></div>
      <div class="kv"><span class="k">Encroached tanks within 500 m</span><span class="v tnum">${r.hy.enc500}</span></div>` : ''}
      <div class="kv"><span class="k">Nearest listed inundation area</span><span class="v">${G.inund ? esc(G.inund.name.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())) + ' · ' + d(G.inund.d) : 'none within 3 km'}</span></div>
      <div class="kv"><span class="k">Listed inundation areas within 1 km</span><span class="v tnum">${G.inund1k}</span></div>
      <div class="kv"><span class="k">HMDA lake notification</span><span class="v" style="max-width:62%">${r.hmda ? esc(SETUE.hmdaText(r.hmda).replace(/^HMDA's lake portal lists /, '')) + (SETUE.hmdaLink(r.hmda) ? ` · <a href="${esc(SETUE.hmdaLink(r.hmda))}" target="_blank" rel="noopener">official FTL map (PDF)</a>` : '') : (r.water.lake && r.water.lake.name ? 'no unambiguous match for ' + esc(r.water.lake.name) + ' — check the portal' : 'no named lake nearby')}</span></div>
      <div class="legend-note">Tank status is HYDRAA / TGRAC's satellite classification (2014 vs 2023), not a legal notification. Other records are public GIS layers with no stated date, so confirm with GHMC. A proposed width is a plan, not a notice. Nala-level encroachment fields in this service are blank, so SETHU does not show them. HMDA status is matched by lake name only when the name is unambiguous; FTL and buffer maps are on <a href="https://lakes.hmda.gov.in/" target="_blank" rel="noopener">lakes.hmda.gov.in</a>. This is not a legal buffer or approval check.</div></div>`;
  }
  function routesCard(r) {
    const N = r.roadNear, H = r.hubs, d = m => m == null ? 'not found nearby' : fmtKm(m);
    const names = (SETUE.D.geo.road_names || {});
    return `<div class="card"><h3>Trade routes &amp; demand drivers</h3><div class="lead">What drives footfall, jobs and resale demand around this address.</div>
      <div class="kv"><span class="k">Outer Ring Road / expressway</span><span class="v">${d(N.motorway)}</span></div>
      <div class="kv"><span class="k">National highway / major trunk road</span><span class="v">${d(N.trunk)}</span></div>
      <div class="kv"><span class="k">Nearest arterial road</span><span class="v">${d(N.primary)}</span></div>
      <div class="kv"><span class="k">IT / office places within 3 km · 5 km</span><span class="v tnum">${H.work3} · ${H.work5}</span></div>
      <div class="kv"><span class="k">Nearest large office / IT hub</span><span class="v">${H.nearestWork ? esc(H.nearestWork.name || 'unnamed') + ' · ' + fmtKm(H.nearestWork.d) : 'none found'}</span></div>
      <div class="kv"><span class="k">Malls within 3 km</span><span class="v tnum">${H.mall3}${H.nearestMall ? ' · nearest ' + fmtKm(H.nearestMall.d) : ''}</span></div>
      <div class="kv"><span class="k">Cinemas within 3 km</span><span class="v tnum">${H.cinema3}</span></div>
      <div class="legend-note">Road classes and places come from the Overture Maps open dataset (Meta, Microsoft, Foursquare, OpenStreetMap). Proximity to a main road helps access and resale but can mean more noise and traffic. Counts are places, not employees.</div></div>`;
  }
  function pillarCard(r, title, lead) {
    const P = r.pillars, rows = P.items.map(it => it.v == null
      ? `<div class="frow"><div class="t"><span>${esc(it.label)}</span><span class="st indicative">not scored</span></div><div class="n">${esc(it.note)}</div></div>`
      : `<div class="frow"><div class="t"><span>${esc(it.label)}</span><span class="tnum" style="font-weight:800;color:${it.v >= .75 ? 'var(--a)' : it.v >= .5 ? 'var(--c)' : 'var(--e)'}">${Math.round(it.v * 100)}</span></div>
        <div class="bar good"><i style="width:${Math.round(it.v * 100)}%"></i></div><div class="n">${esc(it.note)} · <em>weight ${Math.round(it.wn * 100)}%</em> · <span class="st ${it.status}" style="font-size:10.5px;padding:1px 7px">${it.status}</span></div></div>`).join('');
    const nm = a => a.map(x => x.label).join(' and ').toLowerCase();
    return `<div class="card"><h3>${title || 'Location profile'} <span style="color:var(--muted);font-weight:600">· ${P.score}/100 · ${P.label}</span></h3>
      <div class="lead">${lead || `${P.items.length} pillars — flood safety is just one. Higher is better in every row.`}<br><b style="color:var(--text)">Strongest:</b> ${esc(nm(P.best))}. <b style="color:var(--text)">Weakest:</b> ${esc(nm(P.worst))}.</div>${rows}
      <div class="legend-note">Score = weighted average of the pillars above. Facility pillars come from ${r.source === 'google' ? 'Google Places' : 'OpenStreetMap + Overture Maps open data (can lag recent openings/closures)'}; air quality is a live reading. It describes the surroundings — it is not a valuation.</div></div>`;
  }
  function footnote(r) {
    return `<div class="footnote"><b>How to read this.</b> SETHU is a decision aid built on public data and map services. The ward-level flood ranking was tested on 8 real floods (mean AUC 0.69; 0.79 against GHMC's own waterlogging list). Lake distance, terrain pocket and facilities are <i>indicators</i>, not validated predictions. Lake outlines are not legal FTL/buffer boundaries — verify with HMDA / the Irrigation Dept. Rain-to-depth is a stated assumption. Not legal, valuation or insurance advice.<br>
      Data: SRTM terrain · Telangana State GIS (GHMC nalas &amp; inundation list) · OpenStreetMap · ESA WorldCover · Open-Meteo · ${r.source === 'google' ? 'Google Places' : 'Overture Maps places (Meta · Microsoft · Foursquare)'} · GHMC public data. Generated ${new Date().toLocaleString('en-IN')}.</div>`;
  }


  /* ---------- five-section evidence report (no combined score; every finding shows where it comes from) ---------- */
  const EVCOL = { Concern: 'var(--e)', Watch: 'var(--c)', Good: 'var(--a)', Unknown: 'var(--muted)' };
  const EVIC = { concern: '⛔', watch: '⚠️', good: '✅', info: 'ℹ️', unknown: '❔' };
  function evFinding(f) {
    const KL = SETUE.KIND_LABEL;
    return `<div class="evf lv-${f.level}"><div class="evh"><span class="ic">${EVIC[f.level]}</span><b>${esc(f.label)}</b><span class="kind k-${f.kind}">${esc(KL[f.kind] || f.kind)}</span></div>
      <div class="evv">${esc(f.value)}</div>${f.note ? `<div class="evn">${esc(f.note)}</div>` : ''}
      <div class="evm"><span>Confidence <b class="conf-${f.conf}">${esc(f.conf)}</b></span>${f.source ? `<span>Source: ${esc(f.source)}</span>` : ''}${f.period ? `<span>Period: ${esc(f.period)}</span>` : ''}${f.res ? `<span>Resolution: ${esc(f.res)}</span>` : ''}</div>
      ${f.scope ? `<div class="evs"><span class="scope sc-${f.scope}">Applies to: ${SCOPE_LAB[f.scope] || esc(f.scope)}</span><small>${esc(f.scopeText || '')}</small></div>` : ''}
      ${f.links && f.links.length ? `<div class="evl">${f.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join(' · ')}</div>` : ''}
      ${f.next ? `<div class="evx">▸ Next: ${esc(f.next)}</div>` : ''}</div>`;
  }
  const SCOPE_LAB = { pin: 'the pin position', parcel: 'the matched parcel outline', nearby: 'features near the pin', area: 'an area estimate', ward: 'the whole ward', mandal: 'the whole mandal', locality: 'a locality', region: 'the whole city', live: 'live data for this position', none: 'nothing (no data)' };

  function gapsCard(r) {
    const g = (r.ev && r.ev.gaps) || []; if (!g.length) return '';
    return `<details class="more gapcard"><summary><b>Why this report is incomplete</b><span>${g.length} thing${g.length === 1 ? '' : 's'} SETU could not establish</span></summary><div class="mbody"><div class="lead">Each item below is shown as unknown in the report. Unknown means "not established", never "safe".</div>
      ${g.map(x => `<div class="gap"><b>${esc(x.label)}</b><i>${esc(x.section)}</i><span>${esc(x.why)}</span></div>`).join('')}</div></details>`;
  }
  function evidenceCard(r, S) { return r.ev ? View.identity(r, S) + View.shortVersion(r, S) + View.topics(r, S) : ''; }

  /* ---------- evidence-driven due-diligence checklist: one action per concern or data gap; ticks are remembered on this device ---------- */
  const chkStore = (key, set) => { try { if (set === undefined) return localStorage.getItem(key) === '1'; localStorage.setItem(key, set ? '1' : '0'); } catch (e) { return false; } };
  function checklistCard(r) {
    const c = SETUE.checklist(r); if (!c) return '';
    const base = 'sethu.chk.' + r.lat.toFixed(4) + ',' + r.lon.toFixed(4) + '.';
    const TAG = { concern: 'concern', watch: 'watch', unknown: 'data gap', standard: 'every purchase' };
    const all = [...c.items, ...c.std], ticked = all.filter(it => chkStore(base + it.key)).length;
    const row = it => { const k = base + it.key, done = chkStore(k), w = it.where || {};
      return `<label class="chk${done ? ' done' : ''}"><input type="checkbox" data-chk="${esc(k)}"${done ? ' checked' : ''}><span class="cb"><span class="ct"><b>${esc(it.trigger.label)}</b><i class="lvtag lt-${it.trigger.level}">${TAG[it.trigger.level] || ''}</i></span>
        ${it.trigger.value ? `<span class="cs">${esc(it.trigger.value)}</span>` : ''}<span class="cw">${esc(it.why)}</span><span class="ca"><b>Do:</b> ${esc(it.action)}</span>
        <span class="cwh"><b>Where:</b> ${w.url ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a>` : esc(w.name || '')}${w.status ? ` <small>(${esc(w.status)})</small>` : ''}</span>${it.doc ? `<span class="cd"><b>Ask for:</b> ${esc(it.doc)}</span>` : ''}</span></label>`; };
    const groups = Object.entries(c.cats).map(([cat, name]) => { const its = [...c.items, ...c.std].filter(i => i.cat === cat); return its.length ? `<div class="chkgrp"><h4>${esc(name)}</h4>${its.map(row).join('')}</div>` : ''; }).join('');
    return `<div class="card chkcard"><h3>Due-diligence checklist <span class="chkprog" style="color:var(--muted);font-weight:600">${ticked} of ${all.length} ticked</span></h3>
      <div class="lead">Built from what this report found: one step for every concern, watch item and data gap, plus two checks that apply to every purchase. Legal and land-record checks are kept apart from flood, water and infrastructure ones.</div>${groups}
      <div class="legend-note"><b>Unknown means "verify", not "unsafe".</b> A missing record is not a finding. SETU has not verified any office's process unless the line says so; where it says "not verified", ask the office what it needs. Ticks are saved on this device only.</div></div>`;
  }


  /* ============================== COMPARE TWO ADDRESSES ============================== */
  const CMP_TAG = { 'a-more-severe': 'A is rated worse', 'b-more-severe': 'B is rated worse', same: 'same', 'not-comparable': 'only one side could be checked', 'both-unknown': "neither could be checked",
    'only-a': 'shown for A only', 'only-b': 'shown for B only', 'differs-unrated': 'differs (not rated)' };
  function compareView(S) {
    const { a, b } = S.cmp, c = SETUE.compare(a, b), open = (S && S.open) || {};
    const nameA = S.cmp.la || a.ward.name, nameB = S.cmp.lb || b.ward.name, pc = x => Math.round(x * 100) + '%', ST = View.STATUS;
    const title = (id, lab) => View.title({ id, label: lab });
    const cnt = r => { const all = r.ev.sections.flatMap(s => s.findings), n = l => all.filter(f => f.level === l).length; return { c: n('concern'), w: n('watch'), g: n('good'), u: n('unknown') }; };
    const cell = f => { if (!f) return '<span class="cmuted">not shown for this address</span>'; const st = ST[f.level] || ST.info;
      return `<span class="v-cell"><span class="v-ic b-${st.k}" aria-hidden="true">${st.glyph}</span><span><b class="s-${st.k}">${st.word}</b><br>${esc(f.value)}</span></span>`; };
    const head = (r, nm, tag, cov, cl) => { const n = cnt(r), id = r.ev.identity;
      return `<div class="v-card v-cmphead"><div class="v-eyebrow">Address ${tag}</div><h2>${esc(nm)}</h2><div class="v-sub">${esc(r.ward.name)} · ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div>
        <div class="v-counts"><span class="n-bad"><b>${n.c}</b> need attention</span><span class="n-warn"><b>${n.w}</b> look into</span><span class="n-ok"><b>${n.g}</b> no issue found</span><span class="n-mute"><b>${n.u}</b> couldn't check</span></div>
        <p class="v-small">${cov.known} of ${cov.total} findings had data (${pc(cov.pct)}) · ${cl} things to do before paying · ${esc(id.label)}</p>
        <button class="v-btn ghost sm" data-act="cmp-open" data-which="${tag.toLowerCase()}">Open the full check for ${tag}</button></div>`; };
    const diff = rw => `<div class="v-cdiff"><div class="v-cdt">${esc(title(rw.id, rw.label))}<small>${esc(rw.section)}</small></div><div class="v-ccols"><div><em>A</em>${cell(rw.a)}</div><div><em>B</em>${cell(rw.b)}</div></div></div>`;
    const big = c.biggest.slice(0, 8).map(diff).join(''), gaps = c.notComparable.slice(0, 10).map(diff).join('');
    const secs = c.sections.map(sec => {
      const nd = sec.counts.aMore + sec.counts.bMore, T = View.TOPICS.find(t => t.id === sec.id) || { icon: '', title: sec.title };
      const rating = r => ST[{ Concern: 'concern', Watch: 'watch', Good: 'good', Unknown: 'unknown' }[r]] || ST.unknown;
      const rows = sec.rows.map(rw => `<div class="v-crow cmp-${rw.cmp}"><div class="v-cdt">${esc(title(rw.id, rw.label))}<small>${esc(CMP_TAG[rw.cmp])}</small></div><div class="v-ccols"><div><em>A</em>${cell(rw.a)}</div><div><em>B</em>${cell(rw.b)}</div></div></div>`).join('');
      return `<details class="more v-topic t-mute" data-id="cmp_${sec.id}"${open['cmp_' + sec.id] !== undefined ? (open['cmp_' + sec.id] ? ' open' : '') : (nd ? ' open' : '')}><summary><span class="v-ticon" aria-hidden="true">${T.icon}</span><span class="v-tt"><b>${esc(T.title)}</b><small>${nd} rated difference${nd === 1 ? '' : 's'} · ${sec.counts.notComparable} only one side could be checked</small></span>
        <span class="v-tr"><small>A: <b class="s-${rating(sec.ratingA).k}">${rating(sec.ratingA).word}</b></small><small>B: <b class="s-${rating(sec.ratingB).k}">${rating(sec.ratingB).word}</b></small></span></summary><div class="v-tbody">${rows}</div></details>`;
    }).join('');
    return `<div class="printonly"><b>SETHU — Address comparison</b> · ${new Date().toLocaleDateString('en-IN')}</div>
      <div class="v-page v-cmp">
        <section class="v-card"><div class="v-eyebrow">Comparing two addresses</div><h2>${esc(nameA)} <span style="color:var(--muted);font-weight:600">vs</span> ${esc(nameB)}</h2><p class="v-lead">${esc(c.note)}</p>
          <div class="noprint v-idbtn"><button class="v-btn ghost sm" data-act="cmp-swap">⇄ Swap A and B</button><button class="v-btn ghost sm" data-act="cmp-start">Compare with a different address</button></div></section>
        <div class="v-cmpheads">${head(a, nameA, 'A', c.coverage.a, c.checklist.a)}${head(b, nameB, 'B', c.coverage.b, c.checklist.b)}</div>
        <section class="v-card"><div class="v-eyebrow">Biggest differences</div><h2>Where one address is rated worse</h2><p class="v-lead">Only findings both addresses could be checked for. "Rated worse" describes one finding, not the whole address.</p>${big || '<div class="callout">No rated finding differs between the two addresses.</div>'}</section>
        <section class="v-card"><div class="v-eyebrow">Gaps</div><h2>Only one address could be checked</h2><p class="v-lead">Couldn't check is not the same as safe, and a gap is not a difference.</p>${gaps || '<div class="callout">Nothing was checked for only one of them.</div>'}</section>
        <section class="v-topics"><div class="v-eyebrow">Section by section</div><h2>Every finding, side by side</h2>${secs}</section>
        <p class="v-small">Both addresses use the same engine, sources and rules, including research data with non-commercial licences. A pin is not a surveyed plot for either address unless a survey outline was matched.</p></div>`;
  }

  /* ---------- compact-report helpers ---------- */
  // collapsible detail section; open/closed state lives in S.open so re-renders (terrain, forecast, air arriving) do not close it
  function nearbyCard(r, title, lead) {
    const f = r.fac, H = r.hubs || {}, mall = H.nearestMall;
    const rows = [
      ['🏥', 'Hospital', f.hospital.nearest, `${f.hospital.n2km}${f.hospital.capped ? '+' : ''} within 2 km`],
      ['🚇', 'Metro / transit stop', f.metro.nearest, `${f.metro.n2km}${f.metro.capped ? '+' : ''} within 2 km`],
      ['🏬', 'Mall', mall, `${H.mall3 || 0} within 3 km`],
      ['🏫', 'School', f.school.nearest, `${f.school.n2km}${f.school.capped ? '+' : ''} within 2 km`],
      ['🛒', 'Market', f.market.nearest, `${f.market.n2km}${f.market.capped ? '+' : ''} within 2 km`]
    ];
    const body = rows.map(([ic, lab, n, sub]) => {
      const d = n ? n.d : null, w = d == null ? 0 : Math.max(7, Math.round(100 - Math.min(d, 5000) / 50)), col = d == null ? 'var(--line2)' : d < 1000 ? 'var(--a)' : d < 2500 ? 'var(--c)' : 'var(--d)';
      return `<div class="nb"><span class="ic">${ic}</span><div class="m"><div class="top"><b>${esc(n && n.name ? n.name : lab)}</b><span class="d tnum">${d == null ? 'none found' : fmtKm(d)}</span></div>
        <div class="bar2"><i style="width:${w}%;background:${col}"></i></div><small>${lab} · ${sub}</small></div></div>`;
    }).join('');
    return `<div class="card"><h3>${title || 'Hospitals, malls, stations &amp; schools nearby'}</h3>${lead === false ? '' : `<div class="lead">${lead || 'Nearest one of each, from this address. Longer bar = closer.'}</div>`}${body}
      <div class="legend-note" style="margin-top:6px">Longer bar = closer · ${r.source === 'google' ? 'Google Places' : 'OpenStreetMap + Overture Maps'}, straight-line</div></div>`;
  }
  function nearStrip(r, keys, wide) {
    const f = r.fac, H = r.hubs || {};
    const pick = { hospital: ['🏥', 'Hospital', f.hospital.nearest], metro: ['🚇', 'Metro / transit', f.metro.nearest], mall: ['🏬', 'Mall', H.nearestMall], school: ['🏫', 'School', f.school.nearest],
      market: ['🛒', 'Market', f.market.nearest], fire: ['🚒', 'Fire station', f.fire.nearest], police: ['👮', 'Police station', f.police.nearest], park: ['🌳', 'Park', f.park.nearest] };
    return `<div class="ns${wide ? ' wide' : ''}">${keys.map(k => { const [ic, lab, n] = pick[k], d = n ? n.d : null, col = d == null ? 'var(--muted)' : d < 1000 ? 'var(--a)' : d < 2500 ? 'var(--c)' : 'var(--d)';
      return `<div><span class="ic">${ic}</span><b class="tnum" style="color:${col}">${d == null ? '—' : fmtKm(d)}</b><span class="l">${lab}</span><small>${esc(n && n.name ? n.name : 'none found')}</small></div>`; }).join('')}</div>`;
  }
  const miniDetails = (title, html) => `<details class="mini"><summary>${title}</summary>${html}</details>`;

  // "why this score": the pillars as compact bars, so the number is never unexplained
  function whyScore(r) {
    const P = r.pillars, nm = a => a.map(x => x.label.toLowerCase()).join(', ');
    const rows = P.items.filter(it => it.v != null).map(it => {
      const pct = Math.round(it.v * 100), col = it.v >= .75 ? 'var(--a)' : it.v >= .5 ? 'var(--c)' : 'var(--e)';
      return `<div class="wy"><span class="n">${esc(it.label)}</span><div class="bar2"><i style="width:${pct}%;background:${col}"></i></div><b class="tnum" style="color:${col}">${pct}</b></div>`;
    }).join('');
    return `<div class="card"><h3>Why the score is ${P.score}/100</h3>${rows}
      <div class="legend-note" style="margin-top:8px">Higher is better. Weakest: ${esc(nm(P.worst))}.</div></div>`;
  }
  // the summary page ends here; the detailed report is a PDF download (or an on-screen preview)
  const dlBar = (S, includes) => `<div class="dl"><div><b>Detailed report</b><span>${includes}</span></div>
    <div class="btns"><button class="btn" data-act="print">⬇ Download full report (PDF)</button><button class="btn ghost" data-act="toggle-detail">${S.open && S.open.detail ? 'Hide' : 'Preview'} full report</button></div></div>`;
  const detailWrap = (S, inner) => `<div class="detail${S.open && S.open.detail ? ' show' : ''}">${inner}</div>`;
  const endNote = '<div class="endnote">Ward-level flood ranking tested on 8 real floods; every other figure is an indicator from open map data. Asking prices are not deal prices. Limits are listed in the full report.</div>';

  /* ============================== CUSTOMER ============================== */
  function customerParts(S) {
    const r = S.r, w = r.tiers.water, v = r.buyer, thr = SETUE.D.thr, lb = SETUE.lakeBand(r.water);
    const d192 = r.outside ? null : r.setu.depth[192], fcMax = S.fc ? Math.max(...S.fc.map(x => x.mm)) : 0;
    const summary = r.outside ? 'This address lies beyond the 145 GHMC wards the validated flood model covers, so no flood verdict is given. Judge it on the surroundings below and ask locally about waterlogging.' : v.worst === 'red' ? 'Serious water-related concerns turned up. Read the full report before paying any advance.'
      : v.worst === 'amber' ? 'Some water-related concerns turned up. They may be manageable — verify them before you commit.'
        : 'No major water red flags in the map data. Still verify documents and visit in the rain.';
    const hero = `<div class="hero"><div class="verdict ${v.worst}"><div class="k">Verdict for buyers</div><h2>${v.headline}</h2><p>${summary}</p>
      <div class="vstats">${r.outside ? '' : `<div><b style="color:${d192 >= .5 ? 'var(--e)' : d192 >= thr ? 'var(--c)' : 'var(--a)'}">${d192 >= thr ? d192.toFixed(2) + ' m' : 'Dry'}</b><span>water in a 2020-size storm</span></div>`}
        <div><b style="color:${['inside', 'very close'].includes(lb.band) ? 'var(--e)' : lb.band === 'near' ? 'var(--c)' : 'var(--a)'}">${r.water.lake ? (r.water.lake.inside ? 'Inside' : fmtKm(r.water.lake.d)) : 'None'}</b><span>nearest lake / tank</span></div>
        <div><b>${S.air ? S.air.aqi : '—'}</b><span>air quality (AQI)</span></div></div>
      <div class="pillrow" style="margin-top:14px"><span class="tag">${esc(r.ward.name)}</span></div></div>
      <div class="card gaugebox chartwrap">${Charts.scoreDial(r.pillars.score, r.pillars.label + ' location', 'Location score / 100')}<div class="cap">Across ${r.pillars.items.length} pillars. Strongest: ${esc(r.pillars.best.map(x => x.label.toLowerCase()).join(', '))}.<br>Weakest: ${esc(r.pillars.worst.map(x => x.label.toLowerCase()).join(', '))}.</div></div></div>`;
    const aq = S.air ? `${S.air.aqi}` : '—';
    const kpis = `<div class="kpis">
      ${r.outside ? kpi('Flood model', 'n/a', 'Outside the 145 GHMC wards it covers') : kpi('Depth in a 2020-size storm', d192 >= thr ? d192.toFixed(2) + ' m' : 'Dry', 'Modelled for this ward at 192 mm of rain', d192 >= .5 ? 'var(--e)' : d192 >= thr ? 'var(--c)' : 'var(--a)')}
      ${kpi('Nearest lake / tank', r.water.lake ? (r.water.lake.inside ? 'Inside' : fmtKm(r.water.lake.d)) : 'None', esc(lb.text), ['inside', 'very close'].includes(lb.band) ? 'var(--e)' : lb.band === 'near' ? 'var(--c)' : '')}
      ${kpi('Facilities nearby', r.scores.dev.score + '<span style="font-size:16px;color:var(--muted)">/100</span>', 'Hospital, school, transit, market…')}
      ${kpi('Air quality now', aq, S.air ? esc(S.air.band) + ' (US AQI)' : 'Loading…')}</div>`;
    const free = `<div class="card"><h3>What to know first</h3><div class="lead">The three things a careful buyer should check.</div>${flagList(v.flags.slice(0, 3))}</div>`;

    const curve = SETUE.curve(r.wid);
    const marks = [100, 192, 300].map(mm => ({ mm, depth: SETUE.depthAt(r.wid, mm), label: mm + ' mm' + (mm === 192 ? ' (Oct 2020)' : ''), color: mm === 192 ? '#f97316' : '#38bdf8' }));
    const chart = r.outside ? `<div class="card"><h3>Flood model not applied here</h3><div class="callout warn">This address is about ${r.ward.km.toFixed(1)} km beyond the 145 GHMC wards the validated flood model covers, so there is no rain-versus-water curve. The lake, terrain, facility and air-quality findings still apply.</div></div>` : `<div class="card"><h3>How the water rises with rain</h3><div class="lead">Modelled flood depth in ${esc(r.ward.name)}.${r.setu.floodsAtMm ? ` Starts to count as flooded at about <b>${r.setu.floodsAtMm} mm</b>.` : ' Stays below the flooding threshold up to 300 mm.'}</div>
      <div class="chartwrap">${Charts.depthCurve(curve, thr, marks, fcMax)}</div>
      <div class="legend-note">The ward <i>ranking</i> is validated; rain-to-depth is a stated assumption.</div></div>`;
    const moreFlags = v.flags.length > 3 ? `<div class="card"><h3>More flags</h3>${flagList(v.flags.slice(3))}</div>` : '';
    const fac = `<div class="card"><h3>Every facility nearby</h3><div class="lead">${srcBadge(r)}</div>${facList(r)}</div>`;
    const lake = `<div class="card"><h3>Lakes, terrain &amp; access</h3><div class="lead">Where water tends to collect and whether help can reach you.</div>
        <div class="kv"><span class="k">Nearest lake / tank</span><span class="v">${esc(lb.text)}</span></div>
        <div class="kv"><span class="k">Ponds within 500 m</span><span class="v tnum">${r.water.pondsNear}</span></div>
        <div class="kv"><span class="k">Ground vs surroundings</span><span class="v tnum">${r.terrain ? (r.terrain.relief >= 0 ? '+' : '') + r.terrain.relief.toFixed(1) + ' m' : 'checking…'}</span></div>
        <div class="kv"><span class="k">Underpasses within 1 km</span><span class="v tnum">${r.underpass1k}</span></div>
        <div class="kv"><span class="k">Road to hospital in 192 mm</span><span class="v" style="color:${r.outside ? 'var(--muted)' : r.setu.cut192 ? 'var(--e)' : 'var(--a)'}">${r.outside ? 'not modelled here' : r.setu.cut192 ? 'can be cut' : 'stays open'}</span></div>
        <div class="kv"><span class="k">Seismic zone (IS 1893)</span><span class="v">II · low</span></div>
        <div class="legend-note">Lake outlines come from open maps and are <b>not</b> the legal FTL / buffer boundary. Ground difference uses a 90 m elevation grid.</div></div>`;

    const cs = S.cust, m = SETUE.market(r.lat, r.lon, r.wid), price = +cs.price, area = +cs.area;
    let costHtml = '<div class="callout">Enter a quoted price to see the duties and the total.</div>', bandHtml = '';
    if (price > 0) {
      const t = SETUE.totalCost({ price, brokeragePct: +cs.brokerage || 0 });
      costHtml = `<table class="cost"><tr><td>Quoted price</td><td class="tnum">${inrFull(t.price)}</td></tr>
        <tr><td>Stamp, transfer &amp; registration (6%)</td><td class="tnum">${inrFull(t.govt)}</td></tr>
        ${t.brokerage ? `<tr><td>Brokerage (${esc(cs.brokerage)}%)</td><td class="tnum">${inrFull(t.brokerage)}</td></tr>` : ''}
        <tr class="total"><td>Total cost to you</td><td class="tnum">${inrFull(t.total)}</td></tr></table>`;
      if (area > 0 && m) {
        const ppsf = price / area, pos = ppsf < m.loc.low ? 'below' : ppsf > m.loc.high ? 'above' : 'within';
        bandHtml += `<div class="result ${pos === 'within' ? 'green' : pos === 'below' ? 'amber' : 'red'}" style="margin-top:12px;padding:12px 16px"><h4 style="font-size:16px;margin-bottom:2px">${inrFull(ppsf)} / sq ft — ${pos === 'within' ? 'inside' : pos} the ${esc(m.loc.name)} asking band</h4>
          <div class="chartwrap">${Charts.band(m.loc.low, m.loc.high, m.loc.typical, ppsf, v => '₹' + Math.round(v).toLocaleString('en-IN'))}</div>
          <div class="legend-note" style="margin-top:2px">${pos === 'above' ? 'Above what portals ask for this area — a point to negotiate.' : pos === 'below' ? 'Below the usual ask: a bargain or a warning — check title, access and water history.' : 'Within the usual asking range.'} Asking prices, not deal prices${m.loc.origin === 'llm-compiled' ? ' (AI-compiled estimate — verify)' : ''}.</div></div>`;
      } else if (area > 0) bandHtml += `<div class="callout warn" style="margin-top:12px">No market band within 4 km of this location, so the price check can't run.</div>`;
    }
    const cost = `<div class="card"><h3>True cost of buying &amp; price check</h3><div class="lead" style="margin-bottom:12px">Example numbers are filled in — change them to your quote.</div>
      <div class="calcgrid"><div><div class="row3"><div><label class="f">Quoted price (₹)</label><input class="in" type="number" data-bind="cust.price" value="${esc(cs.price)}" placeholder="9000000"></div>
        <div><label class="f">Area (sq ft)</label><input class="in" type="number" data-bind="cust.area" value="${esc(cs.area)}" placeholder="1200"></div>
        <div><label class="f">Brokerage (%)</label><input class="in" type="number" step="0.1" data-bind="cust.brokerage" value="${esc(cs.brokerage)}" placeholder="0"></div></div>
        <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap"><button class="btn" data-act="cust-calc">Calculate</button><button class="btn ghost" data-act="cust-example">Reset example</button></div>
        <div class="legend-note">About 4% stamp + 1.5% transfer + 0.5% registration — confirm with the Sub-Registrar.</div>${bandHtml}</div>
        <div>${costHtml}</div></div></div>`;
    const ins = `<div class="card"><h3>What this means for your insurance</h3><div class="lead">How an insurer's location score could look here. Loadings are illustrative, not a quote.</div>
      <div class="kv"><span class="k">Home insurance exposure</span><span class="v t${r.tiers.prop.letter}">Tier ${r.tiers.prop.letter} · ${SETUE.LOADING[r.tiers.prop.letter]}</span></div>
      <div class="kv"><span class="k">Vehicle insurance exposure</span><span class="v t${r.tiers.motor.letter}">Tier ${r.tiers.motor.letter} · ${SETUE.LOADING[r.tiers.motor.letter]}</span></div>
      <div class="kv"><span class="k">Health-care access</span><span class="v t${r.tiers.health.letter}">Tier ${r.tiers.health.letter} · ${TNAME[r.tiers.health.letter]}</span></div></div>`;
    const qs = ['Ask the seller for the Encumbrance Certificate (EC) and a clean title chain', 'Confirm approved layout / building permission (HMDA / GHMC); LRS status if it is a plot', 'Check RERA registration if the project is under construction'];
    if (['inside', 'very close', 'near'].includes(lb.band)) qs.push('Get the lake FTL / buffer-zone status in writing from the Irrigation Dept / HMDA');
    if (r.terrain && r.terrain.relief <= -4) qs.push('Ask whether water has ever entered the ground floor — the plot sits below its surroundings');
    if (d192 >= thr) qs.push('Ask neighbours how the street behaved in October 2020 and July 2023');
    qs.push('Visit once during heavy rain and see where the road and nearby nala overflow', 'Get a home-insurance quote before paying an advance');
    const chk = `<div class="card"><h3>Before you pay: checklist</h3><div class="lead">Tailored to what this report found.</div><ul class="list">${qs.map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>`;

    const detail = `<div class="grid2">${chart}<div class="card"><h3>All flags</h3><div class="lead">Everything a careful buyer should know.</div>${flagList(v.flags)}</div></div>
      <div class="grid2">${chk}${lake}</div>${ins}${govCard(r)}<div class="grid2">${routesCard(r)}${fac}</div>
      ${pillarCard(r, 'Location profile', `Every pillar with its weight. Flood safety is one of ${r.pillars.items.length}.`)}${footnote(r)}`;
    return { cost, detail };
  }
  function aboutCard(r) {
    const g = (r.ev && r.ev.gaps) || [];
    return `<section class="v-card v-about"><div class="v-eyebrow">About this check</div><h2>How to read it, and what it cannot tell you</h2>
      <ul class="v-ul"><li><b>Needs attention / look into / no issue found / couldn't check.</b> Every finding carries one of these four words and an icon. "No issue found" means the check ran and found nothing in the data we have; it is never a clearance. There is deliberately no single score: a serious flag is never averaged away by good amenities.</li>
        <li><b>"Couldn't check" means verify, not unsafe.</b> It means no public data answered the question.</li>
        <li><b>Public map data only.</b> Outlines are drawn, not legal boundaries. SETHU cannot see title, ownership, loans, court cases or what a seller has not shown you.</li>
        <li><b>How local is each result?</b> Every finding says whether it applies to the pin, a nearby area, the whole ward or the whole city.</li></ul>
      ${g.length ? `<details class="more v-more" data-id="gaps_all"><summary>Everything we couldn't check, and why (${g.length})</summary>${g.map(x => `<div class="v-gap"><b>${esc(x.label)}</b><i>${esc(x.section)}</i><span>${esc(x.why)}</span></div>`).join('')}</details>` : ''}
      <p class="v-small">Where each number comes from, how recent it is and how far it was checked: <a href="quality.html" target="_blank" rel="noopener">data quality dashboard</a>. Generated ${new Date().toLocaleString('en-IN')}. Not legal, valuation or insurance advice.</p>
      <div class="noprint"><button class="v-btn ghost" data-act="print">Print or save as PDF</button></div></section>`;
  }
  function customer(S) {
    const r = S.r, P = customerParts(S);
    return `<div class="printonly"><b>SETHU — Buyer check</b> · ${esc(S.label || r.ward.name)} · ${new Date().toLocaleDateString('en-IN')}</div>
      <div class="v-page">${View.identity(r, S)}${View.shortVersion(r, S)}${View.beforePay(r, S)}${View.topics(r, S)}
        <details class="more v-topic t-mute" data-id="tp_costs"${S.open && S.open.tp_costs ? ' open' : ''}><summary><span class="v-ticon" aria-hidden="true">₹</span><span class="v-tt"><b>What it will really cost</b><small>Duties and brokerage on your quoted price, and a check against typical asking prices.</small></span><span class="v-tr"></span></summary><div class="v-tbody">${P.cost}</div></details>
        <details class="more v-topic t-mute" data-id="tp_more"${S.open && S.open.tp_more ? ' open' : ''}><summary><span class="v-ticon" aria-hidden="true">📊</span><span class="v-tt"><b>Charts and official records</b><small>Rain-versus-water curve, official drainage and tank records, routes, every facility, insurance angle.</small></span><span class="v-tr"></span></summary><div class="v-tbody">${P.detail}</div></details>
        ${aboutCard(r)}</div>`;
  }

  /* ============================== REAL ESTATE AGENT ============================== */
  function agent(S) {
    const r = S.r, w = r.tiers.water, dev = r.scores.dev, m = SETUE.market(r.lat, r.lon, r.wid), a = S.agent, lb = SETUE.lakeBand(r.water);
    const ppsfAsk = +a.ask, area = +a.area, total = ppsfAsk && area ? ppsfAsk * area : 0;
    const comps = (a.comps || '').split(/[\s,;]+/).map(Number).filter(x => x > 0);
    let res = '';
    if (ppsfAsk > 0) {
      const lines = []; let level = 'amber';
      if (m) { const pos = ppsfAsk < m.loc.low ? 'below' : ppsfAsk > m.loc.high ? 'above' : 'within'; level = pos === 'within' ? 'green' : pos === 'below' ? 'amber' : 'red'; lines.push(`Asking <b>₹${Math.round(ppsfAsk).toLocaleString('en-IN')}/sq ft</b> is <b>${pos}</b> the portal asking band for ${esc(m.loc.name)} (₹${m.loc.low.toLocaleString('en-IN')}–₹${m.loc.high.toLocaleString('en-IN')}).`); }
      if (comps.length >= 2) { const s = [...comps].sort((x, y) => x - y), med = s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2, diff = (ppsfAsk - med) / med * 100; lines.push(`Median of your ${comps.length} comparables is ₹${Math.round(med).toLocaleString('en-IN')}/sq ft — this ask is <b>${diff >= 0 ? '+' : ''}${diff.toFixed(0)}%</b> against it.`); if (!m) level = diff > 12 ? 'red' : diff < -8 ? 'green' : 'amber'; }
      else lines.push('Add 2+ comparable quotes from the same area to compare with real local deals.');
      if (+a.guide) lines.push(`Official guidance value ₹${(+a.guide).toLocaleString('en-IN')}/sq yd — guidance values are legal floors; real deals sit above them.`);
      res = `<div class="result ${level}"><h4>${level === 'red' ? 'Priced above the band' : level === 'green' ? 'In line with the market' : 'Check the context'}</h4>${lines.map(l => `<div class="ck"><span>▸</span><span>${l}</span></div>`).join('')}</div>`;
    }
    const mp = SETUE.market(r.lat, r.lon, r.wid, 'plot');
    const plotHtml = mp ? `<h3 style="margin:20px 0 4px;font-size:16px">Land / plot rates · ${esc(mp.loc.name)}</h3><div class="chartwrap">${Charts.band(mp.loc.plot.low, mp.loc.plot.high, null, null, v => '₹' + Math.round(v).toLocaleString('en-IN'))}</div>
      <p class="legend-note">₹ per sq yd, asking prices${mp.loc.guidance ? ` · official guidance value ₹${mp.loc.guidance.toLocaleString('en-IN')} per sq yd (a legal floor — real deals sit above it)` : ''}.</p>` : '';
    const srcList = m ? `${m.loc.note ? `<p class="legend-note">${esc(m.loc.note)}</p>` : ''}<ul class="list tick" style="margin-top:8px">${m.loc.sources.map(s => `<li>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>` : esc(s.name)}</li>`).join('')}</ul>${plotHtml}<div class="callout warn" style="margin-top:12px"><b>Asking prices, not deal prices.</b> ${esc(SETUE.D.rates.caution || '')}</div>` : '';
    const bandHtml = m ? `<div class="chartwrap">${Charts.band(m.loc.low, m.loc.high, m.loc.typical, ppsfAsk || null, v => '₹' + Math.round(v).toLocaleString('en-IN'))}</div>
      <div class="pillrow"><span class="tag">Rate point: ${esc(m.loc.name)} (${fmtKm(m.d)} away)</span><span class="tag">confidence: ${esc(m.loc.conf)}</span><span class="tag">₹ per sq ft · apartments · asking</span>${m.loc.origin === 'llm-compiled' ? '<span class="tag" style="border-color:var(--c);color:var(--c)">AI-compiled estimate — verify</span>' : ''}</div>
      `
      : `<div class="callout warn">No market band within 4 km of this location yet. Use your own comparables below — the tool works without a band.</div>`;
    const fee = +a.fee || 0, feeAmt = total * fee / 100;
    const hero = `<div class="hero"><div class="verdict ${w.letter <= 'B' ? 'green' : w.letter === 'C' ? 'amber' : 'red'}"><div class="k">Listing brief</div><h2>${esc(S.label && S.label !== 'My location' ? S.label : r.ward.name)}</h2>
      <p>${w.letter <= 'B' ? 'Low modelled water risk — a selling point.' : w.letter === 'C' ? 'Moderate water risk — be ready for the question.' : 'Elevated water risk — buyers will ask; have the facts ready.'} ${dev.score >= 70 ? 'Strong facilities nearby.' : dev.score >= 45 ? 'Average facilities nearby.' : 'Thin facilities nearby.'}</p>
      <div class="pillrow" style="margin:16px 0 18px"><span class="tag">Water tier ${w.letter}</span><span class="tag">Facilities ${dev.score}/100</span><span class="tag">Location score ${r.pillars.score}/100</span></div>
      <div class="kv"><span class="k">Lakes / tanks</span><span class="v">${esc(lb.band)}</span></div><div class="kv"><span class="k">Depth in a 192 mm storm</span><span class="v">${r.outside ? 'not modelled here' : r.setu.depth[192] >= SETUE.D.thr ? r.setu.depth[192].toFixed(2) + ' m' : 'dry'}</span></div></div>
      <div class="card"><h3>Market band${m ? ' · ' + esc(m.loc.name) : ''}</h3><div class="lead">Typical portal asking prices per sq ft.</div>${bandHtml}</div></div>`;
    const price = `<div class="card"><h3>Price check against the market</h3><div class="lead">Example numbers are filled in — enter your listing's.</div>
      <div class="row2"><div><label class="f">Asking rate (₹ / sq ft)</label><input class="in" type="number" data-bind="agent.ask" value="${esc(a.ask)}" placeholder="9500"></div><div><label class="f">Area (sq ft)</label><input class="in" type="number" data-bind="agent.area" value="${esc(a.area)}" placeholder="1200"></div></div>
      <label class="f">Comparable deals (₹ / sq ft, comma-separated)</label><input class="in" data-bind="agent.comps" value="${esc(a.comps)}" placeholder="8800, 9200, 9600">
      <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap"><button class="btn" data-act="agent-calc">Compare</button><button class="btn ghost" data-act="agent-example">Reset example</button></div>${res}</div>`;
    const commission = `<div class="card"><h3>Commission &amp; deal economics</h3><div class="lead">Commissions aren't published — enter your fee.</div>
      <label class="f">Your fee (% of price)</label><input class="in" type="number" step="0.1" data-bind="agent.fee" value="${esc(a.fee)}" placeholder="1">
      ${total > 0 ? `<table class="cost" style="margin-top:12px"><tr><td>Deal value (${inr(ppsfAsk)}/sq ft × ${area.toLocaleString('en-IN')} sq ft)</td><td class="tnum">${inr(total)}</td></tr>${fee ? `<tr><td>Your fee at ${fee}%</td><td class="tnum">${inr(feeAmt)}</td></tr>` : ''}
        <tr><td>Govt. duties payable by buyer (~6%)</td><td class="tnum">${inr(total * .06)}</td></tr><tr class="total"><td>Buyer's all-in cost</td><td class="tnum">${inr(total * 1.06 + feeAmt)}</td></tr></table>` : '<div class="callout" style="margin-top:14px">Enter the asking rate and area in the price check to see the deal economics.</div>'}</div>`;
    const neg = r.buyer.flags.filter(f => f.lvl !== 'green'), pos = dev.parts.filter(p => p.v >= .7).map(p => `${p.label}: ${p.note.split(' · ').slice(0, 2).join(' · ')}`);
    if (w.letter <= 'B') pos.unshift('Low modelled water risk (flood-susceptibility tier ' + w.letter + ')');
    const negCard = `<div class="card"><h3>What buyers will push back on</h3>${neg.length ? neg.slice(0, 3).map(f => `<div class="flagline"><span>${f.lvl === 'red' ? '⛔' : '⚠️'}</span><b>${esc(f.t)}</b></div>`).join('') + '<div class="legend-note" style="margin-top:8px">Facts a buyer will cite — not a made-up discount.</div>' : '<div class="callout">No water red flags in the open data — price on facilities and demand.</div>'}</div>`;
    const posCard = `<div class="card"><h3>Selling points</h3>${pos.length ? `<ul class="list tick">${pos.slice(0, 3).map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '<div class="callout">No standout facilities in the data.</div>'}</div>`;
    const land = `<div class="card"><h3>Land character</h3><div class="kv"><span class="k">Ward</span><span class="v">${esc(r.ward.name)}</span></div><div class="kv"><span class="k">Built-up share of ward</span><span class="v">${r.setu.builtup != null ? Math.round(r.setu.builtup * 100) + '%' : '—'}</span></div>
        <div class="kv"><span class="k">Density · size</span><span class="v">${esc(r.prof.density_class || '—')} · ${esc(r.prof.size_class || '—')}</span></div><div class="kv"><span class="k">Lakes / tanks</span><span class="v">${esc(lb.band)} — ${esc(lb.text)}</span></div>
        <div class="kv"><span class="k">Ground vs surroundings</span><span class="v">${r.terrain ? (r.terrain.relief >= 0 ? '+' : '') + r.terrain.relief.toFixed(1) + ' m' : '…'}</span></div><div class="kv"><span class="k">Parks within 1 km</span><span class="v">${r.fac.park.n1km}${r.fac.park.capped ? '+' : ''}</span></div>
        <div class="kv"><span class="k">Industrial land</span><span class="v">${r.industry ? fmtKm(r.industry.d) + ' away' : 'none mapped nearby'}</span></div><div class="kv"><span class="k">Air quality now</span><span class="v">${S.air ? S.air.aqi + ' · ' + esc(S.air.band) : '…'}</span></div></div>`;
    const waterBreak = `<div class="card"><h3>Water-risk breakdown <span style="color:var(--muted);font-weight:600">· ${w.score}/100</span></h3><div class="lead">Every factor with its weight, so you can explain it to a client.</div>${factorRows(r.scores.water.parts)}</div>`;
    const detail = `${m ? `<div class="card"><h3>Market band — sources &amp; notes</h3>${srcList}</div>` : ''}${waterBreak}
      ${pillarCard(r, 'Location profile for your client', 'Where this address shines and where a buyer will push back.')}${govCard(r)}
      <div class="grid2">${routesCard(r)}<div class="card"><h3>Neighbourhood &amp; connectivity</h3><div class="lead">${srcBadge(r)}</div>${facList(r)}</div></div>${land}${footnote(r)}`;
    return `<div class="printonly"><b>SETHU — Listing brief</b> · ${esc(S.label || r.ward.name)} · ${new Date().toLocaleDateString('en-IN')}</div>${hero}
      <div class="sec-t" style="margin:2px 0 10px">What a buyer will ask about</div>${nearStrip(r, ['hospital', 'metro', 'mall', 'school'], true)}
      <div class="grid2">${posCard}${negCard}</div>
      ${evidenceCard(r, S)}
      ${checklistCard(r)}
      <div class="grid2">${price}${commission}</div>
      ${dlBar(S, 'Water-risk breakdown · location profile · official drainage and tank records · trade routes · every facility · water-risk breakdown')}${endNote}
      ${detailWrap(S, detail)}`;
  }

  /* ============================== INSURER ============================== */
  function insurer(S) {
    const r = S.r, line = S.line, T = r.tiers, cl = S.claim, PER = S.PERILS;
    const lineKey = { motor: 'motor', prop: 'prop', health: 'health' }[line], sc = r.scores[lineKey], t = T[lineKey];
    const names = { motor: 'Motor', prop: 'Property', health: 'Health access' };
    const hero = `<div class="hero"><div class="card"><h3>Underwriting snapshot</h3><div class="lead">${S.label && S.label !== r.ward.name ? esc(S.label) + ' · ' : ''}${esc(r.ward.name)} · ${srcBadge(r)}</div>
      <div class="tiersrow" style="margin:0;grid-template-columns:repeat(3,1fr)">${tierCard('Motor', T.motor, 'motor', SETUE.LOADING[T.motor.letter])}${tierCard('Property', T.prop, 'prop', SETUE.LOADING[T.prop.letter])}${tierCard('Health access', T.health, 'health', TNAME[T.health.letter])}</div>
      <div class="legend-note">Loadings are illustrative — a starting point to calibrate on your own claims, not an actuarial rate.</div></div>
      <div class="card gaugebox chartwrap">${Charts.gauge(sc.score, CUTS[lineKey], t.letter, names[line] + ' exposure')}<div class="cap">${names[line]} exposure, scored 0–100</div>
        <div class="drivers"><b>Biggest drivers</b>${[...sc.parts].filter(p => p.v != null).sort((x, y) => y.pts - x.pts).slice(0, 3).map(p => `<div><span>${esc(p.label)}</span><span class="tnum">${p.pts.toFixed(0)} pts</span></div>`).join('')}</div>
        <div class="seg" style="margin:12px 0 0">${['motor', 'prop', 'health'].map(k => `<button data-act="line" data-line="${k}" class="${line === k ? 'on' : ''}">${names[k]}</button>`).join('')}</div></div></div>`;
    const factors = `<div class="card"><h3>${names[line]} — underwriting factors</h3><div class="lead">${line === 'health' ? 'How easily this location can reach care — useful for network adequacy and day-one claim severity.' : line === 'motor' ? 'What makes vehicles here more likely to be flooded or stranded.' : 'What drives flood, lake, fire-reach and density exposure for a building here.'}</div>${factorRows(sc.parts, false)}</div>`;
    const per = PER[cl.peril];
    let claimRes = '';
    if (cl.busy) claimRes = '<div class="callout" style="margin-top:16px"><span class="spin"></span> &nbsp;Fetching rainfall for that date…</div>';
    else if (cl.out) {
      const o = cl.out;
      claimRes = o.error ? `<div class="callout warn" style="margin-top:16px">${esc(o.error)}</div>` : o.noEvidence
        ? `<div class="callout warn" style="margin-top:16px"><b>No external evidence source for this cause yet.</b> SETHU's evidence layer covers rain-related water damage. A ${esc(per.label.toLowerCase())} claim goes through standard checks. Roadmap: accident black-spot and fire-incident data.</div>`
        : `<div class="result ${o.level}"><h4>${esc(o.verdict)}</h4>${o.checks.map(c => `<div class="ck"><span>${c.ok ? '✅' : '⚠️'}</span><span><b>${esc(c.k)}:</b> ${esc(c.v)}</span></div>`).join('')}
          ${o.rain ? `<div class="chartwrap" style="margin-top:12px;max-width:520px">${Charts.rainBars(o.rain.days, cl.date)}</div>` : ''}<div class="legend-note">${esc(o.caveat)}</div></div>`;
    }
    const claim = `<div class="card"><h3>Claim evidence check</h3><div class="lead">Does the weather and terrain at the claimed location support a rain-damage claim? Triage for investigators — never an accusation.</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px"><button class="btn" data-act="claim-demo" data-d="1">▶ Demo: genuine claim · Tolichowki, 13 Oct 2020</button><button class="btn ghost" data-act="claim-demo" data-d="2">▶ Demo: doubtful claim · Banjara Hills, 2 Mar 2020</button></div>
      <div class="row3"><div><label class="f">Claimed cause</label><select class="in" data-bind="claim.peril">${Object.entries(PER).map(([k, p]) => `<option value="${k}"${cl.peril === k ? ' selected' : ''}>${esc(p.label)}</option>`).join('')}</select></div>
        <div><label class="f">Date of loss</label><input class="in" type="date" data-bind="claim.date" value="${esc(cl.date)}" max="${new Date().toISOString().slice(0, 10)}"></div>
        <div><label class="f">Claim amount (₹, optional)</label><input class="in" type="number" data-bind="claim.amount" value="${esc(cl.amount)}"></div></div>
      <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap"><button class="btn ghost" data-act="claim-run">Check this location &amp; date</button></div>${claimRes}</div>`;
    const fcHtml = S.fc ? `<div class="fc">${S.fc.map(x => { const d = r.outside ? 0 : SETUE.depthAt(r.wid, x.mm), h = Math.max(4, Math.round(x.mm / Math.max(60, ...S.fc.map(y => y.mm)) * 110)); return `<div><div class="col"><b class="tnum">${x.mm.toFixed(0)}</b><i style="height:${h}px;background:${d >= SETUE.D.thr ? 'var(--d)' : 'var(--accent)'}"></i></div>${new Date(x.date).toLocaleDateString('en-IN', { weekday: 'short' })}</div>`; }).join('')}</div>
      <div class="legend-note">Daily rain in mm (Open-Meteo forecast). ${r.outside ? 'The flood model does not cover this address, so no surge estimate is shown.' : 'Orange bars are heavy enough to push this ward past the flooding threshold — expect a claims surge from this area after such a day.'}</div>` : '<div class="callout"><span class="spin"></span> &nbsp;Loading the 7-day outlook…</div>';
    const outlook = `<div class="card"><h3>Rain outlook → claim surge risk</h3><div class="lead">What the next week means for this ward.</div>${fcHtml}</div>`;
    const apiJson = JSON.stringify({
      location: { lat: +r.lat.toFixed(5), lon: +r.lon.toFixed(5), ward: r.ward.name }, source: r.source,
      tiers: { motor: T.motor.letter, property: T.prop.letter, health: T.health.letter, water: T.water.letter },
      scores: { motor: r.scores.motor.score, property: r.scores.prop.score, health: r.scores.health.score, water: r.scores.water.score },
      flood_model: r.outside ? null : { susceptibility_percentile: Math.round(r.setu.pct * 100), depth_m: { '100mm': +r.setu.depth[100].toFixed(2), '192mm': +r.setu.depth[192].toFixed(2), '300mm': +r.setu.depth[300].toFixed(2) }, starts_flooding_at_mm: r.setu.floodsAtMm },
      factors_water: r.scores.water.parts.filter(p => p.v != null).map(p => ({ id: p.id, weight_pct: Math.round(p.wn * 100), points: +p.pts.toFixed(1), status: p.status })),
      evidence_sections: r.ev ? r.ev.sections.map(x => ({ section: x.id, rating: x.rating, concern: x.counts.concern, watch: x.counts.watch, good: x.counts.good, unknown: x.counts.unknown })) : undefined
    }, null, 2);
    const api = `<div class="grid2"><div class="card"><h3>API-ready output</h3><div class="lead">The same engine behind this page, returned as JSON for your underwriting or claims systems. <b>Preview of the planned endpoint</b> — the response is exactly what the engine computed for this location.</div>
      <div class="code">curl "https://api.sethu.example/v1/risk?lat=${r.lat.toFixed(5)}&lon=${r.lon.toFixed(5)}" \\\n  -H "Authorization: Bearer $SETHU_KEY"</div></div>
      <div class="card"><h3>Response</h3><div class="code" style="max-height:300px">${esc(apiJson)}</div></div></div>`;
    const prov = `<div class="card"><h3>What's validated, and what isn't</h3><div class="grid3" style="margin:0">
      <div><span class="st validated">validated</span><p style="margin-top:10px;color:var(--text2)">Ward flood-susceptibility rank: mean AUC <b>0.69</b> on 8 held-out floods, <b>0.79</b> against GHMC's own list. Our first version scored 0.49 — a coin flip.</p></div>
      <div><span class="st modelled">modelled</span><p style="margin-top:10px;color:var(--text2)">Depth at a given rainfall and hospital-road cut-off. A stated assumption anchored to documented flood extents.</p></div>
      <div><span class="st indicative">indicative</span><p style="margin-top:10px;color:var(--text2)">Lake distance, terrain pocket, facilities, fire reach. Useful signals — calibrate on your own claims before relying on them for pricing.</p></div></div></div>`;
    const detail = `${factors}${api}${pillarCard(r, 'Environment & resource profile', 'Context beyond flood: access to care, services, connectivity and air quality around the insured location.')}${govCard(r)}${prov}${footnote(r)}`;
    return `<div class="printonly"><b>SETHU — Underwriting &amp; claims evidence pack</b> · ${esc(S.label || r.ward.name)} · ${new Date().toLocaleDateString('en-IN')}</div>
      ${hero}${claim}
      <div class="grid2">${outlook}<div class="card"><h3>Care &amp; access nearby</h3><div class="lead">Response and care reach around the insured location.</div>${nearStrip(r, ['hospital', 'fire', 'police', 'metro'])}</div></div>
      ${evidenceCard(r, S)}
      ${checklistCard(r)}
      ${dlBar(S, 'All underwriting factors with weights · API-ready JSON · environment profile · official drainage records · what is validated')}${endNote}
      ${detailWrap(S, detail)}`;
  }

  return { render: (lens, S) => lens === 'customer' ? customer(S) : lens === 'agent' ? agent(S) : insurer(S), compare: compareView, inr };
})();
