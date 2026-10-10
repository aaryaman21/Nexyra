======================================================================
NEXYRA — PHASE 1 COMPLETE TECHNICAL & ARCHITECTURAL MANUAL
======================================================================

1. WHAT NEXYRA IS
----------------------------------------------------------------------
NEXYRA is a specialized personal financial decision assistant designed
to answer one essential question:
"Should I make this purchase now, or would waiting be financially better?"

It provides clarity on large, planned discretionary purchases by running
deterministic simulations of your personal finances and mapping their
ripple effects on your liquidity, emergency runway, active goals, and
capital recovery horizon.

2. WHAT PHASE 1 DOES
----------------------------------------------------------------------
- Captures manual financial profile: monthly income, regular additions,
  liquid savings, recurring fixed expenses, discretionary expenses,
  upcoming scheduled obligations, and target financial goals.
- Simulates a planned purchase: price, item name, and execution date.
- Generates month-by-month deterministic projections across 1M, 3M, 6M,
  and 12M horizons for:
  a) Baseline Scenario (no purchase executed).
  b) Purchase Scenario (purchase deducted at month 0).
- Calculates Emergency Runway in months of recurring obligations.
- Evaluates qualitative Resilience Status: Comfortable, Manageable,
  Tight, or Risky.
- Calculates Capital Recovery Time in weeks.
- Calculates Financial Consequence Horizon in weeks (time to re-stabilize).
- Outputs a deterministic recommendation: BUY or WAIT.
- Delivers explainable, transparent factors and a plain-language
  breakdown with zero hallucination.
- Organizes the entire journey through 8 connected modules:
  MoneyMap, FutureFlow, GoalPath, Decision Lab, Safety Net, Impact Map,
  Best Move, and Decision Why.
- Features custom contextual animated loaders and persistent theme support.

3. WHAT PHASE 1 DOES NOT DO
----------------------------------------------------------------------
To maintain hard scope integrity, Phase 1 strictly excludes:
- Live banking integrations (Plaid, Open Banking).
- Automated transaction synchronization or receipt parsing.
- Stock market or cryptocurrency price prediction.
- Investment yield forecasting or autonomous fund management.
- Behavioural spending profiling.
- E-commerce price scraping or item availability trackers.
- Digital Twin or stochastic multi-future branching simulations.
- Car loans, mortgages, or specialized multi-domain advisors.

4. TECHNOLOGY STACK
----------------------------------------------------------------------
- Frontend: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4,
  Framer Motion, Recharts, Lucide React.
- Backend: Python 3.14, FastAPI, Pydantic v2, NumPy, Pandas, Uvicorn.
- Persistence: SQLAlchemy, SQLite (development) / PostgreSQL / Supabase ready.
- Testing: Pytest, pytest-asyncio, FastAPI TestClient.

5. WHY EACH TECHNOLOGY IS USED
----------------------------------------------------------------------
- TypeScript & Pydantic: Guarantee strict typing across API contracts.
- Next.js & React: Deliver server-rendered performance and smooth client
  transitions with Framer Motion.
- Tailwind CSS: Enables rapid, customized styling and consistent design tokens.
- Recharts: High-performance, animated SVG charting for cash-flow curves.
- FastAPI & Python: Asynchronous REST framework paired with Python's proven
  numeric manipulation capabilities.
- Pytest: Authoritative automated unit and integration test verification.

6. ARCHITECTURE & DATA FLOW
----------------------------------------------------------------------
User Input / Demo Mode
        |
        v
Frontend (Next.js 16 + React 19 + Framer Motion)
  -> 8 Connected Modules (MoneyMap ... Decision Why)
        |  REST JSON (POST /api/decision/simulate)
        v
FastAPI Backend (/backend/app/api/routes.py)
        |
        v
