import { motion } from 'framer-motion';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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
    const data = [
        { name: 'Noor Sales', value: noorSales.count, fill: '#10b981' },
        { name: 'Post-Escalation', value: postEscalationSales.count, fill: '#3b82f6' },
        { name: 'Escalations', value: escalationCount, fill: '#f59e0b' },
    ];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-xl border border-white/[0.08] p-6"
        >
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-slate-200">Sales & Escalation</h3>
                    <p className="text-sm text-slate-500">Conversion Rate: {conversionRate}%</p>
                </div>
            </div>
            <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#64748b" fontSize={12} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '12px',
                            color: '#e2e8f0',
                            fontSize: '13px',
                        }}
                    />
                    <Bar dataKey="value" radius={[8, 8, 0, 0]} barSize={50}>
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </motion.div>
    );
}
