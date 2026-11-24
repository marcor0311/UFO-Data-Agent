"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { geoGraticule10, geoNaturalEarth1, geoPath } from "d3-geo";
import type { MapReport } from "./geo-map";
import { feature, mesh } from "topojson-client";
import type { Feature, FeatureCollection, Geometry, MultiLineString } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";
import type { Catalog, GoldResult, Row } from "@/lib/contracts";
import { cell, metricLabel, num } from "@/lib/format";
import { Empty, RAMP, formatMetric, metricsOf, rampIndex, useTooltip, value } from "./shared";
import { RampLegend } from "./charts";

type Props = { result: GoldResult; catalog: Catalog | null };
const WIDTH = 760;
const HEIGHT = 400;

const topology = world as unknown as Topology<{ countries: GeometryCollection; land: GeometryCollection }>;
const countries = feature(topology, topology.objects.countries) as FeatureCollection<Geometry, { name: string }>;
const borders = mesh(topology, topology.objects.countries, (a, b) => a !== b) as MultiLineString;
const sphere = { type: "Sphere" } as const;
const projection = geoNaturalEarth1().fitExtent([[8, 8], [WIDTH - 8, HEIGHT - 8]], sphere);
const path = geoPath(projection);
const base = { sphere: path(sphere) ?? "", graticule: path(geoGraticule10()) ?? "", borders: path(borders) ?? "" };

function Basemap({ fill = true }: { fill?: boolean }) {
  return (
    <>
      <path d={base.sphere} className="map-sphere" />
      <path d={base.graticule} className="map-graticule" />
      {fill ? countries.features.map((f, i) => <path key={i} d={path(f) ?? ""} className="map-land" />) : null}
      <path d={base.borders} className="map-borders" />
    </>
  );
}

/* -- points: MapLibre + deck.gl map (2D/3D, points or 3D models) ------------- */
// WebGL engine is fetched only when a map visualization exists, never in the initial bundle.
const GeoMap = dynamic(() => import("./geo-map"), { ssr: false, loading: () => <div className="geo-map-canvas geo-map-loading">Cargando mapa…</div> });

/** Mount the WebGL map only once it is near the viewport (limits live WebGL contexts). */
function useNearViewport() {
  const ref = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || near) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setNear(true); io.disconnect(); } }, { rootMargin: "300px" });
    io.observe(el);
    return () => io.disconnect();
  }, [near]);
  return { ref, near };
}

export function PointsView({ result }: Props) {
  const { ref, near } = useNearViewport();
  const reports = useMemo<MapReport[]>(() => result.rows
    .filter((r) => typeof r.lat === "number" && typeof r.lng === "number")
    .map((r) => ({
      id: String(r.report_id), lng: r.lng as number, lat: r.lat as number,
      shape: (r.shape_code as string | null) ?? null, shapeLabel: String(r.shape_code_label ?? ""),
      source: String(r.source_code_label ?? r.source_code ?? ""), date: r.date_key == null ? null : String(r.date_key),
      external: r.uses_external_evidence === 1,
    })), [result.rows]);
  if (!reports.length) return <Empty>No hay informes con coordenadas aptas para el mapa con esos filtros.</Empty>;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{num(reports.length)} informes con coordenadas aptas{result.truncated ? " (truncado)" : ""}</figcaption>
        {near ? <GeoMap reports={reports} /> : <div className="geo-map-canvas geo-map-loading">Mapa</div>}
      </figure>
    </div>
  );
}

/* -- density: report counts per grid cell --------------------------------- */
function resolutionOf(result: GoldResult): number {
  const filter = result.query.filters.find((f) => f.column === "resolution_deg" && (f.op ?? "eq") === "eq");
  if (filter && typeof filter.value === "number") return filter.value;
  return result.query.group_by[0]?.startsWith("cell5") ? 5 : 1;
}

