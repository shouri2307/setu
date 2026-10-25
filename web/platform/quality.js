/* Internal evidence-quality dashboard. Everything is computed from data/quality.json through SETUE.qualityTable / removalImpact; nothing is hand-coloured. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const FLAG = {
    stale: ['Stale', 'bad', 'older than the age the registry allows for this kind of data'], undated: ['Undated', 'warn', 'no observation date is published'], unvalidated: ['Unvalidated', 'warn', 'not checked against anything independent'],
    'failed-validation': ['Failed validation', 'bad', 'tested against an independent reference and did not agree'], 'restricted-licence': ['Licence: demo only', 'bad', 'non-commercial or demo-server terms'], 'licence-unverified': ['Licence unverified', 'warn', 'terms not confirmed'],
    'no-data': ['No data', 'mute', 'the report says so and never fills a value'], 'coarse-scope': ['Coarse scope', 'warn', 'a ward, mandal, locality or city-wide value, not the plot']
  };
  const SCOPE = { pin: 'the pin position', parcel: 'matched parcel outline', nearby: 'features near the pin', area: 'an area estimate', ward: 'the whole ward', mandal: 'the whole mandal', locality: 'a locality', region: 'the whole city', live: 'live, this position', none: 'nothing (no data)' };
  const FRESH = { current: ['current', 'ok'], aging: ['ageing', 'warn'], stale: ['stale', 'bad'], undated: ['undated', 'warn'], historical: ['historical record', 'mute'], live: ['live', 'mute'], reference: ['reference', 'mute'], documents: ['documents', 'mute'], model: ['model', 'mute'] };
  const VAL = { validated: ['validated', 'ok'], 'internal-check': ['internal check only', 'warn'], negative: ['failed', 'bad'], unvalidated: ['unvalidated', 'warn'], 'not-applicable': ['n/a', 'mute'] };
  const LIC = { ok: ['ok', 'ok'], verify: ['unverified', 'warn'], restricted: ['demo only', 'bad'] };
  const pill = (t, k, title) => `<span class="pill ${k}"${title ? ` title="${esc(title)}"` : ''}>${esc(t)}</span>`;
  const worst = (arr, order) => arr.slice().sort((a, b) => order.indexOf(a) - order.indexOf(b))[0];
  const obsText = s => s.obs ? (s.obs[0] === s.obs[1] ? s.obs[0] : `${s.obs[0]} to ${s.obs[1]}`) : 'not published';
  let T = null, active = new Set();

  function tiles() {
    const f = T.factors, n = k => f.filter(x => x.flags.includes(k)).length;
    const items = [['all', f.length, 'findings in the registry'], ...Object.entries(FLAG).map(([k, v]) => [k, n(k), v[0] + ' · ' + v[2]])];
    $('qtiles').innerHTML = items.map(([k, c, t]) => `<button class="qt${(k === 'all' && !active.size) || active.has(k) ? ' on' : ''}" data-k="${k}"><b>${c}</b><span>${esc(t)}</span></button>`).join('');
  }
  function findings() {
    const q = $('qf').value.toLowerCase(), sec = $('qs').value;
    const rows = T.factors.filter(f => (!sec || f.sec === sec) && (!active.size || [...active].every(k => f.flags.includes(k))) && (!q || (f.id + ' ' + (f.label || '') + ' ' + f.sources.join(' ')).toLowerCase().includes(q)));
    $('qcount').textContent = `${rows.length} of ${T.factors.length} shown`;
    const S = id => T.sources.find(s => s.id === id);
    $('qfind').innerHTML = `<tr><th>Finding</th><th>Section</th><th>Applies to</th><th>Sources</th><th>Freshness</th><th>Validation</th><th>Licence</th><th>Flags</th><th>Why it can be unknown</th></tr>` + rows.map(f => {
      const ss = f.sources.map(S).filter(Boolean), fr = worst(f.freshness, ['stale', 'undated', 'aging', 'current', 'historical', 'model', 'reference', 'documents', 'live']);
      const val = worst(ss.map(s => s.validation), ['negative', 'unvalidated', 'internal-check', 'validated', 'not-applicable']), lic = worst(ss.map(s => s.licence), ['restricted', 'verify', 'ok']);
      return `<tr><td><b>${esc(f.label || f.id)}</b><span class="qn">${esc(f.id)}</span></td><td>${esc(f.sec)}</td><td>${esc(SCOPE[f.scope] || f.scope)}<span class="qn">${esc(f.scope_text)}</span></td>
        <td>${f.sources.map(id => `<a href="#" data-src="${esc(id)}">${esc((S(id) || {}).name || id)}</a>`).join('<br>')}</td><td>${pill(...(FRESH[fr] || [fr, 'mute']))}</td><td>${pill(...(VAL[val] || [val, 'mute']))}</td><td>${pill(...(LIC[lic] || [lic, 'mute']))}</td>
        <td>${f.flags.map(k => pill(FLAG[k][0], FLAG[k][1], FLAG[k][2])).join('')}</td><td>${esc(f.missing || '—')}</td></tr>`;
    }).join('');
  }
  function sources() {
    $('qsrc').innerHTML = `<tr><th>Source</th><th>Survey / observation period</th><th>Map service created</th><th>Fetched</th><th>Resolution</th><th>Coverage</th><th>Freshness</th><th>Validation</th><th>Licence</th><th>Used by</th></tr>` + T.sources.filter(s => s.id !== 'none').map(s =>
      `<tr><td><b>${esc(s.name)}</b><span class="qn">${esc(s.provider)}</span></td><td>${esc(obsText(s))}</td><td>${esc(s.svc || '—')}</td><td>${esc(s.fetched || (s.nature === 'live' ? 'live' : '—'))}</td><td>${esc(s.res)}</td><td>${esc(s.coverage)}<span class="qn">${esc(s.limits || '')}</span></td>
       <td>${pill(...(FRESH[s.freshness] || [s.freshness, 'mute']))}</td><td>${pill(...(VAL[s.validation] || [s.validation, 'mute']))}<span class="qn">${esc(s.validation_note)}</span></td><td>${pill(...(LIC[s.licence] || [s.licence, 'mute']))}<span class="qn">${esc(s.licence_note)}</span></td>
       <td><a href="#" data-rem="${esc(s.id)}">${s.used_by.length} finding${s.used_by.length === 1 ? '' : 's'}</a><span class="qn">if removed…</span></td></tr>`).join('');
  }
  function removal(id) {
    const r = SETUE.removalImpact(id), s = T.sources.find(x => x.id === id), lab = x => (T.factors.find(f => f.id === x) || {}).label || x;
    const p = $('qrem'); p.hidden = false;
    p.innerHTML = `<b>If “${esc(s.name)}” were removed or went out of date</b>
      <div class="sub">${r.becomeUnknown.length} finding${r.becomeUnknown.length === 1 ? '' : 's'} would become <b>unknown</b> (it is their only source) and ${r.degrade.length} would lose a supporting source. Tests remove the data file and check that none of them turns reassuring.${s.files && s.files.length ? ` Data file: ${esc(s.files.join(', '))}.` : ''}</div>
      <div class="qlist"><b>Become unknown</b><br>${r.becomeUnknown.map(x => esc(lab(x))).join('<br>') || '—'}</div><div class="qlist"><b>Lose a supporting source</b><br>${r.degrade.map(x => esc(lab(x))).join('<br>') || '—'}</div>`;
    p.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  async function live() {
    const lat = parseFloat($('qlat').value), lon = parseFloat($('qlon').value); if (!isFinite(lat) || !isFinite(lon)) return ($('qmsg').textContent = 'Enter a latitude and longitude');
    $('qmsg').textContent = 'Running…';
    const r = await SETUE.report(lat, lon); if (!r.ok) return ($('qmsg').textContent = 'Outside the study area');
    await SETUE.attachParcel(r, { survey: $('qsy').value });
    const id = r.ev.identity; $('qmsg').textContent = `${r.ward.name}${r.outside ? ' (outside the 145 wards)' : ''} · parcel: ${id.label}`;
    const rows = r.ev.sections.flatMap(s => s.findings.map(f => ({ s: s.title, f })));
    $('qout').innerHTML = `<div class="sub">${esc(id.text)}</div><div class="qscroll"><table class="qt2"><tr><th>Section</th><th>Finding</th><th>Result</th><th>Level</th><th>Kind</th><th>Confidence</th><th>Applies to</th><th>Period</th><th>Resolution</th></tr>` +
      rows.map(({ s, f }) => `<tr><td>${esc(s)}</td><td>${esc(f.label)}</td><td>${esc(f.value)}</td><td>${pill(f.level, f.level === 'concern' ? 'bad' : f.level === 'watch' ? 'warn' : f.level === 'good' ? 'ok' : 'mute')}</td><td>${esc(f.kind)}</td><td>${esc(f.conf)}</td><td>${esc(SCOPE[f.scope] || '—')}</td><td>${esc(f.period)}</td><td>${esc(f.res)}</td></tr>`).join('') +
      `</table></div><h3 style="margin:14px 0 4px;font-size:15px">Not established (${r.ev.gaps.length})</h3><div class="qlist">${r.ev.gaps.map(g => `<b>${esc(g.label)}</b> <span class="qn" style="display:inline">${esc(g.why)}</span>`).join('<br>')}</div>`;
  }
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-k]'); if (t) { const k = t.dataset.k; if (k === 'all') active.clear(); else active.has(k) ? active.delete(k) : active.add(k); tiles(); findings(); return; }
    const r = e.target.closest('[data-rem]'); if (r) { e.preventDefault(); removal(r.dataset.rem); return; }
    const s = e.target.closest('[data-src]'); if (s) { e.preventDefault(); removal(s.dataset.src); }
  });
  (async () => {
    try { await SETUE.load(); } catch (e) { $('qsub').textContent = 'Could not load the data files: ' + e.message; return; }
    T = SETUE.qualityTable(new Date());
    if (!T) { $('qsub').textContent = 'The registry (data/quality.json) is missing: nothing can be shown.'; return; }
    $('qsub').innerHTML = `Registry updated ${esc(SETUE.D.quality.meta.updated)}; ages computed for ${esc(T.asOf)}. ${T.sources.length - 1} sources and ${T.factors.length} findings. <b>This page is internal.</b> It documents what each number rests on; it is not a score and says nothing about any property.`;
    const secs = [...new Set(T.factors.map(f => f.sec))]; $('qs').innerHTML += secs.map(s => `<option>${esc(s)}</option>`).join('');
    $('qf').oninput = findings; $('qs').onchange = findings; $('qclear').onclick = () => { active.clear(); $('qf').value = ''; $('qs').value = ''; tiles(); findings(); };
    $('qgo').onclick = live; tiles(); findings(); sources();
  })();
})();
