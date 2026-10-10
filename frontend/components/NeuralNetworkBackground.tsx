"use client";

import React, { useEffect, useRef } from "react";
import { useTheme } from "@/context/ThemeContext";

interface Neuron {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  radius: number;
  pulsePhase: number;
  pulseSpeed: number;
  connections: number[];
}

interface Signal {
  from: number;
  to: number;
  progress: number;
  speed: number;
  opacity: number;
}

export function NeuralNetworkBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { resolvedTheme } = useTheme();
  const themeRef = useRef(resolvedTheme);
  const animRef = useRef<number>(0);

  useEffect(() => {
    themeRef.current = resolvedTheme;
  }, [resolvedTheme]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    let time = 0;

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    /* ---------- BUILD NEURONS ---------- */
    const NEURON_COUNT = Math.min(55, Math.floor((width * height) / 18000));
    const neurons: Neuron[] = [];

    for (let i = 0; i < NEURON_COUNT; i++) {
      neurons.push({
        x: Math.random() * width,
        y: Math.random() * height,
        z: Math.random() * 300 - 150,          // depth: -150 → +150
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        vz: (Math.random() - 0.5) * 0.2,
        radius: Math.random() * 2.5 + 1.2,
        pulsePhase: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.025 + 0.01,
        connections: [],
      });
    }

    /* build adjacency — connect nearby neurons */
    const CONNECT_THRESHOLD = Math.min(width, height) * 0.22;
    neurons.forEach((n, i) => {
      n.connections = [];
      neurons.forEach((m, j) => {
        if (i >= j) return;
        const dx = n.x - m.x;
        const dy = n.y - m.y;
        const dz = n.z - m.z;
        if (Math.sqrt(dx * dx + dy * dy + dz * dz) < CONNECT_THRESHOLD) {
          n.connections.push(j);
        }
      });
    });

    /* ---------- SIGNALS ---------- */
    const signals: Signal[] = [];
    const MAX_SIGNALS = 18;

    const spawnSignal = () => {
      if (signals.length >= MAX_SIGNALS) return;
      const from = Math.floor(Math.random() * neurons.length);
      if (!neurons[from].connections.length) return;
      const to = neurons[from].connections[
        Math.floor(Math.random() * neurons[from].connections.length)
      ];
      signals.push({ from, to, progress: 0, speed: 0.008 + Math.random() * 0.012, opacity: 0 });
    };

    /* ---------- PALETTE ---------- */
    const palette = () => {
      const dark = themeRef.current === "dark";
      return {
        /* Neuron dot */
        neuronCore: dark ? "rgba(0,242,254,0.85)"  : "rgba(14,116,167,0.80)",
        neuronGlow: dark ? "rgba(0,242,254,0.25)"  : "rgba(2,132,199,0.20)",
        /* Axon / connection line */
        axon:       dark ? "rgba(0,242,254,0.05)"  : "rgba(2,132,199,0.06)",
        axonClose:  dark ? "rgba(0,242,254,0.14)"  : "rgba(2,132,199,0.14)",
        /* Signal orb */
        signal:     dark ? "rgba(100,255,218,1.0)" : "rgba(6,95,170,1.0)",
        signalGlow: dark ? "rgba(100,255,218,0.4)" : "rgba(6,95,170,0.3)",
        /* Depth tint overlay */
        depthFar:   dark ? "rgba(5,7,13,0.0)"      : "rgba(248,250,252,0.0)",
      };
    };

    /* ---------- HELPERS ---------- */
    const project = (n: Neuron) => {
      const fov = 600;
      const scale = fov / (fov + n.z);
      return {
        sx: n.x * scale + (width / 2) * (1 - scale),
        sy: n.y * scale + (height / 2) * (1 - scale),
        scale,
      };
    };

    /* ---------- RENDER LOOP ---------- */
    const render = () => {
      ctx.clearRect(0, 0, width, height);
      time += 1;
      const p = palette();

      /* Occasionally spawn a signal */
      if (time % 20 === 0) spawnSignal();

      /* Update neuron positions */
      neurons.forEach((n) => {
        n.x += n.vx;
        n.y += n.vy;
        n.z += n.vz;
        if (n.x < 0 || n.x > width) n.vx *= -1;
        if (n.y < 0 || n.y > height) n.vy *= -1;
        if (n.z < -150 || n.z > 150) n.vz *= -1;
        n.pulsePhase += n.pulseSpeed;
      });

      /* Draw connections (axons) */
      neurons.forEach((n, i) => {
        const { sx: nx, sy: ny } = project(n);
        n.connections.forEach((j) => {
          const m = neurons[j];
          const { sx: mx, sy: my } = project(m);
          const dx = n.x - m.x;
          const dy = n.y - m.y;
          const dz = n.z - m.z;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          const proximity = 1 - dist / CONNECT_THRESHOLD;

          ctx.beginPath();
          ctx.moveTo(nx, ny);
          ctx.lineTo(mx, my);
          ctx.strokeStyle = proximity > 0.6 ? p.axonClose : p.axon;
          ctx.lineWidth = proximity * 0.9;
          ctx.stroke();
        });
      });

      /* Draw signals */
      for (let s = signals.length - 1; s >= 0; s--) {
        const sig = signals[s];
        sig.progress += sig.speed;

        /* fade in/out */
        if (sig.progress < 0.1) sig.opacity = sig.progress / 0.1;
        else if (sig.progress > 0.85) sig.opacity = (1 - sig.progress) / 0.15;

        if (sig.progress >= 1) { signals.splice(s, 1); continue; }

        const from = neurons[sig.from];
        const to   = neurons[sig.to];
        const { sx: fx, sy: fy } = project(from);
        const { sx: tx, sy: ty } = project(to);

        const lx = fx + (tx - fx) * sig.progress;
        const ly = fy + (ty - fy) * sig.progress;

        /* glow */
        const grd = ctx.createRadialGradient(lx, ly, 0, lx, ly, 10);
        grd.addColorStop(0, p.signal.replace("1.0)", `${sig.opacity})`));
        grd.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(lx, ly, 10, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();

        /* orb */
        ctx.beginPath();
        ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fillStyle = p.signal.replace("1.0)", `${sig.opacity})`);
        ctx.fill();
      }

      /* Draw neurons */
      neurons.forEach((n) => {
        const { sx, sy, scale } = project(n);
        const pulse = 0.5 + 0.5 * Math.sin(n.pulsePhase);
        const r = n.radius * scale * (1 + pulse * 0.4);
        const depth = (n.z + 150) / 300; // 0..1

        /* outer glow */
        const grd = ctx.createRadialGradient(sx, sy, 0, sx, sy, r * 5);
        grd.addColorStop(0, p.neuronGlow);
        grd.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(sx, sy, r * 5, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();

        /* core dot */
        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        /* near neurons = bright, far = dim */
        const alpha = 0.3 + 0.7 * depth;
        ctx.fillStyle = p.neuronCore.replace("0.85)", `${(alpha * 0.85).toFixed(2)})`);
        ctx.fill();
      });

      animRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animRef.current);
    };
  }, []); // only runs once; reads theme via ref

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.75 }}
    />
  );
}
