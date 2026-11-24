"use client";

/* Views recovered from propuesta-graficos/: composition, matrix, period change,
   chronology, report comparison and duration distribution. Same contract as the
   other views: one metric per panel, keyboard + pointer detail, exact data below. */

import { useId, useState, type KeyboardEvent } from "react";
import type { Catalog, GoldResult, Row } from "@/lib/contracts";
import { cell, compact, dimensionLabel, metricLabel, num } from "@/lib/format";
import { Empty, RAMP, formatMetric, metricsOf, niceMax, rampIndex, useTooltip, value } from "./shared";
import { RampLegend } from "./charts";

type Props = { result: GoldResult; catalog: Catalog | null };

/* Categorical palette: two validated series first, then neutral steps of the sequential ramp. */
const CATEGORY_COLORS = ["var(--series-1)", "var(--series-2)", "var(--seq-700)", "var(--seq-300)", "#8a6d1f", "#5b7f3a", "#7a4f8f", "var(--axis)"];

function pct(part: number, whole: number, digits = 1): string {
  if (!whole) return "—";
  return `${(Math.round((part / whole) * 100 * 10 ** digits) / 10 ** digits).toLocaleString("es-ES")} %`;
}

/** Group rows by the first dimension, keeping server order. */
function byFirst(rows: Row[], first: string): [string, Row[]][] {
  const map = new Map<string, Row[]>();
  for (const row of rows) {
    const key = cell(row, first);
    map.set(key, [...(map.get(key) ?? []), row]);
  }
  return [...map.entries()];
}

/** Categories of the second dimension, largest overall first; the tail folds into “Otras”. */
function categories(rows: Row[], second: string, metric: string, keep: number): { keys: string[]; other: boolean } {
  const totals = new Map<string, number>();
  for (const row of rows) totals.set(cell(row, second), (totals.get(cell(row, second)) ?? 0) + (value(row, metric) ?? 0));
  const sorted = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
  return sorted.length > keep ? { keys: sorted.slice(0, keep - 1), other: true } : { keys: sorted, other: false };
}

function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="viz-legend" aria-label="Leyenda">
      {items.map((item) => (
        <li key={item.label}><span className={item.dashed ? "viz-legend-key dashed" : "viz-legend-key"} style={{ background: item.color }} />{item.label}</li>
      ))}
    </ul>
  );
}

