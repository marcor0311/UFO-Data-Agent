"use client";

import gsap from "gsap";
import { useEffect, useRef, useState, type CSSProperties } from "react";
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
const secondsPerMonth = 1.2;
const playbackLabels = {
  idle: "Recorrer el año",
  playing: "Pausar recorrido",
  paused: "Continuar recorrido",
};

export default function CaliforniaDemo() {
  const [month, setMonth] = useState<number | null>(null);
  const [playbackState, setPlaybackState] = useState<keyof typeof playbackLabels>("idle");
  const playback = useRef<gsap.core.Timeline | null>(null);
  const progress = useRef<HTMLSpanElement>(null);
  const selected = month === null ? reports : reports.filter((report) => report.month === month);
  const selectedLabel = month === null ? "Todo 1990" : months[month - 1].label;

  useEffect(() => () => {
    playback.current?.kill();
  }, []);

  function selectMonth(nextMonth: number | null) {
    playback.current?.kill();
    playback.current = null;
    setPlaybackState("idle");
    setMonth(nextMonth);
    if (progress.current) gsap.set(progress.current, { clearProps: "transform" });
  }

  function togglePlayback() {
    if (playbackState === "playing") {
      playback.current?.pause();
      setPlaybackState("paused");
      return;
    }

    if (playback.current) {
      playback.current.resume();
    } else if (progress.current) {
      const timeline = gsap.timeline({
        onComplete: () => {
          playback.current = null;
          setPlaybackState("idle");
        },
      });
      timeline.fromTo(progress.current, { scaleX: 0 }, {
        scaleX: 1,
        ease: `steps(${months.length})`,
        duration: months.length * secondsPerMonth,
      }, 0);
      months.slice(1).forEach(({ number }, index) => {
        timeline.call(() => setMonth(number), [], (index + 1) * secondsPerMonth);
      });
      playback.current = timeline;
      setMonth(months[0].number);
    }
    setPlaybackState("playing");
  }

  return (
    <figure className={styles.demo} aria-label="Exploración de informes de California en 1990">
      <div className={styles.chart}>
        <div className={styles.chartTitle}>
          <h3>Informes por mes</h3>
        </div>
        <p className={styles.chartInstruction}>Elige un mes para ver sus informes en el mapa.</p>
        <div className={styles.chartActions} role="group" aria-label="Explorar informes de 1990">
          <button type="button" onClick={togglePlayback}>{playbackLabels[playbackState]}</button>
          <button type="button" aria-pressed={month === null} onClick={() => selectMonth(null)}>Todo 1990</button>
        </div>
        <div className={styles.chartProgress} aria-hidden="true"><span ref={progress} /></div>
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
        </div>
        <p className={styles.chartNote}>Las barras omiten {withoutMonth} informes sin mes confiable.</p>
      </div>
      <div className={styles.mapPane}>
        <div className={styles.mapTitle}>
          <h3>Mapa 3D</h3>
          <p className={styles.selection} aria-live={playbackState === "playing" ? "off" : "polite"}>{selectedLabel}, {selected.length} {selected.length === 1 ? "informe" : "informes"}</p>
        </div>
        <CaliforniaTerrain reports={selected} />
      </div>
      <figcaption>
        El mapa muestra los informes que se pueden ubicar dentro de California. Relieve de Mapzen y límites del U.S. Census Bureau.
      </figcaption>
    </figure>
  );
}
