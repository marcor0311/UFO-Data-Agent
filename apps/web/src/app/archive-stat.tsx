"use client";

import gsap from "gsap";
import { useEffect, useRef } from "react";
import { num } from "@/lib/format";
import styles from "./landing.module.css";

const reportCount = 700_000;
const formattedCount = num(reportCount);

export default function ArchiveStat() {
  const displayRef = useRef<HTMLSpanElement>(null);
  const numberRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const display = displayRef.current;
    const number = numberRef.current;
    if (!display || !number || typeof IntersectionObserver === "undefined") return;

    let played = false;
    const motion = gsap.matchMedia();
    motion.add("(prefers-reduced-motion: no-preference)", () => {
      if (played) return;

      const count = { value: 0 };
      const reveal = gsap.timeline({ paused: true })
        .from(display, {
          opacity: 0.65,
          y: 10,
          duration: 0.18,
          ease: "power2.out",
          immediateRender: false,
        }, 0)
        .to(count, {
          value: reportCount,
          duration: 0.32,
          ease: "power2.out",
          snap: { value: 1 },
          onUpdate: () => {
            const formatted = num(count.value);
            if (number.textContent !== formatted) number.textContent = formatted;
          },
        }, 0);

      const observer = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting) return;
        played = true;
        observer.disconnect();
        number.textContent = num(count.value);
        reveal.play();
      });
      observer.observe(display);

      return () => {
        observer.disconnect();
        if (number.textContent !== formattedCount) number.textContent = formattedCount;
      };
    });

    return () => motion.revert();
  }, []);

  return (
    <p className={styles.archiveStat}>
      <span className="sr-only">Más de {formattedCount} reportes para explorar</span>
      <span ref={displayRef} className={styles.archiveStatDisplay} aria-hidden="true">
        Más de <strong ref={numberRef}>{formattedCount}</strong> reportes para explorar
      </span>
    </p>
  );
}