/* -- 100 % stacked composition ----------------------------------------------------- */
export function StackedView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const [first, second] = result.query.group_by;
  const metric = metricsOf(result, catalog)[0];
  const { keys, other } = categories(result.rows, second, metric, CATEGORY_COLORS.length);
  const series = [...keys, ...(other ? ["Otras"] : [])];
  const color = (k: string) => k === "Otras" ? "var(--axis)" : CATEGORY_COLORS[keys.indexOf(k)];
  const groups = byFirst(result.rows, first);
  const label = metricLabel(catalog, metric);
  const left = 64, right = 72, bar = 22, gap = 8;
  const plot = width - left - right;
  const height = groups.length * (bar + gap) + 24;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Composición de {label.toLowerCase()} por {dimensionLabel(catalog, second).toLowerCase()} en cada {dimensionLabel(catalog, first).toLowerCase()}</figcaption>
        <Legend items={series.map((k) => ({ label: k, color: color(k) }))} />
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Barras apiladas al 100 % de ${label.toLowerCase()}`}>
          {[0, 25, 50, 75, 100].map((t) => {
            const x = left + (t / 100) * plot;
            return (
              <g key={t} aria-hidden="true">
                <line x1={x} x2={x} y1={0} y2={height - 20} className="grid" />
                <text x={x} y={height - 6} className="tick" textAnchor="middle">{t} %</text>
              </g>
            );
          })}
          {groups.map(([group, rows], i) => {
            const y = i * (bar + gap) + 2;
            const parts = series.map((k) => ({
              key: k,
              v: rows.filter((r) => k === "Otras" ? !keys.includes(cell(r, second)) : cell(r, second) === k).reduce((s, r) => s + (value(r, metric) ?? 0), 0),
            }));
            const total = parts.reduce((s, p) => s + p.v, 0);
            let x = left;
            return (
              <g key={group}>
                <text x={left - 8} y={y + bar / 2} className="cat" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{group}</text>
                {parts.map((p) => {
                  const w = total ? (p.v / total) * plot : 0;
                  const x0 = x; x += w;
                  if (w <= 0) return null;
                  const share = pct(p.v, total);
                  const lines = [{ value: share, label: `${num(p.v)} de ${num(total)} ${label.toLowerCase()}`, key: color(p.key) }];
                  const title = `${group}, ${p.key}`;
                  return (
                    <rect key={p.key} x={x0} y={y} width={Math.max(0, w - 1)} height={bar} fill={color(p.key)} className="mark" role="img" tabIndex={0}
                          aria-label={`${title}: ${share} (${num(p.v)} de ${num(total)})`}
                          onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                          onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
                  );
                })}
                <text x={left + plot + 6} y={y + bar / 2} className="val" dominantBaseline="middle" aria-hidden="true">{compact(total)}</text>
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Cada barra suma el 100 % de su {dimensionLabel(catalog, first).toLowerCase()}; a la derecha, su total. Un cambio de mezcla no implica un cambio de volumen: compara también los totales.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- two-dimension count matrix ---------------------------------------------------- */
export function MatrixView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width: measured } = useTooltip();
  const missingId = useId();
  const [active, setActive] = useState(0);
  if (result.empty) return <Empty />;
  const [first, second] = result.query.group_by;
  const metric = metricsOf(result, catalog)[0];
  const rows = [...new Set(result.rows.map((r) => cell(r, first)))];
  const cols = [...new Set(result.rows.map((r) => cell(r, second)))].sort((a, b) => a.localeCompare(b, "es", { numeric: true }));
  const grid = new Map(result.rows.map((r) => [`${cell(r, first)}|${cell(r, second)}`, r]));
  const max = Math.max(0, ...result.rows.map((r) => value(r, metric) ?? 0));
  const label = metricLabel(catalog, metric);
  const left = Math.min(180, 12 + Math.max(...rows.map((r) => r.length)) * 7);
  const size = Math.max(22, Math.min(56, Math.floor((measured - left - 8) / cols.length)));
  const rowH = 26;
  const width = left + cols.length * size + 8;
  const height = 22 + rows.length * rowH;

  function move(event: KeyboardEvent<SVGRectElement>, r: number, c: number) {
    const next = { ArrowLeft: [r, c - 1], ArrowRight: [r, c + 1], ArrowUp: [r - 1, c], ArrowDown: [r + 1, c],
      Home: [r, 0], End: [r, cols.length - 1] }[event.key];
    if (!next) return;
    event.preventDefault();
    const [nr, nc] = [Math.max(0, Math.min(rows.length - 1, next[0])), Math.max(0, Math.min(cols.length - 1, next[1]))];
    event.currentTarget.ownerSVGElement?.querySelector<SVGRectElement>(`[data-r="${nr}"][data-c="${nc}"]`)?.focus();
  }

  return (
    <div className="viz hour-weekday" ref={ref}>
      <figure className="viz-panel">
        <figcaption>{label} por {dimensionLabel(catalog, first).toLowerCase()} y {dimensionLabel(catalog, second).toLowerCase()}</figcaption>
        <svg viewBox={`0 0 ${width} ${height}`} style={{ maxWidth: width }} role="grid" aria-readonly="true"
             aria-rowcount={rows.length} aria-colcount={cols.length} aria-label={`Matriz de ${label.toLowerCase()}`}>
          <defs>
            <pattern id={missingId} width={6} height={6} patternUnits="userSpaceOnUse">
              <rect width={6} height={6} fill="var(--surface-2)" />
              <path d="M-1 1L1 -1M0 6L6 0M5 7L7 5" stroke="var(--axis)" strokeWidth={1} />
            </pattern>
          </defs>
          {cols.map((c, i) => <text key={c} x={left + i * size + size / 2} y={12} className="tick" textAnchor="middle" aria-hidden="true">{c}</text>)}
          {rows.map((rowKey, r) => (
            <g key={rowKey} role="row" aria-rowindex={r + 1} aria-label={rowKey}>
              <text x={left - 8} y={22 + r * rowH + rowH / 2} className="cat" textAnchor="end" dominantBaseline="middle" aria-hidden="true">{rowKey}</text>
              {cols.map((colKey, c) => {
                const row = grid.get(`${rowKey}|${colKey}`);
                const v = row ? value(row, metric) : null;
                const i = v === null ? -1 : rampIndex(v, max, "log");
                const text = !row ? "Sin fila en este resultado" : formatMetric(v, metric, catalog);
                const title = `${rowKey}, ${colKey}`;
                const lines = [{ value: text, label }];
                const index = r * cols.length + c;
                return (
                  <rect key={colKey} x={left + c * size + 1} y={22 + r * rowH + 1} width={size - 2} height={rowH - 2} rx={3}
                        fill={v === null ? `url(#${missingId})` : i < 0 ? "var(--empty-cell)" : RAMP[i]}
                        className="mark" role="gridcell" aria-colindex={c + 1} data-r={r} data-c={c}
                        tabIndex={active === index ? 0 : -1} aria-label={`${title}: ${text}`}
                        onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                        onFocus={(e) => { setActive(index); show(e.currentTarget.getBoundingClientRect(), { title, lines }); }}
                        onKeyDown={(e) => move(e, r, c)} onBlur={hide} />
                );
              })}
            </g>
          ))}
        </svg>
        <RampLegend max={max} scale="log" missing note="escala logarítmica de informes" />
        <p className="viz-note">Las celdas rayadas no tienen fila en este resultado; no equivalen a cero. La escala es logarítmica para que se vean a la vez los países con pocos y con muchos informes.</p>
      </figure>
      {layer}
    </div>
  );
}

