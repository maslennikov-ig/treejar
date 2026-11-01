import { redirectOnAdminUnauthorized } from '@/api/sessionGuard';
import type { DashboardMetrics, Period, TimeseriesResponse } from '@/types/metrics';

const API_BASE = '/api/v1/admin';

export async function fetchDashboardMetrics(
    period: Period = 'all_time',
    refresh = false,
): Promise<DashboardMetrics> {
    const suffix = refresh ? '&refresh=true' : '';
    const res = await fetch(`${API_BASE}/dashboard/metrics/?period=${period}${suffix}`);
    if (!res.ok) {
        redirectOnAdminUnauthorized(res);
        throw new Error(`Failed to fetch metrics: ${res.status} ${res.statusText}`);
    }
    return res.json();
}

export async function fetchTimeseries(
    period: Period = 'all_time',
    refresh = false,
): Promise<TimeseriesResponse> {
    const suffix = refresh ? '&refresh=true' : '';
    const res = await fetch(`${API_BASE}/dashboard/timeseries/?period=${period}${suffix}`);
    if (!res.ok) {
        redirectOnAdminUnauthorized(res);
        throw new Error(`Failed to fetch timeseries: ${res.status} ${res.statusText}`);
    }
    return res.json();
}
