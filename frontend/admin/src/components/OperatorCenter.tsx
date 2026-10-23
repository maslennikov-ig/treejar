import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    AlertTriangle,
    Bell,
    BookOpen,
    CheckCircle2,
    ClipboardList,
    Clock,
    FileText,
    MessageCircle,
    Package,
    RefreshCw,
    Send,
    Share2,
    TrendingUp,
} from 'lucide-react';
import {
    evaluateManagerReview,
    fetchAIQualityControls,
    fetchNotificationConfig,
    fetchPendingManagerReviews,
    fetchRecentManagerReviews,
    fetchRecentFeedback,
    fetchReferralPolicy,
    generateOperationsReport,
    sendTestNotification,
    syncProducts,
} from '@/api/operators';
import AIQualityControlsPanel from '@/components/AIQualityControlsPanel';
import CanonicalSyncButton from '@/components/CanonicalSyncButton';
import EnableManualModeButton from '@/components/EnableManualModeButton';
import { HelpTooltip } from '@/components/HelpTooltip';
import {
    buildManagerReviewMessage,
    type OperatorActionMessage,
} from '@/components/operatorCenterMessages';
import { useI18n } from '@/i18n';
import type {
    AIQualityControlsConfig,
    ManagerReviewRead,
    NotificationConfig,
    OperationsReportResponse,
    PendingManagerReview,
    ProductSyncSource,
    RecentFeedbackRead,
    ReferralPolicyResponse,
} from '@/types/operators';

interface OperatorCenterProps {
    onMetricsRefresh: () => void | Promise<void>;
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
    const { t, label, formatDateTime, formatDuration } = useI18n();
    const [notificationConfig, setNotificationConfig] = useState<NotificationConfig | null>(null);
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [recentFeedback, setRecentFeedback] = useState<RecentFeedbackRead[]>([]);
    const [referralPolicy, setReferralPolicy] = useState<ReferralPolicyResponse | null>(null);
    const [report, setReport] = useState<OperationsReportResponse | null>(null);
    const [qualityConfig, setQualityConfig] = useState<AIQualityControlsConfig | null>(null);
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

    const loadOperatorData = useCallback(async (isCurrent: () => boolean = () => true) => {
        setLoading(true);
        setError(null);
        fetchAIQualityControls()
            .then((response) => {
                if (isCurrent()) setQualityConfig(response.config);
            })
            .catch(() => {
                if (isCurrent()) setQualityConfig(null);
            });
        try {
            const [
                configResult,
                pendingResult,
                recentResult,
                reportResult,
                feedbackResult,
                referralPolicyResult,
            ] = await Promise.all([
                fetchNotificationConfig(),
                fetchPendingManagerReviews(),
                fetchRecentManagerReviews(),
                generateOperationsReport(),
                fetchRecentFeedback(),
                fetchReferralPolicy(),
            ]);

            if (!isCurrent()) {
                return null;
            }
            setNotificationConfig(configResult);
            setPendingReviews(pendingResult);
            setRecentReviews(recentResult.items);
            setReport(reportResult);
            setRecentFeedback(feedbackResult);
            setReferralPolicy(referralPolicyResult);
            return null;
        } catch (err) {
            const message = err instanceof Error ? err.message : t('op.loadFailed');
            if (!isCurrent()) {
                return null;
            }
            setError(message);
            return message;
        } finally {
            if (isCurrent()) {
                setLoading(false);
            }
        }
    }, [t]);

    useEffect(() => {
        let ignore = false;
        void loadOperatorData(() => !ignore);
        return () => {
            ignore = true;
        };
    }, [loadOperatorData]);

