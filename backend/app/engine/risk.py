from backend.app.schemas.financial import UserFinancialState, BufferAssessment, ResilienceLevel
from backend.app.engine.financial_state import calculate_total_monthly_expenses

def calculate_emergency_runway_months(liquidity: float, monthly_expenses: float) -> float:
    """
    Months of basic expenses covered by liquid funds.
    """
    if monthly_expenses <= 0:
        return 99.0 if liquidity > 0 else 0.0
    return round(liquidity / monthly_expenses, 2)

def evaluate_resilience_level(runway_months: float) -> ResilienceLevel:
    """
    Qualitative buffer resilience levels:
    - >= 6.0 months: Comfortable
    - >= 3.0 months: Manageable
    - >= 1.0 months: Tight
    - < 1.0 months: Risky
    """
    if runway_months >= 6.0:
        return ResilienceLevel.COMFORTABLE
    elif runway_months >= 3.0:
        return ResilienceLevel.MANAGEABLE
    elif runway_months >= 1.0:
        return ResilienceLevel.TIGHT
    else:
        return ResilienceLevel.RISKY

def assess_buffer_impact(state: UserFinancialState, purchase_price: float) -> BufferAssessment:
    monthly_expenses = calculate_total_monthly_expenses(state)
    baseline_liquidity = float(state.current_savings)
    post_purchase_liquidity = float(baseline_liquidity - purchase_price)

    baseline_runway = calculate_emergency_runway_months(baseline_liquidity, monthly_expenses)
    purchase_runway = calculate_emergency_runway_months(post_purchase_liquidity, monthly_expenses)

    baseline_resilience = evaluate_resilience_level(baseline_runway)
    purchase_resilience = evaluate_resilience_level(purchase_runway)

    reduction_amount = min(baseline_liquidity, purchase_price)
    reduction_pct = round((reduction_amount / baseline_liquidity * 100.0), 1) if baseline_liquidity > 0 else 100.0

    # Recommended safe minimum buffer: 3 months of essential recurring expenses
    safe_buffer = round(state.recurring_expenses * 3.0, 2)

    return BufferAssessment(
        baseline_emergency_runway_months=baseline_runway,
        purchase_emergency_runway_months=purchase_runway,
        buffer_reduction_amount=reduction_amount,
        buffer_reduction_percentage=reduction_pct,
        baseline_resilience=baseline_resilience,
        purchase_resilience=purchase_resilience,
        safe_minimum_buffer=safe_buffer
    )

