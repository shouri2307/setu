"""Map upgrade (free): OpenFreeMap vector basemap (buildings, labels) with OSM raster fallback; survey-plot outlines you can click; the matched plot highlighted."""
from pathlib import Path
def patch(path, pairs):
    p = Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, f"{path}: {s.count(old)} x {old[:90]!r}"; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")

# ---------------- index.html ----------------
patch("web/index.html", [
    ('<link rel="stylesheet" href="vendor/leaflet.css">', '<link rel="stylesheet" href="vendor/leaflet.css">\n<link rel="stylesheet" href="vendor/maplibre-gl.css">'),
    ('<script src="vendor/leaflet.js"></script>', '<script src="vendor/leaflet.js"></script>\n<script src="vendor/maplibre-gl.js"></script>\n<script src="vendor/leaflet-maplibre-gl.js"></script>'),
    ('      <button class="chip" data-t="ev_lost">Disappeared tanks</button>', '      <button class="chip" data-t="ev_plots">Survey plots (zoom in)</button>\n      <button class="chip" data-t="ev_lost">Disappeared tanks</button>'),
])

# ---------------- engine: parcel area on load (used by the map popup) ----------------
patch("web/platform/engine.js", [
    ("const t = j.p.map(row => ({ n: row[0], v: j.v[row[1]], m: j.m[row[2]], code: row[3], rem: row[4], rings: row[5], _b: bbLL(row[5][0]) }));",
     "const t = j.p.map(row => ({ n: row[0], v: j.v[row[1]], m: j.m[row[2]], code: row[3], rem: row[4], rings: row[5], _b: bbLL(row[5][0]), area: Math.round(areaM2(row[5])) }));"),
])

