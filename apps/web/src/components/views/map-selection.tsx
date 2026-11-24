"use client";

/* Rectangle and lasso selection shared by the 2D/3D map and the globe, as in DB Test:
   Mover / Rectángulo / Lazo. The selection is drawn in screen pixels over the canvas;
   each map decides which reports fall inside by projecting them to the same pixels. */

import { useEffect, useRef, useState, type ReactNode } from "react";

export type Tool = "move" | "rectangle" | "lasso";
export type Pixel = [number, number];

const MIN_DRAG = 8; // a click is not a selection

/** Ray casting: is the pixel inside the polygon? */
export function inside([x, y]: Pixel, poly: Pixel[]): boolean {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

export function SelectionTools({ tool, onTool }: { tool: Tool; onTool: (t: Tool) => void }) {
  const tools: [Tool, string][] = [["move", "Mover"], ["rectangle", "Rectángulo"], ["lasso", "Lazo"]];
  return (
    <span className="map-mode" role="group" aria-label="Herramienta del mapa">
      {tools.map(([t, label]) => (
        <button key={t} type="button" aria-pressed={tool === t} onClick={() => onTool(t)}>{label}</button>
      ))}
    </span>
  );
}

/** Captures the pointer over the map while a selection tool is active and draws the shape. */
export function SelectionLayer({ tool, onSelect, onCancel }: { tool: Tool; onSelect: (poly: Pixel[]) => void; onCancel: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<Pixel[]>([]);
  const drag = useRef<{ start: Pixel; trail: Pixel[] } | null>(null);

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") { drag.current = null; setPoints([]); onCancel(); } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onCancel]);

  if (tool === "move") return null;
  const at = (e: React.PointerEvent): Pixel => {
    const r = host.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const shape = (start: Pixel, p: Pixel, trail: Pixel[]): Pixel[] =>
    tool === "lasso" ? [...trail] : [start, [p[0], start[1]], p, [start[0], p[1]]];

  return (
    <div ref={host} className="map-selection-layer" aria-hidden="true"
         onPointerDown={(e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); const p = at(e); drag.current = { start: p, trail: [p] }; setPoints([]); }}
         onPointerMove={(e) => {
           const d = drag.current; if (!d) return;
           const p = at(e); d.trail.push(p); setPoints(shape(d.start, p, d.trail));
         }}
         onPointerUp={(e) => {
           const d = drag.current; drag.current = null; if (!d) return;
           const p = at(e);
           const poly = shape(d.start, p, d.trail);
           setPoints([]);
           const xs = poly.map((q) => q[0]), ys = poly.map((q) => q[1]);
           const size = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
           if (size < MIN_DRAG || poly.length < 3) return; // a click, not an area
           onSelect(poly);
         }}
         onPointerCancel={() => { drag.current = null; setPoints([]); }}>
      {points.length > 1 ? (
        <svg><polygon points={points.map((p) => p.join(",")).join(" ")} /></svg>
      ) : null}
    </div>
  );
}

export function SelectionSummary({ children, onClear }: { children: ReactNode; onClear: () => void }) {
  return (
    <div className="map-selection-summary" role="status">
      <div>{children}</div>
      <button type="button" className="geo-map-reset" onClick={onClear}>Limpiar selección</button>
    </div>
  );
}
