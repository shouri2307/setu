const fs = require('fs'), path = require('path'), vm = require('vm');
const WEB = path.join(__dirname, '..', '..', 'web');
const sb = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
  fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); return fs.existsSync(p) ? Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }) : Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); } };
vm.createContext(sb); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\n;globalThis.SETUE = SETUE;', sb);
const E = sb.SETUE, rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8'));
(async () => {
  await E.load(); const idx = E.D.parcelIdx, keys = Object.keys(idx.tiles).filter(k => idx.tiles[k] > 300); let shown = 0;
  for (let ti = 0; ti < keys.length; ti += 2) { const t = rd(`data/parcels/${keys[ti]}.json`);
    for (let i = 0; i < t.p.length; i += 31) { const row = t.p[i]; if (row[3] !== 0 || !row[0]) continue; const ring = row[5][0]; let c = [0, 0]; for (const p of ring.slice(0, -1)) { c[0] += p[0]; c[1] += p[1]; } c = [c[0] / (ring.length - 1), c[1] / (ring.length - 1)];
      let k = false; for (let a = 0, b = ring.length - 1; a < ring.length; b = a++) if (((ring[a][0] > c[0]) !== (ring[b][0] > c[0])) && (c[1] < (ring[b][1] - ring[a][1]) * (c[0] - ring[a][0]) / (ring[b][0] - ring[a][0]) + ring[a][1])) k = !k; if (!k) continue;
      const d = await E.parcelLoad(c[0], c[1]), m = E.parcelMatch(c[0], c[1], d, { survey: row[0], village: t.v[row[1]] });
      if (m.status === 'unavailable' && shown++ < 6) console.log(keys[ti], row[0], t.v[row[1]], 'ring pts', ring.length, 'area?', 'load ok', d.ok, d.outsideBox, 'parcels', d.parcels.length, 'reason', m.reason, 'pt', c.map(x => x.toFixed(5)).join(',')); } }
})();
