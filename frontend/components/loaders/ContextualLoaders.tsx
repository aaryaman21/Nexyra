"use client";

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

/* ─── Shimmer block helper ─── */
function Shimmer({ className = "" }: { className?: string }) {
  return <div className={`shimmer ${className}`} />;
}

/* ─── Full-screen shimmer skeleton ─── */
function ShimmerSkeleton({ rows = 3, headerText }: { rows?: number; headerText: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="glass-panel p-6 space-y-4"
    >
      {/* Module header skeleton */}
      <div className="flex items-center gap-3 pb-4 border-b border-slate-200/60 dark:border-slate-800/60">
        <div className="w-2.5 h-2.5 rounded-full bg-cyan-400/40 animate-pulse" />
        <Shimmer className="h-4 w-40" />
        <Shimmer className="h-4 w-24 ml-auto" />
      </div>

      {/* Label */}
      <p className="text-[11px] font-mono text-cyan-500/60 uppercase tracking-widest animate-pulse">
        {headerText}
      </p>

      {/* Content rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="space-y-2" style={{ animationDelay: `${i * 0.12}s` }}>
          <Shimmer className="h-10 w-full rounded-xl" />
          {i % 2 === 0 && <Shimmer className="h-4 w-3/4 rounded-lg" />}
        </div>
      ))}

      {/* Bottom row of mini cards */}
      <div className="grid grid-cols-3 gap-3 pt-2">
        {[1, 2, 3].map((j) => (
          <Shimmer key={j} className="h-16 rounded-xl" />
        ))}
      </div>
    </motion.div>
  );
}

/* ─── Module-specific animated loaders ─── */

function MoneyMapLoader() {
  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-center py-6">
        <div className="relative w-28 h-28">
          <motion.div
            className="absolute w-5 h-5 rounded-full bg-cyan-400 shadow-[0_0_14px_rgba(6,182,212,0.8)]"
            animate={{ x: [-32, 0, 32, 0, -32], y: [-16, 22, -16, -26, -16] }}
            transition={{ repeat: Infinity, duration: 2.8, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute w-4 h-4 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"
            animate={{ x: [32, -20, -32, 16, 32], y: [22, -16, 26, -20, 22] }}
            transition={{ repeat: Infinity, duration: 3.2, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute w-3.5 h-3.5 rounded-full bg-indigo-400 shadow-[0_0_12px_rgba(129,140,248,0.8)]"
            animate={{ x: [0, 26, -26, 0], y: [-32, 16, -16, -32] }}
            transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
          />
          <svg className="w-full h-full stroke-cyan-500/20 absolute inset-0" viewBox="0 0 112 112">
            <circle cx="56" cy="56" r="40" fill="none" strokeWidth="1.5" strokeDasharray="4 4" />
          </svg>
        </div>
      </div>
      <p className="text-center text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
        Mapping your financial picture...
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Shimmer className="h-14 rounded-xl" />
        <Shimmer className="h-14 rounded-xl" />
      </div>
    </div>
  );
}

function FutureFlowLoader() {
  return (
    <div className="glass-panel p-6 space-y-4">
      <div className="flex items-center justify-center py-4">
        <div className="w-48 h-16 flex items-end justify-between gap-1 relative">
          {[4, 6, 5, 8, 7, 9, 8, 10, 9, 11, 10, 12].map((h, i) => (
            <motion.div
              key={i}
              className="flex-1 rounded-t-sm bg-cyan-400/50"
              initial={{ height: 0 }}
              animate={{ height: `${h * 5}px` }}
              transition={{ delay: i * 0.06, duration: 0.5, ease: "easeOut", repeat: Infinity, repeatType: "reverse", repeatDelay: 0.8 }}
            />
          ))}
        </div>
      </div>
      <p className="text-center text-xs font-mono text-cyan-400 animate-pulse tracking-wider uppercase">
        Projecting 12-month cashflow...
      </p>
      <Shimmer className="h-12 w-full rounded-xl" />
    </div>
  );
}

function DecisionLabLoader() {
  return (
    <ShimmerSkeleton rows={2} headerText="Calculating decision parameters..." />
  );
}

function ResultsShimmer() {
  return (
    <div className="space-y-6">
      <ShimmerSkeleton rows={3} headerText="Running deterministic engine..." />
      <ShimmerSkeleton rows={2} headerText="Projecting goal timelines..." />
      <ShimmerSkeleton rows={2} headerText="Assessing buffer impact..." />
    </div>
  );
}

export function ContextualLoader({ module, text }: LoaderProps) {
  switch (module) {
    case "moneymap":
      return <MoneyMapLoader />;
    case "futureflow":
      return <FutureFlowLoader />;
    case "decisionlab":
      return <DecisionLabLoader />;
    case "bestmove":
    case "decisionwhy":
    case "safetynet":
    case "impactmap":
    case "goalpath":
      return <ResultsShimmer />;
    default:
      return (
        <ShimmerSkeleton rows={3} headerText={text || "Processing..."} />
      );
  }
}
