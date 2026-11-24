import type { Filter, GoldResult } from "./contracts";

const setKey = (values: string[]) => JSON.stringify([...new Set(values)].sort());

function filterKey(filter: Filter) {
  const op = filter.op ?? "eq";
  const value = op === "in" && Array.isArray(filter.value)
    ? setKey(filter.value.map((item) => JSON.stringify(item)))
    : op === "is_null" ? filter.value !== false : filter.value;
  return JSON.stringify([filter.column, op, value]);
}

function sameScope(a: GoldResult, b: GoldResult) {
  return a.query.dataset === b.query.dataset
    && a.provenance.dataset === b.provenance.dataset
    && Boolean(a.provenance.gold_load_id) && a.provenance.gold_load_id === b.provenance.gold_load_id
    && setKey(a.query.filters.map(filterKey)) === setKey(b.query.filters.map(filterKey))
    && setKey(a.eligibility_applied.map((item) => item.code)) === setKey(b.eligibility_applied.map((item) => item.code))
    && setKey(a.query.metrics) === setKey(b.query.metrics);
}

function isSummary(result: GoldResult) {
  return result.view === "table" && result.query.group_by.length === 0
    && result.rows.length === 1 && result.query.metrics.length > 0 && result.query.metrics.length <= 2;
}

/** A comparison and its total share a population, effective eligibility, metrics and Gold load. */
export function groupResults(results: GoldResult[]) {
  const ordered = results.map((result, index) => ({ result, index }))
    .sort((a, b) => Number(a.result.view === "table") - Number(b.result.view === "table") || a.index - b.index);
  const groups: (typeof ordered)[] = [];
  while (ordered.length) {
    const entry = ordered.shift()!;
    const result = entry.result;
    const comparison = (result.view === "bars" || result.view === "table")
      && result.query.group_by.length > 0 && result.query.metrics.length > 0 && result.rows.length > 1;
    const companion = comparison
      ? ordered.findIndex((item) => isSummary(item.result) && sameScope(result, item.result))
      : -1;
    groups.push(companion < 0 ? [entry] : [entry, ...ordered.splice(companion, 1)]);
  }
  return groups;
}
