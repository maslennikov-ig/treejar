import type {
    AIQualityControlsResponse,
    AIQualityControlsUpdate,
    ManagerReviewDetail,
    ManagerReviewRead,
    NotificationConfig,
    NotificationTestResponse,
    OperationsReportResponse,
    PaginatedResponse,
    PendingManagerReview,
    ProductSyncResponse,
    ProductSyncSource,
} from '@/types/operators';

const API_BASE = '/api/v1/admin';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(init?.headers ?? {}),
        },
        ...init,
    });

    if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
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
