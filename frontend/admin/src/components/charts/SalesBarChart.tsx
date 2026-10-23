import { motion } from 'framer-motion';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Cell,
} from 'recharts';
import { useI18n } from '@/i18n';
import type { SalesMetrics } from '@/types/metrics';
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
    noorSales: SalesMetrics;
    postEscalationSales: SalesMetrics;
    escalationCount: number;
    conversionRate: number;
    onSelectBar?: (filter: { escalation?: string; deal_status?: string }) => void;
}

const COLORS = ['#10b981', '#6366f1', '#f59e0b'];

export default function SalesBarChart({
    noorSales,
    postEscalationSales,
    escalationCount,
    conversionRate,
    onSelectBar,
}: Props) {
    const { t, formatNumber } = useI18n();
    const data = [
        {
            code: 'noor_sales',
            name: t('chart.sales.noorSales'),
            count: noorSales.count,
            amount: noorSales.amount,
        },
        {
            code: 'post_escalation',
            name: t('chart.sales.postEscalation'),
            count: postEscalationSales.count,
            amount: postEscalationSales.amount,
        },
        {
            code: 'escalations',
            name: t('chart.sales.escalations'),
            count: escalationCount,
            amount: 0,
        },
    ];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className={`${CHART_CARD_CLASS} flex h-full flex-col rounded-2xl p-4`}
        >
            <div className="mb-3 flex items-center justify-between">
                <div>
                    <h3 className={`text-base font-semibold ${CHART_TITLE_TEXT_CLASS}`}>
                        {t('chart.sales.title')}
                    </h3>
                    <p className={`text-xs ${CHART_MUTED_TEXT_CLASS}`}>
                        {t('chart.sales.subtitle')}
                    </p>
                </div>
                <div className="text-right">
                    <span className="text-xl font-bold text-emerald-500">
                        {formatNumber(conversionRate, 1)}%
                    </span>
                    <p className={`text-[11px] ${CHART_MUTED_TEXT_CLASS}`}>
                        {t('chart.sales.conversionRate', {
                            rate: formatNumber(conversionRate, 1),
                        })}
                    </p>
                </div>
            </div>

            <div className="min-h-[168px] flex-1">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={data}
                        margin={{ top: 5, right: 12, left: -12, bottom: 5 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
                        <XAxis
                            dataKey="name"
                            interval={0}
                            tick={{ ...CHART_AXIS_TICK_STYLE, fontSize: 11 }}
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
                            formatter={(
                                value: number,
                                _name: string,
                                props: { payload?: { amount: number } },
                            ) => {
                                const amt = props.payload?.amount;
                                return [
                                    amt
                                        ? `${formatNumber(value)} (${formatNumber(amt)} AED)`
                                        : formatNumber(value),
                                    t('chart.sales.count'),
                                ];
                            }}
                        />
                        <Bar
                            dataKey="count"
                            radius={[8, 8, 0, 0]}
                            maxBarSize={52}
                            onClick={(entry: { code?: string }) => {
                                if (!onSelectBar) return;
                                if (entry?.code === 'noor_sales') {
                                    onSelectBar({ escalation: 'none' });
                                } else if (entry?.code === 'post_escalation') {
                                    onSelectBar({ escalation: 'resolved' });
                                } else if (entry?.code === 'escalations') {
                                    onSelectBar({ escalation: 'pending' });
                                }
                            }}
                        >
                            {data.map((_, i) => (
                                <Cell
                                    key={i}
                                    fill={COLORS[i]}
                                    className={onSelectBar ? 'cursor-pointer' : undefined}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}
