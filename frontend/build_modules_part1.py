# -*- coding: utf-8 -*-
import os

files = {}

files["components/modules/MoneyMap.tsx"] = """"use client";

import React, { useState } from "react";
import { UserFinancialState, Obligation } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { Wallet, ArrowDownRight, Layers, PiggyBank, Plus, Trash2, Edit3, Check } from "lucide-react";

interface MoneyMapProps {
  state: UserFinancialState;
  onChange: (updated: UserFinancialState) => void;
}

export function MoneyMap({ state, onChange }: MoneyMapProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [newObligationName, setNewObligationName] = useState("");
  const [newObligationAmount, setNewObligationAmount] = useState<number>(0);

  const totalIncome = state.monthly_income + state.additional_income;
  const totalExpenses = state.recurring_expenses + state.discretionary_expenses;
  const currentSurplus = totalIncome - totalExpenses;

  const handleIncomeChange = (val: number) => {
    onChange({ ...state, monthly_income: Math.max(0, val) });
  };

  const handleRecurringChange = (val: number) => {
    onChange({ ...state, recurring_expenses: Math.max(0, val) });
  };

  const handleDiscretionaryChange = (val: number) => {
    onChange({ ...state, discretionary_expenses: Math.max(0, val) });
  };

  const handleSavingsChange = (val: number) => {
    onChange({ ...state, current_savings: Math.max(0, val) });
  };

  const addObligation = () => {
    if (!newObligationName || newObligationAmount <= 0) return;
    const newOb: Obligation = {
      name: newObligationName,
      amount: newObligationAmount,
      recurrence: "one_time"
    };
    onChange({
      ...state,
      upcoming_obligations: [...state.upcoming_obligations, newOb]
    });
    setNewObligationName("");
    setNewObligationAmount(0);
  };

  const removeObligation = (index: number) => {
    const updated = state.upcoming_obligations.filter((_, idx) => idx !== index);
    onChange({ ...state, upcoming_obligations: updated });
  };

  return (
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              01 — MoneyMap
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Current Financial Architecture & Liquid Flow
          </p>
        </div>

        <button
          onClick={() => setIsEditing(!isEditing)}
          className={
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all " +
            (isEditing
              ? "bg-cyan-500 text-black shadow-[0_0_15px_rgba(6,182,212,0.4)]"
              : "bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700")
          }
        >
          {isEditing ? (
            <>
              <Check className="w-3.5 h-3.5" /> Done Editing
            </>
          ) : (
            <>
              <Edit3 className="w-3.5 h-3.5" /> Adjust Parameters
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 my-6 relative">
        <motion.div
          whileHover={{ y: -3 }}
          className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80 relative"
        >
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
            <span>Monthly Inflow</span>
            <Wallet className="w-4 h-4 text-cyan-500" />
          </div>
          {isEditing ? (
            <div className="mt-2">
              <input
                type="number"
                value={state.monthly_income}
                onChange={(e) => handleIncomeChange(Number(e.target.value))}
                className="w-full px-2 py-1 text-sm bg-white dark:bg-slate-800 border border-cyan-500 rounded text-slate-900 dark:text-white font-mono"
              />
            </div>
          ) : (
            <div className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight font-mono">
              {formatINR(totalIncome)}
            </div>
          )}
          <div className="text-[11px] text-cyan-600 dark:text-cyan-400 mt-2 font-mono">
            Primary + Extra regular
          </div>
        </motion.div>

        <motion.div
          whileHover={{ y: -3 }}
          className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80"
        >
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
            <span>Monthly Expenses</span>
            <ArrowDownRight className="w-4 h-4 text-rose-500" />
          </div>
          {isEditing ? (
            <div className="space-y-1.5 mt-1">
              <div>
                <label className="text-[10px] text-slate-400">Fixed/Recurring</label>
                <input
                  type="number"
                  value={state.recurring_expenses}
                  onChange={(e) => handleRecurringChange(Number(e.target.value))}
                  className="w-full px-2 py-0.5 text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded text-slate-900 dark:text-white font-mono"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400">Discretionary</label>
                <input
                  type="number"
                  value={state.discretionary_expenses}
                  onChange={(e) => handleDiscretionaryChange(Number(e.target.value))}
                  className="w-full px-2 py-0.5 text-xs bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded text-slate-900 dark:text-white font-mono"
                />
              </div>
            </div>
          ) : (
            <>
              <div className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight font-mono">
                {formatINR(totalExpenses)}
              </div>
              <div className="text-[11px] text-rose-500 dark:text-rose-400 mt-2 font-mono">
                Fixed: {formatINR(state.recurring_expenses)} | Disc: {formatINR(state.discretionary_expenses)}
              </div>
            </>
          )}
        </motion.div>

        <motion.div
          whileHover={{ y: -3 }}
          className={
            "p-4 rounded-xl border relative " +
            (currentSurplus >= 0
              ? "bg-emerald-500/10 dark:bg-emerald-950/20 border-emerald-500/30 text-emerald-900 dark:text-emerald-300"
              : "bg-rose-500/10 dark:bg-rose-950/20 border-rose-500/30 text-rose-900 dark:text-rose-300")
          }
        >
          <div className="flex items-center justify-between text-xs mb-1 opacity-90">
            <span>Monthly Surplus</span>
            <Layers className="w-4 h-4" />
          </div>
          <div className="text-xl font-extrabold tracking-tight font-mono">
            {formatINR(currentSurplus)}
          </div>
          <div className="text-[11px] mt-2 font-mono opacity-80">
            {currentSurplus >= 0 ? "Liquid capacity growth" : "Cashflow deficit"}
          </div>
        </motion.div>

        <motion.div
          whileHover={{ y: -3 }}
          className="p-4 rounded-xl bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800/80"
        >
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
            <span>Current Liquid Funds</span>
            <PiggyBank className="w-4 h-4 text-emerald-500" />
          </div>
          {isEditing ? (
            <div className="mt-2">
              <input
                type="number"
                value={state.current_savings}
                onChange={(e) => handleSavingsChange(Number(e.target.value))}
                className="w-full px-2 py-1 text-sm bg-white dark:bg-slate-800 border border-emerald-500 rounded text-slate-900 dark:text-white font-mono"
              />
            </div>
          ) : (
            <div className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight font-mono text-emerald-600 dark:text-emerald-400">
              {formatINR(state.current_savings)}
            </div>
          )}
          <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-2 font-mono">
            Baseline liquidity available
          </div>
        </motion.div>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-200/80 dark:border-slate-800/80">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
            Upcoming Financial Obligations ({state.upcoming_obligations.length})
          </h3>
        </div>

        {state.upcoming_obligations.length === 0 ? (
          <p className="text-xs text-slate-400 italic">No scheduled short-term obligations recorded.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {state.upcoming_obligations.map((ob, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-100/80 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs"
              >
                <div>
                  <span className="font-medium text-slate-900 dark:text-slate-200">{ob.name}</span>
                  <div className="text-[11px] text-slate-400">{formatINR(ob.amount)} ({ob.recurrence || "one_time"})</div>
                </div>
                {isEditing && (
                  <button
                    onClick={() => removeObligation(idx)}
                    className="text-rose-400 hover:text-rose-500 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        <AnimatePresence>
          {isEditing && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 p-3 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 flex flex-wrap gap-2 items-center text-xs"
            >
              <input
                type="text"
                placeholder="Obligation Name (e.g. Annual Insurance)"
                value={newObligationName}
                onChange={(e) => setNewObligationName(e.target.value)}
                className="px-2.5 py-1.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 flex-1 text-slate-900 dark:text-white"
              />
              <input
                type="number"
                placeholder="Amount (?)"
                value={newObligationAmount || ""}
                onChange={(e) => setNewObligationAmount(Number(e.target.value))}
                className="px-2.5 py-1.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 w-28 text-slate-900 dark:text-white font-mono"
              />
              <button
                onClick={addObligation}
                className="px-3 py-1.5 rounded bg-cyan-500 text-black font-semibold flex items-center gap-1 hover:bg-cyan-400"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
"""

