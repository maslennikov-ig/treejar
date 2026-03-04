import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    MessageCircle,
    Users,
    TrendingUp,
    DollarSign,
    Activity,
    Star,
    Clock,
    AlertTriangle,
    RefreshCw,
} from 'lucide-react';
import StatCard from '@/components/StatCard';
import ConversationsChart from '@/components/charts/ConversationsChart';
import SegmentPieChart from '@/components/charts/SegmentPieChart';
import SalesBarChart from '@/components/charts/SalesBarChart';
import { useMetrics } from '@/hooks/useMetrics';
import type { Period } from '@/types/metrics';

const PERIODS: { label: string; value: Period }[] = [
    { label: 'Day', value: 'day' },
    { label: 'Week', value: 'week' },
    { label: 'Month', value: 'month' },
    { label: 'All Time', value: 'all_time' },
];

export default function App() {
    const [period, setPeriod] = useState<Period>('all_time');
    const { data, timeseries, loading, error, refetch } = useMetrics(period);

    return (
        <div className="min-h-screen bg-[#0f172a] px-4 py-6 sm:px-6 lg:px-8">
            {/* Header */}
            <motion.header
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="mx-auto max-w-7xl mb-8"
            >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">
                            <span className="text-emerald-400">Noor</span> Dashboard
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">AI Sales Performance Analytics</p>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Period selector */}
                        <div className="flex bg-slate-800/60 rounded-xl p-1 border border-white/[0.06]">
                            {PERIODS.map((p) => (
                                <button
                                    key={p.value}
                                    onClick={() => setPeriod(p.value)}
                                    className={`
                    px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    ${period === p.value
                                            ? 'bg-emerald-500/20 text-emerald-400 shadow-sm'
                                            : 'text-slate-400 hover:text-slate-300 hover:bg-white/[0.04]'
                                        }
                  `}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>

                        {/* Refresh button */}
                        <button
                            onClick={refetch}
                            disabled={loading}
                            className="p-2.5 rounded-xl bg-slate-800/60 border border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.08] transition-all disabled:opacity-50"
                        >
                            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                </div>
            </motion.header>

            {/* Error state */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mx-auto max-w-7xl mb-6"
                    >
                        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm">
                            <AlertTriangle size={16} className="inline mr-2" />
                            {error}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Loading skeleton */}
            {loading && !data && (
                <div className="mx-auto max-w-7xl">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <div key={i} className="h-[140px] rounded-2xl bg-slate-800/30 animate-pulse" />
                        ))}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <div key={i} className="h-[380px] rounded-2xl bg-slate-800/30 animate-pulse" />
                        ))}
                    </div>
                </div>
            )}

            {/* Dashboard content */}
            {data && (
                <div className="mx-auto max-w-7xl space-y-6">
                    {/* KPI row */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            title="Total Conversations"
                            value={data.total_conversations.toLocaleString()}
                            subtitle={`${data.new_vs_returning.new} new · ${data.new_vs_returning.returning} returning`}
                            icon={MessageCircle}
                            color="emerald"
                            delay={0}
                        />
                        <StatCard
                            title="Unique Customers"
                            value={data.unique_customers.toLocaleString()}
                            icon={Users}
                            color="blue"
                            delay={0.1}
                        />
                        <StatCard
                            title="Conversion Rate"
                            value={`${data.conversion_rate}%`}
                            subtitle={`${data.noor_sales.count + data.post_escalation_sales.count} deals total`}
                            icon={TrendingUp}
                            color="violet"
                            delay={0.2}
                        />
                        <StatCard
                            title="LLM Cost"
                            value={`$${data.llm_cost_usd.toFixed(2)}`}
                            subtitle={`Avg response: ${data.avg_response_time_ms.toFixed(0)}ms`}
                            icon={DollarSign}
                            color="amber"
                            delay={0.3}
                        />
                    </div>

                    {/* Secondary KPI row */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            title="Escalations"
                            value={data.escalation_count}
                            icon={AlertTriangle}
                            color="amber"
                            delay={0.15}
                        />
                        <StatCard
                            title="Avg Quality Score"
                            value={`${data.avg_quality_score}/30`}
                            icon={Star}
                            color="violet"
                            delay={0.2}
                        />
                        <StatCard
                            title="Avg Dialog Length"
                            value={`${data.avg_conversation_length} msgs`}
                            icon={Activity}
                            color="blue"
                            delay={0.25}
                        />
                        <StatCard
                            title="Avg Response Time"
                            value={`${data.avg_response_time_ms.toFixed(0)}ms`}
                            icon={Clock}
                            color="emerald"
                            delay={0.3}
                        />
                    </div>

                    {/* Charts row */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <ConversationsChart
                            points={timeseries?.points ?? []}
                            totalConversations={data.total_conversations}
                        />
                        <SegmentPieChart
                            byLanguage={data.by_language}
                            targetVsNontarget={data.target_vs_nontarget}
                        />
                        <SalesBarChart
                            noorSales={data.noor_sales}
                            postEscalationSales={data.post_escalation_sales}
                            conversionRate={data.conversion_rate}
                            escalationCount={data.escalation_count}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
