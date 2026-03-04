import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: LucideIcon;
    color: string; // tailwind color class e.g. 'emerald', 'blue', 'violet', 'amber'
    delay?: number;
}

const colorMap: Record<string, { bg: string; text: string; ring: string; icon: string }> = {
    emerald: {
        bg: 'from-emerald-500/10 to-emerald-500/5',
        text: 'text-emerald-400',
        ring: 'ring-emerald-500/20',
        icon: 'bg-emerald-500/20 text-emerald-400',
    },
    blue: {
        bg: 'from-blue-500/10 to-blue-500/5',
        text: 'text-blue-400',
        ring: 'ring-blue-500/20',
        icon: 'bg-blue-500/20 text-blue-400',
    },
    violet: {
        bg: 'from-violet-500/10 to-violet-500/5',
        text: 'text-violet-400',
        ring: 'ring-violet-500/20',
        icon: 'bg-violet-500/20 text-violet-400',
    },
    amber: {
        bg: 'from-amber-500/10 to-amber-500/5',
        text: 'text-amber-400',
        ring: 'ring-amber-500/20',
        icon: 'bg-amber-500/20 text-amber-400',
    },
};

export default function StatCard({ title, value, subtitle, icon: Icon, color, delay = 0 }: StatCardProps) {
    const colors = colorMap[color] ?? colorMap.blue;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay }}
            className={`
        relative overflow-hidden rounded-2xl
        bg-gradient-to-br ${colors.bg}
        backdrop-blur-xl
        border border-white/[0.08]
        ring-1 ${colors.ring}
        p-6
        hover:border-white/[0.15] transition-all duration-300
      `}
        >
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <p className="text-sm font-medium text-slate-400">{title}</p>
                    <p className={`text-3xl font-bold tracking-tight ${colors.text}`}>
                        {value}
                    </p>
                    {subtitle && (
                        <p className="text-xs text-slate-500">{subtitle}</p>
                    )}
                </div>
                <div className={`rounded-xl p-3 ${colors.icon}`}>
                    <Icon size={22} />
                </div>
            </div>

            {/* Decorative glow */}
            <div className={`absolute -top-12 -right-12 w-32 h-32 rounded-full ${colors.bg} blur-3xl opacity-50`} />
        </motion.div>
    );
}
