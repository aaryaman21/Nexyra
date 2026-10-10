# -*- coding: utf-8 -*-
import os

files = {}

files["components/ConstellationBackground.tsx"] = """"use client";

import React, { useEffect, useRef } from "react";
import { useTheme } from "@/context/ThemeContext";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

export function ConstellationBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", handleResize);

    const nodeCount = Math.min(38, Math.floor(width / 35));
    const nodes: Node[] = [];

    for (let i = 0; i < nodeCount; i++) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 1.8 + 1,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const isDark = resolvedTheme === "dark";
      const nodeColor = isDark ? "rgba(0, 242, 254, 0.4)" : "rgba(2, 132, 199, 0.3)";
      const lineColor = isDark ? "rgba(0, 242, 254, 0.08)" : "rgba(2, 132, 199, 0.06)";

      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 0 || node.x > width) node.vx *= -1;
        if (node.y < 0 || node.y > height) node.vy *= -1;

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fillStyle = nodeColor;
        ctx.fill();

        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j];
          const dx = node.x - other.x;
          const dy = node.y - other.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 140) {
            ctx.beginPath();
            ctx.moveTo(node.x, node.y);
            ctx.lineTo(other.x, other.y);
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [resolvedTheme]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 opacity-80"
    />
  );
}
"""

