from backend.app.schemas.financial import UserFinancialState, ConsequenceHorizon

def calculate_recovery_time_weeks(purchase_price: float, monthly_surplus: float) -> int:
    """
    Calculates the time in weeks needed to replenish the spent amount purely from monthly surplus.
    If monthly surplus <= 0, recovery time is theoretically infinite or undefined (capped at 520 weeks = 10 years).
    """
    if purchase_price <= 0:
        return 0
    if monthly_surplus <= 0:
        return 520 # > 10 years
    
    months_needed = purchase_price / monthly_surplus
    weeks = int(round(months_needed * 4.333))
    return max(1, weeks)

def calculate_consequence_horizon(
    state: UserFinancialState,
    purchase_price: float,
    monthly_surplus: float
) -> ConsequenceHorizon:
    """
    Financial Consequence Horizon:
    Estimates how long the purchase materially alters the projected trajectory
    relative to baseline. This includes the direct replenishment horizon plus
    buffer re-stabilization time.
    """
    recovery_weeks = calculate_recovery_time_weeks(purchase_price, monthly_surplus)

    # If purchase significantly reduces buffer below safe minimum (3 months expenses),
    # consequence horizon extends until safe buffer is restored.
    safe_buffer = state.recurring_expenses * 3.0
    post_liquidity = state.current_savings - purchase_price
    
    if post_liquidity < safe_buffer and monthly_surplus > 0:
        extra_months_for_buffer = (safe_buffer - post_liquidity) / monthly_surplus
        extra_weeks = int(round(extra_months_for_buffer * 4.333))
        consequence_weeks = max(recovery_weeks, recovery_weeks + extra_weeks)
    else:
        consequence_weeks = recovery_weeks

    # UI wording exactly as requested in specifications
    summary_wording = f"This purchase is projected to affect your savings trajectory for approximately {consequence_weeks} weeks."
    if monthly_surplus <= 0:
        summary_wording = "There is no positive monthly surplus to replenish the purchase. Recovery requires a change in income or expenses."

    return ConsequenceHorizon(
        recovery_time_weeks=recovery_weeks,
        consequence_horizon_weeks=consequence_weeks,
        summary_wording=summary_wording
    )

