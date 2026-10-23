import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ComponentType, KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react';
import {
    AlertTriangle,
    BarChart3,
    Bell,
    BookOpen,
    Bot,
    Boxes,
    CheckCircle2,
    ClipboardList,
    Clock,
    FileText,
    History,
    Inbox,
    LifeBuoy,
    MessageCircle,
    Package,
    RefreshCw,
    RotateCcw,
    Save,
    Search,
    Send,
    Settings,
    ShieldCheck,
    SlidersHorizontal,
    Trash2,
    TrendingUp,
} from 'lucide-react';
import AcceptanceDemo from '@/components/AcceptanceDemo';
import ConversationsChart from '@/components/charts/ConversationsChart';
import EscalationReasonsChart from '@/components/charts/EscalationReasonsChart';
import FunnelEfficiencyChart from '@/components/charts/FunnelEfficiencyChart';
import SalesBarChart from '@/components/charts/SalesBarChart';
import SegmentPieChart from '@/components/charts/SegmentPieChart';
import AIQualityControlsPanel from '@/components/AIQualityControlsPanel';
import CanonicalSyncButton, { runCanonicalSync } from '@/components/CanonicalSyncButton';
import type { CanonicalSyncKind } from '@/components/CanonicalSyncButton';
import EnableManualModeButton, { scopesNeedingManualMode } from '@/components/EnableManualModeButton';
import { HelpTooltip, SectionInfoBanner } from '@/components/HelpTooltip';
import {
    approveKnowledgeBaseCandidate,
    archiveBotRule,
    createBotRule,
    createKnowledgeBaseEntry,
    executeConversationReset,
    fetchAdminAudit,
    fetchAdminConversation,
    fetchAdminCustomers,
    fetchBotRules,
    fetchKnowledgeBaseCandidates,
    fetchKnowledgeBaseEntries,
    previewBotRules,
    previewConversationReset,
    previewKnowledgeBaseEntry,
    reindexBotRule,
    reindexKnowledgeBaseEntry,
    rejectKnowledgeBaseCandidate,
    runBotQualityReview,
    softDeleteKnowledgeBaseEntry,
    updateBotRule,
    updateAdminConversation,
    updateKnowledgeBaseEntry,
} from '@/api/crm';
import {
    evaluateManagerReview,
    fetchAIQualityControls,
    fetchNotificationConfig,
    fetchPendingManagerReviews,
    fetchRecentManagerReviews,
    generateOperationsReport,
    sendTestNotification,
    syncProducts,
} from '@/api/operators';
import { useMetrics } from '@/hooks/useMetrics';
import { LanguageProvider, useI18n } from '@/i18n';
import type { Lang, TranslateFn, TranslationKey } from '@/i18n';
import { getAppRouteMode } from '@/routes';
import type { Period } from '@/types/metrics';
import type {
    AdminActionAuditRead,
    AdminBotRulePreviewResponse,
    AdminBotRuleRead,
    AdminBotRuleWrite,
    AdminConversationDetail,
    AdminCustomerListItem,
    AdminKnowledgeBaseCandidate,
    AdminKnowledgeBasePreview,
    AdminKnowledgeBaseRead,
    AdminKnowledgeBaseWrite,
    AdminResetPreview,
} from '@/types/crm';
import type {
    AIQualityControlsConfig,
    AIQualityScopeConfig,
    AIQualityScopeKey,
    ManagerReviewRead,
    NotificationConfig,
    OperationsReportResponse,
    PendingManagerReview,
    ProductSyncResponse,
    ProductSyncSource,
} from '@/types/operators';

const PERIODS: { labelKey: TranslationKey; value: Period }[] = [
    { labelKey: 'period.day', value: 'day' },
    { labelKey: 'period.week', value: 'week' },
    { labelKey: 'period.month', value: 'month' },
    { labelKey: 'period.all', value: 'all_time' },
];

const NAV_ITEMS = [
    { id: 'overview', labelKey: 'nav.overview', icon: BarChart3 },
    { id: 'conversations', labelKey: 'nav.conversations', icon: MessageCircle },
    { id: 'queues', labelKey: 'nav.queues', icon: Inbox },
    { id: 'knowledge', labelKey: 'nav.knowledge', icon: BookOpen },
    { id: 'botRules', labelKey: 'nav.botRules', icon: SlidersHorizontal },
    { id: 'catalog', labelKey: 'nav.catalog', icon: Boxes },
    { id: 'quality', labelKey: 'nav.quality', icon: ShieldCheck },
    { id: 'reports', labelKey: 'nav.reports', icon: FileText },
    { id: 'settings', labelKey: 'nav.settings', icon: Settings },
    { id: 'audit', labelKey: 'nav.audit', icon: History },
] as const satisfies readonly { id: string; labelKey: TranslationKey; icon: unknown }[];

type ViewId = (typeof NAV_ITEMS)[number]['id'] | 'support';
type ActionMessage = { tone: 'success' | 'error' | 'info'; text: string };
type StatusTone = 'gray' | 'amber' | 'green' | 'blue';

/** Views whose list is filtered by the header search box. */
const SEARCHABLE_VIEWS: ViewId[] = ['conversations', 'queues', 'knowledge', 'botRules', 'quality', 'audit'];

const EMPTY_KB_FORM: AdminKnowledgeBaseWrite = {
    source: 'manual',
    title: '',
    content: '',
    language: 'en',
    category: 'faq',
};

const EMPTY_BOT_RULE_FORM: AdminBotRuleWrite = {
    title: '',
    type: 'playbook',
    status: 'draft',
    priority: 100,
    scope: 'global',
    stage: null,
    language: 'en',
    segment: null,
    instruction: '',
    trigger_examples: [],
};

function qualityControlBlockMessage(
    scopeConfig: AIQualityScopeConfig,
    labelText: string,
    t: TranslateFn,
): string | null {
    if (scopeConfig.mode === 'disabled') {
        return t('qcBlock.disabled', { label: labelText });
    }
    if (scopeConfig.daily_budget_cents <= 0) {
        return t('qcBlock.zeroBudget', { label: labelText });
    }
    if (scopeConfig.max_calls_per_run <= 0) {
        return t('qcBlock.zeroPerRun', { label: labelText });
    }
    if (scopeConfig.max_calls_per_day <= 0) {
        return t('qcBlock.zeroPerDay', { label: labelText });
    }
    return null;
}

interface QualityControlBlock {
    message: string | null;
    config: AIQualityControlsConfig | null;
    reload: () => void;
}

function useAIQualityControlBlock(
    scope: AIQualityScopeKey,
    labelText: string,
): QualityControlBlock {
    const { t } = useI18n();
    const [config, setConfig] = useState<AIQualityControlsConfig | null>(null);
    const [version, setVersion] = useState(0);

    useEffect(() => {
        let mounted = true;
        fetchAIQualityControls()
            .then((response) => {
                if (mounted) setConfig(response.config);
            })
            .catch(() => {
                if (mounted) setConfig(null);
            });
        return () => {
            mounted = false;
        };
    }, [version]);

    const reload = useCallback(() => setVersion((current) => current + 1), []);
    const message = config ? qualityControlBlockMessage(config[scope], labelText, t) : null;
    return { message, config, reload };
}

/** Maps backend manual-run gate reasons to a localized hint. */
function localizeQualityGateError(message: string, t: TranslateFn): string {
    if (message.includes('daily_budget_exhausted')) return `${message} ${t('qcBlock.budgetExhausted')}`;
    if (message.includes('daily_call_quota_exhausted')) return `${message} ${t('qcBlock.quotaExhausted')}`;
    return message;
}

function QualityBlockNotice({ block }: { block: QualityControlBlock }) {
    if (!block.message) return null;
    const canEnable = scopesNeedingManualMode(block.config).length > 0;
    return (
        <div className="rounded-md border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]" data-quality-block="">
            <p>{block.message}</p>
            {canEnable && (
                <div className="mt-2">
                    <EnableManualModeButton config={block.config} onDone={() => block.reload()} />
                </div>
            )}
        </div>
    );
}

function matchesQuery(query: string, ...values: Array<string | number | null | undefined>): boolean {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return values.some((value) => value !== null && value !== undefined && String(value).toLowerCase().includes(needle));
}

export default function App({ initialLang }: { initialLang?: Lang } = {}) {
    const routeMode = getAppRouteMode();

    if (routeMode === 'acceptance-public') {
        return <PublicAcceptanceApp />;
    }

    return (
        <LanguageProvider initialLang={initialLang}>
            <DashboardApp />
        </LanguageProvider>
    );
}

function PublicAcceptanceApp() {
    return (
        <div className="min-h-screen bg-[#111827] px-4 py-6 sm:px-6 lg:px-8">
            <header className="mx-auto mb-8 max-w-7xl">
                <h1 className="text-2xl font-bold text-white">
                    <span className="text-[#2dd4bf]">TreeJar</span> Acceptance Demo
                </h1>
                <p className="mt-1 text-sm text-slate-400">
                    Прямая self-test страница для клиентской проверки WhatsApp, Telegram и backend-сценариев.
                </p>
            </header>
            <main className="mx-auto max-w-7xl">
                <AcceptanceDemo />
            </main>
        </div>
    );
}

