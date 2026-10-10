from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import date
from enum import Enum

class RecommendationEnum(str, Enum):
    BUY = "BUY"
    WAIT = "WAIT"

class ResilienceLevel(str, Enum):
    COMFORTABLE = "Comfortable"
    MANAGEABLE = "Manageable"
    TIGHT = "Tight"
    RISKY = "Risky"

class Obligation(BaseModel):
    name: str
    amount: float = Field(..., ge=0, description="Amount due")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    recurrence: Optional[str] = Field("one_time", description="one_time or monthly")

class FinancialGoal(BaseModel):
    id: Optional[str] = None
    name: str
    target_amount: float = Field(..., ge=0)
    current_amount: float = Field(0.0, ge=0)
    deadline: str = Field(..., description="Target completion date YYYY-MM-DD")
    monthly_allocation: Optional[float] = Field(None, ge=0, description="Explicit monthly savings allocation, or auto-calculated from surplus")

class UserFinancialState(BaseModel):
    monthly_income: float = Field(..., ge=0)
    additional_income: float = Field(0.0, ge=0)
    current_savings: float = Field(..., ge=0, description="Total liquid funds available")
    recurring_expenses: float = Field(..., ge=0, description="Fixed unavoidable monthly expenses like rent, utilities, insurance")
    discretionary_expenses: float = Field(0.0, ge=0, description="Lifestyle, dining, leisure")
    upcoming_obligations: List[Obligation] = Field(default_factory=list)
    goals: List[FinancialGoal] = Field(default_factory=list)

    @field_validator('monthly_income', 'current_savings', 'recurring_expenses')
    @classmethod
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError("Financial figures cannot be negative")
        return v

class PurchaseDecision(BaseModel):
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    planned_date: Optional[str] = Field(None, description="Planned purchase date in YYYY-MM-DD, defaults to immediate")

class PeriodProjection(BaseModel):
    month_index: int
    period_label: str
    income: float
    expenses: float
    obligations: float
    surplus: float
    baseline_savings: float
    purchase_savings: Optional[float] = None
    baseline_liquidity: float
    purchase_liquidity: Optional[float] = None
    goal_progress: Dict[str, float] = Field(default_factory=dict)
    purchase_goal_progress: Optional[Dict[str, float]] = None

class GoalProjectionResult(BaseModel):
    goal_id: str
    goal_name: str
    target_amount: float
    current_amount: float
    deadline: str
    baseline_projected_completion_date: Optional[str]
    purchase_projected_completion_date: Optional[str]
    delay_in_weeks: int
    baseline_achievable_by_deadline: bool
    purchase_achievable_by_deadline: bool
    progress_percentage: float
    purchase_progress_percentage: float

class BufferAssessment(BaseModel):
    baseline_emergency_runway_months: float
    purchase_emergency_runway_months: float
    buffer_reduction_amount: float
    buffer_reduction_percentage: float
    baseline_resilience: ResilienceLevel
    purchase_resilience: ResilienceLevel
    safe_minimum_buffer: float

class ConsequenceHorizon(BaseModel):
    recovery_time_weeks: int
    consequence_horizon_weeks: int
    summary_wording: str

class DecisionFactor(BaseModel):
    code: str
    title: str
    severity: str # 'positive' | 'warning' | 'danger' | 'neutral'
    detail: str
    numerical_impact: Optional[str] = None

class DecisionResult(BaseModel):
    recommendation: RecommendationEnum
    headline: str
    bottom_line: str
    purchase_name: str
    purchase_price: float
    monthly_surplus: float
    baseline_liquidity: float
    post_purchase_liquidity: float
    buffer_impact: BufferAssessment
    goal_impacts: List[GoalProjectionResult]
    consequence: ConsequenceHorizon
    supporting_factors: List[DecisionFactor]
    timeline_projection: List[PeriodProjection]
    assumptions: List[str]
    justification: List[Dict[str, str]] = Field(default_factory=list)

class ExplanationRequest(BaseModel):
    decision_result: DecisionResult

class ExplanationResponse(BaseModel):
    recommendation: RecommendationEnum
    title: str
    summary: str
    sections: List[Dict[str, str]]
    bottom_line: str

