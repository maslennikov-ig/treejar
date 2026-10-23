export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    pages: number;
}

export interface AdminCustomerListItem {
    phone: string;
    customer_name: string | null;
    latest_conversation_id: string;
    latest_message_at: string | null;
    latest_message_preview: string | null;
    conversation_count: number;
    status: string;
    sales_stage: string;
    language: string;
    escalation_status: string;
    deal_status: string | null;
    zoho_contact_id: string | null;
    zoho_deal_id: string | null;
    segment: string | null;
    updated_at: string | null;
}

export interface AdminConversationListItem {
    id: string;
    phone: string;
    customer_name: string | null;
    language: string;
    sales_stage: string;
    status: string;
    escalation_status: string;
    deal_status: string | null;
    deal_amount: number | null;
    zoho_contact_id: string | null;
    zoho_deal_id: string | null;
    message_count: number;
    last_message_at: string | null;
    last_message_preview: string | null;
    source: string | null;
    segment: string | null;
    utm: Record<string, unknown> | null;
    order_metadata: Record<string, unknown> | null;
    metadata: Record<string, unknown> | null;
    created_at: string;
    updated_at: string | null;
}

export interface AdminTimelineMessage {
    id: string;
    role: string;
    content: string;
    message_type: string;
    created_at: string;
    wazzup_message_id: string | null;
    model: string | null;
    cost: number | null;
    audio_url: string | null;
    transcription: string | null;
}

export interface AdminEscalationRead {
    id: string;
    conversation_id: string;
    reason: string;
    assigned_to: string | null;
    status: string;
    notes: string | null;
    created_at: string;
    updated_at: string | null;
}

export interface AdminQualityReviewSummary {
    id: string;
    conversation_id: string;
    total_score: number;
    max_score: number;
    rating: string;
    summary: string | null;
    reviewer: string;
    created_at: string;
}

export interface AdminManagerReviewSummary {
    id: string;
    escalation_id: string;
    conversation_id: string;
    manager_name: string | null;
    total_score: number;
    max_score: number;
    rating: string;
    summary: string | null;
    deal_converted: boolean;
    deal_amount: number | null;
    reviewer: string;
    created_at: string;
}

export interface AdminFeedbackRead {
    id: string;
    rating_overall: number;
    rating_delivery: number;
    recommend: boolean;
    comment: string | null;
    created_at: string;
}

export interface AdminOutboundAuditRead {
    id: string;
    provider: string;
    message_type: string;
    source: string;
    status: string;
    provider_message_id: string | null;
    crm_message_id: string | null;
    content: string | null;
    caption: string | null;
    created_at: string;
}

export interface AdminBotRuleApplied {
    id: string;
    title: string;
    type: string;
    priority: number;
    scope: string;
    instruction: string;
}

export interface AdminConversationDetail extends AdminConversationListItem {
    timeline: AdminTimelineMessage[];
    escalations: AdminEscalationRead[];
    quality_reviews: AdminQualityReviewSummary[];
    manager_reviews: AdminManagerReviewSummary[];
    feedback: AdminFeedbackRead[];
    outbound_audits: AdminOutboundAuditRead[];
    applied_bot_rules: AdminBotRuleApplied[];
}

export interface AdminConversationUpdate {
    customer_name?: string | null;
    status?: string | null;
    sales_stage?: string | null;
    escalation_status?: string | null;
    deal_status?: string | null;
    language?: 'en' | 'ar' | null;
}

export interface AdminActionAuditRead {
    id: string;
    actor: string;
    action: string;
    entity_type: string;
    entity_id: string | null;
    request_path: string | null;
    before: unknown;
    after: unknown;
    metadata: unknown;
    created_at: string;
}

export interface AdminKnowledgeBaseRead {
    id: string;
    source: string;
    title: string;
    content: string;
    language: string;
    category: string | null;
    has_embedding: boolean;
    is_auto_generated: boolean;
    is_canonical_customized?: boolean;
    original_question: string | null;
    manager_draft: string | null;
    created_at: string;
    updated_at: string | null;
    deleted_at: string | null;
    deleted_by: string | null;
}

export interface AdminKnowledgeBaseWrite {
    source: string;
    title: string;
    content: string;
    language: 'en' | 'ar';
    category: string | null;
}

export interface AdminKnowledgeBasePreview {
    embedding_ready: boolean;
    duplicate: boolean;
    duplicate_similarity: number | null;
    unsafe_reasons: string[];
    context_reasons: string[];
}

export interface AdminKnowledgeBaseCandidate {
    id: string;
    question: string;
    answer: string;
    language: string;
    confidence: number | null;
    status: string;
    guard_reasons: string[];
    duplicate_similarity: number | null;
    original_question: string | null;
    manager_draft: string | null;
    customer_message: string | null;
    metadata: Record<string, unknown> | null;
    created_at: string;
    updated_at: string | null;
}

