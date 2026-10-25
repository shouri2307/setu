"""One-off patch: add the five-section evidence card to reports.js and its CSS."""
p = "web/platform/reports.js"
s = open(p, encoding="utf-8").read()

CARD = r'''
  /* ---------- five-section evidence report (no combined score; every finding shows where it comes from) ---------- */
  const EVCOL = { Concern: 'var(--e)', Watch: 'var(--c)', Good: 'var(--a)', Unknown: 'var(--muted)' };
  const EVIC = { concern: '⛔', watch: '⚠️', good: '✅', info: 'ℹ️', unknown: '❔' };
  function evFinding(f) {
    const KL = SETUE.KIND_LABEL;
    return `<div class="evf ${f.level}"><div class="evh"><span class="ic">${EVIC[f.level]}</span><b>${esc(f.label)}</b><span class="kind k-${f.kind}">${esc(KL[f.kind] || f.kind)}</span></div>
      <div class="evv">${esc(f.value)}</div>${f.note ? `<div class="evn">${esc(f.note)}</div>` : ''}
      <div class="evm"><span>Confidence <b class="conf-${f.conf}">${esc(f.conf)}</b></span>${f.source ? `<span>Source: ${esc(f.source)}</span>` : ''}${f.period ? `<span>Period: ${esc(f.period)}</span>` : ''}${f.res ? `<span>Resolution: ${esc(f.res)}</span>` : ''}</div>
      ${f.next ? `<div class="evx">▸ Next: ${esc(f.next)}</div>` : ''}</div>`;
  }
  function evidenceCard(r, S) {
    const ev = r.ev; if (!ev) return '';
    const open = (S && S.open) || {};
    const chips = ev.sections.map(sec => `<button type="button" class="evchip" onclick="var d=document.querySelector('[data-id=ev_${sec.id}]');if(d){d.open=true;d.scrollIntoView({behavior:'smooth',block:'start'})}">
      <span class="t">${esc(sec.title)}</span><b style="color:${EVCOL[sec.rating]}">${sec.rating}</b><small>${sec.counts.concern} concern · ${sec.counts.watch} watch · ${sec.counts.good} fine · ${sec.counts.unknown} unknown</small></button>`).join('');
    const secs = ev.sections.map(sec => `<details class="more evsec" data-id="ev_${sec.id}"${open['ev_' + sec.id] ? ' open' : ''}><summary><b>${esc(sec.title)}</b><em style="color:${EVCOL[sec.rating]}">${sec.rating}</em><span>${sec.findings.length} findings · ${sec.counts.concern} concern · ${sec.counts.watch} watch · ${sec.counts.unknown} unknown</span></summary>
      <div class="mbody"><div class="lead">${esc(sec.blurb)}</div>${sec.findings.map(evFinding).join('')}</div></details>`).join('');
    return `<div class="card evcard"><h3>Evidence report <span style="color:var(--muted);font-weight:600">· ${ev.total} findings in 5 sections</span></h3>
      <div class="lead">Each finding says what it is based on, how recent it is, how local it is and how much to trust it. <b style="color:var(--text)">There is deliberately no single number</b> — a severe flag is never averaged away by good amenities, and a section turns red only on a high-severity finding or three ordinary concerns.</div>
      <div class="evchips">${chips}</div>${secs}
      <div class="legend-note"><b>Observed</b> = a measurement · <b>Official record</b> = a government layer (date often not stated) · <b>Model</b> = SETHU model output · <b>Estimate from nearby data</b> = derived from surrounding wells or points, not this plot · <b>Open-map indicator</b> = from OpenStreetMap / Overture · <b>Not available</b> = we could not answer, and we show that instead of a zero. This demo includes research-only sources, some with non-commercial licences (see docs/DATA_REGISTER.md). Unknown never means safe.</div></div>`;
  }
'''
anchor = "  /* ---------- compact-report helpers ---------- */"
assert anchor in s
s = s.replace(anchor, CARD + "\n" + anchor, 1)

