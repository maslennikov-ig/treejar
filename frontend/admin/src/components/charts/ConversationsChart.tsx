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
import { CHART_AXIS_FONT_SIZE, CHART_AXIS_STROKE, CHART_GRID_STROKE, CHART_TOOLTIP_STYLE } from './chartTheme';
import type { TimeseriesPoint } from '@/types/metrics';

interface ConversationsChartProps {
    points: TimeseriesPoint[];
    totalConversations: number;
}

function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

export default function ConversationsChart({ points, totalConversations }: ConversationsChartProps) {
    const data = points.map((p) => ({
        name: formatDate(p.date),
        new: p.new,
        returning: p.returning,
    }));

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-xl border border-white/[0.08] p-6"
        >
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-slate-200">Conversations</h3>
                    <p className="text-sm text-slate-500">New vs Returning • Total: {totalConversations}</p>
                </div>
            </div>
            {data.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_STROKE} />
                        <XAxis dataKey="name" stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                        <YAxis stroke={CHART_AXIS_STROKE} fontSize={CHART_AXIS_FONT_SIZE} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Line
                            type="monotone"
                            dataKey="new"
                            stroke="#10b981"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: '#10b981' }}
                            activeDot={{ r: 6 }}
                            name="New"
                        />
                        <Line
                            type="monotone"
                            dataKey="returning"
                            stroke="#3b82f6"
                            strokeWidth={2.5}
                            dot={{ r: 4, fill: '#3b82f6' }}
                            activeDot={{ r: 6 }}
                            name="Returning"
                        />
                    </LineChart>
                </ResponsiveContainer>
            ) : (
                <div className="flex items-center justify-center h-[280px] text-slate-600 text-sm">
                    No conversation data for this period
                </div>
            )}
        </motion.div>
    );
}
