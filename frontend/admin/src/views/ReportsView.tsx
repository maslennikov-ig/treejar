import { useCallback, useEffect, useState } from 'react';
import { Clock, FileText, TrendingUp } from 'lucide-react';
import { generateOperationsReport } from '@/api/operators';
import { HelpTooltip } from '@/components/HelpTooltip';
import {
    ActionMessageBox,
    Badge,
    Panel,
    RefreshButton,
    SideListPanel,
    StateLine,
    StatusCard,
    ViewBanner,
    errorMessage,
    stripHtml,
} from '@/components/ui/Primitives';
import type { ActionMessage } from '@/components/ui/Primitives';
import { useI18n } from '@/i18n';
import type { OperationsReportResponse } from '@/types/operators';

export default function ReportsView() {
    const { t, formatDateTime } = useI18n();
    const [report, setReport] = useState<OperationsReportResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const loadReport = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const result = await generateOperationsReport();
            setReport(result);
        } catch (err) {
            setMessage({ tone: 'error', text: errorMessage(err, t) });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        void loadReport();
    }, [loadReport]);

    return (
        <>
            <ViewBanner view="reports" />
            <section className="space-y-4 p-5" data-reports-view="">
                {message && <ActionMessageBox message={message} />}
                <Panel
                    title={t('reports.title')}
                    subtitle={t('reports.subtitle')}
                    help={t('reports.help')}
                    icon={FileText}
                    action={
                        <RefreshButton
                            loading={loading}
                            label={t('reports.generate')}
                            onClick={() => void loadReport()}
                        />
                    }
                >
                    {report ? (
                        <div className="space-y-4">
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                                <StatusCard
                                    title={t('metric.conversations')}
                                    help={t('metric.conversationsHelp')}
                                    value={report.data.total_conversations}
                                    note={t('reports.perDay', {
                                        count: report.data.conversations_per_day,
                                    })}
                                />
                                <StatusCard
                                    title={t('metric.conversion')}
                                    help={t('metric.conversionHelp')}
                                    value={`${report.data.conversion_rate}%`}
                                    note={t('metric.dealsCount', {
                                        count: report.data.total_deals,
                                    })}
                                    tone="green"
                                />
                                <StatusCard
                                    title={t('metric.escalations')}
                                    help={t('metric.escalationsHelp')}
                                    value={report.data.escalation_count}
                                    note={t('reports.reasonsCount', {
                                        count: Object.keys(report.data.escalation_reasons).length,
                                    })}
                                    tone="amber"
                                />
                                <StatusCard
                                    title="Manager QA"
                                    help={t('aiqc.contour.manager_qa')}
                                    value={`${report.data.avg_manager_score}/20`}
                                    note={t('reports.reviewsCount', {
                                        count: report.data.manager_reviews_count,
                                    })}
                                    tone="blue"
                                />
                            </div>

                            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                                <div
                                    className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4"
                                    data-telegram-report-preview=""
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <div>
                                            <p className="flex items-center gap-1.5 text-sm font-semibold text-[var(--text-primary)]">
                                                {t('reports.telegramPreview')}
                                                <HelpTooltip text={t('reports.telegramPreviewHelp')} />
                                            </p>
                                            <p className="mt-1 text-xs text-[var(--text-muted)]">
                                                {formatDateTime(report.data.period_start)} —{' '}
                                                {formatDateTime(report.data.period_end)}
                                            </p>
                                        </div>
                                        <Badge
                                            label={`${report.data.avg_quality_score}/30 Bot QA`}
                                            tone="blue"
                                        />
                                    </div>
                                    <pre className="mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 text-sm leading-6 text-[var(--text-primary)]">
                                        {stripHtml(report.text)}
                                    </pre>
                                </div>

                                <div className="space-y-4">
                                    <SideListPanel
                                        title={t('reports.topProducts')}
                                        icon={TrendingUp}
                                        empty={t('reports.topProductsEmpty')}
                                        items={report.data.top_products.map((product) => ({
                                            key: product.sku,
                                            title: product.name,
                                            meta: `${product.sku} · ${t('reports.mentions', {
                                                count: product.mentions,
                                            })}`,
                                        }))}
                                    />
                                    <SideListPanel
                                        title={t('reports.topManagers')}
                                        icon={Clock}
                                        empty={t('reports.topManagersEmpty')}
                                        items={report.data.top_managers.map((manager) => ({
                                            key: manager.name,
                                            title: manager.name,
                                            meta: `${manager.avg_score}/20`,
                                        }))}
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <StateLine
                            text={loading ? t('reports.generating') : t('reports.notLoaded')}
                        />
                    )}
                </Panel>
            </section>
        </>
    );
}
