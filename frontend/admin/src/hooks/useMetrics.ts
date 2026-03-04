import { useCallback, useEffect, useState } from 'react';
import { fetchDashboardMetrics, fetchTimeseries } from '@/api/metrics';
import type { DashboardMetrics, Period, TimeseriesResponse } from '@/types/metrics';

interface UseMetricsResult {
    data: DashboardMetrics | null;
    timeseries: TimeseriesResponse | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useMetrics(period: Period = 'all_time'): UseMetricsResult {
    const [data, setData] = useState<DashboardMetrics | null>(null);
    const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [metricsResult, timeseriesResult] = await Promise.all([
                fetchDashboardMetrics(period),
                fetchTimeseries(period),
            ]);
            setData(metricsResult);
            setTimeseries(timeseriesResult);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }, [period]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return { data, timeseries, loading, error, refetch: fetchData };
}
