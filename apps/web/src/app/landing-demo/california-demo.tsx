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
const maxBarShare = 2 / 3;
const scale = Math.ceil(Math.max(...months.map(({ count }) => count)) / (20 * maxBarShare)) * 20;
export default function CaliforniaDemo() {
  const [month, setMonth] = useState<number | null>(null);
  const [overhead, setOverhead] = useState(false);
  const selected = month === null ? reports : reports.filter((report) => report.month === month);
  const selectedLabel = month === null ? "1990" : months[month - 1].label;

  function selectMonth(nextMonth: number | null) {
    setMonth(nextMonth);
  }

  return (
    <figure className={styles.demo} aria-label="Exploración de informes de California en 1990">
      <div className={styles.chart}>
        <div className={styles.chartTitle}>
          <h3>Informes por mes</h3>
        </div>
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
                onClick={() => selectMonth(month === number ? null : number)}
              >
                <span className={styles.barSpace}><span className={styles.bar}><span>{count}</span></span></span>
                {" "}
                <span className={styles.month}>{short}</span>
              </button>
            ))}
          </div>
          <p className={styles.chartHint}>Selecciona un mes para filtrar el mapa o quitar el filtro</p>
        </div>
      </div>
      <div className={styles.mapPane}>
        <div className={styles.mapTitle}>
          <h3>{overhead ? "Mapa 2D" : "Mapa 3D"}</h3>
          <p className={styles.selection} aria-live="polite">{selectedLabel}, {selected.length} {selected.length === 1 ? "informe" : "informes"}</p>
        </div>
        <CaliforniaTerrain reports={selected} onViewChange={setOverhead} />
      </div>
    </figure>
  );
}
