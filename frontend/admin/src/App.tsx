import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ComponentType, ReactNode } from 'react';
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
import SalesBarChart from '@/components/charts/SalesBarChart';
import SegmentPieChart from '@/components/charts/SegmentPieChart';
import AIQualityControlsPanel from '@/components/AIQualityControlsPanel';
import {
    approveKnowledgeBaseCandidate,
    archiveBotRule,
    createBotRule,
    createKnowledgeBaseEntry,
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
} from '@/types/crm';
import type {
    AIQualityScopeConfig,
    AIQualityScopeKey,
    ManagerReviewRead,
    NotificationConfig,
    OperationsReportResponse,
    PendingManagerReview,
    ProductSyncResponse,
    ProductSyncSource,
} from '@/types/operators';

const PERIODS: { label: string; value: Period }[] = [
    { label: 'День', value: 'day' },
    { label: 'Неделя', value: 'week' },
    { label: 'Месяц', value: 'month' },
    { label: 'Все', value: 'all_time' },
];

const NAV_ITEMS = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'conversations', label: 'Клиенты и диалоги', icon: MessageCircle },
    { id: 'queues', label: 'Очереди', icon: Inbox },
    { id: 'knowledge', label: 'База знаний', icon: BookOpen },
    { id: 'botRules', label: 'Правила бота', icon: SlidersHorizontal },
    { id: 'catalog', label: 'Каталог', icon: Boxes },
    { id: 'quality', label: 'Качество', icon: ShieldCheck },
    { id: 'reports', label: 'Отчеты', icon: FileText },
    { id: 'settings', label: 'Настройки', icon: Settings },
    { id: 'audit', label: 'Аудит', icon: History },
] as const;

type ViewId = (typeof NAV_ITEMS)[number]['id'] | 'support';
type ActionMessage = { tone: 'success' | 'error' | 'info'; text: string };
type StatusTone = 'gray' | 'amber' | 'green' | 'blue';

const STATUS_LABELS: Record<string, string> = {
    active: 'Активен',
    paused: 'Пауза',
    closed: 'Закрыт',
    escalated: 'Эскалация',
    none: 'Нет',
    pending: 'Ожидает',
    in_progress: 'В работе',
    resolved: 'Закрыта',
    manual_takeover: 'Ручной режим',
    greeting: 'Приветствие',
    qualifying: 'Квалификация',
    needs_analysis: 'Потребности',
    solution: 'Решение',
    company_details: 'Компания',
    quoting: 'КП',
    closing: 'Закрытие',
    feedback: 'Фидбек',
    excellent: 'Отлично',
    good: 'Хорошо',
    satisfactory: 'Средне',
    poor: 'Плохо',
    draft: 'Черновик',
    archived: 'Архив',
    hard_rule: 'Жесткое',
    playbook: 'Сценарий',
    upsell_rule: 'Допродажа',
    style_rule: 'Стиль',
    escalation_rule: 'Эскалация',
    global: 'Глобально',
    stage: 'Этап',
    segment: 'Сегмент',
    conversation: 'Диалог',
};

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
): string | null {
    if (scopeConfig.mode === 'disabled') {
        return `${labelText} отключена в Admin AI Quality Controls. Включите manual mode в настройках.`;
    }
    if (scopeConfig.daily_budget_cents <= 0) {
        return `${labelText} отключена: дневной бюджет равен 0.`;
    }
    if (scopeConfig.max_calls_per_run <= 0) {
        return `${labelText} отключена: лимит запусков на run равен 0.`;
    }
    if (scopeConfig.max_calls_per_day <= 0) {
        return `${labelText} отключена: дневной лимит запусков равен 0.`;
    }
    return null;
}

function useAIQualityControlBlock(
    scope: AIQualityScopeKey,
    labelText: string,
): string | null {
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        let mounted = true;
        fetchAIQualityControls()
            .then((response) => {
                if (!mounted) return;
                setMessage(qualityControlBlockMessage(response.config[scope], labelText));
            })
            .catch(() => {
                if (mounted) setMessage(null);
            });
        return () => {
            mounted = false;
        };
    }, [labelText, scope]);

    return message;
}

export default function App() {
    const routeMode = getAppRouteMode();

    if (routeMode === 'acceptance-public') {
        return <PublicAcceptanceApp />;
    }

    return <DashboardApp />;
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
    const [activeView, setActiveView] = useState<ViewId>('conversations');
    const [period, setPeriod] = useState<Period>('all_time');
    const { data, timeseries, loading, error, refetch } = useMetrics(period);
    const activeNavItem = NAV_ITEMS.find((item) => item.id === activeView);
    const activeLabel = activeView === 'support' ? 'Поддержка' : activeNavItem?.label;

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
                            <p className="text-[11px] font-semibold uppercase leading-4 text-[#7c839b]">Панель управления</p>
                        </div>
                    </div>
                    <div className="mb-6 rounded-lg border border-[#273247] bg-[#18243a] px-3 py-3">
                        <div className="flex items-center gap-2 text-sm font-semibold text-white">
                            <ShieldCheck size={16} />
                            <span>Режим мониторинга</span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[#9ca3af]">
                            История и аудит без ручных сообщений клиентам.
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
                                    <span>{item.label}</span>
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
                            <span>Поддержка</span>
                        </button>
                    </div>
                </aside>

                <main className="min-w-0 flex-1">
                    <header className="flex h-16 items-center justify-between border-b border-[#c6c6cd] bg-[#f8f9ff] px-6">
                        <div className="flex items-center gap-5">
                            <h2 className="text-xl font-semibold text-[#000]">Noor CRM</h2>
                            <div className="relative">
                                <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                                <input
                                    placeholder="Поиск..."
                                    className="h-9 w-[300px] rounded-lg border border-[#c6c6cd] bg-[#eff4ff] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {activeView === 'overview' && (
                                <SegmentedControl
                                    items={PERIODS}
                                    value={period}
                                    onChange={setPeriod}
                                />
                            )}
                            <button
                                type="button"
                                onClick={() => void refetch()}
                                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[#c6c6cd] bg-white text-[#3f465c] hover:bg-[#f2f4f7]"
                                title="Обновить"
                            >
                                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                            </button>
                            <div className="ml-2 flex h-9 items-center gap-2 border-l border-[#c6c6cd] pl-4 text-sm font-medium text-[#0b1c30]">
                                <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[#c6c6cd] bg-[#d8e2ff] text-[#004395]">
                                    <Settings size={15} />
                                </div>
                                <span>Администратор</span>
                            </div>
                        </div>
                    </header>

                    <div className="border-b border-[#e5e7eb] bg-white px-6 py-4">
                        <p className="text-xs font-semibold uppercase text-[#45464d]">
                            {activeLabel}
                        </p>
                        <h2 className="mt-1 text-2xl font-semibold text-[#0b1c30]">
                            {activeView === 'conversations'
                                ? 'Клиенты и диалоги'
                                : activeView === 'botRules'
                                    ? 'Правила поведения бота'
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
                    {activeView === 'conversations' && <ConversationsView />}
                    {activeView === 'queues' && <QueuesView />}
                    {activeView === 'knowledge' && <KnowledgeBaseView />}
                    {activeView === 'botRules' && <BotRulesView />}
                    {activeView === 'catalog' && <CatalogView />}
                    {activeView === 'quality' && <QualityView refetch={refetch} />}
                    {activeView === 'reports' && <ReportsView />}
                    {activeView === 'settings' && <SettingsView />}
                    {activeView === 'audit' && <AuditView />}
                    {activeView === 'support' && <SupportView />}
                </main>
            </div>
        </div>
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
    if (!data) {
        return (
            <section className="p-6">
                <div className="grid grid-cols-4 gap-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div key={index} className="h-24 rounded-md bg-white shadow-sm" />
                    ))}
                </div>
            </section>
        );
    }

    return (
        <section className="space-y-5 p-6">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <MetricTile label="Диалоги" value={data.total_conversations} note={`${data.unique_customers} клиентов`} />
                <MetricTile label="Эскалации" value={data.escalation_count} note="очередь менеджеров" tone="amber" />
                <MetricTile label="Конверсия" value={`${data.conversion_rate}%`} note={`${data.noor_sales.count + data.post_escalation_sales.count} сделок`} tone="green" />
                <MetricTile label="Качество" value={`${data.avg_quality_score}/30`} note={`${data.avg_manager_score}/20 менеджеры`} tone="blue" />
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

            <OverviewActionPanel data={data} refetch={refetch} />
        </section>
    );
}

