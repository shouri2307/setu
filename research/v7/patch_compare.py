"""Fix compare-two-addresses: remember A when Compare is pressed, ignore stale/duplicate picks, refuse the same address, open instantly and fill live data in afterwards; redo the screen in the new plain-language style."""
from pathlib import Path
ROOT = Path(".")

# ---------------- app.js ----------------
p = ROOT / "web/platform/app.js"; s = p.read_text(encoding="utf-8")
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]; s = s.replace(old, new)

rep("busy: false, cmp: null, cmpPending: false,", "busy: false, cmp: null, cmpPending: false, cmpA: null, cmpSeq: 0,")
rep("  if (S.cmpPending && S.r && S.r.ok) return startCompare(lat, lon, label);\n", "  if (S.cmpPending && S.cmpA && S.cmpA.ok) return startCompare(lat, lon, label);   // address A was fixed when Compare was pressed; this pick is B\n")
rep("  if (!opts.keepView && S.view === 'report') closeReport(true);", "  if (!opts.keepView && (S.view === 'report' || S.view === 'compare')) closeReport(true);")

a = s.index("async function startCompare(lat, lon, label) {"); b = s.index("function openCompare()")
s = s[:a] + """const metres = (la1, lo1, la2, lo2) => { const k = Math.cos(la1 * Math.PI / 180); return Math.hypot((lo2 - lo1) * k * 111320, (la2 - la1) * 110540); };
const cleanLabel = (l, fb) => l && !['Coordinates', 'My location'].includes(l) ? l : fb;
async function startCompare(lat, lon, label) {
  const A = S.cmpA || S.r;
  if (!A || !A.ok) return;
  if (metres(A.lat, A.lon, lat, lon) < 20) { toast('That is the same address as A. Pick a different one for B.', 4500); return; }   // stays in "pick the second address"
  const seq = ++S.cmpSeq; S.cmpPending = false; toast('Comparing the two addresses…', 6000);
  const rb = await SETUE.report(lat, lon);
  if (seq !== S.cmpSeq) return;   // a newer pick for B replaced this one
  if (!rb.ok) { toast('That address is outside Hyderabad coverage'); S.cmpPending = true; renderDock(); return; }
  // the parcel layer is local and quick; it is part of the evidence for B, so wait for it
  const pd = await SETUE.parcelLoad(lat, lon).catch(() => null); if (seq !== S.cmpSeq) return;
  if (pd) rb.parcel = { data: pd, ref: {}, match: SETUE.parcelMatch(lat, lon, pd, {}) };
  SETUE.reanalyse(rb);
  S.cmp = { a: A, b: rb, la: cleanLabel(S.cmpA === S.r ? S.label : '', A.ward.name), lb: cleanLabel(label, rb.ward.name) };
  openCompare();
  // slow live lookups (elevation, road routing, air) fill in afterwards, so the comparison never waits on a slow server
  Promise.all([SETUE.elevationProfile(lat, lon).catch(() => null), SETUE.roadAccess(lat, lon).catch(() => null), SETUE.airNow(lat, lon).catch(() => null)]).then(([t, ac, air]) => {
    if (seq !== S.cmpSeq) return; rb.terrain = t; rb.access = ac; rb.air = air; SETUE.reanalyse(rb); if (S.view === 'compare') renderCompare();
  });
}
""" + s[b:]

rep("  else if (a === 'cmp-start') { if (!S.r || !S.r.ok) return; S.cmpPending = true; if (S.view !== 'explore') closeReport(true); renderDock(); toast('Now search or click the map for the second address', 5000); }",
    "  else if (a === 'cmp-start') { const A = S.view === 'compare' && S.cmp ? S.cmp.a : S.r; if (!A || !A.ok) return; S.cmpA = A; S.cmpPending = true; if (S.view !== 'explore') closeReport(true); renderDock(); toast('Now search or click the map for the second address', 6000); }")
rep("  else if (a === 'cmp-cancel') { S.cmpPending = false; renderDock(); }", "  else if (a === 'cmp-cancel') { S.cmpPending = false; S.cmpA = null; renderDock(); }")
rep("{ S.cmpPending = true; await startCompare(lb, lob, ''); } else openCompare();", "{ S.cmpA = S.r; S.cmpPending = true; await startCompare(lb, lob, ''); } else openCompare();")
p.write_text(s, encoding="utf-8")

# ---------------- reports.js: the comparison screen ----------------
p = ROOT / "web/platform/reports.js"; s = p.read_text(encoding="utf-8")
a = s.index("  /* ============================== COMPARE TWO ADDRESSES"); b = s.index("  /* ---------- compact-report helpers ---------- */")
s = s[:a] + r"""  /* ============================== COMPARE TWO ADDRESSES ============================== */
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
        <div class="v-counts"><span class="n-bad"><b>${n.c}</b> need attention</span><span class="n-warn"><b>${n.w}</b> look into</span><span class="n-ok"><b>${n.g}</b> fine</span><span class="n-mute"><b>${n.u}</b> couldn't check</span></div>
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

""" + s[b:]
p.write_text(s, encoding="utf-8")

p = ROOT / "web/platform/theme.css"; s = p.read_text(encoding="utf-8")
s += """
/* ---- compare two addresses ---- */
.v-cmpheads{display:grid;grid-template-columns:1fr 1fr;gap:16px}.v-cmphead h2{margin-bottom:2px}
.v-cdiff,.v-crow{padding:14px 0;border-bottom:1px solid var(--line)}.v-cdiff:last-child,.v-crow:last-child{border-bottom:none}
.v-cdt{font-weight:800;font-size:16.5px;margin-bottom:8px}.v-cdt small{display:block;font-weight:600;font-size:12.5px;color:var(--muted);margin-top:2px}
.v-ccols{display:grid;grid-template-columns:1fr 1fr;gap:12px}.v-ccols>div{background:var(--surface2);border-radius:12px;padding:10px 12px;font-size:14.5px;line-height:1.45}.v-ccols em{display:block;font-style:normal;font-size:12px;font-weight:800;color:var(--muted);letter-spacing:.06em;margin-bottom:4px}
.v-cell{display:flex;gap:10px;align-items:flex-start}.v-cell .v-ic{margin-top:2px;width:22px;height:22px;font-size:13px}.v-cell b{font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}
.v-crow.cmp-a-more-severe .v-ccols>div:first-child,.v-crow.cmp-b-more-severe .v-ccols>div:last-child{outline:2px solid var(--badbg);background:#fff}
.cmuted{color:var(--muted);font-size:14px}
@media (max-width:860px){.v-cmpheads,.v-ccols{grid-template-columns:1fr}}
"""
p.write_text(s, encoding="utf-8")
print("compare patched")
