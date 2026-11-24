"use client";

import { useId, useState } from "react";
import type { Catalog, GoldResult } from "@/lib/contracts";
import { num } from "@/lib/format";
import { DataTable } from "../views/shared";

const short = (sha: string) => sha.slice(0, 12) + "…";

export function Evidence({ result, catalog }: { result: GoldResult; catalog: Catalog | null }) {
  const [open, setOpen] = useState<"data" | "source" | null>(null);
  const id = useId();
  const ex = result.exclusions;
  const reportCount = result.total?.report_count ?? (result.rows.length === 1 ? result.rows[0].report_count : undefined);
  const dataset = catalog?.datasets[result.provenance.dataset]?.label ?? result.provenance.dataset;
  const toggle = (panel: "data" | "source") => setOpen((current) => current === panel ? null : panel);
  return (
    <div className="evidence">
      <div className="evidence-bar">
        {result.rows.length ? (
          <button type="button" aria-expanded={open === "data"} aria-controls={`${id}-data`} onClick={() => toggle("data")}>Datos exactos</button>
        ) : null}
        <button type="button" aria-expanded={open === "source"} aria-controls={`${id}-source`} onClick={() => toggle("source")}>Fuentes y consulta</button>
        <span className="evidence-note">{dataset}, {num(result.matched_source_rows)} registros de origen</span>
      </div>
      {result.rows.length ? (
        <div id={`${id}-data`} className="evidence-body" hidden={open !== "data"}>
          {open === "data" ? <DataTable result={result} catalog={catalog} /> : null}
        </div>
      ) : null}
      <div id={`${id}-source`} className="evidence-body" hidden={open !== "source"}>
        <p className="readable">{result.readable_query.texto}</p>
        <dl className="provenance">
          <dt>Carga Gold</dt><dd><code title={result.provenance.gold_load_id}>{short(result.provenance.gold_load_id)}</code></dd>
          <dt>Conjunto</dt><dd>{dataset} <code>{result.provenance.dataset}</code></dd>
          <dt>Snapshot</dt><dd>{result.snapshot.label}{result.snapshot.silver_reference_date ? `; referencia de Silver ${result.snapshot.silver_reference_date}` : ""}</dd>
          <dt>SHA de Gold</dt><dd><code title={result.provenance.gold_sha256}>{short(result.provenance.gold_sha256)}</code></dd>
          <dt>SHA de Silver</dt><dd><code title={result.provenance.silver_sha256}>{short(result.provenance.silver_sha256)}</code></dd>
          <dt>Definiciones</dt><dd><code title={result.provenance.definitions_sha256}>{short(result.provenance.definitions_sha256)}</code></dd>
          <dt>Consulta</dt><dd><code title={result.provenance.query_sha256}>{short(result.provenance.query_sha256)}</code></dd>
          <dt>Filas de origen</dt><dd>{num(result.matched_source_rows)}{result.truncated ? " · resultado truncado" : ""}</dd>
        </dl>
        {ex ? (
          <>
            {typeof reportCount === "number" ? <p><strong>Informes del corte consultado:</strong> {num(reportCount)}.</p> : null}
            <p>
              Elegibilidad aplicada: {result.eligibility_applied.map((e) => e.label + (e.implied ? " (implícita)" : "")).join(", ")}.
            </p>
            <p>
              <strong>Población evaluada para elegibilidad:</strong> {ex.scope}.{" "}
              Base: {num(ex.base_reports)} informes; elegibles: {num(ex.eligible_reports)}; excluidos: {num(ex.excluded_reports)}
              {ex.excluded_by_reason.length ? " (" + ex.excluded_by_reason.slice(0, 4).map((r) => `${r.label.toLowerCase()} (${num(r.reports)})`).join(", ") + ")" : ""}.
              {" "}Estos conteos corresponden al alcance indicado y pueden abarcar una población mayor que el corte consultado.
            </p>
          </>
        ) : null}
        {result.external_evidence_reports ? (
          <p>{num(result.external_evidence_reports)} informes usan coordenadas, país u hora del catálogo externo de UFO-search.</p>
        ) : null}
        {result.limitations.length ? (
          <>
            <p className="evidence-subhead">Limitaciones de los datos</p>
            <ul className="limitations" aria-label="Limitaciones">
              {result.limitations.map((l) => <li key={l.code + l.text}>{l.text}</li>)}
            </ul>
          </>
        ) : null}
        <p className="evidence-subhead">Consulta reproducible</p>
        <pre className="query-json" tabIndex={0} aria-label="Consulta reproducible en JSON">
          {JSON.stringify({ query: result.query, provenance: result.provenance }, null, 2)}
        </pre>
      </div>
    </div>
  );
}
