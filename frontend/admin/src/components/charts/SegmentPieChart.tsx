import { motion } from 'framer-motion';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { CHART_TOOLTIP_STYLE } from './chartTheme';

interface SegmentPieChartProps {
    byLanguage: Record<string, number>;
    targetVsNontarget: { target: number; nontarget: number };
}

const LANGUAGE_COLORS: Record<string, string> = {
    en: '#3b82f6',
    ar: '#10b981',
    ru: '#8b5cf6',
    other: '#64748b',
};

const TARGET_COLORS = ['#10b981', '#ef4444'];

export default function SegmentPieChart({ byLanguage, targetVsNontarget }: SegmentPieChartProps) {
    const langData = Object.entries(byLanguage).map(([lang, count]) => ({
        name: lang.toUpperCase(),
        value: count,
        fill: LANGUAGE_COLORS[lang] ?? LANGUAGE_COLORS.other,
    }));

    const targetData = [
        { name: 'Target', value: targetVsNontarget.target },
        { name: 'Non-target', value: targetVsNontarget.nontarget },
    ];

    const hasLangData = langData.some(d => d.value > 0);
    const hasTargetData = targetData.some(d => d.value > 0);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-xl border border-white/[0.08] p-6"
        >
            <h3 className="text-lg font-semibold text-slate-200 mb-4">Classification</h3>
            <div className="grid grid-cols-2 gap-4">
                {/* Language donut */}
                <div>
                    <p className="text-xs text-slate-500 text-center mb-2">By Language</p>
                    {hasLangData ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={langData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={40}
                                    outerRadius={70}
                                    paddingAngle={3}
                                    dataKey="value"
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                >
                                    {langData.map((entry, idx) => (
                                        <Cell key={idx} fill={entry.fill} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-[200px] text-slate-600 text-sm">No data</div>
                    )}
                </div>

                {/* Target vs non-target donut */}
                <div>
                    <p className="text-xs text-slate-500 text-center mb-2">Target vs Non-target</p>
                    {hasTargetData ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={targetData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={40}
                                    outerRadius={70}
                                    paddingAngle={3}
                                    dataKey="value"
                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                >
                                    {targetData.map((_, idx) => (
                                        <Cell key={idx} fill={TARGET_COLORS[idx]} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                                <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '12px' }} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-[200px] text-slate-600 text-sm">No data</div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
