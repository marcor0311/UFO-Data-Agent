"use client";

import { useEffect, useRef } from "react";

const CIRCLE = Math.PI * 2;
const ROTATION_SPEED = 0.0000375;
const PITCH = 0.16;

function seed(index: number) {
  const value = Math.sin(index * 127.1 + 311.7) * 43758.5453;
  return value - Math.floor(value);
}

// Keep the DB Test prototype's volumetric distribution and perspective.
function createParticles(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const azimuth = seed(index + 1900) * CIRCLE;
    const height = seed(index + 3900) * 2 - 1;
    const radius = Math.cbrt(seed(index + 5900));
    const ring = Math.sqrt(1 - height * height) * radius;
    return {
      x: Math.cos(azimuth) * ring,
      y: height * radius * 0.72,
      z: Math.sin(azimuth) * ring,
      phase: seed(index + 6900) * CIRCLE,
      radius: 1 + seed(index + 7900) * 2.2,
      alpha: 0.18 + seed(index + 8900) * 0.6,
    };
  });
}

export function AmbientParticles() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = ref.current;
    const context = element?.getContext("2d");
    if (!element || !context) return;
    const canvas = element;
    const ctx = context;

    const particles = createParticles(Math.min(1050, Math.round(window.innerWidth * 0.65)));
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pitchCos = Math.cos(PITCH);
    const pitchSin = Math.sin(PITCH);
    let width = 0;
    let height = 0;
    let angle = 0;
    let lastFrame: number | undefined;
    let frame = 0;

    function draw(now?: number) {
      if (!width || !height || document.hidden) return;
      if (lastFrame !== undefined && now !== undefined) {
        angle = (angle + Math.min(40, now - lastFrame) * ROTATION_SPEED) % CIRCLE;
      }
      lastFrame = now;

      ctx.clearRect(0, 0, width, height);
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      const size = Math.min(width * 0.42, height * 0.46);
      const projected = particles.map((particle) => {
        const x = particle.x * cos - particle.z * sin;
        const depth = particle.x * sin + particle.z * cos;
        const drift = Math.sin(particle.phase + angle * 0.6) * 0.025;
        const y = (particle.y + drift) * pitchCos - depth * pitchSin;
        const z = (particle.y + drift) * pitchSin + depth * pitchCos;
        const perspective = 1 / (1 + z * 0.46);
        return {
          x: width * 0.5 + x * size * perspective,
          y: height * 0.46 + y * size * perspective,
          radius: particle.radius * perspective,
          alpha: Math.min(0.9, particle.alpha * Math.max(0.48, Math.min(1.15, perspective))),
          z,
        };
      });
      projected.sort((a, b) => b.z - a.z);

      ctx.fillStyle = "#2f5391";
      for (const point of projected) {
        ctx.globalAlpha = point.alpha;
        ctx.beginPath();
        ctx.arc(point.x, point.y, point.radius, 0, CIRCLE);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (!motion.matches) frame = requestAnimationFrame(draw);
    }

    function syncAnimation() {
      cancelAnimationFrame(frame);
      lastFrame = undefined;
      draw();
    }

    function resize() {
      const bounds = canvas.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return;

      const dpr = Math.min(window.devicePixelRatio, 2);
      const pixelsWide = Math.round(bounds.width * dpr);
      const pixelsHigh = Math.round(bounds.height * dpr);
      if (width === bounds.width && height === bounds.height && canvas.width === pixelsWide && canvas.height === pixelsHigh) return;

      width = bounds.width;
      height = bounds.height;
      canvas.width = pixelsWide;
      canvas.height = pixelsHigh;
      ctx.setTransform(canvas.width / width, 0, 0, canvas.height / height, 0, 0);
      syncAnimation();
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", syncAnimation);
    motion.addEventListener("change", syncAnimation);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", syncAnimation);
      motion.removeEventListener("change", syncAnimation);
    };
  }, []);

  return <canvas ref={ref} className="ambient-particles" aria-hidden="true" />;
}
