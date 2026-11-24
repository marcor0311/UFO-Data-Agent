/* Helpers compartidos por los prototipos: carga de datos, proyección, fondo de mapa y reproducción. */
const PALETA = { fondo: "#0b1016", tierra: "#16212d", borde: "#2a3a4b", texto: "#f0f3f6", tenue: "#b6c2cf", acento: "#c6d9e9" };
async function datos(nombre) { return (await fetch(`data/${nombre}`)).json(); }
const fmt = (n) => Math.round(n).toLocaleString("es-ES").replace(/ /g, ".");

/* Proyección equirectangular simple sobre un canvas. */
function proyeccion(w, h, caja = [-180, -60, 180, 80]) {
  const [x0, y0, x1, y1] = caja;
  return ([lng, lat]) => [((lng - x0) / (x1 - x0)) * w, h - ((lat - y0) / (y1 - y0)) * h];
}

function dibujarMundo(ctx, mundo, proy) {
  ctx.fillStyle = PALETA.tierra; ctx.strokeStyle = PALETA.borde; ctx.lineWidth = 0.6;
  const cruza = (anillo) => anillo.some((p, i) => i && Math.abs(p[0] - anillo[i - 1][0]) > 180);
  const trazar = (poly, mover) => {
    ctx.beginPath();
    for (const anillo of poly) anillo.forEach((p, i) => { const [x, y] = proy([mover(p[0]), p[1]]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.fill(); ctx.stroke();
  };
  for (const f of mundo.features) {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const poly of polys) {
      if (!poly.some(cruza)) { trazar(poly, (x) => x); continue; }
      /* Anillos que cruzan el antimeridiano: se dibujan desplazados ±360° y cada mitad queda en su lado. */
      trazar(poly, (x) => (x < 0 ? x + 360 : x));
      trazar(poly, (x) => (x > 0 ? x - 360 : x));
    }
  }
}

/* Bucle de animación con pausa: llama a paso(t) con t en [0,1] durante `ms` y repite. */
function reproducir(paso, ms, { repetir = true } = {}) {
  let inicio = performance.now(), pausa = false, offset = 0;
  const boton = document.querySelector("[data-play]");
  if (boton) boton.onclick = () => { pausa = !pausa; boton.textContent = pausa ? "Reproducir" : "Pausa"; if (!pausa) inicio = performance.now() - offset; };
  function frame(now) {
    if (!pausa) {
      offset = now - inicio;
      let t = Math.max(0, offset / ms);
      if (t >= 1) { if (repetir) { inicio = now; t = 0; } else t = 1; }
      paso(t);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
