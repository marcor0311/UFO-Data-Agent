/* Solid UAP models per standardized shape, ported from DB Test/mapas-analiticos.js.
   Procedural meshes, no network or GPU needed to build them. Symbolic shapes
   (Light, Cloud, Formation…) are representations, not physical reconstructions. */

type Vec3 = [number, number, number];
export type Detail = "low" | "medium" | "high";
export type Mesh = {
  positions: Float32Array; normals: Float32Array; colors: Float32Array; vertexCount: number;
  topology: "triangle-list";
  attributes: { POSITION: { size: 3; value: Float32Array }; NORMAL: { size: 3; value: Float32Array }; COLOR_0: { size: 3; value: Float32Array } };
};

export const MODEL_LIMITS = { maxModels: 60, maxTriangles: 18000 } as const;
const DETAILS = {
  low: { longitude: 14, latitude: 10, radial: 16, corner: 2 },
  medium: { longitude: 20, latitude: 12, radial: 24, corner: 4 },
  high: { longitude: 28, latitude: 16, radial: 40, corner: 6 },
} as const;

const SYMBOLIC = ["Changing", "Formation", "Light", "Fireball", "Flash", "Cloud", "Star", "Other", "Unknown"];
export const MODEL_FORMS = ([
  ["boomerang", "Boomerang"], ["changing", "Changing"], ["chevron", "Chevron"], ["cigar", "Cigar"], ["circle", "Circle"],
  ["cloud", "Cloud"], ["cone", "Cone"], ["crescent", "Crescent"], ["cross", "Cross"], ["cube", "Cube"], ["cylinder", "Cylinder"],
  ["diamond", "Diamond"], ["disc", "Disc"], ["dome", "Dome"], ["egg", "Egg"], ["fireball", "Fireball"], ["flash", "Flash"],
  ["formation", "Formation"], ["light", "Light"], ["other", "Other"], ["oval", "Oval"], ["rectangle", "Rectangle"],
  ["saucer", "Saucer"], ["sphere", "Sphere"], ["star", "Star"], ["teardrop", "Teardrop"], ["triangle", "Triangle"], ["unknown", "Unknown"],
] as const).map(([kind, label]) => ({ kind, label, symbolic: SYMBOLIC.includes(label) }));
export type ModelKind = (typeof MODEL_FORMS)[number]["kind"];
const KINDS = new Set<string>(MODEL_FORMS.map((f) => f.kind));

const normal = (s: unknown) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const ALIASES: Record<string, ModelKind> = { disk: "disc", disco: "disc", triangulo: "triangle", luz: "light" };

/** Model for a Gold shape_code (e.g. "Disc"); null when it has no model (keeps its point). */
const SPANISH: Record<string, ModelKind> = {
  esfera: "sphere", cigarro: "cigar", puro: "cigar", circulo: "circle", nube: "cloud", cono: "cone", "media luna": "crescent",
  cruz: "cross", cubo: "cube", cilindro: "cylinder", diamante: "diamond", rombo: "diamond", cupula: "dome", huevo: "egg",
  "bola de fuego": "fireball", destello: "flash", formacion: "formation", otra: "other", otro: "other", ovalo: "oval",
  rectangulo: "rectangle", platillo: "saucer", estrella: "star", lagrima: "teardrop", desconocida: "unknown", cambiante: "changing",
};

/** Catalog request typed in the chat ("ver modelos 3d", "muéstrame el modelo 3d del disco").
    Returns the shape to open ("all" for the whole catalog), or null when it is a data question
    (reports, places, counts), which must still go to the agent. */
export function modelCatalogIntent(text: string): ModelKind | "all" | null {
  const n = normal(text);
  const asks = /\b(modelos?|formas?|figuras?|objetos?)\s*(en\s*)?(3d|tridimensional(es)?)\b|\bcatalogo\s+de\s+(modelos|formas)\b|\bvisor\s+de\s+modelos\b/.test(n);
  if (!asks || /\b(reportes?|informes?|avistamientos?|casos?|mapa|cuantos?|cuantas?)\b/.test(n)) return null;
  for (const [word, kind] of Object.entries({ ...SPANISH, ...ALIASES })) if (new RegExp(`\\b${word}\\b`).test(n)) return kind;
  for (const f of MODEL_FORMS) if (new RegExp(`\\b${f.kind}\\b`).test(n)) return f.kind;
  return "all";
}

