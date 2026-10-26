import { useCallback, useEffect, useRef, useState } from 'react';
import {
    CheckCircle2,
    MoreHorizontal,
    PanelRightOpen,
    RotateCcw,
    Search,
    SlidersHorizontal,
    Sparkles,
    X,
} from 'lucide-react';
import {
    closeConversationEscalation,
    executeConversationReset,
    fetchAdminConversation,
    fetchAdminCustomers,
    previewConversationReset,
    runBotQualityReview,
    updateAdminConversation,
} from '@/api/crm';
import { SectionInfoBanner } from '@/components/HelpTooltip';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Drawer } from '@/components/ui/Drawer';
import {
    Badge,
    EmptyBox,
    FieldLabel,
    PaginationBar,
    QualityBlockNotice,
} from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';
import { useAIQualityControlBlock } from '@/hooks/useAIQualityControlBlock';
import { useI18n, type TranslationKey } from '@/i18n';
import type {
    AdminConversationDetail,
    AdminCustomerListItem,
    AdminResetExecuteResult,
    AdminResetPreview,
} from '@/types/crm';

export interface ConversationsViewProps {
    globalSearch?: string;
    initialId?: string;
    initialFilter?: string;
    initialLanguage?: string;
    initialStatus?: string;
    initialStage?: string;
    initialEscalation?: string;
    refreshSignal?: number;
    onSelectConversationId?: (id: string | undefined) => void;
    onClearRouteFilter?: () => void;
}

type QuickTab = 'all' | 'waiting' | 'review';

function leadStatusBadge(detail: {
    status: string;
    escalation_status: string;
}): { tone: 'emerald' | 'amber' | 'slate'; labelKey: TranslationKey } {
    if (
        detail.escalation_status === 'pending' ||
        detail.escalation_status === 'in_progress' ||
        detail.escalation_status === 'manual_takeover'
    ) {
        return { tone: 'amber', labelKey: 'conv.lead.waitingOperator' };
    }
    if (detail.status === 'closed' || detail.status === 'completed') {
        return { tone: 'slate', labelKey: 'conv.lead.closed' };
    }
    return { tone: 'emerald', labelKey: 'conv.lead.noorActive' };
}

