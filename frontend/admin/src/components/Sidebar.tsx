import React from 'react';
import {
    BarChart3,
    BookOpen,
    Bot,
    ClipboardCheck,
    FileText,
    HelpCircle,
    History,
    Inbox,
    MessageCircle,
    Package,
    Settings,
} from 'lucide-react';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';

export type AdminViewId =
    | 'overview'
    | 'conversations'
    | 'queuesQuality'
    | 'knowledge'
    | 'botRules'
    | 'catalog'
    | 'reports'
    | 'settings'
    | 'auditSystem'
    | 'guide'
    | 'acceptance';

export interface NavBadgeCounts {
    conversations?: number;
    queuesQuality?: number;
    knowledge?: number;
}

export interface SidebarProps {
    activeView: AdminViewId;
    onSelectView: (view: AdminViewId) => void;
    badges?: NavBadgeCounts;
    botEnabled?: boolean;
}

interface NavItemConfig {
    id: AdminViewId;
    labelKey: TranslationKey;
    icon: React.ComponentType<{ className?: string }>;
    badgeKey?: keyof NavBadgeCounts;
}

interface NavGroupConfig {
    groupKey: TranslationKey;
    items: NavItemConfig[];
}

export const NAV_GROUPS: NavGroupConfig[] = [
    {
        groupKey: 'nav.group.operations',
        items: [
            { id: 'overview', labelKey: 'nav.overview', icon: BarChart3 },
            {
                id: 'conversations',
                labelKey: 'nav.conversations',
                icon: MessageCircle,
                badgeKey: 'conversations',
            },
            {
                id: 'queuesQuality',
                labelKey: 'nav.queuesQuality',
                icon: Inbox,
                badgeKey: 'queuesQuality',
            },
        ],
    },
    {
        groupKey: 'nav.group.knowledge',
        items: [
            {
                id: 'knowledge',
                labelKey: 'nav.knowledge',
                icon: BookOpen,
                badgeKey: 'knowledge',
            },
            { id: 'botRules', labelKey: 'nav.botRules', icon: Bot },
            { id: 'catalog', labelKey: 'nav.catalogInventory', icon: Package },
        ],
    },
    {
        groupKey: 'nav.group.system',
        items: [
            { id: 'reports', labelKey: 'nav.reports', icon: FileText },
            { id: 'settings', labelKey: 'nav.settings', icon: Settings },
            { id: 'auditSystem', labelKey: 'nav.auditSystem', icon: History },
        ],
    },
];

export default function Sidebar({
    activeView,
    onSelectView,
    badges = {},
    botEnabled = true,
}: SidebarProps) {
    const { t } = useI18n();

    return (
        <aside
            data-admin-sidebar
            className="admin-sidebar flex w-60 shrink-0 flex-col border-r transition-colors"
        >
            <div className="flex items-center justify-between gap-2.5 border-b border-slate-200 px-4 py-3.5 dark:border-slate-800">
                <div className="flex items-center gap-2.5">
                    <img
                        src="/dashboard/favicon.svg"
                        alt="Treejar Noor"
                        className="h-8 w-8 shrink-0 rounded-lg shadow-xs"
                    />
                    <div>
                        <div className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100">
                            Noor CRM
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400">
                            Treejar AI Operations
                        </div>
                    </div>
                </div>
            </div>

            <nav
                aria-label="CRM navigation"
                className="flex-1 space-y-4 overflow-y-auto px-2.5 py-3"
            >
                {NAV_GROUPS.map((group) => (
                    <div key={group.groupKey}>
                        <div className="mb-1 px-2.5 text-[10px] font-bold tracking-wider text-slate-400 uppercase dark:text-slate-500">
                            {t(group.groupKey)}
                        </div>
                        <div className="space-y-0.5">
                            {group.items.map((item) => {
                                const Icon = item.icon;
                                const active = activeView === item.id;
                                const badgeCount = item.badgeKey
                                    ? (badges[item.badgeKey] ?? 0)
                                    : 0;
                                return (
                                    <button
                                        key={item.id}
                                        type="button"
                                        data-nav-item={item.id}
                                        onClick={() => onSelectView(item.id)}
                                        className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-medium transition-colors ${
                                            active
                                                ? 'bg-[#2170e4] text-white shadow-xs'
                                                : 'text-slate-700 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-white'
                                        }`}
                                    >
                                        <span className="flex min-w-0 items-center gap-2.5">
                                            <Icon className="h-4 w-4 shrink-0" />
                                            <span className="truncate">{t(item.labelKey)}</span>
                                        </span>
                                        {badgeCount > 0 && (
                                            <span
                                                data-nav-badge={item.id}
                                                className={`shrink-0 rounded-full px-1.5 py-0.5 font-mono text-[10px] font-bold leading-none ${
                                                    active
                                                        ? 'bg-white/25 text-white'
                                                        : 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                                                }`}
                                            >
                                                {badgeCount}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </nav>

            <div className="space-y-1 border-t border-slate-200 p-2.5 dark:border-slate-800">
                <button
                    type="button"
                    data-nav-item="guide"
                    onClick={() => onSelectView('guide')}
                    className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs font-semibold transition-colors ${
                        activeView === 'guide'
                            ? 'bg-[#2170e4] text-white shadow-xs'
                            : 'bg-blue-50/70 text-[#2170e4] hover:bg-blue-100/80 dark:bg-blue-950/40 dark:text-blue-300 dark:hover:bg-blue-950/70'
                    }`}
                >
                    <HelpCircle className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{t('nav.guide')}</span>
                </button>
                <button
                    type="button"
                    data-nav-item="acceptance"
                    onClick={() => onSelectView('acceptance')}
                    className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
                        activeView === 'acceptance'
                            ? 'bg-[#2170e4] text-white'
                            : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                    }`}
                >
                    <ClipboardCheck className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{t('nav.acceptance')}</span>
                </button>
                <div className="admin-subpanel flex items-center justify-between rounded-lg px-2.5 py-1.5 text-[11px]">
                    <span className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-200">
                        <span
                            className={`h-2 w-2 rounded-full ${
                                botEnabled ? 'bg-emerald-500' : 'bg-amber-500'
                            }`}
                        />
                        Noor AI
                    </span>
                    <span className="text-[10px] text-slate-500 dark:text-slate-400">
                        {t('app.monitoringMode')}
                    </span>
                </div>
            </div>
        </aside>
    );
}
