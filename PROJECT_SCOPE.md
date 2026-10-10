# PROJECT SCOPE SPECIFICATION — NEXYRA

**CURRENT BUILD TARGET: PHASE 1 — PERSONAL FINANCIAL DECISION ASSISTANT ONLY**

---

## 1. PURPOSE
NEXYRA Phase 1 helps a user determine whether a planned purchase is financially sensible based on their current and near-future financial circumstances.

It answers the core question:
> **"Should I make this purchase now, or would waiting be financially better?"**

---

## 2. CORE WORKFLOW
`
USER INPUT
? DATA VALIDATION
? FINANCIAL STATE
? CASH-FLOW PROJECTION
? GOAL PROJECTION
? PURCHASE SIMULATION
? RISK / BUFFER ASSESSMENT
? DECISION EVALUATION
? RECOMMENDATION (BUY / WAIT)
? EXPLANATION
`

---

## 3. STRICT PHASE 1 SCOPE BOUNDARIES

### IMPLEMENTED:
- Manual financial inputs (monthly income, additional regular income, savings/liquid funds, recurring fixed expenses, discretionary expenses, upcoming obligations, financial goals & deadlines).
- Planned purchase evaluation (purchase name, purchase price, planned purchase timing).
- Deterministic cash-flow projection across 1M, 3M, 6M, and 12M horizons.
- Baseline scenario vs Purchase scenario comparative simulation.
- Quantitative buffer & emergency runway assessment (months of essential expenses covered).
- Qualitative resilience rating (Comfortable, Manageable, Tight, Risky).
- Recovery-time calculation in weeks.
- Financial Consequence Horizon calculation (duration the purchase materially alters savings trajectory).
- Deterministic Decision evaluation outputting BUY or WAIT with supporting factors.
- Explainable reasoning and natural-language narrative strictly bounded by engine metrics.
- The 8 interconnected UI modules: **MoneyMap**, **FutureFlow**, **GoalPath**, **Decision Lab**, **Safety Net**, **Impact Map**, **Best Move**, and **Decision Why**.
- Custom contextual loaders for each module phase.
- Persistent Light / Dark / System theme system.
- One-click interactive Demo Mode with the quintessential ?70,000 laptop test scenario.

### STRICTLY NOT IMPLEMENTED (FUTURE PHASES):
- NO live banking integrations or account aggregation (Plaid, Yodlee, etc.).
- NO automatic transaction synchronization or receipt OCR.
- NO stock-market prediction or ticker analysis.
- NO investment forecasting or algorithmic portfolio management.
- NO autonomous investing or automated fund transfers.
- NO advanced behavioural AI or spending-habit profiling.
- NO external product-price tracking or scrapers.
- NO live product availability or ecommerce inventory checking.
- NO product lifecycle forecasting.
- NO market macroeconomic forecasting.
- NO Digital Twin simulations.
- NO advanced counterfactual multi-future or Monte Carlo stochastic uncertainty engines.
- NO specialized external decision categories (travel booking, car loan calculators, real-estate mortgages, student loan consolidation).

---

## 4. ARCHITECTURAL COMPLIANCE
- The deterministic Python financial engine (ackend/app/engine/) is the sole authoritative calculator.
- The frontend does not contain authoritative financial business logic.
- The LLM never invents numbers, prices, or predictions.
