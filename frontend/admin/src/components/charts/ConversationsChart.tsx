import { motion } from 'framer-motion';
import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
import {
    CHART_AXIS_FONT_SIZE,
    CHART_AXIS_STROKE,
    CHART_CARD_CLASS,
    CHART_EMPTY_CLASS,
    CHART_GRID_STROKE,
    CHART_META_CLASS,
    CHART_TITLE_CLASS,
    CHART_TOOLTIP_STYLE,
    CHART_TOOLTIP_WRAPPER_STYLE,
} from './chartTheme';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { TimeseriesPoint } from '@/types/metrics';

interface ConversationsChartProps {
    points: TimeseriesPoint[];
    totalConversations: number;
}

export default function ConversationsChart({ points, totalConversations }: ConversationsChartProps) {
    const { t, lang } = useI18n();
    const locale = lang === 'ru' ? 'ru-RU' : 'en-US';
    const data = points.map((p) => ({
        name: new Date(p.date).toLocaleDateString(locale, { month: 'short', day: 'numeric' }),
        new: p.new,
        returning: p.returning,
    }));

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className={CHART_CARD_CLASS}
        >
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <h3 className={CHART_TITLE_CLASS}>{t('chart.conversationsTitle')}</h3>
                        <HelpTooltip text={t('chart.conversationsHelp')} />
                    </div>
                    <p className={CHART_META_CLASS}>{t('chart.conversationsMeta', { total: totalConversations })}</p>
                </div>
            </div>
            {data.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
                        <XAxis dataKey="name" stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                        <YAxis stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                        <Tooltip wrapperStyle={CHART_TOOLTIP_WRAPPER_STYLE} contentStyle={CHART_TOOLTIP_STYLE} />
                        <Line
                            type="monotone"
                            dataKey="new"
                            stroke="#10b981"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: '#10b981' }}
                            activeDot={{ r: 6 }}
                            name={t('chart.new')}
                        />
                        <Line
                            type="monotone"
                            dataKey="returning"
                            stroke="#3b82f6"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: '#3b82f6' }}
                            activeDot={{ r: 6 }}
                            name={t('chart.returning')}
                        />
                    </LineChart>
                </ResponsiveContainer>
            ) : (
                <div className={`${CHART_EMPTY_CLASS} h-[280px]`}>
                    {t('chart.noConversationData')}
                </div>
            )}
        </motion.div>
    );
}
