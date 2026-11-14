/* Render the Mermaid directory tree as indented, searchable SVG rows. */
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

function renderDirectory(item, { vertices, edges, groups }) {
  const width = 1600;
  const junction = 146;
  const boxes = new Map();
  const incoming = new Map(edges.map(({ start, end }) => [end, start]));
  const panels = [];
  const text = (value, x, y, size, fill, weight = 400) =>
    `<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${escape(value)}</text>`;
  const rect = (x, y, w, h, fill, radius = 0, stroke = 'none') =>
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${radius}" fill="${fill}" stroke="${stroke}"/>`;
  const line = (d, runtime = false) =>
    `<path class="flowchart-link" d="${d}" fill="none" stroke="${runtime ? '#ab792f' : '#8fa9ba'}" stroke-width="1.4"${runtime ? ' stroke-dasharray="6 5"' : ''}/>`;

  function addBox(id, x, y, w, panel, depth = 0) {
    const [title, ...description] = vertices[id].split(/<br\s*\/?\s*>/);
    const box = { x, y, w, h: 32 + 18 * description.length, panel, depth, title, description };
    boxes.set(id, box);
    return box;
  }

  function addPanel(id, x, y, w) {
    const group = groups.find(group => group.id === id);
    const panel = { x, y, w, h: 0, title: group.title, runtime: id === 'LOCAL' };
    panels.push(panel);
    let rowY = y + 45;
    for (const nodeId of group.nodes) {
      const parent = boxes.get(incoming.get(nodeId));
      const depth = parent?.panel === panel ? parent.depth + 1 : 0;
      const inset = 18 + depth * 19;
      const row = addBox(nodeId, x + inset, rowY, w - inset - 14, panel, depth);
      rowY += row.h + 6;
    }
    panel.h = rowY - y + 8;
    return panel;
  }

  const root = addBox('ROOT', 26, 76, 930, null);
  const rootFiles = addBox('ROOT_FILES', 974, 76, 600, null);
  addPanel('BACKEND', 26, 160, 636);
  addPanel('FRONTEND', 680, 160, 430);
  const docs = addPanel('DOCS', 1128, 160, 446);
  addPanel('LOCAL', 1128, docs.y + docs.h + 16, 446);

  const height = Math.max(...panels.map(panel => panel.y + panel.h)) + 52;
  const body = [
    rect(0, 0, width, height, '#f2f6fa'),
    text(item.title, 26, 37, 27, '#193044', 700),
    text(item.subtitle, 26, 60, 15, '#536b7c'),
    ...panels.flatMap(panel => [
      rect(panel.x, panel.y, panel.w, panel.h, panel.runtime ? '#fff4df' : '#e5edf4', 12),
      text(panel.title, panel.x + 18, panel.y + 28, 18, '#193044', 700),
    ]),
    line(`M ${root.x + root.w} ${root.y + root.h / 2} H ${rootFiles.x}`),
    line(`M ${root.x + root.w / 2} ${root.y + root.h} V ${junction} M 34 ${junction} H 1136`),
  ];
  for (const { start, end } of edges) {
    if (end === 'ROOT_FILES') continue;
    const parent = boxes.get(start);
    const child = boxes.get(end);
    const mid = child.y + child.h / 2;
    if (child.panel.runtime) {
      body.push(line(`M 1136 ${junction} H 1586 V ${mid} H ${child.x + child.w}`, true));
    } else if (parent === root) {
      body.push(line(`M ${child.x - 10} ${junction} V ${mid} H ${child.x}`));
    } else {
      body.push(line(`M ${child.x - 9} ${parent.y + parent.h} V ${mid} H ${child.x}`));
    }
  }

  for (const [id, box] of boxes) {
    const { x, y, w, h, title, description, panel } = box;
    const runtime = panel?.runtime;
    const ink = runtime ? '#8c5b18' : '#126d61';
    const fill = id === 'ROUTES' ? '#d8f1e8' : runtime ? '#fffdf8' : '#f3fbf7';
    body.push(
      `<g class="node" id="directory-${escape(id)}"><title>${escape([title, ...description].join(' · '))}</title>`,
      rect(x, y, w, h, fill, 5, runtime ? '#e3d1a8' : '#bad9cf'),
      rect(x, y + 6, id === 'ROUTES' ? 4 : 3, h - 12, ink, 1),
      text(title, x + 12, y + 19, 16, ink, 700),
      ...description.map((value, index) => text(value, x + 12, y + 38 + 18 * index, 14, '#465f71')),
      '</g>',
    );
  }
  body.push(text('目录与文件为当前仓库的主要入口。虚线标出运行时数据。', 26, height - 22, 14, '#536b7c'));
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="Microsoft YaHei,Segoe UI,sans-serif" role="img"><title>${escape(item.title)}</title><desc>${escape(item.subtitle)}</desc>${body.join('')}</svg>\n`;
  return { svg, width, height, nodes: boxes.size, edges: edges.length, labelMoves: 0 };
}

module.exports = { renderDirectory };
