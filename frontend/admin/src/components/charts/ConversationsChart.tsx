import { motion } from 'framer-motion';
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from 'recharts';
import { useI18n } from '@/i18n';
import type { TimeseriesPoint } from '@/types/metrics';
import {
    CHART_AXIS_TICK_STYLE,
    CHART_CARD_CLASS,
    CHART_GRID_STROKE,
    CHART_MUTED_TEXT_CLASS,
    CHART_TITLE_TEXT_CLASS,
    CHART_TOOLTIP_CONTENT_STYLE,
    CHART_TOOLTIP_ITEM_STYLE,
    CHART_TOOLTIP_LABEL_STYLE,
    CHART_TOOLTIP_WRAPPER_STYLE,
} from './chartTheme';

interface Props {
    points: TimeseriesPoint[];
}

export default function ConversationsChart({ points }: Props) {
    const { t } = useI18n();
    const formatted = points.map((p) => ({
        ...p,
        label: p.date.slice(5), // MM-DD
    }));

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className={`${CHART_CARD_CLASS} flex h-full flex-col rounded-2xl p-4`}
        >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                    <h3 className={`text-base font-semibold ${CHART_TITLE_TEXT_CLASS}`}>
                        {t('chart.conv.title')}
                    </h3>
                    <p className={`text-xs ${CHART_MUTED_TEXT_CLASS}`}>
                        {t('chart.conv.subtitle')}
                    </p>
                </div>
                <div
                    data-conv-legend
                    className="flex items-center gap-3 text-xs font-medium"
                >
                    <span className="inline-flex items-center gap-1.5">
                        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                        <span className={CHART_TITLE_TEXT_CLASS}>{t('chart.conv.new')}</span>
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
                        <span className={CHART_TITLE_TEXT_CLASS}>
                            {t('chart.conv.returning')}
                        </span>
                    </span>
                </div>
            </div>

            <div className="min-h-[210px] flex-1">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                        data={formatted}
                        margin={{ top: 5, right: 10, left: -12, bottom: 0 }}
                    >
                        <defs>
                            <linearGradient id="gradNew" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                                <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="gradRet" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.35} />
                                <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
                        <XAxis
                            dataKey="label"
                            tick={CHART_AXIS_TICK_STYLE}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            tick={CHART_AXIS_TICK_STYLE}
                            axisLine={false}
                            tickLine={false}
                            allowDecimals={false}
                        />
                        <Tooltip
                            wrapperStyle={CHART_TOOLTIP_WRAPPER_STYLE}
                            contentStyle={CHART_TOOLTIP_CONTENT_STYLE}
                            labelStyle={CHART_TOOLTIP_LABEL_STYLE}
                            itemStyle={CHART_TOOLTIP_ITEM_STYLE}
                        />
                        <Legend wrapperStyle={{ display: 'none' }} />
                        <Area
                            type="monotone"
                            dataKey="new"
                            name={t('chart.conv.new')}
                            stroke="#10b981"
                            strokeWidth={2}
                            fill="url(#gradNew)"
                        />
                        <Area
                            type="monotone"
                            dataKey="returning"
                            name={t('chart.conv.returning')}
                            stroke="#6366f1"
                            strokeWidth={2}
                            fill="url(#gradRet)"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}
