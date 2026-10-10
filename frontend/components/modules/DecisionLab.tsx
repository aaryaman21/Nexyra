"use client";

import React, { useState } from "react";
import { PurchaseDecision } from "@/types/financial";
import { ShoppingBag, Sparkles, RefreshCw, AlertCircle, Calendar, Tag } from "lucide-react";
import { motion } from "framer-motion";

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
    onSimulate({ name, price, planned_date: plannedDate || undefined });
  };

  return (
    <div className="glass-panel hover-lift p-6 relative overflow-hidden">
      {/* Subtle accent glow */}
      <div className="absolute -bottom-12 -right-12 w-48 h-48 rounded-full
        bg-gradient-to-tl from-cyan-500/8 to-indigo-500/6 blur-2xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-slate-200/70 dark:border-slate-800/70 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
            <h2 className="text-lg font-black tracking-tight text-slate-900 dark:text-white uppercase">
              04 — Decision Lab
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 ml-4.5">
            Planned Purchase Simulation — Scenario A vs Scenario B
          </p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full
          bg-cyan-500/10 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400 text-xs font-mono">
          <Sparkles className="w-3 h-3" /> Core Engine
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-4 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Purchase name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5 text-cyan-400" />
              What are you buying?
            </label>
            <div className="relative">
              <ShoppingBag className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="What are you considering?"
                className="input-field pl-9"
              />
            </div>
          </div>

          {/* Price */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Purchase Price (₹)
            </label>
            <input
              type="number"
              required
              min={1}
              value={price || ""}
              onChange={(e) => setPrice(Number(e.target.value))}
              placeholder="Enter purchase price"
              className="input-field"
            />
          </div>

          {/* Date */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              Planned Date
            </label>
            <input
              type="date"
              value={plannedDate}
              onChange={(e) => setPlannedDate(e.target.value)}
              className="input-field"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between pt-4
          border-t border-slate-200/70 dark:border-slate-800/70 gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <AlertCircle className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
            <span>Engine calculates liquidity impact, buffer safety &amp; goal disruption.</span>
          </div>

          <motion.button
            type="submit"
            disabled={isLoading}
            whileHover={!isLoading ? { scale: 1.04, y: -2 } : {}}
            whileTap={!isLoading ? { scale: 0.97 } : {}}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed text-black"
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Simulating...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Run Purchase Simulation
              </>
            )}
          </motion.button>
        </div>
      </form>
    </div>
  );
}
