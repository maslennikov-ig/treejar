import { CHART_CARD_CLASS, CHART_META_CLASS, CHART_TITLE_CLASS } from './chartTheme';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';
import type { DashboardMetrics } from '@/types/metrics';

const STAGE_ORDER = [
    'greeting',
    'qualifying',
    'needs_analysis',
    'solution',
    'company_details',
    'quoting',
    'closing',
    'feedback',
    'unknown',
];

interface FunnelStep {
    key: string;
    labelKey: TranslationKey;
    helpKey: TranslationKey;
    value: number;
    color: string;
}

function KpiCell({ label, value, help }: { label: string; value: string; help: string }) {
    return (
        <div className="rounded-md border border-[var(--admin-chart-border)] px-3 py-2">
            <div className="flex items-center gap-1.5 text-[11px] uppercase text-[var(--admin-chart-muted)]">
                <span>{label}</span>
                <HelpTooltip text={help} />
            </div>
            <p className="mt-1 text-base font-semibold text-[var(--admin-chart-title)]">{value}</p>
        </div>
    );
}

export default function FunnelEfficiencyChart({
    data,
    onSelectStage,
}: {
    data: DashboardMetrics;
    onSelectStage?: (stage: string) => void;
}) {
    const { t, label, formatNumber } = useI18n();
    const deals = data.noor_sales.count + data.post_escalation_sales.count;
    const steps: FunnelStep[] = [
        { key: 'total', labelKey: 'funnel.total', helpKey: 'funnel.totalHelp', value: data.total_conversations, color: '#0058be' },
        { key: 'target', labelKey: 'funnel.target', helpKey: 'funnel.targetHelp', value: data.target_vs_nontarget.target, color: '#2563eb' },
        { key: 'escalated', labelKey: 'funnel.escalated', helpKey: 'funnel.escalatedHelp', value: data.escalation_count, color: '#f59e0b' },
        { key: 'deals', labelKey: 'funnel.deals', helpKey: 'funnel.dealsHelp', value: deals, color: '#10b981' },
    ];
    const base = Math.max(1, steps[0].value);

    const stageEntries = data.sales_stage_distribution
        ? Object.entries(data.sales_stage_distribution)
            .filter(([, count]) => count > 0)
            .sort((left, right) => {
                const li = STAGE_ORDER.indexOf(left[0]);
                const ri = STAGE_ORDER.indexOf(right[0]);
                return (li === -1 ? 99 : li) - (ri === -1 ? 99 : ri);
            })
        : [];
    const stageTotal = stageEntries.reduce((sum, [, count]) => sum + count, 0);

    return (
        <div className={`${CHART_CARD_CLASS} flex h-full flex-col justify-between p-4`} data-chart="funnel-efficiency">
            <div className="mb-3">
                <div className="flex items-center gap-2">
                    <h3 className={CHART_TITLE_CLASS}>{t('funnel.title')}</h3>
                    <HelpTooltip text={t('funnel.help')} />
                </div>
                <p className={CHART_META_CLASS}>{t('funnel.meta')}</p>
            </div>

            <ol className="space-y-2.5">
                {steps.map((step, index) => {
                    const previous = index > 0 ? steps[index - 1].value : null;
                    const stepConversion = previous !== null && previous > 0 ? (step.value / previous) * 100 : null;
                    const width = Math.min(100, (step.value / base) * 100);
                    return (
                        <li key={step.key}>
                            <div className="flex items-center justify-between gap-3 text-sm">
                                <span className="flex items-center gap-1.5 text-[var(--admin-chart-title)]">
                                    {t(step.labelKey)}
                                    <HelpTooltip text={t(step.helpKey)} />
                                </span>
                                <span className="tabular-nums text-xs text-[var(--admin-chart-muted)]">
                                    <span className="text-sm font-semibold text-[var(--admin-chart-title)]">{formatNumber(step.value)}</span>
                                    {stepConversion !== null && (
                                        <> · {t('funnel.stepConversion', { percent: formatNumber(stepConversion, 1) })}</>
                                    )}
                                </span>
                            </div>
                            <div className="mt-1 h-2.5 w-full overflow-hidden rounded bg-[var(--admin-chart-grid)]">
                                <div className="h-full rounded" style={{ width: `${width}%`, backgroundColor: step.color }} />
                            </div>
                        </li>
                    );
                })}
            </ol>

            <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-3">
                <KpiCell
                    label={t('funnel.avgDeal')}
                    value={`${formatNumber(data.average_deal_value, 0)} AED`}
                    help={t('funnel.avgDealHelp')}
                />
                <KpiCell
                    label={t('funnel.newReturning')}
                    value={`${formatNumber(data.new_vs_returning.new)} / ${formatNumber(data.new_vs_returning.returning)}`}
                    help={t('funnel.newReturningHelp')}
                />
                <KpiCell
                    label={t('funnel.avgLength')}
                    value={t('funnel.messagesValue', { count: formatNumber(data.avg_conversation_length, 1) })}
                    help={t('funnel.avgLengthHelp')}
                />
                <KpiCell
                    label={t('funnel.llmSpend')}
                    value={`$${formatNumber(data.llm_cost_usd, 2)}`}
                    help={t('funnel.llmSpendHelp')}
                />
                <KpiCell
                    label={t('funnel.feedback')}
                    value={`${formatNumber(data.avg_rating_overall, 1)} / ${formatNumber(data.avg_rating_delivery, 1)} /5`}
                    help={t('funnel.feedbackHelp')}
                />
                <KpiCell
                    label={t('funnel.nps')}
                    value={formatNumber(data.nps_score, 0)}
                    help={t('funnel.npsHelp')}
                />
            </div>

            {stageEntries.length > 0 && (
                <div className="mt-4 border-t border-[var(--admin-chart-grid)] pt-3">
                    <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-[var(--admin-chart-muted)]">
                        {t('funnel.stages')}
                        <HelpTooltip text={t('funnel.stagesHelp')} />
                    </div>
                    <ul className="space-y-1.5">
                        {stageEntries.map(([stage, count]) => {
                            const percent = stageTotal > 0 ? (count / stageTotal) * 100 : 0;
                            return (
                                <li
                                    key={stage}
                                    onClick={() => onSelectStage?.(stage)}
                                    className={`grid grid-cols-[110px_1fr_auto] items-center gap-2 text-xs ${onSelectStage ? 'cursor-pointer hover:opacity-80' : ''}`}
                                >
                                    <span className="truncate text-[var(--admin-chart-title)]">{label(stage)}</span>
                                    <span className="h-1.5 overflow-hidden rounded-full bg-[var(--admin-chart-grid)]">
                                        <span className="block h-full rounded-full bg-[#2563eb]" style={{ width: `${percent}%` }} />
                                    </span>
                                    <span className="tabular-nums text-[var(--admin-chart-muted)]">
                                        {formatNumber(count)} · {formatNumber(percent, 1)}%
                                    </span>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            )}
        </div>
    );
}