Deterministic Financial Engine (/backend/app/engine/)
  +-- financial_state.py  (Inflow, Outflow, Surplus)
  +-- cashflow.py         (1M, 3M, 6M, 1Y projections)
  +-- goals.py            (Milestone delays, target dates)
  +-- risk.py             (Runway months, resilience level)
  +-- consequence.py      (Recovery weeks, consequence horizon)
  +-- decision.py         (Authoritative BUY / WAIT evaluation)
        |
        +---> Database (DecisionRecord in SQLite / Postgres)
        |
        v
Explanation Service (/backend/app/services/explanation.py)
  (Synthesizes plain-language summary strictly bounded by engine metrics)
        |
        v
Frontend Visualization & Decision Display

7. FOLDER STRUCTURE
----------------------------------------------------------------------
Nexyra/
+-- backend/
¦   +-- app/
¦   ¦   +-- api/routes.py            # API Endpoints
¦   ¦   +-- engine/                  # Deterministic Financial Engine
¦   ¦   ¦   +-- cashflow.py
¦   ¦   ¦   +-- consequence.py
¦   ¦   ¦   +-- decision.py
¦   ¦   ¦   +-- financial_state.py
¦   ¦   ¦   +-- goals.py
¦   ¦   ¦   +-- risk.py
¦   ¦   +-- models/database.py       # SQLAlchemy ORM Models
¦   ¦   +-- schemas/financial.py     # Pydantic Validation Models
¦   ¦   +-- services/explanation.py  # Transparent Narrative Generator
¦   ¦   +-- main.py                  # FastAPI Application Entry
¦   +-- requirements.txt
¦   +-- tests/
¦       +-- test_financial_engine.py # Comprehensive Pytest Suite
+-- frontend/
¦   +-- app/
¦   ¦   +-- globals.css              # Theme tokens & constellation styles
¦   ¦   +-- layout.tsx               # Root layout & ThemeProvider
¦   ¦   +-- page.tsx                 # Main application dashboard
¦   +-- components/
¦   ¦   +-- ConstellationBackground.tsx
¦   ¦   +-- ThemeToggle.tsx
¦   ¦   +-- loaders/
¦   ¦   ¦   +-- ContextualLoaders.tsx # 8 Custom contextual loaders
¦   ¦   +-- modules/
¦   ¦       +-- BestMove.tsx
¦   ¦       +-- DecisionLab.tsx
¦   ¦       +-- DecisionWhy.tsx
¦   ¦       +-- FutureFlow.tsx
¦   ¦       +-- GoalPath.tsx
¦   ¦       +-- ImpactMap.tsx
¦   ¦       +-- MoneyMap.tsx
¦   ¦       +-- SafetyNet.tsx
¦   +-- context/ThemeContext.tsx     # Light/Dark/System Theme Context
¦   +-- lib/utils.ts                 # Formatting & class merging
¦   +-- types/financial.ts           # TypeScript interfaces
+-- .env.example
+-- PROJECT_SCOPE.md
+-- README_PHASE1.txt

8. FINANCIAL CALCULATIONS & FORMULAS
----------------------------------------------------------------------
- Total Monthly Inflow:
  Monthly Income + Additional Regular Income

- Total Monthly Outflow:
  Recurring Fixed Expenses + Discretionary Expenses + Scheduled Obligations

- Net Monthly Surplus:
  Total Monthly Inflow - Total Monthly Outflow

- Post-Purchase Liquidity:
  Current Liquid Savings - Purchase Price

- Emergency Runway (Months):
  Post-Purchase Liquidity / Total Monthly Outflow

- Safe Minimum Buffer Benchmark:
  3.0 * Recurring Fixed Expenses

- Qualitative Resilience Levels:
  * Runway >= 6.0 months: "Comfortable"
  * Runway >= 3.0 months: "Manageable"
  * Runway >= 1.0 months: "Tight"
  * Runway < 1.0 months:  "Risky"

- Capital Recovery Time (Weeks):
  (Purchase Price / Net Monthly Surplus) * 4.333

