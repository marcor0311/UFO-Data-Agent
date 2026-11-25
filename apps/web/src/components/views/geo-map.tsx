"use client";

/* Geographic map of reports: MapLibre + deck.gl (overlay), as in DB Test.
   2D: flat, no tilt. 3D: Terrarium relief, extruded buildings, tilt and rotation.
   Points: one marker per report. Models: a solid model per standardized shape,
   within a triangle budget; reports without model or beyond budget keep their point.
   This module is loaded lazily, only when a map visualization is on screen. */

import "maplibre-gl/dist/maplibre-gl.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMapArea } from "@/lib/map-area";
import { SelectionLayer, SelectionSummary, SelectionTools, inside, type Pixel, type Tool } from "./map-selection";
import maplibregl, { type Map as MapLibre } from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import { SimpleMeshLayer } from "@deck.gl/mesh-layers";
import type { Layer, PickingInfo } from "@deck.gl/core";
import { ModelViewer } from "./model-viewer";
import { mesh, metersPerPixel, modelMetrics, planModels, shapeKind, type ModelKind } from "@/lib/map-models";

export type MapReport = {
  id: string; lng: number; lat: number; shape: string | null; shapeLabel: string; source: string; date: string | null; external: boolean;
  /** Reports sharing these exact coordinates (area opened from the globe); absent for a single report. */
  count?: number;
};
type Placed = MapReport & { kind: ModelKind };
type Mode = "2d" | "3d";
type Style = "points" | "models";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const REFERENCE_METERS = 12; // visual reference, not a measured size
const CLEARANCE_METERS = 50; // illustrative height over terrain, not a flight altitude
const POINT: [number, number, number] = [37, 99, 178];
const SELECTED: [number, number, number] = [208, 59, 59]; // critical: stands out from both point colours
const SHOWN_IDS = 12;
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function bounds(reports: MapReport[]): [[number, number], [number, number]] {
  let w = 180, s = 90, e = -180, n = -90;
  if (reports.length >= 50) {
    // Frame the bulk of the reports: a few stray coordinates (2 % per side) do not zoom the map out to the world.
    const q = (xs: number[], f: number) => xs[Math.min(xs.length - 1, Math.floor(f * xs.length))];
    const lngs = reports.map((r) => r.lng).sort((a, b) => a - b), lats = reports.map((r) => r.lat).sort((a, b) => a - b);
    [w, e, s, n] = [q(lngs, 0.02), q(lngs, 0.98), q(lats, 0.02), q(lats, 0.98)];
  } else for (const r of reports) { w = Math.min(w, r.lng); e = Math.max(e, r.lng); s = Math.min(s, r.lat); n = Math.max(n, r.lat); }
  const pad = Math.max(0.05, Math.max(e - w, n - s) * 0.08);
  return [[Math.max(-180, w - pad), Math.max(-85, s - pad)], [Math.min(180, e + pad), Math.min(85, n + pad)]];
}

function tooltip({ object }: PickingInfo) {
  const r = object as MapReport | undefined;
  if (!r || !("id" in r)) return null;
  if (r.count) return { text: `${r.count} ${r.count === 1 ? "informe" : "informes"} en esta ubicación\n${r.lat.toFixed(3)}, ${r.lng.toFixed(3)}`,
    style: { fontSize: "12px", lineHeight: "1.4", padding: "6px 8px", borderRadius: "6px", background: "#10202f", color: "#e8f1f6" } };
  const lines = [`Informe ${r.id}`, r.shapeLabel ? `Forma: ${r.shapeLabel}` : "", r.date ? `Fecha: ${r.date}` : "", r.source ? `Fuente: ${r.source}` : "",
    `${r.lat.toFixed(3)}, ${r.lng.toFixed(3)}`, r.external ? "Coordenadas del catálogo externo" : ""].filter(Boolean);
  return { text: lines.join("\n"), style: { fontSize: "12px", lineHeight: "1.4", padding: "6px 8px", borderRadius: "6px", background: "#10202f", color: "#e8f1f6" } };
}

