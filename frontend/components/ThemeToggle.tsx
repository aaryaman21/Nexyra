"use client";

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
