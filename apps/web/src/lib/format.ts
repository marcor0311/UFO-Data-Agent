import type { Catalog, Row, Scalar } from "./contracts";

const integer = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0, useGrouping: true });
const decimal = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2, useGrouping: true });
const compactFmt = new Intl.NumberFormat("es-ES", { notation: "compact", maximumFractionDigits: 1 });

/* es-ES omits the separator for four-digit numbers; the project writes 1.234. */
function group(text: string): string {
  return text.replace(/^(-?)(\d)(\d{3})(?=,|$)/, "$1$2.$3");
}

export function num(value: Scalar | undefined): string {
  if (value === null || value === undefined) return "—";
  if (typeof value !== "number") return String(value);
  return group(Number.isInteger(value) ? integer.format(value) : decimal.format(value));
}

export function compact(value: number): string {
  return Math.abs(value) < 10000 ? num(value) : compactFmt.format(value);
}

export function metricLabel(catalog: Catalog | null, code: string): string {
  return catalog?.metrics[code]?.label ?? code;
}

export function dimensionLabel(catalog: Catalog | null, code: string): string {
  return catalog?.dimensions[code]?.label ?? code;
}

/** Display value of a dimension cell: the Spanish label the API attached, or the raw value. */
export function cell(row: Row, column: string): string {
  const label = row[column + "_label"];
  if (typeof label === "string") return label;
  const value = row[column];
  return value === null || value === undefined ? "sin dato" : typeof value === "number" ? num(value) : String(value);
}

export function isMetric(catalog: Catalog | null, column: string): boolean {
  return Boolean(catalog?.metrics[column]);
}

export function percent(metric: string, catalog: Catalog | null): boolean {
  return catalog?.metrics[metric]?.unit === "%";
}
