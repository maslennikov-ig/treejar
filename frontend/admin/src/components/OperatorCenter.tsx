import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    AlertTriangle,
    Bell,
    CheckCircle2,
    ClipboardList,
    Clock,
    FileText,
    Package,
    RefreshCw,
    Send,
    TrendingUp,
} from 'lucide-react';
import {
    evaluateManagerReview,
    fetchNotificationConfig,
    fetchPendingManagerReviews,
    fetchRecentManagerReviews,
    generateOperationsReport,
    sendTestNotification,
    syncProducts,
} from '@/api/operators';
import {
    buildManagerReviewMessage,
    type OperatorActionMessage,
} from '@/components/operatorCenterMessages';
import type {
    ManagerReviewRead,
    NotificationConfig,
    OperationsReportResponse,
    PendingManagerReview,
    ProductSyncSource,
} from '@/types/operators';

interface OperatorCenterProps {
    onMetricsRefresh: () => void | Promise<void>;
}

function formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(new Date(value));
}

function formatDuration(seconds: number | null): string {
    if (seconds === null) {
        return '—';
    }

    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    }

    return `${(seconds / 60).toFixed(1)}m`;
}

function stripHtml(text: string): string {
    return text.replace(/<[^>]+>/g, '').trim();
}

function messageClasses(tone: OperatorActionMessage['tone']): string {
    switch (tone) {
        case 'success':
            return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300';
        case 'error':
            return 'border-red-500/20 bg-red-500/10 text-red-300';
        default:
            return 'border-amber-500/20 bg-amber-500/10 text-amber-200';
    }
}

function ratingClasses(rating: string): string {
    switch (rating) {
        case 'excellent':
            return 'bg-emerald-500/15 text-emerald-300';
        case 'good':
            return 'bg-blue-500/15 text-blue-300';
        case 'satisfactory':
            return 'bg-amber-500/15 text-amber-200';
        default:
            return 'bg-red-500/15 text-red-300';
    }
}

