const fs = require('node:fs');
const path = require('node:path');

function readDiagramSource(sourcePath) {
  // Match the LF checkout convention in .gitattributes on every operating system.
  return fs.readFileSync(sourcePath, 'utf8').replaceAll('\r\n', '\n');
}

function buildViewer(out, manifest) {
  const data = manifest.map(item => ({ ...item, markup: fs.readFileSync(path.join(out, item.svg), 'utf8'), code: readDiagramSource(path.join(out, item.source)) }));
  const template = fs.readFileSync(path.join(__dirname, 'viewer.html'), 'utf8');
  const json = JSON.stringify(data).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029');
  fs.writeFileSync(path.join(out, '00_打开图表.html'), template.replace('__DIAGRAM_DATA__', json));
}
module.exports = { buildViewer, readDiagramSource };
