import type { Metadata } from "next";
import localFont from "next/font/local";
import Image from "next/image";
import Link from "next/link";
import cierre from "../../public/archivo-uap/cierre.webp";
import ArchiveBriefing from "./archive-briefing";
import ArchiveGallery from "./archive-gallery";
import LandingHero from "./landing-hero";
import styles from "./landing.module.css";

const displayFont = localFont({
  src: "./fonts/BarlowCondensed-Bold.ttf",
  weight: "700",
  variable: "--archive-display",
  display: "swap",
});
const bodyFont = localFont({
  src: "./fonts/Manrope.woff2",
  variable: "--archive-body",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "UFO Data Agent | Archivo UAP",
  description: "Analítica de datos conversacional para explorar informes sobre fenómenos aéreos no identificados.",
};

export default function Home() {
  return (
    <div className={`${styles.landing} ${displayFont.variable} ${bodyFont.variable}`}>
      <a className={styles.skip} href="#contenido">Saltar al contenido</a>
      <header className={styles.header}>
        <a className={styles.brand} href="#portada" aria-label="UFO Data Agent, portada">
          <span className={styles.mark} aria-hidden="true" />
          <span>UFO <span>DATA AGENT</span></span>
        </a>
        <nav aria-label="Navegación principal">
          <a className={styles.archiveLink} href="#archivo">El archivo</a>
          <a className={styles.archiveLink} href="#metodo">El agente</a>
          <Link className={styles.headerButton} href="/agent">Entrar al Data Agent</Link>
        </nav>
      </header>
      <main id="contenido">
        <LandingHero />
        <ArchiveGallery />
        <ArchiveBriefing />
      </main>
      <footer className={styles.entrance}>
        <Image className={styles.entranceImage} src={cierre} alt="" fill sizes="100vw" />
        <h2 className={styles.sectionTitle}>Pregunta al agente</h2>
        <Link className={styles.button} href="/agent">Entrar al Data Agent</Link>
      </footer>
    </div>
  );
}
