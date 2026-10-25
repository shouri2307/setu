"""One-off: batch 4 UI — scope chips, plan links, property-identity card with manual references, 'why incomplete' list, parcel attach flow."""
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: anchor count {s.count(old)}: {old[:70]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

# ---------------- reports.js ----------------
patch("web/platform/reports.js", [
("""      ${f.next ? `<div class="evx">▸ Next: ${esc(f.next)}</div>` : ''}</div>`;
  }""",
"""      ${f.scope ? `<div class="evs"><span class="scope sc-${f.scope}">Applies to: ${SCOPE_LAB[f.scope] || esc(f.scope)}</span><small>${esc(f.scopeText || '')}</small></div>` : ''}
      ${f.links && f.links.length ? `<div class="evl">${f.links.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join(' · ')}</div>` : ''}
      ${f.next ? `<div class="evx">▸ Next: ${esc(f.next)}</div>` : ''}</div>`;
  }
  const SCOPE_LAB = { pin: 'the pin position', parcel: 'the matched parcel outline', nearby: 'features near the pin', area: 'an area estimate', ward: 'the whole ward', mandal: 'the whole mandal', locality: 'a locality', region: 'the whole city', live: 'live data for this position', none: 'nothing (no data)' };

  /* property identity: a map pin is never called a parcel. The form holds the buyer's own references; only survey number and village are matched. */
  function identityCard(r, S) {
    const id = r.ev.identity, p = (S && S.pref) || {}, m = r.parcel && r.parcel.match;
    const tone = { verified: 'ok', approximate: 'warn', none: 'bad', unavailable: 'mute', pending: 'mute' }[id.status] || 'mute';
    const cand = m && m.candidates && m.candidates.length > 1 ? `<div class="pcand"><b>Could be:</b> ${m.candidates.map(c => `<button type="button" class="chip" data-act="parcel-pick" data-n="${esc(c.number)}" data-v="${esc(c.village)}">${esc(c.number)} · ${esc(c.village)}${c.d ? ' · ' + c.d + ' m away' : ''}</button>`).join(' ')}</div>` : '';
    const field = (k, label, ph) => `<label class="pf"><span>${label}</span><input data-bind="pref.${k}" value="${esc(p[k] || '')}" placeholder="${esc(ph)}" autocomplete="off"></label>`;
    const rec = ['plot', 'layout', 'doc'].filter(k => p[k]).map(k => ({ plot: 'plot/flat', layout: 'layout (LP) no.', doc: 'document no.' }[k] + ' ' + esc(p[k]))).join(' · ');
    const area = id.parcel && id.parcel.areaM2 ? ` Outline area about ${id.parcel.areaM2 >= 10000 ? (id.parcel.areaM2 / 10000).toFixed(2) + ' ha' : id.parcel.areaM2.toLocaleString('en-IN') + ' m²'} (a survey number often holds many house plots).` : '';
    return `<div class="card idcard id-${tone}"><div class="idh"><b>Property identity</b><span class="idst">${esc(id.label)}</span></div>
      <div class="lead"><b style="color:var(--text)">${id.status === 'verified' ? 'The pin is matched to a surveyed outline.' : 'This report is about a map pin, not a verified parcel.'}</b> ${esc(id.text)}${area}</div>${cand}
      <div class="pform">${field('survey', 'Survey number (Sy. No.)', 'e.g. 91/1')}${field('village', 'Village / colony', 'as on your deed')}${field('plot', 'Plot or flat number', 'recorded only')}${field('layout', 'Layout (LP) number', 'recorded only')}${field('doc', 'Document number', 'deed / EC, recorded only')}
        <div class="pbtn"><button type="button" class="btn sm" data-act="parcel-match">Match</button><button type="button" class="btn ghost sm" data-act="parcel-clear">Clear</button></div></div>
      ${rec ? `<div class="idrec">You recorded: ${rec}. These are shown as entered and are <b>not checked</b> by SETU.</div>` : ''}
      <div class="legend-note">Survey number and village are checked against the state's mapped survey outlines, which are drawn outlines, not legal boundaries, and say nothing about title or ownership. Plot, layout and document numbers are only recorded. Nothing you type leaves this device or goes into the link.</div></div>`;
  }
  function gapsCard(r) {
    const g = (r.ev && r.ev.gaps) || []; if (!g.length) return '';
    return `<details class="more gapcard"><summary><b>Why this report is incomplete</b><span>${g.length} thing${g.length === 1 ? '' : 's'} SETU could not establish</span></summary><div class="mbody"><div class="lead">Each item below is shown as unknown in the report. Unknown means "not established", never "safe".</div>
      ${g.map(x => `<div class="gap"><b>${esc(x.label)}</b><i>${esc(x.section)}</i><span>${esc(x.why)}</span></div>`).join('')}</div></details>`;
  }"""),
("""    return `<div class="card evcard"><h3>Evidence report <span""", """    return identityCard(r, S) + `<div class="card evcard"><h3>Evidence report <span"""),
("""      <div class="evchips">${chips}</div>${secs}""", """      <div class="evchips">${chips}</div>${secs}${gapsCard(r)}"""),
])

# ---------------- app.js ----------------
patch("web/platform/app.js", [
("cmp: null, cmpPending: false\n};", """cmp: null, cmpPending: false,
  pref: { survey: '', village: '', plot: '', layout: '', doc: '' }, pdata: null
};
/* the buyer's own references stay on this device (localStorage) and never go into the link */
const refKey = (lat, lon) => 'sethu.ref.' + lat.toFixed(4) + ',' + lon.toFixed(4);
function loadRef(lat, lon) { const e = { survey: '', village: '', plot: '', layout: '', doc: '' }; try { return Object.assign(e, JSON.parse(localStorage.getItem(refKey(lat, lon)) || '{}')); } catch (x) { return e; } }
function saveRef(lat, lon, ref) { try { localStorage.setItem(refKey(lat, lon), JSON.stringify(ref)); } catch (x) { } }
function applyRef() { const r = S.r; if (!r || !r.ok) return; saveRef(r.lat, r.lon, S.pref); if (S.pdata) SETUE.setParcel(r, S.pdata, S.pref); renderReport(); }"""),
("  S.label = label || ''; S.gp = null; S.fc = null; S.air = null; S.terrain = null; S.access = null; S.ai = { q: '', a: '', think: false }; S.claim.out = null;",
 "  S.label = label || ''; S.gp = null; S.fc = null; S.air = null; S.terrain = null; S.access = null; S.pdata = null; S.pref = loadRef(lat, lon); S.ai = { q: '', a: '', think: false }; S.claim.out = null;"),
("  SETUE.airNow(lat, lon).then(a => { if (seq !== S.seq) return; S.air = a; if (S.r) { S.r.air = a; SETUE.reanalyse(S.r); } refresh(); });\n  if (S.cfg.places) {",
 "  SETUE.airNow(lat, lon).then(a => { if (seq !== S.seq) return; S.air = a; if (S.r) { S.r.air = a; SETUE.reanalyse(S.r); } refresh(); });\n  SETUE.parcelLoad(lat, lon).then(d => { if (seq !== S.seq) return; S.pdata = d; if (S.r && S.r.ok) SETUE.setParcel(S.r, d, S.pref); refresh(); }).catch(() => { });\n  if (S.cfg.places) {"),
("        r2.terrain = S.terrain; r2.air = S.air; r2.access = S.access; SETUE.reanalyse(r2); S.r = r2; refresh();",
 "        r2.terrain = S.terrain; r2.air = S.air; r2.access = S.access; if (S.pdata) r2.parcel = { data: S.pdata, ref: S.pref, match: SETUE.parcelMatch(lat, lon, S.pdata, S.pref) }; SETUE.reanalyse(r2); S.r = r2; refresh();"),
("  rb.terrain = t; rb.access = ac; rb.air = air; SETUE.reanalyse(rb);",
 "  rb.terrain = t; rb.access = ac; rb.air = air;\n  const pd = await SETUE.parcelLoad(lat, lon).catch(() => null); if (pd) rb.parcel = { data: pd, ref: {}, match: SETUE.parcelMatch(lat, lon, pd, {}) };\n  SETUE.reanalyse(rb);"),
("  else if (a === 'claim-run') runClaim();", "  else if (a === 'parcel-match') applyRef();\n  else if (a === 'parcel-pick') { S.pref.survey = t.dataset.n; if (t.dataset.v && !S.pref.village) S.pref.village = t.dataset.v; applyRef(); }\n  else if (a === 'parcel-clear') { S.pref = { survey: '', village: '', plot: '', layout: '', doc: '' }; applyRef(); }\n  else if (a === 'claim-run') runClaim();"),
])

# ---------------- styles.css ----------------
css = Path("web/platform/styles.css"); s = css.read_text(encoding="utf-8")
s += """

/* ---- batch 4: scope chips, property identity, why-incomplete ---- */
.evs{margin:6px 0 0 31px;display:flex;gap:4px 10px;flex-wrap:wrap;align-items:center;font-size:12px;color:var(--muted)}
.scope{display:inline-block;padding:1px 8px;border-radius:999px;border:1px solid var(--line);font-weight:600;color:var(--text2);background:rgba(127,127,127,.08)}
.scope.sc-parcel,.scope.sc-pin{border-color:var(--a);color:var(--a)}
.scope.sc-ward,.scope.sc-mandal,.scope.sc-region,.scope.sc-locality{border-color:var(--c);color:var(--c)}
.scope.sc-none{border-color:var(--muted);color:var(--muted)}
.evl{margin:6px 0 0 31px;font-size:13px}.evl a{color:#9bd8f7}
.idcard{border-left:4px solid var(--muted)}.idcard.id-ok{border-left-color:var(--a)}.idcard.id-warn{border-left-color:var(--c)}.idcard.id-bad{border-left-color:var(--e)}
.idh{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:6px}.idst{font-weight:700;font-size:13px;padding:2px 10px;border-radius:999px;border:1px solid var(--line)}
.id-ok .idst{color:var(--a);border-color:var(--a)}.id-warn .idst{color:var(--c);border-color:var(--c)}.id-bad .idst{color:var(--e);border-color:var(--e)}
.pform{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px 10px;margin:10px 0 4px;align-items:end}
.pf{display:flex;flex-direction:column;gap:3px;font-size:12px;color:var(--muted)}.pf input{padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--text);font-size:14px;min-width:0}
.pbtn{display:flex;gap:8px}.pcand{margin:6px 0;font-size:13px}.pcand .chip{margin:2px 4px 2px 0}
.idrec{margin:8px 0 0;font-size:13px;color:var(--text2)}
.gapcard .gap{padding:8px 0;border-bottom:1px solid var(--line);font-size:13.5px;display:flex;flex-direction:column;gap:2px}.gapcard .gap i{font-style:normal;color:var(--muted);font-size:12px}.gapcard .gap span{color:var(--text2)}
"""
css.write_text(s, encoding="utf-8"); print("ui patched")
