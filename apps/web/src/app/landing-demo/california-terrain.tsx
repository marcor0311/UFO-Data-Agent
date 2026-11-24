"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { drawTerrain, maxReliefPitch, type Camera, type ReportPoint } from "./terrain";
import styles from "./demo.module.css";

const initialCamera: Camera = { yaw: -0.52, pitch: 0.66, zoom: 1, panX: 0, panY: 0, overhead: false };
const zoomLevels = [0.55, 0.75, 1, 1.25, 1.5, 2];

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export default function CaliforniaTerrain({ reports, onViewChange }: { reports: ReportPoint[]; onViewChange: (overhead: boolean) => void }) {
  const helpId = useId();
  const canvas = useRef<HTMLCanvasElement>(null);
  const camera = useRef(initialCamera);
  const drag = useRef<{ x: number; y: number; pan: boolean } | null>(null);
  const redraw = useRef<(() => void) | null>(null);
  const [{ zoom, overhead }, setControls] = useState(initialCamera);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext("2d");
    if (!element || !context) return;

    let frame: number | null = null;
    function queueDraw() {
      if (frame !== null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        if (!element || !context) return;
        const { clientWidth: width, clientHeight: height } = element;
        if (!width || !height) return;

        const ratio = Math.min(window.devicePixelRatio, 2);
        const pixelWidth = Math.round(width * ratio);
        const pixelHeight = Math.round(height * ratio);
        if (element.width !== pixelWidth) element.width = pixelWidth;
        if (element.height !== pixelHeight) element.height = pixelHeight;
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        drawTerrain(context, width, height, camera.current, reports);
      });
    }

    const observer = new ResizeObserver(queueDraw);
    observer.observe(element);
    redraw.current = queueDraw;
    queueDraw();

    return () => {
      observer.disconnect();
      if (frame !== null) cancelAnimationFrame(frame);
      redraw.current = null;
    };
  }, [reports]);

  function setCamera(next: Camera) {
    camera.current = next;
    setControls(next);
    redraw.current?.();
  }

  function zoomBy(step: number) {
    const view = camera.current;
    const index = clamp(zoomLevels.indexOf(view.zoom) + step, 0, zoomLevels.length - 1);
    const nextZoom = zoomLevels[index];
    if (nextZoom === view.zoom) return;
    const ratio = nextZoom / view.zoom;
    setCamera({
      ...view,
      zoom: nextZoom,
      panX: clamp(view.panX * ratio, -0.55, 0.55),
      panY: clamp(view.panY * ratio, -0.55, 0.55),
    });
  }

  function moveCamera(dx: number, dy: number, pan: boolean) {
    const element = canvas.current;
    if (!element?.clientWidth || !element.clientHeight) return;
    const view = camera.current;

    camera.current = pan ? {
      ...view,
      panX: clamp(view.panX + dx / element.clientWidth, -0.55, 0.55),
      panY: clamp(view.panY + dy / element.clientHeight, -0.55, 0.55),
    } : {
      ...view,
      yaw: view.yaw + dx * 0.0045,
      pitch: clamp(view.pitch + dy * 0.0035, 0.38, maxReliefPitch),
    };
    redraw.current?.();
  }

  function onMapKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const pan = camera.current.overhead || event.shiftKey;

    switch (event.key) {
      case "ArrowLeft": moveCamera(-40, 0, pan); break;
      case "ArrowRight": moveCamera(40, 0, pan); break;
      case "ArrowUp": moveCamera(0, -40, pan); break;
      case "ArrowDown": moveCamera(0, 40, pan); break;
      case "+": case "=": zoomBy(1); break;
      case "-": zoomBy(-1); break;
      case "Home": setCamera(initialCamera); break;
      default: return;
    }
    event.preventDefault();
  }

  return (
    <div className={styles.map}>
      <canvas
        ref={canvas}
        role="img"
        tabIndex={0}
        aria-label={`${overhead ? "Vista cenital" : "Relieve 3D"} de California con ${reports.length} informes ubicados`}
        aria-describedby={helpId}
        onKeyDown={onMapKeyDown}
        onPointerDown={(event) => {
          if (event.button !== 0 || !event.isPrimary) return;
          drag.current = { x: event.clientX, y: event.clientY, pan: overhead || event.shiftKey };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const start = drag.current;
          if (!start || !event.isPrimary) return;
          moveCamera(event.clientX - start.x, event.clientY - start.y, start.pan);
          drag.current = { ...start, x: event.clientX, y: event.clientY };
        }}
        onLostPointerCapture={() => { drag.current = null; }}
      >
        El mapa representa los informes seleccionados sobre California
      </canvas>
      <div className={styles.mapFooter}>
        <span id={helpId}>
          {overhead ? "Arrastra para mover" : "Arrastra para girar"}
          <span className="sr-only">. Usa las flechas, más y menos, o Inicio para restablecer</span>
        </span>
        <div className={styles.mapControls} role="group" aria-label="Controles del mapa">
          <div className={styles.zoomControls} role="group" aria-label="Zoom">
            <button type="button" aria-label="Alejar" title="Alejar" disabled={zoom === zoomLevels[0]} onClick={() => zoomBy(-1)}>−</button>
            <button type="button" aria-label="Acercar" title="Acercar" disabled={zoom === zoomLevels.at(-1)} onClick={() => zoomBy(1)}>+</button>
          </div>
          <button
            type="button"
            aria-pressed={overhead}
            onClick={() => {
              const nextOverhead = !overhead;
              onViewChange(nextOverhead);
              setCamera({ ...camera.current, overhead: nextOverhead, panX: 0, panY: 0 });
            }}
          >
            {overhead ? "Vista 3D" : "Vista 2D"}
          </button>
          <button type="button" onClick={() => setCamera(initialCamera)}>Restablecer</button>
        </div>
      </div>
    </div>
  );
}
