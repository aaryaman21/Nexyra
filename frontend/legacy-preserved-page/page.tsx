"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  UserFinancialState,
  PurchaseDecision,
  DecisionResult,
  FinancialGoal,
} from "@/types/financial";
import { formatINR } from "@/lib/utils";
import { useCountUp } from "@/lib/useCountUp";
import { LotusArt } from "@/components/BotanicalArt";
import { FooterGarden } from "@/components/FooterGarden";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AmbientBackground } from "@/components/DaylightAtmosphere";
import { LaunchIntro } from "@/components/LaunchIntro";
import { FinancialSetup } from "@/components/FinancialSetup";
import { ContextualLoader, LoaderModule } from "@/components/loaders/ContextualLoaders";

import { MoneyMap } from "@/components/modules/MoneyMap";
import { FutureFlow } from "@/components/modules/FutureFlow";
import { GoalPath } from "@/components/modules/GoalPath";
import { DecisionLab } from "@/components/modules/DecisionLab";
import { SafetyNet } from "@/components/modules/SafetyNet";
import { ImpactMap } from "@/components/modules/ImpactMap";
import { BestMove } from "@/components/modules/BestMove";
import { DecisionWhy } from "@/components/modules/DecisionWhy";

import { motion, AnimatePresence, MotionConfig } from "framer-motion";
import { Compass, Cpu } from "lucide-react";

/* ─────────────────────────────────────────────────────────────
   DEMO DATA
───────────────────────────────────────────────────────────── */
const EMPTY_STATE: UserFinancialState = {
  monthly_income: 0,
  additional_income: 0,
  current_savings: 0,
  recurring_expenses: 0,
  discretionary_expenses: 0,
  upcoming_obligations: [],
  goals: [],
};
const EMPTY_PURCHASE: PurchaseDecision = { name: "", price: 0 };

