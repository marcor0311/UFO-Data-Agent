"use client";

/* Views for the measures of query_gold (histogram and ECDF of any measure, boxes, scatter)
   and for the analyses of the analyze tool (scripts/gold_analysis.py). Same contract as the
   other views: one idea per panel, pointer and keyboard detail, exact data under each chart. */

import { useId, useMemo, useState } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import type { Axis, Catalog, GoldResult, Row, Series } from "@/lib/contracts";
import { cell, compact, dimensionLabel, metricLabel, num } from "@/lib/format";
import { Empty, RAMP, metricsOf, niceMax, rampIndex, useTooltip, value } from "./shared";
import { GeoMap, borders, countries, toReports, useNearViewport } from "./maps";

type Props = { result: GoldResult; catalog: Catalog | null };
const COLORS = ["var(--series-1)", "var(--series-2)", "var(--seq-700)", "#8a6d1f", "#5b7f3a", "#7a4f8f", "var(--seq-400)", "var(--axis)"];

function share(part: number, whole: number, digits = 1): string {
  if (!whole) return "—";
  return `${(Math.round((part / whole) * 100 * 10 ** digits) / 10 ** digits).toLocaleString("es-ES")} %`;
}

const edgeText = (x: number) => x.toLocaleString("es-ES", { maximumFractionDigits: 2 });

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="viz-legend" aria-label="Leyenda">
      {items.map((item) => <li key={item.label}><span className="viz-legend-key" style={{ background: item.color }} />{item.label}</li>)}
    </ul>
  );
}

/* -- histogram of any measure, one panel per facet ------------------------------------ */
export function MeasureHistogram({ result }: { result: GoldResult; catalog?: Catalog | null }) {
  const { ref, show, hide, layer, width: measured } = useTooltip();
  const d = result.distribution;
  if (!d?.series?.length || !d.edges) return <Empty>No hay informes con un valor de esta medida.</Empty>;
  const edges = d.edges;
  const series = d.series as Series[];
  const width = series.length > 1 ? Math.max(320, Math.floor((measured - 12) / 2)) : measured;
  const left = 56, height = 220, pad = 30;
  const plot = width - left - 12;
  const n = edges.length; // bins + the tail
  const bw = plot / n;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Informes por tramos de {d.label?.toLowerCase()} ({d.unit})</figcaption>
        <div className={series.length > 1 ? "facets" : undefined}>
          {series.map((s, si) => {
            const bars = [...s.counts, s.over_max];
            const max = Math.max(1, ...bars);
            const sy = (v: number) => height - pad - (v / max) * (height - pad - 12);
            return (
              <div key={String(s.key)}>
                {s.label ? <div className="facet-title">{s.label}: {num(s.with_value)} con valor, {num(s.without_value)} sin valor</div> : null}
                <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Histograma de ${d.label?.toLowerCase()}${s.label ? `, ${s.label}` : ""}`}>
                  {[0, 0.5, 1].map((t) => (
                    <g key={t} aria-hidden="true">
                      <line x1={left} x2={width - 12} y1={sy(t * max)} y2={sy(t * max)} className="grid" />
                      <text x={left - 6} y={sy(t * max)} className="tick" textAnchor="end" dominantBaseline="middle">{compact(Math.round(t * max))}</text>
                    </g>
                  ))}
                  {bars.map((count, i) => {
                    const tail = i === bars.length - 1;
                    const title = tail ? `${edgeText(edges[edges.length - 1])} ${d.unit} o más` : `${edgeText(edges[i])}–${edgeText(edges[i + 1])} ${d.unit}`;
                    const lines = [{ value: num(count), label: `informes, ${share(count, s.with_value)} de los que tienen valor`, key: COLORS[si % COLORS.length] }];
                    const every = Math.max(1, Math.ceil(n / Math.floor(plot / 34)));
                    return (
                      <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${title}: ${num(count)} informes`}
                         onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                         onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                        <rect x={left + i * bw + 1} y={sy(count)} width={Math.max(1, bw - 2)} height={height - pad - sy(count)}
                              fill={tail ? "var(--surface-2)" : COLORS[si % COLORS.length]} stroke={tail ? "var(--axis)" : "none"} strokeDasharray={tail ? "3 2" : undefined} />
                        {i % every === 0 ? <text x={left + i * bw} y={height - 12} className="tick" textAnchor="start" aria-hidden="true">{tail ? `≥${edgeText(edges[i])}` : edgeText(edges[i])}</text> : null}
                      </g>
                    );
                  })}
                </svg>
              </div>
            );
          })}
        </div>
        <p className="viz-note">Eje: inicio de cada tramo, en {d.unit}. La barra punteada reúne los valores a partir del último tramo; los informes sin valor no se imputan.
          {series.some((s) => s.below_min) ? ` ${num(series.reduce((a, s) => a + s.below_min, 0))} informes quedan por debajo del primer tramo.` : ""}</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- cumulative distribution of any measure, one line per facet -------------------------- */
