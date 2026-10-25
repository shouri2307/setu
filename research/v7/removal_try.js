/* Remove each data source in turn and report which findings still produce a rated (good / watch / concern) result.  node research/v7/removal_try.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
function engine(blocked) {
  const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
    fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
  vm.createContext(sb); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb); return sb.SETUE;
}
const PLACES = [[17.4235, 78.4745], [17.4401, 78.3489], [17.3616, 78.4747], [17.3558, 78.526], [17.514, 78.45], [17.4948, 78.3996], [17.4126, 78.4482], [17.63, 78.48]];
(async () => {
  const base = engine([]); await base.load(); const Q = base.D.quality;
  const groups = new Map();
  for (const [id, s] of Object.entries(Q.sources)) if (s.files && s.files.length && !['sethu_model'].includes(id)) { const k = s.files.join('+'); (groups.get(k) || groups.set(k, { files: s.files, srcs: [] }).get(k)).srcs.push(id); }
  for (const g of groups.values()) {
    const E = engine(g.files); try { await E.load(); } catch (e) { console.log(g.files.join("+").padEnd(22), "required: the engine refuses to start without it"); continue; }
    const remove = new Set(g.srcs); const bad = new Map();
    for (const [la, lo] of PLACES) {
      const r = await E.report(la, lo); if (!r.ok) continue;
      for (const s of r.ev.sections) for (const f of s.findings) {
        const qf = Q.factors[f.id]; if (!qf) continue;
        const only = qf.sources.every(x => remove.has(x));
        if (only && ['good', 'watch', 'concern'].includes(f.level)) bad.set(f.id, `${f.level}: ${String(f.value).slice(0, 70)}`);
      }
    }
    console.log(`${g.files.join('+').padEnd(22)} [${g.srcs.join(',')}]`.padEnd(100), bad.size ? 'STILL RATED -> ' + [...bad].map(([k, v]) => k + ' (' + v + ')').join(' | ') : 'ok');
  }
})();
