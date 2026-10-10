/* Tiny dependency-free SVG chart helpers. All return HTML strings. */
const Charts = (() => {
  const TIER_COL = ['#22c55e', '#a3e635', '#eab308', '#f97316', '#ef4444'];
  const f1 = x => (Math.round(x * 10) / 10).toString();
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const pol = (cx, cy, r, deg) => [cx + r * Math.cos(deg * Math.PI / 180), cy - r * Math.sin(deg * Math.PI / 180)];
  const arc = (cx, cy, r0, r1, a0, a1) => { // angles in degrees, 180 (left) -> 0 (right)
    const [x0, y0] = pol(cx, cy, r1, a0), [x1, y1] = pol(cx, cy, r1, a1), [x2, y2] = pol(cx, cy, r0, a1), [x3, y3] = pol(cx, cy, r0, a0);
    return `M${x0},${y0} A${r1},${r1} 0 0 1 ${x1},${y1} L${x2},${y2} A${r0},${r0} 0 0 0 ${x3},${y3} Z`;
  };

  // Semicircle risk gauge. cuts = tier cut points [c1..c4]; score 0..100.
  function gauge(score, cuts, letter, label) {
    const b = [0, ...cuts, 100], cx = 150, cy = 150, r0 = 92, r1 = 132;
    let segs = '';
    for (let i = 0; i < 5; i++) {
      const a0 = 180 - b[i] * 1.8, a1 = 180 - b[i + 1] * 1.8;
      segs += `<path d="${arc(cx, cy, r0, r1, a0 - .6, a1 + .6)}" fill="${TIER_COL[i]}" opacity="${letter === 'ABCDE'[i] ? 1 : .32}"/>`;
    }
    const ang = 180 - Math.max(0, Math.min(100, score)) * 1.8, [nx, ny] = pol(cx, cy, r1 + 6, ang), [bx, by] = pol(cx, cy, r0 - 14, ang);
    return `<svg viewBox="0 0 300 190" role="img" aria-label="Risk gauge ${esc(label)}">
      ${segs}
      <line x1="${bx}" y1="${by}" x2="${nx}" y2="${ny}" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${nx}" cy="${ny}" r="6" fill="#fff"/>
      <text x="150" y="132" text-anchor="middle" font-size="58" font-weight="800" fill="${TIER_COL['ABCDE'.indexOf(letter)]}">${letter}</text>
      <text x="150" y="160" text-anchor="middle" font-size="17" font-weight="600" fill="#eef3fb">${esc(label)}</text>
      <text x="150" y="182" text-anchor="middle" font-size="14" fill="#8a9ab5">${Math.round(score)} / 100</text>
      <text x="22" y="170" font-size="12" fill="#8a9ab5">low</text><text x="278" y="170" text-anchor="end" font-size="12" fill="#8a9ab5">severe</text>
    </svg>`;
  }

  // Semicircle score dial where HIGHER is BETTER (red -> green). score 0..100.
  function scoreDial(score, label, sub) {
    const cx = 150, cy = 150, r0 = 92, r1 = 132, cols = ['#ef4444', '#f97316', '#eab308', '#a3e635', '#22c55e'];
    let segs = '';
    for (let i = 0; i < 5; i++) segs += `<path d="${arc(cx, cy, r0, r1, 180 - i * 36 - .6, 180 - (i + 1) * 36 + .6)}" fill="${cols[i]}" opacity="${Math.min(4, Math.floor(score / 20)) === i ? 1 : .3}"/>`;
    const ang = 180 - Math.max(0, Math.min(100, score)) * 1.8, [nx, ny] = pol(cx, cy, r1 + 6, ang), [bx, by] = pol(cx, cy, r0 - 14, ang);
    const col = cols[Math.min(4, Math.floor(score / 20))];
    return `<svg viewBox="0 0 300 190" role="img" aria-label="Location score ${Math.round(score)} of 100">${segs}
      <line x1="${bx}" y1="${by}" x2="${nx}" y2="${ny}" stroke="#fff" stroke-width="4" stroke-linecap="round"/><circle cx="${nx}" cy="${ny}" r="6" fill="#fff"/>
      <text x="150" y="134" text-anchor="middle" font-size="54" font-weight="800" fill="${col}">${Math.round(score)}</text>
      <text x="150" y="160" text-anchor="middle" font-size="17" font-weight="600" fill="#eef3fb">${esc(label)}</text>
      <text x="150" y="182" text-anchor="middle" font-size="13" fill="#8a9ab5">${esc(sub || 'Location score / 100')}</text></svg>`;
  }

  // Water depth vs rainfall for one ward.
  function depthCurve(curve, thr, marks, forecastMm) {
    const W = 640, H = 300, L = 52, R = 40, T = 20, B = 44, pw = W - L - R, ph = H - T - B;
    const maxD = Math.max(0.6, ...curve.map(c => c.depth)) * 1.15, maxX = 300;
    const X = mm => L + mm / maxX * pw, Y = d => T + ph - d / maxD * ph;
    let path = `M${X(0)},${Y(0)}`; curve.forEach(c => path += ` L${X(c.mm)},${Y(c.depth)}`);
    const area = path + ` L${X(curve[curve.length - 1].mm)},${Y(0)} Z`;
    let yt = '', step = maxD > 2 ? 0.5 : maxD > 1 ? 0.25 : 0.2;
    for (let v = 0; v <= maxD; v += step) yt += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#ffffff" opacity=".07"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" font-size="12" fill="#8a9ab5">${f1(v)}</text>`;
    let xt = ''; for (let m = 0; m <= 300; m += 50) xt += `<text x="${X(m)}" y="${H - 18}" text-anchor="middle" font-size="12" fill="#8a9ab5">${m}</text>`;
    let mk = '';
    marks.forEach(m => {
      const d = m.depth, x = X(m.mm), y = Y(d);
      mk += `<line x1="${x}" x2="${x}" y1="${y}" y2="${Y(0)}" stroke="${m.color || '#38bdf8'}" stroke-dasharray="4 4" opacity=".8"/>
        <circle cx="${x}" cy="${y}" r="6" fill="${m.color || '#38bdf8'}" stroke="#0a0f1a" stroke-width="2"/>
        <text x="${x}" y="${Math.max(14, y - 12)}" text-anchor="middle" font-size="13" font-weight="700" fill="#eef3fb">${f1(d * 100 / 100)} m</text>
        <text x="${x}" y="${H - 4}" text-anchor="middle" font-size="12" font-weight="700" fill="${m.color || '#38bdf8'}">${esc(m.label)}</text>`;
    });
    let fc = '';
    if (forecastMm > 0) { const x = X(Math.min(300, forecastMm)); fc = `<line x1="${x}" x2="${x}" y1="${T}" y2="${Y(0)}" stroke="#f97316" stroke-width="2"/><text x="${x + 6}" y="${T + 12}" font-size="12" font-weight="700" fill="#f97316">heaviest forecast day · ${Math.round(forecastMm)} mm</text>`; }
    const ty = Y(thr);
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Flood depth versus rainfall">
      <defs><linearGradient id="dg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#38bdf8" stop-opacity=".55"/><stop offset="1" stop-color="#38bdf8" stop-opacity=".03"/></linearGradient></defs>
      ${yt}<line x1="${L}" x2="${W - R}" y1="${ty}" y2="${ty}" stroke="#eab308" stroke-dasharray="6 5" opacity=".85"/>
      <text x="${W - R}" y="${ty - 6}" text-anchor="end" font-size="12" fill="#eab308">counts as flooded</text>
      <path d="${area}" fill="url(#dg)"/><path d="${path}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linejoin="round"/>
      ${fc}${mk}${xt}
      <text x="${L + pw / 2}" y="${H}" text-anchor="middle" font-size="12" fill="#8a9ab5" opacity="0">rain</text>
      <text x="14" y="${T + ph / 2}" font-size="12" fill="#8a9ab5" transform="rotate(-90 14 ${T + ph / 2})" text-anchor="middle">water depth (m)</text>
    </svg>`;
  }

  // Price band: portal range (low-high), typical band, optional asking marker. fmt formats a number.
  function band(low, high, typ, ask, fmt) {
    const W = 460, H = 150, L = 34, R = 34, pw = W - L - R;
    const lo = Math.min(low, ask || low) * .9, hi = Math.max(high, ask || high) * 1.06, X = v => L + (v - lo) / (hi - lo) * pw;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Price band">
      <rect x="${X(low)}" y="64" width="${X(high) - X(low)}" height="22" rx="11" fill="#2a3b5c"/>
      ${typ ? `<rect x="${X(typ[0])}" y="64" width="${Math.max(8, X(typ[1]) - X(typ[0]))}" height="22" rx="11" fill="#38bdf8"/>` : ''}
      <text x="${X(low)}" y="112" font-size="14" fill="#a9b7cf" text-anchor="middle">${esc(fmt(low))}</text>
      <text x="${X(high)}" y="112" font-size="14" fill="#a9b7cf" text-anchor="middle">${esc(fmt(high))}</text>`;
    if (typ) s += `<text x="${(X(typ[0]) + X(typ[1])) / 2}" y="138" font-size="13.5" font-weight="700" fill="#38bdf8" text-anchor="middle">typical asking</text>`;
    if (ask) {
      const x = Math.max(60, Math.min(W - 60, X(ask))), inside = ask >= low && ask <= high, col = inside ? '#22c55e' : '#f97316';
      s += `<path d="M${X(ask)},60 l-9,-15 h18 z" fill="${col}"/><text x="${x}" y="30" font-size="16" font-weight="800" fill="${col}" text-anchor="middle">ask ${esc(fmt(ask))}</text>`;
    }
    return s + '</svg>';
  }

  // Rain timeline around a claim date
  function rainBars(days, hit) {
    const W = 520, H = 190, L = 30, B = 40, T = 24, n = days.length, bw = Math.min(80, (W - L) / n - 18), mx = Math.max(20, ...days.map(d => d.mm)) * 1.15;
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Rainfall around the claim date">`;
    days.forEach((d, i) => {
      const x = L + (i + .5) * ((W - L) / n) - bw / 2, h = d.mm / mx * (H - T - B), y = H - B - h, on = d.date === hit;
      s += `<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(2, h)}" rx="6" fill="${on ? '#38bdf8' : '#2f4670'}"/>
        <text x="${x + bw / 2}" y="${y - 7}" text-anchor="middle" font-size="14" font-weight="700" fill="#eef3fb">${f1(d.mm)}</text>
        <text x="${x + bw / 2}" y="${H - 18}" text-anchor="middle" font-size="12.5" fill="${on ? '#38bdf8' : '#8a9ab5'}" font-weight="${on ? 700 : 500}">${esc(d.date.slice(5))}${on ? ' (claim)' : ''}</text>`;
    });
    return s + `<text x="4" y="14" font-size="12" fill="#8a9ab5">mm / day</text></svg>`;
  }

  return { gauge, scoreDial, depthCurve, band, rainBars, TIER_COL };
})();
