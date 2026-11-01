import { useCallback, useEffect, useRef, useState } from 'react';
import {
    AlertTriangle,
    Award,
    BookOpen,
    CheckCircle2,
    ClipboardList,
    ExternalLink,
    Inbox,
    MessageCircle,
    RefreshCw,
    ShieldCheck,
    SlidersHorizontal,
} from 'lucide-react';
import { closeConversationEscalation, fetchEscalationsQueue } from '@/api/crm';
import {
    evaluateManagerReview,
    fetchPendingManagerReviews,
    fetchRecentManagerReviews,
} from '@/api/operators';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Drawer from '@/components/ui/Drawer';
import {
    ActionMessageBox,
    Badge,
    Field,
    Panel,
    QualityBlockNotice,
    RefreshButton,
    StateLine,
    StatusCard,
    ViewBanner,
    cx,
    errorMessage,
    matchesQuery,
} from '@/components/ui/Primitives';
import type { ActionMessage } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';
import { localizeQualityGateError, useAIQualityControlBlock } from '@/hooks/useAIQualityControlBlock';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';
import type { AdminEscalationQueueItem } from '@/types/crm';
import type { ManagerReviewRead, PendingManagerReview } from '@/types/operators';

export type QueuesQualityTab = 'escalations' | 'manager_deals' | 'ai_rubric';
export type EscalationQueueFilter = 'open' | 'resolved' | 'all';

interface QueuesQualityViewProps {
    globalSearch?: string;
    activeTab?: string;
    onTabChange?: (tab: QueuesQualityTab) => void;
    onOpenConversation?: (conversationId: string) => void;
    onCountsChange?: (counts: { escalations: number; pendingReviews: number }) => void;
    refetchMetrics?: () => void;
    refreshSignal?: number;
}

export type BotQaCriterionGroup =
    | 'greeting_and_identity'
    | 'tone_and_language'
    | 'need_discovery_and_catalog'
    | 'commercial_vat_and_quotation';

export interface BotQaRubricItem {
    ruleNumber: number;
    code: string;
    group: BotQaCriterionGroup;
    maxPoints: number;
    labelKey: TranslationKey;
}

/**
 * Exact 15-rule Noor Bot QA rubric matching `src/quality/evaluator.py` and
 * `BOT_QA_CRITERIA_RULES` in `src/quality/config.py` (15 × 2 pts = 30 max).
 */
export const BOT_QA_RUBRIC_ITEMS: BotQaRubricItem[] = [
    { ruleNumber: 1, code: 'rule_1', group: 'greeting_and_identity', maxPoints: 2, labelKey: 'rubric.rule.1' },
    { ruleNumber: 2, code: 'rule_2', group: 'greeting_and_identity', maxPoints: 2, labelKey: 'rubric.rule.2' },
    { ruleNumber: 3, code: 'rule_3', group: 'greeting_and_identity', maxPoints: 2, labelKey: 'rubric.rule.3' },
    { ruleNumber: 4, code: 'rule_4', group: 'tone_and_language', maxPoints: 2, labelKey: 'rubric.rule.4' },
    { ruleNumber: 5, code: 'rule_5', group: 'need_discovery_and_catalog', maxPoints: 2, labelKey: 'rubric.rule.5' },
    { ruleNumber: 6, code: 'rule_6', group: 'tone_and_language', maxPoints: 2, labelKey: 'rubric.rule.6' },
    { ruleNumber: 7, code: 'rule_7', group: 'commercial_vat_and_quotation', maxPoints: 2, labelKey: 'rubric.rule.7' },
    { ruleNumber: 8, code: 'rule_8', group: 'need_discovery_and_catalog', maxPoints: 2, labelKey: 'rubric.rule.8' },
    { ruleNumber: 9, code: 'rule_9', group: 'need_discovery_and_catalog', maxPoints: 2, labelKey: 'rubric.rule.9' },
    { ruleNumber: 10, code: 'rule_10', group: 'need_discovery_and_catalog', maxPoints: 2, labelKey: 'rubric.rule.10' },
    { ruleNumber: 11, code: 'rule_11', group: 'commercial_vat_and_quotation', maxPoints: 2, labelKey: 'rubric.rule.11' },
    { ruleNumber: 12, code: 'rule_12', group: 'commercial_vat_and_quotation', maxPoints: 2, labelKey: 'rubric.rule.12' },
    { ruleNumber: 13, code: 'rule_13', group: 'need_discovery_and_catalog', maxPoints: 2, labelKey: 'rubric.rule.13' },
    { ruleNumber: 14, code: 'rule_14', group: 'commercial_vat_and_quotation', maxPoints: 2, labelKey: 'rubric.rule.14' },
    { ruleNumber: 15, code: 'rule_15', group: 'commercial_vat_and_quotation', maxPoints: 2, labelKey: 'rubric.rule.15' },
];

