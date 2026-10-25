/* Generate docs/EVIDENCE_MATRIX.md from web/data/quality.json through the engine's own qualityTable(), so the document can never disagree with the dashboard.  node research/v7/gen_matrix.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const ROOT = path.join(__dirname, '..', '..'), WEB = path.join(ROOT, 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); } };
vm.createContext(sb); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE;
(async () => {
  await E.load(); const asOf = new Date(Date.UTC(2026, 9, 24)), T = E.qualityTable(asOf), q = E.D.quality, md = s => String(s == null ? '' : s).replace(/\|/g, '/').replace(/\n/g, ' ');
  const L = [];
  L.push('# SETU evidence matrix', '', `Generated from \`web/data/quality.json\` by \`research/v7/gen_matrix.js\`; ages computed for ${T.asOf}. **Do not edit by hand**: edit the registry, regenerate, and run the tests (they fail if the engine emits a finding the registry does not list).`, '',
    'The same data drives the internal dashboard at `web/quality.html`. Survey / observation dates are kept apart from the date a GIS service document was created (the second says when a map was published, not when the ground was surveyed).', '');
  const cnt = k => T.factors.filter(f => f.flags.includes(k)).length;
  L.push('## Summary', '', `${T.factors.length} findings, ${T.sources.length - 1} sources.`, '', '| Flag | Findings |', '|---|---|',
    ...[['stale', 'Stale (older than allowed for this kind of data)'], ['undated', 'Undated (no observation date published)'], ['unvalidated', 'Unvalidated (not checked against anything independent)'], ['failed-validation', 'Failed validation'],
      ['restricted-licence', 'Licence: demo / non-commercial only'], ['licence-unverified', 'Licence unverified'], ['no-data', 'No data (reported as unknown)'], ['coarse-scope', 'Coarse scope (ward, mandal, locality or city-wide)']].map(([k, t]) => `| ${t} | ${cnt(k)} |`), '');
  L.push('## Sources', '', '| Source | Provider | Observation period | Map service created | Fetched | Resolution | Coverage | Freshness | Validation | Licence | Findings |', '|---|---|---|---|---|---|---|---|---|---|---|');
  for (const s of T.sources.filter(x => x.id !== 'none')) L.push(`| ${md(s.name)} | ${md(s.provider)} | ${s.obs ? (s.obs[0] === s.obs[1] ? s.obs[0] : s.obs[0] + ' to ' + s.obs[1]) : 'not published'} | ${s.svc || '—'} | ${s.fetched || (s.nature === 'live' ? 'live' : '—')} | ${md(s.res)} | ${md(s.coverage)} | ${s.freshness} | ${s.validation}: ${md(s.validation_note)} | ${s.licence}: ${md(s.licence_note)} | ${s.used_by.length} |`);
  L.push('', '## Findings', '', 'Scope says what a result applies to: the pin position, the matched parcel outline, features near the pin, an area estimate, the whole ward / mandal / city, live data, or nothing.', '',
    '| Finding | Section | Applies to | Sources | Flags | Why it can be unknown |', '|---|---|---|---|---|---|');
  for (const f of T.factors) L.push(`| ${md(f.label)} (\`${f.id}\`) | ${f.sec} | ${f.scope}: ${md(f.scope_text)} | ${f.sources.map(id => md((q.sources[id] || {}).name || id)).join('; ')} | ${f.flags.join(', ') || '—'} | ${md(f.missing || '—')} |`);
  L.push('', '## If a source is removed', '', 'Findings that rest only on the source become unknown; findings with other sources lose a supporting source. The test suite removes each data file in turn and fails if any finding that depends only on it is still rated good, watch or concern.', '',
    '| Source | Becomes unknown | Loses a supporting source |', '|---|---|---|');
  for (const s of T.sources.filter(x => x.id !== 'none')) { const r = E.removalImpact(s.id); L.push(`| ${md(s.name)} | ${r.becomeUnknown.length ? r.becomeUnknown.join(', ') : '—'} | ${r.degrade.length ? r.degrade.join(', ') : '—'} |`); }
  fs.writeFileSync(path.join(ROOT, 'docs', 'EVIDENCE_MATRIX.md'), L.join('\n') + '\n'); console.log('wrote docs/EVIDENCE_MATRIX.md', L.length, 'lines');
})();
