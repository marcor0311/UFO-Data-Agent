/* Montaje aislado para examinar los componentes recuperados. */
const $ = (query) => document.querySelector(query);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);

const { config, registros } = window.recuperacion;
const cases = registros;
const state = { compareIds: [1, 121] };
function remember() {}

$("#scope").textContent = config.scope ?? "";
$("#close-record").addEventListener("click", () => $("#record").close());

const normalized = config.engine === "compare" ? cases : window.UAPAnalytics.normalize(registros);
const byId = new Map(normalized.map((report) => [String(report.id), report]));

function mostrarDatos(title, data) {
  $("#record-title").textContent = title;
  $("#record-content").textContent = JSON.stringify(data, null, 2);
  $("#record").showModal();
}
function selectItem({ caseId }) {
  const record = byId.get(String(caseId));
  if (record) mostrarDatos("Reporte " + (record.dbId ?? record.recordId), record.raw);
}
function seleccionar(ids, label = "Selección") {
  mostrarDatos(label, { cantidad: ids.length, ids });
}

let mounted;
if (config.engine === "viewer") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Abrir visor de modelos 3D";
  button.onclick = () => window.UAPModelViewer.open();
  $("#controls").append(button);
} else if (config.engine === "compare") {
  renderCompareControls();
  renderCaseComparison();
} else if (config.engine === "map") {
  $("#viz").className = "map-host";
  mounted = window.UAPGeo.mount({
    container: $("#viz"),
    records: normalized,
    areaBounds: config.bounds,
    areaLabel: config.scope,
    pitch: 0,
    onRecord: (id) => selectItem({ caseId: id }),
    onSelect: seleccionar,
    fallback: () => {
      $("#notice").textContent = "El mapa no pudo cargar. Consulta la lámina y el respaldo del prototipo.";
    },
  });
} else {
  mounted = window.UAPAnalytics.mount({
    container: $("#viz"),
    kind: config.id,
    records: normalized,
    options: { cohortKey: null },
    scope: config.scope,
    onRecord: (id) => selectItem({ caseId: id }),
    onSelect: seleccionar,
    onView: (kind, selection) => seleccionar(selection.ids, kind),
  });
}

window.addEventListener("pagehide", () => mounted?.destroy(), { once: true });
