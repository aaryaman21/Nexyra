# -*- coding: utf-8 -*-
import os

files = {}

files["components/modules/GoalPath.tsx"] = """"use client";

import React, { useState } from "react";
import { FinancialGoal, GoalProjectionResult } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Target, Calendar, AlertTriangle, CheckCircle2, Plus, Trash2 } from "lucide-react";

interface GoalPathProps {
  goals: FinancialGoal[];
  goalImpacts: GoalProjectionResult[];
  onAddGoal?: (goal: FinancialGoal) => void;
  onRemoveGoal?: (goalId: string) => void;
}

export function GoalPath({ goals, goalImpacts, onAddGoal, onRemoveGoal }: GoalPathProps) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [newGoalName, setNewGoalName] = useState("");
  const [newGoalTarget, setNewGoalTarget] = useState<number>(0);
  const [newGoalCurrent, setNewGoalCurrent] = useState<number>(0);
  const [newGoalDeadline, setNewGoalDeadline] = useState("2027-06-30");

  const handleCreateGoal = () => {
    if (!newGoalName || newGoalTarget <= 0 || !onAddGoal) return;
    onAddGoal({
      id: "goal_" + Date.now(),
      name: newGoalName,
      target_amount: newGoalTarget,
      current_amount: newGoalCurrent,
      deadline: newGoalDeadline,
    });
    setNewGoalName("");
    setNewGoalTarget(0);
    setNewGoalCurrent(0);
    setShowAddModal(false);
  };

  return (
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              03 — GoalPath
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Active Financial Targets & Timeline Disruption Analysis
          </p>
        </div>

        {onAddGoal && (
          <button
            onClick={() => setShowAddModal(!showAddModal)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-cyan-500 text-black hover:bg-cyan-400 transition-all shadow-[0_0_10px_rgba(6,182,212,0.4)]"
          >
            <Plus className="w-3.5 h-3.5" /> Define Goal
          </button>
        )}
      </div>

      <AnimatePresence>
        {showAddModal && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="my-4 p-4 rounded-xl bg-slate-100 dark:bg-slate-900/90 border border-cyan-500/40 space-y-3"
          >
            <div className="text-xs font-bold text-slate-800 dark:text-slate-200">
              New Financial Goal Target
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <input
                type="text"
                placeholder="Goal Name (e.g. Emergency Fund)"
                value={newGoalName}
                onChange={(e) => setNewGoalName(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white"
              />
              <input
                type="number"
                placeholder="Target Amount (?)"
                value={newGoalTarget || ""}
                onChange={(e) => setNewGoalTarget(Number(e.target.value))}
                className="px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white font-mono"
              />
              <input
                type="number"
                placeholder="Current Saved (?)"
                value={newGoalCurrent || ""}
                onChange={(e) => setNewGoalCurrent(Number(e.target.value))}
                className="px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white font-mono"
              />
              <input
                type="date"
                value={newGoalDeadline}
                onChange={(e) => setNewGoalDeadline(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-white font-mono"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1 rounded text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateGoal}
                className="px-4 py-1 rounded bg-cyan-500 text-black font-semibold text-xs hover:bg-cyan-400"
              >
                Save Target
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6 space-y-4">
        {goals.length === 0 ? (
          <div className="text-center py-8 border border-dashed border-slate-300 dark:border-slate-800 rounded-xl">
            <Target className="w-8 h-8 mx-auto text-slate-400 mb-2" />
            <p className="text-xs text-slate-500">No active goals linked yet. Add a goal to see how purchases affect milestones.</p>
          </div>
        ) : (
          goals.map((g, idx) => {
            const impact = goalImpacts.find(
              (gi) => gi.goal_name.toLowerCase() === g.name.toLowerCase() || gi.goal_id === g.id
            );
            const progress = Math.min(100, Math.round((g.current_amount / g.target_amount) * 100));
            const hasDelay = impact && impact.delay_in_weeks > 0;

            return (
              <div
                key={idx}
                className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 relative"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-900 dark:text-white">
                      {g.name}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      ({formatINR(g.current_amount)} / {formatINR(g.target_amount)})
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs font-mono">
                    <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>Target: {g.deadline}</span>
                    </div>
                    {onRemoveGoal && g.id && (
                      <button
                        onClick={() => onRemoveGoal(g.id!)}
                        className="text-slate-400 hover:text-rose-400 p-1"
                        title="Remove goal"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden my-2 relative">
                  <motion.div
                    className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400"
                    initial={{ width: 0 }}
                    animate={{ width: progress + "%" }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between text-xs mt-3 pt-2 border-t border-slate-200/50 dark:border-slate-800/50">
                  <span className="text-slate-500 dark:text-slate-400 font-mono">
                    {progress}% Funded
                  </span>

                  {impact ? (
                    hasDelay ? (
                      <span className="flex items-center gap-1 text-rose-500 dark:text-rose-400 font-medium">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Purchase shifts completion by ~{impact.delay_in_weeks} weeks
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-emerald-500 dark:text-emerald-400 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Timeline preserved on schedule
                      </span>
                    )
                  ) : (
                    <span className="text-slate-400">Baseline pacing</span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
"""

files["components/modules/DecisionLab.tsx"] = """"use client";

import React, { useState } from "react";
import { PurchaseDecision } from "@/types/financial";
import { ShoppingBag, Sparkles, RefreshCw, AlertCircle } from "lucide-react";

interface DecisionLabProps {
  currentPurchase: PurchaseDecision;
  onSimulate: (purchase: PurchaseDecision) => void;
  isLoading?: boolean;
}

export function DecisionLab({ currentPurchase, onSimulate, isLoading }: DecisionLabProps) {
  const [name, setName] = useState(currentPurchase.name);
  const [price, setPrice] = useState<number>(currentPurchase.price);
  const [plannedDate, setPlannedDate] = useState(currentPurchase.planned_date || "");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || price <= 0) return;
    onSimulate({
      name,
      price,
      planned_date: plannedDate || undefined,
    });
  };

  return (
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              04 — Decision Lab
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Planned Purchase Simulation (Scenario A Baseline vs Scenario B Purchase)
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400 text-xs font-mono">
          <Sparkles className="w-3 h-3" /> Core Engine
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              What are you thinking about buying?
            </label>
            <div className="relative">
              <ShoppingBag className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Ultra-Thin Developer Laptop"
                className="w-full pl-9 pr-3 py-2 bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-900 dark:text-white focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Purchase Price (?)
            </label>
            <input
              type="number"
              required
              min={1}
              value={price || ""}
              onChange={(e) => setPrice(Number(e.target.value))}
              placeholder="70000"
              className="w-full px-3 py-2 bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-900 dark:text-white font-mono focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Planned Purchase Date
            </label>
            <input
              type="date"
              value={plannedDate}
              onChange={(e) => setPlannedDate(e.target.value)}
              className="w-full px-3 py-2 bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl text-sm text-slate-900 dark:text-white font-mono focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between pt-4 border-t border-slate-200/80 dark:border-slate-800/80 gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <AlertCircle className="w-3.5 h-3.5 text-cyan-400" />
            <span>Deterministic engine calculates liquidity, buffer, and goal disruption.</span>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-bold rounded-xl text-xs uppercase tracking-wider transition-all shadow-[0_0_20px_rgba(6,182,212,0.4)] disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Simulating...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" /> Run Purchase Simulation
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
"""

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {path} ({len(content)} chars)")
