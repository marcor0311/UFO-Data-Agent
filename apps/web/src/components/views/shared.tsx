"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Catalog, GoldResult, Row } from "@/lib/contracts";
import { cell, dimensionLabel, metricLabel, num, percent } from "@/lib/format";

/* Sequential ramp (one hue, light → dark), validated reference steps. */
export const RAMP = ["var(--seq-100)", "var(--seq-200)", "var(--seq-300)", "var(--seq-400)", "var(--seq-500)", "var(--seq-600)", "var(--seq-700)"];

/** Metric columns present in the rows, the requested ones first. */
export function metricsOf(result: GoldResult, catalog: Catalog | null): string[] {
  const keys = result.rows[0] ? Object.keys(result.rows[0]) : [...result.query.metrics];
  const present = keys.filter((k) => catalog?.metrics[k] || result.query.metrics.includes(k));
  return [...result.query.metrics.filter((m) => present.includes(m)), ...present.filter((m) => !result.query.metrics.includes(m))];
}

/** Metrics drawn as panels: an analysis draws only the ones it asks for; the rest stay in the exact data. */
export function chartMetrics(result: GoldResult, catalog: Catalog | null): string[] {
  const all = metricsOf(result, catalog);
  return result.query.analysis ? all.filter((m) => result.query.metrics.includes(m)) : all;
}

export function value(row: Row, metric: string): number | null {
  const v = row[metric];
  return typeof v === "number" ? v : null;
}

export function formatMetric(v: number | null, metric: string, catalog: Catalog | null): string {
  if (v === null) return "—";
  if (catalog?.metrics[metric]?.unit === "año") return String(v);  // a year reads 1965, never “1.965”
  return num(v) + (percent(metric, catalog) ? " %" : "");
}

export function groupLabel(row: Row, groups: string[]): string {
  return groups.map((g) => cell(row, g)).join(", ") || "Total";
}

export function niceMax(max: number): number {
  if (max <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(max)));
  for (const step of [1, 2, 2.5, 5, 10]) if (step * exp >= max) return step * exp;
  return 10 * exp;
}

export function ticks(max: number, count = 4): number[] {
  const top = niceMax(max);
  return Array.from({ length: count + 1 }, (_, i) => (top * i) / count);
}

/** Sequential step (0 → no fill). Log scale for heavy-tailed counts (maps), linear otherwise. */
export function rampIndex(v: number, max: number, scale: "log" | "linear" = "log"): number {
  if (v <= 0 || max <= 0) return -1;
  if (max <= 1) return RAMP.length - 1;
  const share = scale === "log" ? Math.log(v) / Math.log(max) : v / max;
  return Math.min(RAMP.length - 1, Math.floor(share * RAMP.length - 1e-9 * (scale === "linear" ? 1 : 0)));
}

export function rampLegend(max: number, scale: "log" | "linear" = "log"): { color: string; from: number }[] {
  return RAMP.map((color, i) => ({
    color,
    from: i === 0 ? 1 : scale === "log" ? Math.ceil(Math.exp((i / RAMP.length) * Math.log(Math.max(max, 1)))) : Math.ceil((i / RAMP.length) * max),
  }));
}

/** Diverging fill: blue below the centre, orange above, stronger with the distance. */
export function divergingColor(v: number, spread: number): string {
  // Square root: one extreme cell must not wash out every other one.
  const share = Math.sqrt(Math.min(1, Math.abs(v) / Math.max(spread, 1e-9)));
  const strength = Math.round(12 + share * 78);
  if (Math.abs(v) < 1e-12) return "var(--empty-cell)";
  return `color-mix(in srgb, ${v < 0 ? "var(--series-1)" : "var(--series-2)"} ${strength}%, var(--surface))`;
}

export function DivergingLegend({ spread, ratio = false, unit = "" }: { spread: number; ratio?: boolean; unit?: string }) {
  const fmt = (x: number) => (ratio ? `×${(Math.round(x * 100) / 100).toLocaleString("es-ES")}` : `${x > 0 ? "+" : ""}${(Math.round(x * 100) / 100).toLocaleString("es-ES")}${unit}`);
  const low = ratio ? 1 / spread : -spread, high = ratio ? spread : spread;
  return (
    <div className="viz-legend diverging" aria-label="Escala divergente">
      <span>{fmt(low)}</span>
      <span className="diverging-bar" aria-hidden="true"
            style={{ background: "linear-gradient(90deg, color-mix(in srgb, var(--series-1) 90%, var(--surface)), var(--empty-cell), color-mix(in srgb, var(--series-2) 90%, var(--surface)))" }} />
      <span>{fmt(high)}</span>
      <span className="viz-legend-note">{ratio ? "×1 = lo esperado; azul, menos; naranja, más" : "0 = sin cambio; azul, menos; naranja, más"}</span>
    </div>
  );
}

