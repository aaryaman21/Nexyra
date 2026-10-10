"use client";

import { useId, useState } from "react";
import { ChevronDown, GitCompareArrows } from "lucide-react";

export function ModelComparison() {
  const id = useId();
  const [open, setOpen] = useState(false);
  return <div className="mb-6">
    <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
      className="mx-auto flex items-center gap-2 rounded-full border border-slate-300 dark:border-slate-600 px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-500">
      <GitCompareArrows size={14} /> {open ? "Hide model status" : "Agricultural model status"}
      <ChevronDown size={14} className={open ? "rotate-180" : ""} />
    </button>
    <section id={id} hidden={!open} aria-label="Agricultural model status" className="mt-4 rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-900/60 p-4 sm:p-5">
      <p className="text-sm font-semibold text-slate-900 dark:text-white">Agricultural forecasts are not available yet.</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">The legacy financial inference API has been retired. Agricultural forecasts will become available after real market prices are imported and evaluated; no forecast is generated from financial data.</p>
    </section>
  </div>;
}