export function buildEscalationsQueueParams(
    filter: EscalationQueueFilter,
    pageSize = 50,
): URLSearchParams {
    const params = new URLSearchParams({
        page_size: String(pageSize),
    });
    if (filter !== 'all') {
        params.set('status', filter);
    }
    return params;
}

export default function QueuesQualityView({
    globalSearch = '',
    activeTab: externalTab,
    onTabChange,
    onOpenConversation,
    onCountsChange,
    refetchMetrics,
    refreshSignal = 0,
}: QueuesQualityViewProps) {
    const { t, label, formatDateTime, formatDuration } = useI18n();
    const { pushToast } = useToast();

    const resolvedTab: QueuesQualityTab =
        externalTab === 'manager_deals' || externalTab === 'managerReviews'
            ? 'manager_deals'
            : externalTab === 'ai_rubric' || externalTab === 'reviews'
              ? 'ai_rubric'
              : 'escalations';

    const [localTab, setLocalTab] = useState<QueuesQualityTab>(resolvedTab);
    useEffect(() => {
        if (externalTab) {
            setLocalTab(resolvedTab);
        }
    }, [externalTab, resolvedTab]);

    const currentTab = onTabChange ? resolvedTab : localTab;
    const handleSelectTab = (next: QueuesQualityTab) => {
        setLocalTab(next);
        onTabChange?.(next);
    };

    const [escalationFilter, setEscalationFilter] = useState<EscalationQueueFilter>('open');
    const [escalations, setEscalations] = useState<AdminEscalationQueueItem[]>([]);
    const [escalationsTotal, setEscalationsTotal] = useState<number>(0);
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [recentReviewsTotal, setRecentReviewsTotal] = useState<number>(0);
    const [loading, setLoading] = useState(true);
    const [closingEscalation, setClosingEscalation] = useState<AdminEscalationQueueItem | null>(null);
    const [closingBusy, setClosingBusy] = useState(false);
    const [evaluatingDeal, setEvaluatingDeal] = useState<PendingManagerReview | null>(null);
    const [evaluatingBusy, setEvaluatingBusy] = useState(false);
    const [selectedReview, setSelectedReview] = useState<ManagerReviewRead | null>(null);
    const [rubricOpen, setRubricOpen] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);
    const lastRefreshSignalRef = useRef<number>(refreshSignal);

    const managerQa = useAIQualityControlBlock('manager_qa', 'Manager QA');
    const managerQaRefresh = managerQa.refresh;

    const loadAll = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const escParams = buildEscalationsQueueParams(escalationFilter, 50);
            const openCountPromise =
                escalationFilter === 'open'
                    ? Promise.resolve(null)
                    : fetchEscalationsQueue(buildEscalationsQueueParams('open', 1));
            const [escPayload, openPayload, pendingResult, recentResult] = await Promise.all([
                fetchEscalationsQueue(escParams),
                openCountPromise,
                fetchPendingManagerReviews(50),
                fetchRecentManagerReviews(20),
            ]);
            setEscalations(escPayload.items);
            setEscalationsTotal(escPayload.total);
            setPendingReviews(pendingResult);
            setRecentReviews(recentResult.items);
            setRecentReviewsTotal(recentResult.total);
            onCountsChange?.({
                escalations: openPayload ? openPayload.total : escPayload.total,
                pendingReviews: pendingResult.length,
            });
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [escalationFilter, onCountsChange, t]);

    useEffect(() => {
        void loadAll();
    }, [loadAll]);

    useEffect(() => {
        if (refreshSignal === lastRefreshSignalRef.current) return;
        lastRefreshSignalRef.current = refreshSignal;
        if (!refreshSignal) return;
        void loadAll();
        managerQaRefresh();
    }, [refreshSignal, loadAll, managerQaRefresh]);

    async function handleConfirmCloseEscalation() {
        if (!closingEscalation) return;
        setClosingBusy(true);
        try {
            await closeConversationEscalation(closingEscalation.id);
            pushToast({
                tone: 'success',
                message: t('queues.escalationClosedToast'),
            });
            setClosingEscalation(null);
            await loadAll();
            refetchMetrics?.();
        } catch (err) {
            pushToast({
                tone: 'error',
                message: errorMessage(err, t),
            });
        } finally {
            setClosingBusy(false);
        }
    }

    async function handleConfirmEvaluateDeal() {
        if (!evaluatingDeal || managerQa.blocked) return;
        setEvaluatingBusy(true);
        setMessage(null);
        try {
            const review = await evaluateManagerReview(evaluatingDeal.escalation_id);
            const resultText = t('queues.evaluated', {
                score: review.total_score,
                max: review.max_score,
            });
            setMessage({ tone: 'success', text: resultText });
            pushToast({ tone: 'success', message: resultText });
            setEvaluatingDeal(null);
            await loadAll();
            refetchMetrics?.();
        } catch (err) {
            const errText = localizeQualityGateError(errorMessage(err, t), t);
            setMessage({ tone: 'error', text: errText });
            pushToast({ tone: 'error', message: errText });
        } finally {
            setEvaluatingBusy(false);
        }
    }

    const visibleEscalations = escalations.filter((item) =>
        matchesQuery(
            globalSearch,
            item.customer_name,
            item.phone,
            item.reason,
            item.assigned_to,
            item.status,
            item.notes,
        ),
    );

    const visiblePendingReviews = pendingReviews.filter((item) =>
        matchesQuery(globalSearch, item.manager_name, item.phone, item.reason, item.status),
    );

    const visibleRecentReviews = recentReviews.filter((review) =>
        matchesQuery(globalSearch, review.manager_name, review.rating, review.reviewer),
    );

    const avgManagerScore = recentReviews.length
        ? (recentReviews.reduce((sum, review) => sum + review.total_score, 0) / recentReviews.length).toFixed(1)
        : '—';
    const convertedCount = recentReviews.filter((review) => review.deal_converted).length;

    return (
        <>
            <ViewBanner
                view="queues"
                actions={
                    <button
                        type="button"
                        onClick={() => setRubricOpen(true)}
                        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
                        data-open-rubric=""
                    >
                        <BookOpen size={13} />
                        {t('queues.openRubricBtn')}
                    </button>
                }
            />

            <section className="space-y-4 p-5" data-queues-quality-view="">
                {message && <ActionMessageBox message={message} />}
                <QualityBlockNotice block={managerQa} />

                {/* Top Tabs Bar (Variant 1B) */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-3">
                    <div
                        role="tablist"
                        aria-label={t('nav.queuesQuality')}
                        className="inline-flex rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-1"
                        data-queues-tabs=""
                    >
                        <button
                            type="button"
                            role="tab"
                            aria-selected={currentTab === 'escalations'}
                            onClick={() => handleSelectTab('escalations')}
                            className={cx(
                                'inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition',
                                currentTab === 'escalations'
                                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] shadow-xs'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                            )}
                            data-tab="escalations"
                        >
                            <AlertTriangle size={14} />
                            <span>{t('queues.tab.escalations')}</span>
                            <Badge
                                label={String(escalationsTotal)}
                                tone={escalationsTotal > 0 ? 'amber' : 'gray'}
                            />
                        </button>

                        <button
                            type="button"
                            role="tab"
                            aria-selected={currentTab === 'manager_deals'}
                            onClick={() => handleSelectTab('manager_deals')}
                            className={cx(
                                'inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition',
                                currentTab === 'manager_deals'
                                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] shadow-xs'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                            )}
                            data-tab="manager_deals"
                        >
                            <ClipboardList size={14} />
                            <span>{t('queues.tab.managerDeals')}</span>
                            <Badge
                                label={String(pendingReviews.length)}
                                tone={pendingReviews.length > 0 ? 'blue' : 'gray'}
                            />
                        </button>

                        <button
                            type="button"
                            role="tab"
                            aria-selected={currentTab === 'ai_rubric'}
                            onClick={() => handleSelectTab('ai_rubric')}
                            className={cx(
                                'inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition',
                                currentTab === 'ai_rubric'
                                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] shadow-xs'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                            )}
                            data-tab="ai_rubric"
                        >
                            <ShieldCheck size={14} />
                            <span>{t('queues.tab.aiRubric')}</span>
                            <Badge label={String(recentReviewsTotal)} tone="green" />
                        </button>
                    </div>

                    <div className="flex items-center gap-2">
                        {currentTab === 'escalations' && (
                            <select
                                value={escalationFilter}
                                onChange={(event) =>
                                    setEscalationFilter(event.target.value as EscalationQueueFilter)
                                }
                                aria-label={t('common.status')}
                                className="h-8 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                data-escalation-status-filter=""
                            >
                                <option value="open">{t('queues.filterOpenEscalations')}</option>
                                <option value="resolved">{t('queues.filterResolvedEscalations')}</option>
                                <option value="all">{t('common.allStatuses')}</option>
                            </select>
                        )}
                        <RefreshButton loading={loading} onClick={() => void loadAll()} />
                    </div>
                </div>

                {/* TAB 1: Escalations Queue */}
                {currentTab === 'escalations' && (
                    <Panel
                        title={t('queues.activeEscalationsTitle')}
                        subtitle={t('queues.activeEscalationsSubtitle')}
                        help={t('queues.activeEscalationsHelp')}
                        icon={Inbox}
                    >
                        {!loading && visibleEscalations.length === 0 && (
                            <StateLine text={t('queues.noActiveEscalations')} />
                        )}

                        <div className="space-y-2.5" data-escalations-queue-list="">
                            {visibleEscalations.map((esc) => {
                                const isResolved = esc.status === 'resolved';
                                return (
                                    <div
                                        key={esc.id}
                                        className="flex flex-col justify-between gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 lg:flex-row lg:items-center"
                                        data-escalation-row={esc.id}
                                    >
                                        <div className="min-w-0 flex-1 space-y-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                                    {esc.customer_name || esc.phone}
                                                </p>
                                                <span className="text-xs text-[var(--text-muted)]">
                                                    {esc.phone}
                                                </span>
                                                <Badge
                                                    label={label(esc.status)}
                                                    tone={isResolved ? 'green' : 'amber'}
                                                />
                                                {esc.sales_stage && (
                                                    <Badge label={label(esc.sales_stage)} tone="blue" />
                                                )}
                                            </div>
                                            <p className="text-sm font-medium text-[var(--text-secondary)]">
                                                {esc.reason}
                                            </p>
                                            {esc.notes && (
                                                <p className="line-clamp-1 text-xs text-[var(--text-muted)]">
                                                    «{esc.notes}»
                                                </p>
                                            )}
                                            <p className="text-xs text-[var(--text-muted)]">
                                                {esc.assigned_to || t('queues.managerUnassigned')} ·{' '}
                                                {formatDateTime(esc.created_at)}
                                            </p>
                                        </div>

                                        <div className="flex shrink-0 flex-wrap items-center gap-2">
                                            {onOpenConversation && (
                                                <button
                                                    type="button"
                                                    onClick={() => onOpenConversation(esc.conversation_id)}
                                                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                                                    data-open-escalation-chat={esc.conversation_id}
                                                >
                                                    <MessageCircle size={14} />
                                                    {t('queues.openChatBtn')}
                                                </button>
                                            )}
                                            {!isResolved && (
                                                <button
                                                    type="button"
                                                    onClick={() => setClosingEscalation(esc)}
                                                    className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                                                    data-close-escalation={esc.id}
                                                >
                                                    <CheckCircle2 size={14} />
                                                    {t('queues.closeEscalationBtn')}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </Panel>
                )}

                {/* TAB 2: Manager Deals Review Queue (single unified queue, no duplicate) */}
                {currentTab === 'manager_deals' && (
                    <Panel
                        title={t('queues.escalationsTitle')}
                        subtitle={t('queues.escalationsSubtitle')}
                        help={t('queues.pendingHelp')}
                        icon={ClipboardList}
                    >
                        {!loading && visiblePendingReviews.length === 0 && (
                            <StateLine text={t('queues.escalationsEmpty')} />
                        )}
                        <div className="space-y-2.5" data-manager-deals-queue="">
                            {visiblePendingReviews.map((item) => (
                                <div
                                    key={item.escalation_id}
                                    className="flex flex-col justify-between gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 lg:flex-row lg:items-center"
                                    data-pending-review-row={item.escalation_id}
                                >
                                    <div className="min-w-0 flex-1 space-y-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <p className="text-sm font-semibold text-[var(--text-primary)]">
                                                {item.manager_name || t('queues.managerUnassigned')}
                                            </p>
                                            <span className="text-xs text-[var(--text-muted)]">
                                                {item.phone}
                                            </span>
                                            <Badge label={label(item.status)} tone="amber" />
                                        </div>
                                        <p className="text-sm text-[var(--text-secondary)]">{item.reason}</p>
                                        <p className="text-xs text-[var(--text-muted)]">
                                            {t('queues.updated', { date: formatDateTime(item.updated_at) })}
                                        </p>
                                    </div>

                                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                                        {onOpenConversation && (
                                            <button
                                                type="button"
                                                onClick={() => onOpenConversation(item.conversation_id)}
                                                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                                            >
                                                <ExternalLink size={14} />
                                                {t('queues.openChatBtn')}
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            disabled={evaluatingBusy || managerQa.blocked}
                                            onClick={() => setEvaluatingDeal(item)}
                                            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-50"
                                            data-evaluate-deal={item.escalation_id}
                                        >
                                            {evaluatingBusy && evaluatingDeal?.escalation_id === item.escalation_id ? (
                                                <RefreshCw size={14} className="animate-spin" />
                                            ) : (
                                                <CheckCircle2 size={14} />
                                            )}
                                            {t('common.evaluate')}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Panel>
                )}

                {/* TAB 3: AI Quality Scores & Rubric */}
                {currentTab === 'ai_rubric' && (
                    <div className="space-y-4" data-ai-rubric-tab="">
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                            <StatusCard
                                title={t('quality.pendingTitle')}
                                help={t('queues.pendingHelp')}
                                value={pendingReviews.length}
                                note={t('quality.pendingNote')}
                                tone="amber"
                            />
                            <StatusCard
                                title={t('quality.recentCount')}
                                help={t('quality.recentHelp')}
                                value={recentReviewsTotal}
                                note={t('quality.recentNote')}
                            />
                            <StatusCard
                                title={t('quality.avgScore')}
                                help={t('quality.avgScoreHelp')}
                                value={`${avgManagerScore}/20`}
                                note={t('quality.avgScoreNote')}
                                tone="blue"
                            />
                            <StatusCard
                                title={t('quality.converted')}
                                help={t('quality.convertedHelp')}
                                value={convertedCount}
                                note={t('quality.convertedNote')}
                                tone="green"
                            />
                        </div>

                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.35fr_0.65fr]">
                            <Panel
                                title={t('quality.recentTitle')}
                                subtitle={t('quality.recentSubtitle')}
                                help={t('quality.recentHelp')}
                                icon={ShieldCheck}
                                action={
                                    <button
                                        type="button"
                                        onClick={() => setRubricOpen(true)}
                                        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                                    >
                                        <Award size={14} />
                                        {t('queues.openRubricBtn')}
                                    </button>
                                }
                            >
                                <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)]">
                                    <table className="min-w-full divide-y divide-[var(--border-subtle)] text-sm">
                                        <thead className="bg-[var(--bg-surface)] text-left text-xs uppercase text-[var(--text-muted)]">
                                            <tr>
                                                <th className="px-4 py-2.5">{t('quality.colManager')}</th>
                                                <th className="px-4 py-2.5">{t('quality.colScore')}</th>
                                                <th className="px-4 py-2.5">{t('quality.colResponse')}</th>
                                                <th className="px-4 py-2.5">{t('quality.colDeal')}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-[var(--border-subtle)] bg-[var(--bg-card)]">
                                            {visibleRecentReviews.map((review) => (
                                                <tr
                                                    key={review.id}
                                                    onClick={() => setSelectedReview(review)}
                                                    className="cursor-pointer hover:bg-[var(--bg-hover)]"
                                                >
                                                    <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">
                                                        {review.manager_name || '—'}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                                                        <Badge
                                                            label={`${review.total_score}/${review.max_score} · ${label(review.rating)}`}
                                                            tone={review.total_score >= 16 ? 'green' : review.total_score >= 12 ? 'blue' : 'amber'}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-2.5 text-[var(--text-muted)]">
                                                        {formatDuration(review.first_response_time_seconds)}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-[var(--text-secondary)]">
                                                        {review.deal_converted
                                                            ? `${review.deal_amount || 0} AED`
                                                            : '—'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {visibleRecentReviews.length === 0 && (
                                        <StateLine text={t('queues.noRecentReviews')} />
                                    )}
                                </div>
                            </Panel>

                            <Panel
                                title={t('quality.contoursTitle')}
                                subtitle={t('quality.contoursSubtitle')}
                                icon={SlidersHorizontal}
                            >
                                <div className="space-y-3">
                                    <StatusCard
                                        title={t('rubric.botQaScaleLabel')}
                                        help={t('aiqc.contour.bot_qa')}
                                        value={
                                            managerQa.config
                                                ? t(`aiqc.mode.${managerQa.config.bot_qa.mode}` as TranslationKey)
                                                : '—'
                                        }
                                        note={t('quality.botQaNote')}
                                        tone={
                                            managerQa.config?.bot_qa.mode === 'scheduled'
                                                ? 'green'
                                                : managerQa.config?.bot_qa.mode === 'manual'
                                                    ? 'blue'
                                                    : 'gray'
                                        }
                                    />
                                    <StatusCard
                                        title={t('rubric.managerQaScaleLabel')}
                                        help={t('aiqc.contour.manager_qa')}
                                        value={
                                            managerQa.config
                                                ? t(`aiqc.mode.${managerQa.config.manager_qa.mode}` as TranslationKey)
                                                : '—'
                                        }
                                        note={t('quality.managerQaNote')}
                                        tone={
                                            managerQa.config?.manager_qa.mode === 'scheduled'
                                                ? 'green'
                                                : managerQa.config?.manager_qa.mode === 'manual'
                                                    ? 'blue'
                                                    : 'gray'
                                        }
                                    />
                                    <StatusCard
                                        title={t('aiqc.scope.red_flags')}
                                        help={t('aiqc.contour.red_flags')}
                                        value={
                                            managerQa.config
                                                ? t(`aiqc.mode.${managerQa.config.red_flags.mode}` as TranslationKey)
                                                : '—'
                                        }
                                        note={t('quality.redFlagsNote')}
                                        tone={
                                            managerQa.config?.red_flags.mode === 'scheduled'
                                                ? 'green'
                                                : managerQa.config?.red_flags.mode === 'manual'
                                                    ? 'blue'
                                                    : 'gray'
                                        }
                                    />
                                </div>
                            </Panel>
                        </div>
                    </div>
                )}
            </section>

            {/* Confirm Close Escalation Modal */}
            <ConfirmDialog
                open={Boolean(closingEscalation)}
                title={t('queues.confirmCloseEscalationTitle')}
                description={t('queues.confirmCloseEscalationDesc', {
                    phone: closingEscalation?.phone ?? '',
                })}
                confirmLabel={t('queues.closeEscalationBtn')}
                cancelLabel={t('common.cancel')}
                busy={closingBusy}
                onConfirm={() => void handleConfirmCloseEscalation()}
                onCancel={() => setClosingEscalation(null)}
            />

            {/* Confirm Evaluate Manager Deal Modal */}
            <ConfirmDialog
                open={Boolean(evaluatingDeal)}
                title={t('queues.confirmEvaluateTitle')}
                description={t('queues.confirmEvaluate')}
                confirmLabel={t('common.evaluate')}
                cancelLabel={t('common.cancel')}
                busy={evaluatingBusy}
                onConfirm={() => void handleConfirmEvaluateDeal()}
                onCancel={() => setEvaluatingDeal(null)}
            />

            {/* Review Detail Drawer */}
            <Drawer
                open={Boolean(selectedReview)}
                title={selectedReview?.manager_name || t('quality.recentTitle')}
                subtitle={
                    selectedReview
                        ? `${selectedReview.total_score}/${selectedReview.max_score} · ${label(selectedReview.rating)}`
                        : undefined
                }
                onClose={() => setSelectedReview(null)}
            >
                {selectedReview && (
                    <div className="space-y-4">
                        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 space-y-2">
                            <Field
                                label={t('quality.colManager')}
                                value={selectedReview.manager_name || '—'}
                            />
                            <Field
                                label={t('quality.colScore')}
                                value={`${selectedReview.total_score}/${selectedReview.max_score}`}
                            />
                            <Field
                                label={t('quality.colResponse')}
                                value={formatDuration(selectedReview.first_response_time_seconds)}
                            />
                            <Field
                                label={t('quality.colDeal')}
                                value={
                                    selectedReview.deal_converted
                                        ? `${selectedReview.deal_amount || 0} AED`
                                        : t('common.no')
                                }
                            />
                        </div>
                    </div>
                )}
            </Drawer>

            {/* 15-Criterion AI Rubric Drawer */}
            <Drawer
                open={rubricOpen}
                title={t('queues.rubricModalTitle')}
                subtitle={t('queues.rubricModalSubtitle')}
                onClose={() => setRubricOpen(false)}
                widthClassName="max-w-xl"
            >
                <div className="space-y-3" data-bot-qa-rubric-list="">
                    {BOT_QA_RUBRIC_ITEMS.map((item) => (
                        <div
                            key={item.code}
                            className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3"
                        >
                            <div>
                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                    {item.ruleNumber}. {t(item.labelKey)}
                                </p>
                                <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                                    {t(`rubric.group.${item.group}` as TranslationKey)}
                                </p>
                            </div>
                            <Badge
                                label={t('rubric.pointsBadge', { points: item.maxPoints })}
                                tone="blue"
                            />
                        </div>
                    ))}
                </div>
            </Drawer>
        </>
    );
}
