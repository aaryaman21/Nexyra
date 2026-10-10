# -*- coding: utf-8 -*-
import os

files = {}

files["components/modules/SafetyNet.tsx"] = """"use client";

import React from "react";
import { BufferAssessment } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { ShieldCheck, AlertTriangle, ShieldX } from "lucide-react";

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
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-6">
        <div className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Post-Purchase Liquidity
          </span>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white font-mono">
            {formatINR(postLiquidity)}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Funds remaining immediately after transaction
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Emergency Runway
          </span>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white font-mono">
            {bufferImpact.purchase_emergency_runway_months.toFixed(1)} Months
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Down from {bufferImpact.baseline_emergency_runway_months.toFixed(1)} months baseline
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80">
          <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">
            Buffer Reduction
          </span>
          <div className="text-2xl font-extrabold text-rose-500 dark:text-rose-400 font-mono">
            -{bufferImpact.buffer_reduction_percentage.toFixed(0)}%
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Safe recommended target: {formatINR(bufferImpact.safe_minimum_buffer)}
          </p>
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
"""

files["components/modules/ImpactMap.tsx"] = """"use client";

import React, { useState } from "react";
import { DecisionResult } from "@/types/financial";
import { motion, AnimatePresence } from "framer-motion";
import { GitCommit, ArrowRight, Info, Zap } from "lucide-react";

interface ImpactMapProps {
  decision: DecisionResult;
}

export function ImpactMap({ decision }: ImpactMapProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>("liquidity");

  const nodes = [
    {
      id: "liquidity",
      title: "Liquid Capital",
      short: `-${decision.buffer_impact.buffer_reduction_percentage.toFixed(0)}%`,
      detail: `Capital absorbs ?${decision.purchase_price.toLocaleString("en-IN")}, reducing available cash from ?${decision.baseline_liquidity.toLocaleString("en-IN")} to ?${decision.post_purchase_liquidity.toLocaleString("en-IN")}.`,
      status: decision.post_purchase_liquidity < 0 ? "critical" : "warning",
    },
    {
      id: "buffer",
      title: "Safety Net Runway",
      short: `${decision.buffer_impact.purchase_emergency_runway_months.toFixed(1)} mo`,
      detail: `Living expense coverage shifts from ${decision.buffer_impact.baseline_emergency_runway_months.toFixed(1)} months down to ${decision.buffer_impact.purchase_emergency_runway_months.toFixed(1)} months.`,
      status: decision.buffer_impact.purchase_resilience === "Comfortable" ? "safe" : "warning",
    },
    {
      id: "goals",
      title: "Goal Milestones",
      short: decision.goal_impacts.length > 0 ? `${decision.goal_impacts[0].delay_in_weeks}w delay` : "No delay",
      detail: decision.goal_impacts.length > 0
        ? decision.goal_impacts.map((g) => `${g.goal_name}: +${g.delay_in_weeks} weeks`).join(", ")
        : "No active targets disrupted.",
      status: decision.goal_impacts.some((g) => g.delay_in_weeks > 4) ? "warning" : "safe",
    },
    {
      id: "recovery",
      title: "Capital Recovery",
      short: `${decision.consequence.recovery_time_weeks} weeks`,
      detail: `At your current net surplus of ?${decision.monthly_surplus.toLocaleString("en-IN")}/mo, full recovery takes approximately ${decision.consequence.recovery_time_weeks} weeks.`,
      status: decision.consequence.recovery_time_weeks > 20 ? "warning" : "safe",
    },
  ];

  return (
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              06 — Impact Map
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Interconnected Personal Financial Consequence Network (Click node to inspect)
          </p>
        </div>

        <div className="text-xs font-mono text-cyan-500 dark:text-cyan-400 flex items-center gap-1">
          <Zap className="w-3.5 h-3.5" /> Ripple Analysis
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 my-6">
        {nodes.map((node) => {
          const isSelected = selectedNode === node.id;
          return (
            <motion.div
              key={node.id}
              whileHover={{ y: -3 }}
              onClick={() => setSelectedNode(node.id)}
              className={`p-4 rounded-xl cursor-pointer border transition-all ${
                isSelected
                  ? "bg-cyan-500/15 border-cyan-400 dark:border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.25)]"
                  : "bg-slate-100/70 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800/80 hover:border-slate-300 dark:hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-2">
                <span className="font-semibold">{node.title}</span>
                <GitCommit className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div className="text-xl font-extrabold text-slate-900 dark:text-white font-mono">
                {node.short}
              </div>
              <div className="text-[10px] text-slate-400 mt-2 font-mono flex items-center gap-1">
                <span>Click for details</span>
                <ArrowRight className="w-2.5 h-2.5" />
              </div>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        {selectedNode && (
          <motion.div
            key={selectedNode}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="p-4 rounded-xl bg-slate-100 dark:bg-slate-900 border border-cyan-500/30 flex items-start gap-3"
          >
            <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-1">
                {nodes.find((n) => n.id === selectedNode)?.title} Impact
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed font-mono">
                {nodes.find((n) => n.id === selectedNode)?.detail}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
"""