- Financial Consequence Horizon (Weeks):
  Duration until spent capital is replenished, extended by time required
  to restore emergency buffer to benchmark if depleted below safe minimum.

9. DECISION LOGIC (BUY vs WAIT)
----------------------------------------------------------------------
The engine evaluates 4 primary objective factors:
1. Solvency: If Post-Purchase Liquidity < 0 -> WAIT (immediate blocker).
2. Safety Net: If post-purchase runway is "Risky" (<1 mo) or "Tight" (<3 mo)
   with large capital absorption (>60% of savings) -> WAIT.
3. Goal Conflict: If capital deduction causes any active goal to miss
   its scheduled deadline -> WAIT.
4. Cashflow: If monthly surplus <= 0 (unable to recover) or recovery time
   exceeds 6 months (>26 weeks) -> WAIT.
Otherwise, if runway is healthy and goals remain on schedule -> BUY.

10. AI / LLM ROLE
----------------------------------------------------------------------
The LLM is strictly used as an explanation synthesizer over the
deterministic engine output. It receives calculated numbers as input
and converts them into natural phrasing. If an LLM API key is not
configured, an authoritative deterministic explainer generates the
transparent 3-part rationale with zero disruption.

11. API ENDPOINTS
----------------------------------------------------------------------
- GET  /api/health                  Health check & engine status
- POST /api/financial-state/validate Validates input parameters & computes surplus
- POST /api/projection              Returns multi-horizon cashflow curves
- POST /api/goals/projection        Returns goal milestone impacts
- POST /api/decision/simulate       Executes full deterministic evaluation & persists
- POST /api/decision/explain        Generates natural-language reasoning

12. HOW TO RUN BACKEND & TESTS
----------------------------------------------------------------------
1. Navigate to repository root:
   cd C:\Nexyra

2. Activate virtual environment:
   .\venv\Scripts\Activate.ps1

3. Run unit test suite:
   $env:PYTHONPATH="."; pytest backend\tests -v
   (All 13 tests covering Comfortable, Liquidity Pressure, Goal Conflict,
    Zero Income, Zero Savings, and API endpoints pass)

4. Start FastAPI server:
   $env:PYTHONPATH="."; python -m uvicorn backend.app.main:app --reload --port 8000

13. HOW TO RUN FRONTEND
----------------------------------------------------------------------
1. In a new terminal, navigate to frontend/:
   cd C:\Nexyra\frontend

2. Start Next.js development server:
   npm run dev

3. Open your browser at http://localhost:3000

14. FIRST-USE WORKFLOW
----------------------------------------------------------------------
The application opens with an empty financial setup form. Enter your own
income, expenses, and savings, then enter a purchase in Decision Lab.
Recommendations and charts appear after the backend evaluates those inputs.
If the backend is unavailable, the UI shows an error instead of a generated
decision.

15. THE 8 CONNECTED MODULES EXPLAINED
----------------------------------------------------------------------
01 — MoneyMap: Current financial state nodes (Inflow, Outflow, Surplus,
     Savings, and scheduled obligations).
02 — FutureFlow: Interactive timeline chart (1M, 3M, 6M, 1Y) contrasting
     Baseline vs Purchase savings curves.
03 — GoalPath: Visual journey tracking how purchases push back target dates.
04 — Decision Lab: The central purchase simulator where users test purchases.
05 — Safety Net: Resilience cushion visualizer rating runway in months.
06 — Impact Map: Interactive ripple network showing consequences on click.
07 — Best Move: Definitive, dignified recommendation badge (BUY / WAIT).
08 — Decision Why: Transparent 3-part evidence breakdown explaining the move.

16. THEME SYSTEM
----------------------------------------------------------------------
Supports Light, Dark, and System modes with an animated sliding toggle,
smooth CSS transitions, and local storage persistence.

17. CONTEXTUAL LOADERS
----------------------------------------------------------------------
Features 8 bespoke loaders (no generic circular spinners) visually
representing the mathematical operation of each module.
======================================================================