export default function ConversationsView({
    globalSearch = '',
    initialId,
    initialFilter = '',
    initialLanguage = '',
    initialStatus = '',
    initialStage = '',
    initialEscalation = '',
    refreshSignal = 0,
    onSelectConversationId,
    onClearRouteFilter,
}: ConversationsViewProps) {
    const { t, label, formatNumber, formatDateTime, formatCurrency } = useI18n();
    const { showToast } = useToast();
    const botQaBlock = useAIQualityControlBlock('bot_qa', 'Bot QA');

    const [customers, setCustomers] = useState<AdminCustomerListItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pages, setPages] = useState(1);

    const [searchInput, setSearchInput] = useState(globalSearch);
    const [debouncedSearch, setDebouncedSearch] = useState(globalSearch);
    const [quickTab, setQuickTab] = useState<QuickTab>('all');
    const [routeFilter, setRouteFilter] = useState(initialFilter);
    const [showFilters, setShowFilters] = useState(
        Boolean(initialLanguage || initialStatus || initialStage || initialEscalation),
    );
    const [status, setStatus] = useState(initialStatus);
    const [stage, setStage] = useState(initialStage);
    const [language, setLanguage] = useState(initialLanguage);
    const [escalation, setEscalation] = useState(initialEscalation);

    const [selectedId, setSelectedId] = useState<string | null>(initialId ?? null);
    const selectedIdRef = useRef<string | null>(initialId ?? null);
    const onSelectConversationIdRef = useRef(onSelectConversationId);
    onSelectConversationIdRef.current = onSelectConversationId;
    const [detail, setDetail] = useState<AdminConversationDetail | null>(null);
    const [loadingList, setLoadingList] = useState(true);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [actionMessage, setActionMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [crmDrawerOpen, setCrmDrawerOpen] = useState(false);
    const [moreMenuOpen, setMoreMenuOpen] = useState(false);
    const [resetPreview, setResetPreview] = useState<AdminResetPreview | null>(null);
    const [resetModalOpen, setResetModalOpen] = useState(false);
    const [resetResult, setResetResult] = useState<AdminResetExecuteResult | null>(null);
    const [resetBusy, setResetBusy] = useState(false);
    const [closingEscalation, setClosingEscalation] = useState(false);

    const [editName, setEditName] = useState('');
    const [editStatus, setEditStatus] = useState('');
    const [editStage, setEditStage] = useState('');
    const [editEscalation, setEditEscalation] = useState('');
    const [editDealStatus, setEditDealStatus] = useState('');

    useEffect(() => {
        setSearchInput(globalSearch);
    }, [globalSearch]);

    useEffect(() => {
        const timer = globalThis.setTimeout(() => {
            setDebouncedSearch(searchInput);
            setPage(1);
        }, 300);
        return () => globalThis.clearTimeout(timer);
    }, [searchInput]);

    useEffect(() => {
        if (initialLanguage !== undefined) setLanguage(initialLanguage);
        if (initialStatus !== undefined) setStatus(initialStatus);
        if (initialStage !== undefined) setStage(initialStage);
        if (initialEscalation !== undefined) setEscalation(initialEscalation);
        setRouteFilter(initialFilter || '');
    }, [initialFilter, initialLanguage, initialStatus, initialStage, initialEscalation]);

    const selectCustomerConversation = useCallback((id: string | null) => {
        selectedIdRef.current = id;
        setSelectedId(id);
        onSelectConversationIdRef.current?.(id ?? undefined);
    }, []);

    // Note: selectedId is intentionally NOT a dependency here so clicking a customer
    // never triggers a redundant GET /api/v1/admin/crm/customers request (tj-7ps5.7).
    const loadCustomers = useCallback(async () => {
        setLoadingList(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(page),
                page_size: '20',
            });
            if (debouncedSearch.trim()) params.set('search', debouncedSearch.trim());
            const effectiveEscalation =
                quickTab === 'waiting'
                    ? 'pending'
                    : quickTab === 'review'
                      ? 'resolved'
                      : escalation;
            if (status) params.set('status', status);
            if (stage) params.set('stage', stage);
            if (language) params.set('language', language);
            if (effectiveEscalation) params.set('escalation', effectiveEscalation);
            if (routeFilter === 'deals') {
                params.set('has_deal', 'true');
            } else if (routeFilter === 'target') {
                params.set('target_only', 'true');
            } else if (routeFilter === 'nontarget') {
                params.set('target_only', 'false');
            }

            const response = await fetchAdminCustomers(params);
            setCustomers(response.items);
            setTotal(response.total);
            setPages(response.pages);
            if (!selectedIdRef.current && response.items[0]) {
                selectCustomerConversation(response.items[0].latest_conversation_id);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.list'));
        } finally {
            setLoadingList(false);
        }
    }, [
        page,
        debouncedSearch,
        quickTab,
        status,
        stage,
        language,
        escalation,
        routeFilter,
        selectCustomerConversation,
        t,
    ]);

    const loadDetail = useCallback(
        async (conversationId: string) => {
            setLoadingDetail(true);
            setError(null);
            setResetPreview(null);
            setResetResult(null);
            try {
                const next = await fetchAdminConversation(conversationId);
                setDetail(next);
                setEditName(next.customer_name || '');
                setEditStatus(next.status);
                setEditStage(next.sales_stage);
                setEditEscalation(next.escalation_status);
                setEditDealStatus(next.deal_status || '');
            } catch (err) {
                setError(err instanceof Error ? err.message : t('conv.error.detail'));
            } finally {
                setLoadingDetail(false);
            }
        },
        [t],
    );

    useEffect(() => {
        void loadCustomers();
    }, [loadCustomers]);

    useEffect(() => {
        if (selectedId) {
            void loadDetail(selectedId);
        }
    }, [selectedId, loadDetail]);

    useEffect(() => {
        if (!refreshSignal) return;
        void loadCustomers();
        if (selectedIdRef.current) {
            void loadDetail(selectedIdRef.current);
        }
    }, [refreshSignal, loadCustomers, loadDetail]);

    const handleSaveCrm = async () => {
        if (!detail) return;
        setActionMessage(null);
        setError(null);
        try {
            const updated = await updateAdminConversation(detail.id, {
                customer_name: editName.trim() || null,
                status: editStatus,
                sales_stage: editStage,
                escalation_status: editEscalation,
                deal_status: editDealStatus.trim() || null,
            });
            setDetail(updated);
            setActionMessage(t('conv.saved'));
            showToast({ tone: 'success', message: t('conv.saved') });
            void loadCustomers();
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.save'));
        }
    };

    const handleOpenResetDialog = async () => {
        if (!detail) return;
        setMoreMenuOpen(false);
        setResetBusy(true);
        setError(null);
        try {
            const preview = await previewConversationReset(detail.id);
            setResetPreview(preview);
            setResetModalOpen(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.resetPreview'));
        } finally {
            setResetBusy(false);
        }
    };

    const handleExecuteReset = async () => {
        if (!detail) return;
        setResetBusy(true);
        setError(null);
        try {
            const result = await executeConversationReset(detail.id);
            setResetResult(result);
            setResetPreview(null);
            setResetModalOpen(false);
            const msg = t('conv.resetCompleted', {
                phone: result.phone,
                count: result.archived_count,
            });
            setActionMessage(msg);
            showToast({ tone: 'success', message: msg });
            if (result.new_conversation_id) {
                selectCustomerConversation(result.new_conversation_id);
            }
            void loadCustomers();
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.resetExecute'));
        } finally {
            setResetBusy(false);
        }
    };

    const handleCloseOpenEscalation = async () => {
        if (!detail) return;
        const openEsc = (detail.escalations ?? []).find(
            (esc) =>
                esc.status === 'pending' ||
                esc.status === 'in_progress' ||
                esc.status === 'manual_takeover',
        );
        if (!openEsc) return;
        setClosingEscalation(true);
        setError(null);
        try {
            await closeConversationEscalation(openEsc.id);
            showToast({ tone: 'success', message: t('conv.escalationClosed') });
            await loadDetail(detail.id);
            void loadCustomers();
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.save'));
        } finally {
            setClosingEscalation(false);
        }
    };

    const handleBotReview = async () => {
        if (!detail) return;
        setActionMessage(null);
        setError(null);
        try {
            await runBotQualityReview(detail.id);
            setActionMessage(t('conv.botQaDone'));
            showToast({ tone: 'success', message: t('conv.botQaDone') });
            botQaBlock.refresh();
            await loadDetail(detail.id);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('conv.error.botQa'));
            botQaBlock.refresh();
        }
    };

    const openEscalation = (detail?.escalations ?? []).find(
        (esc) =>
            esc.status === 'pending' ||
            esc.status === 'in_progress' ||
            esc.status === 'manual_takeover',
    );
    const leadInfo = detail ? leadStatusBadge(detail) : null;

    return (
        <div className="flex h-[calc(100vh-88px)] flex-col">
            <SectionInfoBanner
                storageKey="conversations"
                title={t('banner.conversations.title')}
                description={t('banner.conversations.body')}
                runtime={t('banner.conversations.runtime')}
                defaultCollapsed
            />

            {/* Variant 4A: 2-Column Workspace (List + Wide Chat) + CRM Slide-over Drawer */}
            <div
                data-conversations-layout="variant-4a"
                className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[340px_minmax(420px,1fr)]"
            >
                {/* Left Column: Customer List with Quick Tabs & 300ms Debounced Search */}
                <div className="admin-panel flex min-h-0 flex-col rounded-xl shadow-2xs">
                    <div className="space-y-2 border-b border-slate-200 p-3 dark:border-slate-800">
                        <div className="flex items-center justify-between gap-2">
                            <div
                                data-conv-quick-tabs
                                className="admin-subpanel flex flex-1 items-center gap-1 rounded-lg p-0.5 text-xs"
                            >
                                {(
                                    [
                                        ['all', t('conv.tab.all')],
                                        ['waiting', t('conv.tab.waiting')],
                                        ['review', t('conv.tab.review')],
                                    ] as const
                                ).map(([tabId, tabLabel]) => (
                                    <button
                                        key={tabId}
                                        type="button"
                                        onClick={() => {
                                            setQuickTab(tabId);
                                            setPage(1);
                                        }}
                                        className={`flex-1 rounded-md px-2 py-1 font-semibold transition-colors ${
                                            quickTab === tabId
                                                ? 'bg-[#2170e4] text-white'
                                                : 'text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-white'
                                        }`}
                                    >
                                        {tabLabel}
                                    </button>
                                ))}
                            </div>
                            <button
                                type="button"
                                onClick={() => setShowFilters((curr) => !curr)}
                                aria-label={t('conv.toggleFilters')}
                                className={`admin-subpanel rounded-lg p-1.5 text-xs ${
                                    showFilters
                                        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                                        : 'text-slate-600 dark:text-slate-300'
                                }`}
                            >
                                <SlidersHorizontal className="h-3.5 w-3.5" />
                            </button>
                        </div>

                        <div className="relative">
                            <Search className="pointer-events-none absolute top-2.5 left-2.5 h-3.5 w-3.5 text-slate-400" />
                            <input
                                type="search"
                                value={searchInput}
                                onChange={(event) => setSearchInput(event.target.value)}
                                placeholder={t('conv.searchPlaceholder')}
                                className="admin-input w-full rounded-lg py-1.5 pr-3 pl-8 text-xs focus:border-[#2170e4] focus:outline-none"
                            />
                        </div>

                        {(routeFilter === 'deals' ||
                            routeFilter === 'target' ||
                            routeFilter === 'nontarget') && (
                            <div
                                data-conv-route-filter={routeFilter}
                                className="flex items-center justify-between gap-2 rounded-lg border border-blue-200 bg-blue-50/80 px-2.5 py-1.5 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200"
                            >
                                <span className="truncate font-medium">
                                    {t(`conv.filter.activeChip.${routeFilter}` as TranslationKey)}
                                </span>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setRouteFilter('');
                                        setPage(1);
                                        onClearRouteFilter?.();
                                    }}
                                    aria-label={t('conv.filter.clearAll')}
                                    className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold hover:bg-blue-100 dark:hover:bg-blue-900/60"
                                >
                                    <X className="h-3 w-3" />
                                    <span>{t('conv.filter.clearAll')}</span>
                                </button>
                            </div>
                        )}

                        {showFilters && (
                            <div className="grid grid-cols-2 gap-1.5 pt-1">
                                <select
                                    value={status}
                                    onChange={(event) => {
                                        setStatus(event.target.value);
                                        setPage(1);
                                    }}
                                    className="admin-input rounded-lg px-2 py-1.5 text-xs"
                                >
                                    <option value="">{t('conv.filter.allStatuses')}</option>
                                    <option value="active">{t('conv.filter.status.active')}</option>
                                    <option value="paused">{t('conv.filter.status.paused')}</option>
                                    <option value="escalated">{t('conv.filter.status.escalated')}</option>
                                    <option value="closed">{t('conv.filter.status.closed')}</option>
                                </select>
                                <select
                                    value={stage}
                                    onChange={(event) => {
                                        setStage(event.target.value);
                                        setPage(1);
                                    }}
                                    className="admin-input rounded-lg px-2 py-1.5 text-xs"
                                >
                                    <option value="">{t('conv.filter.allStages')}</option>
                                    <option value="greeting">{label('greeting')}</option>
                                    <option value="qualifying">{label('qualifying')}</option>
                                    <option value="needs_analysis">{label('needs_analysis')}</option>
                                    <option value="solution">{label('solution')}</option>
                                    <option value="company_details">{label('company_details')}</option>
                                    <option value="quoting">{label('quoting')}</option>
                                    <option value="closing">{label('closing')}</option>
                                    <option value="feedback">{label('feedback')}</option>
                                    <option value="unknown">{label('unknown')}</option>
                                </select>
                                <select
                                    value={language}
                                    onChange={(event) => {
                                        setLanguage(event.target.value);
                                        setPage(1);
                                    }}
                                    className="admin-input rounded-lg px-2 py-1.5 text-xs"
                                >
                                    <option value="">{t('conv.filter.allLangs')}</option>
                                    <option value="en">{label('en')}</option>
                                    <option value="ar">{label('ar')}</option>
                                </select>
                                <select
                                    value={escalation}
                                    onChange={(event) => {
                                        setEscalation(event.target.value);
                                        setPage(1);
                                    }}
                                    className="admin-input rounded-lg px-2 py-1.5 text-xs"
                                >
                                    <option value="">{t('conv.filter.allEscalations')}</option>
                                    <option value="none">{label('none')}</option>
                                    <option value="pending">{label('pending')}</option>
                                    <option value="in_progress">{label('in_progress')}</option>
                                    <option value="resolved">{label('resolved')}</option>
                                    <option value="manual_takeover">{label('manual_takeover')}</option>
                                </select>
                            </div>
                        )}
                    </div>

                    <div className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800/70">
                        {loadingList ? (
                            <div className="p-4 text-xs text-slate-500">
                                {t('conv.loadingCustomers')}
                            </div>
                        ) : customers.length === 0 ? (
                            <div className="p-4 text-xs text-slate-500">
                                {t('conv.noCustomers')}
                            </div>
                        ) : (
                            customers.map((customer) => {
                                const active = customer.latest_conversation_id === selectedId;
                                const lead = leadStatusBadge(customer);
                                return (
                                    <button
                                        key={customer.phone}
                                        type="button"
                                        data-customer-item={customer.phone}
                                        onClick={() =>
                                            selectCustomerConversation(
                                                customer.latest_conversation_id,
                                            )
                                        }
                                        className={`w-full px-3.5 py-2.5 text-left transition-colors ${
                                            active
                                                ? 'border-l-4 border-l-[#2170e4] bg-blue-50/70 dark:bg-blue-950/40'
                                                : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <div className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                                                    {customer.customer_name ||
                                                        t('conv.unnamedCustomer')}
                                                </div>
                                                <div className="font-mono text-xs text-slate-500 dark:text-slate-400">
                                                    {customer.phone}
                                                </div>
                                            </div>
                                            <Badge tone={lead.tone}>{t(lead.labelKey)}</Badge>
                                        </div>
                                        <p className="mt-1 line-clamp-1 text-xs text-slate-600 dark:text-slate-300">
                                            {customer.latest_message_preview ||
                                                t('conv.noMessages')}
                                        </p>
                                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                                            <span>{label(customer.sales_stage)}</span>
                                            <span>·</span>
                                            <span>{customer.language.toUpperCase()}</span>
                                            {customer.conversation_count > 1 && (
                                                <>
                                                    <span>·</span>
                                                    <span>
                                                        {t('conv.chatsCount', {
                                                            count: customer.conversation_count,
                                                        })}
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                    </button>
                                );
                            })
                        )}
                    </div>
                    <PaginationBar
                        page={page}
                        pages={pages}
                        total={total}
                        onPageChange={setPage}
                    />
                </div>

                {/* Right Column: Wide Chat Timeline */}
                <div className="admin-panel flex min-h-0 flex-col rounded-xl shadow-2xs">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
                        <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                                <h2 className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                                    {detail?.customer_name ||
                                        detail?.phone ||
                                        t('conv.pickDialog')}
                                </h2>
                                {detail && leadInfo && (
                                    <Badge tone={leadInfo.tone}>{t(leadInfo.labelKey)}</Badge>
                                )}
                                {detail && (
                                    <Badge
                                        tone={
                                            detail.escalation_status === 'none'
                                                ? 'slate'
                                                : detail.escalation_status === 'resolved'
                                                  ? 'emerald'
                                                  : 'amber'
                                        }
                                    >
                                        {label(detail.escalation_status)}
                                    </Badge>
                                )}
                            </div>
                            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                {detail
                                    ? `${detail.phone} · ${t('conv.messagesCount', {
                                          count: detail.message_count,
                                      })} · ${label(detail.sales_stage)}`
                                    : t('conv.chatReadOnlyHint')}
                            </p>
                        </div>

                        {detail && (
                            <div className="flex flex-wrap items-center gap-1.5">
                                {openEscalation && (
                                    <button
                                        type="button"
                                        onClick={() => void handleCloseOpenEscalation()}
                                        disabled={closingEscalation}
                                        data-close-escalation-btn
                                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                                    >
                                        <CheckCircle2 className="h-3.5 w-3.5" />
                                        {t('conv.action.closeEscalation')}
                                    </button>
                                )}

                                <button
                                    type="button"
                                    onClick={() => void handleBotReview()}
                                    disabled={botQaBlock.blocked}
                                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#2170e4] px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    <Sparkles className="h-3.5 w-3.5" />
                                    {t('conv.action.botReview')}
                                </button>

                                <button
                                    type="button"
                                    onClick={() => setCrmDrawerOpen(true)}
                                    data-open-crm-drawer
                                    className="admin-subpanel inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                                >
                                    <PanelRightOpen className="h-3.5 w-3.5" />
                                    {t('conv.action.openCrmDrawer')}
                                </button>

                                <div className="relative">
                                    <button
                                        type="button"
                                        onClick={() => setMoreMenuOpen((curr) => !curr)}
                                        data-conv-more-menu-btn
                                        aria-label={t('conv.action.more')}
                                        className="admin-subpanel rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                                    >
                                        <MoreHorizontal className="h-4 w-4" />
                                    </button>
                                    {moreMenuOpen && (
                                        <div
                                            data-conv-more-menu
                                            className="admin-panel absolute right-0 z-30 mt-1 w-52 rounded-xl p-1.5 shadow-xl"
                                        >
                                            <button
                                                type="button"
                                                onClick={() => void handleOpenResetDialog()}
                                                disabled={resetBusy}
                                                data-reset-client-menu-item
                                                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-semibold text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/50"
                                            >
                                                <RotateCcw className="h-3.5 w-3.5" />
                                                <span>{t('conv.action.resetPreview')}</span>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {(error || actionMessage || botQaBlock.blocked) && (
                        <div className="space-y-1.5 border-b border-slate-100 px-4 py-2 text-xs dark:border-slate-800">
                            <QualityBlockNotice block={botQaBlock} className="" />
                            {error && (
                                <div className="text-red-600 dark:text-red-400">{error}</div>
                            )}
                            {actionMessage && (
                                <div className="text-emerald-700 dark:text-emerald-400">
                                    {actionMessage}
                                </div>
                            )}
                        </div>
                    )}

                    {resetResult && (
                        <div className="mx-4 mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200">
                            {t('conv.resetDoneBanner', {
                                count: resetResult.archived_count,
                                phone: resetResult.phone,
                            })}
                        </div>
                    )}

                    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                        {loadingDetail ? (
                            <div className="text-xs text-slate-500">
                                {t('conv.loadingMessages')}
                            </div>
                        ) : !detail ? (
                            <EmptyBox text={t('conv.selectCustomerPrompt')} />
                        ) : (detail.timeline ?? []).length === 0 ? (
                            <EmptyBox text={t('conv.emptyConversation')} />
                        ) : (
                            (detail.timeline ?? []).map((message) => {
                                const isUser = message.role === 'user';
                                return (
                                    <div
                                        key={message.id}
                                        className={`flex ${isUser ? 'justify-start' : 'justify-end'}`}
                                    >
                                        <div
                                            className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed ${
                                                isUser
                                                    ? 'admin-subpanel text-slate-900 dark:text-slate-100'
                                                    : 'bg-[#2170e4] text-white'
                                            }`}
                                        >
                                            <div className="mb-1 flex items-center justify-between gap-4 text-[10px] opacity-75">
                                                <span className="font-semibold uppercase">
                                                    {isUser
                                                        ? t('conv.role.client')
                                                        : 'Noor / CRM'}
                                                </span>
                                                <span>
                                                    {formatDateTime(message.created_at)}
                                                </span>
                                            </div>
                                            <div className="whitespace-pre-wrap">
                                                {message.content}
                                            </div>
                                            {message.transcription && (
                                                <div className="mt-2 rounded bg-black/10 p-2 text-[11px]">
                                                    {t('conv.audioPrefix')}:{' '}
                                                    {message.transcription}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>
            </div>

            {/* Slide-over CRM & Context Drawer (Variant 4A) */}
            <Drawer
                open={crmDrawerOpen && Boolean(detail)}
                title={t('conv.inspector.title')}
                subtitle={detail?.phone}
                widthClass="max-w-lg"
                onClose={() => setCrmDrawerOpen(false)}
            >
                {detail && (
                    <div className="space-y-4">
                        <div className="space-y-2.5">
                            <FieldLabel label={t('conv.field.customerName')}>
                                <input
                                    value={editName}
                                    onChange={(event) => setEditName(event.target.value)}
                                    className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                />
                            </FieldLabel>
                            <div className="grid grid-cols-2 gap-2">
                                <FieldLabel label={t('conv.field.status')}>
                                    <select
                                        value={editStatus}
                                        onChange={(event) => setEditStatus(event.target.value)}
                                        className="admin-input w-full rounded-lg px-2 py-1.5 text-xs"
                                    >
                                        <option value="active">
                                            {t('conv.filter.status.active')}
                                        </option>
                                        <option value="paused">
                                            {t('conv.filter.status.paused')}
                                        </option>
                                        <option value="escalated">
                                            {t('conv.filter.status.escalated')}
                                        </option>
                                        {editStatus === 'completed' && (
                                            <option value="completed">
                                                {t('conv.filter.status.completed')}
                                            </option>
                                        )}
                                        <option value="closed">
                                            {t('conv.filter.status.closed')}
                                        </option>
                                    </select>
                                </FieldLabel>
                                <FieldLabel label={t('conv.field.stage')}>
                                    <select
                                        value={editStage}
                                        onChange={(event) => setEditStage(event.target.value)}
                                        className="admin-input w-full rounded-lg px-2 py-1.5 text-xs"
                                    >
                                        <option value="greeting">{label('greeting')}</option>
                                        <option value="qualifying">{label('qualifying')}</option>
                                        <option value="needs_analysis">
                                            {label('needs_analysis')}
                                        </option>
                                        <option value="solution">{label('solution')}</option>
                                        <option value="company_details">
                                            {label('company_details')}
                                        </option>
                                        <option value="quoting">{label('quoting')}</option>
                                        <option value="closing">{label('closing')}</option>
                                        <option value="feedback">{label('feedback')}</option>
                                    </select>
                                </FieldLabel>
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                                <FieldLabel label={t('conv.field.escalation')}>
                                    <select
                                        value={editEscalation}
                                        onChange={(event) =>
                                            setEditEscalation(event.target.value)
                                        }
                                        className="admin-input w-full rounded-lg px-2 py-1.5 text-xs"
                                    >
                                        <option value="none">{label('none')}</option>
                                        <option value="pending">{label('pending')}</option>
                                        <option value="in_progress">
                                            {label('in_progress')}
                                        </option>
                                        <option value="resolved">{label('resolved')}</option>
                                        <option value="manual_takeover">
                                            {label('manual_takeover')}
                                        </option>
                                    </select>
                                </FieldLabel>
                                <FieldLabel label={t('conv.field.dealStatus')}>
                                    <input
                                        value={editDealStatus}
                                        onChange={(event) =>
                                            setEditDealStatus(event.target.value)
                                        }
                                        placeholder="pending / won / delivered"
                                        className="admin-input w-full rounded-lg px-2 py-1.5 text-xs"
                                    />
                                </FieldLabel>
                            </div>
                            <button
                                type="button"
                                onClick={() => void handleSaveCrm()}
                                className="w-full rounded-lg bg-[#2170e4] px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                            >
                                {t('conv.saveCard')}
                            </button>
                        </div>

                        <div className="admin-subpanel space-y-1.5 rounded-lg p-3 text-xs">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                                {t('conv.inspector.zohoAndOrder')}
                            </div>
                            <div>Contact ID: {detail.zoho_contact_id || '—'}</div>
                            <div>Deal ID: {detail.zoho_deal_id || '—'}</div>
                            <div>
                                {t('conv.inspector.amount')}:{' '}
                                {detail.deal_amount
                                    ? formatCurrency(detail.deal_amount, 'AED')
                                    : '—'}
                            </div>
                            <div>
                                {t('conv.inspector.segment')}:{' '}
                                {detail.segment || detail.source || '—'}
                            </div>
                        </div>

                        <div className="space-y-2 text-xs">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                                {t('conv.inspector.appliedRules')} (
                                {(detail.applied_bot_rules ?? []).length})
                            </div>
                            {(detail.applied_bot_rules ?? []).length === 0 ? (
                                <div className="text-slate-500">
                                    {t('conv.inspector.noAppliedRules')}
                                </div>
                            ) : (
                                (detail.applied_bot_rules ?? []).map((rule) => (
                                    <div
                                        key={rule.id}
                                        className="admin-subpanel rounded-lg p-2.5"
                                    >
                                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                                            {rule.title}
                                        </div>
                                        <div className="text-[11px] text-slate-500">
                                            {label(rule.type)} · {t('botRules.col.priority')}{' '}
                                            {rule.priority}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>

                        <div className="space-y-2 text-xs">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                                {t('conv.inspector.escalations')} ({(detail.escalations ?? []).length})
                            </div>
                            {(detail.escalations ?? []).map((esc) => (
                                <div
                                    key={esc.id}
                                    className="admin-subpanel rounded-lg p-2.5"
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="font-semibold text-slate-900 dark:text-slate-100">
                                            {esc.reason}
                                        </span>
                                        <Badge
                                            tone={
                                                esc.status === 'resolved' ? 'emerald' : 'amber'
                                            }
                                        >
                                            {label(esc.status)}
                                        </Badge>
                                    </div>
                                    <div className="mt-1 text-[11px] text-slate-500">
                                        {esc.assigned_to || t('conv.inspector.unassigned')} ·{' '}
                                        {formatDateTime(esc.created_at)}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="space-y-2 text-xs">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">
                                {t('conv.inspector.reviews')} (
                                {(detail.quality_reviews ?? []).length + (detail.manager_reviews ?? []).length})
                            </div>
                            {(detail.quality_reviews ?? []).map((review) => (
                                <div
                                    key={review.id}
                                    className="admin-subpanel rounded-lg p-2.5"
                                >
                                    <div className="font-semibold text-slate-900 dark:text-slate-100">
                                        Bot QA: {formatNumber(review.total_score, 1)}/
                                        {review.max_score} ({label(review.rating)})
                                    </div>
                                    <p className="mt-1 text-slate-600 dark:text-slate-300">
                                        {review.summary}
                                    </p>
                                </div>
                            ))}
                            {(detail.manager_reviews ?? []).map((review) => (
                                <div
                                    key={review.id}
                                    className="admin-subpanel rounded-lg p-2.5"
                                >
                                    <div className="font-semibold text-slate-900 dark:text-slate-100">
                                        Manager QA: {formatNumber(review.total_score, 1)}/
                                        {review.max_score} ({label(review.rating)})
                                    </div>
                                    <p className="mt-1 text-slate-600 dark:text-slate-300">
                                        {review.summary}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </Drawer>

            {/* Typed RESET Confirmation Modal (Variant 4A) */}
            <ConfirmDialog
                open={resetModalOpen && Boolean(resetPreview)}
                title={t('conv.resetPreview.title')}
                tone="danger"
                requireTypedText="RESET"
                typedPlaceholder="RESET"
                busy={resetBusy}
                confirmLabel={
                    resetBusy
                        ? t('conv.resetPreview.executing')
                        : t('conv.resetPreview.confirm')
                }
                cancelLabel={t('conv.resetPreview.cancel')}
                onConfirm={() => void handleExecuteReset()}
                onCancel={() => {
                    if (!resetBusy) {
                        setResetModalOpen(false);
                        setResetPreview(null);
                    }
                }}
                description={
                    resetPreview && (
                        <div className="space-y-2 text-xs">
                            <p>{t('conv.confirmResetPreview')}</p>
                            <div className="admin-subpanel space-y-1 rounded-lg p-3">
                                <div>
                                    {t('conv.resetPreview.phone')}:{' '}
                                    <strong className="font-mono">{resetPreview.phone}</strong>
                                </div>
                                <div>
                                    {t('conv.resetPreview.conversations')}:{' '}
                                    <strong>{resetPreview.conversation_count}</strong>
                                </div>
                                <div>
                                    {t('conv.resetPreview.messages')}:{' '}
                                    <strong>{resetPreview.message_count}</strong>
                                </div>
                                <div>
                                    {t('conv.resetPreview.openEscalations')}:{' '}
                                    <strong>{resetPreview.pending_escalation_count}</strong>
                                </div>
                            </div>
                            <p className="font-semibold text-red-600 dark:text-red-400">
                                {t('conv.resetPreview.typeHint')}
                            </p>
                        </div>
                    )
                }
            />
        </div>
    );
}
