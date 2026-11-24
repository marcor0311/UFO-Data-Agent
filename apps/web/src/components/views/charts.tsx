"use client";

import { useId, useMemo, useState, type KeyboardEvent } from "react";
import type React from "react";
import type { Catalog, GoldResult, Row } from "@/lib/contracts";
import { cell, compact, metricLabel, num } from "@/lib/format";
import {
  DataTable, Empty, RAMP, formatMetric, groupLabel, metricsOf, niceMax, rampIndex, rampLegend, ticks, useTooltip, value, yearTicks,
} from "./shared";

type Props = { result: GoldResult; catalog: Catalog | null };

/* -- table & stat cards ------------------------------------------------- */
export function TableView({ result, catalog }: Props) {
  if (result.empty) return <Empty />;
  const grouped = result.query.group_by.length > 0;
  if (!grouped && result.query.metrics.length && result.rows.length === 1) {
    const row = result.rows[0];
    return (
      <div className="stat-grid">
        {metricsOf(result, catalog).map((m) => (
          <div className="stat" key={m}>
            <div className="stat-label">{metricLabel(catalog, m)}</div>
            <div className="stat-value">{formatMetric(value(row, m), m, catalog)}</div>
          </div>
        ))}
      </div>
    );
  }
  return <DataTable result={result} catalog={catalog} />;
}

/* -- bars: one panel per metric, horizontal ------------------------------- */
const BAR = 18;
const GAP = 10;

