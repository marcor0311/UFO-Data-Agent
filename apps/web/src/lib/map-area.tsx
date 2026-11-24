"use client";

/* The area selected on a map (lasso or rectangle) stays active for the conversation:
   every following question is limited to it on the server until it is removed. */

import { createContext, useContext } from "react";

export type MapArea = { polygon: [number, number][]; label: string };
type Value = { area: MapArea | null; setArea: (area: MapArea | null) => void };

export const MapAreaContext = createContext<Value>({ area: null, setArea: () => {} });
export const useMapArea = () => useContext(MapAreaContext);