export interface AdminKnowledgeBaseCandidateReject {
    reason?: string | null;
}

export interface AdminBotRuleRead {
    id: string;
    title: string;
    type: string;
    status: string;
    priority: number;
    scope: string;
    stage: string | null;
    language: string | null;
    segment: string | null;
    instruction: string;
    trigger_examples: string[];
    has_embedding: boolean;
    source_type?: string;
    canonical_key?: string | null;
    is_canonical_customized?: boolean;
    created_by: string;
    updated_by: string;
    created_at: string;
    updated_at: string | null;
    archived_at: string | null;
}

export interface AdminBotRuleWrite {
    title: string;
    type: 'hard_rule' | 'playbook' | 'upsell_rule' | 'style_rule' | 'escalation_rule';
    status: 'draft' | 'active' | 'archived';
    priority: number;
    scope: 'global' | 'stage' | 'language' | 'segment' | 'conversation';
    stage: string | null;
    language: 'en' | 'ar' | null;
    segment: string | null;
    instruction: string;
    trigger_examples: string[];
}

export interface AdminBotRulePreviewRequest {
    message: string;
    stage: string | null;
    language: 'en' | 'ar' | null;
    segment: string | null;
    conversation_id?: string | null;
}

export interface AdminBotRulePreviewResponse {
    applied_rules: AdminBotRuleApplied[];
    prompt_block: string;
    rule_count: number;
}

export type CanonicalSyncMode = 'safe' | 'full_reset';

export interface AdminCanonicalSyncResult {
    ok: boolean;
    status: string;
    mode?: CanonicalSyncMode;
    created: number;
    updated: number;
    restored: number;
    unchanged: number;
    skipped_customized?: number;
    skipped_deleted?: number;
    total_active: number;
    detail: string | null;
}

export interface AdminCanonicalSyncPreviewItem {
    key: string;
    title: string;
    category: string | null;
    status: 'missing' | 'customized' | 'deleted' | 'unchanged' | 'unindexed';
    changed_fields: string[];
}

export interface AdminCanonicalSyncPreview {
    kind: 'knowledge' | 'bot_rules';
    total_templates: number;
    will_create: number;
    customized: number;
    deleted_or_archived: number;
    unchanged: number;
    unindexed: number;
    items: AdminCanonicalSyncPreviewItem[];
}

export interface AdminCanonicalSyncStatus {
    kind: 'knowledge' | 'bot_rules';
    running: boolean;
    last_mode: string | null;
    last_synced_at: string | null;
    last_result: AdminCanonicalSyncResult | null;
    total_templates: number;
    active_canonical_count: number;
    customized_count: number;
    unindexed_count: number;
}

export interface AdminEscalationQueueItem {
    id: string;
    conversation_id: string;
    phone: string;
    customer_name: string | null;
    reason: string;
    category: string;
    assigned_to: string | null;
    status: string;
    notes: string | null;
    sales_stage: string | null;
    created_at: string;
    updated_at: string | null;
}

export interface AdminCatalogSyncSourceStatus {
    source: string;
    last_triggered_at: string | null;
    last_status: string;
    job_name: string | null;
    detail: string | null;
}

export interface AdminZohoSnapshotStatus {
    present: boolean;
    status: 'fresh' | 'stale' | 'missing';
    item_count: number;
    updated_at: string | null;
    age_seconds: number | null;
    ttl_seconds: number | null;
}

export interface AdminCatalogStatusResponse {
    active_products_count: number;
    total_products_count: number;
    indexed_products_count: number;
    sources: Record<string, AdminCatalogSyncSourceStatus>;
    zoho_snapshot: AdminZohoSnapshotStatus;
}

export interface AdminSystemHealthContour {
    id: string;
    label: string;
    status: 'ok' | 'warning' | 'error';
    summary: string;
    detail: string | null;
    updated_at: string | null;
}

export interface AdminSystemHealthResponse {
    overall_status: 'ok' | 'warning' | 'error';
    contours: AdminSystemHealthContour[];
    last_inbound_message_at: string | null;
    active_kb_count: number;
    active_bot_rules_count: number;
    open_escalations_count: number;
    pending_manager_reviews_count: number;
    checked_at: string;
}

export interface AdminResetPreview {
    phone: string;
    phone_variants: string[];
    conversation_count: number;
    latest_conversation_id: string | null;
    message_count: number;
    pending_escalation_count: number;
}

export interface AdminResetExecuteResult {
    phone: string;
    archived_count: number;
    new_conversation_id: string | null;
}
