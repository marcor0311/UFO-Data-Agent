import snapshot from "./california-1990.json";

const { west, east, north, south, columns, rows, heights } = snapshot.terrain;
const eastWest = 1.05;
const northSouth = 1.12;
const relief = 0.000056;
const diagonal = Math.hypot(eastWest, northSouth);

export const maxReliefPitch = 0.93;
export type Camera = { yaw: number; pitch: number; zoom: number; panX: number; panY: number; overhead: boolean };
export type ReportPoint = { month: number | null; longitude: number; latitude: number };
type Vertex = { x: number; z: number; elevation: number };

function terrainVertex(column: number, row: number, elevation: number): Vertex {
  return { x: (column / (columns - 1) - 0.5) * eastWest, z: (row / (rows - 1) - 0.5) * northSouth, elevation };
}

function geographicVertex(longitude: number, latitude: number) {
  const column = (longitude - west) / (east - west) * (columns - 1);
  const row = (north - latitude) / (north - south) * (rows - 1);
  const x = Math.floor(column);
  const y = Math.floor(row);
  const interpolate = (a: number, b: number, t: number) => a + (b - a) * t;
  const top = interpolate(heights[y * columns + x], heights[y * columns + x + 1], column - x);
  const bottom = interpolate(heights[(y + 1) * columns + x], heights[(y + 1) * columns + x + 1], column - x);
  return terrainVertex(column, row, interpolate(top, bottom, row - y));
}

const vertices = heights.map((height, index) => terrainVertex(index % columns, Math.floor(index / columns), height));
const faces: { indices: [number, number, number, number]; color: string }[] = [];

for (let row = 0; row < rows - 1; row++) {
  for (let column = 0; column < columns - 1; column++) {
    const a = row * columns + column;
    const b = a + 1;
    const c = b + columns;
    const d = c - 1;
    const elevation = (heights[a] + heights[b] + heights[c] + heights[d]) / 4;
    const shade = Math.max(-8, Math.min(8, (heights[a] + heights[d] - heights[b] - heights[c]) / 85));
    const light = elevation > 0 ? 25 + Math.min(elevation, 3400) * 0.0075 + shade : Math.max(13, 22 + elevation / 480);
    const color = elevation > 0 ? `hsl(205 25% ${light}%)` : `hsl(211 55% ${light}%)`;
    faces.push({ indices: [a, b, c, d], color });
  }
}

// Split long boundary segments so they follow the sampled terrain.
const outlines = snapshot.outline.map((ring) => ring.flatMap(([lng, lat], i) => {
  if (!i) return [geographicVertex(lng, lat)];
  const [previousLng, previousLat] = ring[i - 1];
  const steps = Math.ceil(Math.hypot(lng - previousLng, lat - previousLat) / 0.11) || 1;
  return Array.from({ length: steps }, (_, index) => {
    const ratio = (index + 1) / steps;
    return geographicVertex(previousLng + (lng - previousLng) * ratio, previousLat + (lat - previousLat) * ratio);
  });
}));

const cities = [
  { name: "San Francisco", position: geographicVertex(-122.42, 37.77), offset: -9 },
  { name: "Los Ángeles", position: geographicVertex(-118.24, 34.05), offset: 9 },
  { name: "Sacramento", position: geographicVertex(-121.49, 38.58), offset: 9 },
];

export function drawTerrain(ctx: CanvasRenderingContext2D, width: number, height: number, camera: Camera, reports: ReportPoint[]) {
  const yaw = camera.overhead ? 0 : camera.yaw;
  const pitch = camera.overhead ? Math.PI / 2 : camera.pitch;
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  // Fit each view once so rotating or tilting does not also change the zoom.
  const fitWidth = camera.overhead ? eastWest : diagonal;
  const fitHeight = camera.overhead ? northSouth : diagonal * Math.sin(maxReliefPitch) + 0.16;
  const framing = camera.overhead ? 1 : 1.75;
  const scale = Math.min(width * 0.9 / fitWidth, height * 0.9 / fitHeight) * framing * camera.zoom;
  const centerX = width * (0.5 + camera.panX);
  const centerY = height * ((camera.overhead ? 0.5 : 0.54) + camera.panY);
  function project({ x, z, elevation }: Vertex, offset = 0) {
    const away = x * sinYaw + z * cosYaw;
    const altitude = Math.max(0, elevation) * relief + offset;
    return {
      x: centerX + scale * (x * cosYaw - z * sinYaw),
      y: centerY + scale * (away * sinPitch - altitude * cosPitch),
      depth: away * cosPitch + altitude * sinPitch,
    };
  }

  const projected = vertices.map((vertex) => project(vertex));
  const sortedFaces = faces.map(({ indices, color }) => ({
    indices,
    color,
    depth: indices.reduce((sum, index) => sum + projected[index].depth, 0),
  })).sort((a, b) => a.depth - b.depth);

  ctx.clearRect(0, 0, width, height);
  ctx.lineJoin = "round";
  ctx.lineWidth = 0.85;
  for (const { indices: [a, b, c, d], color } of sortedFaces) {
    ctx.beginPath();
    ctx.moveTo(projected[a].x, projected[a].y);
    ctx.lineTo(projected[b].x, projected[b].y);
    ctx.lineTo(projected[c].x, projected[c].y);
    ctx.lineTo(projected[d].x, projected[d].y);
    ctx.closePath();
    ctx.fillStyle = ctx.strokeStyle = color;
    ctx.fill();
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(176, 213, 226, .82)";
  ctx.lineWidth = 1.1;
  for (const ring of outlines) {
    ctx.beginPath();
    ring.forEach((vertex, index) => {
      const point = project(vertex, 0.003);
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
    ctx.stroke();
  }

  for (const { longitude, latitude } of reports) {
    const point = project(geographicVertex(longitude, latitude), 0.004);
    ctx.beginPath();
    ctx.arc(point.x, point.y, 3.25, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(12, 21, 29, .9)";
    ctx.lineWidth = 1.1;
    ctx.fillStyle = "#efc480";
    ctx.fill();
    ctx.stroke();
  }

  ctx.font = "500 12px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 3;
  for (const { name, position, offset } of cities) {
    const point = project(position, 0.006);
    ctx.textAlign = offset < 0 ? "right" : "left";
    ctx.strokeStyle = "#10202f";
    ctx.fillStyle = "#e0edf3";
    ctx.strokeText(name, point.x + offset, point.y - 8);
    ctx.fillText(name, point.x + offset, point.y - 8);
  }
}
