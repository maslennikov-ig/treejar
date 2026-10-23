import { useEffect, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import {
    AlertTriangle,
    Moon,
    RefreshCw,
    Search,
    Settings,
    Sun,
} from 'lucide-react';
import AcceptanceDemo from '@/components/AcceptanceDemo';
import { HelpTooltip } from '@/components/HelpTooltip';
import Sidebar, { NAV_GROUPS } from '@/components/Sidebar';
import type { AdminViewId, NavBadgeCounts } from '@/components/Sidebar';
import { SegmentedControl, cx } from '@/components/ui/Primitives';
import { ToastProvider } from '@/components/ui/Toast';
import { useAdminRouter } from '@/hooks/useAdminRouter';
import { useMetrics } from '@/hooks/useMetrics';
import { LanguageProvider, useI18n } from '@/i18n';
import type { Lang, TranslationKey } from '@/i18n';
import { getAppRouteMode } from '@/routes';
import { ThemeProvider, useTheme } from '@/theme';
import type { AdminTheme } from '@/theme';
import type { Period } from '@/types/metrics';
import AuditSystemView from '@/views/AuditSystemView';
import BotRulesView from '@/views/BotRulesView';
import CatalogView from '@/views/CatalogView';
import ConversationsView from '@/views/ConversationsView';
import KnowledgeBaseView from '@/views/KnowledgeBaseView';
import OverviewView from '@/views/OverviewView';
import QueuesQualityView from '@/views/QueuesQualityView';
import ReportsView from '@/views/ReportsView';
import SettingsView from '@/views/SettingsView';

const PERIODS: { labelKey: TranslationKey; value: Period }[] = [
    { labelKey: 'period.day', value: 'day' },
    { labelKey: 'period.week', value: 'week' },
    { labelKey: 'period.month', value: 'month' },
    { labelKey: 'period.all', value: 'all_time' },
];

/** Views whose list is filtered by the header search box. */
const SEARCHABLE_VIEWS: AdminViewId[] = [
    'conversations',
    'queuesQuality',
    'knowledge',
    'botRules',
    'auditSystem',
];

export default function App({
    initialLang,
    initialTheme,
    initialView,
}: {
    initialLang?: Lang;
    initialTheme?: AdminTheme;
    initialView?: AdminViewId;
} = {}) {
    const routeMode = getAppRouteMode();

    if (routeMode === 'acceptance-public') {
        return (
            <ThemeProvider initialTheme={initialTheme}>
                <PublicAcceptanceApp />
            </ThemeProvider>
        );
    }

    return (
        <ThemeProvider initialTheme={initialTheme}>
            <LanguageProvider initialLang={initialLang}>
                <ToastProvider>
                    <DashboardApp initialView={initialView} />
                </ToastProvider>
            </LanguageProvider>
        </ThemeProvider>
    );
}

function PublicAcceptanceApp() {
    return (
        <div className="min-h-screen bg-[var(--bg-app)] px-4 py-6 text-[var(--text-primary)] sm:px-6 lg:px-8">
            <header className="mx-auto mb-8 max-w-7xl">
                <h1 className="text-2xl font-bold text-[var(--text-primary)]">
                    <span className="text-[var(--accent-primary)]">TreeJar</span> Acceptance Demo
                </h1>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    Прямая self-test страница для клиентской проверки WhatsApp, Telegram и backend-сценариев.
                </p>
            </header>
            <main className="mx-auto max-w-7xl">
                <AcceptanceDemo />
            </main>
        </div>
    );
}

function DashboardApp({ initialView }: { initialView?: AdminViewId }) {
    const { t, lang, setLang } = useI18n();
    const { theme, toggleTheme } = useTheme();
    const { route, navigate } = useAdminRouter(initialView ?? 'conversations');
    const activeView = route.view;

    const [period, setPeriod] = useState<Period>('all_time');
    const [globalSearchQuery, setGlobalSearchQuery] = useState('');
    const { data, timeseries, loading, error, refetch } = useMetrics(period);

    const [queueCounts, setQueueCounts] = useState<{
        escalations: number;
        pendingReviews: number;
    }>({ escalations: 0, pendingReviews: 0 });
    const [kbCandidatesCount, setKbCandidatesCount] = useState<number>(0);

    useEffect(() => {
        if (data?.escalation_count !== undefined && queueCounts.escalations === 0) {
            setQueueCounts((prev) => ({
                ...prev,
                escalations: data.escalation_count,
            }));
        }
    }, [data?.escalation_count, queueCounts.escalations]);

    const badges: NavBadgeCounts = {
        conversations: data?.escalation_count ?? 0,
        queuesQuality:
            (queueCounts.escalations || (data?.escalation_count ?? 0)) +
            queueCounts.pendingReviews,
        knowledge: kbCandidatesCount,
    };

    const allNavItems = NAV_GROUPS.flatMap((group) => group.items);
    const activeNavItem = allNavItems.find((item) => item.id === activeView);
    const activeLabel =
        activeView === 'acceptance'
            ? t('nav.acceptance')
            : activeNavItem
              ? t(activeNavItem.labelKey)
              : t('nav.conversations');

    const searchable = SEARCHABLE_VIEWS.includes(activeView);

    function handleSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
        if (event.key === 'Enter' && !searchable && globalSearchQuery.trim()) {
            navigate({ view: 'conversations' });
        }
        if (event.key === 'Escape') {
            setGlobalSearchQuery('');
        }
    }

    return (
        <div
            className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)] transition-colors"
            data-admin-shell=""
            data-theme={theme}
        >
            <div className="flex min-h-screen">
                <Sidebar
                    activeView={activeView}
                    onSelectView={(view) => navigate({ view })}
                    badges={badges}
                />

                <main className="flex min-w-0 flex-1 flex-col">
                    {/* Compact Top Header (56px, fits 100vh without double title bar) */}
                    <header
                        className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-header)] px-5"
                        data-admin-header=""
                    >
                        <div className="flex min-w-0 items-center gap-4">
                            <h2 className="truncate text-base font-bold text-[var(--text-primary)]">
                                {activeView === 'botRules'
                                    ? t('botRules.pageTitle')
                                    : activeLabel}
                            </h2>

                            <div className="relative flex items-center gap-1.5">
                                <Search
                                    size={15}
                                    className="pointer-events-none absolute left-3 top-2.5 text-[var(--text-muted)]"
                                />
                                <input
                                    type="search"
                                    value={globalSearchQuery}
                                    onChange={(event) => setGlobalSearchQuery(event.target.value)}
                                    onKeyDown={handleSearchKeyDown}
                                    aria-label={t('header.searchLabel')}
                                    placeholder={
                                        searchable
                                            ? t('header.searchPlaceholder')
                                            : t('header.searchPlaceholderJump')
                                    }
                                    className="admin-input h-8 w-[260px] rounded-lg pl-8 pr-3 text-xs outline-none"
                                />
                                <HelpTooltip text={t('header.searchHelp')} />
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            {activeView === 'overview' && (
                                <SegmentedControl
                                    items={PERIODS.map((item) => ({
                                        label: t(item.labelKey),
                                        value: item.value,
                                    }))}
                                    value={period}
                                    onChange={setPeriod}
                                />
                            )}

                            <div
                                role="group"
                                aria-label={t('header.language')}
                                className="admin-subpanel flex rounded-lg p-0.5"
                                data-lang-toggle=""
                            >
                                {(['ru', 'en'] as const).map((code) => (
                                    <button
                                        key={code}
                                        type="button"
                                        aria-pressed={lang === code}
                                        onClick={() => setLang(code)}
                                        className={cx(
                                            'rounded-md px-2 py-1 text-xs font-semibold transition',
                                            lang === code
                                                ? 'bg-[var(--accent-primary)] text-white shadow-2xs'
                                                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                                        )}
                                    >
                                        {code.toUpperCase()}
                                    </button>
                                ))}
                            </div>

                            <button
                                type="button"
                                onClick={toggleTheme}
                                data-theme-toggle=""
                                aria-label={
                                    theme === 'light'
                                        ? t('theme.switchToDark')
                                        : t('theme.switchToLight')
                                }
                                className="admin-subpanel inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                            >
                                {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
                            </button>

                            <button
                                type="button"
                                onClick={() => void refetch()}
                                className="admin-subpanel inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                                aria-label={t('common.refresh')}
                            >
                                <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                            </button>

                            <div className="ml-1 hidden h-8 items-center gap-2 border-l border-[var(--border-subtle)] pl-3 text-xs font-medium text-[var(--text-secondary)] sm:flex">
                                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                                    <Settings size={14} />
                                </div>
                                <span>{t('header.admin')}</span>
                            </div>
                        </div>
                    </header>

                    {error && activeView === 'overview' && (
                        <div className="border-b border-red-300 bg-red-50 px-5 py-2.5 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200">
                            <AlertTriangle size={14} className="mr-1.5 inline" />
                            {error}
                        </div>
                    )}

                    <div className="min-h-0 flex-1">
                        {activeView === 'overview' && (
                            <div className="p-4">
                                <OverviewView
                                    period={period}
                                    onPeriodChange={setPeriod}
                                    data={data}
                                    timeseries={timeseries}
                                    loading={loading}
                                    error={error}
                                    onNavigate={navigate}
                                    onRefresh={() => void refetch()}
                                />
                            </div>
                        )}

                        {activeView === 'conversations' && (
                            <ConversationsView
                                globalSearch={globalSearchQuery}
                                initialId={route.id}
                                initialLanguage={route.language}
                                initialStatus={route.status}
                                initialStage={route.stage}
                                initialEscalation={route.escalation}
                                onSelectConversationId={(id) => navigate({ id }, true)}
                            />
                        )}

                        {activeView === 'queuesQuality' && (
                            <QueuesQualityView
                                globalSearch={globalSearchQuery}
                                activeTab={route.tab}
                                onTabChange={(tab) => navigate({ tab })}
                                onOpenConversation={(conversationId) =>
                                    navigate({ view: 'conversations', id: conversationId })
                                }
                                onCountsChange={setQueueCounts}
                                refetchMetrics={() => void refetch()}
                            />
                        )}

                        {activeView === 'knowledge' && (
                            <KnowledgeBaseView
                                globalSearch={globalSearchQuery}
                                selectedId={route.id}
                                onSelectId={(id) => navigate({ id: id || undefined }, true)}
                                onCandidatesCountChange={setKbCandidatesCount}
                            />
                        )}

                        {activeView === 'botRules' && (
                            <BotRulesView
                                globalSearch={globalSearchQuery}
                                selectedId={route.id}
                                onSelectId={(id) => navigate({ id: id || undefined }, true)}
                            />
                        )}

                        {activeView === 'catalog' && <CatalogView />}

                        {activeView === 'reports' && <ReportsView />}

                        {activeView === 'settings' && <SettingsView />}

                        {activeView === 'auditSystem' && (
                            <AuditSystemView
                                globalSearch={globalSearchQuery}
                                activeTab={route.tab}
                                onTabChange={(tab) => navigate({ tab })}
                                onNavigateEntity={(view, id) => navigate({ view, id })}
                            />
                        )}

                        {activeView === 'acceptance' && (
                            <div className="p-5">
                                <AcceptanceDemo />
                            </div>
                        )}
                    </div>
                </main>
            </div>
        </div>
    );
}