export function BarsView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const groups = result.query.group_by;
  return (
    <div className="viz" ref={ref}>
      {metricsOf(result, catalog).map((metric) => {
        const max = niceMax(Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0)));
        const labelWidth = Math.min(240, Math.round(width * 0.3));
        const plot = width - labelWidth - 140;
        const chars = Math.floor(labelWidth / 7);
        const height = result.rows.length * (BAR + GAP) + 26;
        return (
          <figure className="viz-panel" key={metric}>
            <figcaption>{metricLabel(catalog, metric)}</figcaption>
            <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${metricLabel(catalog, metric)} por ${groups.join(", ")}`}>
              {ticks(max).map((t) => {
                const x = labelWidth + (t / max) * plot;
                return (
                  <g key={t}>
                    <line x1={x} x2={x} y1={0} y2={height - 20} className="grid" />
                    <text x={x} y={height - 6} className="tick" textAnchor="middle">{compact(t)}</text>
                  </g>
                );
              })}
              {result.rows.map((row, i) => {
                const y = i * (BAR + GAP) + 4;
                const v = value(row, metric) ?? 0;
                const w = Math.max(0, (v / max) * plot);
                const label = groupLabel(row, groups);
                const text = formatMetric(value(row, metric), metric, catalog);
                const lines = [{ value: text, label: metricLabel(catalog, metric), key: "var(--series-1)" }];
                return (
                  <g key={i} className="mark" role="img" tabIndex={0} aria-label={`${label}: ${text}`}
                     onPointerMove={(e) => show(e, { title: label, lines })} onPointerLeave={hide}
                     onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title: label, lines })} onBlur={hide}>
                    <rect x={0} y={y - GAP / 2} width={width} height={BAR + GAP} fill="transparent" />
                    <text x={labelWidth - 10} y={y + BAR / 2} className="cat" textAnchor="end" dominantBaseline="middle">
                      {label.length > chars ? label.slice(0, chars - 1) + "…" : label}
                    </text>
                    <path d={barPath(labelWidth, y, w, BAR)} fill="var(--series-1)" />
                    <text x={labelWidth + w + 6} y={y + BAR / 2} className="val" dominantBaseline="middle">{text}</text>
                  </g>
                );
              })}
            </svg>
          </figure>
        );
      })}
      {layer}
    </div>
  );
}

/** Bar with a 4px rounded data end and a square baseline. */
function barPath(x: number, y: number, w: number, h: number): string {
  if (w <= 0) return "";
  const r = Math.min(4, w, h / 2);
  return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
}

/* -- time series --------------------------------------------------------- */
function timeValue(raw: unknown): number | null {
  if (typeof raw === "number") return raw;
  if (typeof raw !== "string") return null;
  const [y, m, d] = raw.split("-").map(Number);
  if (!Number.isFinite(y)) return null;
  if (!m) return y;
  if (!d) return y + (m - 1) / 12;
  return y + (m - 1) / 12 + (d - 1) / 365;
}

export function TimeseriesView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width: measured } = useTooltip();
  const [hover, setHover] = useState<number | null>(null);
  const time = result.query.group_by[0];
  const facet = result.query.group_by[1];
  const facets = useMemo(() => {
    if (!facet) return [{ key: "", label: "", rows: result.rows }];
    const map = new Map<string, Row[]>();
    for (const row of result.rows) {
      const key = cell(row, facet);
      map.set(key, [...(map.get(key) ?? []), row]);
    }
    return [...map.entries()].slice(0, 6).map(([key, rows]) => ({ key, label: key, rows }));
  }, [result.rows, facet]);
  if (result.empty) return <Empty />;
  const xs = result.rows.map((r) => timeValue(r[time])).filter((v): v is number => v !== null);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const width = facets.length > 1 ? Math.max(320, Math.floor((measured - 12) / 2)) : measured;
  const height = 240;
  const pad = { l: 56, r: 16, t: 12, b: 28 };
  const sx = (v: number) => pad.l + (x1 === x0 ? 0.5 : (v - x0) / (x1 - x0)) * (width - pad.l - pad.r);
  const xticks = yearTicks(x0, x1, Math.max(3, Math.floor(width / 110)));
  return (
    <div className="viz" ref={ref}>
      {metricsOf(result, catalog).map((metric) => {
        const max = niceMax(Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0)));
        const sy = (v: number) => height - pad.b - (v / max) * (height - pad.t - pad.b);
        return (
          <figure className="viz-panel" key={metric}>
            <figcaption>{metricLabel(catalog, metric)}</figcaption>
            <div className={facets.length > 1 ? "facets" : undefined}>
              {facets.map((f) => {
                const points = f.rows.map((row) => ({ row, x: timeValue(row[time]) })).filter((p): p is { row: Row; x: number } => p.x !== null)
                  .sort((a, b) => a.x - b.x);
                const path = (m: string) => points.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(value(p.row, m) ?? 0).toFixed(1)}`).join("");
                const nearest = (clientX: number, svg: SVGSVGElement) => {
                  const box = svg.getBoundingClientRect();
                  const vx = ((clientX - box.left) / box.width) * width;
                  return points.reduce((best, p, i) => Math.abs(sx(p.x) - vx) < Math.abs(sx(points[best].x) - vx) ? i : best, 0);
                };
                return (
                  <div key={f.key}>
                    {f.label ? <div className="facet-title">{f.label}</div> : null}
                    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${metricLabel(catalog, metric)} en el tiempo ${f.label}`}
                         onPointerMove={(e) => {
                           const i = nearest(e.clientX, e.currentTarget);
                           setHover(i);
                           const p = points[i];
                           const lines = [{ value: formatMetric(value(p.row, metric), metric, catalog), label: metricLabel(catalog, metric), key: "var(--series-1)" }];
                           show(e, { title: cell(p.row, time) + (f.label ? ", " + f.label : ""), lines });
                         }}
                         onPointerLeave={() => { setHover(null); hide(); }}>
                      {ticks(max).map((t) => (
                        <g key={t}>
                          <line x1={pad.l} x2={width - pad.r} y1={sy(t)} y2={sy(t)} className="grid" />
                          <text x={pad.l - 8} y={sy(t)} className="tick" textAnchor="end" dominantBaseline="middle">{compact(t)}</text>
                        </g>
                      ))}
                      {xticks.map((t, i) => (
                        <text key={i} x={sx(t)} y={height - 8} className="tick" textAnchor="middle">{t}</text>
                      ))}
                      <line x1={pad.l} x2={width - pad.r} y1={sy(0)} y2={sy(0)} className="axis" />
                      <path d={path(metric)} className="series" stroke="var(--series-1)" />
                      {hover !== null && points[hover] ? (
                        <g>
                          <line x1={sx(points[hover].x)} x2={sx(points[hover].x)} y1={pad.t} y2={height - pad.b} className="crosshair" />
                          <circle cx={sx(points[hover].x)} cy={sy(value(points[hover].row, metric) ?? 0)} r={4} className="dot" fill="var(--series-1)" />
                        </g>
                      ) : null}
                    </svg>
                  </div>
                );
              })}
            </div>
          </figure>
        );
      })}
      {facet && new Set(result.rows.map((r) => cell(r, facet))).size > 6 ? <p className="viz-note">Se muestran las 6 primeras categorías; el resto está en los datos exactos.</p> : null}
      {layer}
    </div>
  );
}

/* -- weekday × hour matrix ------------------------------------------------ */
const DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

export function HourWeekdayView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width: measured } = useTooltip();
  const missingId = useId();
  const [activeCell, setActiveCell] = useState(0);
  if (result.empty) return <Empty />;
  const metric = metricsOf(result, catalog)[0];
  const grid = new Map(result.rows.map((r) => [`${r.weekday}-${r.event_hour}`, r]));
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  const left = 82;
  const size = Math.max(16, Math.min(36, Math.floor((measured - left - 8) / 24)));
  const width = left + 24 * size + 8;
  const height = 7 * size + 30;

  function moveCell(event: KeyboardEvent<SVGRectElement>, day: number, hour: number) {
    let nextDay = day, nextHour = hour;
    switch (event.key) {
      case "ArrowLeft": nextHour = Math.max(0, hour - 1); break;
      case "ArrowRight": nextHour = Math.min(23, hour + 1); break;
      case "ArrowUp": nextDay = Math.max(0, day - 1); break;
      case "ArrowDown": nextDay = Math.min(6, day + 1); break;
      case "Home": nextHour = 0; if (event.ctrlKey || event.metaKey) nextDay = 0; break;
      case "End": nextHour = 23; if (event.ctrlKey || event.metaKey) nextDay = 6; break;
      default: return;
    }
    event.preventDefault();
    event.currentTarget.ownerSVGElement?.querySelector<SVGRectElement>(
      `[data-weekday="${nextDay + 1}"][data-hour="${nextHour}"]`,
    )?.focus();
  }

  return (
    <div className="viz hour-weekday" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{metricLabel(catalog, metric)} por día de la semana y hora local declarada</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width }} role="grid" aria-readonly="true" aria-rowcount={7} aria-colcount={24}
             aria-describedby={`${missingId}-help`}
             aria-label={`Matriz de ${metricLabel(catalog, metric).toLowerCase()} por día de la semana y hora local declarada`}>
          <defs>
            <pattern id={missingId} width={6} height={6} patternUnits="userSpaceOnUse">
              <rect width={6} height={6} fill="var(--surface-2)" />
              <path d="M-1 1L1 -1M0 6L6 0M5 7L7 5" stroke="var(--axis)" strokeWidth={1} />
            </pattern>
          </defs>
          {Array.from({ length: 24 }, (_, h) => h % 3 === 0 ? (
            <text key={h} x={left + h * size + size / 2} y={height - 8} className="tick" textAnchor="middle" aria-hidden="true">{h}h</text>
          ) : null)}
          {DAYS.map((day, d) => (
            <g key={day} role="row" aria-rowindex={d + 1} aria-label={day}>
              <text x={left - 8} y={d * size + size / 2 + 2} className="cat" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{day}</text>
              {Array.from({ length: 24 }, (_, h) => {
                const row = grid.get(`${d + 1}-${h}`);
                const v = row ? value(row, metric) : null;
                const i = v === null ? -1 : rampIndex(v, max, "linear");
                const text = !row ? "Sin fila en este resultado" : v === null ? "Sin valor disponible" : formatMetric(v, metric, catalog);
                const lines = [{ value: text, label: metricLabel(catalog, metric) }];
                const title = `${day}, ${h}:00–${h}:59`;
                return (
                  <rect key={h} x={left + h * size + 1} y={d * size + 1} width={size - 2} height={size - 2} rx={3}
                        fill={v === null ? `url(#${missingId})` : i < 0 ? "var(--empty-cell)" : RAMP[i]}
                        className="mark" role="gridcell" aria-colindex={h + 1} data-weekday={d + 1} data-hour={h}
                        tabIndex={activeCell === d * 24 + h ? 0 : -1} aria-label={`${title}: ${text}`}
                        onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                        onFocus={(e) => { setActiveCell(d * 24 + h); show(e.currentTarget.getBoundingClientRect(), { title, lines }); }}
                        onKeyDown={(e) => moveCell(e, d, h)} onBlur={hide} />
                );
              })}
            </g>
          ))}
        </svg>
        <RampLegend max={max} scale="linear" missing note="escala lineal de informes (todos los informes)" />
        <p className="viz-note" id={`${missingId}-help`}>Las celdas rayadas no tienen fila o valor en este resultado; no equivalen a cero. Usa las flechas para recorrer los días y las horas.</p>
      </figure>
      {layer}
    </div>
  );
}

