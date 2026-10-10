"use client";

import { useState } from "react";
import { ClipboardCheck, ArrowUpRight } from "lucide-react";

export function ReviewTransitionButton() {
  const [transitioning, setTransitioning] = useState(false);

  function openReview() {
    if (transitioning) return;
    setTransitioning(true);
    window.dispatchEvent(new Event("nexyra:review-shatter"));
  }

  return <button type="button" onClick={openReview} disabled={transitioning} className="group inline-flex items-center gap-2 rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-800 shadow-sm transition hover:border-cyan-400 hover:bg-cyan-500/15 hover:shadow-[0_0_22px_rgba(34,211,238,.18)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-500 disabled:cursor-wait dark:text-cyan-200">
      <ClipboardCheck size={16} /> {transitioning ? "Opening review…" : "Article review"} <ArrowUpRight size={14} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
    </button>;
}
