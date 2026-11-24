import type { Catalog, ViewCode } from "@/lib/contracts";

const viewPaths: Record<ViewCode, string> = {
  table: "M3 2.75h10a1 1 0 0 1 1 1v8.5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-8.5a1 1 0 0 1 1-1ZM2 6.25h12M2 9.75h12M6.5 6.25v7",
  bars: "M2.5 4.5h8M2.5 8h11M2.5 11.5h5.5",
  timeseries: "m2 12.5 3.5-4.5 3 2.5L14 4",
  points: "M8 14s4-3.6 4-7.5a4 4 0 0 0-8 0C4 10.4 8 14 8 14Zm.75-7.5a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z",
  density: "M2.5 2.5h11v11h-11zM6.2 2.5v11M9.8 2.5v11M2.5 6.2h11M2.5 9.8h11",
  globe: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM2 8h12M8 2c-2.2 2.4-2.2 9.6 0 12M8 2c2.2 2.4 2.2 9.6 0 12",
  choropleth: "m2 4.5 4-2 4 2 4-2v9l-4 2-4-2-4 2zM6 2.5v9M10 4.5v9",
  hour_weekday: "M2.5 4.5h11v9h-11zM5 2.5v4M11 2.5v4M2.5 7.5h11M6.2 7.5v6M9.8 7.5v6M2.5 10.5h11",
  month_calendar: "M2.5 2.5h11v11h-11zM2.5 5.5h11M2.5 8.5h11M2.5 11.5h11M6.2 5.5v8M9.8 5.5v8",
  stacked: "M3 13.5V3M3 13.5h10.5M5.5 11.5v-3h2v3zM9 11.5V6h2v5.5zM5.5 8.5v-2h2v2zM9 6V4h2v2z",
  matrix: "M2.5 2.5h11v11h-11zM2.5 6.2h11M2.5 9.8h11M6.2 2.5v11M9.8 2.5v11",
  dumbbell: "M4 4.5h8M4 8h5M6 11.5h6M4 4.5h.01M12 4.5h.01M4 8h.01M9 8h.01M6 11.5h.01M12 11.5h.01",
  timeline: "M8 2v12M8 4h4M4 8h4M8 12h4",
  histogram: "M2.5 13.5h11M3.5 13.5V9h2v4.5M6.5 13.5V5h2v8.5M9.5 13.5V7h2v6.5",
  ecdf: "M2.5 13.5h11M2.5 13.5V2.5M3 12h2V8h2V5h3V3.5h3.5",
};

export function CatalogViews({ views }: { views: Catalog["views"] }) {
  return (
    <ul className="catalog-views" aria-label="Tipos de resultado disponibles">
      {(Object.entries(views) as [ViewCode, Catalog["views"][ViewCode]][]).map(([key, view]) => (
        <li key={key}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
               strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
            <path d={viewPaths[key] ?? viewPaths.table} />
          </svg>
          <strong>{view.label}</strong>
          <span>{view.description}</span>
        </li>
      ))}
    </ul>
  );
}