export function RampLegend({ max, note, scale = "log", missing = false }: { max: number; note?: string; scale?: "log" | "linear"; missing?: boolean }) {
  return (
    <div className="ramp-legend" aria-label="Escala">
      <span className="ramp-cell" style={{ background: "var(--empty-cell)" }} /><span>0</span>
      {missing ? <span className="ramp-step"><span className="ramp-cell missing-cell" aria-hidden="true" /><span>Sin fila o valor en este resultado</span></span> : null}
      {rampLegend(max, scale).map((s, i) => (
        <span key={i} className="ramp-step"><span className="ramp-cell" style={{ background: s.color }} /><span>{compact(s.from)}+</span></span>
      ))}
      <span className="ramp-note">{note ?? "escala logarítmica de informes (todos los informes)"}</span>
    </div>
  );
}

/* -- year × month calendar ------------------------------------------------ */
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

/* Years requested by the query filters, so a year without rows still gets its (missing) row. */
function calendarYears(result: GoldResult): number[] {
  let low: number | null = null, high: number | null = null;
  for (const f of result.query.filters) {
    if (f.column !== "event_year") continue;
    const values = (Array.isArray(f.value) ? f.value : [f.value]).filter((v): v is number => typeof v === "number");
    if (!values.length) continue;
    const op = f.op ?? "eq";
    if (op === "eq" || op === "in") { low = Math.max(low ?? -Infinity, Math.min(...values)); high = Math.min(high ?? Infinity, Math.max(...values)); }
    else if (op === "gte") low = Math.max(low ?? -Infinity, values[0]);
    else if (op === "lte") high = Math.min(high ?? Infinity, values[0]);
  }
  const seen = result.rows.map((r) => r.event_year).filter((v): v is number => typeof v === "number");
  low ??= seen.length ? Math.min(...seen) : null;
  high ??= seen.length ? Math.max(...seen) : null;
  if (low === null || high === null || high < low || high - low > 60) return [...new Set(seen)].sort((a, b) => a - b);
  return Array.from({ length: high - low + 1 }, (_, i) => low! + i);
}

