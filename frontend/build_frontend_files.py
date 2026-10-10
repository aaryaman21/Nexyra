# -*- coding: utf-8 -*-
import os

files = {}

files["types/financial.ts"] = """export type Recommendation = 'BUY' | 'WAIT';

export type ResilienceLevel = 'Comfortable' | 'Manageable' | 'Tight' | 'Risky';

export interface Obligation {
  name: string;
  amount: number;
  due_date?: string;
  recurrence?: 'one_time' | 'monthly';
}

export interface FinancialGoal {
  id?: string;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  monthly_allocation?: number;
}

export interface UserFinancialState {
  monthly_income: number;
  additional_income: number;
  current_savings: number;
  recurring_expenses: number;
  discretionary_expenses: number;
  upcoming_obligations: Obligation[];
  goals: FinancialGoal[];
}

export interface PurchaseDecision {
  name: string;
  price: number;
  planned_date?: string;
}

export interface PeriodProjection {
  month_index: number;
  period_label: string;
  income: number;
  expenses: number;
  obligations: number;
  surplus: number;
  baseline_savings: number;
  purchase_savings: number;
  baseline_liquidity: number;
  purchase_liquidity: number;
  goal_progress: Record<string, number>;
  purchase_goal_progress: Record<string, number>;
}

export interface GoalProjectionResult {
  goal_id: string;
  goal_name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  baseline_projected_completion_date: string | null;
  purchase_projected_completion_date: string | null;
  delay_in_weeks: number;
  baseline_achievable_by_deadline: boolean;
  purchase_achievable_by_deadline: boolean;
  progress_percentage: number;
  purchase_progress_percentage: number;
}

export interface BufferAssessment {
  baseline_emergency_runway_months: number;
  purchase_emergency_runway_months: number;
  buffer_reduction_amount: number;
  buffer_reduction_percentage: number;
  baseline_resilience: ResilienceLevel;
  purchase_resilience: ResilienceLevel;
  safe_minimum_buffer: number;
}

export interface ConsequenceHorizon {
  recovery_time_weeks: number;
  consequence_horizon_weeks: number;
  summary_wording: string;
}

export interface DecisionFactor {
  code: string;
  title: string;
  severity: 'positive' | 'warning' | 'danger' | 'neutral';
  detail: string;
  numerical_impact?: string;
}

export interface DecisionResult {
  recommendation: Recommendation;
  headline: string;
  bottom_line: string;
  purchase_name: string;
  purchase_price: number;
  monthly_surplus: number;
  baseline_liquidity: number;
  post_purchase_liquidity: number;
  buffer_impact: BufferAssessment;
  goal_impacts: GoalProjectionResult[];
  consequence: ConsequenceHorizon;
  supporting_factors: DecisionFactor[];
  timeline_projection: PeriodProjection[];
  assumptions: string[];
}

export interface ExplanationSection {
  number: string;
  title: string;
  detail: string;
}

export interface ExplanationResponse {
  recommendation: Recommendation;
  title: string;
  summary: string;
  sections: ExplanationSection[];
  bottom_line: string;
}
"""

files["lib/utils.ts"] = """import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatINR(amount: number): string {
  if (isNaN(amount)) return "?0";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}
"""

files["context/ThemeContext.tsx"] = """"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("nexyra_theme") as Theme | null;
    if (stored) {
      setThemeState(stored);
    }
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const computeResolved = (t: Theme): "light" | "dark" => {
      if (t === "system") {
        return mediaQuery.matches ? "dark" : "light";
      }
      return t;
    };

    const currentResolved = computeResolved(theme);
    setResolvedTheme(currentResolved);

    const root = document.documentElement;
    if (currentResolved === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

    localStorage.setItem("nexyra_theme", theme);

    const handleChange = () => {
      if (theme === "system") {
        const res = mediaQuery.matches ? "dark" : "light";
        setResolvedTheme(res);
        if (res === "dark") {
          root.classList.add("dark");
        } else {
          root.classList.remove("dark");
        }
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme, mounted]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  const toggleTheme = () => {
    setThemeState((prev) => {
      if (prev === "dark") return "light";
      if (prev === "light") return "system";
      return "dark";
    });
  };

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
"""

files["components/ThemeToggle.tsx"] = """"use client";

import React from "react";
import { useTheme } from "@/context/ThemeContext";
import { Sun, Moon, Monitor } from "lucide-react";
import { motion } from "framer-motion";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-200/60 dark:bg-slate-800/80 border border-slate-300/50 dark:border-slate-700/60 text-xs font-medium backdrop-blur-md">
      <button
        onClick={() => setTheme("light")}
        className={
          "relative px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 " +
          (theme === "light"
            ? "text-slate-900 font-semibold"
            : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white")
        }
        title="Light mode"
      >
        {theme === "light" && (
          <motion.div
            layoutId="activeTheme"
            className="absolute inset-0 bg-white rounded-lg shadow-sm border border-slate-200/80"
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
        <Sun className="w-3.5 h-3.5 relative z-10 text-amber-500" />
        <span className="relative z-10 hidden sm:inline">Light</span>
      </button>

      <button
        onClick={() => setTheme("dark")}
        className={
          "relative px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 " +
          (theme === "dark"
            ? "text-white font-semibold"
            : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white")
        }
        title="Dark mode"
      >
        {theme === "dark" && (
          <motion.div
            layoutId="activeTheme"
            className="absolute inset-0 bg-slate-900 rounded-lg shadow-sm border border-slate-700"
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
        <Moon className="w-3.5 h-3.5 relative z-10 text-cyan-400" />
        <span className="relative z-10 hidden sm:inline">Dark</span>
      </button>

      <button
        onClick={() => setTheme("system")}
        className={
          "relative px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 " +
          (theme === "system"
            ? "text-slate-900 dark:text-white font-semibold"
            : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white")
        }
        title="System preference"
      >
        {theme === "system" && (
          <motion.div
            layoutId="activeTheme"
            className="absolute inset-0 bg-white dark:bg-slate-700/80 rounded-lg shadow-sm border border-slate-200 dark:border-slate-600"
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
        <Monitor className="w-3.5 h-3.5 relative z-10 text-slate-500 dark:text-slate-300" />
        <span className="relative z-10 hidden sm:inline">System</span>
      </button>
    </div>
  );
}
"""

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {path} ({len(content)} chars)")
