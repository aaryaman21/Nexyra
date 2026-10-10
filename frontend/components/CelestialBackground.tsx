"use client";

import { useEffect, useRef } from "react";

type Blink = { nextBlink: number; blinkDuration: number; strength: number };

function blinkLevel(star: Blink, time: number) {
  if (time >= star.nextBlink + star.blinkDuration) {
    star.nextBlink = time + 1.5 + Math.random() * 5.5;
    star.blinkDuration = .45 + Math.random() * 1.15;
    star.strength = .65 + Math.random() * .35;
  }
  const progress = (time - star.nextBlink) / star.blinkDuration;
  return progress >= 0 && progress <= 1
    ? star.strength * Math.pow(Math.sin(Math.PI * progress), 2)
    : 0;
}

/** Synchronized back/front canvases let each orbit pass through the panel plane. */
export function CelestialBackground() {
  const ref = useRef<HTMLCanvasElement>(null);
  const frontRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    const front = frontRef.current;
    const frontCtx = front?.getContext("2d");
    if (!canvas || !ctx || !front || !frontCtx) return;
    const pointer = { x: 0, y: 0 };
    let width = 0, height = 0, frame = 0, last = 0, time = 0;
    const stars = Array.from({ length: 95 }, () => ({
      x: Math.random(), y: Math.random(), depth: .3 + Math.random() * .7,
      nextBlink: Math.random() * 5,
      blinkDuration: .45 + Math.random() * 1.15,
      strength: .65 + Math.random() * .35,
    }));
    const orbitingStars = Array.from({ length: 9 }, (_, i) => ({
      phase: i * 2.399, period: 24 + i * 4.5,
      nextBlink: Math.random() * 5,
      blinkDuration: .45 + Math.random() * 1.15,
      strength: .65 + Math.random() * .35,
      centerX: .42 + (i % 3) * .08, centerY: .25 + (i % 4) * .16,
      radius: .31 + (i % 3) * .08, tilt: -.55 + (i % 4) * .32,
      size: i % 3 === 0 ? 1.7 : 1.1,
    }));
    const resize = () => {
      width = innerWidth; height = innerHeight;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = width * dpr; canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      front.width = width * dpr; front.height = height * dpr;
      frontCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const draw = (now: number) => {
      const dt = last ? Math.min(now - last, 50) : 0;
      last = now;
      time += dt / 1000;
      ctx.clearRect(0, 0, width, height);
      frontCtx.clearRect(0, 0, width, height);
      // Read the interpolated CSS color so theme changes also crossfade the stars.
      const style = getComputedStyle(canvas);
      const color = style.color;
      const visibility = Number(style.getPropertyValue("--star-visibility")) || 1;
      ctx.fillStyle = color;
      for (const star of stars.slice(0, width < 640 ? 35 : 95)) {
        // Brief, unsynchronized pulses give each fixed star a firefly-like blink.
        const x = star.x * width;
        const y = star.y * height;
        const margin = x < width * .13 || x > width * .87;
        const blink = blinkLevel(star, time);
        const radius = (.75 + star.depth * 1.2) * (1 + .25 * blink);
        ctx.save();
        ctx.globalAlpha = Math.min(1, visibility * ((margin ? .22 : .13) + blink * (margin ? .7 : .48)));
        ctx.shadowColor = color;
        ctx.shadowBlur = 2 + 12 * blink;
        ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
        if (star.depth > .82) {
          ctx.save();
          ctx.globalAlpha = Math.min(1, visibility * (margin ? .4 : .2) * blink);
          ctx.fillRect(x - radius * 2.8, y - .35, radius * 5.6, .7);
          ctx.fillRect(x - .35, y - radius * 2.8, .7, radius * 5.6);
          ctx.restore();
        }
      }
      for (const star of orbitingStars.slice(0, width < 640 ? 5 : 9)) {
        const angle = time * Math.PI * 2 / star.period + star.phase;
        const depth = Math.sin(angle);
        const radius = Math.min(width * star.radius, height * .66);
        const orbitX = Math.cos(angle) * radius;
        const orbitY = depth * radius * .42;
        const x = width * star.centerX + orbitX * Math.cos(star.tilt) - orbitY * Math.sin(star.tilt) + pointer.x * 6;
        const y = height * star.centerY + orbitX * Math.sin(star.tilt) + orbitY * Math.cos(star.tilt) + pointer.y * 6;
        const size = star.size * (1 + depth * .28);
        const blink = blinkLevel(star, time);
        // Crossfade at the panel plane, avoiding a sudden layer-switch pop.
        const blend = Math.max(0, Math.min(1, (depth + .12) / .24));
        const foreground = blend * blend * (3 - 2 * blend);
        for (const [context, opacity] of [[ctx, 1 - foreground], [frontCtx, foreground]] as const) {
          if (opacity === 0) continue;
          context.save();
          context.fillStyle = color;
          context.globalAlpha = Math.min(1, visibility * opacity * (.2 + .7 * blink) * (1 + depth * .15));
          context.shadowColor = color; context.shadowBlur = size * (2 + 7 * blink);
          context.beginPath(); context.arc(x, y, size, 0, Math.PI * 2); context.fill();
          context.shadowBlur = 0;
          // Fine tapered rays read as starlight rather than a solid planet.
          context.globalAlpha *= .15 + .5 * blink;
          context.beginPath();
          context.moveTo(x, y - size * 3);
          context.lineTo(x + size * .4, y - size * .4);
          context.lineTo(x + size * 3, y);
          context.lineTo(x + size * .4, y + size * .4);
          context.lineTo(x, y + size * 3);
          context.lineTo(x - size * .4, y + size * .4);
          context.lineTo(x - size * 3, y);
          context.lineTo(x - size * .4, y - size * .4);
          context.closePath(); context.fill();
          context.restore();
        }
      }
      if (!document.hidden) frame = requestAnimationFrame(draw);
    };
    const restart = () => { cancelAnimationFrame(frame); last = 0; draw(performance.now()); };
    const onResize = () => { resize(); restart(); };
    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      pointer.x = e.clientX / width - .5; pointer.y = e.clientY / height - .5;
    };
    resize(); restart();
    const observer = new MutationObserver(restart);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("visibilitychange", restart);
    return () => {
      cancelAnimationFrame(frame); observer.disconnect();
      window.removeEventListener("resize", onResize); window.removeEventListener("pointermove", move);
      document.removeEventListener("visibilitychange", restart);
    };
  }, []);
  return <>
    <div className="celestial-field" aria-hidden="true"><div className="celestial-cloud cloud-one" /><div className="celestial-cloud cloud-two" /><canvas ref={ref} /></div>
    <div className="celestial-field celestial-foreground" aria-hidden="true"><canvas ref={frontRef} /></div>
  </>;
}
