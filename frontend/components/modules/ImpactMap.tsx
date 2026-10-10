"use client";

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
      detail: `Capital absorbs \u20b9${decision.purchase_price.toLocaleString("en-IN")}, reducing available cash from \u20b9${decision.baseline_liquidity.toLocaleString("en-IN")} to \u20b9${decision.post_purchase_liquidity.toLocaleString("en-IN")}.`,
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
      detail: `At your current net surplus of \u20b9${decision.monthly_surplus.toLocaleString("en-IN")}/mo, full recovery takes approximately ${decision.consequence.recovery_time_weeks} weeks.`,
      status: decision.consequence.recovery_time_weeks > 20 ? "warning" : "safe",
    },
  ];

  return (
    <div className="glass-panel hover-lift p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
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
