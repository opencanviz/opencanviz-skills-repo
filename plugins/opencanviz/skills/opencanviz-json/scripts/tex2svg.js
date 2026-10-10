#!/usr/bin/env node
// LaTeX -> self-contained SVG with MathJax 3, for opencanviz.py's scene.math().
//
// stdin:  {"items": [{"tex": "x^2", "color": "#f8fafc", "display": true}]}
// stdout: {"results": [{"ok": true, "svg": "<svg ...>", "widthEx": 2.4, "heightEx": 2.1, "depthEx": 0.2}]}
//
// mathjax-full is looked up from: $MATHJAX_PATH (a node_modules dir or the package dir), the current
// directory, this script's directory, and the global npm root. Install it with `npm i mathjax-full`
// (or `npm i -g mathjax-full`). Exit code 3 means it was not found.
'use strict';
const path = require('path');
const { execSync } = require('child_process');

function findMathjax() {
  const roots = [];
  if (process.env.MATHJAX_PATH) roots.push(process.env.MATHJAX_PATH, path.dirname(process.env.MATHJAX_PATH));
  roots.push(process.cwd(), __dirname, path.join(__dirname, '..'));
  try { roots.push(execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()); } catch (e) { /* no npm */ }
  for (const r of roots) {
    try { return path.dirname(require.resolve('mathjax-full/package.json', { paths: [r] })); } catch (e) { /* next */ }
    try {
      const p = path.join(r, 'package.json');
      if (require(p).name === 'mathjax-full') return r;
    } catch (e) { /* next */ }
  }
  return null;
}

const root = findMathjax();
if (!root) {
  process.stderr.write('mathjax-full not found. Install it with: npm i mathjax-full (or set MATHJAX_PATH)\n');
  process.exit(3);
}
const { mathjax } = require(path.join(root, 'js/mathjax.js'));
const { TeX } = require(path.join(root, 'js/input/tex.js'));
const { SVG } = require(path.join(root, 'js/output/svg.js'));
const { liteAdaptor } = require(path.join(root, 'js/adaptors/liteAdaptor.js'));
const { RegisterHTMLHandler } = require(path.join(root, 'js/handlers/html.js'));
const { AllPackages } = require(path.join(root, 'js/input/tex/AllPackages.js'));

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const doc = mathjax.document('', {
  InputJax: new TeX({ packages: AllPackages }),
  OutputJax: new SVG({ fontCache: 'local' }),   // glyphs inside each SVG: no external refs
});

const PX = 8;   // px per ex in the written SVG; an <img> with ex units has no size on a canvas

// Boxes of the marked parts: \cssId{oc-NAME}{...} in the TeX (opencanviz.py writes these for
// \part{NAME}{...}). Each box is [x, y, w, h] as fractions of the SVG's width and height, measured
// from the glyph outlines under that group, so a highlighter can sit on one term of an equation.
function pathBox(d) {
  const toks = d.match(/[A-Za-z]|-?[\d.]+(?:e-?\d+)?/g) || [];
  let cmd = 'M', i = 0, x = 0, y = 0;
  const xs = [], ys = [];
  while (i < toks.length) {
    if (/[A-Za-z]/.test(toks[i])) { cmd = toks[i++]; if (cmd === 'Z' || cmd === 'z') continue; }
    const n = () => parseFloat(toks[i++]);
    if (cmd === 'H') { x = n(); } else if (cmd === 'V') { y = n(); } else { x = n(); y = n(); }
    if (Number.isNaN(x) || Number.isNaN(y)) break;
    xs.push(x); ys.push(y);
  }
  if (!xs.length) return null;
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

// MathJax writes glyph outlines in absolute coordinates; relative ones are about a fifth shorter.
const ARGS = { M: 2, L: 2, T: 2, Q: 4, C: 6, S: 4, H: 1, V: 1, Z: 0 };
function relPath(d) {
  const toks = d.match(/[A-Za-z]|-?[\d.]+(?:e-?\d+)?/g) || [];
  let i = 0, cmd = null, x = 0, y = 0, sx = 0, sy = 0, out = '', last = '';
  const fmt = (v) => { const r = Math.round(v * 10) / 10; return (Object.is(r, -0) ? 0 : r).toString(); };
  const put = (c, nums) => {
    let txt = c === last && c !== 'm' ? '' : c;
    for (const n of nums) { const t = fmt(n); txt += (txt && !/[a-z]$/.test(txt) && t[0] !== '-') || (!txt && !/[a-z]$/.test(out) && t[0] !== '-') ? ' ' + t : t; }
    out += txt; last = c;
  };
  while (i < toks.length) {
    if (/[A-Za-z]/.test(toks[i])) cmd = toks[i++];
    if (!cmd || !(cmd in ARGS)) return d;   // lowercase or unknown: leave it alone
    if (cmd === 'Z') { out += 'z'; last = 'z'; x = sx; y = sy; continue; }
    const n = [];
    for (let k = 0; k < ARGS[cmd]; k++) n.push(parseFloat(toks[i++]));
    if (n.some(Number.isNaN)) return d;
    if (cmd === 'H') { put('h', [n[0] - x]); x = n[0]; }
    else if (cmd === 'V') { put('v', [n[0] - y]); y = n[0]; }
    else {
      const rel = n.map((v, k) => v - (k % 2 ? y : x));
      put(cmd.toLowerCase(), rel);
      x = n[n.length - 2]; y = n[n.length - 1];
      if (cmd === 'M') { sx = x; sy = y; cmd = 'L'; }
    }
  }
  return out;
}

function parseTransform(t) {
  let m = [1, 0, 0, 1, 0, 0];
  const mul = (a, b) => [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3],
    a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]];
  const re = /(translate|scale|matrix)\(([^)]*)\)/g;
  let r;
  while ((r = re.exec(t || ''))) {
    const v = r[2].split(/[\s,]+/).filter(Boolean).map(parseFloat);
    if (r[1] === 'translate') m = mul(m, [1, 0, 0, 1, v[0] || 0, v[1] || 0]);
    else if (r[1] === 'scale') m = mul(m, [v[0], 0, 0, v.length > 1 ? v[1] : v[0], 0, 0]);
    else m = mul(m, v);
  }
  return { m, mul };
}

