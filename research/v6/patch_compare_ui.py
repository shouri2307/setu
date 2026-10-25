"""One-off patch: compare-two-addresses view (reports.js), wiring (app.js), styles."""

def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, f"{path}: missing {old[:80]!r}"
        s = s.replace(old, new, 1)
    open(path, "w", encoding="utf-8").write(s)

CMP = r'''
  /* ============================== COMPARE TWO ADDRESSES ============================== */
  const CMP_TAG = { 'a-more-severe': 'A is more severe', 'b-more-severe': 'B is more severe', same: 'same level', 'not-comparable': 'only one side has data: not comparable', 'both-unknown': 'unknown for both',
    'only-a': 'shown for A only', 'only-b': 'shown for B only', 'differs-unrated': 'differs (not rated)' };
  function compareView(S) {
    const { a, b } = S.cmp, c = SETUE.compare(a, b), open = (S && S.open) || {};
    const nameA = S.cmp.la || a.ward.name, nameB = S.cmp.lb || b.ward.name, pc = x => Math.round(x * 100) + '%';
    const cell = f => !f ? '<span class="cmuted">not shown for this address</span>'
      : `<span class="cv lvl-${f.level}">${EVIC[f.level]} ${esc(f.value)}</span><span class="cmeta"><i class="kind k-${f.kind}">${esc(SETUE.KIND_LABEL[f.kind] || f.kind)}</i> confidence ${esc(f.conf)}</span>`;
    const head = (r, nm, tag, cov, cl) => `<div class="card cmphead"><div class="eyebrow">Address ${tag}</div><h3>${esc(nm)}</h3><div class="sub">${esc(r.ward.name)} · ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div>
      <div class="covbar"><i style="width:${Math.round(cov.pct * 100)}%"></i></div><div class="covtxt"><b>${cov.known} of ${cov.total}</b> findings have data (${pc(cov.pct)}) · ${cov.unknown} unknown · ${cl} checklist actions</div>
      <div class="cmpchips">${r.ev.sections.map(sec => `<span class="evchip2"><span>${esc(sec.title)}</span><b style="color:${EVCOL[sec.rating]}">${sec.rating}</b></span>`).join('')}</div>
      <button class="btn ghost sm" data-act="cmp-open" data-which="${tag.toLowerCase()}">Open full report</button></div>`;
    const big = c.biggest.slice(0, 8).map(rw => `<div class="cdiff"><b>${esc(rw.label)}</b><span>${esc(rw.section)}</span><div>A: ${EVIC[rw.a.level]} ${esc(rw.a.level)} · ${esc(rw.a.value)}</div><div>B: ${EVIC[rw.b.level]} ${esc(rw.b.level)} · ${esc(rw.b.value)}</div></div>`).join('');
    const gaps = c.notComparable.slice(0, 10).map(rw => `<div class="cdiff"><b>${esc(rw.label)}</b><span>${esc(rw.section)}</span><div>A: ${esc(rw.a.level === 'unknown' ? 'unknown' : rw.a.value)}</div><div>B: ${esc(rw.b.level === 'unknown' ? 'unknown' : rw.b.value)}</div></div>`).join('');
    const secs = c.sections.map(sec => {
      const ndiff = sec.counts.aMore + sec.counts.bMore, rows = sec.rows.map(rw => `<div class="crow cmp-${rw.cmp}"><div class="cl"><b>${esc(rw.label)}</b><small>${esc(CMP_TAG[rw.cmp])}</small></div><div class="cc ca"><em>A</em>${cell(rw.a)}</div><div class="cc cb2"><em>B</em>${cell(rw.b)}</div></div>`).join('');
      return `<details class="more cmpsec" data-id="cmp_${sec.id}"${open['cmp_' + sec.id] || ndiff ? ' open' : ''}><summary><b>${esc(sec.title)}</b><span>A <em style="color:${EVCOL[sec.ratingA]}">${sec.ratingA}</em> · B <em style="color:${EVCOL[sec.ratingB]}">${sec.ratingB}</em> · ${ndiff} rated difference${ndiff === 1 ? '' : 's'} · ${sec.counts.notComparable} not comparable · data A ${pc(sec.covA.pct)} / B ${pc(sec.covB.pct)}</span></summary><div class="mbody">${rows}</div></details>`;
    }).join('');
    return `<div class="printonly"><b>SETHU — Address comparison</b> · ${new Date().toLocaleDateString('en-IN')}</div>
      <div class="card cmpnote"><h3>Comparing two addresses</h3><div class="lead">${esc(c.note)}</div>
        <div class="cmpbtns noprint"><button class="btn ghost sm" data-act="cmp-swap">⇄ Swap A and B</button><button class="btn ghost sm" data-act="cmp-start">Compare with a different address</button></div></div>
      <div class="grid2 cmpheads">${head(a, nameA, 'A', c.coverage.a, c.checklist.a)}${head(b, nameB, 'B', c.coverage.b, c.checklist.b)}</div>
      <div class="grid2"><div class="card"><h3>Where they differ most</h3><div class="lead">Findings that both addresses have data for, where one is rated more severe. "More severe" describes one finding, not the address overall.</div>${big || '<div class="callout">No rated finding differs between the two addresses.</div>'}</div>
        <div class="card"><h3>Evidence gaps: not comparable</h3><div class="lead">One address has data and the other does not. Unknown is not safe, and a gap is not a difference.</div>${gaps || '<div class="callout">No finding is known for only one of them.</div>'}</div></div>
      <div class="card"><h3>Section by section</h3><div class="lead">Sections with rated differences open by default. Every row keeps its evidence kind and confidence.</div>${secs}</div>
      <div class="legend-note" style="margin-top:12px">Both addresses use the same engine, sources and rules, including research-layer data with non-commercial licences (see the data register). A pin is not a surveyed plot for either address.</div>`;
  }
'''
patch("web/platform/reports.js", [
    ("  /* ---------- compact-report helpers ---------- */", CMP + "\n  /* ---------- compact-report helpers ---------- */"),
    ("  return { render: (lens, S) => lens === 'customer' ? customer(S) : lens === 'agent' ? agent(S) : insurer(S), inr };",
     "  return { render: (lens, S) => lens === 'customer' ? customer(S) : lens === 'agent' ? agent(S) : insurer(S), compare: compareView, inr };"),
])