files["components/modules/BestMove.tsx"] = """"use client";

import React from "react";
import { DecisionResult } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { CheckCircle2, Clock } from "lucide-react";
import { motion } from "framer-motion";

interface BestMoveProps {
  decision: DecisionResult;
}

export function BestMove({ decision }: BestMoveProps) {
  const isWait = decision.recommendation === "WAIT";

  return (
    <div className="glass-panel p-6 sm:p-8 relative overflow-hidden transition-all duration-300">
      <div
        className={`absolute -top-20 -right-20 w-72 h-72 rounded-full blur-3xl pointer-events-none opacity-20 ${
          isWait ? "bg-amber-500" : "bg-emerald-500"
        }`}
      />

      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              07 — Best Move
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Definitive Synthesis & Recommended Action
          </p>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          Deterministic Assessment
        </span>
      </div>

      <div className="my-8 flex flex-col items-center text-center max-w-2xl mx-auto">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`px-8 py-3 rounded-2xl font-black text-2xl tracking-widest uppercase mb-4 border shadow-2xl flex items-center gap-3 ${
            isWait
              ? "bg-amber-500/10 text-amber-500 border-amber-500/40 shadow-[0_0_30px_rgba(245,158,11,0.2)]"
              : "bg-emerald-500/10 text-emerald-400 border-emerald-500/40 shadow-[0_0_30px_rgba(16,185,129,0.2)]"
          }`}
        >
          {isWait ? <Clock className="w-7 h-7" /> : <CheckCircle2 className="w-7 h-7" />}
          <span>YOUR BEST MOVE: {decision.recommendation}</span>
        </motion.div>

        <h3 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight leading-snug">
          "{decision.headline}"
        </h3>

        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-3 leading-relaxed">
          {decision.bottom_line}
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-6 border-t border-slate-200/80 dark:border-slate-800/80">
        <div className="p-3 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 text-center">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
            Capital Recovery
          </span>
          <span className="text-base font-bold font-mono text-slate-800 dark:text-slate-200">
            ~{decision.consequence.recovery_time_weeks} Weeks
          </span>
        </div>

        <div className="p-3 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 text-center">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
            Consequence Horizon
          </span>
          <span className="text-base font-bold font-mono text-cyan-500 dark:text-cyan-400">
            ~{decision.consequence.consequence_horizon_weeks} Weeks
          </span>
        </div>

        <div className="p-3 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 text-center">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
            Buffer Reduction
          </span>
          <span className="text-base font-bold font-mono text-rose-500 dark:text-rose-400">
            -{decision.buffer_impact.buffer_reduction_percentage.toFixed(0)}%
          </span>
        </div>

        <div className="p-3 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 text-center">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
            Monthly Surplus
          </span>
          <span className="text-base font-bold font-mono text-emerald-500 dark:text-emerald-400">
            {formatINR(decision.monthly_surplus)}
          </span>
        </div>
      </div>

      <div className="mt-4 text-center">
        <p className="text-[11px] text-slate-400 italic">
          {decision.consequence.summary_wording}
        </p>
      </div>
    </div>
  );
}
"""

files["components/modules/DecisionWhy.tsx"] = """"use client";

import React, { useEffect, useState } from "react";
import { DecisionResult, ExplanationResponse } from "@/types/financial";
import { FileText } from "lucide-react";
import { motion } from "framer-motion";

interface DecisionWhyProps {
  decision: DecisionResult;
}

export function DecisionWhy({ decision }: DecisionWhyProps) {
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchExplanation() {
      try {
        const res = await fetch("/api/agri/models");
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setExplanation(data.models?.length
            ? "Agricultural model evaluations are available for selected markets."
            : "No agricultural forecast is available until verified market prices have been imported and evaluated.");
        }
      } catch {
        if (isMounted) {
          setExplanation(null);
        }
      }
    }

    fetchExplanation();
    return () => {
      isMounted = false;
    };
  }, [decision]);

  return (
    <div className="glass-panel p-6 sm:p-8 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              08 — Decision Why
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Transparent, Explainable Rationale & Supporting Evidence
          </p>
        </div>

        <div className="flex items-center gap-1 text-xs font-mono text-cyan-500 dark:text-cyan-400">
          <FileText className="w-3.5 h-3.5" /> Explainability Engine
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {explanation ? (
          <>
            <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-900 dark:text-cyan-200 text-xs sm:text-sm font-medium leading-relaxed">
              {explanation.summary}
            </div>

            <div className="space-y-3 pt-2">
              {explanation.sections.map((sec, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 flex items-start gap-4"
                >
                  <div className="px-2.5 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400 font-mono font-bold text-xs">
                    {sec.number}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-200 tracking-wide uppercase mb-1">
                      {sec.title}
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-mono">
                      {sec.detail}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 font-mono mt-4">
              <span className="text-cyan-500 font-bold block mb-1">BOTTOM LINE:</span>
              {explanation.bottom_line}
            </div>
          </>
        ) : (
          <div className="py-8 text-center text-xs text-slate-400">
            Synthesizing plain-language rationale...
          </div>
        )}
      </div>
    </div>
  );
}
"""

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {path} ({len(content)} chars)")
