from typing import List, Dict, Tuple
from datetime import datetime, date, timedelta
from backend.app.schemas.financial import UserFinancialState, FinancialGoal, GoalProjectionResult
from backend.app.engine.financial_state import calculate_monthly_surplus

def parse_deadline(deadline_str: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(deadline_str, fmt).date()
        except ValueError:
            pass
    # Fallback to 1 year from now
    return date.today() + timedelta(days=365)

def project_goals_progress(
    state: UserFinancialState,
    monthly_surplus: float,
    purchase_price: float = 0.0,
    horizon_months: int = 12
) -> List[GoalProjectionResult]:
    """
    Deterministic goal progression analysis comparing baseline vs purchase scenario.
    Surplus is allocated either according to goal.monthly_allocation or split proportionally.
    """
    results: List[GoalProjectionResult] = []
    today = date.today()

    if not state.goals:
        return results

    total_target_gap = sum(max(0.0, g.target_amount - g.current_amount) for g in state.goals)
    
    for g in state.goals:
        goal_id = g.id or g.name.lower().replace(" ", "_")
        gap = max(0.0, g.target_amount - g.current_amount)
        deadline = parse_deadline(g.deadline)
        months_to_deadline = max(1.0, (deadline - today).days / 30.4375)

        # Baseline allocation per month
        if g.monthly_allocation and g.monthly_allocation > 0:
            alloc_baseline = min(monthly_surplus, g.monthly_allocation)
        elif total_target_gap > 0 and monthly_surplus > 0:
            alloc_baseline = monthly_surplus * (gap / total_target_gap)
        else:
            alloc_baseline = monthly_surplus / len(state.goals) if monthly_surplus > 0 else 0.0

        # Months required to complete under baseline
        if gap <= 0:
            baseline_months_needed = 0.0
            baseline_date_str = today.strftime("%Y-%m-%d")
            baseline_achievable = True
        elif alloc_baseline > 0:
            baseline_months_needed = gap / alloc_baseline
            est_days = int(baseline_months_needed * 30.4375)
            baseline_date = today + timedelta(days=est_days)
            baseline_date_str = baseline_date.strftime("%Y-%m-%d")
            baseline_achievable = baseline_months_needed <= months_to_deadline
        else:
            baseline_months_needed = 999.0
            baseline_date_str = None
            baseline_achievable = False

        # Purchase impact scenario:
        # If purchase is made, does it take away from current liquid savings, or if savings drops,
        # does it delay goal progress?
        # In NEXYRA Phase 1: Purchase price directly deducts from liquid capital or shifts recovery.
        # If savings < purchase_price + safe buffer, surplus must first replenish emergency buffer,
        # thereby delaying monthly goal allocation!
        safe_buffer = state.recurring_expenses * 3.0
        post_savings = state.current_savings - purchase_price
        buffer_deficit = max(0.0, safe_buffer - post_savings)
        
        # Weeks/months surplus is redirected or capital deficit shifts timeline
        if monthly_surplus > 0 and purchase_price > 0:
            # Capital deduction delays goal completion by (purchase_price / monthly_surplus) months
            # or buffer recovery delay
            delay_months = (purchase_price / monthly_surplus) if alloc_baseline > 0 else (purchase_price / max(1.0, monthly_surplus))
        else:
            delay_months = 0.0

        purchase_months_needed = baseline_months_needed + delay_months
        delay_in_weeks = int(round(delay_months * 4.33))

        if gap <= 0:
            purchase_date_str = today.strftime("%Y-%m-%d")
            purchase_achievable = True
        elif alloc_baseline > 0 and purchase_months_needed < 900:
            purchase_days = int(purchase_months_needed * 30.4375)
            purchase_date = today + timedelta(days=purchase_days)
            purchase_date_str = purchase_date.strftime("%Y-%m-%d")
            purchase_achievable = purchase_months_needed <= months_to_deadline
        else:
            purchase_date_str = None
            purchase_achievable = False

        progress_pct = round(min(100.0, (g.current_amount / g.target_amount * 100.0)), 1) if g.target_amount > 0 else 100.0
        purchase_prog_pct = progress_pct

        results.append(GoalProjectionResult(
            goal_id=goal_id,
            goal_name=g.name,
            target_amount=g.target_amount,
            current_amount=g.current_amount,
            deadline=g.deadline,
            baseline_projected_completion_date=baseline_date_str,
            purchase_projected_completion_date=purchase_date_str,
            delay_in_weeks=max(0, delay_in_weeks),
            baseline_achievable_by_deadline=baseline_achievable,
            purchase_achievable_by_deadline=purchase_achievable,
            progress_percentage=progress_pct,
            purchase_progress_percentage=purchase_prog_pct
        ))

    return results

