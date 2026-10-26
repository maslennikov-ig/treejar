import { useMemo } from 'react';
import {
    ArrowRight,
    ArrowUpRight,
    BookOpen,
    Boxes,
    CheckCircle2,
    ClipboardList,
    Clock,
    Database,
    ExternalLink,
    HelpCircle,
    ShieldCheck,
    Sparkles,
    Zap,
} from 'lucide-react';
import type { AdminViewId } from '@/components/Sidebar';
import {
    Badge,
    EmptyBox,
    Panel,
    ViewBanner,
    cx,
    matchesQuery,
} from '@/components/ui/Primitives';
import {
    GUIDE_FAQ,
    GUIDE_GLOSSARY,
    GUIDE_PIPELINE_STEPS,
    GUIDE_PLAYBOOKS,
    GUIDE_SECTIONS,
    MINI_TOUR_CARDS,
    TOUR_TRACKS,
    pickText,
} from '@/data/adminGuideData';
import type { TourTrackId } from '@/data/adminGuideData';
import type { AdminRouteState } from '@/hooks/useAdminRouter';
import { useI18n } from '@/i18n';

export type GuideTabId = 'playbooks' | 'sections' | 'glossary' | 'faq';

const VALID_GUIDE_TABS: ReadonlySet<GuideTabId> = new Set([
    'playbooks',
    'sections',
    'glossary',
    'faq',
]);

function normalizeGuideTab(rawTab?: string): GuideTabId {
    if (rawTab && VALID_GUIDE_TABS.has(rawTab as GuideTabId)) {
        return rawTab as GuideTabId;
    }
    return 'playbooks';
}

export interface GuideViewProps {
    globalSearch?: string;
    activeTab?: string;
    onTabChange: (tab: GuideTabId) => void;
    onNavigate: (next: Partial<AdminRouteState> & { view: AdminViewId }) => void;
    onStartTour: (track: TourTrackId) => void;
    onClearSearch?: () => void;
}

