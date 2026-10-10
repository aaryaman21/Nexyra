from typing import List
from backend.app.schemas.financial import (
    UserFinancialState,
    PurchaseDecision,
    DecisionResult,
    RecommendationEnum,
    ResilienceLevel,
    DecisionFactor,
    BufferAssessment,
    GoalProjectionResult,
    ConsequenceHorizon
)
from backend.app.engine.financial_state import calculate_monthly_surplus, calculate_total_monthly_expenses
from backend.app.engine.risk import assess_buffer_impact
from backend.app.engine.goals import project_goals_progress
from backend.app.engine.consequence import calculate_consequence_horizon
from backend.app.engine.cashflow import project_cash_flow

def evaluate_decision(
    state: UserFinancialState,
    purchase: PurchaseDecision
) -> DecisionResult:
    """
    Authoritative deterministic decision evaluation:
    Determines BUY or WAIT based on:
    1. Liquidity solvency (Does user have enough liquid funds?)
    2. Buffer resilience (Does purchase push buffer to Tight/Risky?)
    3. Goal disruption (Does purchase cause any goal to miss its deadline?)
    4. Monthly cashflow surplus (Can monthly surplus recover the purchase in reasonable time?)
    """
    monthly_surplus = calculate_monthly_surplus(state)
    monthly_expenses = calculate_total_monthly_expenses(state)
    baseline_liquidity = float(state.current_savings)
    post_liquidity = float(baseline_liquidity - purchase.price)

    # 1. Buffer Assessment
    buffer_impact = assess_buffer_impact(state, purchase.price)

    # 2. Goal Impacts
    goal_impacts = project_goals_progress(state, monthly_surplus, purchase.price)

    # 3. Consequence Horizon
    consequence = calculate_consequence_horizon(state, purchase.price, monthly_surplus)

    # 4. Projections
    timeline_projection = project_cash_flow(state, purchase.price, horizon_months=12)

    # 5. Determine Decision Factors & Recommendation
    factors: List[DecisionFactor] = []
    reasons_to_wait = 0
    reasons_to_buy = 0

    # Solvency factor
    if post_liquidity < 0:
        reasons_to_wait += 10 # Hard blocker
        factors.append(DecisionFactor(
            code="INSUFFICIENT_FUNDS",
            title="Capital Deficit",
            severity="danger",
            detail=f"Purchase price (\u20b9{purchase.price:,.0f}) exceeds current liquid savings (\u20b9{baseline_liquidity:,.0f}) by \u20b9{abs(post_liquidity):,.0f}.",
            numerical_impact=f"-\u20b9{abs(post_liquidity):,.0f} shortfall"
        ))
    else:
        # Buffer factor
        if buffer_impact.purchase_resilience == ResilienceLevel.RISKY:
            reasons_to_wait += 4
            factors.append(DecisionFactor(
                code="BUFFER_DEPLETION_RISKY",
                title="Safety Cushion Severely Depleted",
                severity="danger",
                detail=f"Post-purchase runway drops to {buffer_impact.purchase_emergency_runway_months:.1f} months of expenses (< 1.0 month emergency threshold).",
                numerical_impact=f"{buffer_impact.purchase_emergency_runway_months:.1f} mo runway"
            ))
        elif buffer_impact.purchase_resilience == ResilienceLevel.TIGHT:
            reasons_to_wait += 2
            factors.append(DecisionFactor(
                code="BUFFER_DEPLETION_TIGHT",
                title="Cushion Compressed into Tight Zone",
                severity="warning",
                detail=f"Post-purchase emergency runway drops to {buffer_impact.purchase_emergency_runway_months:.1f} months (below recommended 3.0 months).",
                numerical_impact=f"{buffer_impact.purchase_emergency_runway_months:.1f} mo runway"
            ))
        else:
            reasons_to_buy += 2
            factors.append(DecisionFactor(
                code="BUFFER_HEALTHY",
                title="Resilient Financial Buffer Maintained",
                severity="positive",
                detail=f"Post-purchase liquid buffer covers {buffer_impact.purchase_emergency_runway_months:.1f} months of expenses comfortably.",
                numerical_impact=f"{buffer_impact.purchase_emergency_runway_months:.1f} mo runway"
            ))

    # Goal factor
    goals_delayed = [g for g in goal_impacts if not g.purchase_achievable_by_deadline and g.baseline_achievable_by_deadline]
    max_delay_weeks = max([g.delay_in_weeks for g in goal_impacts], default=0)

    if goals_delayed:
        reasons_to_wait += 3
        delayed_names = ", ".join(g.goal_name for g in goals_delayed)
        factors.append(DecisionFactor(
            code="GOAL_DEADLINE_BREACH",
            title="Goal Deadline Disruption",
            severity="danger",
            detail=f"The purchase delays deadline achievement for: {delayed_names}.",
            numerical_impact=f"+{max_delay_weeks} weeks delay"
        ))
    elif max_delay_weeks > 8:
        reasons_to_wait += 2
        factors.append(DecisionFactor(
            code="GOAL_SIGNIFICANT_DELAY",
            title="Material Goal Timeline Delay",
            severity="warning",
            detail=f"Goal completion is shifted out by approximately {max_delay_weeks} weeks.",
            numerical_impact=f"+{max_delay_weeks} weeks delay"
        ))
    elif goal_impacts:
        reasons_to_buy += 1
        factors.append(DecisionFactor(
            code="GOAL_TIMELINE_PRESERVED",
            title="Goal Path On Track",
            severity="positive",
            detail="The purchase creates no new deadline breach and adds no more than 8 weeks of goal delay. Some goals may already be behind schedule.",
            numerical_impact="No new breach"
        ))

    # Surplus & Recovery factor
    if monthly_surplus <= 0:
        reasons_to_wait += 4
        factors.append(DecisionFactor(
            code="ZERO_SURPLUS",
            title="Negative or Zero Monthly Cashflow",
            severity="danger",
            detail=f"Monthly expenses equal or exceed income. Replenishing savings is currently not possible without changes.",
            numerical_impact=f"\u20b9{monthly_surplus:,.0f}/mo surplus"
        ))
    elif consequence.recovery_time_weeks > 26: # > 6 months recovery
        reasons_to_wait += 2
        factors.append(DecisionFactor(
            code="EXTENDED_RECOVERY",
            title="Extended Capital Recovery",
            severity="warning",
            detail=f"Replenishing the \u20b9{purchase.price:,.0f} outlay will require approximately {consequence.recovery_time_weeks} weeks ({consequence.recovery_time_weeks // 4} months).",
            numerical_impact=f"{consequence.recovery_time_weeks} weeks"
        ))
    else:
        reasons_to_buy += 2
        factors.append(DecisionFactor(
            code="RAPID_RECOVERY",
            title="Swift Recovery Horizon",
            severity="positive",
            detail=f"Strong monthly surplus of \u20b9{monthly_surplus:,.0f} allows full replenishment within {consequence.recovery_time_weeks} weeks.",
            numerical_impact=f"{consequence.recovery_time_weeks} weeks"
        ))

    # Liquidity share factor
    liquidity_share_pct = (purchase.price / baseline_liquidity * 100.0) if baseline_liquidity > 0 else 100.0
    if liquidity_share_pct >= 60.0 and post_liquidity >= 0:
        reasons_to_wait += 2
        factors.append(DecisionFactor(
            code="HIGH_LIQUIDITY_ABSORPTION",
            title="High Capital Concentration",
            severity="warning",
            detail=f"This single purchase absorbs {liquidity_share_pct:.0f}% of total available liquid funds.",
            numerical_impact=f"{liquidity_share_pct:.0f}% of savings"
        ))

    # Final Decision Rule
    recommendation = RecommendationEnum.WAIT if (reasons_to_wait > reasons_to_buy or post_liquidity < 0) else RecommendationEnum.BUY

    headline = f"{recommendation.value.title()}: this purchase {'passes' if recommendation == RecommendationEnum.BUY else 'does not pass'} the current financial assessment."
    bottom_line = f"The \u20b9{purchase.price:,.0f} purchase leaves \u20b9{post_liquidity:,.0f} in liquid funds. The checks below explain the verdict, including any trade-offs."
    justification = [{
        "keyword": "Available funds",
        "evidence": f"\u20b9{baseline_liquidity:,.0f} savings - \u20b9{purchase.price:,.0f} purchase = \u20b9{post_liquidity:,.0f} remaining. " + ("A negative balance is a hard WAIT blocker." if post_liquidity < 0 else "You can cover the price from current savings."),
    }, {
        "keyword": "Emergency buffer",
        "evidence": (f"\u20b9{post_liquidity:,.0f} / \u20b9{monthly_expenses:,.0f} monthly expenses = {buffer_impact.purchase_emergency_runway_months:.2f} months of cover. Under 1 month is Risky; 1 to under 3 is Tight; 3 to under 6 is Manageable; 6 or more is Comfortable."
                     if monthly_expenses > 0 else "No monthly expenses were entered, so meaningful expense-based runway cannot be calculated."),
    }, {
        "keyword": "Recovery capacity",
        "evidence": (f"\u20b9{purchase.price:,.0f} / \u20b9{monthly_surplus:,.0f} monthly surplus = {purchase.price / monthly_surplus:.2f} months, or approximately {consequence.recovery_time_weeks} weeks. Recovery above 26 weeks adds a WAIT concern."
                     if monthly_surplus > 0 else f"Monthly surplus is \u20b9{monthly_surplus:,.0f}. Savings cannot rebuild from this cash flow; waiting alone does not fix this."),
    }]
    for goal in goal_impacts:
        justification.append({"keyword": f"Goal: {goal.goal_name}", "evidence": f"Deadline {goal.deadline}: achievable before purchase: {'yes' if goal.baseline_achievable_by_deadline else 'no'}; after purchase: {'yes' if goal.purchase_achievable_by_deadline else 'no'}. Projected delay: {goal.delay_in_weeks} weeks."})
    if not goal_impacts:
        justification.append({"keyword": "Goals", "evidence": "No goals were entered, so other savings priorities could not be checked."})
    justification.extend({"keyword": f.title, "evidence": f.detail} for f in factors)
    justification.append({"keyword": "Decision rule", "evidence": f"WAIT points: {reasons_to_wait}; BUY points: {reasons_to_buy}. A negative remaining balance always means WAIT. Otherwise WAIT wins when its points exceed BUY points; ties resolve to BUY. These are policy weights, not probabilities."})
    if monthly_surplus > 0:
        justification.append({"keyword": "Example using your figures", "evidence": f"Save one month's surplus, then pay the same price: \u20b9{baseline_liquidity:,.0f} + \u20b9{monthly_surplus:,.0f} - \u20b9{purchase.price:,.0f} = \u20b9{post_liquidity + monthly_surplus:,.0f} remaining. This illustration assumes unchanged income and expenses and excludes additional obligations or goal allocations. It does not guarantee a different verdict after one month."})

    assumptions = [
        f"Monthly income remains stable at \u20b9{state.monthly_income + state.additional_income:,.0f}.",
        f"Recurring fixed expenses do not exceed \u20b9{state.recurring_expenses:,.0f}/month.",
        f"Projected surplus of \u20b9{monthly_surplus:,.0f}/month is redirected towards rebuilding savings.",
        "Emergency buffer benchmark is calculated at 3.0 months of recurring obligations.",
        "Calculations are strictly deterministic and based on your entered parameters."
    ]

    return DecisionResult(
        recommendation=recommendation,
        headline=headline,
        bottom_line=bottom_line,
        purchase_name=purchase.name,
        purchase_price=purchase.price,
        monthly_surplus=monthly_surplus,
        baseline_liquidity=baseline_liquidity,
        post_purchase_liquidity=post_liquidity,
        buffer_impact=buffer_impact,
        goal_impacts=goal_impacts,
        consequence=consequence,
        supporting_factors=factors,
        timeline_projection=timeline_projection,
        assumptions=assumptions,
        justification=justification
    )