export default function OperatorCenter({ onMetricsRefresh }: OperatorCenterProps) {
    const [notificationConfig, setNotificationConfig] = useState<NotificationConfig | null>(null);
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [report, setReport] = useState<OperationsReportResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [syncingSource, setSyncingSource] = useState<ProductSyncSource | null>(null);
    const [sendingTest, setSendingTest] = useState(false);
    const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
    const [generatingReport, setGeneratingReport] = useState(false);
    const [syncMessage, setSyncMessage] = useState<OperatorActionMessage | null>(null);
    const [notificationMessage, setNotificationMessage] = useState<OperatorActionMessage | null>(null);
    const [reviewMessage, setReviewMessage] = useState<OperatorActionMessage | null>(null);
    const [reportMessage, setReportMessage] = useState<OperatorActionMessage | null>(null);

    const loadOperatorData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [configResult, pendingResult, recentResult, reportResult] = await Promise.all([
                fetchNotificationConfig(),
                fetchPendingManagerReviews(),
                fetchRecentManagerReviews(),
                generateOperationsReport(),
            ]);

            setNotificationConfig(configResult);
            setPendingReviews(pendingResult);
            setRecentReviews(recentResult.items);
            setReport(reportResult);
            return null;
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to load operator controls.';
            setError(message);
            return message;
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadOperatorData();
    }, [loadOperatorData]);

    async function handleSync(source: ProductSyncSource): Promise<void> {
        setSyncingSource(source);
        setSyncMessage(null);
        try {
            const result = await syncProducts(source);
            setSyncMessage({
                tone: 'success',
                text: `${source === 'treejar' ? 'Treejar' : 'Zoho'} sync queued. Errors: ${result.errors}.`,
            });
        } catch (err) {
            setSyncMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : 'Failed to queue product sync.',
            });
        } finally {
            setSyncingSource(null);
        }
    }

    async function handleSendTestNotification(): Promise<void> {
        setSendingTest(true);
        setNotificationMessage(null);
        try {
            const result = await sendTestNotification();
            setNotificationMessage({
                tone: result.status === 'sent' ? 'success' : 'info',
                text: result.status === 'sent'
                    ? 'Telegram test message sent.'
                    : result.reason ?? 'Telegram integration is not configured.',
            });
        } catch (err) {
            setNotificationMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : 'Failed to send test notification.',
            });
        } finally {
            setSendingTest(false);
        }
    }

    async function handleEvaluateReview(item: PendingManagerReview): Promise<void> {
        setEvaluatingId(item.escalation_id);
        setReviewMessage(null);
        try {
            const detail = await evaluateManagerReview(item.escalation_id);
            setReviewMessage(buildManagerReviewMessage(item.manager_name, detail, null));
            const refreshError = await loadOperatorData();
            if (refreshError) {
                setReviewMessage(
                    buildManagerReviewMessage(item.manager_name, detail, refreshError),
                );
            }
            void onMetricsRefresh();
        } catch (err) {
            setReviewMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : 'Failed to evaluate manager review.',
            });
        } finally {
            setEvaluatingId(null);
        }
    }

    async function handleGenerateReport(): Promise<void> {
        setGeneratingReport(true);
        setReportMessage(null);
        try {
            const reportResult = await generateOperationsReport();
            setReport(reportResult);
            setReportMessage({
                tone: 'success',
                text: 'Weekly operations report refreshed.',
            });
        } catch (err) {
            setReportMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : 'Failed to generate report.',
            });
        } finally {
            setGeneratingReport(false);
        }
    }

    return (
        <motion.section
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.2 }}
            className="rounded-3xl border border-white/[0.08] bg-slate-950/70 p-6 backdrop-blur-xl"
        >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-emerald-300">
                        <ClipboardList size={14} />
                        Operator Center
                    </div>
                    <h2 className="mt-3 text-xl font-semibold text-white">Actionable admin surface</h2>
                    <p className="mt-2 max-w-3xl text-sm text-slate-400">
                        Shared-session controls for catalog sync, Telegram health, manager evaluation,
                        and weekly conversion reporting. This is the operator layer from the admin spec,
                        not raw internal API plumbing.
                    </p>
                </div>

                <button
                    onClick={() => void loadOperatorData()}
                    disabled={loading}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    Refresh
                </button>
            </div>

            {error && (
                <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                    <AlertTriangle size={16} className="mr-2 inline" />
                    {error}
                </div>
            )}

            <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <Package size={18} className="text-emerald-300" />
                                <h3 className="text-lg font-semibold">Catalog Sync</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                Treejar remains the catalog source of truth. Zoho sync stays available as a legacy operational path.
                            </p>
                        </div>
                        <div className="rounded-xl bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300">
                            Admin session only
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <button
                            onClick={() => void handleSync('treejar')}
                            disabled={syncingSource !== null}
                            className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-left text-sm text-emerald-200 transition hover:bg-emerald-500/15 disabled:opacity-50"
                        >
                            <p className="font-medium">Run Treejar Sync</p>
                            <p className="mt-1 text-xs text-emerald-200/80">Recommended canonical catalog refresh</p>
                        </button>
                        <button
                            onClick={() => void handleSync('zoho')}
                            disabled={syncingSource !== null}
                            className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-white/[0.05] disabled:opacity-50"
                        >
                            <p className="font-medium">Run Zoho Sync</p>
                            <p className="mt-1 text-xs text-slate-400">Legacy stock and operational mirror path</p>
                        </button>
                    </div>

                    {syncMessage && (
                        <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${messageClasses(syncMessage.tone)}`}>
                            {syncMessage.text}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <Bell size={18} className="text-blue-300" />
                                <h3 className="text-lg font-semibold">Telegram Notifications</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                Quick configuration health and test send without leaving the dashboard.
                            </p>
                        </div>
                        <div className={`rounded-xl px-3 py-2 text-xs font-medium ${notificationConfig?.telegram_configured ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-200'}`}>
                            {notificationConfig?.telegram_configured ? 'Configured' : 'Not configured'}
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Bot token</p>
                            <p className="mt-2 text-sm font-medium text-white">{notificationConfig?.telegram_bot_token ?? 'Loading...'}</p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Chat ID</p>
                            <p className="mt-2 text-sm font-medium text-white">{notificationConfig?.telegram_chat_id ?? 'Loading...'}</p>
                        </div>
                    </div>

                    <button
                        onClick={() => void handleSendTestNotification()}
                        disabled={sendingTest}
                        className="mt-4 inline-flex items-center gap-2 rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-2.5 text-sm font-medium text-blue-200 transition hover:bg-blue-500/15 disabled:opacity-50"
                    >
                        {sendingTest ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
                        Send test message
                    </button>

                    {notificationMessage && (
                        <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${messageClasses(notificationMessage.tone)}`}>
                            {notificationMessage.text}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5 xl:col-span-2">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <FileText size={18} className="text-violet-300" />
                                <h3 className="text-lg font-semibold">Weekly Operations Report</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                Refusal, conversion, quality, and manager-performance summary aligned with the stage-2 reporting scope.
                            </p>
                        </div>
                        <button
                            onClick={() => void handleGenerateReport()}
                            disabled={generatingReport}
                            className="inline-flex items-center gap-2 rounded-xl border border-violet-500/20 bg-violet-500/10 px-4 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/15 disabled:opacity-50"
                        >
                            {generatingReport ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                            Refresh 7-day report
                        </button>
                    </div>

                    {report && (
                        <>
                            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Dialogues</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.total_conversations}</p>
                                    <p className="mt-1 text-xs text-slate-400">{report.data.conversations_per_day} per day</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Conversion</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.conversion_rate}%</p>
                                    <p className="mt-1 text-xs text-slate-400">{report.data.total_deals} deals</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Escalations</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.escalation_count}</p>
                                    <p className="mt-1 text-xs text-slate-400">{Object.keys(report.data.escalation_reasons).length} tracked reasons</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Manager Reviews</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.manager_reviews_count}</p>
                                    <p className="mt-1 text-xs text-slate-400">{report.data.manager_deal_conversion_rate}% deal conversion</p>
                                </div>
                            </div>

                            <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                                <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-medium text-white">Telegram Preview</p>
                                            <p className="mt-1 text-xs text-slate-500">
                                                {formatDateTime(report.data.period_start)} to {formatDateTime(report.data.period_end)}
                                            </p>
                                        </div>
                                        <div className="rounded-xl bg-white/[0.05] px-3 py-2 text-xs font-medium text-slate-300">
                                            Average quality {report.data.avg_quality_score}/30
                                        </div>
                                    </div>
                                    <pre className="mt-4 whitespace-pre-wrap rounded-xl border border-white/[0.06] bg-black/20 p-4 text-sm leading-6 text-slate-200">
                                        {stripHtml(report.text)}
                                    </pre>
                                </div>

                                <div className="space-y-4">
                                    <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                        <div className="flex items-center gap-2 text-white">
                                            <TrendingUp size={16} className="text-emerald-300" />
                                            <p className="text-sm font-medium">Top Products Mentioned</p>
                                        </div>
                                        <div className="mt-3 space-y-3">
                                            {report.data.top_products.length > 0 ? report.data.top_products.map((product) => (
                                                <div key={product.sku} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                    <p className="text-sm font-medium text-white">{product.name}</p>
                                                    <p className="mt-1 text-xs text-slate-400">{product.sku} · {product.mentions} mentions</p>
                                                </div>
                                            )) : (
                                                <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-sm text-slate-500">
                                                    No assistant SKU mentions in the selected weekly window.
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                        <div className="flex items-center gap-2 text-white">
                                            <Clock size={16} className="text-amber-200" />
                                            <p className="text-sm font-medium">Manager Performance Snapshot</p>
                                        </div>
                                        <div className="mt-3 grid grid-cols-2 gap-3">
                                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Avg score</p>
                                                <p className="mt-2 text-xl font-semibold text-white">{report.data.avg_manager_score}/20</p>
                                            </div>
                                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Response</p>
                                                <p className="mt-2 text-xl font-semibold text-white">{formatDuration(report.data.avg_manager_response_time_seconds)}</p>
                                            </div>
                                        </div>
                                        <div className="mt-3 space-y-2">
                                            {report.data.top_managers.length > 0 ? report.data.top_managers.map((manager) => (
                                                <div key={manager.name} className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                    <p className="text-sm font-medium text-white">{manager.name}</p>
                                                    <p className="text-sm text-violet-300">{manager.avg_score}/20</p>
                                                </div>
                                            )) : (
                                                <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-sm text-slate-500">
                                                    Manager rankings will appear after resolved escalations are reviewed.
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}

                    {reportMessage && (
                        <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${messageClasses(reportMessage.tone)}`}>
                            {reportMessage.text}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5 xl:col-span-2">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <CheckCircle2 size={18} className="text-amber-200" />
                                <h3 className="text-lg font-semibold">Manager Review Queue</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                Pending resolved escalations waiting for evaluation, plus the latest completed manager reviews.
                            </p>
                        </div>
                        <div className="rounded-xl bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200">
                            {pendingReviews.length} pending
                        </div>
                    </div>

                    <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                        <div className="space-y-3">
                            {pendingReviews.length > 0 ? pendingReviews.map((item) => (
                                <div key={item.escalation_id} className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-white">{item.manager_name ?? 'Unassigned manager'}</p>
                                            <p className="mt-1 text-sm text-slate-300">{item.phone}</p>
                                            <p className="mt-2 text-sm text-slate-400">{item.reason}</p>
                                            <p className="mt-2 text-xs text-slate-500">Updated {formatDateTime(item.updated_at)}</p>
                                        </div>
                                        <button
                                            onClick={() => void handleEvaluateReview(item)}
                                            disabled={evaluatingId !== null}
                                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:bg-amber-500/15 disabled:opacity-50"
                                        >
                                            {evaluatingId === item.escalation_id ? <RefreshCw size={16} className="animate-spin" /> : <ClipboardList size={16} />}
                                            Evaluate
                                        </button>
                                    </div>
                                </div>
                            )) : (
                                <div className="rounded-2xl border border-dashed border-white/[0.08] px-4 py-8 text-sm text-slate-500">
                                    No resolved escalations are waiting for manual manager evaluation.
                                </div>
                            )}
                        </div>

                        <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-sm font-medium text-white">Recent Reviews</p>
                                    <p className="mt-1 text-xs text-slate-500">Latest completed manager evaluations</p>
                                </div>
                                <div className="rounded-xl bg-white/[0.05] px-3 py-2 text-xs font-medium text-slate-300">
                                    {recentReviews.length} shown
                                </div>
                            </div>

                            <div className="mt-4 space-y-3">
                                {recentReviews.length > 0 ? recentReviews.map((review) => (
                                    <div key={review.id} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-medium text-white">{review.manager_name ?? 'Unknown manager'}</p>
                                                <p className="mt-1 text-xs text-slate-500">{formatDateTime(review.created_at)}</p>
                                            </div>
                                            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${ratingClasses(review.rating)}`}>
                                                {review.rating}
                                            </span>
                                        </div>
                                        <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-slate-300">
                                            <div>
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Score</p>
                                                <p className="mt-1 font-medium text-white">{review.total_score}/{review.max_score}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Response time</p>
                                                <p className="mt-1 font-medium text-white">{formatDuration(review.first_response_time_seconds)}</p>
                                            </div>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-sm text-slate-500">
                                        Recent manager reviews will appear here after the first evaluation run.
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {reviewMessage && (
                        <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${messageClasses(reviewMessage.tone)}`}>
                            {reviewMessage.text}
                        </div>
                    )}
                </div>
            </div>
        </motion.section>
    );
}