function DashboardApp() {
    const { t, lang, setLang } = useI18n();
    const [activeView, setActiveView] = useState<ViewId>('conversations');
    const [period, setPeriod] = useState<Period>('all_time');
    const [globalSearchQuery, setGlobalSearchQuery] = useState('');
    const { data, timeseries, loading, error, refetch } = useMetrics(period);
    const activeNavItem = NAV_ITEMS.find((item) => item.id === activeView);
    const activeLabel = activeView === 'support' ? t('nav.support') : activeNavItem ? t(activeNavItem.labelKey) : '';
    const searchable = SEARCHABLE_VIEWS.includes(activeView);

    function handleSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
        if (event.key === 'Enter' && !searchable && globalSearchQuery.trim()) {
            setActiveView('conversations');
        }
        if (event.key === 'Escape') {
            setGlobalSearchQuery('');
        }
    }

    return (
        <div className="min-h-screen bg-[#f8f9ff] text-[#0b1c30]">
            <div className="flex min-h-screen">
                <aside className="flex w-[260px] shrink-0 flex-col border-r border-[#273247] bg-[#131b2e] p-4 text-[#fefcff]">
                    <div className="mb-4 flex items-center gap-3 px-2 py-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#0058be] text-sm font-bold text-white">
                            N
                        </div>
                        <div>
                            <h1 className="text-lg font-semibold leading-6 text-white">Noor AI</h1>
                            <p className="text-[11px] font-semibold uppercase leading-4 text-[#7c839b]">{t('app.controlPanel')}</p>
                        </div>
                    </div>
                    <div className="mb-6 rounded-lg border border-[#273247] bg-[#18243a] px-3 py-3">
                        <div className="flex items-center gap-2 text-sm font-semibold text-white">
                            <ShieldCheck size={16} />
                            <span>{t('app.monitoringMode')}</span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[#9ca3af]">
                            {t('app.monitoringModeNote')}
                        </p>
                    </div>
                    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
                        {NAV_ITEMS.map((item) => {
                            const Icon = item.icon;
                            const isActive = activeView === item.id;
                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    onClick={() => setActiveView(item.id)}
                                    className={cx(
                                        'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition',
                                        isActive
                                            ? 'bg-[#2170e4] text-white'
                                            : 'text-[#7c839b] hover:bg-[#0058be] hover:text-white',
                                    )}
                                >
                                    <Icon size={17} />
                                    <span>{t(item.labelKey)}</span>
                                </button>
                            );
                        })}
                    </nav>
                    <div className="mt-4 border-t border-[#273247] pt-4">
                        <button
                            type="button"
                            onClick={() => setActiveView('support')}
                            className={cx(
                                'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition',
                                activeView === 'support'
                                    ? 'bg-[#2170e4] text-white'
                                    : 'text-[#7c839b] hover:bg-[#0058be] hover:text-white',
                            )}
                        >
                            <LifeBuoy size={17} />
                            <span>{t('nav.support')}</span>
                        </button>
                    </div>
                </aside>

                <main className="min-w-0 flex-1">
                    <header className="flex h-16 items-center justify-between border-b border-[#c6c6cd] bg-[#f8f9ff] px-6">
                        <div className="flex items-center gap-5">
                            <h2 className="text-xl font-semibold text-[#000]">Noor CRM</h2>
                            <div className="relative flex items-center gap-1.5">
                                <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                                <input
                                    type="search"
                                    value={globalSearchQuery}
                                    onChange={(event) => setGlobalSearchQuery(event.target.value)}
                                    onKeyDown={handleSearchKeyDown}
                                    aria-label={t('header.searchLabel')}
                                    placeholder={searchable ? t('header.searchPlaceholder') : t('header.searchPlaceholderJump')}
                                    className="h-9 w-[300px] rounded-lg border border-[#c6c6cd] bg-[#eff4ff] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                                />
                                <HelpTooltip text={t('header.searchHelp')} />
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {activeView === 'overview' && (
                                <SegmentedControl
                                    items={PERIODS.map((item) => ({ label: t(item.labelKey), value: item.value }))}
                                    value={period}
                                    onChange={setPeriod}
                                />
                            )}
                            <div role="group" aria-label={t('header.language')} className="flex rounded-md border border-[#c6c6cd] bg-[#f8f9ff] p-1" data-lang-toggle="">
                                {(['ru', 'en'] as const).map((code) => (
                                    <button
                                        key={code}
                                        type="button"
                                        aria-pressed={lang === code}
                                        onClick={() => setLang(code)}
                                        className={cx(
                                            'rounded px-2.5 py-1 text-xs font-semibold',
                                            lang === code ? 'bg-white text-[#0058be] shadow-sm' : 'text-[#45464d] hover:text-[#0b1c30]',
                                        )}
                                    >
                                        {code.toUpperCase()}
                                    </button>
                                ))}
                            </div>
                            <button
                                type="button"
                                onClick={() => void refetch()}
                                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[#c6c6cd] bg-white text-[#3f465c] hover:bg-[#f2f4f7]"
                                aria-label={t('common.refresh')}
                            >
                                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                            </button>
                            <div className="ml-2 flex h-9 items-center gap-2 border-l border-[#c6c6cd] pl-4 text-sm font-medium text-[#0b1c30]">
                                <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[#c6c6cd] bg-[#d8e2ff] text-[#004395]">
                                    <Settings size={15} />
                                </div>
                                <span>{t('header.admin')}</span>
                            </div>
                        </div>
                    </header>

                    <div className="border-b border-[#e5e7eb] bg-white px-6 py-4">
                        <p className="text-xs font-semibold uppercase text-[#45464d]">
                            {activeLabel}
                        </p>
                        <h2 className="mt-1 text-2xl font-semibold text-[#0b1c30]">
                            {activeView === 'conversations'
                                ? t('nav.conversations')
                                : activeView === 'botRules'
                                    ? t('botRules.pageTitle')
                                    : activeLabel}
                        </h2>
                    </div>

                    {error && activeView === 'overview' && (
                        <div className="border-b border-[#fecaca] bg-[#fff1f2] px-6 py-3 text-sm text-[#be123c]">
                            <AlertTriangle size={16} className="mr-2 inline" />
                            {error}
                        </div>
                    )}

                    {activeView === 'overview' && (
                        <OverviewView
                            data={data}
                            timeseries={timeseries?.points ?? []}
                            refetch={refetch}
                        />
                    )}
                    {activeView === 'conversations' && <ConversationsView globalSearch={globalSearchQuery} />}
                    {activeView === 'queues' && <QueuesView globalSearch={globalSearchQuery} />}
                    {activeView === 'knowledge' && <KnowledgeBaseView globalSearch={globalSearchQuery} />}
                    {activeView === 'botRules' && <BotRulesView globalSearch={globalSearchQuery} />}
                    {activeView === 'catalog' && <CatalogView />}
                    {activeView === 'quality' && <QualityView refetch={refetch} globalSearch={globalSearchQuery} />}
                    {activeView === 'reports' && <ReportsView />}
                    {activeView === 'settings' && <SettingsView />}
                    {activeView === 'audit' && <AuditView globalSearch={globalSearchQuery} />}
                    {activeView === 'support' && <SupportView />}
                </main>
            </div>
        </div>
    );
}

/** Section guide banner with translated copy keyed by view id. */
function ViewBanner({ view, actions }: { view: ViewId; actions?: ReactNode }) {
    const { t } = useI18n();
    return (
        <SectionInfoBanner
            storageKey={view}
            title={t(`banner.${view}.title` as TranslationKey)}
            description={t(`banner.${view}.body` as TranslationKey)}
            runtime={t(`banner.${view}.runtime` as TranslationKey)}
            actions={actions}
        />
    );
}

function OverviewView({
    data,
    timeseries,
    refetch,
}: {
    data: ReturnType<typeof useMetrics>['data'];
    timeseries: { date: string; new: number; returning: number }[];
    refetch: () => void;
}) {
    const { t } = useI18n();
    if (!data) {
        return (
            <>
                <ViewBanner view="overview" />
                <section className="p-6">
                    <div className="grid grid-cols-4 gap-3">
                        {Array.from({ length: 4 }).map((_, index) => (
                            <div key={index} className="h-24 rounded-md bg-white shadow-sm" />
                        ))}
                    </div>
                </section>
            </>
        );
    }

    return (
        <>
            <ViewBanner view="overview" />
            <section className="space-y-5 p-6">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <MetricTile label={t('metric.conversations')} help={t('metric.conversationsHelp')} value={data.total_conversations} note={t('metric.customersCount', { count: data.unique_customers })} />
                    <MetricTile label={t('metric.escalations')} help={t('metric.escalationsHelp')} value={data.escalation_count} note={t('metric.managerQueue')} tone="amber" />
                    <MetricTile label={t('metric.conversion')} help={t('metric.conversionHelp')} value={`${data.conversion_rate}%`} note={t('metric.dealsCount', { count: data.noor_sales.count + data.post_escalation_sales.count })} tone="green" />
                    <MetricTile label={t('metric.quality')} help={t('metric.qualityHelp')} value={`${data.avg_quality_score}/30`} note={t('metric.managersScore', { score: data.avg_manager_score })} tone="blue" />
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                    <ConversationsChart points={timeseries} totalConversations={data.total_conversations} />
                    <SegmentPieChart byLanguage={data.by_language} targetVsNontarget={data.target_vs_nontarget} />
                    <SalesBarChart
                        noorSales={data.noor_sales}
                        postEscalationSales={data.post_escalation_sales}
                        conversionRate={data.conversion_rate}
                        escalationCount={data.escalation_count}
                    />
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <EscalationReasonsChart byReason={data.escalation_by_reason} rawReasons={data.escalation_reasons} />
                    <FunnelEfficiencyChart data={data} />
                </div>

                <OverviewActionPanel data={data} refetch={refetch} />
            </section>
        </>
    );
}

function SupportView() {
    const { t } = useI18n();
    return (
        <>
            <ViewBanner view="support" />
            <section className="space-y-5 p-6">
                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
                    <Panel
                        title={t('support.title')}
                        subtitle={t('support.subtitle')}
                        icon={LifeBuoy}
                    >
                        <div className="space-y-3">
                            <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <p className="text-sm font-semibold text-[#0b1c30]">{t('support.telegramTitle')}</p>
                                <p className="mt-1 text-sm leading-6 text-[#45464d]">
                                    {t('support.telegramBody')}
                                </p>
                            </div>
                            <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <p className="text-sm font-semibold text-[#0b1c30]">{t('support.runtimeTitle')}</p>
                                <p className="mt-1 text-sm leading-6 text-[#45464d]">https://noor.starec.ai</p>
                            </div>
                        </div>
                    </Panel>

                    <Panel
                        title={t('support.smokeTitle')}
                        subtitle={t('support.smokeSubtitle')}
                        icon={ShieldCheck}
                    >
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <StatusCard title={t('support.auth')} value="401/200" note={t('support.authNote')} tone="green" />
                            <StatusCard title="CRM" value={t('support.crmValue')} note={t('support.crmNote')} tone="blue" />
                            <StatusCard title={t('support.mutation')} value={t('support.mutationValue')} note={t('support.mutationNote')} tone="amber" />
                            <StatusCard title={t('support.deploy')} value={t('support.deployValue')} note={t('support.deployNote')} />
                        </div>
                    </Panel>
                </div>
            </section>
        </>
    );
}

function ConversationsView({ globalSearch = '' }: { globalSearch?: string }) {
    const { t, label, formatDate } = useI18n();
    const [search, setSearch] = useState(globalSearch);
    const [status, setStatus] = useState('');
    const [customers, setCustomers] = useState<AdminCustomerListItem[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [detail, setDetail] = useState<AdminConversationDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const [actionBusy, setActionBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [resetPreview, setResetPreview] = useState<AdminResetPreview | null>(null);
    const [resetMessage, setResetMessage] = useState<ActionMessage | null>(null);
    const [reloadToken, setReloadToken] = useState(0);
    const botQa = useAIQualityControlBlock('bot_qa', 'Bot QA');
    const botQaBlock = botQa.message;

    useEffect(() => {
        setSearch(globalSearch);
    }, [globalSearch]);

    useEffect(() => {
        let cancelled = false;
        const params = new URLSearchParams({ page_size: '100' });
        if (search.trim()) params.set('search', search.trim());
        if (status) params.set('status', status);

        setLoading(true);
        fetchAdminCustomers(params)
            .then((payload) => {
                if (cancelled) return;
                setCustomers(payload.items);
                if (!selectedId && payload.items[0]) {
                    setSelectedId(payload.items[0].latest_conversation_id);
                }
                setError(null);
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(errorMessage(err, t));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [search, selectedId, status, reloadToken, t]);

    useEffect(() => {
        if (!selectedId) return;
        let cancelled = false;
        setResetPreview(null);
        fetchAdminConversation(selectedId)
            .then((payload) => {
                if (!cancelled) setDetail(payload);
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(errorMessage(err, t));
            });
        return () => {
            cancelled = true;
        };
    }, [selectedId, t]);

    async function patchConversation(payload: Parameters<typeof updateAdminConversation>[1]) {
        if (!detail) return;
        setActionBusy(true);
        try {
            const updated = await updateAdminConversation(detail.id, payload);
            setDetail(updated);
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setActionBusy(false);
        }
    }

    async function handleResetPreview() {
        if (!detail || !globalThis.confirm(t('conv.confirmResetPreview'))) return;
        setActionBusy(true);
        setResetMessage(null);
        try {
            setResetPreview(await previewConversationReset(detail.id));
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setActionBusy(false);
        }
    }

    async function handleResetExecute() {
        if (!detail || !resetPreview || !globalThis.confirm(t('conv.confirmResetExecute', { phone: resetPreview.phone }))) return;
        setActionBusy(true);
        try {
            const result = await executeConversationReset(detail.id);
            setResetPreview(null);
            setResetMessage({ tone: 'success', text: t('conv.resetDone', { count: result.archived_count }) });
            if (result.new_conversation_id) {
                setSelectedId(result.new_conversation_id);
            }
            setReloadToken((current) => current + 1);
        } catch (err) {
            setResetMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setActionBusy(false);
        }
    }

    async function handleBotQa() {
        if (!detail || botQaBlock || !globalThis.confirm(t('conv.confirmBotQa'))) return;
        setActionBusy(true);
        try {
            await runBotQualityReview(detail.id);
            const updated = await fetchAdminConversation(detail.id);
            setDetail(updated);
        } catch (err) {
            setError(localizeQualityGateError(errorMessage(err, t), t));
        } finally {
            setActionBusy(false);
        }
    }

    function roleLabel(role: string): string {
        if (role === 'user') return t('conv.roleCustomer');
        if (role === 'assistant') return t('conv.roleBot');
        return t('conv.roleManager');
    }

    return (
        <>
            <ViewBanner view="conversations" />
            <section className="grid h-[calc(100vh-145px)] grid-cols-[320px_minmax(360px,1fr)_340px] overflow-hidden">
                <div className="border-r border-[#c6c6cd] bg-white">
                    <div className="space-y-3 border-b border-[#c6c6cd] p-4">
                        <div className="flex items-center gap-1.5">
                            <div className="relative flex-1">
                                <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                                <input
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder={t('conv.searchPlaceholder')}
                                    className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                                />
                            </div>
                            <HelpTooltip text={t('conv.searchHelp')} />
                        </div>
                        <div className="flex items-center gap-1.5">
                            <select
                                value={status}
                                onChange={(event) => setStatus(event.target.value)}
                                aria-label={t('common.status')}
                                className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                            >
                                <option value="">{t('common.allStatuses')}</option>
                                <option value="active">{t('conv.filterActive')}</option>
                                <option value="paused">{t('status.paused')}</option>
                                <option value="closed">{t('conv.filterClosed')}</option>
                                <option value="escalated">{t('status.escalated')}</option>
                            </select>
                            <HelpTooltip text={t('conv.statusHelp')} />
                        </div>
                    </div>
                    <div className="h-[calc(100%-112px)] overflow-auto">
                        {loading && <StateLine text={t('conv.loading')} />}
                        {error && <StateLine text={error} tone="red" />}
                        {!loading && customers.length === 0 && <StateLine text={t('conv.empty')} />}
                        {customers.map((customer) => (
                            <button
                                key={`${customer.phone}-${customer.latest_conversation_id}`}
                                type="button"
                                onClick={() => setSelectedId(customer.latest_conversation_id)}
                                className={cx(
                                    'block w-full border-b border-[#e5eeff] px-4 py-3 text-left hover:bg-[#f4f7f9]',
                                    selectedId === customer.latest_conversation_id && 'bg-[#eff4ff]',
                                )}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="truncate text-sm font-semibold text-[#0b1c30]">
                                        {customer.customer_name || customer.phone}
                                    </p>
                                    <Badge label={label(customer.status)} />
                                </div>
                                <p className="mt-1 truncate text-xs text-[#45464d]">{customer.phone}</p>
                                <p className="mt-2 line-clamp-2 text-sm text-[#3f465c]">
                                    {customer.latest_message_preview || t('conv.noMessages')}
                                </p>
                                <div className="mt-2 flex items-center gap-2 text-xs text-[#45464d]">
                                    <span>{label(customer.sales_stage)}</span>
                                    <span>·</span>
                                    <span>{t('conv.dialogsCount', { count: customer.conversation_count })}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex min-w-0 flex-col bg-[#f8f9ff]">
                    <div className="border-b border-[#c6c6cd] bg-white px-5 py-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-semibold text-[#0b1c30]">
                                    {detail?.customer_name || detail?.phone || t('conv.noDialog')}
                                </p>
                                <p className="text-xs text-[#45464d]">
                                    {detail
                                        ? `${detail.phone} · ${label(detail.sales_stage)} · ${t('conv.messagesCount', { count: detail.message_count })}`
                                        : t('conv.selectLeft')}
                                </p>
                            </div>
                            {detail && <Badge label={label(detail.escalation_status)} tone="amber" />}
                        </div>
                    </div>
                    <div className="flex-1 space-y-3 overflow-auto px-6 py-5">
                        {!detail && <StateLine text={t('conv.selectToOpen')} />}
                        {detail?.timeline.map((message) => (
                            <div
                                key={message.id}
                                className={cx(
                                    'max-w-[78%] rounded-md border px-4 py-3 text-sm shadow-sm',
                                    message.role === 'user'
                                        ? 'border-[#c6c6cd] bg-white'
                                        : 'ml-auto border-[#adc6ff] bg-[#eff4ff]',
                                )}
                            >
                                <div className="mb-1 flex items-center justify-between gap-3 text-xs text-[#45464d]">
                                    <span>{roleLabel(message.role)}</span>
                                    <span>{formatDate(message.created_at)}</span>
                                </div>
                                <p className="whitespace-pre-wrap leading-6 text-[#0b1c30]">{message.content}</p>
                            </div>
                        ))}
                    </div>
                </div>

                <aside className="overflow-auto border-l border-[#c6c6cd] bg-white">
                    <div className="space-y-4 p-4">
                        <InspectorBlock title="CRM" help={t('conv.inspector.crmHelp')}>
                            <Field label={t('conv.field.name')} value={detail?.customer_name || '—'} />
                            <Field label={t('conv.field.phone')} value={detail?.phone || '—'} />
                            <Field label={t('conv.field.language')} value={detail?.language || '—'} />
                            <Field label={t('conv.field.zohoContact')} value={detail?.zoho_contact_id || '—'} />
                            <Field label={t('conv.field.zohoDeal')} value={detail?.zoho_deal_id || '—'} />
                        </InspectorBlock>

                        <InspectorBlock title={t('conv.inspector.stage')} help={t('conv.inspector.stageHelp')}>
                            <Field label={t('common.status')} value={detail ? label(detail.status) : '—'} />
                            <Field label={t('conv.field.stage')} value={detail ? label(detail.sales_stage) : '—'} />
                            <Field label={t('conv.field.deal')} value={detail?.deal_status ? label(detail.deal_status) : '—'} />
                            <Field label={t('conv.field.amount')} value={detail?.deal_amount ? `${detail.deal_amount} AED` : '—'} />
                        </InspectorBlock>

                        <InspectorBlock title={t('conv.inspector.actions')} help={t('conv.inspector.actionsHelp')}>
                            {botQaBlock && <QualityBlockNotice block={botQa} />}
                            <div className="grid grid-cols-2 gap-2">
                                <IconButton
                                    icon={CheckCircle2}
                                    label={t('conv.action.close')}
                                    disabled={!detail || actionBusy}
                                    onClick={() => void patchConversation({ status: 'closed' })}
                                />
                                <IconButton
                                    icon={Bot}
                                    label="Bot QA"
                                    disabled={!detail || actionBusy || Boolean(botQaBlock)}
                                    onClick={() => void handleBotQa()}
                                />
                                <IconButton
                                    icon={RotateCcw}
                                    label={t('conv.action.resetPreview')}
                                    disabled={!detail || actionBusy}
                                    onClick={() => void handleResetPreview()}
                                />
                                <IconButton
                                    icon={AlertTriangle}
                                    label={t('conv.action.escalate')}
                                    disabled={!detail || actionBusy}
                                    onClick={() => void patchConversation({ status: 'escalated', escalation_status: 'manual_takeover' })}
                                />
                            </div>
                            {resetMessage && <ActionMessageBox message={resetMessage} />}
                            {resetPreview && (
                                <ResetPreviewCard
                                    preview={resetPreview}
                                    busy={actionBusy}
                                    onConfirm={() => void handleResetExecute()}
                                    onCancel={() => setResetPreview(null)}
                                />
                            )}
                        </InspectorBlock>

                        <InspectorBlock title={t('conv.inspector.scores')} help={t('conv.inspector.scoresHelp')}>
                            <Field label="Bot QA" value={detail?.quality_reviews[0] ? `${detail.quality_reviews[0].total_score}/${detail.quality_reviews[0].max_score}` : '—'} />
                            <Field label="Manager QA" value={detail?.manager_reviews[0] ? `${detail.manager_reviews[0].total_score}/${detail.manager_reviews[0].max_score}` : '—'} />
                            <Field label={t('metric.escalations')} value={String(detail?.escalations.length ?? 0)} />
                            <Field label={t('conv.field.outbound')} value={String(detail?.outbound_audits.length ?? 0)} />
                        </InspectorBlock>

                        <InspectorBlock title={t('conv.inspector.appliedRules')} help={t('conv.inspector.appliedRulesHelp')}>
                            {!detail?.applied_bot_rules.length && <StateLine text={t('conv.noRulesApplied')} />}
                            {detail?.applied_bot_rules.map((rule) => (
                                <div key={rule.id} className="border-b border-[#e5eeff] py-2">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="truncate text-sm font-semibold text-[#0b1c30]">{rule.title}</p>
                                        <Badge label={`P${rule.priority}`} tone="green" />
                                    </div>
                                    <p className="mt-1 text-xs text-[#45464d]">{label(rule.type)} · {label(rule.scope)}</p>
                                </div>
                            ))}
                        </InspectorBlock>
                    </div>
                </aside>
            </section>
        </>
    );
}

function ResetPreviewCard({
    preview,
    busy,
    onConfirm,
    onCancel,
}: {
    preview: AdminResetPreview;
    busy: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}) {
    const { t } = useI18n();
    return (
        <div className="space-y-2 rounded-md border border-[#f59e0b] bg-[#fff7ed] p-3 text-sm" data-reset-preview-card="">
            <p className="font-semibold text-[#92400e]">{t('reset.title')}</p>
            <Field label={t('conv.field.phone')} value={preview.phone} />
            <Field label={t('reset.variants')} value={preview.phone_variants.join(', ') || '—'} />
            <Field label={t('reset.conversations')} value={String(preview.conversation_count)} />
            <Field label={t('reset.messages')} value={String(preview.message_count)} />
            <Field label={t('reset.pendingEscalations')} value={String(preview.pending_escalation_count)} />
            <Field label={t('reset.latestConversation')} value={preview.latest_conversation_id || '—'} />
            <p className="text-xs leading-5 text-[#92400e]">{t('reset.warning')}</p>
            <div className="flex gap-2 pt-1">
                <button
                    type="button"
                    disabled={busy}
                    onClick={onConfirm}
                    className="rounded-md bg-[#be123c] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#9f1239] disabled:opacity-50"
                >
                    {t('reset.confirm')}
                </button>
                <button
                    type="button"
                    disabled={busy}
                    onClick={onCancel}
                    className="rounded-md border border-[#c6c6cd] bg-white px-3 py-1.5 text-xs font-medium text-[#3f465c] hover:bg-[#f2f4f7] disabled:opacity-50"
                >
                    {t('common.cancel')}
                </button>
            </div>
        </div>
    );
}

const autoSeededCanonicalKinds = new Set<CanonicalSyncKind>();

function KnowledgeBaseView({ globalSearch = '' }: { globalSearch?: string }) {
    const { t, label } = useI18n();
    const [entries, setEntries] = useState<AdminKnowledgeBaseRead[]>([]);
    const [candidates, setCandidates] = useState<AdminKnowledgeBaseCandidate[]>([]);
    const [selected, setSelected] = useState<AdminKnowledgeBaseRead | null>(null);
    const [form, setForm] = useState<AdminKnowledgeBaseWrite>(EMPTY_KB_FORM);
    const [preview, setPreview] = useState<AdminKnowledgeBasePreview | null>(null);
    const [search, setSearch] = useState(globalSearch);
    const [loaded, setLoaded] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        setSearch(globalSearch);
    }, [globalSearch]);

    const load = useMemo(
        () => async () => {
            const params = new URLSearchParams({ page_size: '50' });
            if (search.trim()) params.set('search', search.trim());
            let [entryPayload, candidatePayload] = await Promise.all([
                fetchKnowledgeBaseEntries(params),
                fetchKnowledgeBaseCandidates(new URLSearchParams({ status: 'needs_confirmation' })),
            ]);
            if (!search.trim() && entryPayload.items.length === 0 && !autoSeededCanonicalKinds.has('knowledge')) {
                autoSeededCanonicalKinds.add('knowledge');
                try {
                    await runCanonicalSync('knowledge');
                    entryPayload = await fetchKnowledgeBaseEntries(params);
                } catch {
                    // Keep empty state visible if background auto-seed fails.
                }
            }
            setEntries(entryPayload.items);
            setCandidates(candidatePayload.items);
            setLoaded(true);
            if (!selected && entryPayload.items[0]) {
                setSelected(entryPayload.items[0]);
                setForm(entryToForm(entryPayload.items[0]));
            }
        },
        [search, selected],
    );

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err, t)));
    }, [load, t]);

    async function handlePreview() {
        setBusy(true);
        try {
            setPreview(await previewKnowledgeBaseEntry(form));
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleSave() {
        setBusy(true);
        try {
            const saved = selected
                ? await updateKnowledgeBaseEntry(selected.id, form)
                : await createKnowledgeBaseEntry(form);
            setSelected(saved);
            setForm(entryToForm(saved));
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleDelete(entry: AdminKnowledgeBaseRead | null) {
        if (!entry || !globalThis.confirm(t('kb.confirmDelete'))) return;
        setBusy(true);
        try {
            await softDeleteKnowledgeBaseEntry(entry.id);
            setEntries((current) => current.filter((item) => item.id !== entry.id));
            setSelected(null);
            setForm(EMPTY_KB_FORM);
            setPreview(null);
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleReindex() {
        if (!selected) return;
        setBusy(true);
        try {
            const updated = await reindexKnowledgeBaseEntry(selected.id);
            setSelected(updated);
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleApprove(candidateId: string) {
        setBusy(true);
        try {
            const entry = await approveKnowledgeBaseCandidate(candidateId);
            setSelected(entry);
            setForm(entryToForm(entry));
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleReject(candidateId: string) {
        if (!globalThis.confirm(t('kb.confirmRejectCandidate'))) return;
        setBusy(true);
        try {
            await rejectKnowledgeBaseCandidate(candidateId, { reason: 'admin_rejected' });
            setCandidates((current) => current.filter((candidate) => candidate.id !== candidateId));
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleCanonicalSynced() {
        setSelected(null);
        await load();
    }

    return (
        <>
            <ViewBanner
                view="knowledge"
                actions={<CanonicalSyncButton kind="knowledge" onSynced={handleCanonicalSynced} />}
            />
            <section className="grid h-[calc(100vh-145px)] grid-cols-[300px_minmax(420px,1fr)_360px] overflow-hidden">
                <div className="border-r border-[#c6c6cd] bg-white">
                    <div className="border-b border-[#c6c6cd] p-4">
                        <div className="flex items-center gap-1.5">
                            <div className="relative flex-1">
                                <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                                <input
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder={t('kb.searchPlaceholder')}
                                    className="h-9 w-full rounded-md border border-[#c6c6cd] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                                />
                            </div>
                            <HelpTooltip text={t('kb.searchHelp')} />
                        </div>
                    </div>
                    <div className="h-[calc(100%-73px)] overflow-auto">
                        {loaded && entries.length === 0 && (
                            <div className="m-4 space-y-3 rounded-md border border-dashed border-[#adc6ff] bg-[#f8f9ff] p-4 text-sm text-[#3f465c]">
                                <p className="font-semibold text-[#0b1c30]">{t('kb.emptyTitle')}</p>
                                <p>{t('kb.emptyBody')}</p>
                                <CanonicalSyncButton kind="knowledge" prominent onSynced={handleCanonicalSynced} />
                            </div>
                        )}
                        {entries.map((entry) => (
                            <button
                                key={entry.id}
                                type="button"
                                onClick={() => {
                                    setSelected(entry);
                                    setForm(entryToForm(entry));
                                    setPreview(null);
                                }}
                                className={cx(
                                    'block w-full border-b border-[#e5eeff] px-4 py-3 text-left hover:bg-[#f4f7f9]',
                                    selected?.id === entry.id && 'bg-[#eff4ff]',
                                )}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="truncate text-sm font-semibold text-[#0b1c30]">{entry.title}</p>
                                    <Badge label={entry.has_embedding ? t('kb.indexed') : t('kb.notIndexed')} tone={entry.has_embedding ? 'green' : 'amber'} />
                                </div>
                                <p className="mt-1 line-clamp-2 text-sm text-[#45464d]">{entry.content}</p>
                                <p className="mt-2 text-xs text-[#45464d]">{entry.source} · {entry.language} · {entry.category || '—'}</p>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="overflow-auto bg-[#f8f9ff] p-5">
                    <div className="mb-4 flex items-center justify-between">
                        <h3 className="flex items-center gap-1.5 text-base font-semibold text-[#0b1c30]">
                            {t('kb.editor')}
                            <HelpTooltip text={t('kb.editorHelp')} />
                        </h3>
                        <button
                            type="button"
                            onClick={() => {
                                setSelected(null);
                                setForm(EMPTY_KB_FORM);
                                setPreview(null);
                            }}
                            className="rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                        >
                            {t('kb.newEntry')}
                        </button>
                    </div>
                    {error && <StateLine text={error} tone="red" />}
                    <div className="space-y-3 rounded-md border border-[#c6c6cd] bg-white p-4">
                        <Input label={t('kb.field.title')} help={t('kb.help.title')} value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
                        <div className="grid grid-cols-3 gap-3">
                            <Input label={t('kb.field.source')} help={t('kb.help.source')} value={form.source} onChange={(value) => setForm({ ...form, source: value })} />
                            <Select
                                label={t('common.language')}
                                help={t('kb.help.language')}
                                value={form.language}
                                options={[
                                    { label: 'EN', value: 'en' },
                                    { label: 'AR', value: 'ar' },
                                ]}
                                onChange={(value) => setForm({ ...form, language: value as 'en' | 'ar' })}
                            />
                            <Input label={t('kb.field.category')} help={t('kb.help.category')} value={form.category || ''} onChange={(value) => setForm({ ...form, category: value || null })} />
                        </div>
                        <TextArea
                            label={t('kb.field.content')}
                            help={t('kb.help.content')}
                            value={form.content}
                            onChange={(value) => setForm({ ...form, content: value })}
                            className="min-h-[220px]"
                        />
                        <div className="flex flex-wrap gap-2">
                            <IconButton icon={Search} label={t('common.preview')} disabled={busy} onClick={() => void handlePreview()} />
                            <IconButton icon={Save} label={t('common.saveAndIndex')} disabled={busy} onClick={() => void handleSave()} />
                            <IconButton icon={RefreshCw} label={t('common.reindex')} disabled={!selected || busy} onClick={() => void handleReindex()} />
                            <IconButton icon={Trash2} label={t('kb.softDelete')} disabled={!selected || busy} onClick={() => void handleDelete(selected)} danger />
                        </div>
                    </div>
                </div>

                <aside className="overflow-auto border-l border-[#c6c6cd] bg-white p-4">
                    <InspectorBlock title={t('kb.previewTitle')} help={t('kb.previewHelp')}>
                        <Field label={t('kb.embedding')} value={preview?.embedding_ready ? t('kb.ready') : '—'} />
                        <Field label={t('kb.duplicate')} value={preview?.duplicate ? t('common.yes') : t('common.no')} />
                        <Field label={t('kb.similarity')} value={preview?.duplicate_similarity ? preview.duplicate_similarity.toFixed(3) : '—'} />
                        <Field label={t('kb.unsafe')} value={preview?.unsafe_reasons.join(', ') || '—'} />
                        <Field label={t('kb.context')} value={preview?.context_reasons.join(', ') || '—'} />
                    </InspectorBlock>

                    <div className="mt-4">
                        <InspectorBlock title={t('kb.autoFaqTitle')} help={t('kb.autoFaqHelp')}>
                            {candidates.length === 0 && <StateLine text={t('kb.noCandidates')} />}
                            {candidates.map((candidate) => (
                                <div key={candidate.id} className="border-b border-[#e5eeff] py-3">
                                    <p className="text-sm font-semibold text-[#0b1c30]">{candidate.question}</p>
                                    <p className="mt-1 line-clamp-3 text-sm text-[#45464d]">{candidate.answer}</p>
                                    <div className="mt-2 flex items-center justify-between gap-2">
                                        <Badge label={label(candidate.status)} />
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() => void handleReject(candidate.id)}
                                                className="rounded-md border border-[#fecaca] bg-white px-3 py-1.5 text-xs font-medium text-[#be123c] hover:bg-[#fff1f2] disabled:opacity-50"
                                            >
                                                {t('common.reject')}
                                            </button>
                                            <button
                                                type="button"
                                                disabled={busy}
                                                onClick={() => void handleApprove(candidate.id)}
                                                className="rounded-md bg-[#0058be] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                            >
                                                {t('common.approve')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </InspectorBlock>
                    </div>
                </aside>
            </section>
        </>
    );
}

function BotRulesView({ globalSearch = '' }: { globalSearch?: string }) {
    const { t, label } = useI18n();
    const [rules, setRules] = useState<AdminBotRuleRead[]>([]);
    const [selected, setSelected] = useState<AdminBotRuleRead | null>(null);
    const [form, setForm] = useState<AdminBotRuleWrite>(EMPTY_BOT_RULE_FORM);
    const [preview, setPreview] = useState<AdminBotRulePreviewResponse | null>(null);
    const [search, setSearch] = useState(globalSearch);
    const [status, setStatus] = useState('active');
    const [testMessage, setTestMessage] = useState('Customer says: I need 20 chairs for my office');
    const [loaded, setLoaded] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        setSearch(globalSearch);
    }, [globalSearch]);

    const load = useMemo(
        () => async () => {
            const params = new URLSearchParams({ page_size: '50' });
            if (search.trim()) params.set('search', search.trim());
            if (status) params.set('status', status);
            let payload = await fetchBotRules(params);
            if (!search.trim() && status === 'active' && payload.items.length === 0 && !autoSeededCanonicalKinds.has('botRules')) {
                autoSeededCanonicalKinds.add('botRules');
                try {
                    await runCanonicalSync('botRules');
                    payload = await fetchBotRules(params);
                } catch {
                    // Keep empty state visible if background auto-seed fails.
                }
            }
            setRules(payload.items);
            setLoaded(true);
            if (!selected && payload.items[0]) {
                setSelected(payload.items[0]);
                setForm(ruleToForm(payload.items[0]));
            }
        },
        [search, selected, status],
    );

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err, t)));
    }, [load, t]);

    async function handlePreview() {
        setBusy(true);
        try {
            setPreview(
                await previewBotRules({
                    message: testMessage,
                    stage: form.stage,
                    language: form.language,
                    segment: form.segment,
                }),
            );
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleSave() {
        setBusy(true);
        try {
            const saved = selected
                ? await updateBotRule(selected.id, form)
                : await createBotRule(form);
            setSelected(saved);
            setForm(ruleToForm(saved));
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleArchive() {
        if (!selected || !globalThis.confirm(t('botRules.confirmArchive'))) return;
        setBusy(true);
        try {
            await archiveBotRule(selected.id);
            setSelected(null);
            setForm(EMPTY_BOT_RULE_FORM);
            setPreview(null);
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleReindex() {
        if (!selected) return;
        setBusy(true);
        try {
            const updated = await reindexBotRule(selected.id);
            setSelected(updated);
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleCanonicalSynced() {
        setSelected(null);
        await load();
    }

    return (
        <>
            <ViewBanner
                view="botRules"
                actions={<CanonicalSyncButton kind="botRules" onSynced={handleCanonicalSynced} />}
            />
            <section className="grid h-[calc(100vh-145px)] grid-cols-[300px_minmax(440px,1fr)_380px] overflow-hidden">
                <div className="border-r border-[#c6c6cd] bg-white">
                    <div className="space-y-3 border-b border-[#c6c6cd] p-4">
                        <div className="flex items-center gap-1.5">
                            <div className="relative flex-1">
                                <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                                <input
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder={t('botRules.searchPlaceholder')}
                                    className="h-9 w-full rounded-md border border-[#c6c6cd] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                                />
                            </div>
                            <HelpTooltip text={t('botRules.searchHelp')} />
                        </div>
                        <div className="flex items-center gap-1.5">
                            <select
                                value={status}
                                onChange={(event) => setStatus(event.target.value)}
                                aria-label={t('common.status')}
                                className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                            >
                                <option value="">{t('common.allStatuses')}</option>
                                <option value="active">{t('conv.filterActive')}</option>
                                <option value="draft">{t('botRules.filterDrafts')}</option>
                                <option value="archived">{t('status.archived')}</option>
                            </select>
                            <HelpTooltip text={t('botRules.statusHelp')} />
                        </div>
                    </div>
                    <div className="h-[calc(100%-121px)] overflow-auto">
                        {loaded && rules.length === 0 && (
                            status === 'active' && !search.trim() ? (
                                <div className="m-4 space-y-3 rounded-md border border-dashed border-[#adc6ff] bg-[#f8f9ff] p-4 text-sm text-[#3f465c]">
                                    <p className="font-semibold text-[#0b1c30]">{t('botRules.emptyTitle')}</p>
                                    <p>{t('botRules.emptyBody')}</p>
                                    <CanonicalSyncButton kind="botRules" prominent onSynced={handleCanonicalSynced} />
                                </div>
                            ) : (
                                <StateLine text={t('botRules.empty')} />
                            )
                        )}
                        {rules.map((rule) => (
                            <button
                                key={rule.id}
                                type="button"
                                onClick={() => {
                                    setSelected(rule);
                                    setForm(ruleToForm(rule));
                                    setPreview(null);
                                }}
                                className={cx(
                                    'block w-full border-b border-[#e5eeff] px-4 py-3 text-left hover:bg-[#f4f7f9]',
                                    selected?.id === rule.id && 'bg-[#eff4ff]',
                                )}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="truncate text-sm font-semibold text-[#0b1c30]">{rule.title}</p>
                                    <Badge label={label(rule.status)} tone={rule.status === 'active' ? 'green' : 'amber'} />
                                </div>
                                <p className="mt-1 line-clamp-2 text-sm text-[#45464d]">{rule.instruction}</p>
                                <p className="mt-2 text-xs text-[#45464d]">
                                    P{rule.priority} · {label(rule.type)} · {label(rule.scope)}
                                </p>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="overflow-auto bg-[#f8f9ff] p-5">
                    <div className="mb-4 flex items-center justify-between">
                        <h3 className="flex items-center gap-1.5 text-base font-semibold text-[#0b1c30]">
                            {t('botRules.editor')}
                            <HelpTooltip text={t('botRules.editorHelp')} />
                        </h3>
                        <button
                            type="button"
                            onClick={() => {
                                setSelected(null);
                                setForm(EMPTY_BOT_RULE_FORM);
                                setPreview(null);
                            }}
                            className="rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                        >
                            {t('botRules.newRule')}
                        </button>
                    </div>
                    {error && <StateLine text={error} tone="red" />}
                    <div className="space-y-3 rounded-md border border-[#c6c6cd] bg-white p-4">
                        <Input label={t('botRules.field.title')} help={t('botRules.help.title')} value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
                        <div className="grid grid-cols-2 gap-3">
                            <Select
                                label={t('botRules.field.type')}
                                help={t('botRules.help.type')}
                                value={form.type}
                                options={[
                                    { label: t('status.hard_rule'), value: 'hard_rule' },
                                    { label: t('status.playbook'), value: 'playbook' },
                                    { label: t('status.upsell_rule'), value: 'upsell_rule' },
                                    { label: t('status.style_rule'), value: 'style_rule' },
                                    { label: t('status.escalation_rule'), value: 'escalation_rule' },
                                ]}
                                onChange={(value) => setForm({ ...form, type: value as AdminBotRuleWrite['type'] })}
                            />
                            <Select
                                label={t('common.status')}
                                help={t('botRules.help.status')}
                                value={form.status}
                                options={[
                                    { label: t('status.draft'), value: 'draft' },
                                    { label: t('botRules.statusActive'), value: 'active' },
                                    { label: t('status.archived'), value: 'archived' },
                                ]}
                                onChange={(value) => setForm({ ...form, status: value as AdminBotRuleWrite['status'] })}
                            />
                        </div>
                        <div className="grid grid-cols-4 gap-3">
                            <Input label={t('botRules.field.priority')} help={t('botRules.help.priority')} value={String(form.priority)} onChange={(value) => setForm({ ...form, priority: Number(value) || 0 })} />
                            <Select
                                label={t('botRules.field.scope')}
                                help={t('botRules.help.scope')}
                                value={form.scope}
                                options={[
                                    { label: t('status.global'), value: 'global' },
                                    { label: t('status.stage'), value: 'stage' },
                                    { label: t('status.language'), value: 'language' },
                                    { label: t('status.segment'), value: 'segment' },
                                    { label: t('status.conversation'), value: 'conversation' },
                                ]}
                                onChange={(value) => setForm({ ...form, scope: value as AdminBotRuleWrite['scope'] })}
                            />
                            <Select
                                label={t('conv.field.stage')}
                                help={t('botRules.help.stage')}
                                value={form.stage || ''}
                                options={[
                                    { label: t('common.any'), value: '' },
                                    { label: t('status.greeting'), value: 'greeting' },
                                    { label: t('status.qualifying'), value: 'qualifying' },
                                    { label: t('status.needs_analysis'), value: 'needs_analysis' },
                                    { label: t('status.solution'), value: 'solution' },
                                    { label: t('status.quoting'), value: 'quoting' },
                                    { label: t('status.closing'), value: 'closing' },
                                ]}
                                onChange={(value) => setForm({ ...form, stage: value || null })}
                            />
                            <Select
                                label={t('common.language')}
                                help={t('botRules.help.language')}
                                value={form.language || ''}
                                options={[
                                    { label: t('common.any'), value: '' },
                                    { label: 'EN', value: 'en' },
                                    { label: 'AR', value: 'ar' },
                                ]}
                                onChange={(value) => setForm({ ...form, language: value === 'ar' || value === 'en' ? value : null })}
                            />
                        </div>
                        <Input label={t('botRules.field.segment')} help={t('botRules.help.segment')} value={form.segment || ''} onChange={(value) => setForm({ ...form, segment: value || null })} />
                        <TextArea
                            label={t('botRules.field.instruction')}
                            help={t('botRules.help.instruction')}
                            value={form.instruction}
                            onChange={(value) => setForm({ ...form, instruction: value })}
                            className="min-h-[180px]"
                        />
                        <TextArea
                            label={t('botRules.field.triggers')}
                            help={t('botRules.help.triggers')}
                            value={form.trigger_examples.join('\n')}
                            onChange={(value) => setForm({ ...form, trigger_examples: value.split('\n').map((item) => item.trim()).filter(Boolean) })}
                            className="min-h-[90px]"
                        />
                        <div className="flex flex-wrap gap-2">
                            <IconButton icon={Search} label={t('common.preview')} disabled={busy} onClick={() => void handlePreview()} />
                            <IconButton icon={Save} label={t('common.saveAndIndex')} disabled={busy} onClick={() => void handleSave()} />
                            <IconButton icon={RefreshCw} label={t('common.reindex')} disabled={!selected || busy} onClick={() => void handleReindex()} />
                            <IconButton icon={Trash2} label={t('botRules.archive')} disabled={!selected || busy} onClick={() => void handleArchive()} danger />
                        </div>
                    </div>
                </div>

                <aside className="overflow-auto border-l border-[#c6c6cd] bg-white p-4">
                    <InspectorBlock title={t('botRules.previewTitle')} help={t('botRules.previewHelp')}>
                        <TextArea
                            label={t('botRules.testMessage')}
                            help={t('botRules.help.testMessage')}
                            value={testMessage}
                            onChange={setTestMessage}
                            className="min-h-[110px]"
                        />
                        <Field label={t('botRules.applied')} value={String(preview?.rule_count ?? 0)} />
                        {preview?.applied_rules.map((rule) => (
                            <div key={rule.id} className="border-b border-[#e5eeff] py-2">
                                <p className="text-sm font-semibold text-[#0b1c30]">{rule.title}</p>
                                <p className="mt-1 text-xs text-[#45464d]">P{rule.priority} · {label(rule.type)}</p>
                            </div>
                        ))}
                    </InspectorBlock>

                    <div className="mt-4">
                        <InspectorBlock title={t('botRules.promptBlock')} help={t('botRules.promptBlockHelp')}>
                            <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-md bg-[#0b1c30] p-3 text-xs leading-5 text-[#f8fafc]">
                                {preview?.prompt_block || '[BOT OPERATING RULES]'}
                            </pre>
                        </InspectorBlock>
                    </div>
                </aside>
            </section>
        </>
    );
}

function AuditView({ globalSearch = '' }: { globalSearch?: string }) {
    const { t, formatDate } = useI18n();
    const [rows, setRows] = useState<AdminActionAuditRead[]>([]);
    const [selected, setSelected] = useState<AdminActionAuditRead | null>(null);
    const [entityType, setEntityType] = useState('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const params = new URLSearchParams({ page_size: '50' });
        if (entityType) params.set('entity_type', entityType);
        fetchAdminAudit(params)
            .then((payload) => {
                setRows(payload.items);
                setSelected((current) => payload.items.find((row) => row.id === current?.id) ?? payload.items[0] ?? null);
                setError(null);
            })
            .catch((err: unknown) => setError(errorMessage(err, t)));
    }, [entityType, t]);

    const visibleRows = rows.filter((row) =>
        matchesQuery(globalSearch, row.action, row.actor, row.entity_type, row.entity_id, row.request_path),
    );

    return (
        <>
            <ViewBanner view="audit" />
            <section className="grid gap-5 p-6 xl:grid-cols-[1.1fr_0.9fr]">
                {error && <StateLine text={error} tone="red" />}
                <Panel
                    title={t('audit.title')}
                    subtitle={t('audit.subtitle')}
                    help={t('audit.help')}
                    icon={History}
                    action={(
                        <div className="flex items-center gap-1.5">
                            <select
                                value={entityType}
                                onChange={(event) => setEntityType(event.target.value)}
                                aria-label={t('audit.entityFilter')}
                                className="h-9 rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                            >
                                <option value="">{t('audit.allEntities')}</option>
                                <option value="conversation">{t('audit.entity.conversation')}</option>
                                <option value="knowledge_base">{t('nav.knowledge')}</option>
                                <option value="knowledge_base_candidate">{t('audit.entity.candidate')}</option>
                                <option value="bot_behavior_rule">{t('nav.botRules')}</option>
                            </select>
                            <HelpTooltip text={t('audit.entityFilterHelp')} />
                        </div>
                    )}
                >
                    <div className="overflow-hidden rounded-md border border-[#c6c6cd] bg-white">
                        <table className="min-w-full divide-y divide-[#e5eeff] text-sm">
                            <thead className="bg-[#f8f9ff] text-left text-xs uppercase text-[#45464d]">
                                <tr>
                                    <th className="px-4 py-3">{t('audit.colTime')}</th>
                                    <th className="px-4 py-3">{t('audit.colAction')}</th>
                                    <th className="px-4 py-3">{t('audit.colEntity')}</th>
                                    <th className="px-4 py-3">{t('audit.colPath')}</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#e5eeff]">
                                {visibleRows.map((row) => (
                                    <tr
                                        key={row.id}
                                        onClick={() => setSelected(row)}
                                        className={cx('cursor-pointer', selected?.id === row.id ? 'bg-[#eff4ff]' : 'hover:bg-[#f8f9ff]')}
                                    >
                                        <td className="px-4 py-3 text-[#45464d]">{formatDate(row.created_at)}</td>
                                        <td className="px-4 py-3 font-medium text-[#0b1c30]">{row.action}</td>
                                        <td className="px-4 py-3 text-[#3f465c]">{row.entity_type}:{row.entity_id || '—'}</td>
                                        <td className="px-4 py-3 text-[#45464d]">{row.request_path || '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {visibleRows.length === 0 && <StateLine text={t('audit.empty')} />}
                    </div>
                </Panel>

                <Panel
                    title={t('audit.detailsTitle')}
                    subtitle={t('audit.detailsSubtitle')}
                    icon={ShieldCheck}
                >
                    {selected ? (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <Field label={t('audit.actor')} value={selected.actor} />
                                <Field label={t('audit.colAction')} value={selected.action} />
                                <Field label={t('audit.colEntity')} value={`${selected.entity_type}:${selected.entity_id || '—'}`} />
                                <Field label={t('audit.colPath')} value={selected.request_path || '—'} />
                            </div>
                            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                                <JsonPreview title={t('audit.before')} value={selected.before} />
                                <JsonPreview title={t('audit.after')} value={selected.after} />
                            </div>
                            <JsonPreview title={t('audit.metadata')} value={selected.metadata} />
                        </div>
                    ) : (
                        <StateLine text={t('audit.selectRow')} />
                    )}
                </Panel>
            </section>
        </>
    );
}

function OverviewActionPanel({
    data,
    refetch,
}: {
    data: NonNullable<ReturnType<typeof useMetrics>['data']>;
    refetch: () => void;
}) {
    const { t } = useI18n();
    return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Panel
                title={t('overview.queuesTitle')}
                subtitle={t('overview.queuesSubtitle')}
                icon={Inbox}
            >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <StatusCard
                        title={t('metric.escalations')}
                        help={t('metric.escalationsHelp')}
                        value={data.escalation_count}
                        note={t('overview.escalationsNote')}
                        tone="amber"
                    />
                    <StatusCard
                        title={t('overview.deals')}
                        help={t('funnel.dealsHelp')}
                        value={data.noor_sales.count + data.post_escalation_sales.count}
                        note={t('overview.conversionNote', { rate: data.conversion_rate })}
                        tone="green"
                    />
                    <StatusCard
                        title="QA"
                        help={t('metric.qualityHelp')}
                        value={`${data.avg_quality_score}/30`}
                        note={t('overview.qaNote')}
                        tone="blue"
                    />
                </div>
            </Panel>

            <Panel
                title={t('overview.controlTitle')}
                subtitle={t('overview.controlSubtitle')}
                icon={ShieldCheck}
                action={(
                    <button
                        type="button"
                        onClick={() => void refetch()}
                        className="inline-flex items-center gap-2 rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                    >
                        <RefreshCw size={15} />
                        {t('common.refresh')}
                    </button>
                )}
            >
                <div className="space-y-3 text-sm text-[#3f465c]">
                    <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-4 py-3">
                        {t('overview.controlNote1')}
                    </div>
                    <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-4 py-3">
                        {t('overview.controlNote2')}
                    </div>
                </div>
            </Panel>
        </div>
    );
}

function QueuesView({ globalSearch = '' }: { globalSearch?: string }) {
    const { t, label, formatDateTime } = useI18n();
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [candidates, setCandidates] = useState<AdminKnowledgeBaseCandidate[]>([]);
    const [loading, setLoading] = useState(true);
    const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
    const [approvingId, setApprovingId] = useState<string | null>(null);
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);
    const managerQa = useAIQualityControlBlock('manager_qa', 'Manager QA');
    const managerQaBlock = managerQa.message;

    const load = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const [pendingResult, candidateResult] = await Promise.all([
                fetchPendingManagerReviews(20),
                fetchKnowledgeBaseCandidates(new URLSearchParams({ page_size: '20', status: 'needs_confirmation' })),
            ]);
            setPendingReviews(pendingResult);
            setCandidates(candidateResult.items);
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void load();
    }, [load]);

    async function handleEvaluate(item: PendingManagerReview) {
        if (managerQaBlock || !globalThis.confirm(t('queues.confirmEvaluate'))) return;
        setEvaluatingId(item.escalation_id);
        setMessage(null);
        try {
            const review = await evaluateManagerReview(item.escalation_id);
            setMessage({
                tone: 'success',
                text: t('queues.evaluated', { score: review.total_score, max: review.max_score }),
            });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: localizeQualityGateError(errorMessage(err, t), t) });
        } finally {
            setEvaluatingId(null);
        }
    }

    async function handleApprove(candidate: AdminKnowledgeBaseCandidate) {
        if (!globalThis.confirm(t('queues.confirmApprove'))) return;
        setApprovingId(candidate.id);
        setMessage(null);
        try {
            await approveKnowledgeBaseCandidate(candidate.id);
            setMessage({ tone: 'success', text: t('queues.approved') });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setApprovingId(null);
        }
    }

    async function handleReject(candidate: AdminKnowledgeBaseCandidate) {
        if (!globalThis.confirm(t('kb.confirmRejectCandidate'))) return;
        setRejectingId(candidate.id);
        setMessage(null);
        try {
            await rejectKnowledgeBaseCandidate(candidate.id, { reason: 'admin_rejected' });
            setMessage({ tone: 'success', text: t('queues.rejected') });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setRejectingId(null);
        }
    }

    const visibleReviews = pendingReviews.filter((item) =>
        matchesQuery(globalSearch, item.manager_name, item.phone, item.reason, item.status),
    );
    const visibleCandidates = candidates.filter((candidate) =>
        matchesQuery(globalSearch, candidate.question, candidate.answer, candidate.language),
    );

    return (
        <>
            <ViewBanner view="queues" />
            <section className="space-y-5 p-6">
                {message && <ActionMessageBox message={message} />}
                <QualityBlockNotice block={managerQa} />
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <StatusCard title={t('queues.pendingTitle')} help={t('queues.pendingHelp')} value={pendingReviews.length} note={t('queues.pendingNote')} tone="amber" />
                    <StatusCard title={t('queues.candidatesTitle')} help={t('kb.autoFaqHelp')} value={candidates.length} note={t('queues.candidatesNote')} tone="blue" />
                    <StatusCard title={t('queues.modeTitle')} help={t('queues.modeHelp')} value={loading ? '...' : t('queues.live')} note={t('queues.modeNote')} tone="green" />
                </div>

                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
                    <Panel
                        title={t('queues.escalationsTitle')}
                        subtitle={t('queues.escalationsSubtitle')}
                        help={t('queues.pendingHelp')}
                        icon={ClipboardList}
                        action={<RefreshButton loading={loading} onClick={() => void load()} />}
                    >
                        <div className="space-y-3">
                            {!loading && visibleReviews.length === 0 && <StateLine text={t('queues.escalationsEmpty')} />}
                            {visibleReviews.map((item) => (
                                <div key={item.escalation_id} className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                        <div>
                                            <p className="text-sm font-semibold text-[#0b1c30]">{item.manager_name || t('queues.managerUnassigned')}</p>
                                            <p className="mt-1 text-sm text-[#3f465c]">{item.phone}</p>
                                            <p className="mt-2 text-sm text-[#45464d]">{item.reason}</p>
                                            <p className="mt-2 text-xs text-[#7c839b]">{t('queues.updated', { date: formatDateTime(item.updated_at) })}</p>
                                        </div>
                                        <button
                                            type="button"
                                            disabled={evaluatingId !== null || Boolean(managerQaBlock)}
                                            onClick={() => void handleEvaluate(item)}
                                            className="inline-flex items-center justify-center gap-2 rounded-md border border-[#f59e0b] bg-[#fff7ed] px-3 py-2 text-sm font-medium text-[#92400e] hover:bg-[#ffedd5] disabled:opacity-50"
                                        >
                                            {evaluatingId === item.escalation_id ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                                            {t('common.evaluate')}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Panel>

                    <Panel
                        title={t('kb.autoFaqTitle')}
                        subtitle={t('queues.autoFaqSubtitle')}
                        help={t('kb.autoFaqHelp')}
                        icon={BookOpen}
                    >
                        <div className="space-y-3">
                            {!loading && visibleCandidates.length === 0 && <StateLine text={t('kb.noCandidates')} />}
                            {visibleCandidates.map((candidate) => (
                                <div key={candidate.id} className="rounded-md border border-[#e5eeff] bg-white p-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-semibold text-[#0b1c30]">{candidate.question}</p>
                                            <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#45464d]">{candidate.answer}</p>
                                        </div>
                                        <Badge label={candidate.confidence ? `${Math.round(candidate.confidence * 100)}%` : '—'} tone="blue" />
                                    </div>
                                    <div className="mt-3 flex items-center justify-between gap-3">
                                        <p className="text-xs text-[#7c839b]">{candidate.language} · {label(candidate.status)}</p>
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                disabled={rejectingId !== null || approvingId !== null}
                                                onClick={() => void handleReject(candidate)}
                                                className="rounded-md border border-[#fecaca] bg-white px-3 py-2 text-xs font-medium text-[#be123c] hover:bg-[#fff1f2] disabled:opacity-50"
                                            >
                                                {rejectingId === candidate.id ? t('common.rejecting') : t('common.reject')}
                                            </button>
                                            <button
                                                type="button"
                                                disabled={approvingId !== null || rejectingId !== null}
                                                onClick={() => void handleApprove(candidate)}
                                                className="rounded-md bg-[#0058be] px-3 py-2 text-xs font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                            >
                                                {approvingId === candidate.id ? t('common.saving') : t('common.approve')}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Panel>
                </div>
            </section>
        </>
    );
}

function CatalogView() {
    const { t } = useI18n();
    const [syncingSource, setSyncingSource] = useState<ProductSyncSource | null>(null);
    const [result, setResult] = useState<ProductSyncResponse | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    async function handleSync(source: ProductSyncSource) {
        const sourceLabel = source === 'treejar' ? 'Treejar' : 'Zoho';
        if (!globalThis.confirm(t('catalog.confirmSync', { source: sourceLabel }))) return;
        setSyncingSource(source);
        setMessage(null);
        try {
            const response = await syncProducts(source);
            setResult(response);
            setMessage({
                tone: response.errors > 0 ? 'info' : 'success',
                text: t('catalog.syncQueued', { source: sourceLabel, errors: response.errors }),
            });
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setSyncingSource(null);
        }
    }

    return (
        <>
            <ViewBanner view="catalog" />
            <section className="space-y-5 p-6">
                {message && <ActionMessageBox message={message} />}
                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
                    <Panel
                        title={t('catalog.syncTitle')}
                        subtitle={t('catalog.syncSubtitle')}
                        help={t('catalog.syncHelp')}
                        icon={Package}
                    >
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-1">
                            <CatalogSyncCard
                                title={t('catalog.treejarTitle')}
                                note={t('catalog.treejarNote')}
                                source="treejar"
                                syncingSource={syncingSource}
                                onSync={handleSync}
                            />
                            <CatalogSyncCard
                                title={t('catalog.zohoTitle')}
                                note={t('catalog.zohoNote')}
                                source="zoho"
                                syncingSource={syncingSource}
                                onSync={handleSync}
                            />
                        </div>
                    </Panel>

                    <Panel
                        title={t('catalog.resultTitle')}
                        subtitle={t('catalog.resultSubtitle')}
                        icon={History}
                    >
                        {result ? (
                            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                                <StatusCard title={t('catalog.synced')} value={result.synced} note={t('catalog.syncedNote')} />
                                <StatusCard title={t('catalog.created')} value={result.created} note={t('catalog.createdNote')} tone="green" />
                                <StatusCard title={t('catalog.updated')} value={result.updated} note={t('catalog.updatedNote')} tone="blue" />
                                <StatusCard title={t('catalog.deactivated')} value={result.deactivated} note={t('catalog.deactivatedNote')} tone="amber" />
                                <StatusCard title={t('catalog.embeddings')} help={t('catalog.embeddingsHelp')} value={result.embeddings_generated} note={t('catalog.embeddingsNote')} tone="blue" />
                                <StatusCard title={t('catalog.errors')} value={result.errors} note={t('catalog.errorsNote')} tone={result.errors > 0 ? 'amber' : 'green'} />
                            </div>
                        ) : (
                            <StateLine text={t('catalog.noResult')} />
                        )}
                    </Panel>
                </div>
            </section>
        </>
    );
}

function QualityView({ refetch, globalSearch = '' }: { refetch: () => void; globalSearch?: string }) {
    const { t, label, formatDuration } = useI18n();
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [loading, setLoading] = useState(true);
    const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);
    const managerQa = useAIQualityControlBlock('manager_qa', 'Manager QA');
    const managerQaBlock = managerQa.message;

    const load = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const [pendingResult, recentResult] = await Promise.all([
                fetchPendingManagerReviews(10),
                fetchRecentManagerReviews(10),
            ]);
            setPendingReviews(pendingResult);
            setRecentReviews(recentResult.items);
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void load();
    }, [load]);

    async function handleEvaluate(item: PendingManagerReview) {
        if (managerQaBlock || !globalThis.confirm(t('quality.confirmEvaluate'))) return;
        setEvaluatingId(item.escalation_id);
        setMessage(null);
        try {
            const review = await evaluateManagerReview(item.escalation_id);
            setMessage({ tone: 'success', text: t('quality.evaluated', { score: review.total_score, max: review.max_score }) });
            await load();
            void refetch();
        } catch (err) {
            setMessage({ tone: 'error', text: localizeQualityGateError(errorMessage(err, t), t) });
        } finally {
            setEvaluatingId(null);
        }
    }

    const avgScore = recentReviews.length
        ? (recentReviews.reduce((sum, review) => sum + review.total_score, 0) / recentReviews.length).toFixed(1)
        : '—';
    const dealCount = recentReviews.filter((review) => review.deal_converted).length;
    const visiblePending = pendingReviews.filter((item) =>
        matchesQuery(globalSearch, item.manager_name, item.phone, item.reason, item.status),
    );
    const visibleRecent = recentReviews.filter((review) =>
        matchesQuery(globalSearch, review.manager_name, review.rating, review.reviewer),
    );

    return (
        <>
            <ViewBanner view="quality" />
            <section className="space-y-5 p-6">
                {message && <ActionMessageBox message={message} />}
                <QualityBlockNotice block={managerQa} />
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <StatusCard title={t('quality.pendingTitle')} help={t('queues.pendingHelp')} value={pendingReviews.length} note={t('quality.pendingNote')} tone="amber" />
                    <StatusCard title={t('quality.recentCount')} help={t('quality.recentHelp')} value={recentReviews.length} note={t('quality.recentNote')} />
                    <StatusCard title={t('quality.avgScore')} help={t('quality.avgScoreHelp')} value={avgScore} note={t('quality.avgScoreNote')} tone="blue" />
                    <StatusCard title={t('quality.converted')} help={t('quality.convertedHelp')} value={dealCount} note={t('quality.convertedNote')} tone="green" />
                </div>

                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_1fr]">
                    <Panel
                        title={t('quality.queueTitle')}
                        subtitle={t('quality.queueSubtitle')}
                        help={t('queues.pendingHelp')}
                        icon={ClipboardList}
                        action={<RefreshButton loading={loading} onClick={() => void load()} />}
                    >
                        <div className="space-y-3">
                            {!loading && visiblePending.length === 0 && <StateLine text={t('quality.queueEmpty')} />}
                            {visiblePending.map((item) => (
                                <div key={item.escalation_id} className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="text-sm font-semibold text-[#0b1c30]">{item.manager_name || t('queues.managerUnassigned')}</p>
                                            <p className="mt-1 text-sm text-[#45464d]">{item.phone} · {label(item.status)}</p>
                                            <p className="mt-2 text-sm text-[#3f465c]">{item.reason}</p>
                                        </div>
                                        <button
                                            type="button"
                                            disabled={evaluatingId !== null || Boolean(managerQaBlock)}
                                            onClick={() => void handleEvaluate(item)}
                                            className="inline-flex items-center gap-2 rounded-md bg-[#0058be] px-3 py-2 text-sm font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                        >
                                            {evaluatingId === item.escalation_id ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                                            {t('common.evaluate')}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </Panel>

                    <Panel
                        title={t('quality.recentTitle')}
                        subtitle={t('quality.recentSubtitle')}
                        help={t('quality.recentHelp')}
                        icon={ShieldCheck}
                    >
                        <div className="overflow-hidden rounded-md border border-[#e5eeff]">
                            <table className="min-w-full divide-y divide-[#e5eeff] text-sm">
                                <thead className="bg-[#f8f9ff] text-left text-xs uppercase text-[#45464d]">
                                    <tr>
                                        <th className="px-4 py-3">{t('quality.colManager')}</th>
                                        <th className="px-4 py-3">{t('quality.colScore')}</th>
                                        <th className="px-4 py-3">{t('quality.colResponse')}</th>
                                        <th className="px-4 py-3">{t('quality.colDeal')}</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-[#e5eeff] bg-white">
                                    {visibleRecent.map((review) => (
                                        <tr key={review.id}>
                                            <td className="px-4 py-3 font-medium text-[#0b1c30]">{review.manager_name || '—'}</td>
                                            <td className="px-4 py-3 text-[#3f465c]">{review.total_score}/{review.max_score} · {label(review.rating)}</td>
                                            <td className="px-4 py-3 text-[#45464d]">{formatDuration(review.first_response_time_seconds)}</td>
                                            <td className="px-4 py-3 text-[#45464d]">{review.deal_converted ? `${review.deal_amount || 0} AED` : '—'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Panel>
                </div>

                <Panel
                    title={t('quality.contoursTitle')}
                    subtitle={t('quality.contoursSubtitle')}
                    icon={SlidersHorizontal}
                >
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                        <StatusCard title="Bot QA" help={t('aiqc.contour.bot_qa')} value={managerQa.config ? t(`aiqc.mode.${managerQa.config.bot_qa.mode}` as TranslationKey) : '—'} note={t('quality.botQaNote')} tone="green" />
                        <StatusCard title="Manager QA" help={t('aiqc.contour.manager_qa')} value={managerQa.config ? t(`aiqc.mode.${managerQa.config.manager_qa.mode}` as TranslationKey) : '—'} note={t('quality.managerQaNote')} tone="blue" />
                        <StatusCard title={t('aiqc.scope.red_flags')} help={t('aiqc.contour.red_flags')} value={managerQa.config ? t(`aiqc.mode.${managerQa.config.red_flags.mode}` as TranslationKey) : '—'} note={t('quality.redFlagsNote')} tone="amber" />
                    </div>
                </Panel>
            </section>
        </>
    );
}

function ReportsView() {
    const { t, formatDateTime } = useI18n();
    const [report, setReport] = useState<OperationsReportResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const loadReport = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const result = await generateOperationsReport();
            setReport(result);
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadReport();
    }, [loadReport]);

    return (
        <>
            <ViewBanner view="reports" />
            <section className="space-y-5 p-6">
                {message && <ActionMessageBox message={message} />}
                <Panel
                    title={t('reports.title')}
                    subtitle={t('reports.subtitle')}
                    help={t('reports.help')}
                    icon={FileText}
                    action={<RefreshButton loading={loading} label={t('reports.generate')} onClick={() => void loadReport()} />}
                >
                    {report ? (
                        <div className="space-y-5">
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                                <StatusCard title={t('metric.conversations')} help={t('metric.conversationsHelp')} value={report.data.total_conversations} note={t('reports.perDay', { count: report.data.conversations_per_day })} />
                                <StatusCard title={t('metric.conversion')} help={t('metric.conversionHelp')} value={`${report.data.conversion_rate}%`} note={t('metric.dealsCount', { count: report.data.total_deals })} tone="green" />
                                <StatusCard title={t('metric.escalations')} help={t('metric.escalationsHelp')} value={report.data.escalation_count} note={t('reports.reasonsCount', { count: Object.keys(report.data.escalation_reasons).length })} tone="amber" />
                                <StatusCard title="Manager QA" help={t('aiqc.contour.manager_qa')} value={`${report.data.avg_manager_score}/20`} note={t('reports.reviewsCount', { count: report.data.manager_reviews_count })} tone="blue" />
                            </div>

                            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                                <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <p className="flex items-center gap-1.5 text-sm font-semibold text-[#0b1c30]">
                                                {t('reports.telegramPreview')}
                                                <HelpTooltip text={t('reports.telegramPreviewHelp')} />
                                            </p>
                                            <p className="mt-1 text-xs text-[#7c839b]">
                                                {formatDateTime(report.data.period_start)} — {formatDateTime(report.data.period_end)}
                                            </p>
                                        </div>
                                        <Badge label={`${report.data.avg_quality_score}/30 Bot QA`} tone="blue" />
                                    </div>
                                    <pre className="mt-4 max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-[#c6c6cd] bg-white p-4 text-sm leading-6 text-[#0b1c30]">
                                        {stripHtml(report.text)}
                                    </pre>
                                </div>

                                <div className="space-y-4">
                                    <SideListPanel
                                        title={t('reports.topProducts')}
                                        icon={TrendingUp}
                                        empty={t('reports.topProductsEmpty')}
                                        items={report.data.top_products.map((product) => ({
                                            key: product.sku,
                                            title: product.name,
                                            meta: `${product.sku} · ${t('reports.mentions', { count: product.mentions })}`,
                                        }))}
                                    />
                                    <SideListPanel
                                        title={t('reports.topManagers')}
                                        icon={Clock}
                                        empty={t('reports.topManagersEmpty')}
                                        items={report.data.top_managers.map((manager) => ({
                                            key: manager.name,
                                            title: manager.name,
                                            meta: `${manager.avg_score}/20`,
                                        }))}
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <StateLine text={loading ? t('reports.generating') : t('reports.notLoaded')} />
                    )}
                </Panel>
            </section>
        </>
    );
}

function SettingsView() {
    const { t } = useI18n();
    const [config, setConfig] = useState<NotificationConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [sendingTest, setSendingTest] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const loadConfig = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            setConfig(await fetchNotificationConfig());
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadConfig();
    }, [loadConfig]);

    async function handleSendTest() {
        if (!globalThis.confirm(t('settings.confirmSendTest'))) return;
        setSendingTest(true);
        setMessage(null);
        try {
            const result = await sendTestNotification();
            setMessage({
                tone: result.status === 'sent' ? 'success' : 'info',
                text: result.status === 'sent'
                    ? t('settings.testSent')
                    : result.reason || t('settings.telegramNotConfigured'),
            });
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setSendingTest(false);
        }
    }

    const loadingText = loading ? t('common.loading') : '—';

    return (
        <>
            <ViewBanner view="settings" />
            <section className="space-y-5 p-6">
                {message && <ActionMessageBox message={message} />}
                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                    <Panel
                        title={t('settings.title')}
                        subtitle={t('settings.subtitle')}
                        icon={Settings}
                        action={<RefreshButton loading={loading} onClick={() => void loadConfig()} />}
                    >
                        <div className="space-y-3">
                            <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-2">
                                        <Bell size={16} className="text-[#0058be]" />
                                        <p className="text-sm font-semibold text-[#0b1c30]">{t('settings.telegramTitle')}</p>
                                        <HelpTooltip text={t('settings.telegramHelp')} />
                                    </div>
                                    <Badge label={config?.telegram_configured ? t('settings.configured') : t('settings.notConfigured')} tone={config?.telegram_configured ? 'green' : 'amber'} />
                                </div>
                                <Field label={t('settings.botToken')} value={config?.telegram_bot_token || loadingText} />
                                <Field label={t('settings.chatId')} value={config?.telegram_chat_id || loadingText} />
                                <button
                                    type="button"
                                    disabled={sendingTest}
                                    onClick={() => void handleSendTest()}
                                    className="mt-4 inline-flex items-center gap-2 rounded-md bg-[#0058be] px-3 py-2 text-sm font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                >
                                    {sendingTest ? <RefreshCw size={15} className="animate-spin" /> : <Send size={15} />}
                                    {t('settings.sendTest')}
                                </button>
                            </div>

                            <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <p className="text-sm font-semibold text-[#0b1c30]">{t('settings.sessionTitle')}</p>
                                <p className="mt-2 text-sm leading-6 text-[#45464d]">
                                    {t('settings.sessionBody')}
                                </p>
                            </div>
                        </div>
                    </Panel>

                    <AIQualityControlsPanel />
                </div>
            </section>
        </>
    );
}

function MetricTile({
    label: labelText,
    value,
    note,
    help,
    tone = 'gray',
}: {
    label: string;
    value: number | string;
    note: string;
    help?: string;
    tone?: 'gray' | 'amber' | 'green' | 'blue';
}) {
    const tones = {
        gray: 'border-[#c6c6cd]',
        amber: 'border-[#f59e0b]',
        green: 'border-[#0058be]',
        blue: 'border-[#2563eb]',
    };
    return (
        <div className={cx('rounded-md border bg-white p-4 shadow-sm', tones[tone])}>
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase text-[#45464d]">
                {labelText}
                {help && <HelpTooltip text={help} />}
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#0b1c30]">{value}</p>
            <p className="mt-1 text-sm text-[#45464d]">{note}</p>
        </div>
    );
}

function Panel({
    title,
    subtitle,
    help,
    icon: Icon,
    action,
    children,
}: {
    title: string;
    subtitle?: string;
    help?: string;
    icon?: ComponentType<{ size?: number; className?: string }>;
    action?: ReactNode;
    children: ReactNode;
}) {
    return (
        <section className="rounded-md border border-[#c6c6cd] bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-3">
                    {Icon && (
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#eff4ff] text-[#0058be]">
                            <Icon size={18} />
                        </div>
                    )}
                    <div>
                        <h3 className="flex items-center gap-1.5 text-base font-semibold text-[#0b1c30]">
                            {title}
                            {help && <HelpTooltip text={help} />}
                        </h3>
                        {subtitle && <p className="mt-1 max-w-3xl text-sm leading-6 text-[#45464d]">{subtitle}</p>}
                    </div>
                </div>
                {action}
            </div>
            {children}
        </section>
    );
}

function StatusCard({
    title,
    value,
    note,
    help,
    tone = 'gray',
}: {
    title: string;
    value: number | string;
    note: string;
    help?: string;
    tone?: StatusTone;
}) {
    const tones: Record<StatusTone, string> = {
        gray: 'border-[#e5eeff] bg-[#f8f9ff]',
        amber: 'border-[#f59e0b] bg-[#fff7ed]',
        green: 'border-[#22c55e] bg-[#f0fdf4]',
        blue: 'border-[#adc6ff] bg-[#eff4ff]',
    };
    return (
        <div className={cx('rounded-md border p-4', tones[tone])}>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-[#45464d]">
                {title}
                {help && <HelpTooltip text={help} />}
            </p>
            <p className="mt-2 text-2xl font-semibold text-[#0b1c30]">{value}</p>
            <p className="mt-1 text-sm text-[#45464d]">{note}</p>
        </div>
    );
}

function ActionMessageBox({ message }: { message: ActionMessage }) {
    const classes: Record<ActionMessage['tone'], string> = {
        success: 'border-[#bbf7d0] bg-[#f0fdf4] text-[#166534]',
        error: 'border-[#fecaca] bg-[#fff1f2] text-[#be123c]',
        info: 'border-[#fde68a] bg-[#fffbeb] text-[#92400e]',
    };
    return (
        <div className={cx('rounded-md border px-4 py-3 text-sm', classes[message.tone])}>
            {message.text}
        </div>
    );
}

function RefreshButton({
    loading,
    label,
    onClick,
}: {
    loading: boolean;
    label?: string;
    onClick: () => void;
}) {
    const { t } = useI18n();
    return (
        <button
            type="button"
            disabled={loading}
            onClick={onClick}
            className="inline-flex items-center gap-2 rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7] disabled:opacity-50"
        >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            {label ?? t('common.refresh')}
        </button>
    );
}

function CatalogSyncCard({
    title,
    note,
    source,
    syncingSource,
    onSync,
}: {
    title: string;
    note: string;
    source: ProductSyncSource;
    syncingSource: ProductSyncSource | null;
    onSync: (source: ProductSyncSource) => Promise<void>;
}) {
    const isSyncing = syncingSource === source;
    return (
        <button
            type="button"
            disabled={syncingSource !== null}
            onClick={() => void onSync(source)}
            className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4 text-left transition hover:border-[#adc6ff] hover:bg-[#eff4ff] disabled:opacity-50"
        >
            <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-[#0b1c30]">{title}</p>
                {isSyncing ? <RefreshCw size={16} className="animate-spin text-[#0058be]" /> : <Boxes size={16} className="text-[#0058be]" />}
            </div>
            <p className="mt-2 text-sm leading-6 text-[#45464d]">{note}</p>
        </button>
    );
}

function SideListPanel({
    title,
    icon: Icon,
    items,
    empty,
}: {
    title: string;
    icon: ComponentType<{ size?: number; className?: string }>;
    items: { key: string; title: string; meta: string }[];
    empty: string;
}) {
    return (
        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
            <div className="flex items-center gap-2 text-[#0b1c30]">
                <Icon size={16} className="text-[#0058be]" />
                <p className="text-sm font-semibold">{title}</p>
            </div>
            <div className="mt-3 space-y-2">
                {items.length > 0 ? items.map((item) => (
                    <div key={item.key} className="rounded-md border border-[#e5eeff] bg-white px-3 py-3">
                        <p className="text-sm font-medium text-[#0b1c30]">{item.title}</p>
                        <p className="mt-1 text-xs text-[#45464d]">{item.meta}</p>
                    </div>
                )) : (
                    <div className="rounded-md border border-dashed border-[#c6c6cd] px-3 py-5 text-sm text-[#45464d]">
                        {empty}
                    </div>
                )}
            </div>
        </div>
    );
}

function JsonPreview({ title, value }: { title: string; value: unknown }) {
    return (
        <div>
            <p className="mb-2 text-xs font-semibold uppercase text-[#45464d]">{title}</p>
            <pre className="max-h-[260px] overflow-auto rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-3 text-xs leading-5 text-[#0b1c30]">
                {JSON.stringify(value ?? null, null, 2)}
            </pre>
        </div>
    );
}

function InspectorBlock({ title, help, children }: { title: string; help?: string; children: ReactNode }) {
    return (
        <section className="rounded-md border border-[#c6c6cd] bg-white p-4">
            <h3 className="flex items-center gap-1.5 text-sm font-semibold text-[#0b1c30]">
                {title}
                {help && <HelpTooltip text={help} />}
            </h3>
            <div className="mt-3 space-y-2">{children}</div>
        </section>
    );
}

function Field({ label: labelText, value }: { label: string; value: string }) {
    return (
        <div className="flex items-start justify-between gap-3 text-sm">
            <span className="text-[#45464d]">{labelText}</span>
            <span className="max-w-[190px] break-words text-right font-medium text-[#0b1c30]">{value}</span>
        </div>
    );
}

function IconButton({
    icon: Icon,
    label: labelText,
    disabled,
    danger,
    onClick,
}: {
    icon: ComponentType<{ size?: number }>;
    label: string;
    disabled?: boolean;
    danger?: boolean;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            disabled={disabled}
            onClick={onClick}
            className={cx(
                'inline-flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
                danger
                    ? 'border-[#fecaca] bg-white text-[#be123c] hover:bg-[#fff1f2]'
                    : 'border-[#c6c6cd] bg-white text-[#3f465c] hover:bg-[#f2f4f7]',
            )}
        >
            <Icon size={15} />
            <span>{labelText}</span>
        </button>
    );
}

function Badge({ label: labelText, tone = 'gray' }: { label: string; tone?: StatusTone }) {
    const tones = {
        gray: 'bg-[#eef2f6] text-[#3f465c]',
        amber: 'bg-[#fef3c7] text-[#92400e]',
        green: 'bg-[#dcfce7] text-[#166534]',
        blue: 'bg-[#eff4ff] text-[#004395]',
    };
    return <span className={cx('rounded px-2 py-1 text-xs font-medium', tones[tone])}>{labelText}</span>;
}

function StateLine({ text, tone = 'gray' }: { text: string; tone?: 'gray' | 'red' }) {
    return (
        <div className={cx('m-4 rounded-md px-3 py-2 text-sm', tone === 'red' ? 'bg-[#fff1f2] text-[#be123c]' : 'bg-[#f2f4f7] text-[#45464d]')}>
            {text}
        </div>
    );
}

function FieldLabel({ label, help }: { label: string; help?: string }) {
    return (
        <span className="flex items-center gap-1.5 text-xs font-medium text-[#45464d]">
            {label}
            {help && <HelpTooltip text={help} />}
        </span>
    );
}

function Input({
    label,
    help,
    value,
    onChange,
}: {
    label: string;
    help?: string;
    value: string;
    onChange: (value: string) => void;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-[#c6c6cd] px-3 text-sm outline-none focus:border-[#0058be]"
            />
        </label>
    );
}

function TextArea({
    label,
    help,
    value,
    onChange,
    className,
}: {
    label: string;
    help?: string;
    value: string;
    onChange: (value: string) => void;
    className?: string;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <textarea
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className={cx('mt-1 w-full rounded-md border border-[#c6c6cd] px-3 py-2 text-sm leading-6 outline-none focus:border-[#0058be]', className)}
            />
        </label>
    );
}

function Select({
    label,
    help,
    value,
    options,
    onChange,
}: {
    label: string;
    help?: string;
    value: string;
    options: { label: string; value: string }[];
    onChange: (value: string) => void;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <select
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
            >
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        </label>
    );
}

function SegmentedControl<T extends string>({
    items,
    value,
    onChange,
}: {
    items: { label: string; value: T }[];
    value: T;
    onChange: (value: T) => void;
}) {
    return (
        <div className="flex rounded-md border border-[#c6c6cd] bg-[#f8f9ff] p-1">
            {items.map((item) => (
                <button
                    key={item.value}
                    type="button"
                    onClick={() => onChange(item.value)}
                    className={cx(
                        'rounded px-3 py-1.5 text-sm font-medium',
                        item.value === value ? 'bg-white text-[#0058be] shadow-sm' : 'text-[#45464d] hover:text-[#0b1c30]',
                    )}
                >
                    {item.label}
                </button>
            ))}
        </div>
    );
}

function entryToForm(entry: AdminKnowledgeBaseRead): AdminKnowledgeBaseWrite {
    return {
        source: entry.source,
        title: entry.title,
        content: entry.content,
        language: entry.language === 'ar' ? 'ar' : 'en',
        category: entry.category,
    };
}

function ruleToForm(rule: AdminBotRuleRead): AdminBotRuleWrite {
    return {
        title: rule.title,
        type: rule.type as AdminBotRuleWrite['type'],
        status: rule.status as AdminBotRuleWrite['status'],
        priority: rule.priority,
        scope: rule.scope as AdminBotRuleWrite['scope'],
        stage: rule.stage,
        language: rule.language === 'ar' || rule.language === 'en' ? rule.language : null,
        segment: rule.segment,
        instruction: rule.instruction,
        trigger_examples: rule.trigger_examples,
    };
}

function stripHtml(text: string): string {
    return text.replace(/<[^>]+>/g, '').trim();
}

function errorMessage(error: unknown, t: TranslateFn): string {
    return error instanceof Error ? error.message : t('common.unknownError');
}

function cx(...values: Array<string | false | null | undefined>): string {
    return values.filter(Boolean).join(' ');
}
