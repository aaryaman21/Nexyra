export type Recommendation = 'BUY' | 'WAIT';

export type ResilienceLevel = 'Comfortable' | 'Manageable' | 'Tight' | 'Risky';

export interface Obligation {
  name: string;
  amount: number;
  due_date?: string;
  recurrence?: 'one_time' | 'monthly';
}

export interface FinancialGoal {
  id?: string;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  monthly_allocation?: number;
}

export interface UserFinancialState {
  monthly_income: number;
  additional_income: number;
  current_savings: number;
  recurring_expenses: number;
  discretionary_expenses: number;
  upcoming_obligations: Obligation[];
  goals: FinancialGoal[];
}

export interface PurchaseDecision {
  name: string;
  price: number;
  planned_date?: string;
}

export interface PeriodProjection {
  month_index: number;
  period_label: string;
  income: number;
  expenses: number;
  obligations: number;
  surplus: number;
  baseline_savings: number;
  purchase_savings: number;
  baseline_liquidity: number;
  purchase_liquidity: number;
  goal_progress: Record<string, number>;
  purchase_goal_progress: Record<string, number>;
}

export interface GoalProjectionResult {
  goal_id: string;
  goal_name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  baseline_projected_completion_date: string | null;
  purchase_projected_completion_date: string | null;
  delay_in_weeks: number;
  baseline_achievable_by_deadline: boolean;
  purchase_achievable_by_deadline: boolean;
  progress_percentage: number;
  purchase_progress_percentage: number;
}

export interface BufferAssessment {
  baseline_emergency_runway_months: number;
  purchase_emergency_runway_months: number;
  buffer_reduction_amount: number;
  buffer_reduction_percentage: number;
  baseline_resilience: ResilienceLevel;
  purchase_resilience: ResilienceLevel;
  safe_minimum_buffer: number;
}

export interface ConsequenceHorizon {
  recovery_time_weeks: number;
  consequence_horizon_weeks: number;
  summary_wording: string;
}

export interface DecisionFactor {
  code: string;
  title: string;
  severity: 'positive' | 'warning' | 'danger' | 'neutral';
  detail: string;
  numerical_impact?: string;
}

export interface DecisionResult {
  recommendation: Recommendation;
  headline: string;
  bottom_line: string;
  purchase_name: string;
  purchase_price: number;
  monthly_surplus: number;
  baseline_liquidity: number;
  post_purchase_liquidity: number;
  buffer_impact: BufferAssessment;
  goal_impacts: GoalProjectionResult[];
  consequence: ConsequenceHorizon;
  supporting_factors: DecisionFactor[];
  timeline_projection: PeriodProjection[];
  assumptions: string[];
  justification?: { keyword: string; evidence: string }[];
}

export interface ExplanationSection {
  number: string;
  title: string;
  detail: string;
}

export interface ExplanationResponse {
  recommendation: Recommendation;
  title: string;
  summary: string;
  sections: ExplanationSection[];
  bottom_line: string;
}
