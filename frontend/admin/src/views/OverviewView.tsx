import { useEffect, useState } from 'react';
import {
    AlertTriangle,
    ArrowUpRight,
    CheckCircle2,
    MessageCircle,
    Package,
    RefreshCw,
    ShieldAlert,
    Star,
    TrendingUp,
    Zap,
} from 'lucide-react';
import ConversationsChart from '@/components/charts/ConversationsChart';
import EscalationReasonsChart from '@/components/charts/EscalationReasonsChart';
import FunnelEfficiencyChart from '@/components/charts/FunnelEfficiencyChart';
import SalesBarChart from '@/components/charts/SalesBarChart';
import SegmentPieChart from '@/components/charts/SegmentPieChart';
import { HelpTooltip, SectionInfoBanner } from '@/components/HelpTooltip';
import { Badge } from '@/components/ui/Primitives';
import { fetchCatalogStatus } from '@/api/crm';
import { fetchPendingManagerReviews } from '@/api/operators';
import type { AdminCatalogStatusResponse } from '@/types/crm';
import type { DashboardMetrics, Period, TimeseriesResponse } from '@/types/metrics';
import type { AdminRouteState } from '@/hooks/useAdminRouter';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';

export interface OverviewViewProps {
    period: Period;
    onPeriodChange: (period: Period) => void;
    data: DashboardMetrics | null;
    timeseries: TimeseriesResponse | null;
    loading: boolean;
    error: string | null;
    onNavigate: (next: Partial<AdminRouteState> & { view: AdminRouteState['view'] }) => void;
    onRefresh: () => void;
    refreshSignal?: number;
}

function computeSeriesDeltaPct(points: TimeseriesResponse['points']): number | null {
    if (!points || points.length < 4) {
        return null;
    }
    const half = Math.floor(points.length / 2);
    const prevSlice = points.slice(0, half);
    const currSlice = points.slice(half);
    const prevSum = prevSlice.reduce((sum, p) => sum + (p.new || 0) + (p.returning || 0), 0);
    const currSum = currSlice.reduce((sum, p) => sum + (p.new || 0) + (p.returning || 0), 0);
    if (prevSum === 0) {
        return currSum > 0 ? 100 : 0;
    }
    return ((currSum - prevSum) / prevSum) * 100;
}

