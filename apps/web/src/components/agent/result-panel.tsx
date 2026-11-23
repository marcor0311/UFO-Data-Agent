"use client";

import { useId } from "react";
import type { Catalog, GoldResult } from "@/lib/contracts";
import { num } from "@/lib/format";
import { Visualization } from "../views/registry";
import { Evidence } from "./evidence";

export function resultTitle(result: GoldResult, catalog: Catalog | null) {
  return result.title || catalog?.certified_queries.find((q) => q.id === result.certified_query_id)?.title
    || catalog?.views[result.view]?.label || result.view_label;
}

function isSummary(result: GoldResult) {
  return result.view === "table" && result.query.group_by.length === 0
    && result.rows.length === 1 && result.query.metrics.length > 0 && result.query.metrics.length <= 2;
}

export function groupResults(results: GoldResult[]) {
  const ordered = results.map((result, index) => ({ result, index }))
    .sort((a, b) => Number(a.result.view === "table") - Number(b.result.view === "table") || a.index - b.index);
  const groups: (typeof ordered)[] = [];
  while (ordered.length) {
    const entry = ordered.shift()!;
    const result = entry.result;
    const comparison = (result.view === "bars" || result.view === "table")
      && result.query.group_by.length > 0 && result.query.metrics.length > 0 && result.rows.length > 1;
    const companion = comparison
      ? ordered.findIndex((item) => item.result.query.dataset === result.query.dataset && isSummary(item.result))
      : -1;
    groups.push(companion < 0 ? [entry] : [entry, ...ordered.splice(companion, 1)]);
  }
  return groups;
}

export function ResultPanel({ result, catalog, showTitle }: { result: GoldResult; catalog: Catalog | null; showTitle: boolean }) {
  const headingId = useId();
  return (
    <section className="result" aria-labelledby={headingId}>
      <h2 id={headingId} className={showTitle ? "result-title" : "sr-only"}>{resultTitle(result, catalog)}</h2>
      <Visualization result={result} catalog={catalog} />
      {result.truncated ? (
        <p className="result-warning" role="status">Se muestran {num(result.row_count)} filas. Ajusta los filtros para acotar la consulta.</p>
      ) : null}
      <Evidence result={result} catalog={catalog} />
    </section>
  );
}