export function MeasureEcdf({ result }: { result: GoldResult; catalog?: Catalog | null }) {
  const { ref, show, hide, layer, width } = useTooltip();
  const groupId = useId();
  const d = result.distribution;
  const edges = d?.edges ?? [];
  const thresholds = d?.measure === "nuclear_distance" ? [10, 25, 50, 100, 250] : [1, 5, 15, 30, 60];
  const [threshold, setThreshold] = useState(thresholds[1]);
  if (!d?.series?.length || edges.length < 2) return <Empty>No hay informes con un valor de esta medida.</Empty>;
  const series = d.series as Series[];
  const top = edges[edges.length - 1];
  const left = 56, height = 260, pad = 28;
  const plot = width - left - 16;
  const sx = (x: number) => left + ((x - edges[0]) / (top - edges[0])) * plot;
  const sy = (v: number) => height - pad - v * (height - pad - 12);
  const curves = series.map((s) => {
    let running = 0;
    return s.counts.map((c, i) => { running += c; return { x: edges[i + 1], n: running, share: s.with_value ? running / s.with_value : 0 }; });
  });
  const at = (k: number) => curves[k].find((p) => p.x >= threshold) ?? curves[k][curves[k].length - 1];
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Porcentaje acumulado de informes hasta cada valor de {d.label?.toLowerCase()} ({d.unit})</figcaption>
        <div className="segmented" role="radiogroup" aria-labelledby={groupId}>
          <span id={groupId}>Umbral</span>
          {thresholds.map((t) => (
            <button key={t} type="button" role="radio" aria-checked={threshold === t} className="ghost" onClick={() => setThreshold(t)}>{t} {d.unit}</button>
          ))}
        </div>
        <ul className="ecdf-answer" aria-live="polite">
          {series.map((s, k) => (
            <li key={String(s.key)}><strong>{share(at(k).n, s.with_value)}</strong> {s.label ? `de ${s.label}` : "de los informes con valor"} hasta {threshold} {d.unit} ({num(at(k).n)} de {num(s.with_value)})</li>
          ))}
        </ul>
        {series.length > 1 ? <Legend items={series.map((s, k) => ({ label: s.label ?? "", color: COLORS[k % COLORS.length] }))} /> : null}
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Distribución acumulada de ${d.label?.toLowerCase()}`}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={left} x2={width - 16} y1={sy(t)} y2={sy(t)} className="grid" />
              <text x={left - 6} y={sy(t)} className="tick" textAnchor="end" dominantBaseline="middle">{t * 100} %</text>
            </g>
          ))}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const x = edges[0] + t * (top - edges[0]);
            return <text key={t} x={sx(x)} y={height - 8} className="tick" textAnchor="middle" aria-hidden="true">{edgeText(x)}</text>;
          })}
          {curves.map((points, k) => (
            <path key={k} d={`M${sx(edges[0])},${sy(0)}` + points.map((p) => `H${sx(p.x)}V${sy(p.share)}`).join("")} className="series" stroke={COLORS[k % COLORS.length]} />
          ))}
          <line x1={sx(Math.min(threshold, top))} x2={sx(Math.min(threshold, top))} y1={sy(0)} y2={sy(1)} stroke="var(--axis)" strokeDasharray="4 3" />
          {curves[0].map((p, i) => {
            const title = `Hasta ${edgeText(p.x)} ${d.unit}`;
            const lines = series.map((s, k) => ({ value: share(curves[k][i].n, s.with_value), label: s.label ?? "informes con valor", key: COLORS[k % COLORS.length] }));
            return (
              <rect key={i} x={sx(edges[i])} y={12} width={Math.max(1, sx(edges[i + 1]) - sx(edges[i]))} height={height - pad - 12} fill="transparent" className="mark"
                    role="img" tabIndex={-1} aria-label={`${title}: ${lines.map((l) => l.value).join(", ")}`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide} />
            );
          })}
        </svg>
        <p className="viz-note">Los valores por encima de {edgeText(top)} {d.unit} quedan fuera de la curva ({series.map((s) => num(s.over_max)).join(", ")} informes).</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- boxes of quantiles ------------------------------------------------------------------ */
type Box = { n: number; p05: number | null; p25: number | null; p50: number | null; p75: number | null; p95: number | null };

export function BoxplotView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  const metric = metricsOf(result, catalog)[0];
  const group = result.query.group_by[0];
  const rows = result.rows.filter((r) => (r as unknown as { box?: Box }).box?.n);
  if (!rows.length) return <Empty>No hay valores para calcular los cuantiles con esos filtros.</Empty>;
  const boxes = rows.map((r) => ({ row: r, box: (r as unknown as { box: Box }).box }));
  const lows = boxes.map((b) => b.box.p05 ?? 0), highs = boxes.map((b) => b.box.p95 ?? 0);
  const minPos = Math.min(...lows.filter((v) => v > 0), ...highs.filter((v) => v > 0));
  const hi = Math.max(...highs);
  const log = minPos > 0 && hi / minPos > 50;
  const lo = log ? Math.pow(10, Math.floor(Math.log10(minPos))) : Math.min(0, ...lows);
  const top = log ? Math.pow(10, Math.ceil(Math.log10(hi))) : niceMax(hi);
  const labelWidth = Math.min(200, Math.round(width * 0.28));
  const plot = width - labelWidth - 30;
  const sx = (v: number) => labelWidth + (log ? (Math.log10(Math.max(v, lo)) - Math.log10(lo)) / (Math.log10(top) - Math.log10(lo)) : (v - lo) / (top - lo)) * plot;
  const tickValues = log ? Array.from({ length: Math.round(Math.log10(top / lo)) + 1 }, (_, i) => lo * 10 ** i) : [0, 0.25, 0.5, 0.75, 1].map((t) => lo + t * (top - lo));
  const rowH = 28;
  const height = boxes.length * rowH + 30;
  const label = metricLabel(catalog, metric);
  const unit = catalog?.metrics[metric]?.unit ?? "";
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{label}: percentiles 5, 25, 50, 75 y 95{group ? ` por ${dimensionLabel(catalog, group).toLowerCase()}` : ""}</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Cajas de ${label.toLowerCase()}`}>
          {tickValues.map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={sx(t)} x2={sx(t)} y1={0} y2={height - 20} className="grid" />
              <text x={sx(t)} y={height - 6} className="tick" textAnchor="middle">{compact(t)}</text>
            </g>
          ))}
          {boxes.map(({ row, box }, i) => {
            const y = i * rowH + 6;
            const name = group ? cell(row, group) : "Todos";
            const title = `${name} (${num(box.n)} valores)`;
            const lines = [["p95", "percentil 95"], ["p75", "percentil 75"], ["p50", "mediana"], ["p25", "percentil 25"], ["p05", "percentil 5"]]
              .map(([k, l]) => ({ value: `${num(box[k as keyof Box] as number)} ${unit}`, label: l }));
            return (
              <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${title}: mediana ${num(box.p50)} ${unit}, del percentil 25 al 75 entre ${num(box.p25)} y ${num(box.p75)}`}
                 onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                 onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                <rect x={0} y={y - 2} width={width} height={rowH} fill="transparent" />
                <text x={labelWidth - 10} y={y + 10} className="cat" textAnchor="end" dominantBaseline="middle">{name}</text>
                <line x1={sx(box.p05 ?? 0)} x2={sx(box.p95 ?? 0)} y1={y + 10} y2={y + 10} stroke="var(--axis)" />
                <rect x={sx(box.p25 ?? 0)} y={y + 2} width={Math.max(2, sx(box.p75 ?? 0) - sx(box.p25 ?? 0))} height={16} rx={3} fill="color-mix(in srgb, var(--series-1) 35%, var(--surface))" stroke="var(--series-1)" />
                <line x1={sx(box.p50 ?? 0)} x2={sx(box.p50 ?? 0)} y1={y} y2={y + 20} stroke="var(--series-2)" strokeWidth={3} />
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Caja: percentiles 25 a 75; trazo naranja: mediana; línea: percentiles 5 a 95.{log ? " Escala logarítmica." : ""} Cuantiles por rango más cercano sobre los valores del grupo; un grupo pequeño da cuantiles poco estables.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- binned scatter (and K-means profiles) ------------------------------------------------ */
export function ScatterView({ result }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  const d = result.distribution;
  const x = (d?.x ?? result.analysis?.x) as Axis | undefined;
  const y = (d?.y ?? result.analysis?.y) as Axis | undefined;
  if (!x || !y || result.empty) return <Empty />;
  const profiles = result.analysis?.profiles as { cluster: number; reports: number; center_duration_min: number; center_witnesses: number }[] | undefined;
  const clustered = Boolean(profiles);
  const nx = x.edges.length, ny = y.edges.length; // bins + the tail
  const left = 70, bottom = 40, size = Math.max(14, Math.min(34, Math.floor((width - left - 10) / nx)));
  const height = ny * size + bottom + 6;
  const max = Math.max(1, ...result.rows.map((r) => value(r, "report_count") ?? 0));
  const tickOf = (axis: Axis, i: number) => i >= axis.edges.length - 1 ? `≥${edgeText(axis.edges[axis.edges.length - 1])}` : edgeText(axis.edges[i]);
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Informes por {x.label.toLowerCase()} ({x.unit}) y {y.label.toLowerCase()} ({y.unit}){clustered ? `, coloreados por perfil K-means (k = ${result.analysis?.k})` : ""}</figcaption>
        {clustered ? (
          <Legend items={profiles!.map((p) => ({ label: `Perfil ${p.cluster}: ${num(p.reports)} informes, centro ${num(p.center_duration_min)} min y ${num(p.center_witnesses)} testigos`, color: COLORS[(p.cluster - 1) % COLORS.length] }))} />
        ) : null}
        <svg viewBox={`0 0 ${left + nx * size + 10} ${height}`} style={{ maxWidth: left + nx * size + 10 }} role="group" aria-label={`Dispersión agregada de ${x.label} y ${y.label}`}>
          {Array.from({ length: nx }, (_, i) => i % 2 === 0 ? <text key={i} x={left + i * size} y={ny * size + 14} className="tick" textAnchor="start" aria-hidden="true">{tickOf(x, i)}</text> : null)}
          {Array.from({ length: ny }, (_, j) => <text key={j} x={left - 6} y={(ny - j - 1) * size + size / 2} className="tick" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{tickOf(y, j)}</text>)}
          <text x={left + (nx * size) / 2} y={height - 4} className="tick" textAnchor="middle" aria-hidden="true">{x.label} ({x.unit})</text>
          {result.rows.map((row, k) => {
            const bx = row.x_bin as number, by = row.y_bin as number;
            if (bx < 0 || by < 0) return null;
            const n = value(row, "report_count") ?? 0;
            const cluster = row.cluster as number | undefined;
            const fill = clustered && cluster ? `color-mix(in srgb, ${COLORS[(cluster - 1) % COLORS.length]} ${Math.round(25 + 75 * Math.log(n + 1) / Math.log(max + 1))}%, var(--surface))`
              : RAMP[Math.max(0, rampIndex(n, max, "log"))];
            const title = `${x.label}: ${row.x_to == null ? `≥${edgeText(row.x_from as number)}` : `${edgeText(row.x_from as number)}–${edgeText(row.x_to as number)}`} ${x.unit}; ${y.label}: ${row.y_to == null ? `≥${edgeText(row.y_from as number)}` : `${edgeText(row.y_from as number)}–${edgeText(row.y_to as number)}`} ${y.unit}`;
            const lines = [{ value: num(n), label: "informes" }, ...(cluster ? [{ value: `Perfil ${cluster}`, label: "mayoría de la celda", key: COLORS[(cluster - 1) % COLORS.length] }] : [])];
            return (
              <rect key={k} x={left + bx * size + 1} y={(ny - by - 1) * size + 1} width={size - 2} height={size - 2} rx={2} fill={fill} className="mark" role="img" tabIndex={0}
                    aria-label={`${title}: ${num(n)} informes`} onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                    onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
        </svg>
        <p className="viz-note">
          Eje vertical: {y.label.toLowerCase()} ({y.unit}). Cada celda cuenta informes con ambos valores; los tramos no son iguales para mostrar a la vez valores pequeños y grandes.
          {clustered ? ` Perfiles exploratorios sobre valores logarítmicos estandarizados; la asignación coincide en ${(result.analysis?.stability_pct as number[]).map((v) => `${num(v)} %`).join(" y ")} con otras dos semillas. No son tipos de fenómeno.` : ""}
        </p>
      </figure>
      {layer}
    </div>
  );
}

/* -- waterfall: contribution of each category to a change --------------------------------- */
export function WaterfallView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const meta = result.analysis as unknown as { total_from: number; total_to: number; total_change: number; from: number; to: number; period: string };
  const cat = result.query.group_by[0];
  const name = (p: number) => meta.period === "decade" ? `${p}s` : String(p);
  let running = meta.total_from;
  const steps = [{ label: `Total ${name(meta.from)}`, start: 0, end: meta.total_from, total: true, row: null as Row | null },
    ...result.rows.map((row) => { const start = running; running += value(row, "change") ?? 0; return { label: cell(row, cat), start, end: running, total: false, row }; }),
    { label: `Total ${name(meta.to)}`, start: 0, end: meta.total_to, total: true, row: null }];
  const max = niceMax(Math.max(...steps.map((s) => Math.max(s.start, s.end))));
  const labelWidth = Math.min(220, Math.round(width * 0.3));
  const chars = Math.floor(labelWidth / 7);
  const plot = width - labelWidth - 110;
  const sx = (v: number) => labelWidth + (v / max) * plot;
  const rowH = 26;
  const height = steps.length * rowH + 26;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>De {num(meta.total_from)} a {num(meta.total_to)} informes ({meta.total_change >= 0 ? "+" : "−"}{num(Math.abs(meta.total_change))}): aporte de cada {dimensionLabel(catalog, cat).toLowerCase()}</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Cascada del cambio de informes">
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={sx(t * max)} x2={sx(t * max)} y1={0} y2={height - 20} className="grid" />
              <text x={sx(t * max)} y={height - 6} className="tick" textAnchor="middle">{compact(t * max)}</text>
            </g>
          ))}
          {steps.map((s, i) => {
            const y = i * rowH + 4;
            const delta = s.end - s.start;
            const color = s.total ? "var(--seq-500)" : delta >= 0 ? "var(--series-2)" : "var(--series-1)";
            const text = s.total ? num(s.end) : `${delta >= 0 ? "+" : "−"}${num(Math.abs(delta))}`;
            const lines = s.row ? [{ value: text, label: metricLabel(catalog, "change"), key: color },
              { value: num(value(s.row, "count_from")), label: metricLabel(catalog, "count_from") }, { value: num(value(s.row, "count_to")), label: metricLabel(catalog, "count_to") }]
              : [{ value: text, label: "informes", key: color }];
            return (
              <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${s.label}: ${text}`}
                 onPointerMove={(e) => show(e, { title: s.label, lines })} onPointerLeave={hide}
                 onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title: s.label, lines })} onBlur={hide}>
                <rect x={0} y={y - 3} width={width} height={rowH} fill="transparent" />
                <text x={labelWidth - 10} y={y + 9} className="cat" textAnchor="end" dominantBaseline="middle">{s.label.length > chars ? s.label.slice(0, chars - 1) + "…" : s.label}</text>
                <rect x={sx(Math.min(s.start, s.end))} y={y} width={Math.max(2, Math.abs(sx(s.end) - sx(s.start)))} height={18} rx={3} fill={color} />
                <text x={sx(Math.max(s.start, s.end)) + 6} y={y + 9} className="val" dominantBaseline="middle">{text}</text>
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Naranja: suma informes; azul: resta. Las barras intermedias suman exactamente el cambio total.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- bump chart: ranks over time ---------------------------------------------------------- */
export function BumpView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  const [, dim] = result.query.group_by;
  const lines = useMemo(() => {
    const map = new Map<string, Row[]>();
    for (const row of result.rows) map.set(cell(row, dim), [...(map.get(cell(row, dim)) ?? []), row]);
    return [...map.entries()];
  }, [result.rows, dim]);
  if (result.empty) return <Empty />;
  const meta = result.analysis as unknown as { top: number; entered_labels: string[]; left_labels: string[] };
  const years = [...new Set(result.rows.map((r) => r.event_year as number))].sort((a, b) => a - b);
  const left = 34, right = 150, top = 12, height = meta.top * 26 + 40;
  const sx = (y: number) => left + ((y - years[0]) / Math.max(1, years[years.length - 1] - years[0])) * (width - left - right);
  const sy = (rank: number) => top + (rank - 1) * 26;
  const last = years[years.length - 1];
  const finalRank = (rows: Row[]) => (rows.find((r) => r.event_year === last)?.rank as number | null) ?? 99;
  const ordered = [...lines].sort((a, b) => finalRank(a[1]) - finalRank(b[1]));
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Posición en el top {meta.top} de {dimensionLabel(catalog, dim).toLowerCase()} por informes acumulados, {years[0]}–{last}</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Posiciones a lo largo de los años">
          {Array.from({ length: meta.top }, (_, i) => <text key={i} x={left - 8} y={sy(i + 1)} className="tick" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{i + 1}</text>)}
          {years.filter((_, i) => i % Math.ceil(years.length / 8) === 0).map((y) => <text key={y} x={sx(y)} y={height - 8} className="tick" textAnchor="middle" aria-hidden="true">{y}</text>)}
          {ordered.map(([key, rows], k) => {
            const pts = rows.filter((r) => typeof r.rank === "number").sort((a, b) => (a.event_year as number) - (b.event_year as number));
            const color = k < COLORS.length - 1 ? COLORS[k] : "var(--axis)";
            const d = pts.map((r, i) => {
              const gap = i > 0 && (r.event_year as number) - (pts[i - 1].event_year as number) > 1;
              return `${i === 0 || gap ? "M" : "L"}${sx(r.event_year as number).toFixed(1)},${sy(r.rank as number).toFixed(1)}`;
            }).join("");
            const end = pts[pts.length - 1];
            return (
              <g key={key} className="mark" role="img" tabIndex={0} aria-label={`${key}: ${end ? `posición ${end.rank} en ${end.event_year}` : "fuera del top"}`}
                 onPointerMove={(e) => show(e, { title: key, lines: pts.slice(-1).map((r) => ({ value: `#${r.rank}`, label: `en ${r.event_year}, ${num(r.reports as number)} informes`, key: color })) })}
                 onPointerLeave={hide}>
                <path d={d} fill="none" stroke={color} strokeWidth={k < 5 ? 2.5 : 1.5} opacity={k < 8 ? 1 : 0.5} />
                {end && end.event_year === last ? <text x={sx(last) + 6} y={sy(end.rank as number)} className="cat" dominantBaseline="middle" textAnchor="start">{key}</text> : null}
              </g>
            );
          })}
        </svg>
        <p className="viz-note">
          {meta.entered_labels.length ? `Entraron al top: ${meta.entered_labels.join(", ")}. ` : ""}{meta.left_labels.length ? `Salieron: ${meta.left_labels.join(", ")}. ` : ""}
          Una línea cortada sale del top esos años. La posición depende de la cobertura de las fuentes, no de la frecuencia real.
        </p>
      </figure>
      {layer}
    </div>
  );
}