# ---------------- map.js ----------------
patch("web/platform/map.js", [
# 1. vector basemap with fallback
("""    // OpenStreetMap, colour-graded for the dark theme through CSS (.inv on the tile pane)
    const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map);
    map.getPane('tilePane').classList.add('inv');
    const base = osm;""",
"""    // Basemap: OpenFreeMap vector tiles (OpenStreetMap data): crisp labels and real building footprints at every zoom; free for commercial use with attribution, provided as-is.
    // If MapLibre did not load, WebGL is unavailable or the style cannot load in time, the plain OpenStreetMap raster tiles take over, so the map never goes blank.
    const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' });
    let base = osm, vec = null;
    const useRaster = why => { if (vec) { try { map.removeLayer(vec); } catch (e) { } vec = null; } base = osm; if (!map.hasLayer(osm)) osm.addTo(map); map.getPane('tilePane').classList.add('inv'); if (why) console.warn('Vector basemap off, using OpenStreetMap tiles:', why); };
    try {
      if (!(window.maplibregl && L.maplibreGL)) throw new Error('MapLibre not loaded');
      vec = L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty', attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>' }).addTo(map); base = vec;
      const gl = vec.getMaplibreMap(); let loaded = false; gl.on('load', () => { loaded = true; });
      gl.on('error', e => { if (!loaded) useRaster(e && e.error && e.error.message); });
      setTimeout(() => { if (!loaded && base === vec) useRaster('style did not load in time'); }, 9000);
    } catch (e) { useRaster(e.message); }"""),
# 2. plot layer + matched plot, before the object that the leaflet engine returns
("""    return {
      showEv(kind, on) {
        if (evL[kind]) { map.removeLayer(evL[kind]); evL[kind] = null; }""",
"""    // survey-plot outlines: the state cadastral layer, loaded lazily for the area in view and only when zoomed in (hundreds of polygons at most)
    const plotsG = L.layerGroup().addTo(map), plotRenderer = L.canvas({ padding: .4 }); let plotsOn = false, plotSeq = 0, matchL = null, matchKey = '', plotTimer = null;
    const plotStyle = p => p.code === 2 ? { color: '#94a3b8', weight: 1, dashArray: '4 3', fillColor: '#94a3b8', fillOpacity: .04 } : p.code === 1 ? { color: '#965800', weight: 1.2, fillColor: '#965800', fillOpacity: .05 } : { color: '#0b63ce', weight: 1.1, opacity: .9, fillColor: '#0b63ce', fillOpacity: .05 };
    async function drawPlots() {
      const seq = ++plotSeq; plotsG.clearLayers();
      if (!plotsOn || map.getZoom() < 16 || !cfg.plots) return;
      const c = map.getCenter(); let d = null; try { d = await cfg.plots(c.lat, c.lng); } catch (e) { return; }
      if (seq !== plotSeq || !d || !d.ok) return;
      const b = map.getBounds().pad(.15); let n = 0;
      for (const p of d.parcels) {
        if (p._b[2] < b.getSouth() || p._b[0] > b.getNorth() || p._b[3] < b.getWest() || p._b[1] > b.getEast()) continue;
        const poly = L.polygon(p.rings, { ...plotStyle(p), renderer: plotRenderer, bubblingMouseEvents: false });
        poly.on('click', e => { L.popup({ maxWidth: 300 }).setLatLng(e.latlng).setContent(popupFor('ev_plots', { ...p, lat: e.latlng.lat, lon: e.latlng.lng })).openOn(map); });
        poly.addTo(plotsG); if (++n >= 2500) break;
      }
    }
    const schedulePlots = () => { clearTimeout(plotTimer); plotTimer = setTimeout(drawPlots, 250); };
    map.on('moveend zoomend', () => { if (plotsOn) schedulePlots(); });
    return {
      setMatch(rings, status) {
        const key = rings ? status + '|' + rings[0][0][0] + ',' + rings[0][0][1] : ''; if (key === matchKey) return; matchKey = key;
        if (matchL) { map.removeLayer(matchL); matchL = null; } if (!rings) return;
        const col = status === 'verified' ? '#16803c' : status === 'approximate' ? '#965800' : '#0b63ce';
        matchL = L.polygon(rings, { color: col, weight: 3, fillColor: col, fillOpacity: .13, interactive: false, bubblingMouseEvents: false }).addTo(map);
      },
      showEv(kind, on) {
        if (kind === 'ev_plots') { plotsOn = on; if (on && map.getZoom() < 16) map.flyTo(map.getCenter(), 17, { duration: .6 }); else drawPlots(); return; }
        if (evL[kind]) { map.removeLayer(evL[kind]); evL[kind] = null; }"""),
# 3. google engine: no-op
("      showEv() { /* evidence layers are drawn on the OpenStreetMap engine only */ },", "      showEv() { /* evidence layers are drawn on the OpenStreetMap engine only */ },\n      setMatch() { /* the matched plot is drawn on the Leaflet engine only */ },"),
# 4. replay + facade
("    if (st.mode !== 'flood') impl.setColorMode(st.mode);\n    if (st.pin)", "    if (st.mode !== 'flood') impl.setColorMode(st.mode);\n    if (st.match) impl.setMatch(st.match.rings, st.match.status);\n    if (st.pin)"),
("    showEv(kind, on) { st.ev[kind] = on; call('showEv', kind, on); },", "    showEv(kind, on) { st.ev[kind] = on; call('showEv', kind, on); },\n    setMatch(rings, status) { st.match = rings ? { rings, status } : null; call('setMatch', rings, status); },"),
# 5. popup + legend
("    if (kind === 'ev_heat') return evPop(", """    if (kind === 'ev_plots') {
      const ha = f.area >= 10000 ? (f.area / 1e4).toFixed(2) + ' ha' : Math.round(f.area || 0).toLocaleString('en-IN') + ' m²';
      const note = f.code === 2 ? 'Mapped as a road, canal, stream or tank feature, not a plot. ' : f.code === 1 ? 'The source flags this number as duplicate or unreadable. ' : '';
      return evPop({ title: `Survey no. ${f.n}`, value: `${f.v || 'village n/a'}${f.m ? ', ' + f.m : ''} · ${ha}`, rows: [['Remark in the source', f.rem || null]],
        source: 'Telangana State GIS cadastral layer (TGRAC)', period: 'undated (service document created 2025-04-19)', res: 'drawn outline, about 1 m', conf: f.code ? 'low' : 'medium', caveat: note + 'A drawn outline is not a legal boundary and says nothing about title or ownership. A survey number can hold many house plots.' })
        + (f.code === 2 ? '' : `<div style="margin-top:8px"><button type="button" class="v-btn sm" data-act="plot-use" data-n="${escH(f.n)}" data-v="${escH(f.v)}" data-lat="${Number(f.lat).toFixed(6)}" data-lon="${Number(f.lon).toFixed(6)}">Check this plot</button></div>`);
    }
    if (kind === 'ev_heat') return evPop("""),
("    ev_heat: D => ({", "    ev_plots: D => ({ title: 'Survey plots', swatch: [['#0b63ce', 'survey outline'], ['#965800', 'number flagged at source'], ['#94a3b8', 'road / canal / tank'], ['#16803c', 'matched to your pin']], unit: 'zoom in to see them', note: 'State cadastral outlines, undated. Drawn outlines, not legal boundaries; a survey number can hold many house plots. Click one to check it.' }),\n    ev_heat: D => ({"),
])

# ---------------- app.js ----------------
patch("web/platform/app.js", [
    ("    bounds: D.zones.bounds, wards,", "    plots: (la, lo) => SETUE.parcelLoad(la, lo), bounds: D.zones.bounds, wards,"),
    ("  else if (a === 'parcel-match') applyRef();", """  else if (a === 'plot-use') {
    const la = +t.dataset.lat, lo = +t.dataset.lon, n = t.dataset.n, v = t.dataset.v || ''; if (!isFinite(la) || !isFinite(lo)) return;
    setPin(la, lo, 'Survey no. ' + n + (v ? ', ' + v : '')).then(() => { S.pref.survey = n; if (v) S.pref.village = v; if (S.r && S.r.ok) { saveRef(S.r.lat, S.r.lon, S.pref); if (S.pdata) SETUE.setParcel(S.r, S.pdata, S.pref); refresh(); } });
    toast('Checking survey no. ' + n + '…', 3000);
  }
  else if (a === 'parcel-match') applyRef();"""),
    ("function refresh(fresh) {\n", "function syncMatch() {   // draw the matched survey plot on the map (or clear it)\n  const m = S.r && S.r.parcel && S.r.parcel.match;\n  MapKit.setMatch(m && m.parcel && m.parcel.rings && (m.status === 'verified' || m.status === 'approximate') ? m.parcel.rings : null, m && m.status);\n}\nfunction refresh(fresh) {\n  syncMatch();\n"),
])
print("map upgrade patched")
