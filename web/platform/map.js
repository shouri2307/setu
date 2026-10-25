/* MapKit — one interface, two engines.
 * Google Maps when a browser key is configured and loads cleanly; otherwise (or if Google fails
 * mid-session, e.g. auth/billing error) we fall back to Leaflet + OpenStreetMap so the demo never breaks. */
const MapKit = (() => {
  let impl = null, cfg = null, el = null, engine = 'none';
  const st = { pin: null, layers: { wards: true, lakes: true }, poi: {}, sat: false, mode: 'flood', gov: {}, ev: {} };
  const POI_COL = { hospital: '#ef4444', school: '#eab308', metro: '#a78bfa', fire: '#f97316', market: '#22c55e', park: '#10b981', bank: '#60a5fa', police: '#38bdf8' };
  const riskColor = t => {
    const g = [45, 212, 191], y = [250, 204, 21], o = [251, 146, 60], r = [244, 63, 94], L = (a, b, k) => a.map((v, i) => Math.round(v + (b[i] - v) * k));
    return `rgb(${(t < .34 ? L(g, y, t / .34) : t < .67 ? L(y, o, (t - .34) / .33) : L(o, r, (t - .67) / .33))})`;
  };

  const HYCOL = { L: '#22c55e', PB: '#f97316', TB: '#ef4444', PA: '#eab308', TA: '#dc2626', '?': '#94a3b8' };
  const HYLAB = { L: 'Live', PB: 'Partially encroached (built-up)', TB: 'Totally encroached (built-up)', PA: 'Partially encroached (agriculture)', TA: 'Totally encroached (agriculture)', '?': 'not classified' };
  const wardFill = (w, mode) => mode === 'loc' ? riskColor(1 - Math.max(0, Math.min(1, ((w.loc == null ? 70 : w.loc) - 45) / 50))) : riskColor(w.pct);
  const wardLabel = (w, mode) => w.name.replace(/^Ward \d+ /, '') + (mode === 'loc' ? ' · location score ' + Math.round(w.loc) + '/100' : ' · flood rank ' + Math.round(w.pct * 100) + '/100');

  // on wide screens the side panel covers the left 440 px of the map; on phones the panel sits below the map
  const padL = () => innerWidth > 1000 ? 440 : 20;
  const HYD_BOX = [[17.20, 78.18], [17.66, 78.70]];   // south-west, north-east: Hyderabad metro region


  /* ---------------- evidence layers: every feature opens a popup with source, period, resolution and confidence ---------------- */
  const escH = v => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const evPop = o => `<div class="evpop"><b>${escH(o.title)}</b><div class="v">${escH(o.value)}</div>${(o.rows || []).filter(r => r[1] != null && r[1] !== '').map(r => `<div class="r"><span>${escH(r[0])}</span><span>${escH(r[1])}</span></div>`).join('')}` +
    `<div class="m"><div><b>Source</b> ${escH(o.source)}</div><div><b>Data period</b> ${escH(o.period)}</div><div><b>Resolution</b> ${escH(o.res)}</div><div><b>Confidence</b> ${escH(o.conf)}</div>${o.caveat ? `<div class="cv">${escH(o.caveat)}</div>` : ''}</div></div>`;
  const REC_COL = { NIL: '#7f1d1d', POOR: '#f97316', LIMITED: '#eab308', MODERATE: '#84cc16', GOOD: '#22c55e' };
  const recKey = a => { const v = String((a && a[5]) || '').toUpperCase(); return Object.keys(REC_COL).find(k => v.indexOf(k) === 0) || null; };
  const depthCol = d => d == null ? '#64748b' : d < 5 ? '#38bdf8' : d < 10 ? '#22c55e' : d < 20 ? '#eab308' : '#ef4444';
  const TKCOL = { L: '#22c55e', P: '#f97316', T: '#ef4444', D: '#94a3b8' }, TKLAB = { L: 'live', P: 'partially encroached', T: 'totally encroached', D: 'dead (no storage)' };
  const GWPF = ['geom', 'landform', 'rock', 'depth_to_water', 'wells_observed', 'recharge', 'aquifer', 'well_type', 'well_depth', 'yield', 'success', 'water_quality', 'recharge_structures', 'remarks'];
  const mons = (a, n = 4) => a && a.length ? (a.length > n ? a.slice(0, n).join(', ') + ' and ' + (a.length - n) + ' more' : a.join(', ')) : 'n/a';
  // pure: the popup content for one feature of one layer (also used by the tests)
  function popupFor(kind, f, D) {
    const lm = (D && D.land && D.land.meta) || {};
    if (kind === 'ev_wells') return evPop({ title: `Groundwater well · ${f.village || 'unnamed'}${f.mandal ? ', ' + f.mandal : ''}`, value: `${f.latest != null ? f.latest.toFixed(1) : 'n/a'} m below ground in ${f.month || 'latest month'}`,
      rows: [['Dry season (Apr-May mean)', f.pre != null ? f.pre.toFixed(1) + ' m' : null], ['After monsoon (Oct-Nov mean)', f.post != null ? f.post.toFixed(1) + ' m' : null], ['Rebound', f.rec != null ? (f.rec >= 0 ? '+' : '') + f.rec.toFixed(1) + ' m' : null], ['Trend 2021-25', f.trend != null ? (f.trend >= 0 ? '+' : '') + f.trend.toFixed(2) + ' m/yr (positive = falling)' : 'not enough years']],
      source: 'Telangana Ground Water Department monthly piezometer readings (Open Data Telangana)', period: `${f.y0}-${f.y1}, ${f.months} monthly readings, latest ${f.month}`, res: 'one well', conf: 'medium for this well; nearby wells can differ by metres', caveat: 'Depth is metres below ground level: larger means deeper and worse. A neighbouring well is not your borewell.' });
    if (kind === 'ev_gwp') { const a = f.attrs || [], g = Object.fromEntries(GWPF.map((k, i) => [k, a[i]]));
      return evPop({ title: `Hydrogeology unit · ${(g.landform || 'landform n/a').replace(/\s*\(.*\)/, '')}`, value: `${g.recharge ? String(g.recharge).toLowerCase() + ' recharge' : 'recharge not stated'} · ${(g.rock || 'rock n/a').replace(/\s*\(\d+\)/, '').toLowerCase()}`,
        rows: [['Depth to water level', g.depth_to_water], ['Suggested well depth', g.well_depth], ['Typical yield', g.yield], ['Success rate', g.success], ['Water quality', g.water_quality], ['Remarks', g.remarks]],
        source: 'Telangana State GIS groundwater-potential (hydro-geomorphological) map', period: 'undated regional survey', res: 'map unit, about 1:50,000', conf: 'low', caveat: 'Describes what wells usually yield in this kind of ground. It is not a promise for any one plot.' }); }
    if (kind === 'ev_hv') return f.sub
      ? evPop({ title: `Substation · ${f.sub.name}`, value: f.sub.volt || 'voltage n/a', source: 'Telangana State GIS substations (TCUR layer)', period: 'undated', res: 'point', conf: 'medium', caveat: 'A nearby substation can mean a robust supply but also noise and hum.' })
      : evPop({ title: `High-voltage line · ${f.line.name || 'unnamed'}`, value: f.line.kv ? f.line.kv + ' kV' : 'voltage n/a', rows: [['Length (km)', f.line.len]], source: 'Telangana State GIS electric transmission layer (TCUR)', period: 'undated', res: 'line, positional accuracy not published', conf: 'medium', caveat: 'Proximity to a line does not by itself mean a no-build corridor applies.' });
    if (kind === 'ev_lost') return evPop({ title: 'Water body recorded as disappeared', value: f.a && f.a[1] != null ? Number(f.a[1]).toFixed(1) + ' ha mapped extent' : 'size n/a', rows: [['Type', f.a && f.a[0]]],
      source: 'HMDA / TGRAC water-body assessment, "Water Bodies - Disappeared" layer', period: 'undated', res: 'polygon', conf: 'medium', caveat: 'A map record of a tank that no longer exists on the ground. It is not a legal finding and does not itself prove encroachment or a restriction.' });
    if (kind === 'ev_streams') return evPop({ title: `Natural stream · ${f.n || 'unnamed'}`, value: `stream order ${f.o != null ? f.o : '?'} (higher = larger catchment)`,
      source: 'Telangana State GIS stream-order layer (terrain-derived network)', period: 'undated', res: 'line, positional accuracy not published', conf: 'low', caveat: 'Shows where the terrain model puts a natural channel. It does not prove an open or buried channel crosses a plot, or that a plot floods.' });
    if (kind === 'ev_tankcap') { const a = f.a || [];
      return evPop({ title: `Tank · ${a[0] || 'unnamed'}${a[9] ? ', ' + a[9] : ''}`, value: `2023 status: ${TKLAB[a[5]] || 'not classified'} (2011: ${TKLAB[a[4]] || 'not classified'})`,
        rows: [['Mapped area', a[1] != null ? (a[1] / 1e4).toFixed(1) + ' ha' : null], ['Bund height', a[2] != null ? a[2] + ' m' : null], ['Estimated design capacity', a[3] != null ? (a[3] / 1e6).toFixed(2) + ' million m³ (area × bund height ÷ 2)' : 'not available: no bund height in the source'], ['Mapped from', a[6]], ['Origin period', a[7]], ['Type', a[8]]],
        source: 'TGRAC / HMDA water-body layer (HMDA-ORR-GHMC)', period: 'extent from topo sheet or revenue map; status classes 2011 and 2023', res: 'polygon', conf: 'low', caveat: 'The outline is a mapped extent, not a legal boundary, and the status is a satellite classification, not verified encroachment. Capacity is the source\'s estimate, not measured storage.' }); }
    if (kind === 'ev_tankhy') return evPop({ title: `Tank · ${f.name || 'unnamed'}${f.village ? ', ' + f.village : ''}`, value: `satellite status 2023: ${HYLAB[f.s23] || 'not classified'} (2014: ${HYLAB[f.s14] || 'not classified'})`,
      source: 'TGRAC / HYDRAA water-body assessment', period: 'imagery 2014 and 2023', res: 'polygon', conf: 'medium', caveat: 'A satellite classification, not a legal notification or a verified encroachment finding.' });
    if (kind === 'ev_plots') {
      const ha = f.area >= 10000 ? (f.area / 1e4).toFixed(2) + ' ha' : Math.round(f.area || 0).toLocaleString('en-IN') + ' m²';
      const note = f.code === 2 ? 'Mapped as a road, canal, stream or tank feature, not a plot. ' : f.code === 1 ? 'The source flags this number as duplicate or unreadable. ' : '';
      return evPop({ title: `Survey no. ${f.n}`, value: `${f.v || 'village n/a'}${f.m ? ', ' + f.m : ''} · ${ha}`, rows: [['Remark in the source', f.rem || null]],
        source: 'Telangana State GIS cadastral layer (TGRAC)', period: 'undated (service document created 2025-04-19)', res: 'drawn outline, about 1 m', conf: f.code ? 'low' : 'medium', caveat: note + 'A drawn outline is not a legal boundary and says nothing about title or ownership. A survey number can hold many house plots.' })
        + (f.code === 2 ? '' : `<div style="margin-top:8px"><button type="button" class="v-btn sm" data-act="plot-use" data-n="${escH(f.n)}" data-v="${escH(f.v)}" data-lat="${Number(f.lat).toFixed(6)}" data-lon="${Number(f.lon).toFixed(6)}">Check this plot</button></div>`);
    }
    if (kind === 'ev_heat') return evPop({ title: 'Dry-season surface heat', value: `${f.lst.toFixed(1)} °C land-surface · NDVI ${f.ndvi != null ? f.ndvi.toFixed(2) : 'n/a'}`, rows: [['Hotter than', f.pct != null ? Math.round(f.pct * 100) + '% of the city' : null]],
      source: 'Landsat 8/9 Collection 2 Level-2 (USGS) via Microsoft Planetary Computer', period: `${(D && D.heat && D.heat.meta && D.heat.meta.window) || 'Mar-May 2024-26'}, ${(D && D.heat && D.heat.meta && D.heat.meta.scenes) || '?'} scenes`, res: '150 m cell (30 m source)', conf: 'medium', caveat: 'Surface temperature of roofs, roads and soil, not the air temperature a resident feels.' });
    return '';
  }
  const EVINFO = {
    ev_wells: D => ({ title: 'Groundwater wells', swatch: [['#38bdf8', '< 5 m'], ['#22c55e', '5-10 m'], ['#eab308', '10-20 m'], ['#ef4444', '> 20 m']], unit: 'depth below ground, latest month', note: `Ground Water Dept monthly readings, latest ${((D.gwSt || []).reduce((m, x) => x.month > m ? x.month : m, '')) || 'n/a'}. One well ≠ your borewell.` }),
    ev_gwp: D => ({ title: 'Groundwater potential zones', swatch: [['#7f1d1d', 'nil'], ['#f97316', 'poor'], ['#eab308', 'limited'], ['#84cc16', 'moderate'], ['#22c55e', 'good'], ['#64748b', 'not stated']], unit: 'recharge condition', note: 'Regional hydrogeology map, undated, about 1:50,000. Low confidence at plot level.' }),
    ev_plots: D => ({ title: 'Survey plots', swatch: [['#0b63ce', 'survey outline'], ['#965800', 'number flagged at source'], ['#94a3b8', 'road / canal / tank'], ['#16803c', 'matched to your pin']], unit: 'zoom in to see them', note: 'State cadastral outlines, undated. Drawn outlines, not legal boundaries; a survey number can hold many house plots. Click one to check it.' }),
    ev_heat: D => ({ title: 'Dry-season surface heat', swatch: [['rgb(49,130,189)', 'cooler'], ['rgb(250,220,90)', 'median'], ['rgb(215,48,39)', 'hotter']], unit: 'land-surface temperature', note: `Landsat ${D.heat && D.heat.meta ? D.heat.meta.scenes : '?'} clear scenes, Mar-May 2024-26. Click for the value.` }),
    ev_hv: D => ({ title: 'High-voltage lines and substations', swatch: [['#f43f5e', 'transmission line'], ['#fb923c', 'substation']], unit: '', note: 'State GIS (TCUR layer), undated. Proximity is not a legal corridor.' }),
    ev_lost: D => ({ title: 'Water bodies recorded as disappeared', swatch: [['#ef4444', 'recorded as disappeared']], unit: '', note: 'HMDA / TGRAC map record, undated. Not a legal finding.' }),
    ev_streams: D => ({ title: 'Natural streams (order)', swatch: [['#93c5fd', 'order 2'], ['#3b82f6', 'order 4'], ['#1d4ed8', 'order 6']], unit: 'line weight rises with order', note: 'Terrain-derived network, undated. Does not prove a buried channel.' }),
    ev_tankcap: D => ({ title: 'Tanks: 2023 status and design capacity', swatch: [['#22c55e', 'live'], ['#f97316', 'partially encroached'], ['#ef4444', 'totally encroached'], ['#94a3b8', 'dead (no storage)']], unit: 'satellite class; capacity is an estimate', note: 'TGRAC / HMDA layer, status 2011 and 2023. Classification, not verified encroachment.' })
  };

  /* ---------------- Leaflet ---------------- */
  function leaflet() {
    const b = cfg.bounds, map = L.map(el, { preferCanvas: true, zoomControl: false, minZoom: 9, maxZoom: 19 });
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    map.fitBounds([[b[1], b[0]], [b[3], b[2]]], { paddingTopLeft: [padL(), 20] });
    // Hyderabad only: the 145 wards plus the ORR / HMDA fringe; no panning or zooming out to the rest of the world
    const HYD = L.latLngBounds(HYD_BOX);
    map.setMaxBounds(HYD); map.options.maxBoundsViscosity = 1;
    const lockZoom = () => { const s = map.getSize(); if (!s.x || !s.y) return; const z = map.getBoundsZoom(HYD, true); if (isFinite(z)) map.setMinZoom(Math.min(12, Math.max(9, z))); };
    lockZoom(); map.on('resize', lockZoom);
    // Basemap: OpenFreeMap vector tiles (OpenStreetMap data): crisp labels and real building footprints at every zoom; free for commercial use with attribution, provided as-is.
    // If MapLibre did not load, WebGL is unavailable or the style cannot load in time, the plain OpenStreetMap raster tiles take over, so the map never goes blank.
    const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' });
    let base = osm, vec = null;
    const useRaster = why => { if (vec) { try { map.removeLayer(vec); } catch (e) { } vec = null; } base = osm; if (!map.hasLayer(osm)) osm.addTo(map); map.getPane('tilePane').classList.add('inv'); if (why) console.warn('Vector basemap off, using OpenStreetMap tiles:', why); };
    try {
      if (!(window.maplibregl && L.maplibreGL)) throw new Error('MapLibre not loaded');
      vec = L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty', attribution: '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>' }).addTo(map); base = vec;
      const gl = vec.getMaplibreMap(); let loaded = false; gl.on('load', () => { loaded = true; });
      gl.on('error', e => { if (!loaded) useRaster(e && e.error && e.error.message); });
      // only VISIBLE seconds count: a background tab pauses drawing, and that is not a failure
      let seen = 0; const wd = setInterval(() => { if (loaded || base !== vec) return clearInterval(wd); if (document.visibilityState === 'visible' && ++seen >= 20) { clearInterval(wd); useRaster('style did not load in 20 visible seconds'); } }, 1000);
    } catch (e) { useRaster(e.message); }
    const esri = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Imagery © Esri' });
    const wards = L.layerGroup(), lakes = L.layerGroup(), ponds = L.layerGroup(), selStyle = { weight: 2.8, color: '#ffffff', opacity: .95 }, baseStyle = { weight: .7, color: '#cbd5e1', opacity: .28 };
    const wardLayers = new Map();
    for (const w of cfg.wards) {
      const p = L.polygon(w.rings.map(r => r.map(q => [q[1], q[0]])), { ...baseStyle, fillColor: riskColor(w.pct), fillOpacity: .34 })
        .bindTooltip(w.name.replace(/^Ward \d+ /, '') + ' · flood rank ' + Math.round(w.pct * 100) + '/100', { sticky: true });
      p._w = w; p.on('click', e => cfg.onPick(e.latlng.lat, e.latlng.lng)); p.addTo(wards); wardLayers.set(w.id, p);
    }
    for (const wb of cfg.water) if (wb.cls !== 'tiny') for (const r of wb.rings)
      L.polygon(r.map(q => [q[1], q[0]]), { color: '#7dd3fc', weight: 1, fillColor: '#38bdf8', fillOpacity: wb.cls === 'lake' ? .5 : .4, interactive: !!wb.name }).bindTooltip(wb.name || 'water body').addTo(wb.cls === 'lake' && wb.area >= 250000 ? lakes : ponds);   // only the ~46 big lakes show in the city view
    wards.addTo(map); lakes.addTo(map);
    // hundreds of small ponds make the city view unreadable, so they only appear once you zoom in
    const syncPonds = () => { const want = st.layers.lakes && map.getZoom() >= 13; if (want && !map.hasLayer(ponds)) ponds.addTo(map); if (!want && map.hasLayer(ponds)) map.removeLayer(ponds); };
    map.on('zoomend', syncPonds);
    // the ward tint is strong in the city view and fades as you zoom in, so streets stay readable
    const fadeWards = () => { const z = map.getZoom(), o = z <= 12 ? .34 : z >= 15 ? .06 : .34 - (z - 12) * (.28 / 3); wardLayers.forEach(p => p.setStyle({ fillOpacity: o })); };
    map.on('zoomend', fadeWards);
    map.on('click', e => cfg.onPick(e.latlng.lat, e.latlng.lng));
    let pin = null, ring = null, sel = null; const poi = {}, govL = {}, evL = {};
    const heatLookup = (D, lat, lon) => { const h = D.heat; if (!h || !h.lst) return null; const m = h.meta, i = Math.floor((lon - m.bbox[0]) / m.cell_deg), j = Math.floor((m.bbox[3] - lat) / m.cell_deg); if (i < 0 || j < 0 || i >= m.nx || j >= m.ny) return null; const v = h.lst[j * m.nx + i]; if (v == null) return null; const n = h.ndvi[j * m.nx + i]; const below = D.heatSorted ? D.heatSorted.filter(x => x <= v).length / D.heatSorted.length : null; return { lst: v / 10, ndvi: n == null ? null : n / 100, pct: below }; };
    const heatCanvas = D => { const h = D.heat, m = h.meta, c = document.createElement('canvas'); c.width = m.nx; c.height = m.ny; const x = c.getContext('2d'), im = x.createImageData(m.nx, m.ny); const s = D.heatSorted, lo = s[Math.floor(s.length * .02)], hi = s[Math.floor(s.length * .98)], mid = s[s.length >> 1];
      const col = v => { const t = v <= mid ? (v - lo) / Math.max(1, mid - lo) : 1 + (v - mid) / Math.max(1, hi - mid); const k = Math.max(0, Math.min(2, t)); const A = [49, 130, 189], B = [250, 220, 90], C = [215, 48, 39]; return k < 1 ? A.map((a, i) => a + (B[i] - a) * k) : B.map((b, i) => b + (C[i] - b) * (k - 1)); };
      for (let i = 0; i < h.lst.length; i++) { const v = h.lst[i]; if (v == null) { im.data[i * 4 + 3] = 0; continue; } const c3 = col(v); im.data[i * 4] = c3[0]; im.data[i * 4 + 1] = c3[1]; im.data[i * 4 + 2] = c3[2]; im.data[i * 4 + 3] = 150; }
      x.putImageData(im, 0, 0); return c.toDataURL(); };
    map.on('click', e => { if (evL.ev_heat && cfg.D) { const f = heatLookup(cfg.D, e.latlng.lat, e.latlng.lng); if (f) L.popup({ maxWidth: 300 }).setLatLng(e.latlng).setContent(popupFor('ev_heat', f, cfg.D)).openOn(map); } });
    // survey-plot outlines: the state cadastral layer, loaded lazily for the area in view and only when zoomed in (hundreds of polygons at most)
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
      getView() { const c = map.getCenter(); return { zoom: map.getZoom(), lat: c.lat, lon: c.lng, base: base === vec ? 'vector' : 'raster', plots: plotsG.getLayers().length }; },
      jump(lat, lon, zoom) { map.setView([lat, lon], zoom, { animate: false }); },
      setMatch(rings, status) {
        const key = rings ? status + '|' + rings[0][0][0] + ',' + rings[0][0][1] : ''; if (key === matchKey) return; matchKey = key;
        if (matchL) { map.removeLayer(matchL); matchL = null; } if (!rings) return;
        const col = status === 'verified' ? '#16803c' : status === 'approximate' ? '#965800' : '#0b63ce';
        matchL = L.polygon(rings, { color: col, weight: 3, fillColor: col, fillOpacity: .13, interactive: false, bubblingMouseEvents: false }).addTo(map);
      },
      showEv(kind, on) {
        if (kind === 'ev_plots') { plotsOn = on; if (on && map.getZoom() < 16) map.flyTo(map.getCenter(), 17, { duration: .6 }); else drawPlots(); return; }
        if (evL[kind]) { map.removeLayer(evL[kind]); evL[kind] = null; }
        if (!on || !cfg.D) return;
        const BM = { bubblingMouseEvents: false };   // a click on a feature opens its popup and must not also drop a pin
        const D = cfg.D, g = L.layerGroup(), pop = (layer, html) => layer.bindPopup(html, { maxWidth: 300 });
        if (kind === 'ev_wells') for (const w of D.gwSt || []) pop(L.circleMarker([w.lat, w.lon], { ...BM, radius: 5, color: '#fff', weight: 1, fillColor: depthCol(w.latest), fillOpacity: .95 }), popupFor(kind, w, D)).addTo(g);
        if (kind === 'ev_gwp') for (const u of (D.landL && D.landL.gwp) || []) { const a = (D.land.gwp_attrs || [])[u.i] || [], c = REC_COL[recKey(a)] || '#64748b'; for (const r of u.r) pop(L.polygon(r, { ...BM, color: c, weight: .6, fillColor: c, fillOpacity: .38 }), popupFor(kind, { attrs: a }, D)).addTo(g); }
        if (kind === 'ev_hv') { for (const t of (D.landL && D.landL.tx) || []) for (const p of t.p) pop(L.polyline(p, { ...BM, color: '#f43f5e', weight: 2.5, opacity: .9 }), popupFor(kind, { line: { name: t.a[0], kv: t.a[3], len: t.a[4] } }, D)).addTo(g); for (const q of (D.landL && D.landL.sub) || []) pop(L.circleMarker(q.ll, { ...BM, radius: 7, color: '#fff', weight: 1.5, fillColor: '#fb923c', fillOpacity: 1 }), popupFor(kind, { sub: { name: q.a[0], volt: q.a[1] } }, D)).addTo(g); }
        if (kind === 'ev_lost') for (const u of (D.landL && D.landL.lost) || []) for (const r of u.r) pop(L.polygon(r, { ...BM, color: '#ef4444', weight: 1.4, dashArray: '5 4', fillColor: '#ef4444', fillOpacity: .25 }), popupFor(kind, { a: u.a }, D)).addTo(g);
        if (kind === 'ev_streams') for (const s of (D.tankL && D.tankL.streams) || []) { const o = s.o || 2, c = o >= 5 ? '#1d4ed8' : o >= 3 ? '#3b82f6' : '#93c5fd'; for (const p of s.p) pop(L.polyline(p, { ...BM, color: c, weight: .8 + o * .45, opacity: .85 }), popupFor(kind, s, D)).addTo(g); }
        if (kind === 'ev_tankcap') for (const t of (D.tankL && D.tankL.tanks) || []) { const c = TKCOL[t.a[5]] || '#94a3b8'; pop(L.polygon(t.r[0], { ...BM, color: c, weight: 1, fillColor: c, fillOpacity: .5 }), popupFor(kind, t, D)).addTo(g); }
        if (kind === 'ev_heat' && D.heat && D.heat.lst) { const m = D.heat.meta, ov = L.imageOverlay(heatCanvas(D), [[m.bbox[1], m.bbox[0]], [m.bbox[3], m.bbox[2]]], { opacity: .62, interactive: false }); g.addLayer(ov); }
        g.addTo(map); evL[kind] = g;
      },
      setPin(lat, lon, wid, fly) {
        if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring);
        pin = L.marker([lat, lon], { icon: L.divIcon({ className: '', html: '<div class="pin"></div>', iconSize: [30, 30], iconAnchor: [15, 30] }) }).addTo(map);
        ring = L.circle([lat, lon], { radius: 1000, color: '#38bdf8', weight: 1.5, dashArray: '6 6', fillOpacity: .05, interactive: false }).addTo(map);
        if (sel != null && wardLayers.get(sel)) wardLayers.get(sel).setStyle(baseStyle);
        sel = wid; if (wardLayers.get(wid)) wardLayers.get(wid).setStyle(selStyle);
        const sz = map.getSize(); if (fly && sz.x && sz.y) map.flyTo([lat, lon], Math.max(map.getZoom(), 15), { duration: .8 });   // a map with no size yet (opened straight into a report) cannot fly
      },
      clearPin() { if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring); pin = ring = null; },
      setLayer(n, on) { st.layers[n] = on; const g = n === 'wards' ? wards : lakes; on ? g.addTo(map) : map.removeLayer(g); if (n === 'lakes') syncPonds(); },
      setColorMode(mode) { wardLayers.forEach(p => { p.setStyle({ fillColor: wardFill(p._w, mode) }); p.setTooltipContent(wardLabel(p._w, mode)); }); },
      showPoi(cat, rows, on) {
        if (poi[cat]) { map.removeLayer(poi[cat]); poi[cat] = null; }
        if (!on) return;
        const g = L.layerGroup(); for (const p of rows) L.circleMarker([p[0], p[1]], { radius: 5, color: '#fff', weight: 1, fillColor: POI_COL[cat] || '#fff', fillOpacity: .95 }).bindTooltip(p[2] || cat).addTo(g);
        g.addTo(map); poi[cat] = g;
      },
      showGov(kind, on) {
        if (govL[kind]) { map.removeLayer(govL[kind]); govL[kind] = null; }
        if (!on) return;
        const g = L.layerGroup(), G = cfg.gov;
        if (kind === 'nalas') for (const n of G.nalas) for (const path of n.paths) L.polyline(path, { color: '#f472b6', weight: 2.5, opacity: .9 }).bindTooltip(n.name || 'nala').addTo(g);
        if (kind === 'drains') for (const path of G.drains) L.polyline(path, { color: '#60a5fa', weight: 1, opacity: .55, interactive: false }).addTo(g);
        if (kind === 'tanks') for (const t of cfg.hy.tanks) for (const rg of t.rings) L.polygon(rg, { color: HYCOL[t.s23] || '#94a3b8', weight: 1, fillColor: HYCOL[t.s23] || '#94a3b8', fillOpacity: .55 }).bindPopup(popupFor('ev_tankhy', t, cfg.D), { maxWidth: 300 }).addTo(g);
        if (kind === 'spots') for (const q of G.inundation) L.circleMarker([q[0], q[1]], { radius: 8, color: '#fff', weight: 2, fillColor: '#f97316', fillOpacity: 1 }).bindTooltip('Listed inundation area: ' + q[2]).addTo(g);
        g.addTo(map); govL[kind] = g;
      },
      setSatellite(on) { st.sat = on; const tp = map.getPane('tilePane'); if (on) { esri.addTo(map); map.removeLayer(base); tp.classList.add('sat'); tp.classList.remove('inv'); } else { base.addTo(map); map.removeLayer(esri); tp.classList.remove('sat'); if (base === osm) tp.classList.add('inv'); } },
      fitCity() { const bb = cfg.bounds; map.fitBounds([[bb[1], bb[0]], [bb[3], bb[2]]], { paddingTopLeft: [padL(), 20] }); },
      resize() { map.invalidateSize(); }, destroy() { map.remove(); }
    };
  }

  /* ---------------- Google ---------------- */
  const DARK = [
    { elementType: 'geometry', stylers: [{ color: '#16213a' }] }, { elementType: 'labels.text.fill', stylers: [{ color: '#9fb0cc' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0a0f1a' }] }, { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#27395e' }] },
    { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#8a9ab5' }] }, { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0b3a5a' }] },
    { featureType: 'poi', stylers: [{ visibility: 'off' }] }, { featureType: 'poi.park', stylers: [{ visibility: 'on' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#12343a' }] }, { featureType: 'transit', stylers: [{ visibility: 'simplified' }] },
    { featureType: 'administrative', elementType: 'geometry.stroke', stylers: [{ color: '#2a3b5c' }] }];
  function loadGoogle(key) {
    return new Promise((res, rej) => {
      const t = setTimeout(() => rej(new Error('timeout')), 9000);
      window.__gmReady = () => { clearTimeout(t); res(); };
      window.gm_authFailure = () => { clearTimeout(t); rej(new Error('auth')); if (impl && engine === 'google') fallback('Google Maps key rejected'); };
      const s = document.createElement('script');
      s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&callback=__gmReady&v=weekly`;
      s.onerror = () => { clearTimeout(t); rej(new Error('load')); };
      document.head.appendChild(s);
    });
  }
  function google() {
    const gm = google_maps(), b = cfg.bounds;
    const map = new gm.Map(el, { center: { lat: 17.40, lng: 78.45 }, zoom: 11, disableDefaultUI: true, zoomControl: true, zoomControlOptions: { position: gm.ControlPosition.RIGHT_BOTTOM }, gestureHandling: 'greedy', styles: DARK, clickableIcons: false, backgroundColor: '#0a0f1a' });
    map.fitBounds({ south: b[1], west: b[0], north: b[3], east: b[2] }, { left: padL(), top: 20, right: 20, bottom: 20 });
    map.setOptions({ restriction: { latLngBounds: { south: HYD_BOX[0][0], west: HYD_BOX[0][1], north: HYD_BOX[1][0], east: HYD_BOX[1][1] }, strictBounds: true }, minZoom: 10 });
    const tip = document.createElement('div'); tip.className = 'gtip'; el.parentElement.appendChild(tip);
    el.addEventListener('mousemove', e => { const r = el.getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 14) + 'px'; tip.style.top = (e.clientY - r.top + 14) + 'px'; });
    const wardPolys = new Map(), lakePolys = [];
    const ringPath = r => r.map(q => ({ lat: q[1], lng: q[0] }));
    for (const w of cfg.wards) {   // one polygon per ring: avoids Google treating opposite-winding rings as holes
      const lab = { t: wardLabel(w, 'flood') }, list = [];
      for (const r of w.rings) {
        const p = new gm.Polygon({ paths: ringPath(r), strokeColor: '#0a0f1a', strokeWeight: .6, fillColor: riskColor(w.pct), fillOpacity: .2, map });
        p.addListener('click', e => cfg.onPick(e.latLng.lat(), e.latLng.lng()));
        p._w = w; p._lab = lab;
        p.addListener('mouseover', () => { tip.textContent = lab.t; tip.style.display = 'block'; });
        p.addListener('mouseout', () => { tip.style.display = 'none'; });
        list.push(p);
      }
      wardPolys.set(w.id, list);
    }
    for (const wb of cfg.water) if (wb.cls !== 'tiny') for (const r of wb.rings)
      lakePolys.push(new gm.Polygon({ paths: ringPath(r), strokeColor: '#38bdf8', strokeWeight: 1, fillColor: '#38bdf8', fillOpacity: wb.cls === 'lake' ? .5 : .38, clickable: false, map }));
    map.addListener('click', e => cfg.onPick(e.latLng.lat(), e.latLng.lng()));
    let pin = null, ring = null, sel = null; const poi = {}, govG = {};
    const pinIcon = { url: 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="38" height="48" viewBox="0 0 38 48"><path d="M19 2C10 2 3 9 3 18c0 12 16 28 16 28s16-16 16-28C35 9 28 2 19 2z" fill="#38bdf8" stroke="#fff" stroke-width="3"/><circle cx="19" cy="18" r="6" fill="#04121b"/></svg>'), scaledSize: new gm.Size(38, 48), anchor: new gm.Point(19, 46) };
    return {
      setPin(lat, lon, wid, fly) {
        if (pin) pin.setMap(null); if (ring) ring.setMap(null);
        pin = new gm.Marker({ position: { lat, lng: lon }, map, icon: pinIcon, zIndex: 50 });
        ring = new gm.Circle({ center: { lat, lng: lon }, radius: 1000, strokeColor: '#38bdf8', strokeOpacity: .9, strokeWeight: 1.5, fillColor: '#38bdf8', fillOpacity: .05, map, clickable: false });
        if (sel != null && wardPolys.get(sel)) wardPolys.get(sel).forEach(p => p.setOptions({ strokeColor: '#0a0f1a', strokeWeight: .6 }));
        sel = wid; if (wardPolys.get(wid)) wardPolys.get(wid).forEach(p => p.setOptions({ strokeColor: '#38bdf8', strokeWeight: 2.6 }));
        if (fly) { map.panTo({ lat, lng: lon }); if (map.getZoom() < 15) map.setZoom(15); }
      },
      clearPin() { if (pin) pin.setMap(null); if (ring) ring.setMap(null); pin = ring = null; },
      setLayer(n, on) { (n === 'wards' ? [...wardPolys.values()].flat() : lakePolys).forEach(p => p.setMap(on ? map : null)); },
      setColorMode(mode) { wardPolys.forEach(list => list.forEach(p => { p.setOptions({ fillColor: wardFill(p._w, mode) }); p._lab.t = wardLabel(p._w, mode); })); },
      showPoi(cat, rows, on) {
        (poi[cat] || []).forEach(m => m.setMap(null)); poi[cat] = [];
        if (!on) return;
        poi[cat] = rows.map(p => new gm.Marker({ position: { lat: p[0], lng: p[1] }, map, title: p[2] || cat, icon: { path: gm.SymbolPath.CIRCLE, scale: 5.5, fillColor: POI_COL[cat] || '#fff', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 1.2 } }));
      },
      showGov(kind, on) {
        (govG[kind] || []).forEach(o => o.setMap(null)); govG[kind] = [];
        if (!on) return;
        const G = cfg.gov, path = p => p.map(q => ({ lat: q[0], lng: q[1] })), list = [];
        if (kind === 'nalas') for (const n of G.nalas) for (const p of n.paths) list.push(new gm.Polyline({ path: path(p), strokeColor: '#f472b6', strokeWeight: 2.5, map }));
        if (kind === 'drains') for (const p of G.drains) list.push(new gm.Polyline({ path: path(p), strokeColor: '#60a5fa', strokeWeight: 1, strokeOpacity: .55, clickable: false, map }));
        if (kind === 'tanks') for (const t of cfg.hy.tanks) for (const rg of t.rings) list.push(new gm.Polygon({ paths: path(rg), strokeColor: HYCOL[t.s23] || '#94a3b8', strokeWeight: 1, fillColor: HYCOL[t.s23] || '#94a3b8', fillOpacity: .55, map }));
        if (kind === 'spots') for (const q of G.inundation) list.push(new gm.Marker({ position: { lat: q[0], lng: q[1] }, map, title: 'Listed inundation area: ' + q[2], icon: { path: gm.SymbolPath.CIRCLE, scale: 8, fillColor: '#f97316', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 } }));
        govG[kind] = list;
      },
      showEv() { /* evidence layers are drawn on the OpenStreetMap engine only */ },
      setMatch() { /* the matched plot is drawn on the Leaflet engine only */ },
      setSatellite(on) { map.setMapTypeId(on ? 'hybrid' : 'roadmap'); },
      fitCity() { map.fitBounds({ south: b[1], west: b[0], north: b[3], east: b[2] }, { left: padL(), top: 20, right: 20, bottom: 20 }); },
      resize() { gm.event.trigger(map, 'resize'); }, destroy() { el.innerHTML = ''; tip.remove(); }
    };
  }
  const google_maps = () => window.google.maps;

  /* ---------------- shared state replay + fallback ---------------- */
  function replay() {
    for (const n of ['wards', 'lakes']) if (!st.layers[n]) impl.setLayer(n, false);
    for (const c in st.poi) if (st.poi[c]) impl.showPoi(c, cfg.poiRows(c), true);
    if (st.sat) impl.setSatellite(true);
    for (const k in st.gov) if (st.gov[k]) impl.showGov(k, true);
    for (const k in st.ev) if (st.ev[k]) impl.showEv(k, true);
    if (st.mode !== 'flood') impl.setColorMode(st.mode);
    if (st.match) impl.setMatch(st.match.rings, st.match.status);
    if (st.pin) impl.setPin(st.pin.lat, st.pin.lon, st.pin.wid, false);
  }
  function fallback(why) {
    try { impl.destroy(); } catch (e) { }
    engine = 'leaflet'; el.innerHTML = ''; impl = leaflet(); replay();
    if (cfg.onEngine) cfg.onEngine(engine, why);
  }
  async function init(container, config) {
    el = container; cfg = config;
    if (cfg.googleKey) {
      try { await loadGoogle(cfg.googleKey); impl = google(); engine = 'google'; if (cfg.onEngine) cfg.onEngine(engine); return engine; }
      catch (e) { if (cfg.onEngine) cfg.onEngine('leaflet', 'Google Maps unavailable (' + e.message + ')'); }
    }
    el.innerHTML = ''; engine = 'leaflet'; impl = leaflet(); if (cfg.onEngine && !cfg.googleKey) cfg.onEngine(engine);
    return engine;
  }
  // Every call goes through here: if the Google engine throws for any reason mid-demo, switch to Leaflet and carry on.
  function call(name, ...args) {
    if (!impl) return;
    try { return impl[name](...args); }
    catch (e) { console.error('Map engine error in', name, e); if (engine === 'google') { fallback('Google Maps hit an error'); try { return impl[name](...args); } catch (e2) { console.error(e2); } } }
  }
  return {
    init,
    get engine() { return engine; },
    setPin(lat, lon, wid, fly = true) { st.pin = { lat, lon, wid }; call('setPin', lat, lon, wid, fly); },
    clearPin() { st.pin = null; call('clearPin'); },
    setLayer(n, on) { st.layers[n] = on; call('setLayer', n, on); },
    showPoi(cat, on) { st.poi[cat] = on; if (impl) call('showPoi', cat, cfg.poiRows(cat), on); },
    setSatellite(on) { st.sat = on; call('setSatellite', on); },
    showGov(kind, on) { st.gov[kind] = on; call('showGov', kind, on); },
    showEv(kind, on) { st.ev[kind] = on; call('showEv', kind, on); },
    jump(lat, lon, zoom) { call('jump', lat, lon, zoom); },
    getView() { try { return impl && impl.getView ? impl.getView() : null; } catch (e) { return null; } },
    setMatch(rings, status) { st.match = rings ? { rings, status } : null; call('setMatch', rings, status); },
    popupFor, evInfo: (kind, D) => EVINFO[kind] ? EVINFO[kind](D) : null, EV_KINDS: Object.keys(EVINFO),
    setColorMode(mode) { st.mode = mode; call('setColorMode', mode); },
    fitCity() { call('fitCity'); }, resize() { call('resize'); }
  };
})();
