import type { Metadata } from "next";
import localFont from "next/font/local";
import Image from "next/image";
import Link from "next/link";
import cierre from "../../public/archivo-uap/cierre.webp";
import portada from "../../public/archivo-uap/portada.webp";
import ArchiveBriefing from "./archive-briefing";
import ArchiveGallery from "./archive-gallery";
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
  description: "Consulta informes sobre fenómenos aéreos no identificados con preguntas en lenguaje natural.",
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
        <section className={styles.hero} id="portada" aria-labelledby="landing-title">
          <Image className={styles.heroImage} src={portada} alt="" fill sizes="100vw" preload />
          <div className={styles.heroContent}>
            <h1 id="landing-title">UFO <span>Data Agent</span></h1>
            <p>Consulta informes sobre fenómenos aéreos no identificados (UAP) con preguntas en lenguaje natural.</p>
            <Link className={styles.button} href="/agent">Entrar al Data Agent</Link>
          </div>
          <p className={styles.photoCaption}>Recreación editorial</p>
        </section>
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
