/** TypeScript types matching DashboardMetricsResponse from backend. */

export interface SalesMetrics {
    count: number;
    amount: number;
}

export interface ManagerLeaderboardEntry {
    name: string;
    avg_score: number;
    reviews_count: number;
}

export interface DashboardMetrics {
    period: string;

    // Volume (3)
    total_conversations: number;
    unique_customers: number;
    new_vs_returning: { new: number; returning: number };

    // Classification (3)
    by_segment: Record<string, number>;
    by_language: Record<string, number>;
    target_vs_nontarget: { target: number; nontarget: number };

    // Escalation (2)
    escalation_count: number;
    escalation_reasons: Record<string, number>;

    // Sales (4)
    noor_sales: SalesMetrics;
    post_escalation_sales: SalesMetrics;
    conversion_rate: number;
    average_deal_value: number;

    // Quality (3)
    avg_conversation_length: number;
    avg_quality_score: number;
    avg_response_time_ms: number;

    // Cost
    llm_cost_usd: number;

    // Manager performance
    avg_manager_score: number;
    avg_manager_response_time_seconds: number;
    manager_deal_conversion_rate: number;
    manager_leaderboard: ManagerLeaderboardEntry[];

    // Feedback
    feedback_count: number;
    avg_rating_overall: number;
    avg_rating_delivery: number;
    nps_score: number;
    recommend_rate: number;
}

export type Period = 'day' | 'week' | 'month' | 'all_time';

export interface TimeseriesPoint {
    date: string;
    new: number;
    returning: number;
}

export interface TimeseriesResponse {
    period: string;
    points: TimeseriesPoint[];
}
