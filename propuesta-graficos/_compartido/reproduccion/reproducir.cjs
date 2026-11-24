const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const biblioteca = path.resolve(__dirname, "../..");
/** A proposal lives in done/ or pendientes/; its reproduction files are in <slug>/reproduccion/. */
function carpetaDe(slug) {
  for (const estado of ["done", "pendientes"]) {
    const carpeta = path.join(biblioteca, estado, slug, "reproduccion");
    if (fs.existsSync(carpeta)) return carpeta;
  }
  return path.join(biblioteca, "pendientes", slug, "reproduccion");
}
const origenPredeterminado = path.resolve(biblioteca, "../DB Test");

const camposComparacion = [
  "date_event", "shape", "standardized_shape", "duration_seconds", "num_witnesses", "num_objects",
  "database_name", "source_ref", "movement_type", "has_description", "has_photo", "has_video",
];

function leer(ruta) {
  return fs.readFileSync(ruta, "utf8");
}

function leerDatos(origen, archivo) {
  const ruta = path.join(origen, archivo);
  if (!fs.existsSync(ruta)) throw new Error("Falta el recurso original " + ruta);
  return JSON.parse(leer(ruta));
}

function cargarPropuesta(slug, origen = origenPredeterminado) {
  if (!/^[a-z0-9-]+$/.test(slug)) throw new Error("Usa el nombre de una carpeta de la biblioteca.");
  const carpeta = carpetaDe(slug);
  const manifiesto = path.join(carpeta, "propuesta.json");
  if (!fs.existsSync(manifiesto)) throw new Error("La propuesta no tiene un renderizador recuperado.");
  const config = JSON.parse(leer(manifiesto));
  const core = leer(path.join(__dirname, "js/analitica-uap.js"));
  const entorno = vm.createContext({});
  entorno.window = entorno;
  vm.runInContext(core, entorno, { filename: "analitica-uap.js" });
  const A = entorno.UAPAnalytics;

  let registros = [];
  if (config.engine === "sketchbook") {
    const datos = leerDatos(origen, "assets/analitica/sketchbook-v2.json");
    const ids = new Set(datos.cohorts[config.cohort]);
    registros = datos.rows.filter(({ dbId, raw }) => {
      const year = A.dateInfo(raw.date_event)?.year;
      return ids.has(dbId) && year >= config.start && year <= config.end;
    }).map(({ dbId, raw, region }) => ({ id: dbId, recordId: dbId, raw, region }));
  } else if (config.engine === "map") {
    entorno.UAPAnalyticalData = leerDatos(origen, "assets/analitica/cohortes.json");
    const corte = A.decode(config.cohort);
    registros = corte.records.filter((raw) => {
      const year = A.dateInfo(raw.date_event)?.year;
      return year >= config.start && year <= config.end;
    });
  } else if (config.engine === "compare") {
    registros = leerDatos(origen, "muestra-uap.json").records.map((raw, i) => ({
      id: i + 1,
      recordId: raw.id,
      date: raw.date_event ?? "",
      city: raw.location_city ?? "Sin localidad",
      shape: raw.standardized_shape ?? "Sin clasificar",
      raw: Object.fromEntries(camposComparacion.map((key) => [key, raw[key]])),
    }));
  }

  const js = (...nombres) => nombres.map((nombre) => leer(path.join(__dirname, "js", nombre)));
  const css = (...nombres) => nombres.map((nombre) => leer(path.join(__dirname, "css", nombre)));
  const base = { carpeta, config, registros, entorno, A, core, js, css };
  if (config.engine !== "sketchbook") return base;
  const esMapaClusters = config.id === "M1" || config.id === "M1b";
  entorno.UAPSketchbookData = { cards: [config.card] };
  const visualizacion = [
    ...js("sketchbook-base.js"),
    ...(esMapaClusters ? js("mapa-clusters.js") : []),
    leer(path.join(carpeta, "visualizacion.js")),
  ];
  visualizacion.forEach((script) => vm.runInContext(script, entorno));
  return { ...base, visualizacion, esMapaClusters };
}

function renderizar(propuesta) {
  if (propuesta.config.engine !== "sketchbook") throw new Error("Esta vista se abre únicamente como HTML.");
  return propuesta.A.render(propuesta.config.id, propuesta.registros, { cohortKey: null });
}

function jsonIncrustado(valor) {
  return JSON.stringify(valor).replaceAll("<", "\\u003c");
}

function html(propuesta) {
  const { carpeta, config, registros, core, js, css, visualizacion, esMapaClusters } = propuesta;
  const map = esMapaClusters || config.engine === "map";
  const styles = [...css("reproduccion.css")];
  const scripts = ["window.recuperacion = " + jsonIncrustado({ config, registros }) + ";", core];
  let resources = "";
  if (config.engine === "sketchbook") {
    scripts.push("window.UAPSketchbookData = {cards: [window.recuperacion.config.card]};", ...visualizacion);
    styles.push(...css("analitica-uap.css", "sketchbook-integrado.css"));
  }
  if (map) {
    styles.push(...css("mapa-geografico.css"), leer(path.join(__dirname, "vendor/maplibre-gl-5.24.0.css")));
    scripts.push(...js("mapas-analiticos.js", "mapas-geograficos.js"));
    resources = [["uap-sdk-maplibre", "maplibre-gl-5.24.0.js"], ["uap-sdk-deck", "deck.gl-9.4.0.min.js"]]
      .map(([id, file]) => '<script id="' + id + '" type="text/plain">' +
        fs.readFileSync(path.join(__dirname, "vendor", file)).toString("base64") + "</script>").join("\n");
  }
  if (config.engine === "viewer") {
    styles.push(...css("visor-3d.css"));
    scripts.push(...js("mapas-analiticos.js"), leer(path.join(carpeta, "visor-modelos.js")));
  }
  if (config.engine === "compare") {
    styles.push(leer(path.join(carpeta, "comparacion.css")));
    scripts.push(leer(path.join(carpeta, "comparacion.js")));
  }
  scripts.push(...js("host-reproduccion.js"));
  return `<!doctype html>
<html lang="es"><meta charset="utf-8"><title>${config.title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>${styles.join("\n")}</style>
${resources}
<main>
  <header><h1>${config.title}</h1><p id="scope"></p></header>
  <div id="controls"></div>
  <div id="viz"></div>
  <p id="notice" role="status"></p>
</main>
<dialog id="record"><button type="button" id="close-record">Cerrar</button><h2 id="record-title"></h2><pre id="record-content"></pre></dialog>
${scripts.map((script) => "<script>\n" + script + "\n</script>").join("\n")}
</html>`;
}

function main() {
  const [slug, salida, origen = origenPredeterminado] = process.argv.slice(2);
  if (!slug || !salida || !/\.(html|svg)$/.test(salida)) {
    throw new Error("Uso: node propuesta-graficos/_compartido/reproducir.cjs <carpeta> <salida.html|salida.svg> [ruta a DB Test]");
  }
  const propuesta = cargarPropuesta(slug, path.resolve(origen));
  if (salida.endsWith(".svg")) {
    const [svg] = renderizar(propuesta).svgs;
    if (!svg) throw new Error("Esta vista necesita navegador. Usa salida.html o abre la lámina estática recuperada.");
    fs.writeFileSync(salida, svg);
  } else {
    fs.writeFileSync(salida, html(propuesta));
  }
  console.log(path.resolve(salida));
}

if (require.main === module) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { cargarPropuesta, renderizar, html };