/* -- change between two periods (dumbbell) ----------------------------------------- */
export function DumbbellView({ result, catalog }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  if (result.empty) return <Empty />;
  const [period, category] = result.query.group_by;
  const metric = metricsOf(result, catalog)[0];
  const periodFilter = result.query.filters.find((f) => f.column === period && f.op === "in");
  const periods = (Array.isArray(periodFilter?.value) ? periodFilter.value : [...new Set(result.rows.map((r) => r[period]))])
    .map(String).sort((a, b) => a.localeCompare(b, "es", { numeric: true })).slice(0, 2);
  const totals = periods.map((p) => result.rows.filter((r) => String(r[period]) === p).reduce((s, r) => s + (value(r, metric) ?? 0), 0));
  const unclassified = (r: Row) => r[category] === null || r[category] === undefined;
  const missingShare = periods.map((p, i) => totals[i] ? result.rows.filter((r) => String(r[period]) === p && unclassified(r))
    .reduce((s, r) => s + (value(r, metric) ?? 0), 0) / totals[i] : 0);
  const cats = [...new Set(result.rows.filter((r) => !unclassified(r)).map((r) => cell(r, category)))].map((c) => {
    const shares = periods.map((p, i) => {
      const v = result.rows.filter((r) => String(r[period]) === p && cell(r, category) === c).reduce((s, r) => s + (value(r, metric) ?? 0), 0);
      return { v, share: totals[i] ? v / totals[i] : 0 };
    });
    return { c, shares, delta: shares[1].share - shares[0].share };
  }).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 15);
  const label = metricLabel(catalog, metric);
  const name = (p: string) => period === "decade" ? `${p}s` : p;
  const left = 150, right = 64, rowH = 24;
  const plot = width - left - right;
  const maxShare = niceMax(Math.max(1, ...cats.flatMap((c) => c.shares.map((s) => s.share * 100)))) / 100;
  const sx = (s: number) => left + (s / maxShare) * plot;
  const height = cats.length * rowH + 28;
  const steps = 4;
  return (
    <div className="viz" ref={ref}>
      <figure className="viz-panel">
        <figcaption>Proporción de {label.toLowerCase()} por {dimensionLabel(catalog, category).toLowerCase()}: {name(periods[0])} frente a {name(periods[1])}</figcaption>
        <Legend items={[{ label: `${name(periods[0])} (${num(totals[0])} informes)`, color: "var(--series-1)" }, { label: `${name(periods[1])} (${num(totals[1])} informes)`, color: "var(--series-2)" }]} />
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Cambio de proporción entre ${name(periods[0])} y ${name(periods[1])}`}>
          {Array.from({ length: steps + 1 }, (_, i) => (maxShare * i) / steps).map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={sx(t)} x2={sx(t)} y1={0} y2={height - 20} className="grid" />
              <text x={sx(t)} y={height - 6} className="tick" textAnchor="middle">{pct(t, 1, 1)}</text>
            </g>
          ))}
          {cats.map((c, i) => {
            const y = i * rowH + 12;
            const [a, b] = c.shares;
            const delta = `${c.delta >= 0 ? "+" : "−"}${(Math.round(Math.abs(c.delta) * 1000) / 10).toLocaleString("es-ES")} pp`;
            const title = c.c;
            const lines = [
              { value: pct(a.share, 1), label: `${name(periods[0])}, ${num(a.v)} informes`, key: "var(--series-1)" },
              { value: pct(b.share, 1), label: `${name(periods[1])}, ${num(b.v)} informes`, key: "var(--series-2)" },
              { value: delta, label: "cambio en puntos porcentuales" },
            ];
            return (
              <g key={c.c} className="mark" role="img" tabIndex={0}
                 aria-label={`${title}: ${pct(a.share, 1)} en ${name(periods[0])}, ${pct(b.share, 1)} en ${name(periods[1])} (${delta})`}
                 onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                 onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                <rect x={0} y={y - rowH / 2} width={width} height={rowH} fill="transparent" />
                <text x={left - 10} y={y} className="cat" textAnchor="end" dominantBaseline="middle">{c.c}</text>
                <line x1={sx(a.share)} x2={sx(b.share)} y1={y} y2={y} stroke="var(--axis)" strokeWidth={2} />
                <circle cx={sx(a.share)} cy={y} r={5} fill="var(--series-1)" className="dot" />
                <rect x={sx(b.share) - 5} y={y - 5} width={10} height={10} fill="var(--series-2)" className="dot" />
                <text x={left + plot + 8} y={y} className="val" dominantBaseline="middle">{delta}</text>
              </g>
            );
          })}
        </svg>
        {(() => {
          const what = dimensionLabel(catalog, category).toLowerCase();
          const ex = cats[0];
          const [p0, p1] = [name(periods[0]), name(periods[1])];
          return (
            <div className="viz-note dumbbell-help">
              <p>Cada fila muestra cuántos puntos de peso ganó o perdió ese valor de {what} entre {p0} (círculo azul) y {p1} (cuadrado naranja), sobre el total de informes de cada período.
                {ex ? ` Por ejemplo, ${ex.c} ${ex.delta >= 0 ? "+" : "−"}${(Math.round(Math.abs(ex.delta) * 1000) / 10).toLocaleString("es-ES")} pp: pasó de ${pct(ex.shares[0].share, 1)} a ${pct(ex.shares[1].share, 1)} de los informes.` : ""}
                {ex ? ` O sea, en ${p1} ${ex.c} aparece ${Math.abs(ex.delta) >= 0.05 ? "bastante " : Math.abs(ex.delta) < 0.01 ? "un poco " : ""}${ex.delta >= 0 ? "más" : "menos"} que en ${p0}.` : ""}</p>
              {missingShare.some((m) => m > 0) ? <p>No se dibujan los informes sin {what} ({pct(missingShare[0], 1)} en {p0} y {pct(missingShare[1], 1)} en {p1}).</p> : null}
            </div>
          );
        })()}
      </figure>
      {layer}
    </div>
  );
}

/* -- chronology cards -------------------------------------------------------------- */
const PAGE = 8;

function dateLabel(raw: unknown): string {
  if (typeof raw !== "string") return "sin fecha";
  const [y, m, d] = raw.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("es-ES", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

function durationLabel(seconds: unknown): string | null {
  if (typeof seconds !== "number") return null;
  if (seconds < 60) return `${num(seconds)} s`;
  if (seconds < 3600) return `${num(Math.round(seconds / 60))} min`;
  return `${num(Math.round((seconds / 3600) * 10) / 10)} h`;
}

export function TimelineView({ result }: Props) {
  const [page, setPage] = useState(0);
  const headingId = useId();
  if (result.empty) return <Empty>No hay informes con fecha de precisión diaria con esos filtros.</Empty>;
  const pages = Math.ceil(result.rows.length / PAGE);
  const shown = result.rows.slice(page * PAGE, page * PAGE + PAGE);
  return (
    <div className="viz">
      <figure className="viz-panel">
        <figcaption id={headingId}>
          Cronología: {num(result.rows.length)} informes{result.truncated ? " (truncado)" : ""}, del {dateLabel(result.rows[0].event_date)} al {dateLabel(result.rows[result.rows.length - 1].event_date)}
        </figcaption>
        <ol className="timeline" aria-labelledby={headingId} start={page * PAGE + 1}>
          {shown.map((row, i) => (
            <li key={String(row.report_id)} className={(page * PAGE + i) % 2 ? "timeline-item right" : "timeline-item"}>
              <time dateTime={String(row.event_date)}>{dateLabel(row.event_date)}</time>
              <strong>{cell(row, "shape_code") === "sin dato" ? "Forma sin clasificar" : cell(row, "shape_code")}</strong>
              <span>{cell(row, "country_iso2") === "sin dato" ? "País sin dato" : cell(row, "country_iso2")}, {cell(row, "source_code")}</span>
              <span className="timeline-meta">
                {[durationLabel(row.duration_seconds), typeof row.num_witnesses === "number" ? `${num(row.num_witnesses)} testigos` : null, `ID ${row.report_id}`]
                  .filter(Boolean).join(", ")}
              </span>
            </li>
          ))}
        </ol>
        {pages > 1 ? (
          <nav className="timeline-pager" aria-label="Páginas de la cronología">
            <button type="button" className="ghost" onClick={() => setPage((p) => p - 1)} disabled={page === 0}>Anteriores</button>
            <span aria-live="polite">Página {page + 1} de {pages}</span>
            <button type="button" className="ghost" onClick={() => setPage((p) => p + 1)} disabled={page >= pages - 1}>Siguientes</button>
          </nav>
        ) : null}
        <p className="viz-note">Solo entran informes con fecha de precisión diaria. El orden es documental: la separación entre tarjetas no representa el tiempo transcurrido.</p>
      </figure>
    </div>
  );
}

/* -- duration distribution: histogram and ECDF ------------------------------------- */
function DistributionTotals({ result }: { result: GoldResult }) {
  const d = result.distribution!;
  const all = d.with_duration + d.without_duration;
  return (
    <div className="stat-grid calendar-totals">
      <div className="stat"><div className="stat-label">Informes en la consulta</div><div className="stat-value">{num(all)}</div></div>
      <div className="stat"><div className="stat-label">Con duración declarada</div><div className="stat-value">{num(d.with_duration)}</div>
        <div className="stat-note">{pct(d.with_duration, all)}, {num(d.over_max)} duran más de {d.max_minutes} min</div></div>
      <div className="stat stat-unknown"><div className="stat-label">Sin duración declarada</div><div className="stat-value">{num(d.without_duration)}</div>
        <div className="stat-note">{pct(d.without_duration, all)}, no se imputa</div></div>
    </div>
  );
}

export function HistogramView({ result }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  const [step, setStep] = useState(5);
  const groupId = useId();
  const d = result.distribution;
  if (!d) return <Empty />;
  const bins = Array.from({ length: d.max_minutes / step }, (_, i) => ({
    from: i * step, to: (i + 1) * step,
    n: d.bins.slice(i * step, (i + 1) * step).reduce((s, b) => s + b.report_count, 0),
  }));
  const all = [...bins, { from: d.max_minutes, to: null as number | null, n: d.over_max }];
  const max = Math.max(1, ...all.map((b) => b.n));
  const left = 56, height = 260, pad = 28;
  const plot = width - left - 16;
  const bw = plot / all.length;
  const sy = (v: number) => height - pad - (v / max) * (height - pad - 12);
  return (
    <div className="viz" ref={ref}>
      <DistributionTotals result={result} />
      <figure className="viz-panel">
        <figcaption>Informes por duración declarada, en tramos de {step} minutos</figcaption>
        <div className="segmented" role="radiogroup" aria-labelledby={groupId}>
          <span id={groupId}>Tramo</span>
          {[5, 10, 15].map((s) => (
            <button key={s} type="button" role="radio" aria-checked={step === s} className="ghost" onClick={() => setStep(s)}>{s} min</button>
          ))}
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Histograma de duración en tramos de ${step} minutos`}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={left} x2={width - 16} y1={sy(t * max)} y2={sy(t * max)} className="grid" />
              <text x={left - 6} y={sy(t * max)} className="tick" textAnchor="end" dominantBaseline="middle">{compact(Math.round(t * max))}</text>
            </g>
          ))}
          {all.map((b, i) => {
            const tail = b.to === null;
            const title = tail ? `Más de ${d.max_minutes} min` : `${b.from}–${b.to} min`;
            const lines = [{ value: num(b.n), label: `informes, ${pct(b.n, d.with_duration)} de los que declaran duración`, key: tail ? "var(--axis)" : "var(--series-1)" }];
            return (
              <g key={title} className="mark" role="img" tabIndex={0} aria-label={`${title}: ${num(b.n)} informes`}
                 onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                 onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide}>
                <rect x={left + i * bw + 1} y={sy(b.n)} width={Math.max(1, bw - 2)} height={height - pad - sy(b.n)}
                      fill={tail ? "var(--surface-2)" : "var(--series-1)"} stroke={tail ? "var(--axis)" : "none"} strokeDasharray={tail ? "3 2" : undefined} />
                <text x={left + i * bw + bw / 2} y={height - 10} className="tick" textAnchor="middle" aria-hidden="true">{tail ? `>${d.max_minutes}` : b.from}</text>
              </g>
            );
          })}
        </svg>
        <p className="viz-note">Eje: minutos desde el inicio del tramo. La barra punteada reúne la cola superior (más de {d.max_minutes} min) para no ocultar valores extremos; los informes sin duración no se imputan y se cuentan arriba.</p>
      </figure>
      {layer}
    </div>
  );
}

