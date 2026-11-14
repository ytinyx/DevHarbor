/* Rebuild native SVG, PNG and the self-contained offline viewer from Mermaid. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');
const { buildViewer } = require('./viewer.cjs');
const { renderDirectory } = require('./directory.cjs');
const root = path.resolve(__dirname, '../../..');
const out = path.join(root, 'docs/diagrams');
const sourceDir = path.join(out, 'source');
const all = JSON.parse(fs.readFileSync(path.join(sourceDir, 'atlas.json'), 'utf8'));
const selected = process.argv.slice(2);
const esc = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const hash = s => crypto.createHash('sha256').update(s).digest('hex');
let browser;
(async () => {
  for (const id of selected) if (!all.some(x => x.id === id)) throw Error('Unknown diagram: ' + id);
  const candidate = [process.env.BROWSER_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].filter(Boolean).find(p => fs.existsSync(p));
  browser = await chromium.launch({ headless: true, ...(candidate ? { executablePath: candidate } : {}), chromiumSandbox: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.setContent('<!doctype html><html><meta charset="utf-8"><body></body></html>');
  await page.addScriptTag({ path: require.resolve('mermaid/dist/mermaid.min.js') });
  await page.evaluate(() => mermaid.initialize({
    startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false,
    fontFamily: 'Microsoft YaHei,Segoe UI,sans-serif', maxTextSize: 150000,
    themeVariables: { fontSize: '18px', primaryColor: '#eef6f8', primaryTextColor: '#183248', primaryBorderColor: '#80a6b8', lineColor: '#52758b', secondaryColor: '#edf7f1', tertiaryColor: '#fff4df', edgeLabelBackground: '#ffffff', clusterBkg: '#f6f9fc', clusterBorder: '#aec7d6', actorBkg: '#eef6f8', actorTextColor: '#183248', actorBorder: '#80a6b8', signalColor: '#52758b', signalTextColor: '#183248', noteBkgColor: '#fff4df', noteTextColor: '#183248' },
    flowchart: { htmlLabels: false, useMaxWidth: false, curve: 'linear', nodeSpacing: 45, rankSpacing: 65, padding: 18, wrappingWidth: 320 },
    sequence: { useMaxWidth: false, actorMargin: 55, width: 170, height: 70, messageMargin: 48, noteMargin: 20, wrap: true, wrapPadding: 15, diagramMarginX: 35, diagramMarginY: 25 },
    er: { useMaxWidth: false, fontSize: 18, entityPadding: 18, minEntityWidth: 150, diagramPadding: 35, layoutDirection: 'TB' },
    state: { useMaxWidth: false }
  }));
  const raster = await browser.newPage();
  const old = fs.existsSync(path.join(out, 'manifest.json')) ? JSON.parse(fs.readFileSync(path.join(out, 'manifest.json'), 'utf8')) : [];
  const results = new Map(old.map(x => [x.id, x]));
  fs.mkdirSync(path.join(out, 'svg'), { recursive: true });
  fs.mkdirSync(path.join(out, 'png'), { recursive: true });
  for (const item of all) {
    if (selected.length && !selected.includes(item.id)) continue;
    const source = fs.readFileSync(path.join(sourceDir, item.id + '.mmd'), 'utf8');
    const directory = item.id === '00_project_directory';
    const rendered = await page.evaluate(async ({ id, source, directory }) => {
      if (directory) {
        const { db } = await mermaid.mermaidAPI.getDiagramFromText(source);
        const vertices = Object.fromEntries(Object.entries(db.getVertices()).map(([id, node]) => [id, node.text]));
        return { vertices, edges: db.getEdges(), groups: db.getSubGraphs() };
      }
      await mermaid.parse(source);
      const { svg } = await mermaid.render('g_' + id, source);
      const host = document.createElement('div'); host.innerHTML = svg;
      const el = host.querySelector('svg');
      const vb = el.getAttribute('viewBox').split(/[ ,]+/).map(Number);
      el.setAttribute('width', String(vb[2])); el.setAttribute('height', String(vb[3])); el.removeAttribute('style');
      if (el.querySelector('foreignObject,script')) throw Error('Native SVG text required: ' + id);
      let labelMoves = 0;
      if (source.includes('erDiagram')) {
        document.body.append(host);
        const rootRect = el.getBoundingClientRect();
        const bounds = node => { const b = node.getBoundingClientRect(); return { x: b.x - rootRect.x + vb[0], y: b.y - rootRect.y + vb[1], w: b.width, h: b.height }; };
        const overlaps = (a, b) => a.x < b.x + b.w + 7 && a.x + a.w + 7 > b.x && a.y < b.y + b.h + 7 && a.y + a.h + 7 > b.y;
        const occupied = [...el.querySelectorAll('rect.entityBox')].map(bounds);
        const labels = [...el.querySelectorAll('text.relationshipLabel')];
        const boxes = [...el.querySelectorAll('rect.relationshipLabelBox')];
        if (labels.length !== boxes.length) throw Error('ER label/box mismatch');
        labels.forEach((label, i) => {
          const box = boxes[i], initial = bounds(box);
          const offsets = [[0, 0]];
          for (let ring = 1; ring <= 24; ring++) {
            offsets.push([0, ring * 34], [0, -ring * 34], [ring * 70, 0], [-ring * 70, 0]);
            for (const sx of [-1, 1]) for (const sy of [-1, 1]) offsets.push([sx * ring * 70, sy * ring * 34]);
          }
          const position = offsets.map(([dx, dy]) => ({ x: initial.x + dx, y: initial.y + dy, w: initial.w, h: initial.h, dx, dy })).find(b => b.x >= vb[0] + 5 && b.y >= vb[1] + 5 && b.x + b.w <= vb[0] + vb[2] - 5 && b.y + b.h <= vb[1] + vb[3] - 5 && !occupied.some(other => overlaps(b, other)));
          if (!position) throw Error('No clear position for ER label: ' + label.textContent);
          occupied.push(position);
          if (position.dx || position.dy) {
            labelMoves++;
            for (const node of [label, box]) {
              node.setAttribute('x', String(Number(node.getAttribute('x')) + position.dx));
              node.setAttribute('y', String(Number(node.getAttribute('y')) + position.dy));
            }
            const leader = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            for (const [key, value] of Object.entries({ x1: initial.x + initial.w / 2, y1: initial.y + initial.h / 2, x2: position.x + position.w / 2, y2: position.y + position.h / 2, stroke: '#8a9fac', 'stroke-width': '1', 'stroke-dasharray': '3 3', class: 'label-leader' })) leader.setAttribute(key, String(value));
            box.before(leader);
          }
        });
        const expected = [...source.matchAll(/^\s*([A-Za-z][A-Za-z0-9_]*)\s*\{/gm)].length;
        if (el.querySelectorAll('rect.entityBox').length !== expected) throw Error('ER entity count mismatch: ' + id);
        host.remove();
      }
      return { svg: new XMLSerializer().serializeToString(el), width: vb[2], height: vb[3], labelMoves, textCount: el.querySelectorAll('text').length, nodes: el.querySelectorAll('g.node,rect.entityBox,g.actor').length, edges: el.querySelectorAll('.flowchart-link,.relationshipLine,.messageLine0,.messageLine1,.transition').length };
    }, { id: item.id, directory, source: item.erDirection ? '%%{init: ' + JSON.stringify({ er: { layoutDirection: item.erDirection } }) + '}%%\n' + source : source });
    const output = directory ? renderDirectory(item, rendered) : frameDiagram(item, rendered);
    const { width, height, svg, nodes, edges, labelMoves } = output;
    const svgPath = path.join(out, 'svg', item.id + '.svg');
    fs.writeFileSync(svgPath, svg);
    const scale = Math.min(1.5, 10000 / Math.max(width, height));
    const pixels = [Math.ceil(width * scale), Math.ceil(height * scale)];
    await raster.setViewportSize({ width: pixels[0], height: pixels[1] });
    await raster.goto(pathToFileURL(svgPath).href);
    await raster.evaluate(({ w, h }) => { document.documentElement.style.width = w + 'px'; document.documentElement.style.height = h + 'px'; }, { w: pixels[0], h: pixels[1] });
    await raster.evaluate(() => document.fonts.ready);
    const checked = await raster.evaluate(() => ({ root: document.documentElement.localName, errors: document.querySelectorAll('parsererror').length, text: document.querySelectorAll('text').length }));
    if (checked.root !== 'svg' || checked.errors || checked.text < 5) throw Error('Invalid SVG: ' + item.id);
    await raster.screenshot({ path: path.join(out, 'png', item.id + '.png'), timeout: 60000 });
    results.set(item.id, { ...item, source: 'source/' + item.id + '.mmd', svg: 'svg/' + item.id + '.svg', png: 'png/' + item.id + '.png', width, height, pixels, source_sha256: hash(source), svg_sha256: hash(svg), textCount: checked.text, nodes, edges, labelMoves, status: 'implementation_map' });
    console.log('Rendered', item.id, `${width}x${height}`, `texts=${checked.text}`);
  }
  const manifest = all.map(x => results.get(x.id)).filter(Boolean);
  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  if (manifest.length !== all.length) throw Error('Render all diagrams before publishing the viewer.');
  buildViewer(out, manifest);
  console.log(`Built ${manifest.length} diagrams and offline viewer.`);
})().catch(e => { console.error(e); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); });

function frameDiagram(item, rendered) {
  const width = Math.ceil(Math.max(1400, rendered.width + 100));
  const height = Math.ceil(rendered.height + 220);
  const nested = rendered.svg.replace('<svg ', `<svg x="${(width - rendered.width) / 2}" y="155" `);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"><title>${esc(item.title)}</title><desc>${esc(item.subtitle)}</desc><rect width="${width}" height="${height}" fill="#fff"/><rect width="${width}" height="128" fill="#edf5f8"/><g font-family="Microsoft YaHei,Segoe UI,sans-serif"><text x="48" y="36" font-size="17" fill="#087f8c">DEVHARBOR / SOURCE MAP / ${esc(item.number)}</text><text x="48" y="78" font-size="30" font-weight="700" fill="#17334c">${esc(item.title)}</text><text x="48" y="111" font-size="17" fill="#5c7185">${esc(item.subtitle)}</text></g>${nested}<text x="48" y="${height - 20}" font-family="Microsoft YaHei,Segoe UI,sans-serif" font-size="16" fill="#5c7185">依据当前代码绘制；可选服务与真实质量仍需独立验证。源文件：source/${item.id}.mmd</text></svg>\n`;
  return { ...rendered, svg, width, height };
}
