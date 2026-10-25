"""One-off: wire batch 4 (parcels, planning authority, network, evidence-quality registry) into web/platform/engine.js. Every anchor must match exactly once."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
P = ROOT / "web/platform/engine.js"; s = P.read_text(encoding="utf-8")
block = (ROOT / "research/v7/engine_b4_block.js").read_text(encoding="utf-8")

def once(old, new):
    global s
    assert s.count(old) == 1, f"anchor count {s.count(old)} for: {old[:80]!r}"
    s = s.replace(old, new)

# ---- A. load(): five new optional data files ----
once("'land', 'tanks', 'rainstats'];\n    const paths", "'land', 'tanks', 'rainstats', 'plan', 'prohib', 'network', 'parcelIdx', 'quality'];\n    const paths")
once("'data/tanks.json', 'data/rainstats.json'];", "'data/tanks.json', 'data/rainstats.json', 'data/plan.json', 'data/prohib.json', 'data/network.json', 'data/parcels/index.json', 'data/quality.json'];")
once("rainstats: { meta: {}, mandals: {} } };", "rainstats: { meta: {}, mandals: {} }, plan: null, prohib: null, network: null, parcelIdx: null, quality: null };")

# ---- B. prepEvidence: bounding boxes and lookup maps ----
once("    const grid = g => g && g.meta ? g : null;",
"""    const polysBB = ps => (ps || []).map(p => ({ ...p, _b: bbLL(p.o) }));
    D.planL = D.plan && D.plan.zones ? { zones: D.plan.zones.map(z => ({ z: z.z, polys: polysBB(z.polys) })), mandals: D.plan.mandals.map(m => ({ ...m, polys: polysBB(m.polys) })) } : null;
    D.prohibL = D.prohib && D.prohib.p ? D.prohib.p.map(p => ({ cat: p[0], sy: p[1], part: p[2], extent: p[3], village: p[4], mandal: p[5], rings: p[6], _b: bbLL(p[6][0]) })) : null;
    D.networkL = D.network && D.network.meta ? { meta: D.network.meta, sup: new Map(D.network.supply.map(c => [c[0], [c[1], c[2]]])), sew: new Map(D.network.sewer.map(c => [c[0], [c[1], c[2]]])), sections: D.network.sections.map(x => ({ ...x, _b: x.rings.map(bbLL) })) } : null;
    const grid = g => g && g.meta ? g : null;""")

# ---- C. the new functions, before SECTIONS ----
once("  const SECTIONS = [\n", block + "\n  const SECTIONS = [\n")

# ---- D. HIGH set ----
once("'landfill', 'lost', 'forest', 'gwp']);", "'landfill', 'lost', 'forest', 'gwp', 'overlap']);")

# ---- E. water findings ----
a = s.index("    add('water', { id: 'supply', label: 'Piped water and sewerage coverage'"); b = s.index("\n", a)
water = r"""    // mapped HMWSSB network: where the state GIS MAPS a pipe, in coarse cells. A mapped pipe is not a connection; no mapped pipe is not "no supply".
    const nf = netFacts(r.lat, r.lon), secName = nf && nf.section ? nf.section.name : null;
    add('water', { id: 'supply', label: 'Water connection, supply hours and tanker dependence', value: 'not published per address' + (secName ? ` · HMWSSB operating section: ${secName}` : ''), level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'HMWSSB (no public per-address record found)', period: '—', res: '—',
      note: 'Whether a property has a tap connection, how many hours water comes and whether tankers are needed is not in any public dataset we reached. The operating section only says which HMWSSB office area this is, not that a connection exists.', next: 'Ask for the water and sewerage connection papers and recent bills, and ask neighbours how often water comes and whether they buy tankers.' });
    if (nf && nf.inside) {
      const cm = nf.cellM, sup = nf.sup, sew = nf.sew;
      const NB = { kind: 'official', conf: 'low', period: 'undated (service document created 2025-05-24)', res: `${cm} m cell` };
      if (sup.ring != null) add('water', { id: 'supplynet', label: 'Mapped HMWSSB supply pipe near the pin', value: `a supply pipe is mapped within about ${(sup.ring + 1) * cm} m · ${Math.round(sup.len[3])} m of pipe within about ${4 * cm} m, largest ${sup.dia[3]} mm`, level: 'info', source: 'Telangana State GIS (TCUR) HMWSSB supply-line layer', ...NB,
        note: 'A pipe on the map is not a connection: it does not show that this property is connected, that water flows, or how often. Pipes are shown as coarse cells; the GIS does not say when they were surveyed.', next: 'Ask HMWSSB whether the property has a registered connection (CAN number).' });
      else add('water', { id: 'supplynet', label: 'Mapped HMWSSB supply pipe near the pin', value: `no supply pipe mapped within about ${4 * cm} m`, level: 'unknown', source: 'Telangana State GIS (TCUR) HMWSSB supply-line layer', ...NB, kind: 'unavailable', conf: 'unavailable',
        note: 'Mapping is uneven, so this is neither proof of no supply nor a clean result. Newer colonies and the outer wards are often missing from the map.', next: 'Ask the seller and neighbours how water is supplied.' });
      if (sew.ring != null) add('water', { id: 'sewernet', label: 'Mapped sewer line near the pin', value: `a sewer line is mapped within about ${(sew.ring + 1) * cm} m` + (sew.dia[3] ? ` (largest ${sew.dia[3]} mm within about ${4 * cm} m)` : ''), level: sew.ring > 3 && sew.cells >= 20 ? 'watch' : 'info', source: 'Telangana State GIS (TCUR) core-city sewer-line layer', ...NB,
        note: sew.ring > 3 && sew.cells >= 20 ? 'Sewer lines are mapped within about 1 km but none close by, which may mean no public sewer here. The layer covers the core city only and its survey date is unknown.' : 'A sewer line on the map is not a connection. The layer covers the core city only.', next: 'Ask HMWSSB or the seller whether the property is connected to the public sewer or uses a septic tank.' });
      else add('water', { id: 'sewernet', label: 'Mapped sewer line near the pin', value: 'outside the area where sewer lines are mapped (core city only)', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TCUR) core-city sewer-line layer', period: 'undated', res: `${cm} m cell`,
        note: 'The state layer maps sewer lines for the core city only. No line here does not mean there is no sewer.', next: 'Ask whether the property uses the public sewer or a septic tank.' });
    }"""
s = s[:a] + water + s[b:]

# ---- F. land findings: plot, zoning, plus planauth / prohib / overlap ----
a = s.index("    add('land', { id: 'plot', label: 'Plot identity'"); b = s.index("\n", s.index("    add('land', { id: 'zoning'"))
land = r"""    // ---------- property identity, planning authority, parcel overlaps (batch 4) ----------
    const pc = r.parcel ? r.parcel.match : null, pf = planFacts(r.lat, r.lon);
    const PSRC = 'Telangana State GIS (TGRAC) Bhunaksha cadastral layer', PPER = 'undated (service document created 2025-04-19)';
    if (!pc) add('land', { id: 'plot', label: 'Plot identity (survey parcel)', value: 'not matched yet', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: PSRC, period: '—', res: '—',
      note: 'A map pin is not a plot. The pin has not been matched to a surveyed parcel in this view.', next: 'Get the survey number from the sale deed and check it on the Bhu Bharati portal.' });
    else add('land', { id: 'plot', label: 'Plot identity (survey parcel)', value: PARCEL_LABEL[pc.status] + (pc.parcel && pc.status !== 'unavailable' ? ` · survey no. ${pc.parcel.number}, ${pc.parcel.village}` : ''),
      level: pc.status === 'none' && ['number-mismatch', 'neighbour', 'village-mismatch'].includes(pc.reason) ? 'watch' : (pc.status === 'verified' || pc.status === 'approximate') ? 'info' : 'unknown', kind: pc.status === 'unavailable' ? 'unavailable' : 'official',
      conf: pc.status === 'verified' ? 'medium' : pc.status === 'approximate' ? 'low' : 'unavailable', source: PSRC, period: PPER, res: 'parcel outline (~1 m)',
      note: pc.text + ' A drawn outline is not a legal boundary and says nothing about title or ownership.', next: 'Get the survey number from the sale deed, check it on the Bhu Bharati portal, and compare the extent and boundaries with the deed.' });
    if (pf && pf.zone) add('land', { id: 'planauth', label: 'Which official plan governs this area', value: `${pf.info.area}: the ${pf.info.plan}`, level: 'info', kind: 'official', conf: 'medium', source: 'Telangana State GIS (TGRAC) HMDA planning-authority layer', period: 'undated (service document created 2025-04-17)', res: 'authority-area polygon (~22 m)',
      note: `This says which plan governs the area. It does not say what this plot is zoned for. HMDA publishes this plan ${pf.info.how}, and SETU does not read it. The boundaries are undated and HMDA's jurisdiction was reportedly widened in 2025 (secondary source), so confirm which plan applies.`, next: 'Open the plan below, find the survey number, and ask HMDA for the land-use certificate.', links: pf.links });
    else add('land', { id: 'planauth', label: 'Which official plan governs this area', value: pf ? 'outside the HMDA authority areas held' : 'planning-authority layer not loaded', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TGRAC) HMDA planning-authority layer', period: '—', res: '—',
      note: 'The governing plan could not be identified for this location.', next: 'Ask HMDA or the local municipality which master plan applies.' });
    add('land', { id: 'zoning', label: 'Master-plan land use and zoning', value: 'not read by SETU', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'HMDA master plans (PDF / image sheets)', period: '—', res: '—',
      note: 'HMDA publishes its plans as static PDF and image sheets; no queryable land-use layer was found, and SETU does not read the sheets. It cannot say whether this plot is residential, commercial, green or reserved for a road.', next: 'Ask HMDA for the land-use certificate for the survey number in writing.', links: pf && pf.zone ? pf.links : [] });
    const ph = prohibFacts(r.lat, r.lon, pc && pc.parcel), phTested = pc ? pc.status !== 'unavailable' : false;
    if (ph) add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: `listed in a state GIS layer as "${ph.cat}"${ph.how === 'survey-number' ? ' (matched by survey number, not by the pin position)' : ''}`, level: 'watch', kind: 'official', conf: 'low', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: 'undated (service document created 2025-04-19)', res: 'parcel outline',
      note: `Survey no. ${ph.sy}${ph.part === 'Y' ? ' (part of the number)' : ''}${ph.extent ? ', extent ' + ph.extent : ''}. This is a mapped overlap with a state GIS list, not a legal finding, and not the registration department's prohibited-property register, which has reportedly contained wrongly listed parcels and is being revised. This layer's date and basis are not documented.`, next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati, and ask for the removal order if it was listed in error.' });
    else if (phTested) add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: 'not listed in this state GIS layer', level: 'info', kind: 'official', conf: 'low', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: 'undated (service document created 2025-04-19)', res: 'parcel outline',
      note: 'This layer\'s date, basis and completeness are not documented and the official prohibited-property register may differ. Absence here is not clearance.', next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati before paying any advance.' });
    else add('land', { id: 'prohib', label: 'Listed in a state prohibitory-land layer', value: 'cannot be tested here', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: 'Telangana State GIS (TGRAC) "ULB_Cadastral_Prohibited" layer', period: '—', res: '—',
      note: 'No survey parcels are mapped here, so the layer cannot be tested. That says nothing about whether the property is restricted.', next: 'Check the survey number in the Registration Department\'s prohibited-property search and on Bhu Bharati.' });
    if (pc && pc.usable && pc.parcel) {
      const o = overlapFacts(pc.parcel.rings), parts = [], pctx = f => Math.round(f * 100) + '% of the outline';
      if (o.lost) parts.push(`a tank recorded as disappeared (${pctx(o.lost.frac)})`);
      if (o.forest) parts.push(`${o.forest.name || 'a forest boundary'} (${pctx(o.forest.frac)})`);
      for (const t of o.tanks.slice(0, 2)) parts.push(`a mapped tank${t.name ? ' "' + t.name + '"' : ''}, status ${ST_LABEL[t.status] || 'unknown'} in 2023 (${pctx(t.frac)})`);
      add('land', { id: 'overlap', label: 'Mapped features overlapping the parcel outline', value: parts.length ? 'the matched outline overlaps ' + parts.join('; ') : 'no overlap with the 3 layers checked (disappeared water bodies, forest boundary, tank outlines)', level: parts.length ? 'concern' : 'info', kind: 'official', conf: 'low',
        source: 'TGRAC cadastral outline tested against TGRAC water-body, disappeared-tank and forest layers', period: 'undated', res: 'parcel outline vs polygon',
        note: parts.length ? 'Two map layers disagree about the same ground. That is a reason to check, not a legal finding; either outline can be off by metres, and a survey number can be much larger than a house plot.' : 'Only three layers were tested, and a drawn outline can be off by metres. This is not a clearance.', next: 'Ask for a boundary demarcation (FMB sketch) and the revenue record history of the survey number.' });
    } else add('land', { id: 'overlap', label: 'Mapped features overlapping the parcel outline', value: 'needs a matched survey parcel', level: 'unknown', kind: 'unavailable', conf: 'unavailable', source: '—', period: '—', res: '—',
      note: 'Pin-based findings above test the pin position only. Tests against the whole parcel outline need a pin that matches exactly one survey parcel.', next: 'Enter the survey number from your deed so the pin can be matched to its outline.' });"""
s = s[:a] + land + s[b:]

# ---- G. scope tags, identity, gaps ----
once("    return { sections, kinds: KIND_LABEL, total: sections.reduce((a, s) => a + s.findings.length, 0) };",
"""    const QQ = Q();
    for (const sec of sections) for (const f of sec.findings) { const qf = QQ && QQ.factors[f.id]; f.scope = qf ? qf.scope : null; f.scopeText = qf ? qf.scope_text : ''; f.sourceIds = qf ? qf.sources : []; }
    const identity = pc ? { status: pc.status, label: PARCEL_LABEL[pc.status], text: pc.text, usable: pc.usable, parcel: pc.parcel ? { number: pc.parcel.number, village: pc.parcel.village, mandal: pc.parcel.mandal, areaM2: pc.parcel.areaM2 } : null }
      : { status: 'pending', label: 'Not matched yet', text: 'This report describes a map pin, not a surveyed plot.', usable: false, parcel: null };
    const gaps = sections.flatMap(sec => sec.findings.filter(f => f.level === 'unknown').map(f => ({ id: f.id, label: f.label, section: sec.title, value: f.value, why: (QQ && QQ.factors[f.id] && QQ.factors[f.id].missing) || f.note || 'no data' })));
    return { sections, kinds: KIND_LABEL, total: sections.reduce((a, s) => a + s.findings.length, 0), identity, gaps };""")

# ---- H. checklist: HMDA is reachable now; templates for the new findings ----
once("hmda: { name: 'HMDA planning section', url: null, status: 'office process not verified by SETU (its website did not respond when we checked)' },",
     "hmda: { name: 'HMDA master-plan pages', url: 'https://www.hmda.gov.in/planning-2/', status: 'website reached on 24 Oct 2026 (master-plan PDFs and image sheets); the office process for a land-use certificate is not verified by SETU' },")
once("    zoning: { cat: 'legal', why: 'Land use decides", "    prohib: { cat: 'legal', why: 'A state GIS layer lists this survey number under a prohibitory category. That is a mapped overlap, not a legal finding, but property on the official prohibited list is reported to be blocked from registration until it is removed.', action: 'Check the survey number in the Registration Department\\'s prohibited-property search and on Bhu Bharati, and ask the seller for the removal order if it was listed in error.', where: 'srq', doc: 'Prohibited-property search result; removal order if it was ever listed' },\n    overlap: { cat: 'legal', why: 'The matched survey outline overlaps a mapped tank, disappeared water body or forest boundary. Two map layers disagree about the same ground.', action: 'Ask for a boundary demarcation (FMB sketch) and the revenue record history of the survey number.', where: 'rev', doc: 'FMB sketch / demarcation, revenue record history of the survey number' },\n    zoning: { cat: 'legal', why: 'Land use decides")
once("const UNK_OK = new Set(['plot', 'zoning', 'perm', 'nalaenc', 'gwdepth', 'gwq', 'gwp', 'supply']);", "const UNK_OK = new Set(['plot', 'zoning', 'perm', 'nalaenc', 'gwdepth', 'gwq', 'gwp', 'supply', 'prohib']);")
once("(lv === 'info' && (key === 'gwdepth' || key === 'price'))", "(lv === 'info' && (key === 'gwdepth' || key === 'price' || key === 'plot'))")

# ---- I. exports ----
once("return { load, report, evidence, checklist, compare, coverage,", "return { load, report, evidence, checklist, compare, coverage, parcelLoad, parcelMatch, attachParcel, setParcel, planFacts, netFacts, prohibFacts, overlapFacts, freshness, qualityTable, removalImpact, PARCEL_LABEL, normNum, editSim,")
P.write_text(s, encoding="utf-8")
print("engine patched")