function SupportView() {
    return (
        <section className="space-y-5 p-6">
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
                <Panel
                    title="Поддержка администратора"
                    subtitle="Внутренний канал для CRM-инцидентов, доступа и production smoke/regression."
                    icon={LifeBuoy}
                >
                    <div className="space-y-3">
                        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                            <p className="text-sm font-semibold text-[#0b1c30]">Telegram admin channel</p>
                            <p className="mt-1 text-sm leading-6 text-[#45464d]">
                                Используйте рабочий Telegram-чат Noor/Treejar для доступа, smoke evidence и срочных runtime-вопросов.
                            </p>
                        </div>
                        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                            <p className="text-sm font-semibold text-[#0b1c30]">Runtime target</p>
                            <p className="mt-1 text-sm leading-6 text-[#45464d]">https://noor.starec.ai</p>
                        </div>
                    </div>
                </Panel>

                <Panel
                    title="Production smoke checklist"
                    subtitle="Сводка для повторной проверки после локальной верификации и deploy approval."
                    icon={ShieldCheck}
                >
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <StatusCard title="Auth" value="401/200" note="anonymous guard и Telegram login" tone="green" />
                        <StatusCard title="CRM" value="Admin" note="диалоги, очереди, база знаний, аудит" tone="blue" />
                        <StatusCard title="Mutation" value="Guarded" note="только disposable/test data" tone="amber" />
                        <StatusCard title="Deploy" value="Manual" note="требует отдельного разрешения" />
                    </div>
                </Panel>
            </div>
        </section>
    );
}

