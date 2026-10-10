"use client";

import React from "react";
import { DecisionResult, UserFinancialState, PurchaseDecision } from "@/types/financial";
import { ModelComparison } from "@/components/modules/ModelComparison";
import { useCountUp } from "@/lib/useCountUp";
import { CheckCircle2, Clock, TrendingUp, TrendingDown, Shield, Zap } from "lucide-react";
import { motion } from "framer-motion";

interface BestMoveProps {
  decision: DecisionResult;
  evaluatedInput: (UserFinancialState & { purchase: PurchaseDecision }) | null;
}

function AnimatedINR({ value, prefix = "₹" }: { value: number; prefix?: string }) {
  const count = useCountUp(Math.abs(value));
  if (value < 0) return <>-{prefix}{count.toLocaleString("en-IN")}</>;
  return <>{prefix}{count.toLocaleString("en-IN")}</>;
}

export function BestMove({ decision, evaluatedInput }: BestMoveProps) {
  const isWait = decision.recommendation === "WAIT";
  const stats = [
    {
      label: "Capital Recovery",
      value: decision.monthly_surplus > 0 ? `~${decision.consequence.recovery_time_weeks}w` : "No surplus",
      icon: Clock,
      color: "text-cyan-500 dark:text-cyan-400",
      bg: "bg-cyan-500/8 dark:bg-cyan-500/10",
      border: "border-cyan-500/20",
    },
    {
      label: "Buffer Reduction",
      value: `-${decision.buffer_impact.buffer_reduction_percentage.toFixed(0)}%`,
      icon: TrendingDown,
      color: "text-rose-500 dark:text-rose-400",
      bg: "bg-rose-500/8 dark:bg-rose-500/10",
      border: "border-rose-500/20",
    },
    {
      label: "Monthly Surplus",
      value: <AnimatedINR value={decision.monthly_surplus} />,
      icon: TrendingUp,
      color: "text-emerald-500 dark:text-emerald-400",
      bg: "bg-emerald-500/8 dark:bg-emerald-500/10",
      border: "border-emerald-500/20",
    },
    {
      label: "Safety Runway",
      value: `${decision.buffer_impact.purchase_emergency_runway_months.toFixed(1)}mo`,
      icon: Shield,
      color: "text-violet-500 dark:text-violet-400",
      bg: "bg-violet-500/8 dark:bg-violet-500/10",
      border: "border-violet-500/20",
    },
  ];

  return (
    <motion.div
      className="best-move-panel glass-panel hover-lift p-6 sm:p-8 relative overflow-hidden"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Ambient glow */}
      <div
        className={`absolute -top-24 -right-24 w-80 h-80 rounded-full blur-3xl pointer-events-none transition-all duration-700 ${
          isWait ? "opacity-15 bg-amber-500" : "opacity-20 bg-emerald-500"
        }`}
      />

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-slate-200/70 dark:border-slate-800/70 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
            <h2 className="text-lg font-black tracking-tight text-slate-900 dark:text-white uppercase">
              07 — Best Move
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 ml-4.5">
            Definitive Synthesis &amp; Recommended Action
          </p>
        </div>
        <span className="text-[11px] font-mono text-slate-400 px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-800">
          Deterministic Assessment
        </span>
      </div>

      {/* Hero Recommendation */}
      <div className="my-8 flex flex-col items-center text-center max-w-2xl mx-auto">
        <motion.div
          key={decision.recommendation}
          initial={{ scale: 0.7, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 20 }}
          className={`px-8 py-4 rounded-2xl font-black text-xl sm:text-3xl tracking-wide uppercase mb-5 border-2 flex items-center gap-3 result-glow ${
            isWait
              ? "bg-amber-500/10 text-amber-500 border-amber-500/50 shadow-[0_0_40px_rgba(245,158,11,0.25)]"
              : "bg-emerald-500/10 text-emerald-400 border-emerald-500/50 shadow-[0_0_40px_rgba(16,185,129,0.25)]"
          }`}
        >
          {isWait ? <Clock className="w-8 h-8" /> : <CheckCircle2 className="w-8 h-8" />}
          <span>YOUR BEST MOVE: {decision.recommendation}</span>
        </motion.div>

        <motion.h3
          key={decision.headline}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight leading-snug"
        >
          &ldquo;{decision.headline}&rdquo;
        </motion.h3>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.35, duration: 0.5 }}
          className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-3 leading-relaxed max-w-lg"
        >
          {decision.bottom_line}
        </motion.p>
      </div>

      {evaluatedInput && <ModelComparison />}

      {!!decision.justification?.length && (
        <section aria-label="Reasons for the recommendation" className="mb-6 rounded-2xl border border-slate-200 dark:border-slate-700 p-5 sm:p-6">
          <h3 className="text-base font-bold text-slate-900 dark:text-white">Why {decision.recommendation}? The numbers behind it</h3>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Calculated from your inputs using the financial rules.</p>
          <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-relaxed text-slate-600 dark:text-slate-300 marker:text-cyan-600 dark:marker:text-cyan-400">
            {decision.justification.map((point, index) => <li key={`${point.keyword}-${index}`}>
              <strong className="rounded bg-cyan-500/10 px-1 py-0.5 font-semibold text-cyan-800 dark:text-cyan-200">{point.keyword}</strong>
              {" — "}{point.evidence}
            </li>)}
          </ul>
        </section>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-5 border-t border-slate-200/70 dark:border-slate-800/70">
        {stats.map((s, idx) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * idx + 0.4, duration: 0.4 }}
            className={`p-4 rounded-xl ${s.bg} border ${s.border} text-center group hover:scale-105 transition-transform duration-200`}
          >
            <s.icon className={`w-4 h-4 mx-auto mb-2 ${s.color}`} />
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
              {s.label}
            </span>
            <span className={`text-lg font-black font-mono ${s.color}`}>
              {s.value}
            </span>
          </motion.div>
        ))}
      </div>

      {/* Consequence wording */}
      <div className="mt-5 flex items-start gap-2 p-3 rounded-xl bg-slate-100/60 dark:bg-slate-900/50 border border-slate-200/60 dark:border-slate-800/60">
        <Zap className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
          {decision.consequence.summary_wording}
        </p>
      </div>
    </motion.div>
  );
}
