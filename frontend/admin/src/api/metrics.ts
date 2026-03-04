import type { DashboardMetrics, Period } from '@/types/metrics';

const API_BASE = '/api/v1/admin';

export async function fetchDashboardMetrics(period: Period = 'all_time'): Promise<DashboardMetrics> {
    const res = await fetch(`${API_BASE}/dashboard/metrics/?period=${period}`);
    if (!res.ok) {
        throw new Error(`Failed to fetch metrics: ${res.status} ${res.statusText}`);
    }
    return res.json();
}