/* -- concentration curve ------------------------------------------------------------------ */
export function CurveView({ result }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const meta = result.analysis as unknown as { cells: number; top1pct_cells: number; top1pct_share: number; resolution: number };
  const left = 56, height = 280, pad = 30;
  const plot = width - left - 16;
  const sx = (v: number) => left + (v / 100) * plot;
  const sy = (v: number) => height - pad - (v / 100) * (height - pad - 12);
  const d = result.rows.map((r, i) => `${i ? "L" : "M"}${sx(r.cell_share_pct as number).toFixed(1)},${sy(r.report_share_pct as number).toFixed(1)}`).join("");
  return (
    <div className="viz" ref={ref}>
      <p className="ecdf-answer"><strong>{num(meta.top1pct_share)} %</strong> de los informes con mapa cae en el 1 % de celdas de {meta.resolution}° más concurridas ({num(meta.top1pct_cells)} de {num(meta.cells)} celdas ocupadas).</p>
      <figure className="viz-panel">
        <figcaption>Porcentaje acumulado de informes según el porcentaje de celdas, de la más concurrida a la menos</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Curva de concentración de informes por celdas"
             onPointerMove={(e) => {
               const box = e.currentTarget.getBoundingClientRect();
               const v = (((e.clientX - box.left) / box.width) * width - left) / plot * 100;
               const p = result.rows.reduce((best, r) => Math.abs((r.cell_share_pct as number) - v) < Math.abs((best.cell_share_pct as number) - v) ? r : best, result.rows[0]);
               show(e, { title: `${num(p.cell_share_pct as number)} % de las celdas`, lines: [{ value: `${num(p.report_share_pct as number)} %`, label: "de los informes", key: "var(--series-1)" }] });
             }} onPointerLeave={hide}>
          {[0, 25, 50, 75, 100].map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={left} x2={width - 16} y1={sy(t)} y2={sy(t)} className="grid" />
              <text x={left - 6} y={sy(t)} className="tick" textAnchor="end" dominantBaseline="middle">{t} %</text>
              <text x={sx(t)} y={height - 8} className="tick" textAnchor="middle">{t} %</text>
            </g>
          ))}
          <line x1={sx(0)} y1={sy(0)} x2={sx(100)} y2={sy(100)} stroke="var(--axis)" strokeDasharray="4 3" />
          <path d={d} className="series" stroke="var(--series-1)" />
          <circle cx={sx(1)} cy={sy(meta.top1pct_share)} r={5} fill="var(--series-2)" className="dot" />
        </svg>
        <p className="viz-note">La diagonal punteada sería un reparto igual entre celdas. El punto naranja marca el 1 % de celdas más concurridas. Cuenta informes, no población ni área.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- spatio-temporal clusters on the 2D/3D map ---------------------------------------------- */
