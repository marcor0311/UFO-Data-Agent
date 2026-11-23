import type { Metadata } from "next";
import localFont from "next/font/local";
import AgentWorkspace from "@/components/agent/workspace";

const manrope = localFont({ src: "../fonts/Manrope.woff2", variable: "--chat-font", weight: "200 800", display: "swap" });

export const metadata: Metadata = { title: "Agente de datos UFO" };

export default function AgentPage() {
  return <div className={manrope.variable}><AgentWorkspace /></div>;
}
