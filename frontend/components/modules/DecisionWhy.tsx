"use client";

import React, { useEffect, useState } from "react";
import { FileText } from "lucide-react";

export function DecisionWhy() {
  const [explanation, setExplanation] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchExplanation() {
      try {
        const res = await fetch("/api/agri/models");
        if (!res.ok) throw new Error("Agricultural model status unavailable");
        const data = await res.json();
        if (isMounted) setExplanation(data.models?.length
          ? "Agricultural model evaluations are available for selected markets."
          : "No agricultural forecast is available until verified market prices have been imported and evaluated.");
      } catch {
        if (isMounted) setExplanation("Agricultural forecasts are unavailable until the source data is configured, imported, and evaluated.");
      }
    }

    fetchExplanation();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="glass-panel hover-lift p-6 sm:p-8 relative overflow-hidden transition-all duration-300">
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-slate-200/80 dark:border-slate-800/80 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 pulse-dot" />
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
          <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-900 dark:text-cyan-200 text-xs sm:text-sm font-medium leading-relaxed">
            {explanation}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-400">
            Synthesizing plain-language rationale...
          </div>
        )}
      </div>
    </div>
  );
}