patch("web/platform/app.js", [
    # state
    ("seq: 0, token: Math.random().toString(36).slice(2), busy: false", "seq: 0, token: Math.random().toString(36).slice(2), busy: false, cmp: null, cmpPending: false"),
    # setPin: the second address of a comparison
    ("async function setPin(lat, lon, label, opts = {}) {\n  const seq = ++S.seq; S.busy = true;",
     "async function setPin(lat, lon, label, opts = {}) {\n  if (S.cmpPending && S.r && S.r.ok) return startCompare(lat, lon, label);\n  const seq = ++S.seq; S.busy = true;"),
    # hash
    ("  const h = S.view === 'report' ? `#/r/${S.lens}/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}` : `#/l/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}`;",
     "  const h = S.view === 'compare' && S.cmp ? `#/c/${S.cmp.a.lat.toFixed(5)},${S.cmp.a.lon.toFixed(5)}/${S.cmp.b.lat.toFixed(5)},${S.cmp.b.lon.toFixed(5)}` : S.view === 'report' ? `#/r/${S.lens}/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}` : `#/l/${S.r.lat.toFixed(5)},${S.r.lon.toFixed(5)}`;"),
    # dock: compare button and pending banner
    ("    <div class=\"reports\">${['customer', 'agent', 'insurer'].map(l => `<button class=\"rbtn\" data-act=\"open\" data-lens=\"${l}\"><span class=\"e\">${LENS_ICON[l]}</span><span><b>${LENS_NAME[l]}</b><span>${LENS_SUB[l]}</span></span>${infoIcon(l)}</button>`).join('')}</div></div>`;\n}",
     "    <div class=\"reports\">${['customer', 'agent', 'insurer'].map(l => `<button class=\"rbtn\" data-act=\"open\" data-lens=\"${l}\"><span class=\"e\">${LENS_ICON[l]}</span><span><b>${LENS_NAME[l]}</b><span>${LENS_SUB[l]}</span></span>${infoIcon(l)}</button>`).join('')}</div>\n    ${S.cmpPending ? `<div class=\"callout cmpwait\"><b>Pick the second address.</b> Search above or click the map to compare it with ${esc(title)}. <button class=\"btn ghost sm\" data-act=\"cmp-cancel\">Cancel</button></div>` : `<button class=\"btn ghost sm cmpbtn\" data-act=\"cmp-start\">⇄ Compare with another address</button>`}</div>`;\n}"),
    # report header button
    ("<button class=\"btn ghost sm noprint\" data-act=\"print\">🖨 PDF</button><button class=\"btn ghost sm noprint\" data-act=\"share\">🔗 Share</button></div></div>\n    <div class=\"rbody\">${Reports.render(S.lens, S)}</div>`;\n  v.scrollTop = sc;\n}",
     "<button class=\"btn ghost sm noprint\" data-act=\"cmp-start\">⇄ Compare</button><button class=\"btn ghost sm noprint\" data-act=\"print\">🖨 PDF</button><button class=\"btn ghost sm noprint\" data-act=\"share\">🔗 Share</button></div></div>\n    <div class=\"rbody\">${Reports.render(S.lens, S)}</div>`;\n  v.scrollTop = sc;\n}\nfunction renderCompare() {\n  const v = $('report'); if (!S.cmp) return; const sc = v.scrollTop;\n  v.innerHTML = `<div class=\"rhead\"><div class=\"rin\"><button class=\"btn ghost sm back\" data-act=\"back\">← Map</button>\n    <div><h1>Compare two addresses</h1><div class=\"loc\">${esc(S.cmp.la || S.cmp.a.ward.name)} vs ${esc(S.cmp.lb || S.cmp.b.ward.name)}</div></div>\n    <button class=\"btn ghost sm noprint\" data-act=\"print\">🖨 PDF</button><button class=\"btn ghost sm noprint\" data-act=\"share\">🔗 Share</button></div></div>\n    <div class=\"rbody\">${Reports.compare(S)}</div>`;\n  v.scrollTop = sc;\n}\nasync function startCompare(lat, lon, label) {\n  S.cmpPending = false; toast('Comparing the two addresses…', 8000);\n  const rb = await SETUE.report(lat, lon);\n  if (!rb.ok) { toast('That address is outside Hyderabad coverage'); renderDock(); return; }\n  // give B the same live enrichments A has, so the two sides are compared on equal terms\n  const [t, ac, air] = await Promise.all([SETUE.elevationProfile(lat, lon).catch(() => null), SETUE.roadAccess(lat, lon).catch(() => null), SETUE.airNow(lat, lon).catch(() => null)]);\n  rb.terrain = t; rb.access = ac; rb.air = air; SETUE.reanalyse(rb);\n  S.cmp = { a: S.r, b: rb, la: S.label && !['Coordinates', 'My location'].includes(S.label) ? S.label : S.r.ward.name, lb: label && !['Coordinates', 'My location'].includes(label) ? label : rb.ward.name };\n  openCompare();\n}\nfunction openCompare() { S.view = 'compare'; $('report').classList.remove('hide'); $('report').scrollTop = 0; renderCompare(); syncHash(); $('toast').classList.remove('show'); }"),
    # refresh
    ("function refresh(fresh) {\n  if (S.view === 'report') {", "function refresh(fresh) {\n  if (S.view === 'compare') return renderCompare();\n  if (S.view === 'report') {"),
    # actions
    ("  else if (a === 'back') closeReport();",
     "  else if (a === 'back') closeReport();\n  else if (a === 'cmp-start') { if (!S.r || !S.r.ok) return; S.cmpPending = true; if (S.view !== 'explore') closeReport(true); renderDock(); toast('Now search or click the map for the second address', 5000); }\n  else if (a === 'cmp-cancel') { S.cmpPending = false; renderDock(); }\n  else if (a === 'cmp-swap') { if (S.cmp) { S.cmp = { a: S.cmp.b, b: S.cmp.a, la: S.cmp.lb, lb: S.cmp.la }; syncHash(); renderCompare(); } }\n  else if (a === 'cmp-open') { const w = t.dataset.which === 'b' ? 'b' : 'a'; if (S.cmp) { S.r = S.cmp[w]; S.label = w === 'a' ? S.cmp.la : S.cmp.lb; MapKit.setPin(S.r.lat, S.r.lon, S.r.outside ? null : S.r.wid, false); openReport('customer'); } }"),
    # route
    ("  } else if ((m = h.match(/^#\\/l\\/(-?[\\d.]+),(-?[\\d.]+)/)) || (m = h.match(/^#(-?[\\d.]+),(-?[\\d.]+)/))) {",
     "  } else if ((m = h.match(/^#\\/c\\/(-?[\\d.]+),(-?[\\d.]+)\\/(-?[\\d.]+),(-?[\\d.]+)/))) {\n    const la = +m[1], lo = +m[2], lb = +m[3], lob = +m[4];\n    if (!S.r || Math.abs(S.r.lat - la) > 1e-5 || Math.abs(S.r.lon - lo) > 1e-5) await setPin(la, lo, '', { keepView: true });\n    if (!S.cmp || Math.abs(S.cmp.b.lat - lb) > 1e-5 || Math.abs(S.cmp.b.lon - lob) > 1e-5 || Math.abs(S.cmp.a.lat - la) > 1e-5) { S.cmpPending = true; await startCompare(lb, lob, ''); } else openCompare();\n  } else if ((m = h.match(/^#\\/l\\/(-?[\\d.]+),(-?[\\d.]+)/)) || (m = h.match(/^#(-?[\\d.]+),(-?[\\d.]+)/))) {"),
])

