"use client";
import { motion, MotionConfig } from "framer-motion";
import { Compass } from "lucide-react";
import { LaunchIntro } from "@/components/LaunchIntro";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AmbientBackground } from "@/components/DaylightAtmosphere";
import { LotusArt } from "@/components/BotanicalArt";
import { FooterGarden } from "@/components/FooterGarden";
import { AgriDashboard } from "@/components/modules/AgriDashboard";
import { ReviewTransitionButton } from "@/components/ReviewTransitionButton";

export default function Home() {
  return <LaunchIntro><MotionConfig reducedMotion="user"><div className="min-h-screen relative overflow-x-clip">
    <AmbientBackground />
      <motion.header
        className="observatory-header z-20 border-b border-slate-200/80 dark:border-slate-800/80
          backdrop-blur-xl bg-white/75 dark:bg-[#05070d]/75 sticky top-0"
        initial={{ opacity: 0, y: -24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <motion.div
              className="brand-mark w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-indigo-600
                flex items-center justify-center shadow-[0_0_18px_rgba(6,182,212,0.55)]"
              whileHover={{ rotate: 15, scale: 1.1 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
            >
              <Compass className="w-5 h-5 text-white" />
            </motion.div>
            <div>
              <span className="font-black tracking-widest text-lg text-slate-900 dark:text-white uppercase font-mono">
                NEXYRA
              </span>
              <span className="hidden md:inline ml-2 px-2 py-0.5 rounded-full text-[10px] font-mono
                bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20">
                OBSERVATORY
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <ReviewTransitionButton />
            <ThemeToggle />
          </div>
        </div>
      </motion.header>
    <main tabIndex={-1} className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <motion.section className="hero-panel glass-panel-elevated p-6 sm:p-10 relative overflow-hidden" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .65, ease: [.22, 1, .36, 1] }}>
        <div className="absolute -top-16 -left-16 w-64 h-64 rounded-full bg-gradient-to-br from-cyan-500/10 to-violet-500/5 blur-3xl pointer-events-none" />
          <div className="orbital-art" aria-hidden="true"><LotusArt /><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><div className="orbit-core">✦</div><span className="orbit-caption">A little clarity. A bigger horizon.</span></div>

        <div className="relative z-10">
          <motion.span className="text-xs font-mono text-cyan-600 dark:text-cyan-400 uppercase tracking-widest block mb-1" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .2 }}>NEXYRA AGRISENSE</motion.span>
          <motion.h1 className="hero-title text-4xl sm:text-5xl lg:text-6xl font-medium text-slate-900 dark:text-white tracking-tight" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: .3 }}>Your market,<br /><span>in perspective.</span></motion.h1>
          <p className="hero-description">Agricultural market intelligence.<br className="hidden sm:block" /> Evidence, forecasts and the uncertainty between.</p>
        </div>
      </motion.section>
      <AgriDashboard />
      <footer className="pt-8 pb-12 border-t border-slate-200 dark:border-slate-800/80 text-center space-y-2 font-mono">
        <p className="text-xs text-slate-500">NEXYRA AGRISENSE · AGRICULTURAL MARKET INTELLIGENCE</p>
        <p className="text-[11px] text-slate-400">Observed history · Evaluated forecasts · No guaranteed outcomes</p>
        <a href="/legacy" className="text-xs underline text-slate-500">Legacy financial workspace</a>
        <FooterGarden />
      </footer>
    </main>
  </div></MotionConfig></LaunchIntro>;
}