export default function GuideView({
    globalSearch = '',
    activeTab,
    onTabChange,
    onNavigate,
    onStartTour,
    onClearSearch,
}: GuideViewProps) {
    const { lang, t } = useI18n();
    const currentTab = normalizeGuideTab(activeTab);
    const query = globalSearch.trim();

    const filteredPlaybooks = useMemo(
        () =>
            GUIDE_PLAYBOOKS.filter((item) =>
                matchesQuery(
                    query,
                    pickText(item.title, lang),
                    pickText(item.role, lang),
                    pickText(item.goal, lang),
                    pickText(item.tip, lang),
                    ...item.steps.map((step) => pickText(step, lang)),
                ),
            ),
        [lang, query],
    );

    const filteredSections = useMemo(
        () =>
            GUIDE_SECTIONS.filter((item) =>
                matchesQuery(
                    query,
                    pickText(item.group, lang),
                    pickText(item.title, lang),
                    pickText(item.purpose, lang),
                    pickText(item.keyActions, lang),
                    pickText(item.botImpact, lang),
                ),
            ),
        [lang, query],
    );

    const filteredGlossary = useMemo(
        () =>
            GUIDE_GLOSSARY.map((group) => {
                if (!query) return group;
                const groupHeaderMatches = matchesQuery(
                    query,
                    pickText(group.title, lang),
                    pickText(group.subtitle, lang),
                );
                if (groupHeaderMatches) return group;
                const matchingItems = group.items.filter((entry) =>
                    matchesQuery(
                        query,
                        pickText(entry.badge, lang),
                        pickText(entry.meaning, lang),
                    ),
                );
                return { ...group, items: matchingItems };
            }).filter((group) => group.items.length > 0),
        [lang, query],
    );

    const filteredFaq = useMemo(
        () =>
            GUIDE_FAQ.filter((item) =>
                matchesQuery(
                    query,
                    pickText(item.question, lang),
                    pickText(item.answer, lang),
                ),
            ),
        [lang, query],
    );

    const groupedSections = useMemo(() => {
        const groups: Array<{ groupTitle: string; cards: typeof filteredSections }> = [];
        for (const card of filteredSections) {
            const label = pickText(card.group, lang);
            const existing = groups.find((entry) => entry.groupTitle === label);
            if (existing) {
                existing.cards.push(card);
            } else {
                groups.push({ groupTitle: label, cards: [card] });
            }
        }
        return groups;
    }, [filteredSections, lang]);

    const glossaryMatchCount = useMemo(
        () => filteredGlossary.reduce((acc, group) => acc + group.items.length, 0),
        [filteredGlossary],
    );

    const tabs: Array<{
        id: GuideTabId;
        label: string;
        count: number;
    }> = [
        {
            id: 'playbooks',
            label: t('guide.tab.playbooks'),
            count: filteredPlaybooks.length,
        },
        {
            id: 'sections',
            label: t('guide.tab.sections'),
            count: filteredSections.length,
        },
        {
            id: 'glossary',
            label: t('guide.tab.glossary'),
            count: glossaryMatchCount,
        },
        {
            id: 'faq',
            label: t('guide.tab.faq'),
            count: filteredFaq.length,
        },
    ];

    return (
        <div data-guide-view="">
            <ViewBanner view="guide" />

            <div className="space-y-5 p-5">
                {/* Interactive Tour Launchpad */}
                <section
                    className="admin-panel relative overflow-hidden rounded-2xl p-5 shadow-xs sm:p-6"
                    data-guide-launchpad=""
                >
                    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                        <div className="max-w-2xl space-y-2.5">
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--accent-soft)] px-3 py-1 text-[11px] font-semibold text-[var(--accent-primary)]">
                                <Sparkles size={13} />
                                <span>{t('guide.hero.badge')}</span>
                            </span>
                            <h3 className="text-lg font-bold tracking-tight text-slate-900 sm:text-xl dark:text-slate-100">
                                {t('guide.hero.title')}
                            </h3>
                            <p className="text-xs leading-5 text-slate-600 sm:text-sm dark:text-slate-300">
                                {t('guide.hero.subtitle')}
                            </p>
                        </div>

                        <div className="flex shrink-0 flex-wrap items-center gap-2.5">
                            <button
                                type="button"
                                onClick={() => onStartTour('full')}
                                data-start-tour="full"
                                className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:opacity-95"
                            >
                                <Sparkles size={15} />
                                <span>
                                    {t('guide.hero.startFullTour', {
                                        count: TOUR_TRACKS.full.length,
                                    })}
                                </span>
                            </button>

                            <a
                                href="/admin/"
                                className="admin-subpanel inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                            >
                                <Database size={14} className="text-[var(--accent-primary)]" />
                                <span>{t('guide.hero.openSqlAdmin')}</span>
                                <ExternalLink size={13} className="text-slate-400" />
                            </a>
                        </div>
                    </div>

                    {/* Focused 4-step Role Mini-Tours */}
                    <div className="mt-5 border-t border-[var(--border-subtle)] pt-4">
                        <p className="mb-3 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                            {t('guide.hero.miniToursTitle')}
                        </p>
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                            {MINI_TOUR_CARDS.map((card) => (
                                <button
                                    key={card.id}
                                    type="button"
                                    onClick={() => onStartTour(card.id)}
                                    data-start-tour={card.id}
                                    className="admin-subpanel group flex flex-col justify-between rounded-xl p-4 text-left transition hover:border-[var(--accent-primary)] hover:bg-[var(--bg-surface)]"
                                >
                                    <div>
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                            <Badge tone="emerald">
                                                {pickText(card.role, lang)}
                                            </Badge>
                                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
                                                <Clock size={12} />
                                                <span>{pickText(card.duration, lang)}</span>
                                            </span>
                                        </div>
                                        <p className="mt-2.5 text-xs font-bold text-slate-900 group-hover:text-[var(--accent-primary)] sm:text-sm dark:text-slate-100">
                                            {pickText(card.title, lang)}
                                        </p>
                                        <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-slate-400">
                                            {pickText(card.summary, lang)}
                                        </p>
                                    </div>
                                    <div className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[var(--accent-primary)]">
                                        <span>{t('guide.runMiniTour')}</span>
                                        <ArrowRight
                                            size={13}
                                            className="transition-transform group-hover:translate-x-0.5"
                                        />
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Live Architecture & Two-Level Admin Overview */}
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
                    <Panel
                        title={t('guide.pipeline.title')}
                        subtitle={t('guide.pipeline.subtitle')}
                        icon={Zap}
                        className="xl:col-span-7"
                    >
                        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
                            {GUIDE_PIPELINE_STEPS.map((item) => (
                                <div
                                    key={item.step}
                                    className="admin-subpanel flex flex-col rounded-xl p-3"
                                >
                                    <span className="inline-flex w-fit rounded-md bg-[var(--accent-soft)] px-2 py-0.5 font-mono text-[11px] font-bold text-[var(--accent-primary)]">
                                        {item.step}
                                    </span>
                                    <p className="mt-2 text-xs font-bold text-slate-900 dark:text-slate-100">
                                        {pickText(item.title, lang)}
                                    </p>
                                    <p className="mt-1 text-[11px] leading-4.5 text-slate-600 dark:text-slate-400">
                                        {pickText(item.detail, lang)}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </Panel>

                    <Panel
                        title={t('guide.twoLevels.title')}
                        icon={Boxes}
                        className="xl:col-span-5"
                    >
                        <div className="space-y-2.5">
                            <div className="rounded-xl border border-emerald-300/80 bg-emerald-50/60 p-3 dark:border-emerald-800/70 dark:bg-emerald-950/30">
                                <p className="flex items-center gap-1.5 text-xs font-bold text-slate-900 dark:text-slate-100">
                                    <ShieldCheck
                                        size={14}
                                        className="shrink-0 text-emerald-600 dark:text-emerald-400"
                                    />
                                    <span>{t('guide.twoLevels.dashboardLabel')}</span>
                                </p>
                                <p className="mt-1 text-[11px] leading-4.5 text-slate-600 dark:text-slate-300">
                                    {t('guide.twoLevels.dashboardDesc')}
                                </p>
                            </div>

                            <div className="admin-subpanel rounded-xl p-3">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="flex items-center gap-1.5 text-xs font-bold text-slate-900 dark:text-slate-100">
                                        <Database
                                            size={14}
                                            className="shrink-0 text-[var(--accent-primary)]"
                                        />
                                        <span>{t('guide.twoLevels.sqladminLabel')}</span>
                                    </p>
                                    <a
                                        href="/admin/"
                                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--accent-primary)] hover:underline"
                                    >
                                        <span>/admin/</span>
                                        <ArrowUpRight size={12} />
                                    </a>
                                </div>
                                <p className="mt-1 text-[11px] leading-4.5 text-slate-600 dark:text-slate-400">
                                    {t('guide.twoLevels.sqladminDesc')}
                                </p>
                            </div>
                        </div>
                    </Panel>
                </div>

                {/* Guide Navigation Tabs + Active Search Notice */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div
                        className="admin-subpanel flex flex-wrap gap-1 rounded-xl p-1"
                        role="tablist"
                        data-guide-tabs=""
                    >
                        {tabs.map((tab) => {
                            const active = currentTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    type="button"
                                    role="tab"
                                    aria-selected={active}
                                    data-guide-tab={tab.id}
                                    onClick={() => onTabChange(tab.id)}
                                    className={cx(
                                        'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition',
                                        active
                                            ? 'bg-[var(--accent-primary)] text-white shadow-2xs'
                                            : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
                                    )}
                                >
                                    <span>{tab.label}</span>
                                    <span
                                        className={cx(
                                            'rounded-full px-1.5 py-0.2 text-[10px] font-bold',
                                            active
                                                ? 'bg-white/20 text-white'
                                                : 'bg-slate-200/80 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
                                        )}
                                    >
                                        {tab.count}
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    {query && (
                        <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                            <span>{t('guide.searchActive', { query })}</span>
                            {onClearSearch && (
                                <button
                                    type="button"
                                    onClick={onClearSearch}
                                    className="font-semibold text-[var(--accent-primary)] hover:underline"
                                >
                                    {t('guide.clearSearch')}
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* Tab 1: Step-by-Step Playbooks */}
                {currentTab === 'playbooks' && (
                    <div className="space-y-3" data-guide-panel="playbooks">
                        {filteredPlaybooks.length === 0 ? (
                            <EmptyBox text={t('guide.noMatches')} />
                        ) : (
                            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                {filteredPlaybooks.map((playbook) => (
                                    <article
                                        key={playbook.id}
                                        className="admin-panel flex flex-col justify-between rounded-xl p-5 shadow-xs"
                                    >
                                        <div>
                                            <div className="flex flex-wrap items-center justify-between gap-2">
                                                <div className="flex flex-wrap items-center gap-1.5">
                                                    <Badge tone="blue">
                                                        {pickText(playbook.role, lang)}
                                                    </Badge>
                                                    <Badge tone="slate">
                                                        {t('guide.stepsCount', {
                                                            count: playbook.steps.length,
                                                        })}
                                                    </Badge>
                                                </div>
                                                <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
                                                    <Clock size={13} />
                                                    <span>
                                                        {pickText(playbook.duration, lang)}
                                                    </span>
                                                </span>
                                            </div>

                                            <h4 className="mt-3 text-sm font-bold text-slate-900 dark:text-slate-100">
                                                {pickText(playbook.title, lang)}
                                            </h4>
                                            <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                                                {pickText(playbook.goal, lang)}
                                            </p>

                                            <ol className="mt-3.5 space-y-2">
                                                {playbook.steps.map((step, index) => (
                                                    <li
                                                        key={index}
                                                        className="flex items-start gap-2.5 text-xs leading-5 text-slate-700 dark:text-slate-200"
                                                    >
                                                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[11px] font-bold text-[var(--accent-primary)]">
                                                            {index + 1}
                                                        </span>
                                                        <span>{pickText(step, lang)}</span>
                                                    </li>
                                                ))}
                                            </ol>
                                        </div>

                                        <div className="mt-4 space-y-3 pt-2">
                                            <div className="admin-subpanel flex items-start gap-2 rounded-lg px-3 py-2.5 text-[11px] leading-4.5 text-slate-600 dark:text-slate-300">
                                                <CheckCircle2
                                                    size={14}
                                                    className="mt-0.5 shrink-0 text-[var(--accent-primary)]"
                                                />
                                                <span>{pickText(playbook.tip, lang)}</span>
                                            </div>

                                            <div className="flex flex-wrap items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => onNavigate(playbook.route)}
                                                    className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-95"
                                                >
                                                    <span>{t('guide.openSection')}</span>
                                                    <ArrowRight size={13} />
                                                </button>

                                                {playbook.tourTrack && (
                                                    <button
                                                        type="button"
                                                        onClick={() =>
                                                            onStartTour(playbook.tourTrack!)
                                                        }
                                                        className="admin-subpanel inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                                                    >
                                                        <Sparkles
                                                            size={13}
                                                            className="text-[var(--accent-primary)]"
                                                        />
                                                        <span>{t('guide.runMiniTour')}</span>
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Tab 2: All Sections Directory */}
                {currentTab === 'sections' && (
                    <div className="space-y-5" data-guide-panel="sections">
                        {groupedSections.length === 0 ? (
                            <EmptyBox text={t('guide.noMatches')} />
                        ) : (
                            groupedSections.map((sectionGroup) => (
                                <div key={sectionGroup.groupTitle} className="space-y-2.5">
                                    <h4 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                        <ClipboardList
                                            size={14}
                                            className="text-[var(--accent-primary)]"
                                        />
                                        <span>{sectionGroup.groupTitle}</span>
                                    </h4>
                                    <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3">
                                        {sectionGroup.cards.map((card) => (
                                            <article
                                                key={card.id}
                                                className="admin-panel flex flex-col justify-between rounded-xl p-4 shadow-xs"
                                            >
                                                <div className="space-y-2">
                                                    <div className="flex items-start justify-between gap-2">
                                                        <h5 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                                                            {pickText(card.title, lang)}
                                                        </h5>
                                                        {card.route ? (
                                                            <button
                                                                type="button"
                                                                onClick={() =>
                                                                    onNavigate(card.route!)
                                                                }
                                                                className="inline-flex shrink-0 items-center gap-1 rounded-md bg-[var(--accent-soft)] px-2 py-1 text-[11px] font-semibold text-[var(--accent-primary)] hover:opacity-90"
                                                            >
                                                                <span>
                                                                    {t('guide.openSection')}
                                                                </span>
                                                                <ArrowRight size={12} />
                                                            </button>
                                                        ) : card.externalHref ? (
                                                            <a
                                                                href={card.externalHref}
                                                                className="admin-subpanel inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                                                            >
                                                                <span>{card.externalHref}</span>
                                                                <ExternalLink size={12} />
                                                            </a>
                                                        ) : null}
                                                    </div>

                                                    <p className="text-xs leading-5 text-slate-600 dark:text-slate-300">
                                                        {pickText(card.purpose, lang)}
                                                    </p>

                                                    <div className="admin-subpanel rounded-lg p-2.5 text-[11px] leading-4.5 text-slate-700 dark:text-slate-200">
                                                        {pickText(card.keyActions, lang)}
                                                    </div>
                                                </div>

                                                <p className="mt-3 border-t border-[var(--border-subtle)] pt-2.5 text-[11px] leading-4.5 text-slate-500 dark:text-slate-400">
                                                    <strong className="font-semibold text-slate-700 dark:text-slate-200">
                                                        {t('guide.impactLabel')}{' '}
                                                    </strong>
                                                    {pickText(card.botImpact, lang)}
                                                </p>
                                            </article>
                                        ))}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}

                {/* Tab 3: Statuses, Funnel Stages & Rule Types Glossary */}
                {currentTab === 'glossary' && (
                    <div data-guide-panel="glossary">
                        {filteredGlossary.length === 0 ? (
                            <EmptyBox text={t('guide.noMatches')} />
                        ) : (
                            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                                {filteredGlossary.map((group) => (
                                    <Panel
                                        key={group.id}
                                        title={pickText(group.title, lang)}
                                        subtitle={pickText(group.subtitle, lang)}
                                        icon={BookOpen}
                                    >
                                        <div className="space-y-2.5">
                                            {group.items.map((entry, idx) => (
                                                <div
                                                    key={idx}
                                                    className="admin-subpanel rounded-xl p-3"
                                                >
                                                    <Badge tone={entry.tone}>
                                                        {pickText(entry.badge, lang)}
                                                    </Badge>
                                                    <p className="mt-1.5 text-xs leading-5 text-slate-700 dark:text-slate-200">
                                                        {pickText(entry.meaning, lang)}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    </Panel>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Tab 4: FAQ & Operational Safety */}
                {currentTab === 'faq' && (
                    <div data-guide-panel="faq">
                        {filteredFaq.length === 0 ? (
                            <EmptyBox text={t('guide.noMatches')} />
                        ) : (
                            <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-2">
                                {filteredFaq.map((item) => (
                                    <article
                                        key={item.id}
                                        className="admin-panel rounded-xl p-5 shadow-xs"
                                    >
                                        <h4 className="flex items-start gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
                                            <HelpCircle
                                                size={16}
                                                className="mt-0.5 shrink-0 text-[var(--accent-primary)]"
                                            />
                                            <span>{pickText(item.question, lang)}</span>
                                        </h4>
                                        <p className="mt-2.5 text-xs leading-5 text-slate-600 dark:text-slate-300">
                                            {pickText(item.answer, lang)}
                                        </p>
                                    </article>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
