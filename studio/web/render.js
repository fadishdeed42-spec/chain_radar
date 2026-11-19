// node studio/web/render.js <page.html> <timing.json> <out.mp4|--check> [--from s --to s] [--stills t1,t2..]
const { chromium } = require('playwright'); const fs = require('fs'); const { spawn } = require('child_process');
const [page_, timing, out] = process.argv.slice(2);
const arg = k => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };
const FPS = 30;
(async () => {
  const T = JSON.parse(fs.readFileSync(timing));
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.addInitScript(t => { window.TIMING = t; }, T);
  await p.goto('file://' + require('path').resolve(page_)); await p.waitForTimeout(300);
  const miss = await p.evaluate(() => { render(0); return MISSING; });
  if (miss.length) console.log('MISSING WORDS', [...new Set(miss)].join(' '));
  if (out === '--check') {
    const seen = new Map();
    for (let f = 0; f < T.dur * FPS; f += 2) {
      const t = f / FPS; const r = await p.evaluate(t => { render(t); return (window.SKIP || []).some(([a, b]) => t >= a && t <= b) ? [] : checkFrame(t); }, t);
      for (const x of r) { const k = x.slice(0, 3).join('|'); if (!seen.has(k)) seen.set(k, [t.toFixed(2), ...x]); }
    }
    console.log('CHECK', seen.size ? seen.size + ' problems' : 'OK'); for (const v of seen.values()) console.log(' ', JSON.stringify(v));
    await b.close(); return;
  }
  const st = arg('--stills');
  if (st) { for (const s of st.split(',')) { await p.evaluate(t => render(t), +s); await p.screenshot({ path: out.replace('.png', '') + '_' + s + '.png' }); } await b.close(); return; }
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.ceil(T.dur * FPS);
  for (let f = 0; f < n; f++) {
    await p.evaluate(t => render(t), f / FPS);
    const buf = await p.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 150 === 0) console.log('frame', f, '/', n);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close(); console.log('done', out);
})();
