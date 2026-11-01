import { useCallback, useEffect, useState } from 'react';
import { fetchDashboardMetrics, fetchTimeseries } from '@/api/metrics';
import { useI18n } from '@/i18n';
import type { DashboardMetrics, Period, TimeseriesResponse } from '@/types/metrics';

interface UseMetricsResult {
    data: DashboardMetrics | null;
    timeseries: TimeseriesResponse | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useMetrics(period: Period = 'all_time', enabled = true): UseMetricsResult {
    const { t } = useI18n();
    const [data, setData] = useState<DashboardMetrics | null>(null);
    const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);
    const [loading, setLoading] = useState(enabled);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(
        async (forceRefresh = false) => {
            setLoading(true);
            setError(null);
            try {
                const [metricsResult, timeseriesResult] = await Promise.all([
                    fetchDashboardMetrics(period, forceRefresh),
                    fetchTimeseries(period, forceRefresh),
                ]);
                setData(metricsResult);
                setTimeseries(timeseriesResult);
            } catch (err) {
                setError(err instanceof Error ? err.message : t('common.unknownError'));
            } finally {
                setLoading(false);
            }
        },
        [period, t],
    );

    useEffect(() => {
        if (!enabled) {
            setLoading(false);
            return;
        }
        void fetchData(false);
    }, [enabled, fetchData]);

    const refetch = useCallback(() => {
        void fetchData(true);
    }, [fetchData]);

    return { data, timeseries, loading, error, refetch };
}
