import re
import pytest
from backend.app.engine.decision import evaluate_decision
from backend.app.schemas.financial import UserFinancialState, PurchaseDecision
from backend.app.services.explanation import generate_deterministic_explanation


@pytest.mark.parametrize("savings,income,expected", [(500000, 60000, "BUY"), (10000, 60000, "WAIT"), (100000, 20000, "WAIT")])
def test_currency_and_evidence(savings, income, expected):
    result = evaluate_decision(UserFinancialState(monthly_income=income, current_savings=savings,
        recurring_expenses=25000, discretionary_expenses=10000), PurchaseDecision(name="Laptop", price=70000))
    assert result.recommendation.value == expected
    assert "\u20b970,000" in result.bottom_line
    evidence = {item["keyword"]: item["evidence"] for item in result.justification}
    assert f"\u20b9{savings - 70000:,.0f}" in evidence["Available funds"]
    assert "WAIT points:" in evidence["Decision rule"]
    if income <= 35000:
        assert "waiting alone" in evidence["Recovery capacity"]
        assert "Example using your figures" not in evidence
    else:
        assert f"\u20b9{savings + income - 35000 - 70000:,.0f}" in evidence["Example using your figures"]
    explanation = generate_deterministic_explanation(result)
    assert explanation.bottom_line == result.bottom_line
    assert not re.search(r"\?\d", result.model_dump_json() + explanation.model_dump_json())
