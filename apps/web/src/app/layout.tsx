import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agente de datos UFO",
  description: "Pregunta en lenguaje natural sobre informes de fenómenos aéreos no identificados, con datos verificados de Gold.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="es"><body>{children}</body></html>;
}
