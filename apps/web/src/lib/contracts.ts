/* Types of the Gold result envelope (scripts/gold_query.py, docs/gold-contract.md)
   and of the agent API (apps/api/src/app/agent/routes.py). */

export type ViewCode = "table" | "bars" | "timeseries" | "points" | "density" | "choropleth" | "hour_weekday" | "month_calendar"
  | "stacked" | "matrix" | "dumbbell" | "timeline" | "histogram" | "ecdf" | "globe";
export type Scalar = string | number | boolean | null;
export type Row = Record<string, Scalar>;

export type Filter = { column: string; op?: "eq" | "ne" | "in" | "gte" | "lte" | "is_null"; value?: Scalar | Scalar[] };
export type GoldQuery = {
  dataset: string; filters: Filter[]; group_by: string[]; metrics: string[]; columns: string[]; eligibility: string[];
  view: ViewCode; title: string | null; order_by: string | null; descending: boolean; limit: number; rollup: boolean;
};
export type Limitation = { code: string; text: string };
export type ExclusionReason = { reason: string; label: string; reports: number };
export type Exclusions = { scope: string; base_reports: number; eligible_reports: number; excluded_reports: number; excluded_by_reason: ExclusionReason[] };
export type CertificationStatus = { valid: boolean; reasons: string[]; query_sha256: string; verified_load_id: string | null; verified_at: string | null };

export type GoldResult = {
  result_type: "certified" | "composed";
  certified_query_id: string | null;
  certification: CertificationStatus | null;
  view: ViewCode; view_label: string; title: string | null;
  rows: Row[]; total: Row | null; truncated: boolean; row_count: number; matched_source_rows: number; empty: boolean;
  /* month_calendar only: reports in the period, with a reliable month and without one. */
  calendar_totals?: { reports: number; with_month: number; without_month: number };
  /* histogram / ecdf only: one-minute bins up to max_minutes, the upper tail and reports without duration. */
  distribution?: { bins: { from_s: number; to_s: number; report_count: number }[]; over_max: number; without_duration: number;
    with_duration: number; max_minutes: number };
  eligibility_applied: { code: string; label: string; flag: string; implied: boolean }[];
  exclusions: Exclusions | null;
  external_evidence_reports: number | null;
  readable_query: { dataset: string; filtros: string[]; agrupado_por: string[]; metricas: string[]; elegibilidad: string[]; orden: string; limite: number; texto: string };
  query: GoldQuery;
  provenance: { gold_load_id: string; gold_sha256: string; silver_sha256: string; bronze_sha256: string; definitions_sha256: string;
                query_engine_sha256: string; serving_sha256: string; dataset: string; query_sha256: string };
  snapshot: { gold_built_at: string; silver_reference_date: string | null; label: string };
  limitations: Limitation[];
};

export type MetricInfo = { label: string; type: "additive" | "ratio" | "non_additive"; unit: string; denominator?: string };
export type CertifiedSummary = { id: string; title: string; description: string; examples: string[]; recommended_views: ViewCode[]; limitation: string; valid: boolean };
export type Catalog = {
  load_id: string;
  datasets: Record<string, { label: string; grain: string; eligibility: string[]; rows: number }>;
  views: Record<ViewCode, { label: string; datasets: string[] | "*"; description: string }>;
  metrics: Record<string, MetricInfo>;
  dimensions: Record<string, { label: string }>;
  eligibility: Record<string, string>;
  certified_queries: CertifiedSummary[];
  limitations: Limitation[];
  country_m49: Record<string, string>;
};

export type TraceStep = { tool: string; ok: boolean; code?: string; error?: string; arguments?: unknown };
export type Turn = { question: string; answer: string; visualizations: GoldResult[]; trace: TraceStep[]; model: string; load_id: string; created_at: string;
  /* Area selected on a map when the question was asked ([lng, lat] vertices). */
  area?: [number, number][] };
export type Session = { authenticated: boolean; email?: string; account_id?: string; detail?: string };
export type Model = { slug: string; display_name: string };
export type ConversationSummary = { conversation_id: string; updated: number; title: string; turns: number };
