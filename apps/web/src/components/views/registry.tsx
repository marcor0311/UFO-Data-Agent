"use client";

import { useMemo, type ComponentType } from "react";
import type { Catalog, GoldResult, ViewCode } from "@/lib/contracts";
import { BarsView, HourWeekdayView, MonthCalendarView, TableView, TimeseriesView } from "./charts";
import { ChoroplethView, DensityView, GlobeView, PointsView } from "./maps";
import { DumbbellView, EcdfView, HistogramView, MatrixView, StackedView, TimelineView } from "./proposals";
import { BoxplotView, BumpView, ClustersView, CompareView, CurveView, FunnelView, LinksView, ScatterView, UpsetView, WaterfallView } from "./analysis-views";

type View = ComponentType<{ result: GoldResult; catalog: Catalog | null }>;

/* Client registry, aligned with VIEWS in scripts/gold_query.py. */
export const VIEW_REGISTRY: Record<ViewCode, View> = {
  table: TableView,
  bars: BarsView,
  timeseries: TimeseriesView,
  points: PointsView,
  density: DensityView,
  globe: GlobeView,
  choropleth: ChoroplethView,
  hour_weekday: HourWeekdayView,
  month_calendar: MonthCalendarView,
  stacked: StackedView,
  matrix: MatrixView,
  dumbbell: DumbbellView,
  timeline: TimelineView,
  histogram: HistogramView,
  ecdf: EcdfView,
  boxplot: BoxplotView,
  scatter: ScatterView,
  waterfall: WaterfallView,
  bump: BumpView,
  curve: CurveView,
  clusters: ClustersView,
  links: LinksView,
  funnel: FunnelView,
  upset: UpsetView,
  compare: CompareView,
};

/** The catalog plus the derived metrics an analysis brings (labels and percentage unit). */
export function withResultMetrics(catalog: Catalog | null, result: GoldResult): Catalog | null {
  const extra = result.metric_labels;
  if (!catalog || !extra) return catalog;
  const metrics = { ...catalog.metrics };
  for (const [code, label] of Object.entries(extra)) {
    if (!metrics[code]) metrics[code] = { label, type: "non_additive", unit: code.endsWith("_pct") ? "%" : "" };
  }
  return { ...catalog, metrics };
}

export function Visualization({ result, catalog }: { result: GoldResult; catalog: Catalog | null }) {
  const Render = VIEW_REGISTRY[result.view] ?? TableView;
  const local = useMemo(() => withResultMetrics(catalog, result), [catalog, result]);
  return <Render result={result} catalog={local} />;
}