export function shapeKind(shape: unknown): ModelKind | null {
  const n = normal(shape);
  return KINDS.has(n) ? (n as ModelKind) : ALIASES[n] ?? null;
}

const cache = new Map<string, Mesh>();

export function mesh(kind: ModelKind, detail: Detail = "medium"): Mesh {
  const key = `${kind}:${detail}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const settings = DETAILS[detail];
  const positions: number[] = [];
  const normals: number[] = [];

  function tri(a: Vec3, b: Vec3, c: Vec3, smooth?: (p: Vec3) => Vec3) {
    const u = b.map((v, i) => v - a[i]);
    const v = c.map((x, i) => x - a[i]);
    const n: Vec3 = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const l = Math.hypot(...n);
    if (l < 1e-10) return;
    for (const p of [a, b, c]) {
      positions.push(...p);
      normals.push(...(smooth ? smooth(p) : (n.map((x) => x / l) as Vec3)));
    }
  }
  function append(source: Mesh, scale: Vec3 = [1, 1, 1], offset: Vec3 = [0, 0, 0], angle = 0) {
    const c = Math.cos(angle), s = Math.sin(angle);
    for (let i = 0; i < source.positions.length; i += 3) {
      const x = source.positions[i] * scale[0], y = source.positions[i + 1] * scale[1];
      positions.push(c * x - s * y + offset[0], s * x + c * y + offset[1], source.positions[i + 2] * scale[2] + offset[2]);
      const nx = source.normals[i] / scale[0], ny = source.normals[i + 1] / scale[1], nz = source.normals[i + 2] / scale[2];
      const l = Math.hypot(nx, ny, nz);
      normals.push((c * nx - s * ny) / l, (s * nx + c * ny) / l, nz / l);
    }
  }
  function box(size: Vec3 = [1, 1, 1], offset: Vec3 = [0, 0, 0], angle = 0) {
    const v = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]].map((p) => {
      const x = (p[0] * size[0]) / 2, y = (p[1] * size[1]) / 2;
      return [x * Math.cos(angle) - y * Math.sin(angle) + offset[0], x * Math.sin(angle) + y * Math.cos(angle) + offset[1], (p[2] * size[2]) / 2 + offset[2]] as Vec3;
    });
    for (const [a, b, c, d] of [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]) {
      tri(v[a], v[b], v[c]);
      tri(v[a], v[c], v[d]);
    }
  }
  function surface(fn: (u: number, v: number) => Vec3, nu: number = settings.radial, nv: number = settings.latitude, invert = false) {
    const normalAt = (u: number, v: number): Vec3 => {
      const e = 0.0001;
      const du = fn(u + e, v).map((x, k) => x - fn(u - e, v)[k]);
      const dv = fn(u, Math.min(1, v + e)).map((x, k) => x - fn(u, Math.max(0, v - e))[k]);
      const n: Vec3 = [dv[1] * du[2] - dv[2] * du[1], dv[2] * du[0] - dv[0] * du[2], dv[0] * du[1] - dv[1] * du[0]];
      const length = Math.hypot(...n);
      return length < 1e-9 ? [0, 0, v < 0.5 ? 1 : -1] : (n.map((x) => (x / length) * (invert ? -1 : 1)) as Vec3);
    };
    for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
      const a = i / nu, b = (i + 1) / nu, c = j / nv, d = (j + 1) / nv;
      const pts: [number, number][] = [[a, c], [b, c], [b, d], [a, d]];
      const at = pts.map(([u, v]) => fn(u, v));
      const ns = pts.map(([u, v]) => normalAt(u, v));
      const face = (ids: number[]) => { let k = 0; tri(at[ids[0]], at[ids[1]], at[ids[2]], () => ns[ids[k++]]); };
      if (invert) { face([0, 1, 2]); face([0, 2, 3]); } else { face([0, 2, 1]); face([0, 3, 2]); }
    }
  }
  function lathe(profile: [number, number][]) {
    for (let j = 0; j < profile.length - 1; j++) for (let i = 0; i < settings.radial; i++) {
      const p = (a: number, k: number): Vec3 => [profile[k][0] * Math.cos(a), profile[k][0] * Math.sin(a), profile[k][1]];
      const a = (i / settings.radial) * Math.PI * 2, b = ((i + 1) / settings.radial) * Math.PI * 2;
      tri(p(a, j), p(b, j), p(b, j + 1));
      tri(p(a, j), p(b, j + 1), p(a, j + 1));
    }
  }
  function torus(radius = 0.75, tube = 0.1, start = 0, end = Math.PI * 2) {
    surface((u, v) => {
      const a = start + u * (end - start), b = v * Math.PI * 2;
      return [(radius + tube * Math.cos(b)) * Math.cos(a), (radius + tube * Math.cos(b)) * Math.sin(a), tube * Math.sin(b)];
    }, settings.radial, Math.max(6, Math.floor(settings.latitude / 2)), true);
  }
  const ball = (scale: Vec3 = [1, 1, 1], offset: Vec3 = [0, 0, 0]) => append(mesh("sphere", detail), scale, offset);

  if (kind === "triangle") {
    const corners: [number, number][] = [[0, 1.1], [-0.95, -0.65], [0.95, -0.65]];
    const ring: number[][] = [];
    for (let i = 0; i < 3; i++) {
      const v = corners[i], prev = corners[(i + 2) % 3], next = corners[(i + 1) % 3];
      const a = v.map((x, k) => x + (prev[k] - x) * 0.12), b = v.map((x, k) => x + (next[k] - x) * 0.12);
      for (let j = 0; j < settings.corner; j++) {
        const t = j / settings.corner;
        ring.push(v.map((x, k) => (1 - t) ** 2 * a[k] + 2 * t * (1 - t) * x + t * t * b[k]));
      }
    }
    const at = (p: number[], scale: number, z: number): Vec3 => [p[0] * scale, p[1] * scale, z];
    const rings: [number, number][] = [[0.92, -0.14], [1, -0.06], [1, 0.06], [0.92, 0.16]];
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      tri([0, 0, 0.16], at(a, 0.92, 0.16), at(b, 0.92, 0.16));
      tri([0, 0, -0.14], at(b, 0.92, -0.14), at(a, 0.92, -0.14));
      for (let k = 0; k < rings.length - 1; k++) {
        const [s, z] = rings[k], [t, w] = rings[k + 1];
        tri(at(a, s, z), at(b, s, z), at(b, t, w));
        tri(at(a, s, z), at(b, t, w), at(a, t, w));
      }
    }
  } else if (kind === "disc") {
    const profile: [number, number][] = [[0, -0.16], [0.5, -0.14], [0.95, -0.06], [1, 0], [0.77, 0.09], [0.4, 0.12], [0.28, 0.26], [0, 0.28]];
    for (let j = 0; j < profile.length - 1; j++) for (let i = 0; i < settings.radial; i++) {
      const point = (r: number, z: number, t: number): Vec3 => [r * Math.cos(t), r * Math.sin(t), z];
      const t = (i / settings.radial) * Math.PI * 2, u = ((i + 1) / settings.radial) * Math.PI * 2;
      const [r, z] = profile[j], [s, w] = profile[j + 1];
      const a = point(r, z, t), b = point(r, z, u), c = point(s, w, u), d = point(s, w, t);
      const smooth = (p: Vec3): Vec3 => {
        const radial = Math.hypot(p[0], p[1]), dz = w - z, dr = s - r, length = Math.hypot(dz, dr);
        return radial < 1e-8 ? [0, 0, z < 0 ? -1 : 1] : [(p[0] / radial) * dz / length, (p[1] / radial) * dz / length, -dr / length];
      };
      tri(a, b, c, smooth);
      tri(a, c, d, smooth);
    }
  } else if (kind === "sphere" || kind === "cigar") {
    const scales: Vec3 = kind === "cigar" ? [1.3, 0.32, 0.32] : [0.7, 0.7, 0.7];
    const p = (a: number, b: number): Vec3 => [Math.cos(a) * Math.sin(b) * scales[0], Math.sin(a) * Math.sin(b) * scales[1], Math.cos(b) * scales[2]];
    const smooth = (v: Vec3): Vec3 => { const n = v.map((x, k) => x / (scales[k] * scales[k])), l = Math.hypot(...n); return n.map((x) => x / l) as Vec3; };
    for (let j = 0; j < settings.latitude; j++) for (let i = 0; i < settings.longitude; i++) {
      const a = (i / settings.longitude) * Math.PI * 2, b = ((i + 1) / settings.longitude) * Math.PI * 2;
      const c = (j / settings.latitude) * Math.PI, d = ((j + 1) / settings.latitude) * Math.PI;
      tri(p(a, c), p(a, d), p(b, d), smooth);
      tri(p(a, c), p(b, d), p(b, c), smooth);
    }
  } else if (kind === "cube") box([1.25, 1.25, 1.25]);
  else if (kind === "rectangle") box([1.9, 0.85, 0.32]);
  else if (kind === "cross") { box([1.8, 0.38, 0.26]); box([0.38, 1.8, 0.26]); }
  else if (kind === "chevron") { box([1.2, 0.28, 0.22], [-0.43, 0, 0], Math.PI / 4); box([1.2, 0.28, 0.22], [0.43, 0, 0], -Math.PI / 4); }
  else if (kind === "boomerang") { for (let i = 0; i < 10; i++) { const a = -1.15 + (i * 2.3) / 9; box([0.33, 0.25, 0.16], [Math.sin(a), Math.cos(a) - 0.65, 0], -a); } }
  else if (kind === "circle") lathe([[0, -0.045], [0.95, -0.045], [0.95, 0.045], [0, 0.045]]);
  else if (kind === "cylinder") lathe([[0, -0.8], [0.38, -0.8], [0.38, 0.8], [0, 0.8]]);
  else if (kind === "cone") lathe([[0, -0.65], [0.7, -0.65], [0, 0.9]]);
  else if (kind === "dome") lathe([[0, -0.12], [0.9, -0.12], [0.88, 0.12], [0.75, 0.4], [0.5, 0.63], [0, 0.76]]);
  else if (kind === "saucer") lathe([[0, -0.3], [0.3, -0.26], [0.8, -0.12], [1, 0], [0.8, 0.12], [0.3, 0.26], [0, 0.3]]);
  else if (kind === "oval") ball([1.5, 0.8, 0.55]);
  else if (kind === "egg") surface((u, v) => { const a = u * Math.PI * 2, b = v * Math.PI, z = Math.cos(b); return [0.65 * Math.sin(b) * (1 - 0.22 * z) * Math.cos(a), 0.65 * Math.sin(b) * (1 - 0.22 * z) * Math.sin(a), 0.95 * z]; });
  else if (kind === "teardrop") lathe([[0, -0.65], [0.4, -0.6], [0.6, -0.3], [0.5, 0], [0.27, 0.4], [0, 1]]);
  else if (kind === "diamond") {
    const ring: Vec3[] = [[0.75, 0, 0], [0, 0.75, 0], [-0.75, 0, 0], [0, -0.75, 0]];
    for (let i = 0; i < 4; i++) { tri([0, 0, 0.85], ring[i], ring[(i + 1) % 4]); tri([0, 0, -0.6], ring[(i + 1) % 4], ring[i]); }
  } else if (kind === "crescent") torus(0.7, 0.16, 0.5, Math.PI * 2 - 0.5);
  else if (kind === "light") { ball([0.7, 0.7, 0.7]); torus(0.72, 0.045); }
  else if (kind === "fireball") { ball([0.8, 0.8, 0.8], [-0.35, 0, 0]); for (let i = 0; i < 3; i++) append(mesh("cigar", detail), [0.55, 0.17, 0.17], [0.6, i * 0.19 - 0.19, 0]); }
  else if (kind === "flash") { ball([0.28, 0.28, 0.28]); for (let i = 0; i < 8; i++) { const a = (i * Math.PI) / 4; box([0.65, 0.06, 0.06], [Math.cos(a) * 0.6, Math.sin(a) * 0.6, 0], a); } }
  else if (kind === "star") {
    const ring = Array.from({ length: 10 }, (_, i) => { const a = (i * Math.PI) / 5 + Math.PI / 2, r = i % 2 ? 0.4 : 1; return [Math.cos(a) * r, Math.sin(a) * r] as [number, number]; });
    for (let i = 0; i < 10; i++) {
      const a = ring[i], b = ring[(i + 1) % 10];
      tri([0, 0, 0.13], [...a, 0.13], [...b, 0.13]);
      tri([0, 0, -0.13], [...b, -0.13], [...a, -0.13]);
      tri([...a, -0.13], [...b, -0.13], [...b, 0.13]);
      tri([...a, -0.13], [...b, 0.13], [...a, 0.13]);
    }
  } else if (kind === "cloud") { for (const [x, y, z, r] of [[-0.5, 0, 0, 0.6], [0, 0, 0.2, 0.85], [0.55, 0, 0, 0.65], [0, 0.3, -0.25, 0.65]]) ball([r, r * 0.7, r * 0.7], [x, y, z]); }
  else if (kind === "formation") { for (let i = 0; i < 5; i++) ball([0.24, 0.24, 0.24], [(i - 2) * 0.44, Math.abs(i - 2) * 0.3, 0]); }
  else if (kind === "changing") surface((u, v) => { const a = u * Math.PI * 2, b = v * Math.PI, r = 0.72 + 0.17 * Math.sin(a * 3 + b * 2); return [r * Math.sin(b) * Math.cos(a), r * Math.sin(b) * Math.sin(a), r * Math.cos(b)]; });
  else if (kind === "other") { box([0.16, 1.2, 0.16], [-0.55, 0, 0]); box([0.16, 1.2, 0.16], [0.55, 0, 0]); box([1.2, 0.16, 0.16], [0, 0.55, 0]); ball([0.24, 0.24, 0.24]); box([1.2, 0.16, 0.16], [0, -0.55, 0]); }
  else if (kind === "unknown") { torus(0.45, 0.09, -0.15, Math.PI * 1.35); box([0.16, 0.45, 0.16], [-0.06, -0.53, 0]); ball([0.16, 0.16, 0.16], [-0.06, -0.98, 0]); }

  // Blue body, darker canopy on discs (current DB Test material). deck.gl reads {size, value} descriptors.
  const colors = new Float32Array(positions.length);
  for (let i = 0; i < positions.length; i++) {
    const canopy = kind === "disc" && positions[i - (i % 3) + 2] > 0.18;
    colors[i] = (canopy ? [0.055, 0.14, 0.34] : [0.11, 0.32, 0.72])[i % 3];
  }
  const vertices = new Float32Array(positions), directions = new Float32Array(normals);
  const value: Mesh = {
    positions: vertices, normals: directions, colors, topology: "triangle-list", vertexCount: vertices.length / 3,
    attributes: { POSITION: { size: 3, value: vertices }, NORMAL: { size: 3, value: directions }, COLOR_0: { size: 3, value: colors } },
  };
  cache.set(key, value);
  return value;
}

const triangles = (kind: ModelKind, detail: Detail) => mesh(kind, detail).positions.length / 9;

/** Which reports get a model within the triangle budget; the rest keep their point. */
export function planModels<T extends { kind: ModelKind }>(candidates: T[], zoom: number) {
  const eligible = candidates.slice(0, MODEL_LIMITS.maxModels);
  let detail: Detail = zoom >= 14 && eligible.length <= 12 ? "high" : zoom >= 11 && eligible.length <= 30 ? "medium" : "low";
  const cost = (level: Detail) => eligible.reduce((sum, r) => sum + triangles(r.kind, level), 0);
  while (cost(detail) > MODEL_LIMITS.maxTriangles && detail !== "low") detail = detail === "high" ? "medium" : "low";
  let used = 0;
  const rows: T[] = [];
  for (const row of eligible) {
    const count = triangles(row.kind, detail);
    if (used + count > MODEL_LIMITS.maxTriangles) continue;
    rows.push(row);
    used += count;
  }
  return { rows, detail };
}

const diameters = new Map<ModelKind, { diameter: number; bottom: number }>();
/** Diameter and lowest z of the high-detail mesh, to scale and lift models above ground. */
export function modelMetrics(kind: ModelKind) {
  const hit = diameters.get(kind);
  if (hit) return hit;
  const p = mesh(kind, "high").positions;
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < p.length; i++) { min[i % 3] = Math.min(min[i % 3], p[i]); max[i % 3] = Math.max(max[i % 3], p[i]); }
  const value = { diameter: Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]), bottom: min[2] };
  diameters.set(kind, value);
  return value;
}

/** MapLibre uses 512-px tiles: metres per screen pixel at a latitude and zoom. */
export const metersPerPixel = (lat: number, zoom: number) => (78271.51696402048 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
