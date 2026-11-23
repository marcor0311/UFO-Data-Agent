const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { cargarPropuesta, renderizar, html } = require("./reproducir.cjs");

const biblioteca = path.resolve(__dirname, "..");
const origen = path.resolve(process.argv[2] || path.join(biblioteca, "../DB Test"));
const original = vm.createContext({
  UAPSketchbookData: JSON.parse(fs.readFileSync(path.join(origen, "assets/analitica/sketchbook-v2.json"), "utf8")),
});
original.window = original;
for (const name of ["analitica-uap.js", "sketchbook-integrado.js"]) {
  vm.runInContext(fs.readFileSync(path.join(origen, name), "utf8"), original, { filename: name });
}

function grupos(render) {
  return JSON.stringify([...render.groups].map(([key, group]) => [key, group.rows.map((report) => report.id)]));
}

let montajes = 0;
let renderizadores = 0;
for (const carpeta of fs.readdirSync(biblioteca)) {
  if (!fs.existsSync(path.join(biblioteca, carpeta, "propuesta.json"))) continue;
  const actual = cargarPropuesta(carpeta, origen);
  assert.match(html(actual), /^<!doctype html>/, carpeta);
  montajes++;
  if (actual.config.engine !== "sketchbook") continue;
  const recuperado = renderizar(actual);
  const referencia = original.UAPAnalytics.render(actual.config.id, actual.registros, { cohortKey: null });
  assert.equal(JSON.stringify(recuperado.svgs), JSON.stringify(referencia.svgs), carpeta + " SVG");
  assert.equal(grupos(recuperado), grupos(referencia), carpeta + " grupos e IDs");
  if (actual.esMapaClusters) {
    assert.equal(recuperado.model.groups.length, referencia.model.groups.length, carpeta + " DBSCAN");
    assert.equal(recuperado.model.noise.length, referencia.model.noise.length, carpeta + " ruido");
  }
  renderizadores++;
}
assert.equal(montajes, 17);
assert.equal(renderizadores, 14);
console.log(`${montajes} montajes generados; ${renderizadores} renderizadores cotejados con DB Test.`);
