"use client";

import React, { useState, useRef } from "react";
import { useInView } from "framer-motion";
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
  const chartRef = useRef<HTMLDivElement>(null);
  const chartVisible = useInView(chartRef, { once: true, amount: 0.2 });
  const baselineColor = isDark ? "#EAB995" : "#945039";
  const purchaseColor = isDark ? "#B7A2C8" : "#716080";

  const filteredData = projections.slice(0, timeHorizon);

  return (
    <div className="glass-panel hover-lift p-6 relative overflow-hidden">
      <div className="flex flex-wrap items-center justify-between pb-5 border-b border-slate-200/70 dark:border-slate-800/70 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
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
                  ? "bg-cyan-600 text-white dark:bg-cyan-300 dark:text-slate-900 font-bold shadow-sm"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white")
              }
            >
              {h === 12 ? "1Y" : `${h}M`}
            </button>
          ))}
        </div>
      </div>

      <div ref={chartRef} className="h-72 w-full mt-6">
        {chartVisible && (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorBaseline" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={baselineColor} stopOpacity={0.25} />
                <stop offset="95%" stopColor={baselineColor} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorPurchase" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={purchaseColor} stopOpacity={0.2} />
                <stop offset="95%" stopColor={purchaseColor} stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke={isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"}
            />

            <XAxis
              dataKey="period_label"
              stroke={isDark ? "#A496AB" : "#837184"}
              fontSize={11}
              tickLine={false}
            />

            <YAxis
              stroke={isDark ? "#A496AB" : "#837184"}
              fontSize={11}
              tickFormatter={(v) => "₹" + (v >= 1000 ? Math.round(v / 1000) + "k" : v)}
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
                    <div className="flex items-center justify-between gap-4 text-cyan-300">
                      <span>Baseline Savings:</span>
                      <span className="font-bold">{formatINR(Number(payload[0]?.value) || 0)}</span>
                    </div>
                    {purchasePrice > 0 && (
                      <div className="flex items-center justify-between gap-4 text-violet-400">
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
              stroke={baselineColor}
              isAnimationActive={true}
              animationDuration={900}
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#colorBaseline)"
            />

            {purchasePrice > 0 && (
              <Area
                type="monotone"
                dataKey="purchase_savings"
                name="Purchase Scenario"
                stroke={purchaseColor}
                isAnimationActive={true}
                animationDuration={900}
                strokeWidth={2.5}
                strokeDasharray="5 5"
                fillOpacity={1}
                fill="url(#colorPurchase)"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
        )}
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
