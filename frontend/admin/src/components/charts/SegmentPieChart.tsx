import { motion } from 'framer-motion';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import {
    CHART_CARD_CLASS,
    CHART_EMPTY_CLASS,
    CHART_LEGEND_STYLE,
    CHART_SUBTITLE_CLASS,
    CHART_TITLE_CLASS,
    CHART_TOOLTIP_STYLE,
} from './chartTheme';

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
            className={CHART_CARD_CLASS}
        >
            <h3 className={`${CHART_TITLE_CLASS} mb-4`}>Classification</h3>
            <div className="grid grid-cols-2 gap-4">
                {/* Language donut */}
                <div>
                    <p className={CHART_SUBTITLE_CLASS}>By Language</p>
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
                        <div className={`${CHART_EMPTY_CLASS} h-[200px]`}>No data</div>
                    )}
                </div>

                {/* Target vs non-target donut */}
                <div>
                    <p className={CHART_SUBTITLE_CLASS}>Target vs Non-target</p>
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
                                <Legend wrapperStyle={CHART_LEGEND_STYLE} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className={`${CHART_EMPTY_CLASS} h-[200px]`}>No data</div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