/* ─────────────────────────────────────────────────────────────
   ANIMATED COUNTER STAT CARD
───────────────────────────────────────────────────────────── */
function StatCard({
  label,
  value,
  formatted,
  color = "text-slate-900 dark:text-white",
  delay = 0,
}: {
  label: string;
  value: number;
  formatted?: string;
  color?: string;
  delay?: number;
}) {
  const counted = useCountUp(value);
  const display = formatted ?? formatINR(counted);

  return (
    <motion.div
      className="stat-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <span className="text-xs text-slate-500 dark:text-slate-400 block mb-1">{label}</span>
      <span className={`text-xl sm:text-2xl font-black font-mono ${color}`}>
        {display}
      </span>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────
   SCROLL-REVEAL WRAPPER
───────────────────────────────────────────────────────────── */
function RevealSection({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      className="reveal-panel"
      initial={{ opacity: 0, y: 24, scale: 0.975 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: false, amount: "some", margin: "0px 0px -24px 0px" }}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────
   LOCAL FALLBACK ENGINE
───────────────────────────────────────────────────────────── */
/* ─────────────────────────────────────────────────────────────
   MAIN PAGE
───────────────────────────────────────────────────────────── */
export default function Home() {
  return <LaunchIntro><Dashboard /></LaunchIntro>;
}

function Dashboard() {
  const [financialState, setFinancialState] = useState<UserFinancialState>(EMPTY_STATE);
  const [purchase, setPurchase] = useState<PurchaseDecision>(EMPTY_PURCHASE);
  const [hasFinancialData, setHasFinancialData] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [decision, setDecision] = useState<DecisionResult | null>(null);
  const [evaluatedInput, setEvaluatedInput] = useState<(UserFinancialState & { purchase: PurchaseDecision }) | null>(null);
  const simulationSequence = useRef(0);
  const [loadingModule, setLoadingModule] = useState<LoaderModule | null>(null);
  const [showToast, setShowToast] = useState<string | null>(null);
  const toastRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback((msg: string) => {
    setShowToast(msg);
    if (toastRef.current) clearTimeout(toastRef.current);
    toastRef.current = setTimeout(() => setShowToast(null), 3000);
  }, []);

  const runSimulation = useCallback(
    async (state: UserFinancialState, targetPurchase: PurchaseDecision) => {
      const sequence = ++simulationSequence.current;
      const input = structuredClone({ ...state, purchase: targetPurchase });
      setLoadingModule("decisionlab");
      setSimulationError(null);
      setDecision(null);
      try {
        const response = await fetch("/api/agri/models");
        if (!response.ok) throw new Error("Agricultural model status unavailable");
        if (sequence !== simulationSequence.current) return;
        setEvaluatedInput(input);
        setSimulationError("Financial simulations have been retired. Agricultural forecasts are unavailable until verified market prices are imported and evaluated.");
      } catch {
        if (sequence !== simulationSequence.current) return;
        setDecision(null);
        setSimulationError("Financial simulations have been retired. Agricultural forecasts are unavailable until verified market prices are imported and evaluated.");
      } finally {
        if (sequence === simulationSequence.current) setLoadingModule(null);
      }
    },
    []
  );

  const handleFinancialStateChange = (updated: UserFinancialState) => {
    setFinancialState(updated);
    if (purchase.name && purchase.price > 0) runSimulation(updated, purchase);
  };

  const handleSimulatePurchase = (newPurchase: PurchaseDecision) => {
    setPurchase(newPurchase);
    runSimulation(financialState, newPurchase);
  };

  const handleAddGoal = (newGoal: FinancialGoal) => {
    const updated = {
      ...financialState,
      goals: [...financialState.goals, newGoal],
    };
    handleFinancialStateChange(updated);
    toast("Goal added and simulation updated.");
  };

  const handleRemoveGoal = (goalId: string) => {
    const updated = {
      ...financialState,
      goals: financialState.goals.filter((g) => g.id !== goalId),
    };
    handleFinancialStateChange(updated);
  };

  const totalIncome = financialState.monthly_income + financialState.additional_income;
  const totalExpenses = financialState.recurring_expenses + financialState.discretionary_expenses;
  const surplus = totalIncome - totalExpenses;

  return (
    <MotionConfig reducedMotion={process.env.NODE_ENV === "production" ? "user" : "never"}><div className="min-h-screen relative overflow-x-clip">
      {/* ── 3D Neural Network Background ── */}
      <AmbientBackground />

      {/* ── Toast notification ── */}
      <AnimatePresence>
        {showToast && (
          <motion.div
            initial={{ opacity: 0, y: -60, x: "-50%" }}
            animate={{ opacity: 1, y: 0, x: "-50%" }}
            exit={{ opacity: 0, y: -60, x: "-50%" }}
            transition={{ type: "spring", stiffness: 400, damping: 28 }}
            className="fixed top-20 left-1/2 z-50 px-5 py-2.5 rounded-xl
              glass-panel-elevated border-cyan-500/30 text-sm font-medium
              text-slate-900 dark:text-white shadow-xl"
          >
            <span className="text-cyan-500 mr-2">✦</span>
            {showToast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── HEADER ── */}
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
            <ThemeToggle />
          </div>
        </div>
      </motion.header>

      {/* ── MAIN CONTENT ── */}
      <main tabIndex={-1} className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">


        {/* ── HERO HERO SECTION ── */}
        <motion.section
          className="hero-panel glass-panel-elevated p-6 sm:p-10 relative overflow-hidden"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Decorative glow orb */}
          <div className="absolute -top-16 -left-16 w-64 h-64 rounded-full
            bg-gradient-to-br from-cyan-500/10 to-violet-500/5 blur-3xl pointer-events-none" />

          <div className="orbital-art" aria-hidden="true"><LotusArt /><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" /><div className="orbit-core">✦</div><span className="orbit-caption">A little clarity. A bigger horizon.</span></div>
          <div className="relative z-10">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <motion.span
                  className="text-xs font-mono text-cyan-600 dark:text-cyan-400 uppercase tracking-widest block mb-1"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  YOUR PERSONAL FINANCIAL OBSERVATORY
                </motion.span>
                <motion.h1
                  className="hero-title text-4xl sm:text-5xl lg:text-6xl font-medium text-slate-900 dark:text-white tracking-tight"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  Your next move,<br /><span>in perspective.</span>
                </motion.h1>
                <p className="hero-description">Explore the possibilities. See the impact.<br className="hidden sm:block" /> Make room for what matters next.</p>
              </div>

              {/* Engine status badge */}
              <motion.div
                className="flex items-center gap-2 px-3 py-2 rounded-xl
                  bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 }}
              >
                <Cpu className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-mono text-slate-500">Engine</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-mono text-emerald-500">READY</span>
              </motion.div>
            </div>

            {/* Current evaluation chip */}
            <AnimatePresence>
              {decision && (
                <motion.div
                  key={decision.purchase_name}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-xl
                    bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
                >
                  <span className="text-xs font-mono text-slate-500">Evaluating:</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white font-mono">
                    {decision.purchase_name} ({formatINR(decision.purchase_price)})
                  </span>
                  <motion.span
                    key={decision.recommendation}
                    initial={{ scale: 0.7 }}
                    animate={{ scale: 1 }}
                    className={`ml-1 px-2.5 py-0.5 rounded-md text-[11px] font-black ${
                      decision.recommendation === "WAIT"
                        ? "bg-amber-500/15 text-amber-500 border border-amber-500/35"
                        : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/35"
                    }`}
                  >
                    {decision.recommendation}
                  </motion.span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Stats row */}
            {hasFinancialData && <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-5 pt-5
              border-t border-slate-200/70 dark:border-slate-800/70">
              <StatCard
                label="Liquid Funds"
                value={financialState.current_savings}
                delay={0.1}
              />
              <StatCard
                label="Monthly Surplus"
                value={surplus}
                color={surplus >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-500"}
                delay={0.2}
              />
              <StatCard
                label="Active Goals"
                value={financialState.goals.length}
                formatted={`${financialState.goals.length} goal${financialState.goals.length !== 1 ? "s" : ""}`}
                color="text-violet-600 dark:text-violet-400"
                delay={0.3}
              />
            </div>}
          </div>
        </motion.section>

        {/* ── MODULE SECTIONS ── */}
        {!hasFinancialData ? <FinancialSetup onSave={state => { setFinancialState(state); setHasFinancialData(true); }} /> : <div className="space-y-8">
          <div className="section-heading"><span>01 / THE STARTING POINT</span><span>Your world, in numbers</span></div>
          <div className="workspace-grid">
          <RevealSection>
            <MoneyMap state={financialState} onChange={handleFinancialStateChange} />
          </RevealSection>

          <RevealSection delay={0.05}>
            <DecisionLab
              currentPurchase={purchase}
              onSimulate={handleSimulatePurchase}
              isLoading={loadingModule === "decisionlab"}
            />
          </RevealSection>

          </div>
          <div className="section-heading"><span>02 / THE POSSIBILITIES</span><span>A clearer path forward</span></div>
          {/* Results area */}
          <AnimatePresence mode="wait">
            {loadingModule ? (
              <motion.div
                key="loader"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <ContextualLoader module={loadingModule} />
              </motion.div>
            ) : decision ? (
              <motion.div
                key="results"
                className="space-y-8"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4 }}
              >
                <RevealSection>
                  <BestMove decision={decision} evaluatedInput={evaluatedInput} />
                </RevealSection>

                <RevealSection delay={0.05}>
                  <DecisionWhy />
                </RevealSection>

                <RevealSection delay={0.05}>
                  <FutureFlow
                    projections={decision.timeline_projection}
                    purchasePrice={decision.purchase_price}
                  />
                </RevealSection>

                <div className="insights-grid">
                <RevealSection delay={0.05}>
                  <SafetyNet
                    bufferImpact={decision.buffer_impact}
                    postLiquidity={decision.post_purchase_liquidity}
                  />
                </RevealSection>

                <RevealSection delay={0.05}>
                  <ImpactMap decision={decision} />
                </RevealSection>
                </div>

                <RevealSection delay={0.05}>
                  <GoalPath
                    goals={financialState.goals}
                    goalImpacts={decision.goal_impacts}
                    onAddGoal={handleAddGoal}
                    onRemoveGoal={handleRemoveGoal}
                  />
                </RevealSection>
              </motion.div>
            ) : simulationError ? (
              <div role="alert" className="glass-panel p-6 text-sm text-rose-600 dark:text-rose-400">{simulationError}</div>
            ) : (
              <div className="glass-panel p-6 text-sm text-slate-600 dark:text-slate-300">Enter a purchase and run the simulation to see your recommendation and charts.</div>
            )}
          </AnimatePresence>
        </div>}

        {/* ── FOOTER ── */}
        <footer className="pt-8 pb-12 border-t border-slate-200 dark:border-slate-800/80
          text-center space-y-2 font-mono">
          <p className="text-xs text-slate-500">
            NEXYRA PHASE 1 — PERSONAL FINANCIAL DECISION ASSISTANT ONLY
          </p>
          <p className="text-[11px] text-slate-400">
            Deterministic calculations · No live banking APIs · No stock market forecasting · No automatic transactions.
          </p>
          <div className="flex items-center justify-center gap-1.5 mt-3">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-[11px] text-cyan-500/70 font-mono">Engine v1.0</span>
          </div>
          <FooterGarden />
        </footer>
      </main>
    </div></MotionConfig>
  );
}