files["components/modules/FutureFlow.tsx"] = """"use client";

import React, { useState } from "react";
import { PeriodProjection } from "@/types/financial";
import { formatINR } from "@/lib/utils";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { TrendingUp, Clock } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

interface FutureFlowProps {
  projections: PeriodProjection[];
  purchasePrice?: number;
}

export function FutureFlow({ projections, purchasePrice = 0 }: FutureFlowProps) {
  const [timeHorizon, setTimeHorizon] = useState<1 | 3 | 6 | 12>(12);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const filteredData = projections.slice(0, timeHorizon);

  return (
    <div className="glass-panel p-6 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white uppercase">
              02 — FutureFlow
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Projected Cash-Flow Trajectory (Baseline vs Purchase Scenario)
          </p>
        </div>

        <div className="flex items-center bg-slate-100 dark:bg-slate-900/80 p-1 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-mono">
          <Clock className="w-3.5 h-3.5 mx-2 text-slate-400" />
          {([1, 3, 6, 12] as const).map((h) => (
            <button
              key={h}
              onClick={() => setTimeHorizon(h)}
              className={
                "px-3 py-1 rounded-lg transition-all " +
                (timeHorizon === h
                  ? "bg-cyan-500 text-black font-bold shadow-[0_0_10px_rgba(6,182,212,0.5)]"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white")
              }
            >
              {h === 12 ? "1Y" : `${h}M`}
            </button>
          ))}
        </div>
      </div>

      <div className="h-72 w-full mt-6">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorBaseline" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorPurchase" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke={isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}
            />

            <XAxis
              dataKey="period_label"
              stroke={isDark ? "#64748b" : "#94a3b8"}
              fontSize={11}
              tickLine={false}
            />

            <YAxis
              stroke={isDark ? "#64748b" : "#94a3b8"}
              fontSize={11}
              tickFormatter={(v) => "?" + (v >= 1000 ? Math.round(v / 1000) + "k" : v)}
              tickLine={false}
              axisLine={false}
            />

            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload || !payload.length) return null;
                return (
                  <div className="p-3 rounded-xl bg-slate-900/95 border border-slate-700/80 text-white shadow-xl backdrop-blur-md text-xs font-mono space-y-1.5">
                    <div className="text-slate-400 font-bold border-b border-slate-700 pb-1">
                      {label}
                    </div>
                    <div className="flex items-center justify-between gap-4 text-emerald-400">
                      <span>Baseline Savings:</span>
                      <span className="font-bold">{formatINR(Number(payload[0]?.value) || 0)}</span>
                    </div>
                    {purchasePrice > 0 && (
                      <div className="flex items-center justify-between gap-4 text-rose-400">
                        <span>Post-Purchase:</span>
                        <span className="font-bold">{formatINR(Number(payload[1]?.value) || 0)}</span>
                      </div>
                    )}
                  </div>
                );
              }}
            />

            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              formatter={(value) => (
                <span className="text-xs text-slate-600 dark:text-slate-300 font-medium mr-4">
                  {value}
                </span>
              )}
            />

            <Area
              type="monotone"
              dataKey="baseline_savings"
              name="Baseline Trajectory"
              stroke="#10b981"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#colorBaseline)"
            />

            {purchasePrice > 0 && (
              <Area
                type="monotone"
                dataKey="purchase_savings"
                name="Purchase Scenario"
                stroke="#f43f5e"
                strokeWidth={2.5}
                strokeDasharray="5 5"
                fillOpacity={1}
                fill="url(#colorPurchase)"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-200/80 dark:border-slate-800/80 text-xs text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-1.5">
          <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
          <span>Projections assume constant recurring cashflows.</span>
        </div>
        <div className="font-mono text-[11px]">
          Horizon: {timeHorizon} Months ({timeHorizon * 4} Weeks)
        </div>
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
