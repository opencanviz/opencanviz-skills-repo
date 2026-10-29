#!/usr/bin/env node
/**
 * Preview a launch reel built by build.py, locally, with the same player openCanviz uses.
 *
 *   node preview.mjs reel.json                       # reel.sheet.png: one frame per scene
 *   node preview.mjs reel.json --at 12.5             # reel.12.5s.png: one frame
 *   node preview.mjs reel.json --mp4 --audio reel.wav   # reel.mp4 (needs ffmpeg)
 *
 * Options: --out <file>, --height <px> (720), --fps <n> (30), --cols <n> (4).
 *
 * The sheet shows each scene just before it cuts away, when everything in it has landed, so
 * one image answers "does every scene read". Setup once: `npm run setup` in this folder.
 * Runs headless Chromium against a page served from localhost; the only network request is
 * the player's own icon lookup, and build.py inlines every icon, so a reel makes none.
 */
import { spawn } from 'node:child_process';
import * as fs from 'node:fs';
import * as http from 'node:http';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
const arg = (name, def) => { const i = argv.indexOf(`--${name}`); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : def; };
const flag = (name) => argv.includes(`--${name}`);
const input = argv.find((a, i) => !a.startsWith('--') && !(i > 0 && argv[i - 1].startsWith('--') && !['mp4'].includes(argv[i - 1].slice(2))));
if (!input) { console.error('usage: node preview.mjs reel.json [--mp4] [--audio reel.wav] [--at sec] [--out file]'); process.exit(1); }

let chromium;
let playerDir;
try {
  ({ chromium } = await import('playwright'));
  playerDir = path.join(path.dirname(fileURLToPath(import.meta.resolve('@opencanviz/player'))), '..');
} catch {
  console.error('missing dependencies: run `npm run setup` in ' + path.dirname(fileURLToPath(import.meta.url)));
  process.exit(1);
}

const height = +arg('height', 720);
const fps = +arg('fps', 30);
const cols = +arg('cols', 4);
const at = arg('at', null);
const mp4 = flag('mp4');
const audio = arg('audio', null);
const base = input.replace(/\.json$/, '');
const out = arg('out', mp4 ? `${base}.mp4` : at != null ? `${base}.${at}s.png` : `${base}.sheet.png`);
const project = JSON.parse(fs.readFileSync(input, 'utf8'));

