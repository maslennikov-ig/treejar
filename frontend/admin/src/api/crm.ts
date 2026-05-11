import type {
    AdminActionAuditRead,
    AdminBotRulePreviewRequest,
    AdminBotRulePreviewResponse,
    AdminBotRuleRead,
    AdminBotRuleWrite,
    AdminConversationDetail,
    AdminConversationUpdate,
    AdminCustomerListItem,
    AdminKnowledgeBaseCandidate,
    AdminKnowledgeBaseCandidateReject,
    AdminKnowledgeBasePreview,
    AdminKnowledgeBaseRead,
    AdminKnowledgeBaseWrite,
    PaginatedResponse,
} from '@/types/crm';

const ADMIN_BASE = '/api/v1/admin';

async function responseError(response: Response): Promise<Error> {
    const text = await response.text();
    try {
        const payload = JSON.parse(text) as { detail?: unknown };
        if (typeof payload.detail === 'string') {
            return new Error(payload.detail);
        }
        if (Array.isArray(payload.detail)) {
            return new Error(payload.detail.map((item) => JSON.stringify(item)).join('; '));
        }
    } catch {
        // Keep the raw text below when the server did not return JSON.
    }
    return new Error(text || `Request failed: ${response.status} ${response.statusText}`);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${ADMIN_BASE}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(init?.headers ?? {}),
        },
        ...init,
    });

    if (!response.ok) {
        throw await responseError(response);
    }

    return response.json();
}

export function fetchAdminCustomers(
    params: URLSearchParams,
): Promise<PaginatedResponse<AdminCustomerListItem>> {
    return requestJson(`/crm/customers?${params.toString()}`);
}

export function fetchAdminConversation(
    conversationId: string,
): Promise<AdminConversationDetail> {
    return requestJson(`/crm/conversations/${conversationId}`);
}

export function updateAdminConversation(
    conversationId: string,
    payload: AdminConversationUpdate,
): Promise<AdminConversationDetail> {
    return requestJson(`/crm/conversations/${conversationId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
    });
}

export function previewConversationReset(conversationId: string): Promise<unknown> {
    return requestJson(`/crm/conversations/${conversationId}/reset/preview`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function runBotQualityReview(conversationId: string): Promise<unknown> {
    return requestJson(`/crm/conversations/${conversationId}/quality/bot`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function fetchAdminAudit(
    params: URLSearchParams,
): Promise<PaginatedResponse<AdminActionAuditRead>> {
    return requestJson(`/crm/audit?${params.toString()}`);
}

export function fetchKnowledgeBaseEntries(
    params: URLSearchParams,
): Promise<PaginatedResponse<AdminKnowledgeBaseRead>> {
    return requestJson(`/knowledge-base/entries?${params.toString()}`);
}

export function previewKnowledgeBaseEntry(
    payload: AdminKnowledgeBaseWrite,
): Promise<AdminKnowledgeBasePreview> {
    return requestJson('/knowledge-base/entries/preview', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function createKnowledgeBaseEntry(
    payload: AdminKnowledgeBaseWrite,
): Promise<AdminKnowledgeBaseRead> {
    return requestJson('/knowledge-base/entries', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function updateKnowledgeBaseEntry(
    entryId: string,
    payload: Partial<AdminKnowledgeBaseWrite>,
): Promise<AdminKnowledgeBaseRead> {
    return requestJson(`/knowledge-base/entries/${entryId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
    });
}

export function softDeleteKnowledgeBaseEntry(
    entryId: string,
): Promise<AdminKnowledgeBaseRead> {
    return requestJson(`/knowledge-base/entries/${entryId}`, {
        method: 'DELETE',
    });
}

export function reindexKnowledgeBaseEntry(entryId: string): Promise<AdminKnowledgeBaseRead> {
    return requestJson(`/knowledge-base/entries/${entryId}/reindex`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function fetchKnowledgeBaseCandidates(
    params: URLSearchParams,
): Promise<PaginatedResponse<AdminKnowledgeBaseCandidate>> {
    return requestJson(`/knowledge-base/candidates?${params.toString()}`);
}

export function approveKnowledgeBaseCandidate(
    candidateId: string,
): Promise<AdminKnowledgeBaseRead> {
    return requestJson(`/knowledge-base/candidates/${candidateId}/approve`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function rejectKnowledgeBaseCandidate(
    candidateId: string,
    payload: AdminKnowledgeBaseCandidateReject = {},
): Promise<AdminKnowledgeBaseCandidate> {
    return requestJson(`/knowledge-base/candidates/${candidateId}/reject`, {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function fetchBotRules(
    params: URLSearchParams,
): Promise<PaginatedResponse<AdminBotRuleRead>> {
    return requestJson(`/bot-rules/rules?${params.toString()}`);
}

export function previewBotRules(
    payload: AdminBotRulePreviewRequest,
): Promise<AdminBotRulePreviewResponse> {
    return requestJson('/bot-rules/preview', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function createBotRule(payload: AdminBotRuleWrite): Promise<AdminBotRuleRead> {
    return requestJson('/bot-rules/rules', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function updateBotRule(
    ruleId: string,
    payload: Partial<AdminBotRuleWrite>,
): Promise<AdminBotRuleRead> {
    return requestJson(`/bot-rules/rules/${ruleId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
    });
}

export function archiveBotRule(ruleId: string): Promise<AdminBotRuleRead> {
    return requestJson(`/bot-rules/rules/${ruleId}`, {
        method: 'DELETE',
    });
}

export function reindexBotRule(ruleId: string): Promise<AdminBotRuleRead> {
    return requestJson(`/bot-rules/rules/${ruleId}/reindex`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}