/** Round, evenly spaced year ticks. */
export function yearTicks(x0: number, x1: number, max = 7): number[] {
  const span = Math.max(1, x1 - x0);
  const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500].find((s) => span / s <= max - 1) ?? 1000;
  const out = [];
  for (let t = Math.ceil(x0 / step) * step; t <= x1 + 1e-9; t += step) out.push(t);
  return out;
}

type Tip = { x: number; y: number; title: string; lines: { key?: string; value: string; label: string }[] } | null;

/** One positioned tooltip per chart; values lead, labels follow. Uses text nodes only.
    Also measures the container so charts draw at real pixel size (text never scales). */
export function useTooltip(fallbackWidth = 720) {
  const ref = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<Tip>(null);
  const [width, setWidth] = useState(fallbackWidth);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(320, Math.floor(entry.contentRect.width))));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const show = useCallback((event: { clientX: number; clientY: number } | DOMRect, content: Omit<NonNullable<Tip>, "x" | "y">) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const x = "clientX" in event ? event.clientX : event.left + event.width / 2;
    const y = "clientY" in event ? event.clientY : event.top;
    setTip({ ...content, x: x - box.left, y: y - box.top });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  const layer = tip ? (
    <div className="viz-tip" role="status" style={{ left: tip.x, top: tip.y }}>
      <div className="viz-tip-title">{tip.title}</div>
      {tip.lines.map((line, i) => (
        <div className="viz-tip-row" key={i}>
          {line.key ? <span className="viz-tip-key" style={{ background: line.key }} /> : null}
          <strong>{line.value}</strong>
          <span>{line.label}</span>
        </div>
      ))}
    </div>
  ) : null;
  return { ref, show, hide, layer, width };
}

export function DataTable({ result, catalog, caption }: { result: GoldResult; catalog: Catalog | null; caption?: string }) {
  const first = result.rows[0] as Record<string, unknown> | undefined;
  // Nested values (a box of quantiles, the counts of each cluster) stay out of the table; lists read as text.
  const scalar = (k: string) => !first || first[k] === null || typeof first[k] !== "object" || Array.isArray(first[k]);
  const groups = result.query.group_by.length && !result.query.analysis ? result.query.group_by
    : first ? Object.keys(first).filter((k) => !k.endsWith("_label") && !metricsOf(result, catalog).includes(k) && scalar(k)) : [];
  const metrics = metricsOf(result, catalog);
  const percentages = metrics.filter((metric) => percent(metric, catalog));
  const denominators = result.total ? metrics.flatMap((metric) => {
    const denominator = catalog?.metrics[metric]?.denominator;
    if (!denominator) return [];
    // Gold counts the full filtered report population in matched_source_rows,
    // including when report_count was not requested as a separate metric.
    const count = result.total?.[denominator] ?? (denominator === "report_count" ? result.matched_source_rows : null);
    return typeof count === "number" ? [{ metric, denominator, count }] : [];
  }) : [];
  return (
    <div className="viz-table-wrap">
      <table className="viz-table">
        {caption || result.total || result.truncated ? (
          <caption>
            {caption ? <p>{caption}</p> : null}
            <p>
              Se {result.rows.length === 1 ? "muestra" : "muestran"} {num(result.rows.length)} {result.rows.length === 1 ? "fila" : "filas"} de datos;
              {result.truncated ? " hay más filas no mostradas." : " resultado completo."}
            </p>
            {result.total ? (
              <p>El total abarca todos los grupos que cumplen los filtros y la elegibilidad de la consulta{result.truncated ? ", incluidos los no mostrados" : ""}.</p>
            ) : null}
            {result.total && percentages.length ? <p>Los porcentajes del total se recalculan sobre esa población; no se suman ni se promedian los porcentajes de las filas.</p> : null}
            {denominators.map(({ metric, denominator, count }) => (
              <p key={metric}>Denominador de “{metricLabel(catalog, metric)}”: {num(count)} {metricLabel(catalog, denominator).toLowerCase()}.</p>
            ))}
          </caption>
        ) : null}
        <thead>
          <tr>
            {groups.map((g) => <th key={g} scope="col">{dimensionLabel(catalog, g)}</th>)}
            {metrics.map((m) => <th key={m} scope="col" className="num">{metricLabel(catalog, m)}</th>)}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {groups.map((g) => <td key={g}>{cell(row, g)}</td>)}
              {metrics.map((m) => <td key={m} className="num">{formatMetric(value(row, m), m, catalog)}</td>)}
            </tr>
          ))}
          {result.total ? (
            <tr className="total">
              {groups.length ? <th scope="row" colSpan={groups.length}>Total del universo consultado</th> : null}
              {metrics.map((m) => <td key={m} className="num">{formatMetric(value(result.total as Row, m), m, catalog)}</td>)}
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

export function Empty({ children }: { children?: ReactNode }) {
  return <p className="viz-empty">{children ?? "La consulta no devolvió filas: no hay informes que cumplan esos filtros y elegibilidad."}</p>;
}
