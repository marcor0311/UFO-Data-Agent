"use client";

import { useMemo } from "react";
import { geoGraticule10, geoNaturalEarth1, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { Feature, FeatureCollection, Geometry, MultiLineString } from "geojson";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";
import type { Catalog, GoldResult, Row } from "@/lib/contracts";
import { cell, metricLabel, num } from "@/lib/format";
import { Empty, RAMP, formatMetric, lowerBound, metricsOf, rampIndex, useTooltip, value } from "./shared";
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

/* -- points: one report each ------------------------------------------------ */
export function PointsView({ result }: Props) {
  const { ref, show, hide, layer } = useTooltip();
  const points = result.rows.filter((r) => typeof r.lat === "number" && typeof r.lng === "number");
  if (!points.length) return <Empty>No hay informes con coordenadas aptas para el mapa con esos filtros.</Empty>;
  const hasExternal = points.some((r) => r.uses_external_evidence === 1);
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{num(points.length)} informes con coordenadas aptas{result.truncated ? " (truncado)" : ""}</figcaption>
        <div className="viz-legend">
          <span><i className="swatch round" style={{ background: "var(--series-1)" }} />Coordenadas de Bronze</span>
          {hasExternal ? <span><i className="swatch round" style={{ background: "var(--series-2)" }} />Coordenadas del catálogo externo (UFO-search)</span> : null}
        </div>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Mapa de puntos de informes">
          <Basemap />
          {points.map((row) => {
            const xy = projection([row.lng as number, row.lat as number]);
            if (!xy) return null;
            const title = `Informe ${row.report_id}`;
            const lines = [{ value: `${num(row.lat)}, ${num(row.lng)}`, label: "lat, lng" },
              ...Object.keys(row).filter((k) => !["report_id", "lat", "lng"].includes(k) && !k.endsWith("_label"))
                .map((k) => ({ value: cell(row, k), label: k }))];
            return (
              <g key={String(row.report_id)} className="mark" tabIndex={0} aria-label={title}
                 onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                 onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                <circle cx={xy[0]} cy={xy[1]} r={12} fill="transparent" />
                <circle cx={xy[0]} cy={xy[1]} r={4} className="dot" fill={row.uses_external_evidence === 1 ? "var(--series-2)" : "var(--series-1)"} />
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Una coordenada puede ser el centro de una ciudad, no el lugar exacto del testigo.</p>
      </figure>
      {layer}
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
  const lower = lowerBound(result, metric);
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{lower ? "Informes" : metricLabel(catalog, metric)} por celda de {res}°{result.truncated ? ` (las ${num(result.row_count)} celdas con más informes)` : ""}</figcaption>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Densidad de informes por celdas de ${res} grados`}>
          <Basemap />
          {cells.map(({ row, d, lat, lng }, i) => {
            const v = value(row, metric) ?? 0;
            const title = `Celda ${lat}° a ${lat + res}° de latitud, ${lng}° a ${lng + res}° de longitud`;
            const lines = [{ value: formatMetric(v, metric, catalog), label: lower ? "todos los informes" : metricLabel(catalog, metric) }];
            if (lower) lines.push({ value: num(row[lower]), label: "sin candidatos pendientes" });
            return (
              <path key={i} d={d} fill={RAMP[Math.max(0, rampIndex(v, max))]} className="mark cell" tabIndex={0} aria-label={`${title}: ${lines[0].value}`}
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
  const lower = lowerBound(result, metric);
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  const unmapped = result.rows.filter((r) => !catalog?.country_m49[String(r.country_iso2)]
    || !countries.features.some((f: Feature) => String(f.id) === catalog.country_m49[String(r.country_iso2)]));
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{lower ? "Informes" : metricLabel(catalog, metric)} por país</figcaption>
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Mapa coroplético de informes por país">
          <Basemap fill={false} />
          {countries.features.map((f, i) => {
            const row = byM49.get(String(f.id));
            const v = row ? value(row, metric) ?? 0 : 0;
            const idx = rampIndex(v, max);
            const title = row ? cell(row, "country_iso2") : f.properties?.name ?? "";
            const lines = row ? [{ value: formatMetric(v, metric, catalog), label: lower ? "todos los informes" : metricLabel(catalog, metric) }] : [{ value: "0", label: "informes en este resultado" }];
            if (row && lower) lines.push({ value: num(row[lower]), label: "sin candidatos pendientes" });
            return (
              <path key={i} d={path(f) ?? ""} fill={idx < 0 ? "var(--empty-cell)" : RAMP[idx]} className="mark country"
                    tabIndex={row ? 0 : -1} aria-label={`${title}: ${lines[0].value}`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                    onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
          <path d={base.borders} className="map-borders" />
        </svg>
        <RampLegend max={max} note="escala logarítmica de todos los informes; no normaliza por población" />
        {unmapped.length ? (
          <p className="viz-note">
            {num(unmapped.length)} países o territorios pequeños no tienen geometría en el mapa de 110m (suman {num(unmapped.reduce((a, r) => a + (value(r, metric) ?? 0), 0))} informes); están en los datos exactos.
          </p>
        ) : null}
      </figure>
      {layer}
    </div>
  );
}
