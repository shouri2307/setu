/* Which planning-authority zone pairs overlap on a grid of points?  node research/v7/zone_overlap.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); } };
vm.createContext(sb); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE;
(async () => {
  await E.load(); const b = E.D.parcelIdx.bbox, pairs = {}; let tot = 0;
  for (let la = b[1] + .004; la < b[3]; la += .01) for (let lo = b[0] + .004; lo < b[2]; lo += .01) { tot++; const h = E.planFacts(la, lo).hits; if (h.length > 1) { const k = h.join('+'); pairs[k] = (pairs[k] || 0) + 1; } }
  console.log('points', tot, 'overlaps by pair:', pairs);
})();