export function EcdfView({ result }: Props) {
  const { ref, show, hide, layer, width } = useTooltip();
  const [threshold, setThreshold] = useState(5);
  const groupId = useId();
  const d = result.distribution;
  if (!d) return <Empty />;
  let running = 0;
  const points = d.bins.map((b, i) => { running += b.report_count; return { minute: i + 1, share: d.with_duration ? running / d.with_duration : 0, n: running }; });
  const left = 56, height = 260, pad = 28;
  const plot = width - left - 16;
  const sx = (m: number) => left + (m / d.max_minutes) * plot;
  const sy = (s: number) => height - pad - s * (height - pad - 12);
  const path = `M${sx(0)},${sy(0)}` + points.map((p) => `H${sx(p.minute)}V${sy(p.share)}`).join("");
  const at = points[threshold - 1];
  return (
    <div className="viz" ref={ref}>
      <DistributionTotals result={result} />
      <figure className="viz-panel">
        <figcaption>Porcentaje acumulado de informes con duración declarada hasta cada minuto</figcaption>
        <div className="segmented" role="radiogroup" aria-labelledby={groupId}>
          <span id={groupId}>Umbral</span>
          {[1, 5, 15, 60].map((m) => (
            <button key={m} type="button" role="radio" aria-checked={threshold === m} className="ghost" onClick={() => setThreshold(m)}>{m} min</button>
          ))}
        </div>
        <p className="ecdf-answer" aria-live="polite"><strong>{pct(at.n, d.with_duration)}</strong> de los informes con duración declarada duran {threshold} min o menos ({num(at.n)} de {num(d.with_duration)}).</p>
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Duración acumulada">
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t} aria-hidden="true">
              <line x1={left} x2={width - 16} y1={sy(t)} y2={sy(t)} className="grid" />
              <text x={left - 6} y={sy(t)} className="tick" textAnchor="end" dominantBaseline="middle">{t * 100} %</text>
            </g>
          ))}
          {[0, 10, 20, 30, 40, 50, 60].map((m) => <text key={m} x={sx(m)} y={height - 8} className="tick" textAnchor="middle" aria-hidden="true">{m} min</text>)}
          <path d={path} className="series" stroke="var(--series-1)" />
          <line x1={sx(threshold)} x2={sx(threshold)} y1={sy(0)} y2={sy(at.share)} stroke="var(--series-2)" strokeDasharray="4 3" />
          <line x1={left} x2={sx(threshold)} y1={sy(at.share)} y2={sy(at.share)} stroke="var(--series-2)" strokeDasharray="4 3" />
          {points.map((p) => {
            const title = `Hasta ${p.minute} min`;
            const lines = [{ value: pct(p.n, d.with_duration), label: `${num(p.n)} informes`, key: "var(--series-1)" }];
            return (
              <rect key={p.minute} x={sx(p.minute - 1)} y={12} width={plot / d.max_minutes} height={height - pad - 12} fill="transparent"
                    className="mark" role="img" tabIndex={[1, 5, 15, 30, 60].includes(p.minute) ? 0 : -1} aria-label={`${title}: ${pct(p.n, d.with_duration)}`}
                    onPointerMove={(e) => show(e, { title, lines })} onPointerLeave={hide}
                    onFocus={(e) => show(e.currentTarget.getBoundingClientRect(), { title, lines })} onBlur={hide} />
            );
          })}
          <circle cx={sx(threshold)} cy={sy(at.share)} r={5} fill="var(--series-2)" className="dot" />
        </svg>
        <p className="viz-note">La curva llega a {pct(points[points.length - 1].n, d.with_duration)} a los {d.max_minutes} min; el resto ({num(d.over_max)} informes) dura más. Responde “¿qué porcentaje dura hasta X?” sin elegir intervalos de histograma.</p>
      </figure>
      {layer}
    </div>
  );
}