css = open("web/platform/styles.css", encoding="utf-8").read()
CSS = '''
/* compare two addresses */
.cmpbtn{margin-top:12px;width:100%}
.cmpwait{margin-top:12px}.cmpwait .btn{margin-left:8px}
.cmpnote .cmpbtns{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.cmphead .covbar{height:8px;border-radius:99px;background:var(--surface3);margin:12px 0 6px;overflow:hidden}.cmphead .covbar i{display:block;height:100%;background:var(--accent)}
.cmphead .covtxt{font-size:13px;color:var(--text2)}
.cmpchips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.evchip2{display:flex;flex-direction:column;background:var(--surface2);border:1px solid var(--line);border-radius:10px;padding:6px 10px;font-size:11.5px;color:var(--muted)}.evchip2 b{font-size:14px}
.cdiff{padding:10px 0;border-bottom:1px solid var(--line);font-size:13.5px;color:var(--text2)}.cdiff:last-child{border-bottom:none}.cdiff b{color:var(--text);margin-right:8px}.cdiff>span{color:var(--muted);font-size:12px}
.crow{display:grid;grid-template-columns:1.1fr 1.5fr 1.5fr;gap:12px;padding:11px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.crow:last-child{border-bottom:none}
.crow .cl b{display:block;color:var(--text);font-size:14px}.crow .cl small{color:var(--muted);font-size:11.5px}
.crow .cc{display:flex;flex-direction:column;gap:3px}.crow .cc em{display:none;font-style:normal;font-weight:800;color:var(--accent)}
.crow .cv{color:var(--text)}.crow .cv.lvl-concern{color:var(--e)}.crow .cv.lvl-watch{color:var(--c)}.crow .cv.lvl-unknown{color:var(--muted)}
.crow .cmeta{font-size:11px;color:var(--muted)}.crow .cmuted{color:var(--muted);font-style:italic}
.crow.cmp-a-more-severe .ca,.crow.cmp-b-more-severe .cb2{box-shadow:inset 3px 0 0 var(--e);padding-left:8px}
.crow.cmp-not-comparable{background:rgba(148,163,184,.06)}
.cmpsec>summary span{font-size:12.5px}
@media(max-width:760px){.crow{grid-template-columns:1fr}.crow .cc em{display:inline}.crow .cc{flex-direction:row;flex-wrap:wrap;gap:6px 8px;align-items:baseline}.crow .cmeta{width:100%}}
'''
if "/* compare two addresses */" not in css:
    open("web/platform/styles.css", "a", encoding="utf-8").write(CSS)
print("compare UI patched")
