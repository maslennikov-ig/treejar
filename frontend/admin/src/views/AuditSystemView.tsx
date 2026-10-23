import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Activity,
    ArrowRight,
    ChevronLeft,
    ChevronRight,
    Code2,
    ExternalLink,
    History,
    LifeBuoy,
    ShieldCheck,
} from 'lucide-react';
import { fetchAdminAudit, fetchSystemHealth } from '@/api/crm';
import {
    Badge,
    JsonPreview,
    Panel,
    RefreshButton,
    StateLine,
    StatusCard,
    ViewBanner,
    cx,
    errorMessage,
    matchesQuery,
} from '@/components/ui/Primitives';
import { useI18n } from '@/i18n';
import type { TranslateFn } from '@/i18n';
import type { AdminActionAuditRead, AdminSystemHealthResponse } from '@/types/crm';
import type { AdminViewId } from '@/components/Sidebar';

export type AuditSystemTab = 'audit' | 'system';

interface AuditSystemViewProps {
    globalSearch?: string;
    activeTab?: string;
    onTabChange?: (tab: AuditSystemTab) => void;
    onNavigateEntity?: (view: AdminViewId, id?: string) => void;
}

export function localizeAuditAction(action: string, t: TranslateFn): string {
    const map: Record<string, string> = {
        'admin.conversation.patch': t('audit.action.conversationPatch'),
        'admin.conversation.reset_preview': t('audit.action.conversationResetPreview'),
        'admin.conversation.reset_execute': t('audit.action.conversationResetExecute'),
        'admin.escalation.close': t('audit.action.escalationClose'),
        'admin.knowledge_base.create': t('audit.action.kbCreate'),
        'admin.knowledge_base.update': t('audit.action.kbUpdate'),
        'admin.knowledge_base.delete': t('audit.action.kbDelete'),
        'admin.knowledge_base.reindex': t('audit.action.kbReindex'),
        'admin.knowledge_base.sync_canonical': t('audit.action.kbSyncCanonical'),
        'admin.knowledge_base.candidate_approve': t('audit.action.kbCandidateApprove'),
        'admin.knowledge_base.candidate_reject': t('audit.action.kbCandidateReject'),
        'admin.bot_rule.create': t('audit.action.botRuleCreate'),
        'admin.bot_rule.update': t('audit.action.botRuleUpdate'),
        'admin.bot_rule.archive': t('audit.action.botRuleArchive'),
        'admin.bot_rule.reindex': t('audit.action.botRuleReindex'),
        'admin.bot_rule.sync_canonical': t('audit.action.botRuleSyncCanonical'),
        'admin.quality.bot_review': t('audit.action.qualityBotReview'),
    };
    return map[action] ?? action;
}

function asRecord(val: unknown): Record<string, unknown> | null {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
        return val as Record<string, unknown>;
    }
    return null;
}

function computeAuditDiffEntries(
    beforeRaw: unknown,
    afterRaw: unknown,
): Array<{ key: string; beforeVal: string; afterVal: string }> {
    const b = asRecord(beforeRaw) ?? {};
    const a = asRecord(afterRaw) ?? {};
    const keys = Array.from(new Set([...Object.keys(b), ...Object.keys(a)]));
    const diffs: Array<{ key: string; beforeVal: string; afterVal: string }> = [];
    for (const key of keys) {
        const bv = b[key] !== undefined ? JSON.stringify(b[key]) : '—';
        const av = a[key] !== undefined ? JSON.stringify(a[key]) : '—';
        if (bv !== av) {
            diffs.push({ key, beforeVal: bv, afterVal: av });
        }
    }
    return diffs;
}

