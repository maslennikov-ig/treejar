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
