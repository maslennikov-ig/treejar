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

interface ConversationsChartProps {
    newVsReturning: { new: number; returning: number };
    totalConversations: number;
}

export default function ConversationsChart({ newVsReturning, totalConversations }: ConversationsChartProps) {
    // Generate synthetic daily data from the totals for visualization
    // TODO: Replace with real timeseries data from /dashboard/metrics/timeseries/
    const data = [
        { name: 'Mon', new: Math.round(newVsReturning.new * 0.12), returning: Math.round(newVsReturning.returning * 0.10) },
        { name: 'Tue', new: Math.round(newVsReturning.new * 0.14), returning: Math.round(newVsReturning.returning * 0.13) },
        { name: 'Wed', new: Math.round(newVsReturning.new * 0.18), returning: Math.round(newVsReturning.returning * 0.16) },
        { name: 'Thu', new: Math.round(newVsReturning.new * 0.16), returning: Math.round(newVsReturning.returning * 0.18) },
        { name: 'Fri', new: Math.round(newVsReturning.new * 0.20), returning: Math.round(newVsReturning.returning * 0.22) },
        { name: 'Sat', new: Math.round(newVsReturning.new * 0.12), returning: Math.round(newVsReturning.returning * 0.12) },
        { name: 'Sun', new: Math.round(newVsReturning.new * 0.08), returning: Math.round(newVsReturning.returning * 0.09) },
    ];

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
        </motion.div>
    );
}