export default function OverviewView({
    period,
    data,
    timeseries,
    loading,
    error,
    onNavigate,
    onRefresh,
    refreshSignal = 0,
}: OverviewViewProps) {
    const { t, formatNumber } = useI18n();
    const [pendingReviewsCount, setPendingReviewsCount] = useState<number>(0);
    const [catalogStatus, setCatalogStatus] = useState<AdminCatalogStatusResponse | null>(null);

    useEffect(() => {
        fetchPendingManagerReviews(20)
            .then((items) => setPendingReviewsCount(items.length))
            .catch(() => setPendingReviewsCount(0));
        fetchCatalogStatus()
            .then((status) => setCatalogStatus(status))
            .catch(() => setCatalogStatus(null));
    }, [period, refreshSignal]);

    const volumeDelta = computeSeriesDeltaPct(timeseries?.points ?? []);
    const escalationRate =
        data && data.total_conversations > 0
            ? (data.escalation_count / data.total_conversations) * 100
            : 0;
    const zohoState = catalogStatus?.zoho_snapshot?.status ?? 'missing';

    return (
        <div className="space-y-3" data-overview-bento>
            <SectionInfoBanner
                storageKey="overview"
                title={t('banner.overview.title')}
                description={t('banner.overview.body')}
                runtime={t('banner.overview.runtime')}
                defaultCollapsed
                actions={
                    <button
                        type="button"
                        onClick={onRefresh}
                        aria-label={t('common.refresh')}
                        className="admin-subpanel inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                        {t('common.refresh')}
                    </button>
                }
            />

            {/* Variant 5A: Top compact attention strip */}
            <div
                data-overview-attention-bar
                className="admin-panel flex flex-wrap items-center justify-between gap-2 rounded-xl px-3.5 py-2.5 shadow-2xs"
            >
                <div className="flex items-center gap-2 text-xs font-bold text-slate-900 dark:text-slate-100">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400">
                        <Zap className="h-3.5 w-3.5" />
                    </span>
                    <span>{t('overview.attention.title')}</span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <button
                        type="button"
                        onClick={() =>
                            onNavigate({ view: 'queuesQuality', tab: 'escalations' })
                        }
                        className="admin-subpanel inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:border-amber-400"
                    >
                        <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
                        <span>{t('overview.attention.escalations')}</span>
                        <Badge tone={(data?.escalation_count ?? 0) > 0 ? 'amber' : 'slate'}>
                            {data?.escalation_count ?? 0}
                        </Badge>
                    </button>

                    <button
                        type="button"
                        onClick={() =>
                            onNavigate({ view: 'queuesQuality', tab: 'managerReviews' })
                        }
                        className="admin-subpanel inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:border-blue-400"
                    >
                        <Star className="h-3.5 w-3.5 text-blue-500" />
                        <span>{t('overview.attention.pendingReviews')}</span>
                        <Badge tone={pendingReviewsCount > 0 ? 'blue' : 'slate'}>
                            {pendingReviewsCount}
                        </Badge>
                    </button>

                    <button
                        type="button"
                        onClick={() => onNavigate({ view: 'catalog' })}
                        className="admin-subpanel inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:border-emerald-400"
                    >
                        <Package className="h-3.5 w-3.5 text-emerald-500" />
                        <span>{t('overview.attention.zohoStock')}</span>
                        <Badge
                            tone={
                                zohoState === 'fresh'
                                    ? 'emerald'
                                    : zohoState === 'stale'
                                      ? 'amber'
                                      : 'slate'
                            }
                        >
                            {t(`catalog.zohoStatus.${zohoState}` as TranslationKey)}
                        </Badge>
                    </button>
                </div>
            </div>

            {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
                    {error}
                </div>
            )}

            {data && (
                <>
                    {/* 4 KPI cards with period deltas */}
                    <div
                        data-overview-kpi-row
                        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
                    >
                        <KpiCard
                            title={t('metric.totalConversations')}
                            value={formatNumber(data.total_conversations)}
                            subtitle={t('metric.customersCount', {
                                count: formatNumber(data.unique_customers),
                            })}
                            delta={
                                volumeDelta !== null
                                    ? `${volumeDelta >= 0 ? '+' : ''}${formatNumber(volumeDelta, 1)}%`
                                    : t(`period.${period}` as TranslationKey)
                            }
                            deltaTone={
                                volumeDelta === null
                                    ? 'slate'
                                    : volumeDelta >= 0
                                      ? 'emerald'
                                      : 'amber'
                            }
                            tooltip={t('metric.totalConversations.help')}
                            icon={<MessageCircle className="h-4 w-4 text-blue-500" />}
                            onClick={() => onNavigate({ view: 'conversations' })}
                        />
                        <KpiCard
                            title={t('metric.conversionRate')}
                            value={`${formatNumber(data.conversion_rate, 1)}%`}
                            subtitle={t('metric.noorAndPostSales', {
                                noor: data.noor_sales.count,
                                post: data.post_escalation_sales.count,
                            })}
                            delta={`${formatNumber(data.noor_sales.count + data.post_escalation_sales.count)} ${t('overview.kpi.dealsUnit')}`}
                            deltaTone={data.conversion_rate > 0 ? 'emerald' : 'slate'}
                            tooltip={t('metric.conversionRate.help')}
                            icon={<TrendingUp className="h-4 w-4 text-emerald-500" />}
                            onClick={() =>
                                onNavigate({ view: 'conversations', filter: 'deals' })
                            }
                        />
                        <KpiCard
                            title={t('metric.escalations')}
                            value={formatNumber(data.escalation_count)}
                            subtitle={t('metric.managerScore', {
                                score: formatNumber(data.avg_manager_score, 1),
                            })}
                            delta={`${formatNumber(escalationRate, 1)}% ${t('overview.kpi.ofTotal')}`}
                            deltaTone={data.escalation_count > 0 ? 'amber' : 'emerald'}
                            tooltip={t('metric.escalations.help')}
                            icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
                            onClick={() =>
                                onNavigate({ view: 'queuesQuality', tab: 'escalations' })
                            }
                        />
                        <KpiCard
                            title={t('metric.noorQuality')}
                            value={`${formatNumber(data.avg_quality_score, 1)}/30`}
                            subtitle={t('metric.responseSec', {
                                sec: formatNumber(
                                    (data.avg_response_time_ms || 0) / 1000,
                                    1,
                                ),
                            })}
                            delta={`$${(data.llm_cost_usd ?? 0).toFixed(2)} AI`}
                            deltaTone={data.avg_quality_score >= 22 ? 'emerald' : 'blue'}
                            tooltip={t('metric.noorQuality.help')}
                            icon={<CheckCircle2 className="h-4 w-4 text-indigo-500" />}
                            onClick={() =>
                                onNavigate({ view: 'queuesQuality', tab: 'reviews' })
                            }
                        />
                    </div>

                    {/* Variant 5A: Matched-Height Bento Grid (7fr Left / 5fr Right, zero dead whitespace) */}
                    <div
                        data-overview-bento-grid
                        className="grid grid-cols-1 items-stretch gap-3 lg:grid-cols-12"
                    >
                        <div
                            data-bento-col="left"
                            className="flex flex-col gap-3 lg:col-span-7"
                        >
                            {timeseries && (
                                <div className="flex-1">
                                    <ConversationsChart points={timeseries.points} />
                                </div>
                            )}
                            <div className="flex-1">
                                <FunnelEfficiencyChart
                                    data={data}
                                    onSelectStage={(stage) =>
                                        onNavigate({ view: 'conversations', stage })
                                    }
                                />
                            </div>
                        </div>

                        <div
                            data-bento-col="right"
                            className="flex flex-col gap-3 lg:col-span-5"
                        >
                            <div className="flex-1">
                                <SegmentPieChart
                                    byLanguage={data.by_language}
                                    targetVsNontarget={data.target_vs_nontarget}
                                    onSelectFilter={(filter) =>
                                        onNavigate({
                                            view: 'conversations',
                                            ...filter,
                                        })
                                    }
                                />
                            </div>
                            <div className="flex-1">
                                <SalesBarChart
                                    noorSales={data.noor_sales}
                                    postEscalationSales={data.post_escalation_sales}
                                    escalationCount={data.escalation_count}
                                    conversionRate={data.conversion_rate}
                                    onSelectBar={(filter) =>
                                        onNavigate({
                                            view: 'conversations',
                                            ...filter,
                                        })
                                    }
                                />
                            </div>
                            <div className="flex-1">
                                <EscalationReasonsChart
                                    byReason={data.escalation_by_reason}
                                    rawReasons={data.escalation_reasons}
                                    onSelectReason={() =>
                                        onNavigate({
                                            view: 'conversations',
                                            escalation: 'any',
                                        })
                                    }
                                />
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

function KpiCard({
    title,
    value,
    subtitle,
    delta,
    deltaTone = 'slate',
    tooltip,
    icon,
    onClick,
}: {
    title: string;
    value: string;
    subtitle: string;
    delta: string;
    deltaTone?: 'slate' | 'blue' | 'emerald' | 'amber';
    tooltip?: string;
    icon: React.ReactNode;
    onClick?: () => void;
}) {
    return (
        <div
            onClick={onClick}
            className={`admin-panel flex flex-col justify-between rounded-xl p-4 shadow-2xs transition-colors ${
                onClick ? 'cursor-pointer hover:border-blue-400' : ''
            }`}
        >
            <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-400">
                    <span>{title}</span>
                    {tooltip && <HelpTooltip text={tooltip} />}
                </div>
                <div className="flex items-center gap-1.5">
                    <Badge tone={deltaTone}>{delta}</Badge>
                    {icon}
                </div>
            </div>
            <div className="mt-2 flex items-baseline justify-between gap-2">
                <div className="text-2xl font-bold text-slate-950 dark:text-slate-50">
                    {value}
                </div>
                {onClick && (
                    <ArrowUpRight className="h-3.5 w-3.5 text-slate-400" />
                )}
            </div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{subtitle}</div>
        </div>
    );
}