export function ClustersView({ result }: Props) {
  const { ref, near } = useNearViewport();
  const reports = useMemo(() => toReports(result.rows), [result.rows]);
  if (!reports.length) return <Empty>No se formaron agrupaciones con esos umbrales.</Empty>;
  const meta = result.analysis as unknown as { clusters: number; clustered_reports: number };
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{num(meta.clusters)} agrupaciones con {num(meta.clustered_reports)} informes; cada punto es el centro de una agrupación y crece con sus informes</figcaption>
        {near ? <GeoMap reports={reports} /> : <div className="geo-map-canvas geo-map-loading">Mapa</div>}
        <ol className="cluster-list">
          {result.rows.slice(0, 8).map((r) => (
            <li key={String(r.cluster_id)}>{num(r.report_count as number)} informes del {String(r.start_date)} al {String(r.end_date)}
              {typeof r.radius_km === "number" ? `, radio ${num(r.radius_km)} km` : r.cell ? `, celda ${r.cell}` : ""}{r.top_shape_label ? `, forma más frecuente: ${r.top_shape_label}` : ""}</li>
          ))}
        </ol>
      </figure>
    </div>
  );
}

/* -- links between cells and their nearest facility ------------------------------------------ */
export function LinksView({ result, catalog }: Props) {
  const { ref, show, hide, layer } = useTooltip();
  const W = 760, H = 420;
  const view = useMemo(() => {
    // Frame the links that carry most reports, so a few remote facilities do not shrink the map.
    const top = Math.max(1, ...result.rows.map((r) => value(r, "report_count") ?? 0));
    const framed = result.rows.filter((r) => (value(r, "report_count") ?? 0) >= top * 0.02);
    const coordinates = framed.flatMap((r) => [[r.cell_lng as number, r.cell_lat as number], [r.facility_lng as number, r.facility_lat as number]]);
    const projection = geoNaturalEarth1().fitExtent([[12, 12], [W - 12, H - 12]], { type: "MultiPoint", coordinates } as never);
    return { projection, path: geoPath(projection) };
  }, [result.rows]);
  if (result.empty) return <Empty />;
  const max = Math.max(1, ...result.rows.map((r) => value(r, "report_count") ?? 0));
  const facilities = new Map(result.rows.map((r) => [String(r.nearest_facility_key), r]));
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{num(result.rows.length)} celdas unidas con su instalación del catálogo más cercana; el grosor crece con los informes</figcaption>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mapa de enlaces entre celdas e instalaciones" style={{ overflow: "hidden" }}>
          {countries.features.map((f, i) => <path key={i} d={view.path(f) ?? ""} className="map-land" />)}
          <path d={view.path(borders) ?? ""} className="map-borders" />
          {result.rows.map((r, i) => {
            const a = view.projection([r.cell_lng as number, r.cell_lat as number]);
            const b = view.projection([r.facility_lng as number, r.facility_lat as number]);
            if (!a || !b) return null;
            const n = value(r, "report_count") ?? 0;
            const title = `${r.facility_name}: celda ${num(r.cell_lat as number)}°, ${num(r.cell_lng as number)}°`;
            const lines = [{ value: num(n), label: "informes" }, { value: `${num(r.avg_distance_km as number)} km`, label: metricLabel(catalog, "avg_distance_km") }];
            return (
              <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="var(--series-1)" strokeOpacity={0.55} strokeWidth={0.6 + 5 * Math.sqrt(n / max)}
                    className="mark" tabIndex={0} role="img" aria-label={`${title}: ${num(n)} informes`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide} onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
          {[...facilities.values()].map((r) => {
            const p = view.projection([r.facility_lng as number, r.facility_lat as number]);
            return p ? <rect key={String(r.nearest_facility_key)} x={p[0] - 4} y={p[1] - 4} width={8} height={8} fill="var(--series-2)" stroke="white" aria-hidden="true" /> : null;
          })}
        </svg>
        <p className="viz-note">Cuadrados naranjas: instalaciones del catálogo local. Proximidad no implica relación; la distancia es a la instalación más cercana del catálogo, no a todas.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- coverage funnel ------------------------------------------------------------------------ */
export function FunnelView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const by = result.query.group_by.length > 1 ? result.query.group_by[0] : null;
  const groups = new Map<string, Row[]>();
  for (const r of result.rows) groups.set(by ? cell(r, by) : "Todos", [...(groups.get(by ? cell(r, by) : "Todos") ?? []), r]);
  const stages = [...new Map(result.rows.map((r) => [String(r.stage), String(r.stage_label)])).entries()];
  const labelWidth = 150, plot = width - labelWidth - 80, barH = 16;
  return (
    <div className="viz" ref={ref}>
      <Legend items={stages.map(([, label], i) => ({ label, color: RAMP[Math.min(RAMP.length - 1, 2 + i)] }))} />
      {[...groups.entries()].map(([name, rows]) => {
        const all = value(rows[0], "report_count") ?? 0;
        const height = rows.length * (barH + 4) + 6;
        return (
          <figure className="viz-panel" key={name}>
            <figcaption>{name}: {num(all)} informes</figcaption>
            <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Embudo de cobertura de ${name}`}>
              {rows.map((r, i) => {
                const n = value(r, "report_count") ?? 0;
                const w = all ? (n / all) * plot : 0;
                const y = i * (barH + 4) + 2;
                const text = `${num(n)} (${num(value(r, "pct_of_all"))} %)`;
                return (
                  <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${r.stage_label}: ${text}`}
                     onPointerMove={(e) => show(e, { title: `${name}, ${r.stage_label}`, lines: [{ value: text, label: metricLabel(catalog, "report_count") }] })} onPointerLeave={hide}>
                    <text x={labelWidth - 8} y={y + barH / 2} className="cat" textAnchor="end" dominantBaseline="middle">{String(r.stage_label)}</text>
                    <rect x={labelWidth + (plot - w) / 2} y={y} width={Math.max(1, w)} height={barH} rx={3} fill={RAMP[Math.min(RAMP.length - 1, 2 + i)]} />
                    <text x={labelWidth + plot + 6} y={y + barH / 2} className="val" dominantBaseline="middle">{num(value(r, "pct_of_all"))} %</text>
                  </g>
                );
              })}
            </svg>
          </figure>
        );
      })}
      {by ? <p className="viz-note">Una fila por {dimensionLabel(catalog, by).toLowerCase()}. Cada etapa conserva los informes de la anterior que además tienen esa precisión.</p> : null}
      {layer}
    </div>
  );
}