function ConversationsView() {
    const [search, setSearch] = useState('');
    const [status, setStatus] = useState('');
    const [customers, setCustomers] = useState<AdminCustomerListItem[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [detail, setDetail] = useState<AdminConversationDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const [actionBusy, setActionBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const botQaBlock = useAIQualityControlBlock('bot_qa', 'Bot QA');

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
                if (!cancelled) setError(errorMessage(err));
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [search, selectedId, status]);

    useEffect(() => {
        if (!selectedId) return;
        let cancelled = false;
        fetchAdminConversation(selectedId)
            .then((payload) => {
                if (!cancelled) setDetail(payload);
            })
            .catch((err: unknown) => {
                if (!cancelled) setError(errorMessage(err));
            });
        return () => {
            cancelled = true;
        };
    }, [selectedId]);

    async function patchConversation(payload: Parameters<typeof updateAdminConversation>[1]) {
        if (!detail) return;
        setActionBusy(true);
        try {
            const updated = await updateAdminConversation(detail.id, payload);
            setDetail(updated);
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setActionBusy(false);
        }
    }

    async function handleResetPreview() {
        if (!detail || !globalThis.confirm('Показать preview reset для этого клиента?')) return;
        setActionBusy(true);
        try {
            const preview = await previewConversationReset(detail.id);
            globalThis.alert(JSON.stringify(preview, null, 2));
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setActionBusy(false);
        }
    }

    async function handleBotQa() {
        if (!detail || botQaBlock || !globalThis.confirm('Запустить ручную Bot QA проверку?')) return;
        setActionBusy(true);
        try {
            await runBotQualityReview(detail.id);
            const updated = await fetchAdminConversation(detail.id);
            setDetail(updated);
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setActionBusy(false);
        }
    }

    return (
        <section className="grid h-[calc(100vh-145px)] grid-cols-[320px_minmax(360px,1fr)_340px] overflow-hidden">
            <div className="border-r border-[#c6c6cd] bg-white">
                <div className="space-y-3 border-b border-[#c6c6cd] p-4">
                    <div className="relative">
                        <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Телефон, имя, Zoho, SO"
                            className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                        />
                    </div>
                    <select
                        value={status}
                        onChange={(event) => setStatus(event.target.value)}
                        className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                    >
                        <option value="">Все статусы</option>
                        <option value="active">Активные</option>
                        <option value="paused">Пауза</option>
                        <option value="closed">Закрытые</option>
                        <option value="escalated">Эскалация</option>
                    </select>
                </div>
                <div className="h-[calc(100%-112px)] overflow-auto">
                    {loading && <StateLine text="Загрузка клиентов..." />}
                    {error && <StateLine text={error} tone="red" />}
                    {!loading && customers.length === 0 && <StateLine text="Клиенты не найдены" />}
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
                                {customer.latest_message_preview || 'Сообщений нет'}
                            </p>
                            <div className="mt-2 flex items-center gap-2 text-xs text-[#45464d]">
                                <span>{label(customer.sales_stage)}</span>
                                <span>·</span>
                                <span>{customer.conversation_count} диал.</span>
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
                                {detail?.customer_name || detail?.phone || 'Диалог не выбран'}
                            </p>
                            <p className="text-xs text-[#45464d]">
                                {detail ? `${detail.phone} · ${label(detail.sales_stage)} · ${detail.message_count} сообщений` : 'Выберите клиента слева'}
                            </p>
                        </div>
                        {detail && <Badge label={label(detail.escalation_status)} tone="amber" />}
                    </div>
                </div>
                <div className="flex-1 space-y-3 overflow-auto px-6 py-5">
                    {!detail && <StateLine text="Выберите клиента, чтобы открыть полный timeline" />}
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
                                <span>{message.role === 'user' ? 'Клиент' : message.role === 'assistant' ? 'Бот' : 'Менеджер'}</span>
                                <span>{formatDate(message.created_at)}</span>
                            </div>
                            <p className="whitespace-pre-wrap leading-6 text-[#0b1c30]">{message.content}</p>
                        </div>
                    ))}
                </div>
            </div>

            <aside className="overflow-auto border-l border-[#c6c6cd] bg-white">
                <div className="space-y-4 p-4">
                    <InspectorBlock title="CRM">
                        <Field label="Имя" value={detail?.customer_name || '—'} />
                        <Field label="Телефон" value={detail?.phone || '—'} />
                        <Field label="Язык" value={detail?.language || '—'} />
                        <Field label="Zoho contact" value={detail?.zoho_contact_id || '—'} />
                        <Field label="Zoho deal" value={detail?.zoho_deal_id || '—'} />
                    </InspectorBlock>

                    <InspectorBlock title="Стадия и заказ">
                        <Field label="Статус" value={detail ? label(detail.status) : '—'} />
                        <Field label="Этап" value={detail ? label(detail.sales_stage) : '—'} />
                        <Field label="Сделка" value={detail?.deal_status ? label(detail.deal_status) : '—'} />
                        <Field label="Сумма" value={detail?.deal_amount ? `${detail.deal_amount} AED` : '—'} />
                    </InspectorBlock>

                    <InspectorBlock title="Действия">
                        {botQaBlock && <StateLine text={botQaBlock} tone="red" />}
                        <div className="grid grid-cols-2 gap-2">
                            <IconButton
                                icon={CheckCircle2}
                                label="Закрыть"
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
                                label="Reset preview"
                                disabled={!detail || actionBusy}
                                onClick={() => void handleResetPreview()}
                            />
                            <IconButton
                                icon={AlertTriangle}
                                label="Эскалация"
                                disabled={!detail || actionBusy}
                                onClick={() => void patchConversation({ status: 'escalated', escalation_status: 'manual_takeover' })}
                            />
                        </div>
                    </InspectorBlock>

                    <InspectorBlock title="Оценки и аудит">
                        <Field label="Bot QA" value={detail?.quality_reviews[0] ? `${detail.quality_reviews[0].total_score}/${detail.quality_reviews[0].max_score}` : '—'} />
                        <Field label="Manager QA" value={detail?.manager_reviews[0] ? `${detail.manager_reviews[0].total_score}/${detail.manager_reviews[0].max_score}` : '—'} />
                        <Field label="Эскалации" value={String(detail?.escalations.length ?? 0)} />
                        <Field label="Исходящие" value={String(detail?.outbound_audits.length ?? 0)} />
                    </InspectorBlock>

                    <InspectorBlock title="Applied bot rules">
                        {!detail?.applied_bot_rules.length && <StateLine text="Правила не применялись" />}
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
    );
}