export default function AuditSystemView({
    globalSearch = '',
    activeTab: externalTab,
    onTabChange,
    onNavigateEntity,
}: AuditSystemViewProps) {
    const { t, formatDate } = useI18n();

    const resolvedTab: AuditSystemTab =
        externalTab === 'system' || externalTab === 'health' ? 'system' : 'audit';
    const [localTab, setLocalTab] = useState<AuditSystemTab>(resolvedTab);

    useEffect(() => {
        if (externalTab) {
            setLocalTab(resolvedTab);
        }
    }, [externalTab, resolvedTab]);

    const currentTab = onTabChange ? resolvedTab : localTab;
    const handleSelectTab = (next: AuditSystemTab) => {
        setLocalTab(next);
        onTabChange?.(next);
    };

    const [rows, setRows] = useState<AdminActionAuditRead[]>([]);
    const [totalRows, setTotalRows] = useState(0);
    const [page, setPage] = useState(1);
    const [selected, setSelected] = useState<AdminActionAuditRead | null>(null);
    const [entityType, setEntityType] = useState('');
    const [actorFilter, setActorFilter] = useState('');
    const [loadingAudit, setLoadingAudit] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [health, setHealth] = useState<AdminSystemHealthResponse | null>(null);
    const [loadingHealth, setLoadingHealth] = useState(false);

    const loadAudit = useCallback(async () => {
        setLoadingAudit(true);
        const params = new URLSearchParams({
            page: String(page),
            page_size: '25',
        });
        if (entityType) params.set('entity_type', entityType);
        if (actorFilter.trim()) params.set('actor', actorFilter.trim());
        try {
            const payload = await fetchAdminAudit(params);
            setRows(payload.items);
            setTotalRows(payload.total);
            setSelected((current) =>
                payload.items.find((row) => row.id === current?.id) ?? payload.items[0] ?? null,
            );
            setError(null);
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setLoadingAudit(false);
        }
    }, [actorFilter, entityType, page, t]);

    const loadHealth = useCallback(async () => {
        setLoadingHealth(true);
        try {
            const payload = await fetchSystemHealth();
            setHealth(payload);
        } catch {
            // Keep fallback cards visible if health endpoint fails.
        } finally {
            setLoadingHealth(false);
        }
    }, []);

    useEffect(() => {
        void loadAudit();
    }, [loadAudit]);

    useEffect(() => {
        void loadHealth();
    }, [loadHealth]);

    const visibleRows = useMemo(
        () =>
            rows.filter((row) =>
                matchesQuery(
                    globalSearch,
                    row.action,
                    localizeAuditAction(row.action, t),
                    row.actor,
                    row.entity_type,
                    row.entity_id,
                    row.request_path,
                ),
            ),
        [globalSearch, rows, t],
    );

    const diffEntries = useMemo(
        () => (selected ? computeAuditDiffEntries(selected.before, selected.after) : []),
        [selected],
    );

    function handleEntityJump(row: AdminActionAuditRead) {
        if (!onNavigateEntity) return;
        if (row.entity_type === 'conversation' && row.entity_id) {
            onNavigateEntity('conversations', row.entity_id);
        } else if (row.entity_type === 'knowledge_base') {
            onNavigateEntity('knowledge', row.entity_id ?? undefined);
        } else if (row.entity_type === 'bot_rule') {
            onNavigateEntity('botRules', row.entity_id ?? undefined);
        } else if (row.entity_type === 'escalation') {
            onNavigateEntity('queuesQuality');
        }
    }

    const totalPages = Math.max(1, Math.ceil(totalRows / 25));

    return (
        <>
            <ViewBanner view={currentTab === 'system' ? 'support' : 'audit'} />

            <section className="space-y-4 p-5" data-audit-system-view="">
                {/* Tabs Bar: Audit Log vs System Health */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-3">
                    <div
                        role="tablist"
                        aria-label={t('nav.auditSystem')}
                        className="inline-flex rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-1"
                        data-audit-system-tabs=""
                    >
                        <button
                            type="button"
                            role="tab"
                            aria-selected={currentTab === 'audit'}
                            onClick={() => handleSelectTab('audit')}
                            className={cx(
                                'inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition',
                                currentTab === 'audit'
                                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] shadow-xs'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                            )}
                            data-tab="audit"
                        >
                            <History size={14} />
                            <span>{t('audit.tab.log')}</span>
                            <Badge label={String(totalRows || rows.length)} tone="gray" />
                        </button>

                        <button
                            type="button"
                            role="tab"
                            aria-selected={currentTab === 'system'}
                            onClick={() => handleSelectTab('system')}
                            className={cx(
                                'inline-flex items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition',
                                currentTab === 'system'
                                    ? 'bg-[var(--bg-card)] text-[var(--accent-primary)] shadow-xs'
                                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                            )}
                            data-tab="system"
                        >
                            <Activity size={14} />
                            <span>{t('audit.tab.systemHealth')}</span>
                            <Badge
                                label={
                                    health?.overall_status === 'ok'
                                        ? 'OK'
                                        : health?.overall_status === 'warning'
                                            ? 'WARN'
                                            : health?.overall_status === 'error'
                                                ? 'ERR'
                                                : 'LIVE'
                                }
                                tone={
                                    health?.overall_status === 'ok'
                                        ? 'green'
                                        : health?.overall_status === 'warning' || health?.overall_status === 'error'
                                            ? 'amber'
                                            : 'blue'
                                }
                            />
                        </button>
                    </div>

                    <RefreshButton
                        loading={currentTab === 'audit' ? loadingAudit : loadingHealth}
                        onClick={() =>
                            void (currentTab === 'audit' ? loadAudit() : loadHealth())
                        }
                    />
                </div>

                {/* TAB 1: Audit Action Log (tj-7ps5.12, AC12) */}
                {currentTab === 'audit' && (
                    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]" data-audit-log-panel="">
                        <Panel
                            title={t('audit.title')}
                            subtitle={t('audit.subtitle')}
                            icon={History}
                            action={
                                <div className="flex flex-wrap items-center gap-2">
                                    <input
                                        value={actorFilter}
                                        onChange={(event) => {
                                            setActorFilter(event.target.value);
                                            setPage(1);
                                        }}
                                        placeholder={t('audit.actorFilterPlaceholder')}
                                        className="h-8 w-36 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                    />
                                    <select
                                        value={entityType}
                                        onChange={(event) => {
                                            setEntityType(event.target.value);
                                            setPage(1);
                                        }}
                                        aria-label={t('audit.entityFilterLabel')}
                                        className="h-8 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                    >
                                        <option value="">{t('audit.allEntities')}</option>
                                        <option value="conversation">{t('audit.entity.conversation')}</option>
                                        <option value="escalation">{t('audit.entity.escalation')}</option>
                                        <option value="knowledge_base">{t('audit.entity.knowledgeBase')}</option>
                                        <option value="bot_rule">{t('audit.entity.botRule')}</option>
                                        <option value="quality">{t('audit.entity.quality')}</option>
                                    </select>
                                </div>
                            }
                        >
                            {error && <StateLine text={error} tone="red" />}
                            <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)]">
                                <table className="min-w-full divide-y divide-[var(--border-subtle)] text-sm">
                                    <thead className="bg-[var(--bg-surface)] text-left text-xs uppercase text-[var(--text-muted)]">
                                        <tr>
                                            <th className="px-3.5 py-2.5">{t('audit.colTime')}</th>
                                            <th className="px-3.5 py-2.5">{t('audit.colAction')}</th>
                                            <th className="px-3.5 py-2.5">{t('audit.colEntity')}</th>
                                            <th className="px-3.5 py-2.5">{t('audit.actor')}</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-[var(--border-subtle)]">
                                        {visibleRows.map((row) => (
                                            <tr
                                                key={row.id}
                                                onClick={() => setSelected(row)}
                                                className={cx(
                                                    'cursor-pointer transition',
                                                    selected?.id === row.id
                                                        ? 'bg-[var(--accent-soft)]'
                                                        : 'hover:bg-[var(--bg-hover)]',
                                                )}
                                                data-audit-row={row.id}
                                            >
                                                <td className="whitespace-nowrap px-3.5 py-2.5 text-xs text-[var(--text-muted)]">
                                                    {formatDate(row.created_at)}
                                                </td>
                                                <td className="px-3.5 py-2.5">
                                                    <p className="font-medium text-[var(--text-primary)]">
                                                        {localizeAuditAction(row.action, t)}
                                                    </p>
                                                    <p className="text-[11px] font-mono text-[var(--text-muted)]">
                                                        {row.action}
                                                    </p>
                                                </td>
                                                <td className="px-3.5 py-2.5 text-xs text-[var(--text-secondary)]">
                                                    <span className="font-medium">{row.entity_type}</span>
                                                    {row.entity_id ? (
                                                        <span className="ml-1 font-mono text-[11px] text-[var(--text-muted)]">
                                                            :{row.entity_id.slice(0, 8)}
                                                        </span>
                                                    ) : null}
                                                </td>
                                                <td className="px-3.5 py-2.5 text-xs text-[var(--text-secondary)]">
                                                    {row.actor}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                {visibleRows.length === 0 && <StateLine text={t('audit.empty')} />}
                            </div>

                            {/* Pagination Bar */}
                            <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-muted)]">
                                <span>
                                    {t('audit.pageInfo', {
                                        page,
                                        totalPages,
                                        total: totalRows,
                                    })}
                                </span>
                                <div className="flex items-center gap-1.5">
                                    <button
                                        type="button"
                                        disabled={page <= 1 || loadingAudit}
                                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-40"
                                        aria-label="Prev page"
                                    >
                                        <ChevronLeft size={14} />
                                    </button>
                                    <button
                                        type="button"
                                        disabled={page >= totalPages || loadingAudit}
                                        onClick={() => setPage((p) => p + 1)}
                                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-40"
                                        aria-label="Next page"
                                    >
                                        <ChevronRight size={14} />
                                    </button>
                                </div>
                            </div>
                        </Panel>

                        {/* Fixed Non-Overlapping Audit Details Panel (AC12) */}
                        <Panel
                            title={t('audit.detailsTitle')}
                            subtitle={t('audit.detailsSubtitle')}
                            icon={ShieldCheck}
                            action={
                                selected &&
                                onNavigateEntity &&
                                ['conversation', 'knowledge_base', 'bot_rule', 'escalation'].includes(
                                    selected.entity_type,
                                ) ? (
                                    <button
                                        type="button"
                                        onClick={() => handleEntityJump(selected)}
                                        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-1 text-xs font-medium text-[var(--accent-primary)] hover:bg-[var(--bg-hover)]"
                                        data-audit-jump-entity=""
                                    >
                                        <ExternalLink size={13} />
                                        {t('audit.openEntityBtn')}
                                    </button>
                                ) : undefined
                            }
                        >
                            {selected ? (
                                <div className="space-y-4" data-audit-detail-card="">
                                    {/* Stacked non-overlapping metadata grid (fixes AC12 text overlap!) */}
                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                        <AuditMetaItem
                                            label={t('audit.actor')}
                                            value={selected.actor}
                                        />
                                        <AuditMetaItem
                                            label={t('audit.colAction')}
                                            value={`${localizeAuditAction(selected.action, t)} (${selected.action})`}
                                        />
                                        <AuditMetaItem
                                            label={t('audit.colEntity')}
                                            value={`${selected.entity_type}:${selected.entity_id || '—'}`}
                                            mono
                                        />
                                        <AuditMetaItem
                                            label={t('audit.colPath')}
                                            value={selected.request_path || '—'}
                                            mono
                                        />
                                    </div>

                                    {/* Human-readable Field Diff Summary */}
                                    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                                            {t('audit.diffSummaryTitle')}
                                        </p>
                                        {diffEntries.length > 0 ? (
                                            <div className="mt-2 space-y-1.5">
                                                {diffEntries.map((diff) => (
                                                    <div
                                                        key={diff.key}
                                                        className="flex flex-wrap items-center gap-1.5 rounded border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-1.5 text-xs"
                                                    >
                                                        <span className="font-mono font-semibold text-[var(--text-primary)]">
                                                            {diff.key}:
                                                        </span>
                                                        <span className="max-w-[180px] truncate font-mono text-rose-600 dark:text-rose-300">
                                                            {diff.beforeVal}
                                                        </span>
                                                        <ArrowRight size={12} className="text-[var(--text-muted)]" />
                                                        <span className="max-w-[180px] truncate font-mono text-emerald-700 dark:text-emerald-300">
                                                            {diff.afterVal}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                                                {t('audit.noFieldDiffs')}
                                            </p>
                                        )}
                                    </div>

                                    {/* Collapsible Raw JSON Technical Details */}
                                    <details
                                        className="group rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)]"
                                        data-audit-raw-json=""
                                    >
                                        <summary className="flex cursor-pointer list-none items-center justify-between px-3.5 py-2.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]">
                                            <span className="inline-flex items-center gap-1.5">
                                                <Code2 size={14} className="text-[var(--accent-primary)]" />
                                                {t('audit.technicalJsonToggle')}
                                            </span>
                                            <span className="text-[11px] text-[var(--text-muted)]">JSON</span>
                                        </summary>
                                        <div className="space-y-3 border-t border-[var(--border-subtle)] p-3.5">
                                            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                                                <JsonPreview
                                                    title={t('audit.before')}
                                                    value={selected.before}
                                                />
                                                <JsonPreview
                                                    title={t('audit.after')}
                                                    value={selected.after}
                                                />
                                            </div>
                                            <JsonPreview
                                                title={t('audit.metadata')}
                                                value={selected.metadata}
                                            />
                                        </div>
                                    </details>
                                </div>
                            ) : (
                                <StateLine text={t('audit.selectRow')} />
                            )}
                        </Panel>
                    </div>
                )}

                {/* TAB 2: Live System Health Contours (tj-7ps5.11, AC11) */}
                {currentTab === 'system' && (
                    <div className="space-y-4" data-system-health-panel="">
                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.25fr_0.75fr]">
                            <Panel
                                title={t('support.smokeTitle')}
                                subtitle={t('support.smokeSubtitle')}
                                icon={Activity}
                            >
                                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                    {(health?.contours ?? []).map((contour) => (
                                        <StatusCard
                                            key={contour.id}
                                            title={contour.label}
                                            value={contour.summary || contour.status.toUpperCase()}
                                            note={contour.detail || contour.summary}
                                            tone={
                                                contour.status === 'ok'
                                                    ? 'green'
                                                    : contour.status === 'warning' || contour.status === 'error'
                                                        ? 'amber'
                                                        : 'gray'
                                            }
                                        />
                                    ))}
                                    {!health && (
                                        <>
                                            <StatusCard
                                                title="PostgreSQL & pgvector"
                                                value="OK"
                                                note={t('support.crmNote')}
                                                tone="green"
                                            />
                                            <StatusCard
                                                title="Redis Cache & State"
                                                value="OK"
                                                note="Redis operational state"
                                                tone="green"
                                            />
                                            <StatusCard
                                                title="Zoho Inventory Stock"
                                                value="LIVE"
                                                note="Redis stock snapshot contour"
                                                tone="blue"
                                            />
                                            <StatusCard
                                                title="RAG & Canonical Seed"
                                                value="READY"
                                                note="Canonical KB & Bot Rules"
                                                tone="green"
                                            />
                                        </>
                                    )}
                                </div>
                            </Panel>

                            <Panel
                                title={t('support.title')}
                                subtitle={t('support.subtitle')}
                                icon={LifeBuoy}
                            >
                                <div className="space-y-3">
                                    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                                            {t('support.telegramTitle')}
                                        </p>
                                        <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                                            {t('support.telegramBody')}
                                        </p>
                                    </div>
                                    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                                            {t('support.runtimeTitle')}
                                        </p>
                                        <p className="mt-1 font-mono text-xs text-[var(--accent-primary)]">
                                            https://noor.starec.ai
                                        </p>
                                    </div>
                                </div>
                            </Panel>
                        </div>
                    </div>
                )}
            </section>
        </>
    );
}

function AuditMetaItem({
    label,
    value,
    mono = false,
}: {
    label: string;
    value: string;
    mono?: boolean;
}) {
    return (
        <div className="min-w-0 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                {label}
            </p>
            <p
                className={cx(
                    'mt-1 break-all text-xs font-medium text-[var(--text-primary)]',
                    mono && 'font-mono',
                )}
            >
                {value}
            </p>
        </div>
    );
}
