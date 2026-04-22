export interface NotificationConfig {
    telegram_configured: boolean;
    telegram_bot_token: string;
    telegram_chat_id: string;
}

export interface NotificationTestResponse {
    status: string;
    reason?: string | null;
}

export type ProductSyncSource = 'treejar' | 'zoho';

export interface ProductSyncResponse {
    synced: number;
    created: number;
    updated: number;
    errors: number;
    deactivated: number;
    embeddings_generated: number;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    pages: number;
}

export interface ManagerReviewRead {
    id: string;
    escalation_id: string;
    conversation_id: string;
    manager_name: string | null;
    total_score: number;
    max_score: number;
    rating: string;
    first_response_time_seconds: number | null;
    message_count: number | null;
    deal_converted: boolean;
    deal_amount: number | null;
    reviewer: string;
    created_at: string;
}

export interface ManagerReviewDetail extends ManagerReviewRead {
    criteria: Array<Record<string, unknown>>;
    summary: string | null;
}

export interface PendingManagerReview {
    escalation_id: string;
    conversation_id: string;
    phone: string;
    manager_name: string | null;
    reason: string;
    status: string;
    updated_at: string;
}

export interface OperationsReportTopProduct {
    name: string;
    sku: string;
    mentions: number;
}

export interface OperationsReportTopManager {
    name: string;
    avg_score: number;
}

export interface OperationsReportData {
    period_start: string;
    period_end: string;
    total_conversations: number;
    conversations_per_day: number;
    unique_customers: number;
    total_deals: number;
    conversion_rate: number;
    avg_deal_value: number;
    avg_quality_score: number;
    escalation_count: number;
    escalation_reasons: Record<string, number>;
    top_products: OperationsReportTopProduct[];
    avg_manager_score: number;
    avg_manager_response_time_seconds: number;
    manager_deal_conversion_rate: number;
    manager_reviews_count: number;
    top_managers: OperationsReportTopManager[];
}

export interface OperationsReportResponse {
    data: OperationsReportData;
    text: string;
}

export type AIQualityScopeKey = 'bot_qa' | 'manager_qa' | 'red_flags';

export type AIQualityMode = 'disabled' | 'manual' | 'daily_sample' | 'scheduled';

export type AIQualityTranscriptMode = 'disabled' | 'summary' | 'full';

export interface AIQualityRetryPolicy {
    max_attempts: number;
    backoff_seconds: number;
}

export interface AIQualityScopeConfig {
    mode: AIQualityMode;
    transcript_mode: AIQualityTranscriptMode;
    model: string;
    daily_budget_cents: number;
    max_calls_per_run: number;
    max_calls_per_day: number;
    retry: AIQualityRetryPolicy;
    criteria: Record<string, boolean>;
    cache_telemetry_enabled: boolean;
    alert_on_failure: boolean;
    full_transcript_warning_override: boolean;
    glm5_warning_override: boolean;
}

export interface AIQualityControlsConfig {
    bot_qa: AIQualityScopeConfig;
    manager_qa: AIQualityScopeConfig;
    red_flags: AIQualityScopeConfig;
}

export interface AIQualityWarning {
    scope: AIQualityScopeKey;
    code: 'full_transcript' | 'glm5_qa';
    severity: 'warning';
    message: string;
}

export interface AIQualityControlsResponse {
    config: AIQualityControlsConfig;
    warnings: AIQualityWarning[];
}

export interface AIQualityRetryPolicyUpdate {
    max_attempts?: number;
    backoff_seconds?: number;
}

export interface AIQualityScopeUpdate {
    mode?: AIQualityMode;
    transcript_mode?: AIQualityTranscriptMode;
    model?: string;
    daily_budget_cents?: number;
    max_calls_per_run?: number;
    max_calls_per_day?: number;
    retry?: AIQualityRetryPolicyUpdate;
    criteria?: Record<string, boolean>;
    cache_telemetry_enabled?: boolean;
    alert_on_failure?: boolean;
    full_transcript_warning_override?: boolean;
    glm5_warning_override?: boolean;
}

export type AIQualityControlsUpdate = Partial<Record<AIQualityScopeKey, AIQualityScopeUpdate>>;
