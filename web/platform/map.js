/* MapKit — one interface, two engines.
 * Google Maps when a browser key is configured and loads cleanly; otherwise (or if Google fails
 * mid-session, e.g. auth/billing error) we fall back to Leaflet + OpenStreetMap so the demo never breaks. */
const MapKit = (() => {
  let impl = null, cfg = null, el = null, engine = 'none';
  const st = { pin: null, layers: { wards: true, lakes: true }, poi: {}, sat: false, mode: 'flood', gov: {} };
  const POI_COL = { hospital: '#ef4444', school: '#eab308', metro: '#a78bfa', fire: '#f97316', market: '#22c55e', park: '#10b981', bank: '#60a5fa', police: '#38bdf8' };
  const riskColor = t => {
    const g = [34, 197, 94], y = [234, 179, 8], o = [249, 115, 22], r = [239, 68, 68], L = (a, b, k) => a.map((v, i) => Math.round(v + (b[i] - v) * k));
    return `rgb(${(t < .34 ? L(g, y, t / .34) : t < .67 ? L(y, o, (t - .34) / .33) : L(o, r, (t - .67) / .33))})`;
  };

  const HYCOL = { L: '#22c55e', PB: '#f97316', TB: '#ef4444', PA: '#eab308', TA: '#dc2626', '?': '#94a3b8' };
  const HYLAB = { L: 'Live', PB: 'Partially encroached (built-up)', TB: 'Totally encroached (built-up)', PA: 'Partially encroached (agriculture)', TA: 'Totally encroached (agriculture)', '?': 'not classified' };
  const wardFill = (w, mode) => mode === 'loc' ? riskColor(1 - Math.max(0, Math.min(1, ((w.loc == null ? 70 : w.loc) - 45) / 50))) : riskColor(w.pct);
  const wardLabel = (w, mode) => w.name.replace(/^Ward \d+ /, '') + (mode === 'loc' ? ' · location score ' + Math.round(w.loc) + '/100' : ' · flood rank ' + Math.round(w.pct * 100) + '/100');

  /* ---------------- Leaflet ---------------- */
  function leaflet() {
    const b = cfg.bounds, map = L.map(el, { preferCanvas: true, zoomControl: false, minZoom: 9, maxZoom: 19 });
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    map.fitBounds([[b[1], b[0]], [b[3], b[2]]], { paddingTopLeft: [440, 20] });
    const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map);
    const esri = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Imagery © Esri' });
    const wards = L.layerGroup(), lakes = L.layerGroup(), selStyle = { weight: 2.6, color: '#38bdf8' }, baseStyle = { weight: .6, color: '#0a0f1a' };
    const wardLayers = new Map();
    for (const w of cfg.wards) {
      const p = L.polygon(w.rings.map(r => r.map(q => [q[1], q[0]])), { ...baseStyle, fillColor: riskColor(w.pct), fillOpacity: .22 })
        .bindTooltip(w.name.replace(/^Ward \d+ /, '') + ' · flood rank ' + Math.round(w.pct * 100) + '/100', { sticky: true });
      p._w = w; p.on('click', e => cfg.onPick(e.latlng.lat, e.latlng.lng)); p.addTo(wards); wardLayers.set(w.id, p);
    }
    for (const wb of cfg.water) if (wb.cls !== 'tiny') for (const r of wb.rings)
      L.polygon(r.map(q => [q[1], q[0]]), { color: '#38bdf8', weight: 1, fillColor: '#38bdf8', fillOpacity: wb.cls === 'lake' ? .55 : .4, interactive: !!wb.name }).bindTooltip(wb.name || 'water body').addTo(lakes);
    wards.addTo(map); lakes.addTo(map);
    map.on('click', e => cfg.onPick(e.latlng.lat, e.latlng.lng));
    let pin = null, ring = null, sel = null; const poi = {}, govL = {};
    return {
      setPin(lat, lon, wid, fly) {
        if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring);
        pin = L.marker([lat, lon], { icon: L.divIcon({ className: '', html: '<div class="pin"></div>', iconSize: [30, 30], iconAnchor: [15, 30] }) }).addTo(map);
        ring = L.circle([lat, lon], { radius: 1000, color: '#38bdf8', weight: 1.5, dashArray: '6 6', fillOpacity: .05, interactive: false }).addTo(map);
        if (sel != null && wardLayers.get(sel)) wardLayers.get(sel).setStyle(baseStyle);
        sel = wid; if (wardLayers.get(wid)) wardLayers.get(wid).setStyle(selStyle);
        if (fly) map.flyTo([lat, lon], Math.max(map.getZoom(), 15), { duration: .8 });
      },
      clearPin() { if (pin) map.removeLayer(pin); if (ring) map.removeLayer(ring); pin = ring = null; },
      setLayer(n, on) { const g = n === 'wards' ? wards : lakes; on ? g.addTo(map) : map.removeLayer(g); },
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
        if (kind === 'tanks') for (const t of cfg.hy.tanks) for (const rg of t.rings) L.polygon(rg, { color: HYCOL[t.s23] || '#94a3b8', weight: 1, fillColor: HYCOL[t.s23] || '#94a3b8', fillOpacity: .55 }).bindTooltip((t.name || 'Tank') + ' · ' + HYLAB[t.s23]).addTo(g);
        if (kind === 'spots') for (const q of G.inundation) L.circleMarker([q[0], q[1]], { radius: 8, color: '#fff', weight: 2, fillColor: '#f97316', fillOpacity: 1 }).bindTooltip('Listed inundation area: ' + q[2]).addTo(g);
        g.addTo(map); govL[kind] = g;
      },
      setSatellite(on) { if (on) { esri.addTo(map); map.removeLayer(osm); map.getPane('tilePane').classList.add('sat'); } else { osm.addTo(map); map.removeLayer(esri); map.getPane('tilePane').classList.remove('sat'); } },
      fitCity() { const bb = cfg.bounds; map.fitBounds([[bb[1], bb[0]], [bb[3], bb[2]]], { paddingTopLeft: [440, 20] }); },
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
    map.fitBounds({ south: b[1], west: b[0], north: b[3], east: b[2] }, { left: 440, top: 20, right: 20, bottom: 20 });
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
      setSatellite(on) { map.setMapTypeId(on ? 'hybrid' : 'roadmap'); },
      fitCity() { map.fitBounds({ south: b[1], west: b[0], north: b[3], east: b[2] }, { left: 440, top: 20, right: 20, bottom: 20 }); },
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
    if (st.mode !== 'flood') impl.setColorMode(st.mode);
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
    setColorMode(mode) { st.mode = mode; call('setColorMode', mode); },
    fitCity() { call('fitCity'); }, resize() { call('resize'); }
  };
})();
