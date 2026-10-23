import { motion } from 'framer-motion';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
    CHART_AXIS_FONT_SIZE,
    CHART_AXIS_STROKE,
    CHART_CARD_CLASS,
    CHART_GRID_STROKE,
    CHART_META_CLASS,
    CHART_TITLE_CLASS,
    CHART_TOOLTIP_STYLE,
    CHART_TOOLTIP_WRAPPER_STYLE,
} from './chartTheme';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';

interface SalesBarChartProps {
    noorSales: { count: number; amount: number };
    postEscalationSales: { count: number; amount: number };
    conversionRate: number;
    escalationCount: number;
}

export default function SalesBarChart({
    noorSales,
    postEscalationSales,
    conversionRate,
    escalationCount,
}: SalesBarChartProps) {
    const { t } = useI18n();
    const data = [
        { name: t('chart.noorSales'), value: noorSales.count, fill: '#10b981' },
        { name: t('chart.postEscalation'), value: postEscalationSales.count, fill: '#3b82f6' },
        { name: t('chart.escalations'), value: escalationCount, fill: '#f59e0b' },
    ];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className={CHART_CARD_CLASS}
        >
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <h3 className={CHART_TITLE_CLASS}>{t('chart.salesTitle')}</h3>
                        <HelpTooltip text={t('chart.salesHelp')} />
                    </div>
                    <p className={CHART_META_CLASS}>{t('chart.conversionRate', { rate: conversionRate })}</p>
                </div>
            </div>
            <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
                    <XAxis dataKey="name" stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                    <YAxis stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                    <Tooltip wrapperStyle={CHART_TOOLTIP_WRAPPER_STYLE} contentStyle={CHART_TOOLTIP_STYLE} formatter={(value) => [value, t('chart.count')]} />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]} barSize={50}>
                        {data.map((entry, index) => (
                            <Cell key={index} fill={entry.fill} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </motion.div>
    );
}
