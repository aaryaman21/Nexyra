"use client";

import React from "react";
import { BufferAssessment } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { ShieldCheck, AlertTriangle, ShieldX } from "lucide-react";
import { motion } from "framer-motion";

interface SafetyNetProps {
  bufferImpact: BufferAssessment;
  postLiquidity: number;
}

export function SafetyNet({ bufferImpact, postLiquidity }: SafetyNetProps) {
  const resilience = bufferImpact.purchase_resilience;

  const getResilienceBadge = () => {
    switch (resilience) {
      case "Comfortable":
        return {
          icon: ShieldCheck,
          color: "text-emerald-500",
          bgColor: "bg-emerald-500/10 border-emerald-500/30",
          label: "Comfortable",
          desc: "Buffer exceeds 6+ months of recurring living expenses. High resilience.",
        };
      case "Manageable":
        return {
          icon: ShieldCheck,
          color: "text-cyan-500",
          bgColor: "bg-cyan-500/10 border-cyan-500/30",
          label: "Manageable",
          desc: "Buffer maintains 3-6 months of expenses. Healthy baseline cushion.",
        };
      case "Tight":
        return {
          icon: AlertTriangle,
          color: "text-amber-500",
          bgColor: "bg-amber-500/10 border-amber-500/30",
          label: "Tight",
          desc: "Runway compressed between 1-3 months. Susceptible to unexpected obligations.",
        };
      case "Risky":
      default:
        return {
          icon: ShieldX,
          color: "text-rose-500",
          bgColor: "bg-rose-500/10 border-rose-500/30",
          label: "Risky",
          desc: "Post-purchase runway under 1 month. Critical exposure to emergencies.",
        };
    }
  };

  const badge = getResilienceBadge();
  const Icon = badge.icon;

  return (
    <div className="glass-panel hover-lift p-6 relative overflow-hidden">
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-slate-200/70 dark:border-slate-800/70 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              05 — Safety Net
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Emergency Buffer & Post-Purchase Resilience Evaluation
          </p>
        </div>

        <div className={`flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-bold ${badge.bgColor} ${badge.color}`}>
          <Icon className="w-4 h-4" />
          <span>{badge.label} Resilience</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-5">
        <div className="stat-card">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Post-Purchase Liquidity
          </span>
          <div className="text-2xl font-black text-slate-900 dark:text-white font-mono">
            {formatINR(postLiquidity)}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Funds remaining immediately after transaction
          </p>
        </div>

        <div className="stat-card">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Emergency Runway
          </span>
          <div className="text-2xl font-black text-slate-900 dark:text-white font-mono">
            {bufferImpact.purchase_emergency_runway_months.toFixed(1)} mo
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Down from {bufferImpact.baseline_emergency_runway_months.toFixed(1)} months baseline
          </p>
        </div>

        <div className="stat-card">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Buffer Reduction
          </span>
          <div className="text-2xl font-black text-rose-500 dark:text-rose-400 font-mono">
            -{bufferImpact.buffer_reduction_percentage.toFixed(0)}%
          </div>
          {/* Animated reduction bar */}
          <div className="mt-2 h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-rose-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, bufferImpact.buffer_reduction_percentage)}%` }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-slate-100/50 dark:bg-slate-900/40 border border-slate-200/80 dark:border-slate-800/80">
        <div className="flex justify-between items-center text-xs mb-2">
          <span className="font-semibold text-slate-800 dark:text-slate-200">
            Cushion Status Description:
          </span>
          <span className="text-[11px] text-slate-400 font-mono">
            Benchmark: 3.0 Months
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300">
          {badge.desc}
        </p>
      </div>
    </div>
  );
}
