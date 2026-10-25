from pathlib import Path
t = Path("tests/engine.test.js"); s = t.read_text(encoding="utf-8")
old = "  {\n    const fj = rd('data/fire.json'), st = fj.stations, sj = rd('data/seismic.json');"
assert s.count(old) == 1
new = """  {
    const rd = f => JSON.parse(fs.readFileSync(path.join(WEB, f), 'utf8')), Q = D.quality;
    const freshEngine = async blocked => {
      const sb2 = { console, Math, JSON, Promise, Date, Set, Map, Array, Object, Number, String, isFinite, isNaN, parseFloat, setTimeout, clearTimeout, AbortController,
        fetch: u => { if (/^https?:/.test(u)) return Promise.reject(new Error('offline')); const p = path.join(WEB, u); if (blocked.some(b => u === 'data/' + b) || !fs.existsSync(p)) return Promise.resolve({ ok: false, status: 404, json: async () => ({}) }); return Promise.resolve({ ok: true, json: async () => JSON.parse(fs.readFileSync(p, 'utf8')) }); } };
      vm.createContext(sb2); vm.runInContext(fs.readFileSync(path.join(WEB, 'platform', 'engine.js'), 'utf8') + '\\n;globalThis.SETUE = SETUE;', sb2); const E2 = sb2.SETUE; await E2.load(); return E2;
    };
    const reports = []; for (const [la, lo] of D.wards.map(w => [w.c[1], w.c[0]]).concat([[17.63, 78.48], [17.26, 78.43], [17.2403, 78.4294], [17.597, 78.57], [17.514, 78.45]])) { const r = await E.report(la, lo); if (r.ok) reports.push(r); }
    const fj = rd('data/fire.json'), st = fj.stations, sj = rd('data/seismic.json');"""
s = s.replace(old, new); t.write_text(s, encoding="utf-8"); print("ok")