    async function handleSync(source: ProductSyncSource): Promise<void> {
        setSyncingSource(source);
        setSyncMessage(null);
        try {
            const result = await syncProducts(source);
            setSyncMessage({
                tone: 'success',
                text: t('op.syncQueued', { source: source === 'treejar' ? 'Treejar' : 'Zoho', errors: result.errors }),
            });
        } catch (err) {
            setSyncMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('op.syncFailed'),
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
                    ? t('op.testSent')
                    : result.reason ?? t('settings.telegramNotConfigured'),
            });
        } catch (err) {
            setNotificationMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('op.testFailed'),
            });
        } finally {
            setSendingTest(false);
        }
    }

    async function handleEvaluateReview(item: PendingManagerReview): Promise<void> {
        setEvaluatingId(item.escalation_id);
        setReviewMessage(null);
        const texts = {
            managerFallback: t('op.managerFallback'),
            scored: (name: string, score: number, max: number) => t('op.scored', { name, score, max }),
            refreshFailed: t('op.refreshFailed'),
        };
        try {
            const detail = await evaluateManagerReview(item.escalation_id);
            setReviewMessage(buildManagerReviewMessage(item.manager_name, detail, null, texts));
            const refreshError = await loadOperatorData();
            if (refreshError) {
                setReviewMessage(
                    buildManagerReviewMessage(item.manager_name, detail, refreshError, texts),
                );
            }
            void onMetricsRefresh();
        } catch (err) {
            setReviewMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('op.evaluateFailed'),
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
                text: t('op.reportRefreshed'),
            });
        } catch (err) {
            setReportMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('op.reportFailed'),
            });
        } finally {
            setGeneratingReport(false);
        }
    }

    const loadingText = t('common.loading');

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
                        {t('op.badge')}
                    </div>
                    <h2 className="mt-3 text-xl font-semibold text-white">{t('op.title')}</h2>
                    <p className="mt-2 max-w-3xl text-sm text-slate-400">
                        {t('op.subtitle')}
                    </p>
                </div>

                <button
                    type="button"
                    onClick={() => void loadOperatorData()}
                    disabled={loading}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    {t('common.refresh')}
                </button>
            </div>

            {error && (
                <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                    <AlertTriangle size={16} className="mr-2 inline" />
                    {error}
                </div>
            )}

            {qualityConfig && (
                <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 sm:flex-row sm:items-center sm:justify-between">
                    <span>{t('op.qualityHint')}</span>
                    <EnableManualModeButton
                        config={qualityConfig}
                        tone="dark"
                        onDone={(response) => setQualityConfig(response.config)}
                    />
                </div>
            )}

            <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
                <AIQualityControlsPanel />

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-center gap-2 text-white">
                        <BookOpen size={18} className="text-emerald-300" />
                        <h3 className="text-lg font-semibold">{t('op.canonicalTitle')}</h3>
                        <HelpTooltip text={t('op.canonicalHelp')} tone="dark" />
                    </div>
                    <p className="mt-2 text-sm text-slate-400">{t('op.canonicalSubtitle')}</p>
                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-500">{t('nav.knowledge')}</p>
                            <CanonicalSyncButton kind="knowledge" tone="dark" />
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="mb-2 text-xs uppercase tracking-[0.2em] text-slate-500">{t('nav.botRules')}</p>
                            <CanonicalSyncButton kind="botRules" tone="dark" />
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <Package size={18} className="text-emerald-300" />
                                <h3 className="text-lg font-semibold">{t('op.catalogTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.catalogSubtitle')}
                            </p>
                        </div>
                        <div className="rounded-xl bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300">
                            {t('op.adminOnly')}
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <button
                            type="button"
                            onClick={() => void handleSync('treejar')}
                            disabled={syncingSource !== null}
                            className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-left text-sm text-emerald-200 transition hover:bg-emerald-500/15 disabled:opacity-50"
                        >
                            <p className="font-medium">{t('op.runTreejarSync')}</p>
                            <p className="mt-1 text-xs text-emerald-200/80">{t('op.runTreejarSyncNote')}</p>
                        </button>
                        <button
                            type="button"
                            onClick={() => void handleSync('zoho')}
                            disabled={syncingSource !== null}
                            className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-white/[0.05] disabled:opacity-50"
                        >
                            <p className="font-medium">{t('op.runZohoSync')}</p>
                            <p className="mt-1 text-xs text-slate-400">{t('op.runZohoSyncNote')}</p>
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
                                <h3 className="text-lg font-semibold">{t('op.telegramTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.telegramSubtitle')}
                            </p>
                        </div>
                        <div className={`rounded-xl px-3 py-2 text-xs font-medium ${notificationConfig?.telegram_configured ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-200'}`}>
                            {notificationConfig?.telegram_configured ? t('settings.configured') : t('settings.notConfigured')}
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('settings.botToken')}</p>
                            <p className="mt-2 text-sm font-medium text-white">{notificationConfig?.telegram_bot_token ?? loadingText}</p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('settings.chatId')}</p>
                            <p className="mt-2 text-sm font-medium text-white">{notificationConfig?.telegram_chat_id ?? loadingText}</p>
                        </div>
                    </div>

                    <button
                        type="button"
                        onClick={() => void handleSendTestNotification()}
                        disabled={sendingTest}
                        className="mt-4 inline-flex items-center gap-2 rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-2.5 text-sm font-medium text-blue-200 transition hover:bg-blue-500/15 disabled:opacity-50"
                    >
                        {sendingTest ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
                        {t('op.sendTestMessage')}
                    </button>

                    {notificationMessage && (
                        <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${messageClasses(notificationMessage.tone)}`}>
                            {notificationMessage.text}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <MessageCircle size={18} className="text-emerald-300" />
                                <h3 className="text-lg font-semibold">{t('op.feedbackTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.feedbackSubtitle')}
                            </p>
                        </div>
                        <div className="rounded-xl bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300">
                            {t('op.shown', { count: recentFeedback.length })}
                        </div>
                    </div>

                    <div className="mt-4 space-y-3">
                        {recentFeedback.length > 0 ? recentFeedback.map((item) => (
                            <div key={item.conversation_id} className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="text-sm font-medium text-white">{item.customer_name ?? item.phone}</p>
                                        <p className="mt-1 text-xs text-slate-500">{formatDateTime(item.created_at)}</p>
                                    </div>
                                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${item.recommend ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-200'}`}>
                                        {item.recommend ? t('op.recommends') : t('op.needsFollowUp')}
                                    </span>
                                </div>
                                <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-slate-300">
                                    <div>
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('op.overall')}</p>
                                        <p className="mt-1 font-medium text-white">{item.rating_overall}/5</p>
                                    </div>
                                    <div>
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('op.delivery')}</p>
                                        <p className="mt-1 font-medium text-white">{item.rating_delivery}/5</p>
                                    </div>
                                </div>
                                {item.comment && (
                                    <p className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-slate-300">
                                        {item.comment}
                                    </p>
                                )}
                            </div>
                        )) : (
                            <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-8 text-sm text-slate-500">
                                {t('op.feedbackEmpty')}
                            </div>
                        )}
                    </div>
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <Share2 size={18} className="text-amber-200" />
                                <h3 className="text-lg font-semibold">{t('op.referralTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.referralSubtitle')}
                            </p>
                        </div>
                        <div className={`rounded-xl px-3 py-2 text-xs font-medium ${referralPolicy?.allows_launch ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-200'}`}>
                            {referralPolicy?.allows_launch ? t('op.approved') : t('op.clientDecision')}
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('common.status')}</p>
                            <p className="mt-2 text-sm font-medium text-white">
                                {referralPolicy ? label(referralPolicy.config.status) : loadingText}
                            </p>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-3">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('op.confirmation')}</p>
                            <p className="mt-2 text-sm font-medium text-white">
                                {referralPolicy?.config.confirmation_required ? t('op.required') : t('op.notRequired')}
                            </p>
                        </div>
                    </div>

                    <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                        {referralPolicy?.message ?? t('op.referralLoading')}
                    </div>
                </div>

                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5 xl:col-span-2">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                            <div className="flex items-center gap-2 text-white">
                                <FileText size={18} className="text-violet-300" />
                                <h3 className="text-lg font-semibold">{t('op.reportTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.reportSubtitle')}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() => void handleGenerateReport()}
                            disabled={generatingReport}
                            className="inline-flex items-center gap-2 rounded-xl border border-violet-500/20 bg-violet-500/10 px-4 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/15 disabled:opacity-50"
                        >
                            <RefreshCw size={16} className={generatingReport ? 'animate-spin' : ''} />
                            {t('op.refreshReport')}
                        </button>
                    </div>

                    {report && (
                        <>
                            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('metric.conversations')}</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.total_conversations}</p>
                                    <p className="mt-1 text-xs text-slate-400">{t('reports.perDay', { count: report.data.conversations_per_day })}</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('metric.conversion')}</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.conversion_rate}%</p>
                                    <p className="mt-1 text-xs text-slate-400">{t('metric.dealsCount', { count: report.data.total_deals })}</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('metric.escalations')}</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.escalation_count}</p>
                                    <p className="mt-1 text-xs text-slate-400">{t('reports.reasonsCount', { count: Object.keys(report.data.escalation_reasons).length })}</p>
                                </div>
                                <div className="rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('op.managerReviews')}</p>
                                    <p className="mt-2 text-2xl font-semibold text-white">{report.data.manager_reviews_count}</p>
                                    <p className="mt-1 text-xs text-slate-400">{t('op.dealConversion', { rate: report.data.manager_deal_conversion_rate })}</p>
                                </div>
                            </div>

                            <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                                <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-medium text-white">{t('reports.telegramPreview')}</p>
                                            <p className="mt-1 text-xs text-slate-500">
                                                {formatDateTime(report.data.period_start)} — {formatDateTime(report.data.period_end)}
                                            </p>
                                        </div>
                                        <div className="rounded-xl bg-white/[0.05] px-3 py-2 text-xs font-medium text-slate-300">
                                            {t('op.avgQuality', { score: report.data.avg_quality_score })}
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
                                            <p className="text-sm font-medium">{t('reports.topProducts')}</p>
                                        </div>
                                        <div className="mt-3 space-y-3">
                                            {report.data.top_products.length > 0 ? report.data.top_products.map((product) => (
                                                <div key={product.sku} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                    <p className="text-sm font-medium text-white">{product.name}</p>
                                                    <p className="mt-1 text-xs text-slate-400">{product.sku} · {t('reports.mentions', { count: product.mentions })}</p>
                                                </div>
                                            )) : (
                                                <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-sm text-slate-500">
                                                    {t('reports.topProductsEmpty')}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                        <div className="flex items-center gap-2 text-white">
                                            <Clock size={16} className="text-amber-200" />
                                            <p className="text-sm font-medium">{t('op.managerSnapshot')}</p>
                                        </div>
                                        <div className="mt-3 grid grid-cols-2 gap-3">
                                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('quality.avgScore')}</p>
                                                <p className="mt-2 text-xl font-semibold text-white">{report.data.avg_manager_score}/20</p>
                                            </div>
                                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('quality.colResponse')}</p>
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
                                                    {t('reports.topManagersEmpty')}
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
                                <h3 className="text-lg font-semibold">{t('op.reviewQueueTitle')}</h3>
                            </div>
                            <p className="mt-2 text-sm text-slate-400">
                                {t('op.reviewQueueSubtitle')}
                            </p>
                        </div>
                        <div className="rounded-xl bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200">
                            {t('op.pendingCount', { count: pendingReviews.length })}
                        </div>
                    </div>

                    <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                        <div className="space-y-3">
                            {pendingReviews.length > 0 ? pendingReviews.map((item) => (
                                <div key={item.escalation_id} className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-white">{item.manager_name ?? t('queues.managerUnassigned')}</p>
                                            <p className="mt-1 text-sm text-slate-300">{item.phone}</p>
                                            <p className="mt-2 text-sm text-slate-400">{item.reason}</p>
                                            <p className="mt-2 text-xs text-slate-500">{t('queues.updated', { date: formatDateTime(item.updated_at) })}</p>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => void handleEvaluateReview(item)}
                                            disabled={evaluatingId !== null}
                                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:bg-amber-500/15 disabled:opacity-50"
                                        >
                                            {evaluatingId === item.escalation_id ? <RefreshCw size={16} className="animate-spin" /> : <ClipboardList size={16} />}
                                            {t('common.evaluate')}
                                        </button>
                                    </div>
                                </div>
                            )) : (
                                <div className="rounded-2xl border border-dashed border-white/[0.08] px-4 py-8 text-sm text-slate-500">
                                    {t('op.reviewQueueEmpty')}
                                </div>
                            )}
                        </div>

                        <div className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-sm font-medium text-white">{t('quality.recentTitle')}</p>
                                    <p className="mt-1 text-xs text-slate-500">{t('op.recentReviewsSubtitle')}</p>
                                </div>
                                <div className="rounded-xl bg-white/[0.05] px-3 py-2 text-xs font-medium text-slate-300">
                                    {t('op.shown', { count: recentReviews.length })}
                                </div>
                            </div>

                            <div className="mt-4 space-y-3">
                                {recentReviews.length > 0 ? recentReviews.map((review) => (
                                    <div key={review.id} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-medium text-white">{review.manager_name ?? t('op.unknownManager')}</p>
                                                <p className="mt-1 text-xs text-slate-500">{formatDateTime(review.created_at)}</p>
                                            </div>
                                            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${ratingClasses(review.rating)}`}>
                                                {label(review.rating)}
                                            </span>
                                        </div>
                                        <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-slate-300">
                                            <div>
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('quality.colScore')}</p>
                                                <p className="mt-1 font-medium text-white">{review.total_score}/{review.max_score}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{t('op.responseTime')}</p>
                                                <p className="mt-1 font-medium text-white">{formatDuration(review.first_response_time_seconds)}</p>
                                            </div>
                                        </div>
                                    </div>
                                )) : (
                                    <div className="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-sm text-slate-500">
                                        {t('op.recentReviewsEmpty')}
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
