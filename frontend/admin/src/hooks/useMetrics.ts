import { useCallback, useEffect, useState } from 'react';
import { fetchDashboardMetrics } from '@/api/metrics';
import type { DashboardMetrics, Period } from '@/types/metrics';

interface UseMetricsResult {
    data: DashboardMetrics | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useMetrics(period: Period = 'all_time'): UseMetricsResult {
    const [data, setData] = useState<DashboardMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchDashboardMetrics(period);
            setData(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [period]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return { data, loading, error, refetch: fetchData };
}