# customer: after the why-score / nearby grid
old = "      <div class=\"grid2\">${whyScore(r)}${nearbyCard(r, 'Hospitals, malls, stations &amp; schools', false)}</div>\n      ${cost}"
assert old in s
s = s.replace(old, "      <div class=\"grid2\">${whyScore(r)}${nearbyCard(r, 'Hospitals, malls, stations &amp; schools', false)}</div>\n      ${evidenceCard(r, S)}\n      ${cost}", 1)
# agent: after the positives/negatives
old = "      <div class=\"grid2\">${posCard}${negCard}</div>\n      <div class=\"grid2\">${price}${commission}</div>"
assert old in s
s = s.replace(old, "      <div class=\"grid2\">${posCard}${negCard}</div>\n      ${evidenceCard(r, S)}\n      <div class=\"grid2\">${price}${commission}</div>", 1)
# insurer: after the care strip, and a compact rating block in the API json
old = "      ${dlBar(S, 'All underwriting factors with weights · API-ready JSON · environment profile · official drainage records · what is validated')}${endNote}"
assert old in s
s = s.replace(old, "      ${evidenceCard(r, S)}\n" + old, 1)
old = "      factors_water: r.scores.water.parts.filter(p => p.v != null).map(p => ({ id: p.id, weight_pct: Math.round(p.wn * 100), points: +p.pts.toFixed(1), status: p.status }))\n    }, null, 2);"
assert old in s
s = s.replace(old, "      factors_water: r.scores.water.parts.filter(p => p.v != null).map(p => ({ id: p.id, weight_pct: Math.round(p.wn * 100), points: +p.pts.toFixed(1), status: p.status })),\n      evidence_sections: r.ev ? r.ev.sections.map(x => ({ section: x.id, rating: x.rating, concern: x.counts.concern, watch: x.counts.watch, good: x.counts.good, unknown: x.counts.unknown })) : undefined\n    }, null, 2);", 1)
open(p, "w", encoding="utf-8").write(s)

css = open("web/platform/styles.css", encoding="utf-8").read()
CSS = '''
/* evidence report */
.evchips{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0 16px}
.evchip{text-align:left;background:var(--surface2);border:1px solid var(--line);border-radius:12px;padding:12px 14px;color:var(--text);cursor:pointer;font:inherit}
.evchip:hover{border-color:var(--accent)}
.evchip .t{display:block;font-size:13px;color:var(--muted);font-weight:700}
.evchip b{display:block;font-size:20px;margin:2px 0}
.evchip small{display:block;font-size:11.5px;color:var(--muted);line-height:1.35}
details.evsec>summary em{font-style:normal;font-weight:800}
details.evsec .lead{margin:6px 0 8px}
.evf{padding:13px 0;border-bottom:1px solid var(--line)}
.evf:last-child{border-bottom:none}
.evh{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.evh .ic{width:22px}
.evh b{font-size:15.5px}
.evv{margin:3px 0 0 31px;font-size:15px;color:var(--text)}
.evn{margin:3px 0 0 31px;font-size:13.5px;color:var(--text2);line-height:1.45}
.evm{margin:6px 0 0 31px;display:flex;gap:6px 14px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.evm b.conf-high,.evm b.conf-medium{color:var(--a)}.evm b.conf-low{color:var(--c)}.evm b.conf-unavailable{color:var(--muted)}
.evx{margin:6px 0 0 31px;font-size:13px;color:#9bd8f7}
.evf.concern .evv{color:var(--e)}.evf.watch .evv{color:var(--c)}.evf.unknown .evv{color:var(--muted)}
.kind{font-size:10.5px;font-weight:700;padding:1px 8px;border-radius:999px;border:1px solid var(--line2);color:var(--muted);text-transform:none}
.kind.k-observed{color:var(--a);border-color:rgba(34,197,94,.55)}.kind.k-official{color:#c4b5fd;border-color:rgba(167,139,250,.6)}.kind.k-modelled{color:var(--accent);border-color:rgba(56,189,248,.55)}
.kind.k-estimate{color:#7dd3fc;border-color:rgba(125,211,252,.5)}.kind.k-indicative{color:var(--c);border-color:rgba(234,179,8,.55)}.kind.k-unavailable{color:var(--muted);border-style:dashed}
@media print{.evchips{display:none}}
'''
if "/* evidence report */" not in css:
    open("web/platform/styles.css", "a", encoding="utf-8").write(CSS)
print("reports + css patched")