function partBoxes(svgNode) {
  const A = adaptor;
  const kids = (n) => (A.childNodes(n) || []).filter((c) => A.kind(c) !== '#text' && A.kind(c) !== '#comment');
  const glyphs = {};
  const walkDefs = (n) => {
    if (A.kind(n) === 'path' && A.getAttribute(n, 'id')) glyphs[A.getAttribute(n, 'id')] = pathBox(A.getAttribute(n, 'd') || '');
    kids(n).forEach(walkDefs);
  };
  walkDefs(svgNode);
  const vb = (A.getAttribute(svgNode, 'viewBox') || '0 0 1 1').split(/\s+/).map(parseFloat);
  const out = {};
  const apply = (m, x, y) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
  const walk = (n, m, open) => {
    const k = A.kind(n);
    if (k === 'defs') return;
    const tf = parseTransform(A.getAttribute(n, 'transform'));
    const mm = tf.mul(m, tf.m);
    const id = A.getAttribute(n, 'id');
    let here = open;
    if (id && id.indexOf('oc-') === 0) here = open.concat([id.slice(3)]);
    let box = null;
    if (k === 'use') {
      const ref = (A.getAttribute(n, 'xlink:href') || A.getAttribute(n, 'href') || '').replace(/^#/, '');
      box = glyphs[ref] || null;
    } else if (k === 'rect') {
      const x = parseFloat(A.getAttribute(n, 'x') || 0), y = parseFloat(A.getAttribute(n, 'y') || 0);
      box = [x, y, x + parseFloat(A.getAttribute(n, 'width') || 0), y + parseFloat(A.getAttribute(n, 'height') || 0)];
    }
    if (box && here.length) {
      const pts = [apply(mm, box[0], box[1]), apply(mm, box[2], box[3]), apply(mm, box[0], box[3]), apply(mm, box[2], box[1])];
      for (const name of here) {
        const b = out[name] || [Infinity, Infinity, -Infinity, -Infinity];
        for (const [px, py] of pts) { b[0] = Math.min(b[0], px); b[1] = Math.min(b[1], py); b[2] = Math.max(b[2], px); b[3] = Math.max(b[3], py); }
        out[name] = b;
      }
    }
    kids(n).forEach((c) => walk(c, mm, here));
  };
  walk(svgNode, [1, 0, 0, 1, 0, 0], []);
  const res = {};
  for (const [name, b] of Object.entries(out)) {
    res[name] = [(b[0] - vb[0]) / vb[2], (b[1] - vb[1]) / vb[3], (b[2] - b[0]) / vb[2], (b[3] - b[1]) / vb[3]];
  }
  return res;
}

function one(item) {
  const tex = String(item.tex == null ? '' : item.tex);
  const color = item.color || '#f8fafc';
  try {
    const node = doc.convert(tex, { display: item.display !== false });
    const svgNode = (adaptor.childNodes(node) || []).find((c) => adaptor.kind(c) === 'svg');
    const parts = svgNode && tex.indexOf('oc-') >= 0 ? partBoxes(svgNode) : {};
    let svg = adaptor.innerHTML(node);
    if (!svg.includes('<svg') || svg.includes('data-mjx-error')) return { ok: false, error: 'TeX error in ' + tex };
    svg = svg.replace(/currentColor/g, color);
    const num = (name) => { const m = svg.match(new RegExp(name + '="([\\d.]+)ex"')); return m ? parseFloat(m[1]) : 0; };
    const widthEx = num('width'), heightEx = num('height');
    const va = svg.match(/vertical-align:\s*(-?[\d.]+)ex/);
    const depthEx = va ? Math.abs(parseFloat(va[1])) : 0;
    svg = svg.replace(/width="[\d.]+ex"/, 'width="' + (widthEx * PX).toFixed(1) + '"')
             .replace(/height="[\d.]+ex"/, 'height="' + (heightEx * PX).toFixed(1) + '"');
    if (!svg.includes('xmlns=')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    // keep the image small (a video's JSON import times out past ~150 KB): drop MathJax's bookkeeping
    // attributes and shorten the glyph ids; the drawing is unchanged
    svg = svg.replace(/ data-(?:mml-node|c|mjx-texclass|id-align|idbox|mjx-[a-z-]+)="[^"]*"/g, '')
             .replace(/ (?:role|focusable|aria-hidden)="[^"]*"/g, '')
             .replace(/ style="vertical-align:[^"]*"/g, '')
             .replace(/ id="oc-[^"]*"/g, '')
             .replace(/<text><\/text>/g, '')
             .replace(/MJX-\d+-TEX-/g, '')
             .replace(/ transform="translate\(0,0\)"/g, '')
             .replace(/ d="([^"]*)"/g, (m, d) => ' d="' + relPath(d) + '"');
    return { ok: true, svg, widthEx, heightEx, depthEx, parts };
  } catch (err) {
    return { ok: false, error: String((err && err.message) || err) };
  }
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  let payload;
  try { payload = JSON.parse(raw || '{}'); } catch (e) {
    process.stderr.write('bad JSON on stdin: ' + e.message + '\n');
    process.exit(2);
  }
  const items = Array.isArray(payload.items) ? payload.items : [];
  process.stdout.write(JSON.stringify({ results: items.map(one) }));
});
