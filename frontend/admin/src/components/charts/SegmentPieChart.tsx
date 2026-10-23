import { motion } from 'framer-motion';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import {
    CHART_CARD_CLASS,
    CHART_EMPTY_CLASS,
    CHART_SUBTITLE_CLASS,
    CHART_TITLE_CLASS,
    CHART_TOOLTIP_STYLE,
    CHART_TOOLTIP_WRAPPER_STYLE,
} from './chartTheme';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';

interface SegmentPieChartProps {
    byLanguage: Record<string, number>;
    targetVsNontarget: { target: number; nontarget: number };
}

interface SegmentSlice {
    key: string;
    name: string;
    value: number;
    fill: string;
}

const LANGUAGE_COLORS: Record<string, string> = {
    en: '#3b82f6',
    ar: '#10b981',
    ru: '#8b5cf6',
    other: '#64748b',
};

const LANGUAGE_NAME_KEYS: Record<string, TranslationKey> = {
    en: 'chart.lang.en',
    ar: 'chart.lang.ar',
    ru: 'chart.lang.ru',
};

const TARGET_COLORS = ['#10b981', '#ef4444'];

function DonutBlock({
    title,
    help,
    slices,
}: {
    title: string;
    help: string;
    slices: SegmentSlice[];
}) {
    const { t, formatNumber } = useI18n();
    const total = slices.reduce((sum, slice) => sum + slice.value, 0);
    const hasData = slices.some((slice) => slice.value > 0);

    return (
        <div className="min-w-0">
            <div className="mb-2 flex items-center justify-center gap-1.5">
                <p className={`${CHART_SUBTITLE_CLASS} mb-0`}>{title}</p>
                <HelpTooltip text={help} />
            </div>
            {hasData ? (
                <>
                    <div className="relative mx-auto h-[128px] w-full max-w-[180px]">
                        <div className="pointer-events-none absolute inset-0 z-0 flex flex-col items-center justify-center">
                            <span className="text-lg font-semibold leading-5 text-[var(--admin-chart-title)]">{formatNumber(total)}</span>
                            <span className="text-[10px] uppercase text-[var(--admin-chart-muted)]">{t('chart.total')}</span>
                        </div>
                        <ResponsiveContainer className="relative z-10" width="100%" height={128}>
                            <PieChart>
                                <Pie
                                    data={slices}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={38}
                                    outerRadius={56}
                                    paddingAngle={3}
                                    dataKey="value"
                                    nameKey="name"
                                    isAnimationActive={false}
                                >
                                    {slices.map((slice) => (
                                        <Cell key={slice.key} fill={slice.fill} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    wrapperStyle={CHART_TOOLTIP_WRAPPER_STYLE}
                                    contentStyle={CHART_TOOLTIP_STYLE}
                                    formatter={(value: number, name: string) => [formatNumber(value), name]}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <ul className="mt-3 space-y-2" data-segment-legend="">
                        {slices.map((slice) => {
                            const percent = total > 0 ? (slice.value / total) * 100 : 0;
                            return (
                                <li key={slice.key} className="text-xs text-[var(--admin-chart-muted)]">
                                    <div className="flex items-center justify-between gap-2">
                                        <span className="flex min-w-0 items-center gap-2">
                                            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: slice.fill }} />
                                            <span className="truncate font-medium text-[var(--admin-chart-title)]">{slice.name}</span>
                                        </span>
                                        <span className="shrink-0 tabular-nums">
                                            {formatNumber(slice.value)} · {formatNumber(percent, 1)}%
                                        </span>
                                    </div>
                                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--admin-chart-grid)]">
                                        <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: slice.fill }} />
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                </>
            ) : (
                <div className={`${CHART_EMPTY_CLASS} h-[128px]`}>{t('chart.noData')}</div>
            )}
        </div>
    );
}

export default function SegmentPieChart({ byLanguage, targetVsNontarget }: SegmentPieChartProps) {
    const { t } = useI18n();

    const langData: SegmentSlice[] = Object.entries(byLanguage).map(([lang, count]) => {
        const nameKey = LANGUAGE_NAME_KEYS[lang.toLowerCase()];
        return {
            key: lang,
            name: nameKey ? t(nameKey) : lang.toUpperCase(),
            value: count,
            fill: LANGUAGE_COLORS[lang.toLowerCase()] ?? LANGUAGE_COLORS.other,
        };
    });

    const targetData: SegmentSlice[] = [
        { key: 'target', name: t('chart.target'), value: targetVsNontarget.target, fill: TARGET_COLORS[0] },
        { key: 'nontarget', name: t('chart.nontarget'), value: targetVsNontarget.nontarget, fill: TARGET_COLORS[1] },
    ];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className={CHART_CARD_CLASS}
        >
            <div className="mb-4 flex items-center gap-2">
                <h3 className={CHART_TITLE_CLASS}>{t('chart.classification')}</h3>
                <HelpTooltip text={t('chart.classificationHelp')} />
            </div>
            <div className="flex flex-col gap-6">
                <DonutBlock title={t('chart.byLanguage')} help={t('chart.byLanguageHelp')} slices={langData} />
                <DonutBlock title={t('chart.targetVsNontarget')} help={t('chart.targetHelp')} slices={targetData} />
            </div>
        </motion.div>
    );
}