/* -- UpSet: combinations of missing fields --------------------------------------------------- */
export function UpsetView({ result }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const meta = result.analysis as unknown as { field_labels: string[]; fields: { field: string; missing_reports: number }[] };
  const fields = meta.field_labels;
  const max = Math.max(1, ...result.rows.map((r) => value(r, "report_count") ?? 0));
  const colW = Math.max(26, Math.min(44, Math.floor((width - 120) / result.rows.length)));
  const left = 110, barTop = 18, barH = 150, dotTop = barTop + barH + 14, row = 22;
  const height = dotTop + fields.length * row + 10;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Combinaciones más frecuentes de datos faltantes (cada informe cuenta en una sola)</figcaption>
        <svg viewBox={`0 0 ${left + result.rows.length * colW + 10} ${height}`} style={{ maxWidth: left + result.rows.length * colW + 10 }} role="group" aria-label="Combinaciones de datos faltantes">
          {fields.map((f, j) => (
            <g key={f} aria-hidden="true">
              <text x={left - 8} y={dotTop + j * row} className="cat" textAnchor="end" dominantBaseline="middle">{f}</text>
            </g>
          ))}
          {result.rows.map((r, i) => {
            const n = value(r, "report_count") ?? 0;
            const h = (n / max) * barH;
            const x = left + i * colW + colW / 2;
            const missing = r.missing as unknown as string[];
            const title = String(r.combination);
            const lines = [{ value: num(n), label: `informes (${num(value(r, "pct"))} %)` }, { value: missing.length ? `Faltan ${missing.length}` : "Completo", label: missing.join(", ") }];
            return (
              <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${title}: ${num(n)} informes`}
                 onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide} onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                <rect x={x - colW / 2 + 3} y={barTop + barH - h} width={colW - 6} height={h} rx={2} fill="var(--series-1)" />
                <text x={x} y={barTop + barH - h - 4} className="val" textAnchor="middle">{compact(n)}</text>
                <line x1={x} x2={x} y1={dotTop + Math.min(...fields.map((f, j) => missing.includes(f) ? j : 99)) * row}
                      y2={dotTop + Math.max(...fields.map((f, j) => missing.includes(f) ? j : -1)) * row} stroke="var(--series-2)" strokeWidth={2} opacity={missing.length > 1 ? 1 : 0} />
                {fields.map((f, j) => (
                  <circle key={f} cx={x} cy={dotTop + j * row} r={6} fill={missing.includes(f) ? "var(--series-2)" : "var(--surface-2)"} stroke="var(--axis)" strokeWidth={0.5} />
                ))}
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Punto naranja: el dato falta. Totales por campo: {meta.fields.map((f) => `${f.field.toLowerCase()} ${compact(f.missing_reports)}`).join(", ")}. Forma desconocida, duración cero y cero testigos cuentan como faltantes.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- two report cards, field by field -------------------------------------------------------- */
export function CompareView({ result }: Props) {
  if (result.empty) return <Empty />;
  const meta = result.analysis as unknown as { report_ids: number[]; same_fields: number; compared_fields: number; candidate_pair: { match_method: string; similarity_score: number; decision: string } | null };
  const [a, b] = meta.report_ids;
  const show = (v: unknown) => v === null || v === undefined ? "—" : typeof v === "number" ? num(v) : String(v);
  return (
    <div className="viz">
      <figure className="viz-panel">
        <figcaption>Informes {a} y {b}: coinciden en {meta.same_fields} de {meta.compared_fields} campos con valor en ambos
          {meta.candidate_pair ? `; Silver los propuso como par (${meta.candidate_pair.match_method}, similitud ${num(meta.candidate_pair.similarity_score)}, por revisar)` : "; no forman un par candidato en Silver"}</figcaption>
        <div className="viz-table-wrap">
          <table className="viz-table compare-table">
            <thead><tr><th scope="col">Campo</th><th scope="col">Informe {a}</th><th scope="col">Informe {b}</th><th scope="col">¿Coincide?</th></tr></thead>
            <tbody>
              {result.rows.map((r) => (
                <tr key={String(r.field)} className={r.same === true ? "same" : r.same === false ? "differs" : undefined}>
                  <th scope="row">{String(r.field_label)}{r.model_output ? " (modelo)" : ""}</th>
                  <td>{show(r.a_label)}</td>
                  <td>{show(r.b_label)}</td>
                  <td>{r.same === null ? "sin dato" : r.same ? "sí" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="viz-note">Coincidir en campos no prueba que sean el mismo evento. Las puntuaciones de modelo son salidas heredadas del origen.</p>
      </figure>
    </div>
  );
}

