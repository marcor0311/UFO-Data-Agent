"use client";

import type { ComponentType } from "react";
import type { Catalog, GoldResult, ViewCode } from "@/lib/contracts";
import { BarsView, HourWeekdayView, MonthCalendarView, TableView, TimeseriesView } from "./charts";
import { ChoroplethView, DensityView, PointsView } from "./maps";

type View = ComponentType<{ result: GoldResult; catalog: Catalog | null }>;

/* Client registry, aligned with VIEWS in scripts/gold_query.py. */
export const VIEW_REGISTRY: Record<ViewCode, View> = {
  table: TableView,
  bars: BarsView,
  timeseries: TimeseriesView,
  points: PointsView,
  density: DensityView,
  choropleth: ChoroplethView,
  hour_weekday: HourWeekdayView,
  month_calendar: MonthCalendarView,
};

export function Visualization({ result, catalog }: { result: GoldResult; catalog: Catalog | null }) {
  const Render = VIEW_REGISTRY[result.view] ?? TableView;
  return <Render result={result} catalog={catalog} />;
}
