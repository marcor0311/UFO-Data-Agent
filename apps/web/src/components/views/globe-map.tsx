"use client";

/* Globe of reports at their exact coordinates: deck.gl GlobeView, rotating, with drag and zoom.
   Loaded lazily, only when a globe visualization is on screen. Rotation stops on
   interaction, with the pause button and under prefers-reduced-motion. */

import { useCallback, useEffect, useRef, useState } from "react";
import { SelectionLayer, SelectionTools, inside, type Pixel, type Tool } from "./map-selection";
import { Deck, _GlobeView as GlobeView, type PickingInfo } from "@deck.gl/core";
import { GeoJsonLayer, ScatterplotLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { feature } from "topojson-client";
import type { Feature, FeatureCollection, Geometry, Position } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

export type GlobePoint = { lat: number; lng: number; value: number; label: string; text: string };
type ViewState = { longitude: number; latitude: number; zoom: number };
/** A completed selection: its outline in longitude/latitude and the locations inside it. */
export type GlobeArea = { polygon: [number, number][]; points: GlobePoint[] };

/** Is the point on the visible face of the globe? (angular distance to the view centre under 90°) */
function facing(v: ViewState, lng: number, lat: number): boolean {
  const r = Math.PI / 180;
  return Math.sin(lat * r) * Math.sin(v.latitude * r) + Math.cos(lat * r) * Math.cos(v.latitude * r) * Math.cos((lng - v.longitude) * r) > 0;
}

const topology = world as unknown as Topology<{ countries: GeometryCollection }>;
/* Rings crossing the antimeridian (Russia, Fiji…) jump from 180 to -180; on the globe
   that draws a false band. Unwrapping keeps longitudes continuous (190 = -170). */
function unwrap(ring: Position[]): Position[] {
  let shift = 0;
  return ring.map(([lng, lat], i) => {
    if (i) { const prev = ring[i - 1][0]; if (lng - prev > 180) shift -= 360; else if (prev - lng > 180) shift += 360; }
    return [lng + shift, lat];
  });
}
function continuous(f: Feature<Geometry>): Feature<Geometry> {
  const g = f.geometry;
  if (g.type === "Polygon") return { ...f, geometry: { ...g, coordinates: g.coordinates.map(unwrap) } };
  if (g.type === "MultiPolygon") return { ...f, geometry: { ...g, coordinates: g.coordinates.map((p) => p.map(unwrap)) } };
  return f;
}
const raw = feature(topology, topology.objects.countries) as FeatureCollection<Geometry>;
// Antarctica wraps the pole itself and cannot be unwrapped; it carries no reports.
const countries = { ...raw, features: raw.features.filter((f) => String(f.id) !== "010").map(continuous) };
/* A dense ocean polygon so the sphere stays round when zoomed in. */
const OCEAN_RING: Position[] = [
  ...Array.from({ length: 73 }, (_, i) => [-180 + i * 5, 89.9]),
  ...Array.from({ length: 73 }, (_, i) => [180 - i * 5, -89.9]),
];
/* Night palette of prototype 06: dark sphere and warm points that brighten with reports. */
const OCEAN: [number, number, number] = [11, 22, 34];
const LAND: [number, number, number] = [28, 42, 56];
const BORDER: [number, number, number] = [55, 75, 95];
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 6;
const DEG_PER_SECOND = 9;
const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function center(points: GlobePoint[]): ViewState {
  let best = points[0];
  for (const c of points) if (c.value > best.value) best = c;
  return { longitude: best ? best.lng : 0, latitude: best ? Math.max(-50, Math.min(50, best.lat)) : 20, zoom: 1.2 };
}

function tooltip({ object }: PickingInfo) {
  const c = object as GlobePoint | undefined;
  if (!c || !("text" in c)) return null;
  return { text: `${c.label}\n${c.text}`, style: { fontSize: "12px", lineHeight: "1.4", padding: "6px 8px", borderRadius: "6px", background: "#10202f", color: "#e8f1f6" } };
}

export default function GlobeMap({ points, label, onArea }: { points: GlobePoint[]; label: string; onArea: (area: GlobeArea) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const deck = useRef<Deck<GlobeView> | null>(null);
  const view = useRef<ViewState>(center(points));
  const [spinning, setSpinning] = useState(() => !reducedMotion());
  const [tool, setTool] = useState<Tool>("move");
  const spin = useRef(spinning);
  spin.current = spinning;

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const d = new Deck<GlobeView>({
      parent: el, views: new GlobeView({ id: "globe" }), viewState: view.current,
      controller: { scrollZoom: { smooth: true }, keyboard: true, dragRotate: false, inertia: true },
      onViewStateChange: ({ viewState, interactionState }) => {
        const v = viewState as ViewState;
        view.current = { longitude: v.longitude, latitude: v.latitude, zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, v.zoom)) };
        if (interactionState?.isDragging) setSpinning(false);
        d.setProps({ viewState: view.current });
      },
      getTooltip: tooltip,
      layers: [
        new SolidPolygonLayer({ id: "ocean", data: [OCEAN_RING],
          getPolygon: (p) => p, getFillColor: OCEAN }),
        new GeoJsonLayer({ id: "land", data: countries, filled: true, stroked: true, getFillColor: LAND, getLineColor: BORDER, lineWidthMinPixels: 0.5 }),
        new ScatterplotLayer<GlobePoint>({
          id: "reports", data: points, pickable: true, radiusUnits: "pixels",
          getPosition: (c) => [c.lng, c.lat], getRadius: (c) => 0.8 + Math.sqrt(c.value) / 9,
          getFillColor: (c) => [255, 190 + Math.min(60, c.value / 20), 90, 180], parameters: { depthCompare: "always" },
        }),
      ],
    });
    deck.current = d;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      if (spin.current) {
        view.current = { ...view.current, longitude: ((view.current.longitude + DEG_PER_SECOND * dt + 540) % 360) - 180 };
        d.setProps({ viewState: view.current });
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); d.finalize(); deck.current = null; el.replaceChildren(); };
  }, [points]);

  const zoom = (delta: number) => {
    view.current = { ...view.current, zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.current.zoom + delta)) };
    deck.current?.setProps({ viewState: view.current });
  };
  const chooseTool = (t: Tool) => {
    setTool(t);
    if (t !== "move") setSpinning(false); // a moving globe cannot be selected
    deck.current?.setProps({ controller: t === "move" ? { scrollZoom: { smooth: true }, keyboard: true, dragRotate: false, inertia: true } : false });
  };
  const select = useCallback((poly: Pixel[]) => {
    const d = deck.current;
    const viewport = d?.getViewports()[0];
    if (!d || !viewport) return;
    const v = view.current;
    const inArea = points.filter((p) => {
      if (!facing(v, p.lng, p.lat)) return false;
      const [x, y] = viewport.project([p.lng, p.lat]);
      return inside([x, y], poly);
    });
    const polygon = poly.map((px) => viewport.unproject(px)).filter((c) => c.every(Number.isFinite)).map(([lng, lat]) => [lng, lat] as [number, number]);
    if (inArea.length && polygon.length >= 3) onArea({ polygon, points: inArea });
  }, [points, onArea]);
  const cancel = useCallback(() => chooseTool("move"), []); // eslint-disable-line react-hooks/exhaustive-deps
  const reset = () => { view.current = center(points); deck.current?.setProps({ viewState: view.current }); };

  return (
    <div className="geo-map">
      <div className="geo-map-toolbar">
        <SelectionTools tool={tool} onTool={chooseTool} />
        <span className="map-mode" role="group" aria-label="Zoom del globo">
          <button type="button" onClick={() => zoom(0.5)} aria-label="Acercar">+</button>
          <button type="button" onClick={() => zoom(-0.5)} aria-label="Alejar">−</button>
        </span>
        <button type="button" className="geo-map-reset" aria-pressed={!spinning} onClick={() => setSpinning((v) => !v)}>
          {spinning ? "Pausar giro" : "Reanudar giro"}
        </button>
        <button type="button" className="geo-map-reset globe-reset" onClick={reset}>Centrar</button>
      </div>
      <div className="map-stage">
        <div ref={host} className="geo-map-canvas globe-canvas" role="img" aria-label={label} />
        <SelectionLayer tool={tool} onSelect={select} onCancel={cancel} />
      </div>
      <p className="viz-note">Arrastra para girar el globo y usa la rueda o los botones para acercar. Con Rectángulo o Lazo, dibuja un área para abrirla en el mapa 2D y 3D. Cada punto está en la ubicación declarada; su tamaño y su brillo crecen con los informes que comparten esas coordenadas.</p>
    </div>
  );
}
