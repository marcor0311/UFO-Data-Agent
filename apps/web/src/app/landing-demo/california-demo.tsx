"use client";

import { useState, type CSSProperties } from "react";
import CaliforniaTerrain from "./california-terrain";
import snapshot from "./california-1990.json";
import type { ReportPoint } from "./terrain";
import styles from "./demo.module.css";

const reports: ReportPoint[] = snapshot.points;
const months = [
  ["Ene", "Enero"], ["Feb", "Febrero"], ["Mar", "Marzo"], ["Abr", "Abril"],
  ["May", "Mayo"], ["Jun", "Junio"], ["Jul", "Julio"], ["Ago", "Agosto"],
  ["Sep", "Septiembre"], ["Oct", "Octubre"], ["Nov", "Noviembre"], ["Dic", "Diciembre"],
].map(([short, label], index) => ({
  short, label, number: index + 1, count: reports.filter(({ month }) => month === index + 1).length,
}));
const withoutMonth = reports.filter(({ month }) => month === null).length;
const scale = Math.ceil(Math.max(...months.map(({ count }) => count)) / 20) * 20;

export default function CaliforniaDemo() {
  const [month, setMonth] = useState<number | null>(null);
  const selected = month === null ? reports : reports.filter((report) => report.month === month);
  const selectedLabel = month === null ? "Todo 1990" : months[month - 1].label;

  return (
    <figure className={styles.demo} aria-label="Demostración de Gold con informes de California en 1990">
      <div className={styles.chart}>
        <div className={styles.chartTitle}>
          <h3>Informes por mes</h3>
          <button type="button" aria-pressed={month === null} onClick={() => setMonth(null)}>Todo 1990</button>
        </div>
        <p className={styles.chartInstruction}>Elige un mes para ver sus informes en el mapa.</p>
        <div className={styles.plot}>
          <div className={styles.grid} aria-hidden="true">
            <span>{scale}</span><span>{scale / 2}</span><span>0</span>
          </div>
          <div className={styles.bars} role="group" aria-label="Meses de 1990">
            {months.map(({ short, label, number, count }) => (
              <button
                type="button"
                key={number}
                style={{ "--bar-height": `${count / scale * 100}%` } as CSSProperties}
                aria-description={`${count} ${count === 1 ? "informe" : "informes"} en ${label.toLowerCase()} de 1990`}
                aria-pressed={month === number}
                onClick={() => setMonth(month === number ? null : number)}
              >
                <span className={styles.barSpace}><span className={styles.bar}><span>{count}</span></span></span>
                {" "}
                <span className={styles.month}>{short}</span>
              </button>
            ))}
          </div>
        </div>
        <p className={styles.chartNote}>Las barras omiten {withoutMonth} informes sin mes confiable.</p>
      </div>
      <div className={styles.mapPane}>
        <div className={styles.mapTitle}>
          <h3>Mapa 3D</h3>
          <p className={styles.selection} aria-live="polite">{selectedLabel} · {selected.length} {selected.length === 1 ? "informe" : "informes"}</p>
        </div>
        <CaliforniaTerrain reports={selected} />
      </div>
      <figcaption>
        Gold · Informes con coordenadas aptas dentro de California. Relieve de Mapzen y límites del U.S. Census Bureau.
      </figcaption>
    </figure>
  );
}
