import os
import httpx
from backend.app.schemas.financial import DecisionResult, ExplanationResponse, RecommendationEnum

def generate_deterministic_explanation(decision: DecisionResult) -> ExplanationResponse:
    """
    Strict, deterministic explanation based solely on calculated factors.
    Zero hallucination, clear, factual, and transparent.
    """
    sections = []

    # Section 01: Liquidity & Cushion
    liq_change = decision.baseline_liquidity - decision.post_purchase_liquidity
    cushion_state = decision.buffer_impact.purchase_resilience.value
    sections.append({
        "number": "01",
        "title": "LIQUIDITY & RUNWAY",
        "detail": f"The planned purchase of \u20b9{decision.purchase_price:,.0f} reduces liquid funds from \u20b9{decision.baseline_liquidity:,.0f} to \u20b9{decision.post_purchase_liquidity:,.0f}. Your post-purchase emergency runway shifts to {decision.buffer_impact.purchase_emergency_runway_months:.1f} months of expenses ({cushion_state} resilience)."
    })

    # Section 02: Goal Impact
    if decision.goal_impacts:
        delayed = [g for g in decision.goal_impacts if g.delay_in_weeks > 0]
        if delayed:
            delay_details = "; ".join([f"{g.goal_name} shifted by ~{g.delay_in_weeks} weeks" for g in delayed])
            sections.append({
                "number": "02",
                "title": "GOAL IMPACT",
                "detail": f"Direct capital deduction shifts completion timelines: {delay_details}."
            })
        else:
            sections.append({
                "number": "02",
                "title": "GOAL IMPACT",
                "detail": "No additional goal delay is projected. Check each goal for its deadline feasibility."
            })
    else:
        sections.append({
            "number": "02",
            "title": "GOAL IMPACT",
            "detail": "No active goals currently defined to be compromised."
        })

    # Section 03: Recovery Horizon
    weeks = decision.consequence.consequence_horizon_weeks
    recovery_weeks = decision.consequence.recovery_time_weeks
    sections.append({
        "number": "03",
        "title": "RECOVERY HORIZON",
        "detail": (f"Based on your net monthly surplus of \u20b9{decision.monthly_surplus:,.0f}, full capital recovery will require approximately {recovery_weeks} weeks. Total trajectory consequence horizon is estimated at {weeks} weeks."
                   if decision.monthly_surplus > 0 else "There is no positive monthly surplus, so recovery cannot be projected from the current cash flow.")
    })

    summary = decision.headline
    bottom_line = decision.bottom_line

    return ExplanationResponse(
        recommendation=decision.recommendation,
        title=f"WHY NEXYRA RECOMMENDS {decision.recommendation.value}",
        summary=summary,
        sections=sections,
        bottom_line=bottom_line
    )

async def generate_explanation(decision: DecisionResult) -> ExplanationResponse:
    """
    Produces plain-language reasoning. If LLM API key (OPENAI_API_KEY, GEMINI_API_KEY, etc.) is configured,
    it enhances phrasing while strictly adhering to the calculated facts. Otherwise, uses authoritative deterministic explainer.
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return generate_deterministic_explanation(decision)

    # If external LLM key is supplied, query with strict guardrails
    try:
        system_prompt = (
            "You are the explanation module of NEXYRA, a financial decision intelligence engine. "
            "Explain the calculated BUY or WAIT recommendation to the user using strictly the provided facts. "
            "Do NOT invent any numbers, market conditions, or advice outside the provided metrics. "
            "Keep it concise, clear, and professional."
        )
        prompt = f"""
Recommendation: {decision.recommendation.value}
Purchase: {decision.purchase_name} for \u20b9{decision.purchase_price:,.0f}
Monthly Surplus: \u20b9{decision.monthly_surplus:,.0f}
Current Liquidity: \u20b9{decision.baseline_liquidity:,.0f}
Post-Purchase Liquidity: \u20b9{decision.post_purchase_liquidity:,.0f}
Emergency Runway: {decision.buffer_impact.purchase_emergency_runway_months:.1f} months ({decision.buffer_impact.purchase_resilience.value})
Recovery Time: {decision.consequence.recovery_time_weeks} weeks
Consequence Horizon: {decision.consequence.consequence_horizon_weeks} weeks
Supporting Factors: {[f.detail for f in decision.supporting_factors]}
"""
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                # Return structured deterministic with enhanced summary
                det = generate_deterministic_explanation(decision)
                det.summary = text[:250] + "..." if len(text) > 250 else text
                return det
    except Exception:
        pass

    return generate_deterministic_explanation(decision)
