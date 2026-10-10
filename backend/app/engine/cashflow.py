from typing import List, Dict
from datetime import date, timedelta
from backend.app.schemas.financial import UserFinancialState, PeriodProjection
from backend.app.engine.financial_state import (
    calculate_total_income,
    calculate_total_monthly_expenses,
    calculate_monthly_surplus,
    calculate_monthly_obligations
)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def project_cash_flow(
    state: UserFinancialState,
    purchase_price: float = 0.0,
    horizon_months: int = 12
) -> List[PeriodProjection]:
    """
    Generates month-by-month deterministic projections for:
    - Baseline scenario (no purchase)
    - Purchase scenario (purchase price deducted at month 0)
    """
    projections: List[PeriodProjection] = []
    base_income = calculate_total_income(state)
    base_expenses = calculate_total_monthly_expenses(state)

    baseline_savings = float(state.current_savings)
    purchase_savings = float(state.current_savings - purchase_price)

    today = date.today()

    for m in range(horizon_months):
        future_date = today + timedelta(days=int(m * 30.4375))
        period_label = f"{MONTH_NAMES[future_date.month - 1]} {future_date.year}"
        
        obligations = calculate_monthly_obligations(state, month_index=m)
        monthly_surplus = base_income - (base_expenses + obligations)

        baseline_savings += monthly_surplus
        purchase_savings += monthly_surplus

        projections.append(PeriodProjection(
            month_index=m,
            period_label=period_label,
            income=round(base_income, 2),
            expenses=round(base_expenses, 2),
            obligations=round(obligations, 2),
            surplus=round(monthly_surplus, 2),
            baseline_savings=round(baseline_savings, 2),
            purchase_savings=round(purchase_savings, 2),
            baseline_liquidity=round(baseline_savings, 2),
            purchase_liquidity=round(purchase_savings, 2),
            goal_progress={},
            purchase_goal_progress={}
        ))

    return projections