files["components/loaders/ContextualLoaders.tsx"] = """"use client";

import React from "react";
import { motion } from "framer-motion";

export type LoaderModule =
  | "moneymap"
  | "futureflow"
  | "goalpath"
  | "decisionlab"
  | "safetynet"
  | "impactmap"
  | "bestmove"
  | "decisionwhy";

interface LoaderProps {
  module: LoaderModule;
  text?: string;
}

export function ContextualLoader({ module, text }: LoaderProps) {
  switch (module) {
    case "moneymap":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="relative w-24 h-24 flex items-center justify-center">
            <motion.div
              className="absolute w-4 h-4 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.8)]"
              animate={{ x: [-30, 0, 30, 0, -30], y: [-15, 20, -15, -25, -15] }}
              transition={{ repeat: Infinity, duration: 2.8, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute w-3.5 h-3.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"
              animate={{ x: [30, -20, -30, 15, 30], y: [20, -15, 25, -20, 20] }}
              transition={{ repeat: Infinity, duration: 3.2, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute w-3 h-3 rounded-full bg-indigo-400 shadow-[0_0_12px_rgba(129,140,248,0.8)]"
              animate={{ x: [0, 25, -25, 0], y: [-30, 15, -15, -30] }}
              transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
            />
            <svg className="w-full h-full stroke-cyan-500/20" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="35" fill="none" strokeWidth="1.5" strokeDasharray="4 4" />
            </svg>
          </div>
          <p className="text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
            {text || "Mapping your financial picture..."}
          </p>
        </div>
      );

    case "futureflow":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="w-36 h-12 flex items-center justify-between relative overflow-hidden px-2 border-b border-cyan-500/30">
            <motion.div
              className="absolute top-0 bottom-0 left-0 w-12 bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent"
              animate={{ x: [-50, 150] }}
              transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }}
            />
            {[1, 2, 3, 4, 5].map((i) => (
              <motion.div
                key={i}
                className="w-1.5 bg-cyan-400 rounded-full"
                animate={{ height: [8, 28, 12, 36, 16] }}
                transition={{ repeat: Infinity, duration: 1.8, delay: i * 0.15, ease: "easeInOut" }}
              />
            ))}
          </div>
          <p className="text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
            {text || "Projecting your financial trajectory..."}
          </p>
        </div>
      );

    case "goalpath":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="w-40 h-8 flex items-center relative">
            <div className="w-full h-1 bg-slate-700/50 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-400 via-emerald-400 to-indigo-400"
                animate={{ width: ["0%", "100%", "0%"] }}
                transition={{ repeat: Infinity, duration: 2.2, ease: "easeInOut" }}
              />
            </div>
            <motion.div
              className="absolute right-0 w-4 h-4 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.9)]"
              animate={{ scale: [1, 1.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
            />
          </div>
          <p className="text-xs font-mono text-emerald-400 animate-pulse tracking-wider uppercase">
            {text || "Calculating your goal trajectory..."}
          </p>
        </div>
      );

    case "decisionlab":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="w-28 h-16 relative flex items-center justify-center">
            <svg className="w-full h-full" viewBox="0 0 100 60">
              <motion.path
                d="M 10 30 Q 50 30 90 12"
                fill="none"
                stroke="#06b6d4"
                strokeWidth="2"
                strokeDasharray="6 4"
                animate={{ strokeDashoffset: [0, -20] }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              />
              <motion.path
                d="M 10 30 Q 50 30 90 48"
                fill="none"
                stroke="#f43f5e"
                strokeWidth="2"
                strokeDasharray="6 4"
                animate={{ strokeDashoffset: [0, -20] }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              />
              <circle cx="10" cy="30" r="4" fill="#38bdf8" />
              <circle cx="90" cy="12" r="4" fill="#10b981" />
              <circle cx="90" cy="48" r="4" fill="#f43f5e" />
            </svg>
          </div>
          <p className="text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
            {text || "Simulating your purchase..."}
          </p>
        </div>
      );

    case "safetynet":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="relative w-20 h-20 flex items-center justify-center">
            <motion.div
              className="absolute inset-0 rounded-full border-2 border-emerald-400/40 border-dashed"
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 6, ease: "linear" }}
            />
            <motion.div
              className="w-10 h-10 rounded-full bg-emerald-500/20 border border-emerald-400 flex items-center justify-center shadow-[0_0_15px_rgba(16,185,129,0.4)]"
              animate={{ scale: [0.9, 1.1, 0.9] }}
              transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            >
              <div className="w-3 h-3 rounded-full bg-emerald-400" />
            </motion.div>
          </div>
          <p className="text-xs font-mono text-emerald-400 animate-pulse tracking-wider uppercase">
            {text || "Checking your financial cushion..."}
          </p>
        </div>
      );

    case "impactmap":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="relative w-20 h-20 flex items-center justify-center">
            {[1, 2, 3].map((r) => (
              <motion.div
                key={r}
                className="absolute rounded-full border border-cyan-400/50"
                animate={{
                  width: ["20px", "75px"],
                  height: ["20px", "75px"],
                  opacity: [0.8, 0],
                }}
                transition={{
                  repeat: Infinity,
                  duration: 2.2,
                  delay: r * 0.6,
                  ease: "easeOut",
                }}
              />
            ))}
            <div className="w-4 h-4 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.9)]" />
          </div>
          <p className="text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
            {text || "Mapping the consequences..."}
          </p>
        </div>
      );

    case "bestmove":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="w-24 h-16 relative flex items-center justify-center">
            <motion.div
              className="absolute w-2 h-2 rounded-full bg-amber-400"
              animate={{ x: [-35, 0], y: [-20, 0], opacity: [0.2, 1] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeIn" }}
            />
            <motion.div
              className="absolute w-2 h-2 rounded-full bg-cyan-400"
              animate={{ x: [35, 0], y: [-20, 0], opacity: [0.2, 1] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeIn", delay: 0.2 }}
            />
            <motion.div
              className="absolute w-2 h-2 rounded-full bg-emerald-400"
              animate={{ x: [0, 0], y: [30, 0], opacity: [0.2, 1] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeIn", delay: 0.4 }}
            />
            <div className="w-6 h-6 rounded-full bg-white dark:bg-slate-800 border-2 border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.8)]" />
          </div>
          <p className="text-xs font-mono text-amber-400 animate-pulse tracking-wider uppercase">
            {text || "Evaluating your options..."}
          </p>
        </div>
      );

    case "decisionwhy":
      return (
        <div className="flex flex-col items-center justify-center p-8 space-y-4">
          <div className="flex gap-2 items-center">
            {[1, 2, 3].map((idx) => (
              <motion.div
                key={idx}
                className="w-3 h-8 rounded bg-cyan-500/30 border border-cyan-400/50 flex items-center justify-center text-[9px] font-mono text-cyan-300"
                animate={{ opacity: [0.3, 1, 0.3], height: [24, 38, 24] }}
                transition={{ repeat: Infinity, duration: 1.4, delay: idx * 0.2 }}
              >
                0{idx}
              </motion.div>
            ))}
          </div>
          <p className="text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
            {text || "Building your explanation..."}
          </p>
        </div>
      );
  }
}
"""

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {path} ({len(content)} chars)")
