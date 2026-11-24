"use client";

/* Catalog of the 28 UAP models, ported from DB Test/visor-modelos.js.
   Same meshes as the map. One WebGL context, created when the panel is shown inline and
   released when it is closed. Drag or arrow keys to rotate. */

import { useEffect, useMemo, useRef, useState } from "react";
import { MODEL_FORMS, mesh, type ModelKind } from "@/lib/map-models";

const VERTEX = `attribute vec3 position;attribute vec3 normal;attribute vec3 color;uniform mat3 rotation;uniform vec2 scale;
varying vec3 n;varying vec3 pigment;
void main(){vec3 p=rotation*position;n=rotation*normal;pigment=color;gl_Position=vec4(p.x*scale.x,p.y*scale.y,-p.z*.18,1.0);}`;
const FRAGMENT = `precision mediump float;varying vec3 n;varying vec3 pigment;
void main(){vec3 v=normalize(n);float light=max(0.0,dot(v,normalize(vec3(-.4,.7,1.0))));
float spec=pow(max(0.0,dot(v,normalize(vec3(-.2,.35,1.0)))),28.0);gl_FragColor=vec4(pigment*(.48+.52*light)+vec3(spec*.18),1.0);}`;
const START = { yaw: 0.4, pitch: 0.75, zoom: 1 };

function Stage({ kind, zoom, camera }: { kind: ModelKind | "all"; zoom: number; camera: React.MutableRefObject<{ yaw: number; pitch: number; redraw: () => void }> }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const visible = useMemo(() => (kind === "all" ? MODEL_FORMS : MODEL_FORMS.filter((f) => f.kind === kind)), [kind]);
  const columns = kind === "all" ? 4 : 1;
  const rows = Math.ceil(visible.length / columns);

  useEffect(() => {
    const el = canvas.current;
    const gl = el?.getContext("webgl", { antialias: true, alpha: false });
    if (!el || !gl) { setError("Este visor requiere WebGL. Las formas siguen disponibles como puntos en el mapa."); return; }
    const buffers: WebGLBuffer[] = [], shaders: WebGLShader[] = [];
    let program: WebGLProgram | null = null, frame = 0, dead = false;
    try {
      const shader = (type: number, source: string) => {
        const s = gl.createShader(type)!; shaders.push(s);
        gl.shaderSource(s, source); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(s) ?? "shader");
        return s;
      };
      program = gl.createProgram()!;
      gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX));
      gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program) ?? "program");
      gl.useProgram(program);
      gl.enable(gl.DEPTH_TEST);
      gl.clearColor(0.965, 0.968, 0.977, 1);
      const attributes = ["position", "normal", "color"].map((name) => gl.getAttribLocation(program!, name));
      const rotation = gl.getUniformLocation(program, "rotation"), scale = gl.getUniformLocation(program, "scale");
      const meshes = new Map(visible.map((f) => {
        const m = mesh(f.kind, "medium");
        const data = [m.positions, m.normals, m.colors].map((values) => {
          const b = gl.createBuffer()!; buffers.push(b);
          gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW);
          return b;
        });
        return [f.kind, { data, count: m.vertexCount }] as const;
      }));
      const draw = () => {
        frame = 0;
        if (dead) return;
        const rect = el.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = Math.max(1, Math.round(rect.width * dpr)), h = Math.max(1, Math.round(rect.height * dpr));
        if (el.width !== w || el.height !== h) { el.width = w; el.height = h; }
        gl.viewport(0, 0, w, h);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        const { yaw, pitch } = camera.current;
        const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
        gl.uniformMatrix3fv(rotation, false, new Float32Array([cy, sy * sp, -sy * cp, -sy, cy * sp, -cy * cp, 0, cp, sp]));
        visible.forEach((f, i) => {
          const vw = Math.floor(w / columns), vh = Math.floor(h / rows), x = (i % columns) * vw, y = h - (Math.floor(i / columns) + 1) * vh;
          gl.viewport(x, y, vw, vh);
          gl.uniform2f(scale, 0.57 * zoom * Math.min(1, vh / vw), 0.57 * zoom * Math.min(1, vw / vh));
          const m = meshes.get(f.kind)!;
          m.data.forEach((b, j) => { gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.enableVertexAttribArray(attributes[j]); gl.vertexAttribPointer(attributes[j], 3, gl.FLOAT, false, 0, 0); });
          gl.drawArrays(gl.TRIANGLES, 0, m.count);
        });
      };
      camera.current.redraw = () => { if (!dead && !frame) frame = requestAnimationFrame(draw); };
      const observer = new ResizeObserver(() => camera.current.redraw());
      observer.observe(el);
      camera.current.redraw();
      return () => {
        dead = true; cancelAnimationFrame(frame); observer.disconnect();
        buffers.forEach((b) => gl.deleteBuffer(b)); shaders.forEach((s) => gl.deleteShader(s));
        if (program) gl.deleteProgram(program);
      };
    } catch (e) {
      setError("No se pudo iniciar el visor 3D en este dispositivo. " + (e as Error).message);
    }
  }, [kind, zoom, camera, visible, columns, rows]);

  function rotate(dx: number, dy: number) {
    camera.current.yaw += dx;
    camera.current.pitch = Math.max(-1.4, Math.min(1.4, camera.current.pitch + dy));
    camera.current.redraw();
  }
  const drag = useRef<[number, number] | null>(null);

  if (error) return <p className="viz-note" role="alert">{error}</p>;
  return (
    <div className={`model-viewer-stage${kind === "all" ? "" : " single"}`}>
      <canvas ref={canvas} tabIndex={0} aria-label="Modelos 3D interactivos. Arrastra para rotar o usa las flechas del teclado."
              onPointerDown={(e) => { drag.current = [e.clientX, e.clientY]; e.currentTarget.setPointerCapture(e.pointerId); }}
              onPointerMove={(e) => { if (!drag.current) return; rotate((e.clientX - drag.current[0]) * 0.009, (e.clientY - drag.current[1]) * 0.009); drag.current = [e.clientX, e.clientY]; }}
              onPointerUp={() => (drag.current = null)} onPointerCancel={() => (drag.current = null)}
              onKeyDown={(e) => {
                const step: Record<string, [number, number]> = { ArrowLeft: [-0.12, 0], ArrowRight: [0.12, 0], ArrowUp: [0, 0.12], ArrowDown: [0, -0.12] };
                if (!step[e.key]) return;
                e.preventDefault(); rotate(...step[e.key]);
              }} />
      <div className="model-viewer-labels" aria-hidden="true" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }}>
        {visible.map((f) => <span key={f.kind}>{f.label}{f.symbolic ? " *" : ""}</span>)}
      </div>
    </div>
  );
}

