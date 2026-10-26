import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import {
    AlertTriangle,
    ArrowRight,
    ChevronDown,
    Database,
    History,
    LogOut,
    Moon,
    RefreshCw,
    Search,
    Settings,
    Sparkles,
    Sun,
    X,
} from 'lucide-react';
import { fetchAdminSession } from '@/api/operators';
import AcceptanceDemo from '@/components/AcceptanceDemo';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useOnboardingTour } from '@/components/OnboardingTour';
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
import type { AdminSessionInfo } from '@/types/operators';
import AuditSystemView from '@/views/AuditSystemView';
import BotRulesView from '@/views/BotRulesView';
import CatalogView from '@/views/CatalogView';
import ConversationsView from '@/views/ConversationsView';
import GuideView from '@/views/GuideView';
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
    'guide',
];

/** Views that render their own dedicated search input inside the left column (AC05). */
const VIEWS_WITH_LOCAL_SEARCH: AdminViewId[] = [
    'conversations',
    'knowledge',
    'botRules',
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
    const { startTour } = useOnboardingTour({ navigate });
    const activeView = route.view;

    const [period, setPeriod] = useState<Period>('week');
    const [globalSearchQuery, setGlobalSearchQuery] = useState('');
    const [refreshSignal, setRefreshSignal] = useState(0);
    const [sessionInfo, setSessionInfo] = useState<AdminSessionInfo | null>(null);
    const [accountMenuOpen, setAccountMenuOpen] = useState(false);
    const accountMenuRef = useRef<HTMLDivElement | null>(null);
    const { data, timeseries, loading, error, refetch } = useMetrics(period);

    const [queueCounts, setQueueCounts] = useState<{
        escalations: number;
        pendingReviews: number;
    }>({ escalations: 0, pendingReviews: 0 });
    const [kbCandidatesCount, setKbCandidatesCount] = useState<number>(0);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        fetchAdminSession()
            .then((info) => setSessionInfo(info))
            .catch(() => {
                // Keep fallback session label when offline or unmounted.
            });
    }, []);

    useEffect(() => {
        if (!accountMenuOpen || typeof document === 'undefined') return;
        const handleOutsideClick = (event: MouseEvent) => {
            if (
                accountMenuRef.current &&
                event.target instanceof Node &&
                !accountMenuRef.current.contains(event.target)
            ) {
                setAccountMenuOpen(false);
            }
        };
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setAccountMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleOutsideClick);
        document.addEventListener('keydown', handleEscape);
        return () => {
            document.removeEventListener('mousedown', handleOutsideClick);
            document.removeEventListener('keydown', handleEscape);
        };
    }, [accountMenuOpen]);

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
            : activeView === 'guide'
              ? t('nav.guide')
              : activeNavItem
                ? t(activeNavItem.labelKey)
                : t('nav.conversations');

    const searchable = SEARCHABLE_VIEWS.includes(activeView);
    const showHeaderSearch =
        !VIEWS_WITH_LOCAL_SEARCH.includes(activeView) && activeView !== 'acceptance';
    const showHeaderRefresh = activeView !== 'guide' && activeView !== 'acceptance';
    const sessionDisplayName = sessionInfo?.display_name || t('header.admin');
    const authMethodLabel =
        sessionInfo?.auth_method === 'telegram'
            ? t('header.authMethod.telegram')
            : sessionInfo?.auth_method === 'password'
              ? t('header.authMethod.password')
              : t('header.authMethod.session');

    function handleGlobalRefresh() {
        void refetch();
        setRefreshSignal((prev) => prev + 1);
    }

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

                            {showHeaderSearch && (
                                <div className="relative flex items-center gap-1.5">
                                    <div className="relative flex items-center">
                                        <Search
                                            size={15}
                                            className="pointer-events-none absolute left-3 top-2 text-[var(--text-muted)]"
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
                                            className="admin-input h-8 w-[260px] rounded-lg pl-8 pr-7 text-xs outline-none"
                                        />
                                        {globalSearchQuery && (
                                            <button
                                                type="button"
                                                onClick={() => setGlobalSearchQuery('')}
                                                aria-label={t('header.searchClear')}
                                                data-header-search-clear=""
                                                className="absolute right-2 inline-flex h-5 w-5 items-center justify-center rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                                            >
                                                <X size={13} />
                                            </button>
                                        )}
                                    </div>
                                    {!searchable && globalSearchQuery.trim() && (
                                        <button
                                            type="button"
                                            onClick={() => navigate({ view: 'conversations' })}
                                            aria-label={t('header.searchJumpBtn')}
                                            data-header-search-submit=""
                                            className="inline-flex h-8 items-center gap-1 rounded-lg bg-[var(--accent-primary)] px-2.5 text-xs font-semibold text-white transition hover:opacity-90"
                                        >
                                            <span>{t('header.searchJumpBtn')}</span>
                                            <ArrowRight size={13} />
                                        </button>
                                    )}
                                    <HelpTooltip text={t('header.searchHelp')} />
                                </div>
                            )}
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

                            <button
                                type="button"
                                onClick={() => startTour('full')}
                                data-tour-trigger=""
                                aria-label={t('header.startTour')}
                                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--accent-primary)]/25 bg-[var(--accent-soft)] px-2.5 text-xs font-semibold text-[var(--accent-primary)] transition hover:opacity-90"
                            >
                                <Sparkles size={14} />
                                <span className="hidden lg:inline">{t('header.startTour')}</span>
                                <span className="lg:hidden">{t('header.startTourShort')}</span>
                            </button>

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

                            {showHeaderRefresh && (
                                <button
                                    type="button"
                                    onClick={handleGlobalRefresh}
                                    data-header-refresh-btn=""
                                    className="admin-subpanel inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                                    aria-label={t('common.refresh')}
                                >
                                    <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                                </button>
                            )}

                            <div
                                ref={accountMenuRef}
                                className="relative ml-1 border-l border-[var(--border-subtle)] pl-2.5"
                            >
                                <button
                                    type="button"
                                    onClick={() => setAccountMenuOpen((open) => !open)}
                                    aria-haspopup="menu"
                                    aria-expanded={accountMenuOpen}
                                    aria-label={t('header.accountMenuLabel')}
                                    data-admin-account-btn=""
                                    className="admin-subpanel inline-flex h-8 items-center gap-2 rounded-lg px-2 text-xs font-medium text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
                                >
                                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                                        <Settings size={13} />
                                    </span>
                                    <span className="hidden max-w-[140px] truncate sm:inline">
                                        {sessionDisplayName}
                                    </span>
                                    <ChevronDown size={13} className="text-[var(--text-muted)]" />
                                </button>

                                {accountMenuOpen && (
                                    <div
                                        role="menu"
                                        data-admin-account-menu=""
                                        className="admin-panel absolute right-0 top-10 z-50 w-72 rounded-xl p-2 shadow-xl"
                                    >
                                        <div className="border-b border-[var(--border-subtle)] px-2.5 py-2">
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="truncate text-xs font-bold text-[var(--text-primary)]">
                                                    {sessionDisplayName}
                                                </span>
                                                <span className="shrink-0 rounded-full bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--accent-primary)]">
                                                    {authMethodLabel}
                                                </span>
                                            </div>
                                            {sessionInfo?.username && (
                                                <p className="mt-0.5 font-mono text-[11px] text-[var(--text-muted)]">
                                                    @{sessionInfo.username}
                                                </p>
                                            )}
                                            <p className="mt-1 text-[11px] leading-snug text-[var(--text-secondary)]">
                                                {t('header.sessionSharedNote')}
                                            </p>
                                        </div>

                                        <div className="mt-1 space-y-0.5">
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => {
                                                    setAccountMenuOpen(false);
                                                    navigate({ view: 'settings' });
                                                }}
                                                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                                            >
                                                <Settings size={14} />
                                                <span>{t('header.menuSettings')}</span>
                                            </button>
                                            <button
                                                type="button"
                                                role="menuitem"
                                                onClick={() => {
                                                    setAccountMenuOpen(false);
                                                    navigate({ view: 'auditSystem', tab: 'audit' });
                                                }}
                                                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                                            >
                                                <History size={14} />
                                                <span>{t('header.menuAudit')}</span>
                                            </button>
                                            <a
                                                role="menuitem"
                                                href={sessionInfo?.sqladmin_url || '/admin/'}
                                                onClick={() => setAccountMenuOpen(false)}
                                                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[var(--text-secondary)] transition hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                                            >
                                                <Database size={14} />
                                                <span>{t('header.menuSqlAdmin')}</span>
                                            </a>
                                        </div>

                                        <div className="mt-1 border-t border-[var(--border-subtle)] pt-1">
                                            <a
                                                role="menuitem"
                                                href={sessionInfo?.logout_url || '/admin/logout'}
                                                data-admin-logout-link=""
                                                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-semibold text-rose-600 transition hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/50"
                                            >
                                                <LogOut size={14} />
                                                <span>{t('header.menuLogout')}</span>
                                            </a>
                                        </div>
                                    </div>
                                )}
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
                                    onRefresh={handleGlobalRefresh}
                                    refreshSignal={refreshSignal}
                                />
                            </div>
                        )}

                        {activeView === 'conversations' && (
                            <ConversationsView
                                globalSearch={globalSearchQuery}
                                initialId={route.id}
                                initialFilter={route.filter}
                                initialLanguage={route.language}
                                initialStatus={route.status}
                                initialStage={route.stage}
                                initialEscalation={route.escalation}
                                refreshSignal={refreshSignal}
                                onSelectConversationId={(id) => navigate({ id }, true)}
                                onClearRouteFilter={() => navigate({ filter: undefined }, true)}
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
                                refreshSignal={refreshSignal}
                            />
                        )}

                        {activeView === 'knowledge' && (
                            <KnowledgeBaseView
                                globalSearch={globalSearchQuery}
                                selectedId={route.id}
                                onSelectId={(id) => navigate({ id: id || undefined }, true)}
                                onCandidatesCountChange={setKbCandidatesCount}
                                refreshSignal={refreshSignal}
                            />
                        )}

                        {activeView === 'botRules' && (
                            <BotRulesView
                                globalSearch={globalSearchQuery}
                                selectedId={route.id}
                                onSelectId={(id) => navigate({ id: id || undefined }, true)}
                                refreshSignal={refreshSignal}
                            />
                        )}

                        {activeView === 'catalog' && <CatalogView refreshSignal={refreshSignal} />}

                        {activeView === 'reports' && <ReportsView refreshSignal={refreshSignal} />}

                        {activeView === 'settings' && <SettingsView refreshSignal={refreshSignal} />}

                        {activeView === 'auditSystem' && (
                            <AuditSystemView
                                globalSearch={globalSearchQuery}
                                activeTab={route.tab}
                                onTabChange={(tab) => navigate({ tab })}
                                onNavigateEntity={(view, id) => navigate({ view, id })}
                                refreshSignal={refreshSignal}
                            />
                        )}

                        {activeView === 'guide' && (
                            <GuideView
                                globalSearch={globalSearchQuery}
                                activeTab={route.tab}
                                onTabChange={(tab) => navigate({ tab })}
                                onNavigate={navigate}
                                onStartTour={startTour}
                                onClearSearch={() => setGlobalSearchQuery('')}
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
