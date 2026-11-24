"use client";

import gsap from "gsap";
import Image from "next/image";
import { useEffect, useRef } from "react";
import portada from "../../public/archivo-uap/portada.webp";
import styles from "./landing.module.css";

const allowMotion = "(prefers-reduced-motion: no-preference)";

export default function LandingHero() {
  const content = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const animations = gsap.matchMedia();
    animations.add(allowMotion, () => {
      if (!content.current) return;
      gsap.from(content.current.children, {
        y: 16,
        opacity: 0.7,
        duration: 0.85,
        stagger: 0.1,
        ease: "power3.out",
      });
    });

    return () => animations.revert();
  }, []);

  return (
    <section className={styles.hero} id="portada" aria-labelledby="landing-title">
      <div className={styles.heroMedia} aria-hidden="true">
        <Image className={styles.heroImage} src={portada} alt="" fill preload unoptimized />
      </div>
      <div ref={content} className={styles.heroContent}>
        <h1 id="landing-title">UFO <span>Data Agent</span></h1>
        <p>Consulta informes sobre fenómenos aéreos no identificados (UAP) con preguntas en lenguaje natural</p>
      </div>
    </section>
  );
}