export function ModelViewer({ onClose, initial = "all" }: { onClose: () => void; initial?: ModelKind | "all" }) {
  const panel = useRef<HTMLElement>(null);
  const [kind, setKind] = useState<ModelKind | "all">(initial);
  const [zoom, setZoom] = useState(START.zoom);
  const camera = useRef({ yaw: START.yaw, pitch: START.pitch, redraw: () => {} });

  useEffect(() => { setKind(initial); }, [initial]);
  useEffect(() => { panel.current?.focus({ preventScroll: true }); panel.current?.scrollIntoView({ block: "nearest" }); }, []);

  return (
    <section ref={panel} className="model-viewer" aria-labelledby="model-viewer-title" tabIndex={-1}
             onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="model-viewer-heading">
        <h2 id="model-viewer-title">Modelos 3D</h2>
        <button type="button" onClick={onClose} aria-label="Cerrar visor">Cerrar</button>
      </div>
      <p>
        {MODEL_FORMS.length} formas estandarizadas, cada una con su representación propia. Changing, Formation, Cloud, Light, Fireball,
        Flash, Star, Other y Unknown (marcadas con *) son símbolos interpretativos: no reconstruyen objetos verificados.
      </p>
      <div className="model-viewer-toolbar">
        <label>Forma{" "}
          <select value={kind} onChange={(e) => setKind(e.target.value as ModelKind | "all")}>
            <option value="all">Todas, {MODEL_FORMS.length} formas</option>
            {MODEL_FORMS.map((f) => <option key={f.kind} value={f.kind}>{f.label}</option>)}
          </select>
        </label>
        <label>Acercamiento{" "}
          <input type="range" min="0.7" max="1.6" step="0.05" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
        </label>
        <button type="button" onClick={() => { camera.current.yaw = START.yaw; camera.current.pitch = START.pitch; setZoom(START.zoom); camera.current.redraw(); }}>
          Restablecer vista
        </button>
      </div>
      {/* Mounted only while shown: the WebGL context exists only then. */}
      <Stage kind={kind} zoom={zoom} camera={camera} />
      <p className="viz-note">Arrastra para rotar, flechas para girar, elige una forma para verla en detalle.</p>
    </section>
  );
}
