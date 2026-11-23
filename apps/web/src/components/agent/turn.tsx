"use client";

import type { Turn } from "@/lib/contracts";
import AnswerMarkdown from "./answer-markdown";

const TOOL_LABELS = new Map([
  ["search_certified", "Buscar una consulta de ejemplo"],
  ["run_certified", "Ejecutar la consulta de ejemplo"],
  ["query_gold", "Consultar los datos Gold"],
  ["find_entities", "Identificar fuentes, lugares y otros términos"],
  ["describe_data", "Revisar los datos disponibles"],
]);

export function TurnView({ turn, index, active, onShowResults }: { turn: Turn; index: number; active: boolean; onShowResults: () => void }) {
  return (
    <article className="turn" aria-label={`Respuesta ${index + 1}`}>
      {turn.visualizations.length ? (
        <button type="button" className="turn-question" aria-controls="resultados" aria-pressed={active} onClick={onShowResults}
                title="Ver de nuevo el resultado de esta pregunta">
          {turn.question}<span className="sr-only"> (ver resultado)</span>
        </button>
      ) : <p className="turn-question"><span className="sr-only">Pregunta. </span>{turn.question}</p>}
      <div className="turn-answer">
        <span className="sr-only">Respuesta.</span>
        <AnswerMarkdown text={turn.answer} />
      </div>
      <details className="turn-trace">
        <summary>Cómo se obtuvo</summary>
        {turn.model ? <p>Modelo <code>{turn.model}</code></p> : null}
        {turn.trace.length ? (
          <ol>
            {turn.trace.map((step, index) => {
              const label = TOOL_LABELS.get(step.tool);
              return (
                <li key={index}>
                  {label ?? step.tool}
                  {label && step.tool !== "search_certified" && step.tool !== "run_certified"
                    ? <> <code>{step.tool}</code></> : null}
                  {" · "}{step.ok ? "Completada" : "Con error"}
                </li>
              );
            })}
          </ol>
        ) : <p>Esta respuesta se obtuvo sin usar herramientas.</p>}
        {turn.visualizations.length ? <p>Los datos exactos y las fuentes están disponibles en el resultado.</p> : null}
      </details>
    </article>
  );
}