export default function GeoMap({ reports, initialSelection = null }: { reports: MapReport[]; initialSelection?: Set<string> | null }) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibre | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<Mode>("2d");
  const [style, setStyle] = useState<Style>("points");
  // revision: camera changed (models rescale with zoom); settled: camera stopped or tiles arrived (re-read terrain).
  const [view, setView] = useState({ zoom: 3, revision: 0, settled: 0 });
  const styleRef = useRef<Style>(style);
  useEffect(() => { styleRef.current = style; }, [style]);
  // Terrain elevation per coordinate, read once per settled camera instead of on every frame of a move.
  const heights = useRef<{ key: string; byCoord: Map<string, number> }>({ key: "", byCoord: new Map() });
  const [failed, setFailed] = useState<string | null>(null);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [tool, setTool] = useState<Tool>("move");
  const [selected, setSelected] = useState<Set<string> | null>(initialSelection);
  const { setArea } = useMapArea();
  const box = useMemo(() => bounds(reports), [reports]);
  const withModel = useMemo(() => reports.flatMap((r) => { const kind = shapeKind(r.shape); return kind ? [{ ...r, kind }] : []; }), [reports]);

  // One map per visualization; destroyed on unmount so long conversations do not leak WebGL contexts.
  useEffect(() => {
    if (!host.current) return;
    const m = new maplibregl.Map({
      container: host.current, style: STYLE_URL, bounds: box, fitBoundsOptions: { padding: 40, maxZoom: 12 },
      maxPitch: 0, dragRotate: false, attributionControl: { compact: true },
      cooperativeGestures: false, // the wheel zooms directly, with no "use Cmd + scroll" hint
      renderWorldCopies: false, // one world: countries are not repeated
    });
    m.touchZoomRotate.disableRotation();
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
    const deck = new MapboxOverlay({ interleaved: false, layers: [], getTooltip: tooltip });
    m.addControl(deck);
    map.current = m;
    overlay.current = deck;

    // While moving, only models need rebuilding (their scale follows zoom), at most every 100 ms.
    // Points are drawn by the GPU as the camera moves: nothing to recompute until it stops.
    let timer: ReturnType<typeof setTimeout> | null = null;
    const step = () => setView((v) => ({ ...v, zoom: m.getZoom(), revision: v.revision + 1 }));
    const sync = () => setView((v) => ({ zoom: m.getZoom(), revision: v.revision + 1, settled: v.settled + 1 }));
    const throttled = () => {
      if (styleRef.current !== "models" || timer) return;
      timer = setTimeout(() => { timer = null; step(); }, 100);
    };
    m.on("move", throttled);
    m.on("moveend", sync);
    m.on("idle", sync); // terrain tiles arrive asynchronously: re-query elevations
    m.on("error", (e) => { if (!m.loaded() && String(e.error?.message ?? "").includes("style")) setFailed("No se pudo cargar el mapa base. Revisa la conexión."); });
    m.on("load", () => {
      m.addSource("terrain", { type: "raster-dem", tiles: [TERRARIUM], tileSize: 256, encoding: "terrarium", maxzoom: 15 });
      m.addSource("terrain-shade", { type: "raster-dem", tiles: [TERRARIUM], tileSize: 256, encoding: "terrarium", maxzoom: 15 });
      m.addLayer({ id: "relief", type: "hillshade", source: "terrain-shade", layout: { visibility: "none" },
                   paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#5b6b78" } }, "building");
      m.addLayer({ id: "buildings-3d", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 14,
                   layout: { visibility: "none" },
                   paint: { "fill-extrusion-color": "#d9dfe4", "fill-extrusion-opacity": 0.85,
                            "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
                            "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0] } });
      setReady(true);
      sync();
    });
    return () => {
      if (timer) clearTimeout(timer);
      deck.finalize();
      m.remove();
      map.current = null;
      overlay.current = null;
    };
  }, [box]);

  // 2D ⇄ 3D: same map, camera and relief change; no second engine.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const duration = reducedMotion() ? 0 : 900;
    const three = mode === "3d";
    m.setLayoutProperty("relief", "visibility", three ? "visible" : "none");
    m.setLayoutProperty("buildings-3d", "visibility", three ? "visible" : "none");
    if (three) {
      m.setMaxPitch(80);
      m.dragRotate.enable();
      m.touchZoomRotate.enableRotation();
      m.setTerrain({ source: "terrain", exaggeration: 1.5 });
      m.easeTo({ pitch: 62, bearing: -20, duration });
    } else {
      m.setTerrain(null);
      m.easeTo({ pitch: 0, bearing: 0, duration });
      m.once("moveend", () => m.setMaxPitch(0));
      m.dragRotate.disable();
      m.touchZoomRotate.disableRotation();
    }
  }, [mode, ready]);

  // deck.gl layers: points always; models on demand within the triangle budget.
  useEffect(() => {
    const m = map.current, deck = overlay.current;
    if (!m || !deck || !ready) return;
    const three = mode === "3d";
    const key = three ? `3d:${view.settled}` : "";
    if (heights.current.key !== key) heights.current = { key, byCoord: new Map() };
    const cache = heights.current.byCoord;
    const ground = (r: MapReport) => {
      if (!three) return 0;
      const coord = `${r.lng},${r.lat}`;
      let h = cache.get(coord);
      if (h === undefined) { h = (m.queryTerrainElevation([r.lng, r.lat]) ?? 0) * 1.5; cache.set(coord, h); }
      return h;
    };
    const modelKey = style === "models" ? view.revision : -1;
    const layers: Layer[] = [];

    let placed: Placed[] = [];
    if (style === "models") {
      // Prefer reports on screen so the budget is spent where the person is looking.
      const b = m.getBounds();
      const visible = withModel.filter((r) => b.contains([r.lng, r.lat]));
      placed = planModels(visible.length ? visible : withModel, view.zoom).rows;
    }
    const modelled = new Set(placed.map((r) => r.id));

    layers.push(new ScatterplotLayer<MapReport>({
      id: "reports", data: reports, pickable: true, billboard: true, stroked: true, radiusUnits: "pixels", lineWidthUnits: "pixels",
      getPosition: (r) => [r.lng, r.lat, ground(r)], getRadius: (r) => (r.count ? 3 + Math.min(9, Math.sqrt(r.count) / 2) : modelled.has(r.id) ? 3 : 5.5),
      getFillColor: (r) => [...(selected?.has(r.id) ? SELECTED : POINT),
        selected && !selected.has(r.id) ? 70 : modelled.has(r.id) ? 140 : 235] as [number, number, number, number],
      getLineColor: [255, 255, 255, 230], getLineWidth: 1.2,
      parameters: { depthCompare: "always" },
      updateTriggers: { getPosition: [three, view.settled], getRadius: [placed.length, modelKey], getFillColor: [placed.length, modelKey, selected] },
    }));

    if (placed.length) {
      const zoom = view.zoom;
      const minPixels = 26 + 16 * Math.max(0, Math.min(1, (zoom - 10) / 8)); // readable symbol size, not a physical size
      const scaleOf = (r: Placed) => Math.max(REFERENCE_METERS, minPixels * metersPerPixel(r.lat, zoom)) / modelMetrics(r.kind).diameter;
      const lift = (r: Placed) => (three ? CLEARANCE_METERS : 0);
      const at = (r: Placed): [number, number, number] => [r.lng, r.lat, ground(r) - modelMetrics(r.kind).bottom * scaleOf(r) + lift(r)];
      const detail = planModels(placed, zoom).detail;
      if (three) {
        layers.push(new LineLayer<Placed>({
          id: "model-anchors", data: placed, getSourcePosition: (r) => [r.lng, r.lat, ground(r)], getTargetPosition: at,
          getColor: [79, 105, 144, 190], getWidth: 1, widthUnits: "pixels",
          updateTriggers: { getSourcePosition: [view.revision], getTargetPosition: [view.revision] },
        }));
      }
      const byKind = new Map<ModelKind, Placed[]>();
      for (const r of placed) { const list = byKind.get(r.kind); if (list) list.push(r); else byKind.set(r.kind, [r]); }
      for (const [kind, data] of byKind) {
        layers.push(new SimpleMeshLayer<Placed>({
          id: `model-${kind}`, data, pickable: true, mesh: mesh(kind, detail) as never,
          getPosition: at, getColor: [255, 255, 255, 255], getOrientation: [0, 0, 0],
          getScale: (r) => { const s = scaleOf(r); return [s, s, s]; },
          material: { ambient: 0.45, diffuse: 0.7, shininess: 24, specularColor: [70, 80, 95] },
          updateTriggers: { getPosition: [view.revision, three], getScale: [view.revision] },
        }));
      }
    }
    deck.setProps({ layers });
  }, [reports, withModel, style, mode, view, ready, selected]);

  const select = useCallback((poly: Pixel[]) => {
    const m = map.current;
    if (!m) return;
    const hit = reports.filter((r) => { const p = m.project([r.lng, r.lat]); return inside([p.x, p.y], poly); });
    setSelected(new Set(hit.map((r) => r.id)));
    setTool("move");
    const n = hit.reduce((s, r) => s + (r.count ?? 1), 0);
    setArea({ polygon: poly.map((px) => { const c = m.unproject(px); return [c.lng, c.lat] as [number, number]; }),
              label: `${n.toLocaleString("es-ES")} ${n === 1 ? "informe" : "informes"} en el mapa` });
  }, [reports, setArea]);
  const cancel = useCallback(() => setTool("move"), []);
  const picked = selected ? reports.filter((r) => selected.has(r.id)) : [];

  // Back from the catalog: the map was hidden, so it must re-measure its canvas.
  useEffect(() => { if (!catalogOpen) map.current?.resize(); }, [catalogOpen]);

  const modelCount = withModel.length;
  const kinds = new Set(withModel.map((r) => r.kind)).size;
  return (
    <div className="geo-map">
      <div className="geo-map-toolbar">
        <SelectionTools tool={tool} onTool={setTool} />
        <span className="map-mode" role="group" aria-label="Vista del mapa">
          <button type="button" aria-pressed={mode === "2d"} onClick={() => setMode("2d")}>Mapa 2D</button>
          <button type="button" aria-pressed={mode === "3d"} onClick={() => setMode("3d")}>Mapa 3D</button>
        </span>
        <span className="map-mode" role="group" aria-label="Representación de los informes">
          <button type="button" aria-pressed={style === "points"} onClick={() => setStyle("points")}>Puntos</button>
          <button type="button" aria-pressed={style === "models"} onClick={() => setStyle("models")} disabled={!modelCount}
                  title={modelCount ? undefined : "Ningún informe de esta selección tiene una forma con modelo"}>Modelos 3D</button>
        </span>
        <button type="button" className="geo-map-reset" aria-pressed={catalogOpen} onClick={() => setCatalogOpen((v) => !v)}>{catalogOpen ? "Volver al mapa" : "Ver los 28 modelos"}</button>
        <button type="button" className="geo-map-reset" onClick={() => map.current?.fitBounds(box, { padding: 40, maxZoom: 12, pitch: mode === "3d" ? 62 : 0, bearing: mode === "3d" ? -20 : 0, duration: reducedMotion() ? 0 : 800 })}>
          Encuadrar
        </button>
      </div>
      <div className="map-stage" hidden={catalogOpen}>
        <div className="geo-map-canvas" ref={host} role="region"
             aria-label={`Mapa ${mode === "3d" ? "3D con relieve" : "2D"} de ${reports.reduce((s, r) => s + (r.count ?? 1), 0)} informes, representados como ${style === "models" ? "modelos 3D por forma" : "puntos"}`} />
        <SelectionLayer tool={tool} onSelect={select} onCancel={cancel} />
      </div>
      {selected ? (
        <SelectionSummary onClear={() => { setSelected(null); setArea(null); }}>
          {picked.some((r) => r.count) ? (
            <strong>{picked.reduce((s, r) => s + (r.count ?? 1), 0).toLocaleString("es-ES")} informes seleccionados en {picked.length.toLocaleString("es-ES")} {picked.length === 1 ? "ubicación" : "ubicaciones"}</strong>
          ) : (
            <>
              <strong>{picked.length} {picked.length === 1 ? "informe seleccionado" : "informes seleccionados"}</strong>
              {picked.length ? <span>: {picked.slice(0, SHOWN_IDS).map((r) => r.id).join(", ")}{picked.length > SHOWN_IDS ? ` y ${picked.length - SHOWN_IDS} más` : ""}</span> : null}
            </>
          )}
        </SelectionSummary>
      ) : null}
      {catalogOpen ? <ModelViewer onClose={() => setCatalogOpen(false)} /> : null}
      {failed ? <p className="viz-note" role="alert">{failed}</p> : null}
      <p className="viz-note">
        {style === "models"
          ? `${modelCount} informes tienen una forma con modelo (${kinds} formas). Los demás, o los que no caben en el presupuesto de detalle, se muestran como punto. Tamaño de referencia de ${REFERENCE_METERS} m y altura de ${CLEARANCE_METERS} m en 3D: son ilustrativos, no medidas del objeto. `
          : ""}
        {mode === "3d" ? "Arrastra con clic derecho o Ctrl para girar e inclinar. " : ""}
        Una coordenada puede ser el centro de una ciudad, no el lugar exacto del testigo.
      </p>
    </div>
  );
}