export function DensityView({ result, catalog }: Props) {
  const { ref, show, hide, layer } = useTooltip();
  const metric = metricsOf(result, catalog)[0];
  const [latKey, lngKey] = result.query.group_by;
  const res = resolutionOf(result);
  const cells = useMemo(() => result.rows.map((row) => {
    const lat = row[latKey] as number;
    const lng = row[lngKey] as number;
    const ring = [[lng, lat], [lng + res, lat], [lng + res, lat + res], [lng, lat + res], [lng, lat]]
      .map(([x, y]) => projection([x, y])).filter((p): p is [number, number] => p !== null);
    return { row, d: "M" + ring.map((p) => p.join(",")).join("L") + "Z", lat, lng };
  }), [result.rows, latKey, lngKey, res]);
  if (result.empty) return <Empty />;
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{metricLabel(catalog, metric)} por celda de {res}°{result.truncated ? ` (las ${num(result.row_count)} celdas con más informes)` : ""}</figcaption>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Densidad de informes por celdas de ${res} grados`}>
          <Basemap />
          {cells.map(({ row, d, lat, lng }, i) => {
            const v = value(row, metric) ?? 0;
            const title = `Celda ${lat}° a ${lat + res}° de latitud, ${lng}° a ${lng + res}° de longitud`;
            const lines = [{ value: formatMetric(v, metric, catalog), label: metricLabel(catalog, metric) }];
            return (
              <path key={i} d={d} fill={RAMP[Math.max(0, rampIndex(v, max))]} className="mark cell" role="img" tabIndex={0} aria-label={`${title}: ${lines[0].value}`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                    onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
        </svg>
        <RampLegend max={max} note="escala logarítmica de todos los informes; cuenta informes, no área ni población" />
      </figure>
      {layer}
    </div>
  );
}

/* -- choropleth: report counts per country -------------------------------- */
export function ChoroplethView({ result, catalog }: Props) {
  const { ref, show, hide, layer } = useTooltip();
  const missingId = useId();
  const metric = metricsOf(result, catalog)[0];
  const byM49 = useMemo(() => {
    const map = new Map<string, Row>();
    for (const row of result.rows) {
      const m49 = catalog?.country_m49[String(row.country_iso2)];
      if (m49) map.set(m49, row);
    }
    return map;
  }, [result.rows, catalog]);
  if (result.empty) return <Empty />;
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  const unmapped = result.rows.filter((r) => !catalog?.country_m49[String(r.country_iso2)]
    || !countries.features.some((f: Feature) => String(f.id) === catalog.country_m49[String(r.country_iso2)]));
  return (
    <div className="viz choropleth" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{metricLabel(catalog, metric)} por país</figcaption>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label={`Mapa de ${metricLabel(catalog, metric).toLowerCase()} por país`}
             aria-describedby={`${missingId}-coverage`}>
          <defs>
            <pattern id={missingId} width={6} height={6} patternUnits="userSpaceOnUse">
              <rect width={6} height={6} fill="var(--surface-2)" />
              <path d="M-1 1L1 -1M0 6L6 0M5 7L7 5" stroke="var(--axis)" strokeWidth={1} />
            </pattern>
          </defs>
          <Basemap fill={false} />
          {countries.features.map((f, i) => {
            const row = byM49.get(String(f.id));
            const v = row ? value(row, metric) : null;
            const idx = v === null ? -1 : rampIndex(v, max);
            const title = row ? cell(row, "country_iso2") : f.properties?.name ?? "";
            const text = !row ? "Sin fila en este resultado" : v === null ? "Sin valor disponible" : formatMetric(v, metric, catalog);
            const lines = [{ value: text, label: metricLabel(catalog, metric) }];
            return (
              <path key={i} d={path(f) ?? ""} fill={v === null ? `url(#${missingId})` : idx < 0 ? "var(--empty-cell)" : RAMP[idx]}
                    className="mark country" data-m49={String(f.id)} role={row ? "img" : undefined} aria-hidden={!row}
                    tabIndex={row ? 0 : -1} aria-label={`${title}: ${text}`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                    onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
          <path d={base.borders} className="map-borders" />
        </svg>
        <RampLegend max={max} missing note="escala logarítmica de todos los informes; no normaliza por población" />
        <p className="viz-note" id={`${missingId}-coverage`}>
          {result.truncated ? "El mapa muestra solo los países devueltos por el resultado truncado." : "El mapa muestra los países devueltos por esta consulta."}
          {" "}Las zonas rayadas no tienen fila o valor en este resultado; no equivalen a cero.
        </p>
        {unmapped.length ? (
          <p className="viz-note">
            {num(unmapped.length)} {unmapped.length === 1 ? "país o territorio de este resultado no tiene" : "países o territorios de este resultado no tienen"} geometría disponible en este mapa. Sus valores se conservan en “Datos exactos”.
          </p>
        ) : null}
      </figure>
      {layer}
    </div>
  );
}
