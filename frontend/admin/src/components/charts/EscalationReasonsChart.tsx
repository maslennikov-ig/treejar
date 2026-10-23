import { useState } from 'react';
import { CHART_CARD_CLASS, CHART_EMPTY_CLASS, CHART_META_CLASS, CHART_TITLE_CLASS } from './chartTheme';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';

export const ESCALATION_CATEGORIES = [
    'quotation_bulk',
    'human_request',
    'delivery_terms',
    'custom_out_of_catalog',
    'urgent_complaint',
    'other',
] as const;

export type EscalationCategory = (typeof ESCALATION_CATEGORIES)[number];

const CATEGORY_KEYS: Record<EscalationCategory, TranslationKey> = {
    quotation_bulk: 'esc.cat.quotation_bulk',
    human_request: 'esc.cat.human_request',
    delivery_terms: 'esc.cat.delivery_terms',
    custom_out_of_catalog: 'esc.cat.custom_out_of_catalog',
    urgent_complaint: 'esc.cat.urgent_complaint',
    other: 'esc.cat.other',
};

const CATEGORY_COLORS: Record<EscalationCategory, string> = {
    quotation_bulk: '#0058be',
    human_request: '#8b5cf6',
    delivery_terms: '#10b981',
    custom_out_of_catalog: '#f59e0b',
    urgent_complaint: '#ef4444',
    other: '#64748b',
};

const CATEGORY_PATTERNS: [Exclude<EscalationCategory, 'other'>, RegExp][] = [
    ['urgent_complaint', /urgent|complain|angry|refund|asap|unhappy|срочн|жалоб|претенз/i],
    ['quotation_bulk', /quot|bulk|wholesale|invoice|proforma|discount|price|large order|кп|оптов|скидк|счет|счёт/i],
    ['custom_out_of_catalog', /\bcustom(?!er)|bespoke|out[ -]of[ -]catalog|not in (the )?catalog|special order|non[- ]catalog|индивидуал|нет в каталоге/i],
    ['delivery_terms', /deliver|shipping|installation|lead time|logistic|доставк|монтаж|сроки/i],
    ['human_request', /human|manager|operator|person|agent|call me|real person|менеджер|оператор|человек/i],
];

export function categorizeEscalationReason(reason: string): EscalationCategory {
    for (const [category, pattern] of CATEGORY_PATTERNS) {
        if (pattern.test(reason)) return category;
    }
    return 'other';
}

export function groupEscalationReasons(rawReasons: Record<string, number>): Record<EscalationCategory, number> {
    const grouped = Object.fromEntries(ESCALATION_CATEGORIES.map((key) => [key, 0])) as Record<EscalationCategory, number>;
    for (const [reason, count] of Object.entries(rawReasons)) {
        grouped[categorizeEscalationReason(reason)] += count;
    }
    return grouped;
}

export default function EscalationReasonsChart({
    byReason,
    rawReasons,
    onSelectReason,
}: {
    byReason?: Record<string, number>;
    rawReasons: Record<string, number>;
    onSelectReason?: (category: EscalationCategory) => void;
}) {
    const { t, formatNumber } = useI18n();
    const [showRaw, setShowRaw] = useState(false);

    const serverReasons = byReason && Object.keys(byReason).length > 0 ? byReason : undefined;
    const grouped: Record<EscalationCategory, number> = serverReasons
        ? (Object.fromEntries(
            ESCALATION_CATEGORIES.map((key) => [key, Number(serverReasons[key] ?? 0)]),
        ) as Record<EscalationCategory, number>)
        : groupEscalationReasons(rawReasons);
    if (serverReasons) {
        for (const [key, value] of Object.entries(serverReasons)) {
            if (!(ESCALATION_CATEGORIES as readonly string[]).includes(key)) grouped.other += Number(value);
        }
    }
    const total = ESCALATION_CATEGORIES.reduce((sum, key) => sum + grouped[key], 0);
    const rawList = Object.entries(rawReasons).sort((left, right) => right[1] - left[1]);
    const maxValue = Math.max(1, ...ESCALATION_CATEGORIES.map((key) => grouped[key]));

    return (
        <div className={`${CHART_CARD_CLASS} flex h-full flex-col justify-between p-4`} data-chart="escalation-reasons">
            <div className="mb-3">
                <div className="flex items-center gap-2">
                    <h3 className={CHART_TITLE_CLASS}>{t('esc.title')}</h3>
                    <HelpTooltip text={t('esc.help')} />
                </div>
                <p className={CHART_META_CLASS}>
                    {t('esc.meta', { total: formatNumber(total) })}
                    {!serverReasons && total > 0 ? ` · ${t('esc.fallbackNote')}` : ''}
                </p>
            </div>
            {total === 0 ? (
                <div className={`${CHART_EMPTY_CLASS} h-[140px]`}>{t('esc.empty')}</div>
            ) : (
                <ul className="space-y-2.5">
                    {ESCALATION_CATEGORIES.map((key) => {
                        const value = grouped[key];
                        const percent = total > 0 ? (value / total) * 100 : 0;
                        return (
                            <li
                                key={key}
                                onClick={() => onSelectReason?.(key)}
                                className={`text-sm ${onSelectReason ? 'cursor-pointer rounded-md px-1 py-0.5 hover:bg-slate-100/70 dark:hover:bg-slate-800/60' : ''}`}
                            >
                                <div className="flex items-center justify-between gap-3">
                                    <span className="flex min-w-0 items-center gap-2 text-[var(--admin-chart-title)]">
                                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[key] }} />
                                        <span className="truncate">{t(CATEGORY_KEYS[key])}</span>
                                    </span>
                                    <span className="shrink-0 tabular-nums text-xs text-[var(--admin-chart-muted)]">
                                        {formatNumber(value)} · {formatNumber(percent, 1)}%
                                    </span>
                                </div>
                                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-[var(--admin-chart-grid)]">
                                    <div
                                        className="h-full rounded-full"
                                        style={{ width: `${(value / maxValue) * 100}%`, backgroundColor: CATEGORY_COLORS[key] }}
                                    />
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
            {rawList.length > 0 && (
                <div className="mt-3 border-t border-[var(--admin-chart-grid)] pt-2.5">
                    <button
                        type="button"
                        onClick={() => setShowRaw((current) => !current)}
                        aria-expanded={showRaw}
                        className="text-xs font-medium text-[#0058be] hover:underline"
                    >
                        {showRaw ? t('esc.hideRaw') : t('esc.showRaw', { count: rawList.length })}
                    </button>
                    {showRaw && (
                        <ul className="mt-2 max-h-48 space-y-1 overflow-auto pr-1">
                            {rawList.map(([reason, count]) => (
                                <li key={reason} className="flex items-start justify-between gap-3 text-xs text-[var(--admin-chart-muted)]">
                                    <span className="break-words text-[var(--admin-chart-title)]">{reason}</span>
                                    <span className="shrink-0 tabular-nums">{formatNumber(count)}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}
