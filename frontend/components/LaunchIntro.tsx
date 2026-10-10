"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const DURATION = 10400;

export function LaunchIntro({ children }: { children: ReactNode }) {
  const [finished, setFinished] = useState(false);
  const [landing, setLanding] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (finished) {
      document.querySelector<HTMLElement>("main")?.focus({ preventScroll: true });
      return;
    }
    const root = rootRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!root || !canvas || !ctx) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    skipRef.current?.focus({ preventScroll: true });
    let frame = 0, elapsed = 0, last = 0, width = 0, height = 0;
    let landingStarted = false;
    const stars = Array.from({ length: 100 }, () => ({
      angle: Math.random() * Math.PI * 2,
      distance: .08 + Math.random() * 1.2,
      speed: .5 + Math.random(),
      size: .5 + Math.random() * 1.2,
    }));
    const resize = () => {
      width = innerWidth; height = innerHeight;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = width * dpr; canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const draw = (now: number) => {
      const dt = last ? Math.min(now - last, 80) : 0;
      last = now; elapsed += dt;
      const seconds = elapsed / 1000;
      const acceleration = Math.pow(Math.max(0, Math.min(1, (seconds - 6.8) / 2.5)), 2);
      const textIn = Math.min(1, seconds / .8);
      const textOut = Math.max(0, Math.min(1, (seconds - 8.8) / .5));
      const flash = seconds < 9.3 ? 0 : seconds < 9.55 ? (seconds - 9.3) / .25 : Math.max(0, 1 - (seconds - 9.55) / .85);
      root.style.setProperty("--quote-opacity", String(textIn * (1 - textOut)));
      root.style.setProperty("--flash-opacity", String(flash * .88));
      root.style.setProperty("--intro-progress", String(Math.min(1, elapsed / DURATION)));
      if (seconds >= 9.55 && !landingStarted) { landingStarted = true; setLanding(true); }
      ctx.clearRect(0, 0, width, height);
      const extent = Math.hypot(width, height) * .6;
      for (const star of stars.slice(0, width < 640 ? 55 : 100)) {
        star.distance += dt / 1000 * star.speed * (.018 + acceleration * .8);
        if (star.distance > 1.35) star.distance = .06;
        const angle = star.angle + acceleration * Math.sin(star.angle * 3 + seconds * .7) * .14;
        const radius = star.distance * extent;
        const tail = (6 + acceleration * 150) * star.speed;
        const x = width * .5 + Math.cos(angle) * radius;
        const y = height * .5 + Math.sin(angle) * radius * .8;
        const tx = width * .5 + Math.cos(angle - acceleration * .04) * Math.max(0, radius - tail);
        const ty = height * .5 + Math.sin(angle - acceleration * .04) * Math.max(0, radius - tail) * .8;
        const gradient = ctx.createLinearGradient(tx, ty, x + .01, y + .01);
        gradient.addColorStop(0, "rgba(234,185,149,0)");
        gradient.addColorStop(1, "rgba(243,235,221,.8)");
        ctx.strokeStyle = gradient;
        ctx.globalAlpha = .3 + acceleration * .5;
        ctx.lineWidth = star.size;
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      }
      if (elapsed >= DURATION) { setFinished(true); return; }
      frame = requestAnimationFrame(draw);
    };
    const visibility = () => {
      cancelAnimationFrame(frame); last = 0;
      if (!document.hidden) frame = requestAnimationFrame(draw);
    };
    const keydown = (e: KeyboardEvent) => { if (e.key === "Escape") setFinished(true); };
    resize(); frame = requestAnimationFrame(draw);
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", visibility);
    document.addEventListener("keydown", keydown);
    return () => {
      cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", visibility);
      document.removeEventListener("keydown", keydown);
    };
  }, [finished]);

  return <>{(landing || finished) && children}{!finished && <div ref={rootRef} className={`launch-intro${landing ? " launch-landing" : ""}`} role="region" aria-label="Welcome to Nexyra">
    <canvas ref={canvasRef} aria-hidden="true" />
    <div className="launch-vignette" aria-hidden="true" />
    <div className="launch-copy">
      <div className="launch-star" aria-hidden="true">✦</div>
      <p className="launch-brand">NEXYRA</p>
      <blockquote>Don’t just ask if you can afford it.<br />Ask what it costs your future.</blockquote>
      <p className="launch-caption">A LITTLE CLARITY. A BIGGER HORIZON.</p>
    </div>
    <div className="launch-footer"><span>YOUR NEXT CHAPTER AWAITS</span><div className="launch-progress" aria-hidden="true"><span /></div></div>
    <button ref={skipRef} className="launch-skip" onClick={() => setFinished(true)}>Skip intro <span aria-hidden="true">↗</span></button>
    <div className="launch-flash" aria-hidden="true" />
  </div>}</>;
}
