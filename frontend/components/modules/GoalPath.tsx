"use client";

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
    <div className="glass-panel hover-lift p-6 relative overflow-hidden">
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-slate-200/70 dark:border-slate-800/70 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              03 — GoalPath
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Active Financial Targets & Timeline Disruption Analysis
          </p>
        </div>

        {onAddGoal && (
          <motion.button
            onClick={() => setShowAddModal(!showAddModal)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.96 }}
            className="btn-primary text-black text-xs"
          >
            <Plus className="w-3.5 h-3.5" /> Define Goal
          </motion.button>
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
                className="input-field text-xs"
              />
              <input
                type="number"
                placeholder="Target Amount (₹)"
                value={newGoalTarget || ""}
                onChange={(e) => setNewGoalTarget(Number(e.target.value))}
                className="input-field text-xs"
              />
              <input
                type="number"
                placeholder="Current Saved (₹)"
                value={newGoalCurrent || ""}
                onChange={(e) => setNewGoalCurrent(Number(e.target.value))}
                className="input-field text-xs"
              />
              <input
                type="date"
                value={newGoalDeadline}
                onChange={(e) => setNewGoalDeadline(e.target.value)}
                className="input-field text-xs"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowAddModal(false)}
                className="btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateGoal}
                className="btn-primary text-black"
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
                        className="btn-danger py-1 px-2"
                        title="Remove goal"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden my-2 relative">
                  <motion.div
                    className="h-full bg-gradient-to-r from-cyan-500 to-violet-400"
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
