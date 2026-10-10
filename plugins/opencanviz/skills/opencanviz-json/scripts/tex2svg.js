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

function one(item) {
  const tex = String(item.tex == null ? '' : item.tex);
  const color = item.color || '#f8fafc';
  try {
    let svg = adaptor.innerHTML(doc.convert(tex, { display: item.display !== false }));
    if (!svg.includes('<svg') || svg.includes('data-mjx-error')) return { ok: false, error: 'TeX error in ' + tex };
    svg = svg.replace(/currentColor/g, color);
    const num = (name) => { const m = svg.match(new RegExp(name + '="([\\d.]+)ex"')); return m ? parseFloat(m[1]) : 0; };
    const widthEx = num('width'), heightEx = num('height');
    const va = svg.match(/vertical-align:\s*(-?[\d.]+)ex/);
    const depthEx = va ? Math.abs(parseFloat(va[1])) : 0;
    svg = svg.replace(/width="[\d.]+ex"/, 'width="' + (widthEx * PX).toFixed(1) + '"')
             .replace(/height="[\d.]+ex"/, 'height="' + (heightEx * PX).toFixed(1) + '"');
    if (!svg.includes('xmlns=')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    return { ok: true, svg, widthEx, heightEx, depthEx };
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
