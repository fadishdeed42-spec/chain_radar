// Shared runtime for the 2D "film" styles (owner Nov 19): pages draw ONLY the picture in the safe middle
// (y 430..1440 of 1080x1920); the engine adds the headline on top and the spoken-word captions below.
const TM = window.TIMING;                       // {para:[[s,e]..], dur, words:[[scene, word, t]..]}
const DUR = TM.dur, PARA = TM.para;
const MISSING = [];
function S(i) { return PARA[i][0]; }
function E(i) { return PARA[i][1]; }
function W(i, w, k = 0) {
  const h = TM.words.filter(x => x[0] === i && x[1] === w).map(x => x[2]);
  if (h.length <= k) { MISSING.push(i + ':' + w); return S(i) + .3; }
  return h[k];
}
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const prog = (t, a, b) => clamp((t - a) / Math.max(1e-6, b - a));
const eOut = x => 1 - Math.pow(1 - x, 3);
const eInOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const eBack = x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const lerp = (a, b, x) => a + (b - a) * x;
function $(html) { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }
// visible between tin and tout with a pop (scale + fade); returns 0..1 presence
function pop(el, t, tin, tout = 1e9, d = .22, base = '') {
  const a = eBack(prog(t, tin, tin + d)), b = 1 - prog(t, tout - d * .8, tout);
  const v = Math.min(a, b);
  el.style.opacity = clamp(Math.min(prog(t, tin, tin + d * .6), b));
  el.style.transform = base + ` scale(${lerp(.6, 1, clamp(v, 0, 1.2))})`;
  el.style.visibility = (t < tin || t > tout) ? 'hidden' : 'visible';
  return v;
}
// camera: keyframes [[t, x, y, zoom]] on a stage div (smooth, never fully still: adds a slow drift)
function camera(stage, t, keys, drift = 6) {
  let k = keys[0];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, ...a] = keys[i], [t1, ...b] = keys[i + 1];
    if (t >= t0 && t <= t1) { const x = eInOut(prog(t, t0, t1)); k = [t, ...a.map((v, j) => lerp(v, b[j], x))]; break; }
    if (t > t1) k = keys[i + 1];
  }
  const [, x, y, z] = k;
  const dx = drift * Math.sin(t * .7), dy = drift * Math.sin(t * .53 + 1), dz = 1 + .012 * Math.sin(t * .4);
  stage.style.transform = `translate(540px,935px) scale(${z * dz}) translate(${-x + dx}px,${-y + dy}px)`;
}
function shake(t, hits, amp = 14) {
  let s = 0; for (const h of hits) if (t >= h && t < h + .4) s = Math.max(s, amp * (1 - (t - h) / .4));
  return `translate(${s * Math.sin(t * 90)}px,${s * Math.cos(t * 77)}px)`;
}
function count(t, a, b, v0, v1, fmt) { return fmt(lerp(v0, v1, eOut(prog(t, a, b)))); }
const usd = v => '$' + Math.round(v).toLocaleString('en-US');
// overlap/edge checker used by render.js --check: every element with class .chk must stay inside the safe area
// and never overlap another visible .chk element
function checkFrame(t) {
  const out = [], els = [...document.querySelectorAll('.chk')].filter(e => {
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || +cs.opacity < .5) return false;
    let p = e.parentElement; while (p) { const c = getComputedStyle(p); if (c.visibility === 'hidden' || +c.opacity < .5) return false; p = p.parentElement; }
    return true;
  });
  const R = els.map(e => [e, e.getBoundingClientRect()]).filter(([e, r]) => r.right > 0 && r.left < 1080 && r.bottom > 0 && r.top < 1920);
  for (const [e, r] of R) {
    if (r.left < 40 || r.right > 1040 || r.top < 425 || r.bottom > 1445) out.push(['EDGE', e.dataset.n || e.className, Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]);
  }
  for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++) {
    const [a, ra] = R[i], [b, rb] = R[j];
    if (a.contains(b) || b.contains(a)) continue;
    const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (ox > 6 && oy > 6) out.push(['OVERLAP', a.dataset.n || a.className, b.dataset.n || b.className]);
  }
  return out;
}
