import type {
    AIQualityControlsResponse,
    AIQualityControlsUpdate,
    ClientSelfTestSubmitRequest,
    ClientSelfTestSubmitResponse,
    ManagerReviewDetail,
    ManagerReviewRead,
    NotificationConfig,
    NotificationTestResponse,
    OperationsReportResponse,
    PaginatedResponse,
    PendingManagerReview,
    ProductSyncResponse,
    ProductSyncSource,
    RecentFeedbackRead,
    ReferralPolicyResponse,
} from '@/types/operators';

const API_BASE = '/api/v1/admin';
const PUBLIC_CLIENT_SELF_TEST_API_BASE = '/api/v1/client-self-test';

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
    const response = await fetch(`${API_BASE}${path}`, {
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

async function requestAbsoluteJson<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, {
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

function getClientSelfTestApiBase(): string {
    return globalThis.location?.pathname.startsWith('/client-self-test')
        ? PUBLIC_CLIENT_SELF_TEST_API_BASE
        : `${API_BASE}/client-self-test`;
}

export function fetchNotificationConfig(): Promise<NotificationConfig> {
    return requestJson('/notifications/config');
}

export function sendTestNotification(): Promise<NotificationTestResponse> {
    return requestJson('/notifications/test', {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function submitClientSelfTest(
    payload: ClientSelfTestSubmitRequest,
): Promise<ClientSelfTestSubmitResponse> {
    return requestAbsoluteJson(`${getClientSelfTestApiBase()}/submit`, {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export function syncProducts(source: ProductSyncSource = 'treejar'): Promise<ProductSyncResponse> {
    return requestJson('/products/sync', {
        method: 'POST',
        body: JSON.stringify({ source }),
    });
}

export function fetchPendingManagerReviews(limit = 5): Promise<PendingManagerReview[]> {
    return requestJson(`/manager-reviews/pending?limit=${limit}`);
}

export function fetchRecentManagerReviews(pageSize = 5): Promise<PaginatedResponse<ManagerReviewRead>> {
    return requestJson(`/manager-reviews/?page_size=${pageSize}`);
}

export function evaluateManagerReview(escalationId: string): Promise<ManagerReviewDetail> {
    return requestJson(`/manager-reviews/${escalationId}/evaluate`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function generateOperationsReport(): Promise<OperationsReportResponse> {
    return requestJson('/reports/generate', {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export function fetchRecentFeedback(limit = 5): Promise<RecentFeedbackRead[]> {
    return requestJson(`/feedback/recent?limit=${limit}`);
}

export function fetchReferralPolicy(): Promise<ReferralPolicyResponse> {
    return requestJson('/referrals/policy');
}

export function fetchAIQualityControls(): Promise<AIQualityControlsResponse> {
    return requestJson('/ai-quality-controls');
}

export function updateAIQualityControls(
    update: AIQualityControlsUpdate,
): Promise<AIQualityControlsResponse> {
    return requestJson('/ai-quality-controls', {
        method: 'PATCH',
        body: JSON.stringify(update),
    });
}
