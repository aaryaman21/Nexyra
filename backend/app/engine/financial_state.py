from backend.app.schemas.financial import UserFinancialState

def calculate_total_income(state: UserFinancialState) -> float:
    return float(state.monthly_income + state.additional_income)

def calculate_total_monthly_expenses(state: UserFinancialState) -> float:
    return float(state.recurring_expenses + state.discretionary_expenses)

def calculate_monthly_surplus(state: UserFinancialState) -> float:
    """
    Net monthly surplus = Total Monthly Income - Total Monthly Expenses
    """
    total_income = calculate_total_income(state)
    total_expenses = calculate_total_monthly_expenses(state)
    return float(total_income - total_expenses)

def calculate_monthly_obligations(state: UserFinancialState, month_index: int = 0) -> float:
    """
    Calculates obligations applicable in a given month.
    If recurrence is 'monthly', it applies every month.
    If 'one_time', it applies in month_index == 0 unless specified.
    """
    total = 0.0
    for ob in state.upcoming_obligations:
        if ob.recurrence == "monthly":
            total += ob.amount
        elif month_index == 0:
            total += ob.amount
    return float(total)