function KnowledgeBaseView() {
    const [entries, setEntries] = useState<AdminKnowledgeBaseRead[]>([]);
    const [candidates, setCandidates] = useState<AdminKnowledgeBaseCandidate[]>([]);
    const [selected, setSelected] = useState<AdminKnowledgeBaseRead | null>(null);
    const [form, setForm] = useState<AdminKnowledgeBaseWrite>(EMPTY_KB_FORM);
    const [preview, setPreview] = useState<AdminKnowledgeBasePreview | null>(null);
    const [search, setSearch] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const load = useMemo(
        () => async () => {
            const params = new URLSearchParams({ page_size: '50' });
            if (search.trim()) params.set('search', search.trim());
            const [entryPayload, candidatePayload] = await Promise.all([
                fetchKnowledgeBaseEntries(params),
                fetchKnowledgeBaseCandidates(new URLSearchParams({ status: 'needs_confirmation' })),
            ]);
            setEntries(entryPayload.items);
            setCandidates(candidatePayload.items);
            if (!selected && entryPayload.items[0]) {
                setSelected(entryPayload.items[0]);
                setForm(entryToForm(entryPayload.items[0]));
            }
        },
        [search, selected],
    );

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err)));
    }, [load]);

    async function handlePreview() {
        setBusy(true);
        try {
            setPreview(await previewKnowledgeBaseEntry(form));
        } catch (err) {
            setError(errorMessage(err));
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
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    async function handleDelete(entry: AdminKnowledgeBaseRead | null) {
        if (!entry || !globalThis.confirm('Удалить запись мягко?')) return;
        setBusy(true);
        try {
            await softDeleteKnowledgeBaseEntry(entry.id);
            setEntries((current) => current.filter((item) => item.id !== entry.id));
            setSelected(null);
            setForm(EMPTY_KB_FORM);
            setPreview(null);
            await load();
        } catch (err) {
            setError(errorMessage(err));
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
            setError(errorMessage(err));
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
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    async function handleReject(candidateId: string) {
        if (!globalThis.confirm('Отклонить Auto-FAQ кандидата?')) return;
        setBusy(true);
        try {
            await rejectKnowledgeBaseCandidate(candidateId, { reason: 'admin_rejected' });
            setCandidates((current) => current.filter((candidate) => candidate.id !== candidateId));
            await load();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    return (
        <section className="grid h-[calc(100vh-145px)] grid-cols-[300px_minmax(420px,1fr)_360px] overflow-hidden">
            <div className="border-r border-[#c6c6cd] bg-white">
                <div className="border-b border-[#c6c6cd] p-4">
                    <div className="relative">
                        <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Поиск в базе знаний"
                            className="h-9 w-full rounded-md border border-[#c6c6cd] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                        />
                    </div>
                </div>
                <div className="h-[calc(100%-73px)] overflow-auto">
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
                                <Badge label={entry.has_embedding ? 'Indexed' : 'No index'} tone={entry.has_embedding ? 'green' : 'amber'} />
                            </div>
                            <p className="mt-1 line-clamp-2 text-sm text-[#45464d]">{entry.content}</p>
                            <p className="mt-2 text-xs text-[#45464d]">{entry.source} · {entry.language} · {entry.category || '—'}</p>
                        </button>
                    ))}
                </div>
            </div>

            <div className="overflow-auto bg-[#f8f9ff] p-5">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-base font-semibold text-[#0b1c30]">Редактор</h3>
                    <button
                        type="button"
                        onClick={() => {
                            setSelected(null);
                            setForm(EMPTY_KB_FORM);
                            setPreview(null);
                        }}
                        className="rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                    >
                        Новая запись
                    </button>
                </div>
                {error && <StateLine text={error} tone="red" />}
                <div className="space-y-3 rounded-md border border-[#c6c6cd] bg-white p-4">
                    <Input label="Заголовок" value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
                    <div className="grid grid-cols-3 gap-3">
                        <Input label="Source" value={form.source} onChange={(value) => setForm({ ...form, source: value })} />
                        <Select
                            label="Язык"
                            value={form.language}
                            options={[
                                { label: 'EN', value: 'en' },
                                { label: 'AR', value: 'ar' },
                            ]}
                            onChange={(value) => setForm({ ...form, language: value as 'en' | 'ar' })}
                        />
                        <Input label="Категория" value={form.category || ''} onChange={(value) => setForm({ ...form, category: value || null })} />
                    </div>
                    <label className="block">
                        <span className="text-xs font-medium text-[#45464d]">Контент</span>
                        <textarea
                            value={form.content}
                            onChange={(event) => setForm({ ...form, content: event.target.value })}
                            className="mt-1 min-h-[220px] w-full rounded-md border border-[#c6c6cd] px-3 py-2 text-sm leading-6 outline-none focus:border-[#0058be]"
                        />
                    </label>
                    <div className="flex flex-wrap gap-2">
                        <IconButton icon={Search} label="Preview" disabled={busy} onClick={() => void handlePreview()} />
                        <IconButton icon={Save} label="Save and index" disabled={busy} onClick={() => void handleSave()} />
                        <IconButton icon={RefreshCw} label="Reindex" disabled={!selected || busy} onClick={() => void handleReindex()} />
                        <IconButton icon={Trash2} label="Soft-delete" disabled={!selected || busy} onClick={() => void handleDelete(selected)} danger />
                    </div>
                </div>
            </div>

            <aside className="overflow-auto border-l border-[#c6c6cd] bg-white p-4">
                <InspectorBlock title="Embedding preview">
                    <Field label="Embedding" value={preview?.embedding_ready ? 'Готов' : '—'} />
                    <Field label="Дубликат" value={preview?.duplicate ? 'Да' : 'Нет'} />
                    <Field label="Similarity" value={preview?.duplicate_similarity ? preview.duplicate_similarity.toFixed(3) : '—'} />
                    <Field label="Unsafe" value={preview?.unsafe_reasons.join(', ') || '—'} />
                    <Field label="Context" value={preview?.context_reasons.join(', ') || '—'} />
                </InspectorBlock>

                <InspectorBlock title="Auto-FAQ queue">
                    {candidates.length === 0 && <StateLine text="Кандидатов нет" />}
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
                                        Reject
                                    </button>
                                    <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => void handleApprove(candidate.id)}
                                        className="rounded-md bg-[#0058be] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                    >
                                        Approve
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </InspectorBlock>
            </aside>
        </section>
    );
}

function BotRulesView() {
    const [rules, setRules] = useState<AdminBotRuleRead[]>([]);
    const [selected, setSelected] = useState<AdminBotRuleRead | null>(null);
    const [form, setForm] = useState<AdminBotRuleWrite>(EMPTY_BOT_RULE_FORM);
    const [preview, setPreview] = useState<AdminBotRulePreviewResponse | null>(null);
    const [search, setSearch] = useState('');
    const [status, setStatus] = useState('active');
    const [testMessage, setTestMessage] = useState('Customer says: I need 20 chairs for my office');
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const load = useMemo(
        () => async () => {
            const params = new URLSearchParams({ page_size: '50' });
            if (search.trim()) params.set('search', search.trim());
            if (status) params.set('status', status);
            const payload = await fetchBotRules(params);
            setRules(payload.items);
            if (!selected && payload.items[0]) {
                setSelected(payload.items[0]);
                setForm(ruleToForm(payload.items[0]));
            }
        },
        [search, selected, status],
    );

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err)));
    }, [load]);

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
            setError(errorMessage(err));
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
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    async function handleArchive() {
        if (!selected || !globalThis.confirm('Архивировать правило бота?')) return;
        setBusy(true);
        try {
            await archiveBotRule(selected.id);
            setSelected(null);
            setForm(EMPTY_BOT_RULE_FORM);
            setPreview(null);
            await load();
        } catch (err) {
            setError(errorMessage(err));
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
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    return (
        <section className="grid h-[calc(100vh-145px)] grid-cols-[300px_minmax(440px,1fr)_380px] overflow-hidden">
            <div className="border-r border-[#c6c6cd] bg-white">
                <div className="space-y-3 border-b border-[#c6c6cd] p-4">
                    <div className="relative">
                        <Search size={16} className="absolute left-3 top-2.5 text-[#45464d]" />
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Поиск правил"
                            className="h-9 w-full rounded-md border border-[#c6c6cd] pl-9 pr-3 text-sm outline-none focus:border-[#0058be]"
                        />
                    </div>
                    <select
                        value={status}
                        onChange={(event) => setStatus(event.target.value)}
                        className="h-9 w-full rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                    >
                        <option value="">Все статусы</option>
                        <option value="active">Активные</option>
                        <option value="draft">Черновики</option>
                        <option value="archived">Архив</option>
                    </select>
                </div>
                <div className="h-[calc(100%-121px)] overflow-auto">
                    {rules.length === 0 && <StateLine text="Правила не найдены" />}
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
                    <h3 className="text-base font-semibold text-[#0b1c30]">Редактор правил</h3>
                    <button
                        type="button"
                        onClick={() => {
                            setSelected(null);
                            setForm(EMPTY_BOT_RULE_FORM);
                            setPreview(null);
                        }}
                        className="rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                    >
                        Новое правило
                    </button>
                </div>
                {error && <StateLine text={error} tone="red" />}
                <div className="space-y-3 rounded-md border border-[#c6c6cd] bg-white p-4">
                    <Input label="Название" value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
                    <div className="grid grid-cols-2 gap-3">
                        <Select
                            label="Тип"
                            value={form.type}
                            options={[
                                { label: 'Жесткое', value: 'hard_rule' },
                                { label: 'Сценарий', value: 'playbook' },
                                { label: 'Допродажа', value: 'upsell_rule' },
                                { label: 'Стиль', value: 'style_rule' },
                                { label: 'Эскалация', value: 'escalation_rule' },
                            ]}
                            onChange={(value) => setForm({ ...form, type: value as AdminBotRuleWrite['type'] })}
                        />
                        <Select
                            label="Статус"
                            value={form.status}
                            options={[
                                { label: 'Черновик', value: 'draft' },
                                { label: 'Активно', value: 'active' },
                                { label: 'Архив', value: 'archived' },
                            ]}
                            onChange={(value) => setForm({ ...form, status: value as AdminBotRuleWrite['status'] })}
                        />
                    </div>
                    <div className="grid grid-cols-4 gap-3">
                        <Input label="Priority" value={String(form.priority)} onChange={(value) => setForm({ ...form, priority: Number(value) || 0 })} />
                        <Select
                            label="Scope"
                            value={form.scope}
                            options={[
                                { label: 'Global', value: 'global' },
                                { label: 'Stage', value: 'stage' },
                                { label: 'Language', value: 'language' },
                                { label: 'Segment', value: 'segment' },
                                { label: 'Conversation', value: 'conversation' },
                            ]}
                            onChange={(value) => setForm({ ...form, scope: value as AdminBotRuleWrite['scope'] })}
                        />
                        <Select
                            label="Stage"
                            value={form.stage || ''}
                            options={[
                                { label: 'Любой', value: '' },
                                { label: 'Greeting', value: 'greeting' },
                                { label: 'Qualifying', value: 'qualifying' },
                                { label: 'Needs', value: 'needs_analysis' },
                                { label: 'Solution', value: 'solution' },
                                { label: 'Quote', value: 'quoting' },
                                { label: 'Closing', value: 'closing' },
                            ]}
                            onChange={(value) => setForm({ ...form, stage: value || null })}
                        />
                        <Select
                            label="Язык"
                            value={form.language || ''}
                            options={[
                                { label: 'Любой', value: '' },
                                { label: 'EN', value: 'en' },
                                { label: 'AR', value: 'ar' },
                            ]}
                            onChange={(value) => setForm({ ...form, language: value === 'ar' || value === 'en' ? value : null })}
                        />
                    </div>
                    <Input label="Сегмент" value={form.segment || ''} onChange={(value) => setForm({ ...form, segment: value || null })} />
                    <label className="block">
                        <span className="text-xs font-medium text-[#45464d]">Instruction</span>
                        <textarea
                            value={form.instruction}
                            onChange={(event) => setForm({ ...form, instruction: event.target.value })}
                            className="mt-1 min-h-[180px] w-full rounded-md border border-[#c6c6cd] px-3 py-2 text-sm leading-6 outline-none focus:border-[#0058be]"
                        />
                    </label>
                    <label className="block">
                        <span className="text-xs font-medium text-[#45464d]">Trigger examples</span>
                        <textarea
                            value={form.trigger_examples.join('\n')}
                            onChange={(event) => setForm({ ...form, trigger_examples: event.target.value.split('\n').map((item) => item.trim()).filter(Boolean) })}
                            className="mt-1 min-h-[90px] w-full rounded-md border border-[#c6c6cd] px-3 py-2 text-sm leading-6 outline-none focus:border-[#0058be]"
                        />
                    </label>
                    <div className="flex flex-wrap gap-2">
                        <IconButton icon={Search} label="Preview" disabled={busy} onClick={() => void handlePreview()} />
                        <IconButton icon={Save} label="Save and index" disabled={busy} onClick={() => void handleSave()} />
                        <IconButton icon={RefreshCw} label="Reindex" disabled={!selected || busy} onClick={() => void handleReindex()} />
                        <IconButton icon={Trash2} label="Archive" disabled={!selected || busy} onClick={() => void handleArchive()} danger />
                    </div>
                </div>
            </div>

            <aside className="overflow-auto border-l border-[#c6c6cd] bg-white p-4">
                <InspectorBlock title="Rule preview">
                    <label className="block">
                        <span className="text-xs font-medium text-[#45464d]">Test message</span>
                        <textarea
                            value={testMessage}
                            onChange={(event) => setTestMessage(event.target.value)}
                            className="mt-1 min-h-[110px] w-full rounded-md border border-[#c6c6cd] px-3 py-2 text-sm leading-6 outline-none focus:border-[#0058be]"
                        />
                    </label>
                    <Field label="Applied" value={String(preview?.rule_count ?? 0)} />
                    {preview?.applied_rules.map((rule) => (
                        <div key={rule.id} className="border-b border-[#e5eeff] py-2">
                            <p className="text-sm font-semibold text-[#0b1c30]">{rule.title}</p>
                            <p className="mt-1 text-xs text-[#45464d]">P{rule.priority} · {label(rule.type)}</p>
                        </div>
                    ))}
                </InspectorBlock>

                <InspectorBlock title="Prompt block">
                    <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-md bg-[#0b1c30] p-3 text-xs leading-5 text-[#f8fafc]">
                        {preview?.prompt_block || '[BOT OPERATING RULES]'}
                    </pre>
                </InspectorBlock>
            </aside>
        </section>
    );
}

function AuditView() {
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
            .catch((err: unknown) => setError(errorMessage(err)));
    }, [entityType]);

    return (
        <section className="grid gap-5 p-6 xl:grid-cols-[1.1fr_0.9fr]">
            {error && <StateLine text={error} tone="red" />}
            <Panel
                title="Журнал системных действий"
                subtitle="Фиксируем кто, что и где изменил. Секреты маскируются на backend."
                icon={History}
                action={(
                    <select
                        value={entityType}
                        onChange={(event) => setEntityType(event.target.value)}
                        className="h-9 rounded-md border border-[#c6c6cd] bg-white px-3 text-sm outline-none focus:border-[#0058be]"
                    >
                        <option value="">Все сущности</option>
                        <option value="conversation">Диалоги</option>
                        <option value="knowledge_base">База знаний</option>
                        <option value="knowledge_base_candidate">Кандидаты FAQ</option>
                        <option value="bot_behavior_rule">Правила бота</option>
                    </select>
                )}
            >
                <div className="overflow-hidden rounded-md border border-[#c6c6cd] bg-white">
                    <table className="min-w-full divide-y divide-[#e5eeff] text-sm">
                        <thead className="bg-[#f8f9ff] text-left text-xs uppercase text-[#45464d]">
                            <tr>
                                <th className="px-4 py-3">Время</th>
                                <th className="px-4 py-3">Действие</th>
                                <th className="px-4 py-3">Сущность</th>
                                <th className="px-4 py-3">Path</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#e5eeff]">
                            {rows.map((row) => (
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
                </div>
            </Panel>

            <Panel
                title="Детали изменения"
                subtitle="Before/after сохраняем как JSON, чтобы расследовать изменения без SQLAdmin."
                icon={ShieldCheck}
            >
                {selected ? (
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <Field label="Actor" value={selected.actor} />
                            <Field label="Action" value={selected.action} />
                            <Field label="Entity" value={`${selected.entity_type}:${selected.entity_id || '—'}`} />
                            <Field label="Path" value={selected.request_path || '—'} />
                        </div>
                        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                            <JsonPreview title="Before" value={selected.before} />
                            <JsonPreview title="After" value={selected.after} />
                        </div>
                        <JsonPreview title="Metadata" value={selected.metadata} />
                    </div>
                ) : (
                    <StateLine text="Выберите запись аудита" />
                )}
            </Panel>
        </section>
    );
}

function OverviewActionPanel({
    data,
    refetch,
}: {
    data: NonNullable<ReturnType<typeof useMetrics>['data']>;
    refetch: () => void;
}) {
    return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Panel
                title="Рабочие очереди"
                subtitle="Операционные зоны, которые требуют внимания администратора."
                icon={Inbox}
            >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <StatusCard
                        title="Эскалации"
                        value={data.escalation_count}
                        note="переходят в очередь менеджеров"
                        tone="amber"
                    />
                    <StatusCard
                        title="Сделки"
                        value={data.noor_sales.count + data.post_escalation_sales.count}
                        note={`${data.conversion_rate}% конверсия`}
                        tone="green"
                    />
                    <StatusCard
                        title="QA"
                        value={`${data.avg_quality_score}/30`}
                        note="средняя оценка бота"
                        tone="blue"
                    />
                </div>
            </Panel>

            <Panel
                title="Контроль без отправки"
                subtitle="CRM показывает историю, QA и аудит, но не добавляет ручную отправку клиентам."
                icon={ShieldCheck}
                action={(
                    <button
                        type="button"
                        onClick={() => void refetch()}
                        className="inline-flex items-center gap-2 rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7]"
                    >
                        <RefreshCw size={15} />
                        Обновить
                    </button>
                )}
            >
                <div className="space-y-3 text-sm text-[#3f465c]">
                    <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-4 py-3">
                        Полные диалоги открываются по клиентам, с timeline и CRM-инспектором справа.
                    </div>
                    <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-4 py-3">
                        Изменяющие действия проходят через admin API и попадают в audit log.
                    </div>
                </div>
            </Panel>
        </div>
    );
}

function QueuesView() {
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [candidates, setCandidates] = useState<AdminKnowledgeBaseCandidate[]>([]);
    const [loading, setLoading] = useState(true);
    const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
    const [approvingId, setApprovingId] = useState<string | null>(null);
    const [rejectingId, setRejectingId] = useState<string | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);
    const managerQaBlock = useAIQualityControlBlock('manager_qa', 'Manager QA');

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
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    async function handleEvaluate(item: PendingManagerReview) {
        if (managerQaBlock || !globalThis.confirm('Запустить Manager QA для этой эскалации?')) return;
        setEvaluatingId(item.escalation_id);
        setMessage(null);
        try {
            const review = await evaluateManagerReview(item.escalation_id);
            setMessage({
                tone: 'success',
                text: `Manager QA готов: ${review.total_score}/${review.max_score}.`,
            });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setEvaluatingId(null);
        }
    }

    async function handleApprove(candidate: AdminKnowledgeBaseCandidate) {
        if (!globalThis.confirm('Подтвердить Auto-FAQ кандидата и добавить его в базу знаний?')) return;
        setApprovingId(candidate.id);
        setMessage(null);
        try {
            await approveKnowledgeBaseCandidate(candidate.id);
            setMessage({ tone: 'success', text: 'FAQ-кандидат добавлен в базу знаний.' });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setApprovingId(null);
        }
    }

    async function handleReject(candidate: AdminKnowledgeBaseCandidate) {
        if (!globalThis.confirm('Отклонить Auto-FAQ кандидата?')) return;
        setRejectingId(candidate.id);
        setMessage(null);
        try {
            await rejectKnowledgeBaseCandidate(candidate.id, { reason: 'admin_rejected' });
            setMessage({ tone: 'success', text: 'FAQ-кандидат отклонен.' });
            await load();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setRejectingId(null);
        }
    }

    return (
        <section className="space-y-5 p-6">
            {message && <ActionMessageBox message={message} />}
            {managerQaBlock && <ActionMessageBox message={{ tone: 'info', text: managerQaBlock }} />}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <StatusCard title="Manager QA pending" value={pendingReviews.length} note="закрытые эскалации без оценки" tone="amber" />
                <StatusCard title="Auto-FAQ candidates" value={candidates.length} note="требуют подтверждения" tone="blue" />
                <StatusCard title="Режим" value={loading ? '...' : 'Live'} note="данные из admin API" tone="green" />
            </div>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
                <Panel
                    title="Эскалации на проверку"
                    subtitle="Resolved-эскалации, где можно вручную запустить Manager QA."
                    icon={ClipboardList}
                    action={<RefreshButton loading={loading} onClick={() => void load()} />}
                >
                    <div className="space-y-3">
                        {!loading && pendingReviews.length === 0 && <StateLine text="Очередь эскалаций пуста" />}
                        {pendingReviews.map((item) => (
                            <div key={item.escalation_id} className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                    <div>
                                        <p className="text-sm font-semibold text-[#0b1c30]">{item.manager_name || 'Менеджер не назначен'}</p>
                                        <p className="mt-1 text-sm text-[#3f465c]">{item.phone}</p>
                                        <p className="mt-2 text-sm text-[#45464d]">{item.reason}</p>
                                        <p className="mt-2 text-xs text-[#7c839b]">Обновлено {formatDateTime(item.updated_at)}</p>
                                    </div>
                                    <button
                                        type="button"
                                        disabled={evaluatingId !== null || Boolean(managerQaBlock)}
                                        onClick={() => void handleEvaluate(item)}
                                        className="inline-flex items-center justify-center gap-2 rounded-md border border-[#f59e0b] bg-[#fff7ed] px-3 py-2 text-sm font-medium text-[#92400e] hover:bg-[#ffedd5] disabled:opacity-50"
                                    >
                                        {evaluatingId === item.escalation_id ? <RefreshCw size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
                                        Evaluate
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>

                <Panel
                    title="Auto-FAQ queue"
                    subtitle="Кандидаты из ответов менеджеров не становятся trusted knowledge без approval."
                    icon={BookOpen}
                >
                    <div className="space-y-3">
                        {!loading && candidates.length === 0 && <StateLine text="Кандидатов нет" />}
                        {candidates.map((candidate) => (
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
                                            {rejectingId === candidate.id ? 'Rejecting...' : 'Reject'}
                                        </button>
                                        <button
                                            type="button"
                                            disabled={approvingId !== null || rejectingId !== null}
                                            onClick={() => void handleApprove(candidate)}
                                            className="rounded-md bg-[#0058be] px-3 py-2 text-xs font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                                        >
                                            {approvingId === candidate.id ? 'Saving...' : 'Approve'}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>
            </div>
        </section>
    );
}

function CatalogView() {
    const [syncingSource, setSyncingSource] = useState<ProductSyncSource | null>(null);
    const [result, setResult] = useState<ProductSyncResponse | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    async function handleSync(source: ProductSyncSource) {
        const sourceLabel = source === 'treejar' ? 'Treejar' : 'Zoho';
        if (!globalThis.confirm(`Запустить синхронизацию каталога из ${sourceLabel}?`)) return;
        setSyncingSource(source);
        setMessage(null);
        try {
            const response = await syncProducts(source);
            setResult(response);
            setMessage({
                tone: response.errors > 0 ? 'info' : 'success',
                text: `${sourceLabel} sync поставлен в очередь. Ошибок: ${response.errors}.`,
            });
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setSyncingSource(null);
        }
    }

    return (
        <section className="space-y-5 p-6">
            {message && <ActionMessageBox message={message} />}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
                <Panel
                    title="Синхронизация товаров"
                    subtitle="Treejar остается основным источником каталога; Zoho доступен как legacy mirror."
                    icon={Package}
                >
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-1">
                        <CatalogSyncCard
                            title="Treejar catalog"
                            note="Рекомендуемый canonical refresh: товары, цены, наличие и embeddings."
                            source="treejar"
                            syncingSource={syncingSource}
                            onSync={handleSync}
                        />
                        <CatalogSyncCard
                            title="Zoho mirror"
                            note="Операционная сверка legacy stock/deal данных без смены источника истины."
                            source="zoho"
                            syncingSource={syncingSource}
                            onSync={handleSync}
                        />
                    </div>
                </Panel>

                <Panel
                    title="Результат последнего запуска"
                    subtitle="Показываем только локальный результат текущей admin-сессии; история действий уходит в аудит."
                    icon={History}
                >
                    {result ? (
                        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                            <StatusCard title="Synced" value={result.synced} note="всего обработано" />
                            <StatusCard title="Created" value={result.created} note="новые товары" tone="green" />
                            <StatusCard title="Updated" value={result.updated} note="обновленные товары" tone="blue" />
                            <StatusCard title="Deactivated" value={result.deactivated} note="скрыты из выдачи" tone="amber" />
                            <StatusCard title="Embeddings" value={result.embeddings_generated} note="переиндексировано" tone="blue" />
                            <StatusCard title="Errors" value={result.errors} note="ошибки интеграции" tone={result.errors > 0 ? 'amber' : 'green'} />
                        </div>
                    ) : (
                        <StateLine text="Запустите sync, чтобы увидеть результат текущего запуска" />
                    )}
                </Panel>
            </div>
        </section>
    );
}

function QualityView({ refetch }: { refetch: () => void }) {
    const [pendingReviews, setPendingReviews] = useState<PendingManagerReview[]>([]);
    const [recentReviews, setRecentReviews] = useState<ManagerReviewRead[]>([]);
    const [loading, setLoading] = useState(true);
    const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);
    const managerQaBlock = useAIQualityControlBlock('manager_qa', 'Manager QA');

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
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    async function handleEvaluate(item: PendingManagerReview) {
        if (managerQaBlock || !globalThis.confirm('Запустить Manager QA и обновить качество?')) return;
        setEvaluatingId(item.escalation_id);
        setMessage(null);
        try {
            const review = await evaluateManagerReview(item.escalation_id);
            setMessage({ tone: 'success', text: `Оценка менеджера: ${review.total_score}/${review.max_score}.` });
            await load();
            void refetch();
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setEvaluatingId(null);
        }
    }

    const avgScore = recentReviews.length
        ? (recentReviews.reduce((sum, review) => sum + review.total_score, 0) / recentReviews.length).toFixed(1)
        : '—';
    const dealCount = recentReviews.filter((review) => review.deal_converted).length;

    return (
        <section className="space-y-5 p-6">
            {message && <ActionMessageBox message={message} />}
            {managerQaBlock && <ActionMessageBox message={{ tone: 'info', text: managerQaBlock }} />}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <StatusCard title="Pending QA" value={pendingReviews.length} note="эскалации без оценки" tone="amber" />
                <StatusCard title="Recent reviews" value={recentReviews.length} note="последние оценки" />
                <StatusCard title="Avg score" value={avgScore} note="по последним manager QA" tone="blue" />
                <StatusCard title="Converted" value={dealCount} note="сделки после эскалаций" tone="green" />
            </div>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_1fr]">
                <Panel
                    title="Manager QA queue"
                    subtitle="Очередь действий для контроля операторов."
                    icon={ClipboardList}
                    action={<RefreshButton loading={loading} onClick={() => void load()} />}
                >
                    <div className="space-y-3">
                        {!loading && pendingReviews.length === 0 && <StateLine text="Нет pending manager QA" />}
                        {pendingReviews.map((item) => (
                            <div key={item.escalation_id} className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="text-sm font-semibold text-[#0b1c30]">{item.manager_name || 'Менеджер не назначен'}</p>
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
                                        Evaluate
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>

                <Panel
                    title="Последние оценки"
                    subtitle="Быстрый срез качества менеджеров после эскалаций."
                    icon={ShieldCheck}
                >
                    <div className="overflow-hidden rounded-md border border-[#e5eeff]">
                        <table className="min-w-full divide-y divide-[#e5eeff] text-sm">
                            <thead className="bg-[#f8f9ff] text-left text-xs uppercase text-[#45464d]">
                                <tr>
                                    <th className="px-4 py-3">Менеджер</th>
                                    <th className="px-4 py-3">Оценка</th>
                                    <th className="px-4 py-3">Ответ</th>
                                    <th className="px-4 py-3">Сделка</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#e5eeff] bg-white">
                                {recentReviews.map((review) => (
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
        </section>
    );
}

function ReportsView() {
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
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadReport();
    }, [loadReport]);

    return (
        <section className="space-y-5 p-6">
            {message && <ActionMessageBox message={message} />}
            <Panel
                title="Аналитика продаж"
                subtitle="Операционный отчет по диалогам, сделкам, качеству и менеджерам."
                icon={FileText}
                action={<RefreshButton loading={loading} label="Сгенерировать" onClick={() => void loadReport()} />}
            >
                {report ? (
                    <div className="space-y-5">
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                            <StatusCard title="Диалоги" value={report.data.total_conversations} note={`${report.data.conversations_per_day} в день`} />
                            <StatusCard title="Конверсия" value={`${report.data.conversion_rate}%`} note={`${report.data.total_deals} сделок`} tone="green" />
                            <StatusCard title="Эскалации" value={report.data.escalation_count} note={`${Object.keys(report.data.escalation_reasons).length} причин`} tone="amber" />
                            <StatusCard title="Manager QA" value={`${report.data.avg_manager_score}/20`} note={`${report.data.manager_reviews_count} оценок`} tone="blue" />
                        </div>

                        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                            <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <p className="text-sm font-semibold text-[#0b1c30]">Telegram preview</p>
                                        <p className="mt-1 text-xs text-[#7c839b]">
                                            {formatDateTime(report.data.period_start)} - {formatDateTime(report.data.period_end)}
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
                                    title="Top products"
                                    icon={TrendingUp}
                                    empty="Товары появятся после SKU-упоминаний ассистента."
                                    items={report.data.top_products.map((product) => ({
                                        key: product.sku,
                                        title: product.name,
                                        meta: `${product.sku} · ${product.mentions} упоминаний`,
                                    }))}
                                />
                                <SideListPanel
                                    title="Top managers"
                                    icon={Clock}
                                    empty="Рейтинг появится после manager QA."
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
                    <StateLine text={loading ? 'Генерируем отчет...' : 'Отчет пока не загружен'} />
                )}
            </Panel>
        </section>
    );
}

function SettingsView() {
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
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadConfig();
    }, [loadConfig]);

    async function handleSendTest() {
        if (!globalThis.confirm('Отправить тестовое Telegram-уведомление администратору?')) return;
        setSendingTest(true);
        setMessage(null);
        try {
            const result = await sendTestNotification();
            setMessage({
                tone: result.status === 'sent' ? 'success' : 'info',
                text: result.status === 'sent'
                    ? 'Тестовое уведомление отправлено.'
                    : result.reason || 'Telegram integration is not configured.',
            });
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err) });
        } finally {
            setSendingTest(false);
        }
    }

    return (
        <section className="space-y-5 p-6">
            {message && <ActionMessageBox message={message} />}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                <Panel
                    title="Конфигурация системы"
                    subtitle="Shared admin session, Telegram health и безопасные ручные проверки."
                    icon={Settings}
                    action={<RefreshButton loading={loading} onClick={() => void loadConfig()} />}
                >
                    <div className="space-y-3">
                        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2">
                                    <Bell size={16} className="text-[#0058be]" />
                                    <p className="text-sm font-semibold text-[#0b1c30]">Telegram notifications</p>
                                </div>
                                <Badge label={config?.telegram_configured ? 'Configured' : 'Not configured'} tone={config?.telegram_configured ? 'green' : 'amber'} />
                            </div>
                            <Field label="Bot token" value={config?.telegram_bot_token || (loading ? 'Loading...' : '—')} />
                            <Field label="Chat ID" value={config?.telegram_chat_id || (loading ? 'Loading...' : '—')} />
                            <button
                                type="button"
                                disabled={sendingTest}
                                onClick={() => void handleSendTest()}
                                className="mt-4 inline-flex items-center gap-2 rounded-md bg-[#0058be] px-3 py-2 text-sm font-medium text-white hover:bg-[#004395] disabled:opacity-50"
                            >
                                {sendingTest ? <RefreshCw size={15} className="animate-spin" /> : <Send size={15} />}
                                Send test
                            </button>
                        </div>

                        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4">
                            <p className="text-sm font-semibold text-[#0b1c30]">Admin session</p>
                            <p className="mt-2 text-sm leading-6 text-[#45464d]">
                                В v1 остаемся на одном shared admin-login. Разделение ролей не добавляется, а все изменяющие действия пишутся в audit.
                            </p>
                        </div>
                    </div>
                </Panel>

                <AIQualityControlsPanel />
            </div>
        </section>
    );
}

function MetricTile({
    label: labelText,
    value,
    note,
    tone = 'gray',
}: {
    label: string;
    value: number | string;
    note: string;
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
            <p className="text-xs font-medium uppercase text-[#45464d]">{labelText}</p>
            <p className="mt-2 text-2xl font-semibold text-[#0b1c30]">{value}</p>
            <p className="mt-1 text-sm text-[#45464d]">{note}</p>
        </div>
    );
}

function Panel({
    title,
    subtitle,
    icon: Icon,
    action,
    children,
}: {
    title: string;
    subtitle?: string;
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
                        <h3 className="text-base font-semibold text-[#0b1c30]">{title}</h3>
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
    tone = 'gray',
}: {
    title: string;
    value: number | string;
    note: string;
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
            <p className="text-xs font-semibold uppercase text-[#45464d]">{title}</p>
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
    label = 'Обновить',
    onClick,
}: {
    loading: boolean;
    label?: string;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            disabled={loading}
            onClick={onClick}
            className="inline-flex items-center gap-2 rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm font-medium text-[#3f465c] hover:bg-[#f2f4f7] disabled:opacity-50"
        >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            {label}
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

function InspectorBlock({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="rounded-md border border-[#c6c6cd] bg-white p-4">
            <h3 className="text-sm font-semibold text-[#0b1c30]">{title}</h3>
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

function Input({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="block">
            <span className="text-xs font-medium text-[#45464d]">{label}</span>
            <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-[#c6c6cd] px-3 text-sm outline-none focus:border-[#0058be]"
            />
        </label>
    );
}

function Select({
    label,
    value,
    options,
    onChange,
}: {
    label: string;
    value: string;
    options: { label: string; value: string }[];
    onChange: (value: string) => void;
}) {
    return (
        <label className="block">
            <span className="text-xs font-medium text-[#45464d]">{label}</span>
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

function label(value: string): string {
    return STATUS_LABELS[value] ?? value;
}

function formatDate(value: string): string {
    return new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(value));
}

function formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('ru-RU', {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(new Date(value));
}

function formatDuration(seconds: number | null): string {
    if (seconds === null) return '—';
    if (seconds < 60) return `${Math.round(seconds)}с`;
    return `${(seconds / 60).toFixed(1)} мин`;
}

function stripHtml(text: string): string {
    return text.replace(/<[^>]+>/g, '').trim();
}

function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : 'Неизвестная ошибка';
}

function cx(...values: Array<string | false | null | undefined>): string {
    return values.filter(Boolean).join(' ');
}
