import { useCallback, useEffect, useState } from 'react';
import {
    CheckCircle2,
    Database,
    History,
    Package,
    RefreshCw,
} from 'lucide-react';
import { fetchCatalogStatus } from '@/api/crm';
import { syncProducts } from '@/api/operators';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import {
    ActionMessageBox,
    Badge,
    Field,
    Panel,
    RefreshButton,
    StatusCard,
    ViewBanner,
    errorMessage,
} from '@/components/ui/Primitives';
import type { ActionMessage } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';
import { useI18n } from '@/i18n';
import type { AdminCatalogStatusResponse } from '@/types/crm';
import type { ProductSyncResponse, ProductSyncSource } from '@/types/operators';

export default function CatalogView() {
    const { t, formatDateTime, formatDuration } = useI18n();
    const { pushToast } = useToast();

    const [catalogStatus, setCatalogStatus] = useState<AdminCatalogStatusResponse | null>(null);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [syncingSource, setSyncingSource] = useState<ProductSyncSource | null>(null);
    const [confirmSource, setConfirmSource] = useState<ProductSyncSource | null>(null);
    const [result, setResult] = useState<ProductSyncResponse | null>(null);
    const [message, setMessage] = useState<ActionMessage | null>(null);

    const loadStatus = useCallback(async () => {
        setLoadingStatus(true);
        try {
            const payload = await fetchCatalogStatus();
            setCatalogStatus(payload);
        } catch {
            // Keep UI operational if status endpoint is temporarily unreachable.
        } finally {
            setLoadingStatus(false);
        }
    }, []);

    useEffect(() => {
        void loadStatus();
    }, [loadStatus]);

    async function handleConfirmSync() {
        if (!confirmSource) return;
        const source = confirmSource;
        const sourceLabel = source === 'treejar' ? 'Treejar' : 'Zoho';
        setConfirmSource(null);
        setSyncingSource(source);
        setMessage(null);
        try {
            const response = await syncProducts(source);
            setResult(response);
            const msgText = t('catalog.syncQueued', {
                source: sourceLabel,
                errors: response.errors,
            });
            setMessage({
                tone: response.errors > 0 ? 'info' : 'success',
                text: msgText,
            });
            pushToast({
                tone: response.errors > 0 ? 'info' : 'success',
                message: msgText,
            });
            await loadStatus();
        } catch (err) {
            const errText = errorMessage(err, t);
            setMessage({ tone: 'error', text: errText });
            pushToast({ tone: 'error', message: errText });
        } finally {
            setSyncingSource(null);
        }
    }

    const zohoSnapshot = catalogStatus?.zoho_snapshot;
    const zohoFresh = zohoSnapshot?.status === 'fresh';
    const zohoAgeLabel =
        zohoSnapshot?.age_seconds != null
            ? formatDuration(zohoSnapshot.age_seconds)
            : t('catalog.snapshotMissing');
    const treejarSyncAt = catalogStatus?.sources?.treejar?.last_triggered_at ?? null;
    const zohoSyncAt =
        catalogStatus?.sources?.zoho?.last_triggered_at ??
        zohoSnapshot?.updated_at ??
        null;

    return (
        <>
            <ViewBanner
                view="catalog"
                actions={
                    <RefreshButton
                        loading={loadingStatus}
                        onClick={() => void loadStatus()}
                    />
                }
            />

            <section className="space-y-4 p-5" data-catalog-view="">
                {message && <ActionMessageBox message={message} />}

                {/* Top Persisted Catalog & Zoho Stock Snapshot KPIs (tj-7ps5.11, AC10) */}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4" data-catalog-status-kpis="">
                    <StatusCard
                        title={t('catalog.activeProductsTitle')}
                        value={catalogStatus ? catalogStatus.active_products_count : '—'}
                        note={t('catalog.totalProductsNote', {
                            total: catalogStatus?.total_products_count ?? 0,
                        })}
                        tone="blue"
                    />
                    <StatusCard
                        title={t('catalog.indexedRagTitle')}
                        help={t('catalog.embeddingsHelp')}
                        value={catalogStatus ? catalogStatus.indexed_products_count : '—'}
                        note={t('catalog.embeddingsNote')}
                        tone="green"
                    />
                    <StatusCard
                        title={t('catalog.zohoFreshnessTitle')}
                        value={zohoFresh ? t('overview.zohoFresh') : t('overview.zohoStale')}
                        note={t('catalog.zohoFreshnessNote', {
                            age: zohoAgeLabel,
                            items: zohoSnapshot?.item_count ?? 0,
                        })}
                        tone={zohoFresh ? 'green' : 'amber'}
                    />
                    <StatusCard
                        title={t('catalog.lastUpdatedTitle')}
                        value={treejarSyncAt ? formatDateTime(treejarSyncAt) : '—'}
                        note={t('catalog.lastUpdatedNote')}
                        tone="gray"
                    />
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                    <Panel
                        title={t('catalog.syncTitle')}
                        subtitle={t('catalog.syncSubtitle')}
                        help={t('catalog.syncHelp')}
                        icon={Package}
                    >
                        <div className="grid grid-cols-1 gap-3">
                            <CatalogSyncCard
                                title={t('catalog.treejarTitle')}
                                note={t('catalog.treejarNote')}
                                source="treejar"
                                lastSyncAt={
                                    treejarSyncAt ? formatDateTime(treejarSyncAt) : null
                                }
                                syncingSource={syncingSource}
                                onSync={(src) => setConfirmSource(src)}
                            />
                            <CatalogSyncCard
                                title={t('catalog.zohoTitle')}
                                note={t('catalog.zohoNote')}
                                source="zoho"
                                lastSyncAt={
                                    zohoSyncAt ? formatDateTime(zohoSyncAt) : null
                                }
                                syncingSource={syncingSource}
                                onSync={(src) => setConfirmSource(src)}
                            />
                        </div>
                    </Panel>

                    <Panel
                        title={t('catalog.resultTitle')}
                        subtitle={t('catalog.resultSubtitle')}
                        icon={History}
                    >
                        {result ? (
                            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                                <StatusCard
                                    title={t('catalog.synced')}
                                    value={result.synced}
                                    note={t('catalog.syncedNote')}
                                />
                                <StatusCard
                                    title={t('catalog.created')}
                                    value={result.created}
                                    note={t('catalog.createdNote')}
                                    tone="green"
                                />
                                <StatusCard
                                    title={t('catalog.updated')}
                                    value={result.updated}
                                    note={t('catalog.updatedNote')}
                                    tone="blue"
                                />
                                <StatusCard
                                    title={t('catalog.deactivated')}
                                    value={result.deactivated}
                                    note={t('catalog.deactivatedNote')}
                                    tone="amber"
                                />
                                <StatusCard
                                    title={t('catalog.embeddings')}
                                    help={t('catalog.embeddingsHelp')}
                                    value={result.embeddings_generated}
                                    note={t('catalog.embeddingsNote')}
                                    tone="blue"
                                />
                                <StatusCard
                                    title={t('catalog.errors')}
                                    value={result.errors}
                                    note={t('catalog.errorsNote')}
                                    tone={result.errors > 0 ? 'amber' : 'green'}
                                />
                            </div>
                        ) : (
                            <div className="space-y-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                        <Database size={16} className="text-[var(--accent-primary)]" />
                                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                                            {t('catalog.persistedStateTitle')}
                                        </p>
                                    </div>
                                    <Badge
                                        label={
                                            catalogStatus?.active_products_count
                                                ? t('catalog.catalogReadyBadge')
                                                : t('catalog.noResult')
                                        }
                                        tone={catalogStatus?.active_products_count ? 'green' : 'gray'}
                                    />
                                </div>
                                <div className="space-y-2 pt-1">
                                    <Field
                                        label={t('catalog.activeProductsTitle')}
                                        value={String(catalogStatus?.active_products_count ?? '—')}
                                    />
                                    <Field
                                        label={t('catalog.indexedRagTitle')}
                                        value={String(catalogStatus?.indexed_products_count ?? '—')}
                                    />
                                    <Field
                                        label="Zoho Inventory Redis Snapshot"
                                        value={
                                            zohoFresh
                                                ? `${t('overview.zohoFresh')} (${zohoAgeLabel})`
                                                : `${t('overview.zohoStale')} (${zohoAgeLabel})`
                                        }
                                    />
                                    <Field
                                        label={t('catalog.lastUpdatedTitle')}
                                        value={
                                            treejarSyncAt
                                                ? formatDateTime(treejarSyncAt)
                                                : '—'
                                        }
                                    />
                                </div>
                            </div>
                        )}
                    </Panel>
                </div>
            </section>

            <ConfirmDialog
                open={Boolean(confirmSource)}
                title={t('catalog.syncTitle')}
                description={t('catalog.confirmSync', {
                    source: confirmSource === 'treejar' ? 'Treejar' : 'Zoho',
                })}
                confirmLabel={t('common.confirm')}
                cancelLabel={t('common.cancel')}
                busy={syncingSource !== null}
                onConfirm={() => void handleConfirmSync()}
                onCancel={() => setConfirmSource(null)}
            />
        </>
    );
}

function CatalogSyncCard({
    title,
    note,
    source,
    lastSyncAt,
    syncingSource,
    onSync,
}: {
    title: string;
    note: string;
    source: ProductSyncSource;
    lastSyncAt: string | null;
    syncingSource: ProductSyncSource | null;
    onSync: (source: ProductSyncSource) => void;
}) {
    const { t } = useI18n();
    const isSyncing = syncingSource === source;
    return (
        <button
            type="button"
            disabled={syncingSource !== null}
            onClick={() => onSync(source)}
            className="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 text-left transition hover:border-[var(--accent-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
            data-catalog-sync-source={source}
        >
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
                    {lastSyncAt && (
                        <Badge
                            label={`${t('catalog.lastSyncShort')}: ${lastSyncAt}`}
                            tone="green"
                        />
                    )}
                </div>
                {isSyncing ? (
                    <RefreshCw size={16} className="animate-spin text-[var(--accent-primary)]" />
                ) : (
                    <CheckCircle2 size={16} className="text-[var(--accent-primary)]" />
                )}
            </div>
            <p className="mt-1.5 text-xs leading-5 text-[var(--text-secondary)]">{note}</p>
        </button>
    );
}