export function MonthCalendarView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width: measured } = useTooltip();
  const missingId = useId();
  const [activeCell, setActiveCell] = useState(0);
  const years = useMemo(() => calendarYears(result), [result]);
  if (result.empty || !years.length) return <Empty />;
  const metric = metricsOf(result, catalog)[0];
  const monthly = result.rows.filter((r) => r.event_month !== null && r.event_month !== undefined);
  const grid = new Map(monthly.map((r) => [`${r.event_year}-${r.event_month}`, r]));
  const unknown = new Map(result.rows.filter((r) => r.event_month === null).map((r) => [r.event_year as number, r]));
  const hasUnknown = unknown.size > 0;
  const max = Math.max(0, ...monthly.map((r) => value(r, metric) ?? 0));
  const label = metricLabel(catalog, metric);
  const totals = result.calendar_totals;
  const left = 52;
  const extra = hasUnknown ? 2 : 0;                  // “Sin mes” and “Total” columns
  const gap = hasUnknown ? 14 : 0;
  const size = Math.max(18, Math.min(40, Math.floor((measured - left - gap - 8) / (12 + extra * 1.6))));
  const wide = Math.round(size * 1.6);
  const rowHeight = Math.max(16, Math.min(size, 26));
  const xOf = (col: number) => col < 12 ? left + col * size : left + 12 * size + gap + (col - 12) * wide;
  const wOf = (col: number) => col < 12 ? size : wide;
  const width = xOf(12 + extra) + 8;
  const height = 22 + years.length * rowHeight;
  const lastCol = 11 + extra;

  function moveCell(event: KeyboardEvent<SVGRectElement>, y: number, c: number) {
    let nextY = y, nextC = c;
    switch (event.key) {
      case "ArrowLeft": nextC = Math.max(0, c - 1); break;
      case "ArrowRight": nextC = Math.min(lastCol, c + 1); break;
      case "ArrowUp": nextY = Math.max(0, y - 1); break;
      case "ArrowDown": nextY = Math.min(years.length - 1, y + 1); break;
      case "Home": nextC = 0; if (event.ctrlKey || event.metaKey) nextY = 0; break;
      case "End": nextC = lastCol; if (event.ctrlKey || event.metaKey) nextY = years.length - 1; break;
      default: return;
    }
    event.preventDefault();
    event.currentTarget.ownerSVGElement?.querySelector<SVGRectElement>(`[data-year="${years[nextY]}"][data-col="${nextC}"]`)?.focus();
  }

  function cellProps(year: number, y: number, c: number, title: string, text: string) {
    const lines = [{ value: text, label }];
    const index = y * (lastCol + 1) + c;
    return {
      x: xOf(c) + 1, y: 22 + y * rowHeight + 1, width: wOf(c) - 2, height: rowHeight - 2, rx: 3,
      role: "gridcell", "aria-colindex": c + 1, "data-year": year, "data-col": c,
      tabIndex: activeCell === index ? 0 : -1, "aria-label": `${title}: ${text}`,
      onPointerMove: (e: React.PointerEvent) => show(e, { title, lines }), onPointerLeave: hide,
      onFocus: (e: React.FocusEvent<SVGRectElement>) => { setActiveCell(index); show(e.currentTarget.getBoundingClientRect(), { title, lines }); },
      onKeyDown: (e: KeyboardEvent<SVGRectElement>) => moveCell(e, y, c), onBlur: hide,
    };
  }

  return (
    <div className="viz hour-weekday month-calendar" ref={ref}>
      {totals ? (
        <div className="stat-grid calendar-totals">
          <div className="stat">
            <div className="stat-label">Informes en el período</div>
            <div className="stat-value">{num(totals.reports)}</div>
            <div className="stat-note">{years[0]}{years.length > 1 ? `–${years[years.length - 1]}` : ""}, con año conocido</div>
          </div>
          <div className="stat">
            <div className="stat-label">Con mes conocido</div>
            <div className="stat-value">{num(totals.with_month)}</div>
            <div className="stat-note">{share(totals.with_month, totals.reports)} del período, en el calendario</div>
          </div>
          <div className="stat stat-unknown">
            <div className="stat-label">Mes desconocido</div>
            <div className="stat-value">{num(totals.without_month)}</div>
            <div className="stat-note">{share(totals.without_month, totals.reports)} del período, no se puede calcular su mes</div>
          </div>
        </div>
      ) : null}
      <figure className="viz-panel">
        <figcaption>{label} por año y mes ({years[0]}{years.length > 1 ? `–${years[years.length - 1]}` : ""})</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width }} role="grid" aria-readonly="true"
             aria-rowcount={years.length} aria-colcount={lastCol + 1} aria-describedby={`${missingId}-help`}
             aria-label={`Calendario de ${label.toLowerCase()} por año y mes`}>
          <defs>
            <pattern id={missingId} width={6} height={6} patternUnits="userSpaceOnUse">
              <rect width={6} height={6} fill="var(--surface-2)" />
              <path d="M-1 1L1 -1M0 6L6 0M5 7L7 5" stroke="var(--axis)" strokeWidth={1} />
            </pattern>
          </defs>
          {[...MONTHS, ...(hasUnknown ? ["sin mes", "total"] : [])].map((m, i) => (
            <text key={m} x={xOf(i) + wOf(i) / 2} y={12} className="tick" textAnchor="middle" aria-hidden="true">{m}</text>
          ))}
          {hasUnknown ? <line x1={xOf(12) - gap / 2} x2={xOf(12) - gap / 2} y1={18} y2={height} className="calendar-divider" aria-hidden="true" /> : null}
          {years.map((year, y) => {
            const unknownRow = unknown.get(year);
            const unknownValue = unknownRow ? value(unknownRow, metric) : null;
            const known = MONTHS.reduce((sum, _, m) => sum + (value(grid.get(`${year}-${m + 1}`) ?? {}, metric) ?? 0), 0);
            const yearTotal = unknownValue === null ? null : known + unknownValue;
            const cy = 22 + y * rowHeight + rowHeight / 2;
            return (
              <g key={year} role="row" aria-rowindex={y + 1} aria-label={String(year)}>
                <text x={left - 8} y={cy} className="cat" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{year}</text>
                {MONTHS.map((_, m) => {
                  const row = grid.get(`${year}-${m + 1}`);
                  const v = row ? value(row, metric) : null;
                  const i = v === null ? -1 : rampIndex(v, max, "linear");
                  const text = !row ? "Sin fila en este resultado" : v === null ? "Sin valor disponible" : formatMetric(v, metric, catalog);
                  return <rect key={m} className="mark" fill={v === null ? `url(#${missingId})` : i < 0 ? "var(--empty-cell)" : RAMP[i]}
                               {...cellProps(year, y, m, `${MONTH_NAMES[m]} de ${year}`, text)} />;
                })}
                {hasUnknown ? (
                  <>
                    <rect className="mark calendar-unknown" {...cellProps(year, y, 12, `Mes desconocido en ${year}`,
                      unknownValue === null ? "Sin valor disponible" : `${formatMetric(unknownValue, metric, catalog)} (no se puede calcular su mes)`)} />
                    <text x={xOf(12) + wide / 2} y={cy} className="calendar-figure" textAnchor="middle" dominantBaseline="middle" aria-hidden="true">
                      {unknownValue === null ? "—" : compact(unknownValue)}
                    </text>
                    <rect className="mark calendar-total" {...cellProps(year, y, 13, `Total de ${year}`,
                      yearTotal === null ? "Sin valor disponible" : formatMetric(yearTotal, metric, catalog))} />
                    <text x={xOf(13) + wide / 2} y={cy} className="calendar-figure calendar-figure-total" textAnchor="middle" dominantBaseline="middle" aria-hidden="true">
                      {yearTotal === null ? "—" : compact(yearTotal)}
                    </text>
                  </>
                ) : null}
              </g>
            );
          })}
        </svg>
        <RampLegend max={max} scale="linear" missing note="escala lineal de informes por mes" />
        <p className="viz-note" id={`${missingId}-help`}>
          Las celdas rayadas no tienen fila o valor en este resultado; no equivalen a cero.
          {hasUnknown ? " “Sin mes” cuenta los informes del año cuyo mes no se puede calcular (solo consignan el año, fecha aproximada o marcador de día); no se reparten entre los meses. “Total” suma ambos." : ""}
          {" "}Usa las flechas para recorrer los años y los meses.
        </p>
      </figure>
      {layer}
    </div>
  );
}

function share(part: number, whole: number): string {
  return whole ? `${(Math.round((part / whole) * 1000) / 10).toLocaleString("es-ES")} %` : "—";
}
