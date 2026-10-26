import { useCallback, useEffect, useState } from 'react';
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

interface QueuesQualityViewProps {
    globalSearch?: string;
    activeTab?: string;
    onTabChange?: (tab: QueuesQualityTab) => void;
    onOpenConversation?: (conversationId: string) => void;
    onCountsChange?: (counts: { escalations: number; pendingReviews: number }) => void;
    refetchMetrics?: () => void;
    refreshSignal?: number;
}

const BOT_QA_RUBRIC_ITEMS: Array<{ code: string; maxPoints: number; ru: string; en: string }> = [
    { code: 'greeting_identity', maxPoints: 2, ru: 'Приветствие и представление Noor (Treejar)', en: 'Greeting and Noor (Treejar) identity' },
    { code: 'language_match', maxPoints: 2, ru: 'Соблюдение языка клиента (EN / AR / RU)', en: 'Customer language matching (EN / AR / RU)' },
    { code: 'need_discovery', maxPoints: 3, ru: 'Выявление потребностей (офис, размеры, бюджет, сроки)', en: 'Need discovery (space, dimensions, budget, timeline)' },
    { code: 'catalog_grounding', maxPoints: 3, ru: 'Точность рекомендаций строго по каталогу Treejar', en: 'Catalog-grounded product recommendations' },
    { code: 'sku_price_accuracy', maxPoints: 2, ru: 'Точность артикулов (SKU) и цен в AED', en: 'SKU and AED price accuracy' },
    { code: 'stock_awareness', maxPoints: 2, ru: 'Проверка актуальных остатков Zoho Inventory', en: 'Real-time Zoho Inventory stock check' },
    { code: 'vat_clarity', maxPoints: 2, ru: 'Прозрачное указание 5% VAT и условий доставки', en: 'Clear 5% UAE VAT and delivery terms' },
    { code: 'upsell_cross_sell', maxPoints: 2, ru: 'Уместный допродажный подбор (кресла + столы / хранение)', en: 'Relevant B2B cross-sell / upsell suggestions' },
    { code: 'objection_handling', maxPoints: 2, ru: 'Отработка возражений без давления и выдумок', en: 'Fact-based objection handling without hallucination' },
    { code: 'quotation_flow', maxPoints: 2, ru: 'Корректный сбор реквизитов для КП (Quotation / TRN)', en: 'Quotation / TRN details collection' },
    { code: 'escalation_timing', maxPoints: 2, ru: 'Своевременная передача менеджеру при сложном запросе', en: 'Timely escalation to human manager when required' },
    { code: 'conciseness_formatting', maxPoints: 2, ru: 'Лаконичность и читаемое форматирование для WhatsApp', en: 'Concise WhatsApp-friendly formatting' },
    { code: 'polite_b2b_tone', maxPoints: 2, ru: 'Деловой тон B2B-консультанта без навязчивости', en: 'Polite consultative B2B tone' },
    { code: 'next_step_cta', maxPoints: 1, ru: 'Чёткий следующий шаг в конце сообщения', en: 'Clear next step / call to action' },
    { code: 'safety_guardrails', maxPoints: 1, ru: 'Соблюдение жёстких ограничений (без скрытых скидок)', en: 'Compliance with hard guardrails (no unauthorized discounts)' },
];

export default function QueuesQualityView({
    globalSearch = '',
    activeTab: externalTab,
    onTabChange,
    onOpenConversation,
    onCountsChange,
    refetchMetrics,
    refreshSignal = 0,
}: QueuesQualityViewProps) {
    const { t, lang, label, formatDateTime, formatDuration } = useI18n();
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

    const [escalationFilter, setEscalationFilter] = useState<'open' | 'resolved' | 'all'>('open');
    const [escalations, setEscalations] = useState<AdminEscalationQueueItem[]>([]);
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [loading, setLoading] = useState(true);
    const [closingEscalation, setClosingEscalation] = useState<AdminEscalationQueueItem | null>(null);
    const [closingBusy, setClosingBusy] = useState(false);
    const [evaluatingDeal, setEvaluatingDeal] = useState<PendingManagerReview | null>(null);
    const [evaluatingBusy, setEvaluatingBusy] = useState(false);
    const [selectedReview, setSelectedReview] = useState<ManagerReviewRead | null>(null);
    const [rubricOpen, setRubricOpen] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const managerQa = useAIQualityControlBlock('manager_qa', 'Manager QA');
    const managerQaBlock = managerQa.message;

    const loadAll = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const escParams = new URLSearchParams({
                page_size: '50',
                status: escalationFilter,
            });
            const [escPayload, pendingResult, recentResult] = await Promise.all([
                fetchEscalationsQueue(escParams),
                fetchPendingManagerReviews(25),
                fetchRecentManagerReviews(20),
            ]);
            setEscalations(escPayload.items);
            setPendingReviews(pendingResult);
            setRecentReviews(recentResult.items);
            onCountsChange?.({
                escalations: escPayload.total,
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
        if (!refreshSignal) return;
        void loadAll();
        managerQa.refresh();
    }, [refreshSignal, loadAll, managerQa]);

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
        if (!evaluatingDeal || managerQaBlock) return;
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
                                label={String(escalations.length)}
                                tone={escalations.length > 0 ? 'amber' : 'gray'}
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
                            <Badge label={String(recentReviews.length)} tone="green" />
                        </button>
                    </div>

                    <div className="flex items-center gap-2">
                        {currentTab === 'escalations' && (
                            <select
                                value={escalationFilter}
                                onChange={(event) =>
                                    setEscalationFilter(event.target.value as 'open' | 'resolved' | 'all')
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
                                            disabled={evaluatingBusy || Boolean(managerQaBlock)}
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
                                value={recentReviews.length}
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
                                        title="Bot QA (30)"
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
                                        title="Manager QA (20)"
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
                    {BOT_QA_RUBRIC_ITEMS.map((item, idx) => (
                        <div
                            key={item.code}
                            className="flex items-start justify-between gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3"
                        >
                            <div>
                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                    {idx + 1}. {lang === 'ru' ? item.ru : item.en}
                                </p>
                                <p className="mt-0.5 text-xs text-[var(--text-muted)]">{item.code}</p>
                            </div>
                            <Badge label={`${item.maxPoints} pt`} tone="blue" />
                        </div>
                    ))}
                </div>
            </Drawer>
        </>
    );
}
