import { motion } from 'framer-motion';
import {
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Tooltip,
} from 'recharts';
import { useI18n, type TranslationKey } from '@/i18n';
import {
    CHART_CARD_CLASS,
    CHART_MUTED_TEXT_CLASS,
    CHART_TITLE_TEXT_CLASS,
    CHART_TOOLTIP_CONTENT_STYLE,
    CHART_TOOLTIP_ITEM_STYLE,
    CHART_TOOLTIP_LABEL_STYLE,
    CHART_TOOLTIP_WRAPPER_STYLE,
} from './chartTheme';

interface Props {
    byLanguage: Record<string, number>;
    targetVsNontarget: Record<string, number>;
    onSelectFilter?: (filter: { language?: string; status?: string }) => void;
}

const LANGUAGE_COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#ec4899'];
const TARGET_COLORS = ['#10b981', '#ef4444'];

const LANGUAGE_NAME_KEYS: Record<string, TranslationKey> = {
    en: 'chart.lang.en',
    ar: 'chart.lang.ar',
    ru: 'chart.lang.ru',
};

interface DonutSlice {
    code: string;
    name: string;
    value: number;
    pct: number;
    color: string;
}

function buildSlices(
    entries: Array<[string, number]>,
    colors: string[],
    labelFor: (key: string) => string,
): DonutSlice[] {
    const clean = entries
        .map(([key, value]) => [key, Number(value) || 0] as const)
        .filter(([, value]) => value > 0);
    const total = clean.reduce((sum, [, value]) => sum + value, 0);
    return clean.map(([key, value], index) => ({
        code: key,
        name: labelFor(key),
        value,
        pct: total > 0 ? (value / total) * 100 : 0,
        color: colors[index % colors.length],
    }));
}

function DonutSection({
    title,
    slices,
    emptyLabel,
    totalLabel,
    formatNumber,
    onSliceClick,
}: {
    title: string;
    slices: DonutSlice[];
    emptyLabel: string;
    totalLabel: string;
    formatNumber: (value: number, digits?: number) => string;
    onSliceClick?: (code: string) => void;
}) {
    const total = slices.reduce((sum, item) => sum + item.value, 0);

    return (
        <div className="admin-subpanel flex flex-col justify-center rounded-xl p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
                <p className={`text-xs font-semibold ${CHART_MUTED_TEXT_CLASS}`}>{title}</p>
                <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                    {totalLabel}: {formatNumber(total)}
                </span>
            </div>
            {slices.length === 0 ? (
                <div className={`flex h-24 items-center justify-center text-xs ${CHART_MUTED_TEXT_CLASS}`}>
                    {emptyLabel}
                </div>
            ) : (
                <div className="flex items-center gap-3">
                    <div className="relative h-28 w-28 shrink-0">
                        <div className="pointer-events-none absolute inset-0 z-0 flex flex-col items-center justify-center text-center">
                            <span className={`text-[9px] font-semibold uppercase ${CHART_MUTED_TEXT_CLASS}`}>
                                {totalLabel}
                            </span>
                            <span className={`text-sm font-bold ${CHART_TITLE_TEXT_CLASS}`}>
                                {formatNumber(total)}
                            </span>
                        </div>
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={slices}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={38}
                                    outerRadius={56}
                                    paddingAngle={3}
                                    dataKey="value"
                                    strokeWidth={0}
                                    onClick={(entry: DonutSlice) => {
                                        if (entry?.code && onSliceClick) {
                                            onSliceClick(entry.code);
                                        }
                                    }}
                                >
                                    {slices.map((slice) => (
                                        <Cell
                                            key={slice.code}
                                            fill={slice.color}
                                            className={onSliceClick ? 'cursor-pointer' : undefined}
                                        />
                                    ))}
                                </Pie>
                                <Tooltip
                                    wrapperStyle={CHART_TOOLTIP_WRAPPER_STYLE}
                                    contentStyle={CHART_TOOLTIP_CONTENT_STYLE}
                                    labelStyle={CHART_TOOLTIP_LABEL_STYLE}
                                    itemStyle={CHART_TOOLTIP_ITEM_STYLE}
                                    formatter={(value: number, name: string) => [
                                        `${formatNumber(value)} (${formatNumber(total > 0 ? (value / total) * 100 : 0, 1)}%)`,
                                        name,
                                    ]}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <ul className="min-w-0 flex-1 space-y-1.5 text-xs" data-segment-legend>
                        {slices.map((slice) => (
                            <li
                                key={slice.code}
                                onClick={() => onSliceClick?.(slice.code)}
                                className={`flex items-center justify-between gap-2 rounded-lg border border-slate-200/80 bg-white px-2.5 py-1.5 dark:border-slate-700/70 dark:bg-slate-900/70 ${
                                    onSliceClick ? 'cursor-pointer hover:border-blue-400' : ''
                                }`}
                            >
                                <span className="flex min-w-0 items-center gap-1.5">
                                    <span
                                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                                        style={{ backgroundColor: slice.color }}
                                    />
                                    <span className={`truncate font-medium ${CHART_TITLE_TEXT_CLASS}`}>
                                        {slice.name}
                                    </span>
                                </span>
                                <span className={`shrink-0 font-mono text-[11px] ${CHART_MUTED_TEXT_CLASS}`}>
                                    {formatNumber(slice.value)} · {formatNumber(slice.pct, 1)}%
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

export default function SegmentPieChart({
    byLanguage,
    targetVsNontarget,
    onSelectFilter,
}: Props) {
    const { t, formatNumber } = useI18n();
    const langData = buildSlices(Object.entries(byLanguage), LANGUAGE_COLORS, (key) => {
        const nameKey = LANGUAGE_NAME_KEYS[key.toLowerCase()];
        return nameKey ? t(nameKey) : key.toUpperCase();
    });
    const targetData = buildSlices(
        [
            ['target', targetVsNontarget.target ?? 0],
            ['nontarget', targetVsNontarget.nontarget ?? 0],
        ],
        TARGET_COLORS,
        (key) => (key === 'target' ? t('chart.target') : t('chart.nontarget')),
    );

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className={`${CHART_CARD_CLASS} flex h-full flex-col rounded-2xl p-4`}
        >
            <h3 className={`mb-3 text-base font-semibold ${CHART_TITLE_TEXT_CLASS}`}>
                {t('chart.segment.title')}
            </h3>

            <div className="flex flex-1 flex-col justify-between gap-2.5">
                <DonutSection
                    title={t('chart.segment.byLanguage')}
                    slices={langData}
                    emptyLabel={t('chart.segment.noData')}
                    totalLabel={t('chart.segment.total')}
                    formatNumber={formatNumber}
                    onSliceClick={
                        onSelectFilter
                            ? (code) => onSelectFilter({ language: code.toLowerCase() })
                            : undefined
                    }
                />
                <DonutSection
                    title={t('chart.segment.targetSplit')}
                    slices={targetData}
                    emptyLabel={t('chart.segment.noData')}
                    totalLabel={t('chart.segment.total')}
                    formatNumber={formatNumber}
                    onSliceClick={
                        onSelectFilter
                            ? (code) =>
                                  onSelectFilter({
                                      status: code === 'target' ? 'active' : 'closed',
                                  })
                            : undefined
                    }
                />
            </div>
        </motion.div>
    );
}
