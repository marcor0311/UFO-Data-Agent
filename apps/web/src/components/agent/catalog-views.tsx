import type { Catalog, ViewCode } from "@/lib/contracts";

const viewPaths: Record<ViewCode, string> = {
  table: "M3 2.75h10a1 1 0 0 1 1 1v8.5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-8.5a1 1 0 0 1 1-1ZM2 6.25h12M2 9.75h12M6.5 6.25v7",
  bars: "M2.5 4.5h8M2.5 8h11M2.5 11.5h5.5",
  timeseries: "m2 12.5 3.5-4.5 3 2.5L14 4",
  points: "M8 14s4-3.6 4-7.5a4 4 0 0 0-8 0C4 10.4 8 14 8 14Zm.75-7.5a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z",
  density: "M2.5 2.5h11v11h-11zM6.2 2.5v11M9.8 2.5v11M2.5 6.2h11M2.5 9.8h11",
  choropleth: "m2 4.5 4-2 4 2 4-2v9l-4 2-4-2-4 2zM6 2.5v9M10 4.5v9",
  hour_weekday: "M2.5 4.5h11v9h-11zM5 2.5v4M11 2.5v4M2.5 7.5h11M6.2 7.5v6M9.8 7.5v6M2.5 10.5h11",
  month_calendar: "M2.5 2.5h11v11h-11zM2.5 5.5h11M2.5 8.5h11M2.5 11.5h11M6.2 5.5v8M9.8 5.5v8",
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
