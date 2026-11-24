"use client";

import { useId } from "react";
import type { Catalog, GoldResult } from "@/lib/contracts";
import { num } from "@/lib/format";
import { Visualization } from "../views/registry";
import { Evidence } from "./evidence";

export { groupResults } from "@/lib/result-groups";

export function resultTitle(result: GoldResult, catalog: Catalog | null) {
  return result.title || catalog?.certified_queries.find((q) => q.id === result.certified_query_id)?.title
    || catalog?.views[result.view]?.label || result.view_label;
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
