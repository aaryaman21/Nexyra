import pytest
from backend.app.schemas.financial import (
    UserFinancialState,
    PurchaseDecision,
    FinancialGoal,
    Obligation,
    RecommendationEnum,
    ResilienceLevel
)
from backend.app.engine.financial_state import (
    calculate_total_income,
    calculate_total_monthly_expenses,
    calculate_monthly_surplus
)
from backend.app.engine.risk import assess_buffer_impact
from backend.app.engine.consequence import calculate_consequence_horizon
from backend.app.engine.decision import evaluate_decision

@pytest.fixture
def base_user_state():
    return UserFinancialState(
        monthly_income=60000.0,
        additional_income=0.0,
        current_savings=100000.0,
        recurring_expenses=25000.0,
        discretionary_expenses=10000.0,
        upcoming_obligations=[],
        goals=[
            FinancialGoal(
                name="Emergency Reserve",
                target_amount=150000.0,
                current_amount=50000.0,
                deadline="2027-12-31"
            )
        ]
    )

def test_surplus_calculation(base_user_state):
    surplus = calculate_monthly_surplus(base_user_state)
    # Income (60k) - Expenses (25k + 10k = 35k) = 25k
    assert surplus == 25000.0

def test_demo_scenario_liquidity_pressure():
    """
    From specification Section 32:
    Income: ?60,000/month
    Expenses: ?35,000/month
    Savings: ?1,00,000
    Purchase: ?70,000
    Demonstrates technically affordable (100k > 70k) but financially unsuitable
    because it absorbs 70% of savings and leaves buffer in Tight/Risky zone.
    Result: WAIT
    """
    state = UserFinancialState(
        monthly_income=60000.0,
        additional_income=0.0,
        current_savings=100000.0,
        recurring_expenses=25000.0,
        discretionary_expenses=10000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="Laptop", price=70000.0)
    decision = evaluate_decision(state, purchase)

    assert decision.recommendation == RecommendationEnum.WAIT
    assert decision.post_purchase_liquidity == 30000.0
    assert decision.buffer_impact.purchase_resilience in (ResilienceLevel.TIGHT, ResilienceLevel.RISKY)
    assert any("70%" in f.detail or "Concentration" in f.title for f in decision.supporting_factors)

def test_comfortable_purchase():
    """
    High income and ample savings:
    Income: 200,000, Expenses: 50,000, Savings: 500,000, Purchase: 50,000
    Result: BUY
    """
    state = UserFinancialState(
        monthly_income=200000.0,
        additional_income=0.0,
        current_savings=500000.0,
        recurring_expenses=40000.0,
        discretionary_expenses=10000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="Ergonomic Chair", price=50000.0)
    decision = evaluate_decision(state, purchase)

    assert decision.recommendation == RecommendationEnum.BUY
    assert decision.post_purchase_liquidity == 450000.0
    assert decision.buffer_impact.purchase_resilience == ResilienceLevel.COMFORTABLE

def test_insufficient_funds_shortfall():
    """
    Purchase price greater than liquid savings:
    Savings: 50,000, Purchase: 80,000
    Result: WAIT with capital deficit factor
    """
    state = UserFinancialState(
        monthly_income=50000.0,
        additional_income=0.0,
        current_savings=50000.0,
        recurring_expenses=30000.0,
        discretionary_expenses=5000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="Motorbike", price=80000.0)
    decision = evaluate_decision(state, purchase)

    assert decision.recommendation == RecommendationEnum.WAIT
    assert decision.post_purchase_liquidity < 0
    assert any(f.code == "INSUFFICIENT_FUNDS" for f in decision.supporting_factors)

def test_zero_income_case():
    state = UserFinancialState(
        monthly_income=0.0,
        additional_income=0.0,
        current_savings=50000.0,
        recurring_expenses=20000.0,
        discretionary_expenses=5000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="Phone", price=25000.0)
    decision = evaluate_decision(state, purchase)
    assert decision.recommendation == RecommendationEnum.WAIT
    assert any(f.code == "ZERO_SURPLUS" for f in decision.supporting_factors)

def test_zero_savings_case():
    state = UserFinancialState(
        monthly_income=50000.0,
        additional_income=0.0,
        current_savings=0.0,
        recurring_expenses=30000.0,
        discretionary_expenses=5000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="Watch", price=10000.0)
    decision = evaluate_decision(state, purchase)
    assert decision.recommendation == RecommendationEnum.WAIT
    assert decision.post_purchase_liquidity < 0

def test_consequence_horizon_wording():
    state = UserFinancialState(
        monthly_income=60000.0,
        additional_income=0.0,
        current_savings=100000.0,
        recurring_expenses=25000.0,
        discretionary_expenses=10000.0,
        upcoming_obligations=[],
        goals=[]
    )
    consequence = calculate_consequence_horizon(state, purchase_price=50000.0, monthly_surplus=25000.0)
    assert consequence.recovery_time_weeks > 0
    assert "This purchase is projected to affect your savings trajectory" in consequence.summary_wording


def test_goal_conflict_scenario():
    # User has an active goal that requires full surplus to hit deadline.
    # A purchase delays goal completion beyond the deadline.
    state = UserFinancialState(
        monthly_income=70000.0,
        additional_income=0.0,
        current_savings=80000.0,
        recurring_expenses=40000.0,
        discretionary_expenses=10000.0,
        upcoming_obligations=[],
        goals=[
            FinancialGoal(
                name="Urgent Medical Exam",
                target_amount=100000.0,
                current_amount=60000.0,
                deadline="2026-11-30" # 2.5 months away
            )
        ]
    )
    # Surplus is 20k. Gap is 40k. Baseline completes in 2 months (before deadline).
    # With 50k purchase, goal is pushed back > 2.5 months, breaching deadline.
    purchase = PurchaseDecision(name="Gaming Console", price=50000.0)
    decision = evaluate_decision(state, purchase)
    assert decision.recommendation == RecommendationEnum.WAIT
    assert any("GOAL" in f.code for f in decision.supporting_factors)

def test_purchase_greater_than_savings():
    state = UserFinancialState(
        monthly_income=50000.0,
        additional_income=0.0,
        current_savings=20000.0,
        recurring_expenses=20000.0,
        discretionary_expenses=5000.0,
        upcoming_obligations=[],
        goals=[]
    )
    purchase = PurchaseDecision(name="New Sofa", price=35000.0)
    decision = evaluate_decision(state, purchase)
    assert decision.recommendation == RecommendationEnum.WAIT
    assert decision.post_purchase_liquidity == -15000.0
    assert any(f.code == "INSUFFICIENT_FUNDS" for f in decision.supporting_factors)
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_demo_endpoint_removed():
    assert client.get("/api/demo").status_code == 404

def test_api_decision_simulate(base_user_state):
    payload = base_user_state.model_dump(mode="json")
    payload["purchase"] = {"name": "Laptop", "price": 70000.0}

    assert client.post("/api/decision/simulate", json=payload).status_code == 404

def test_api_decision_explain(base_user_state):
    payload = base_user_state.model_dump(mode="json")
    payload["purchase"] = {"name": "Laptop", "price": 70000.0}
    assert client.post("/api/decision/simulate", json=payload).status_code == 404
    assert client.post("/api/decision/explain", json={}).status_code == 404