// Serve the player's dist folder (bundle, fonts) plus a blank page on a random local port.
const dist = path.join(playerDir, 'dist');
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/assets/player.css"></head>
<body style="margin:0;background:#000"><canvas id="c"></canvas><canvas id="sheet"></canvas>
<script type="module">
import * as P from '/canviz-player.js';
P.configureAssets({ base: '/assets/' });
window.P = P; window.ready = true;
</script></body></html>`;
const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.png': 'image/png', '.html': 'text/html' };
const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  if (url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); return res.end(PAGE); }
  const file = path.join(dist, path.normalize(url).replace(/^(\.\.[/\\])+/, ''));
  if (!file.startsWith(dist) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ headless: true });
const done = async (code = 0) => { await browser.close(); server.close(); process.exit(code); };
try {
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.error('  [page]', e.message));
  await page.goto(origin + '/');
  await page.waitForFunction('window.ready === true', null, { timeout: 15000 });
  const meta = await page.evaluate(async ({ doc, h }) => {
    for (const f of ['Inter Brand', 'Playfair Display', 'Space Grotesk', 'Caveat', 'Comic Neue'])
      for (const w of [400, 500, 600, 700, 800]) { try { await document.fonts.load(`${w} 40px "${f}"`); } catch {} }
    const r = await window.P.createPlayer(document.getElementById('c'), doc, { targetHeight: h });
    await r.imagesReady;
    window.r = r;
    return { w: r.pxW, h: r.pxH, ms: r.totalDurationMs, failures: (r.mediaFailures || []).length };
  }, { doc: project, h: height });
  if (meta.failures) console.error(`  ${meta.failures} picture(s) failed to load`);

  if (mp4) {
    const total = Math.ceil((meta.ms / 1000) * fps);
    const args = ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${meta.w}x${meta.h}`,
      '-framerate', String(fps), '-i', '-'];
    if (audio) args.push('-i', audio, '-map', '0:v', '-map', '1:a', '-af', 'loudnorm=I=-16:TP=-1.5', '-c:a', 'aac', '-b:a', '160k', '-shortest');
    args.push('-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-movflags', '+faststart', out);
    const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });
    ff.on('error', () => { console.error('ffmpeg not found on PATH'); done(1); });
    const exited = new Promise((r) => ff.on('close', r));
    for (let i = 0; i < total; i++) {
      const b64 = await page.evaluate(async (t) => {
        await window.r.prepareFrameAt?.(t);
        window.r.renderFrameAt(t);
        const c = document.getElementById('c');
        const px = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let s = ''; const CH = 0x8000;
        for (let k = 0; k < px.length; k += CH) s += String.fromCharCode.apply(null, px.subarray(k, k + CH));
        return btoa(s);
      }, (i * 1000) / fps);
      if (!ff.stdin.write(Buffer.from(b64, 'base64'))) await new Promise((r) => ff.stdin.once('drain', r));
      if (i % (fps * 5) === 0) process.stderr.write(`\r  ${(i / fps).toFixed(0)}s / ${(meta.ms / 1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    const code = await exited;
    process.stderr.write('\n');
    if (code !== 0) { console.error('ffmpeg failed'); await done(1); }
  } else {
    // One frame per scene, taken just before the next scene starts. Scene starts come from the
    // builder's cue track; a project without one is sampled evenly.
    const starts = (project.meta?.audio?.transitions || []).map((x) => x.t);
    const labels = (project.meta?.spec?.scenes || []).map((s, i) => `${i + 1} ${s.type}`);
    let times;
    if (at != null) times = [+at * 1000];
    else if (starts.length) times = starts.map((t, i) => Math.max(t, (starts[i + 1] ?? meta.ms) - 350));
    else times = Array.from({ length: 12 }, (_, i) => ((i + 0.8) / 12) * meta.ms);
    const png = await page.evaluate(async ({ times, labels, cols, single }) => {
      const c = document.getElementById('c');
      const s = document.getElementById('sheet');
      const scale = single ? 1 : 0.5;
      const tw = Math.round(c.width * scale), th = Math.round(c.height * scale);
      const n = times.length, cc = single ? 1 : Math.min(cols, n), rows = Math.ceil(n / cc);
      const pad = single ? 0 : 8, lab = single ? 0 : 26;
      s.width = cc * tw + (cc + 1) * pad; s.height = rows * (th + lab) + (rows + 1) * pad;
      const g = s.getContext('2d');
      g.fillStyle = '#1b1b1f'; g.fillRect(0, 0, s.width, s.height);
      for (let i = 0; i < n; i++) {
        await window.r.prepareFrameAt?.(times[i]);
        window.r.renderFrameAt(times[i]);
        const x = pad + (i % cc) * (tw + pad), y = pad + Math.floor(i / cc) * (th + lab + pad);
        g.drawImage(c, x, y + lab, tw, th);
        if (!single) {
          g.fillStyle = '#e8e8ec'; g.font = '600 15px "Inter Brand", sans-serif';
          g.fillText(`${labels[i] || i + 1}  ·  ${(times[i] / 1000).toFixed(1)}s`, x + 2, y + 18);
        }
      }
      return s.toDataURL('image/png').split(',')[1];
    }, { times, labels, cols, single: at != null });
    fs.writeFileSync(out, Buffer.from(png, 'base64'));
  }
  console.log(`${out}  (${meta.w}x${meta.h}, ${(meta.ms / 1000).toFixed(1)}s)`);
  await done(0);
} catch (e) {
  console.error(e.message || e);
  await done(1);
}
