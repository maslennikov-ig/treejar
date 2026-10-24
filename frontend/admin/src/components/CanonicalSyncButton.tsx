import { useEffect, useState } from 'react';
import { CheckCircle2, RefreshCw, AlertTriangle, RotateCcw, ShieldCheck, X } from 'lucide-react';
import { createPortal } from 'react-dom';

import {
    fetchCanonicalBotRulesPreview,
    fetchCanonicalKnowledgeBasePreview,
    syncCanonicalBotRules,
    syncCanonicalKnowledgeBase,
} from '@/api/crm';
import { useI18n } from '@/i18n';
import type {
    AdminCanonicalSyncPreview,
    AdminCanonicalSyncResult,
    CanonicalSyncMode,
} from '@/types/crm';

export type CanonicalSyncKind = 'knowledge' | 'botRules';

export interface CanonicalSyncButtonProps {
    kind: CanonicalSyncKind;
    onSynced?: (result: AdminCanonicalSyncResult) => void | Promise<void>;
    compact?: boolean;
    prominent?: boolean;
}

export async function runCanonicalSync(
    kind: CanonicalSyncKind,
    mode: CanonicalSyncMode = 'safe',
): Promise<AdminCanonicalSyncResult> {
    return kind === 'knowledge'
        ? syncCanonicalKnowledgeBase(mode)
        : syncCanonicalBotRules(mode);
}

interface PersistedSyncState {
    busy: boolean;
    result: AdminCanonicalSyncResult | null;
    error: string | null;
}

const SYNC_STATE_CACHE: Record<CanonicalSyncKind, PersistedSyncState> = {
    knowledge: { busy: false, result: null, error: null },
    botRules: { busy: false, result: null, error: null },
};

export default function CanonicalSyncButton({
    kind,
    onSynced,
    compact = false,
}: CanonicalSyncButtonProps) {
    const { t } = useI18n();
    const cached = SYNC_STATE_CACHE[kind];
    const [busy, setBusy] = useState(cached.busy);
    const [result, setResult] = useState<AdminCanonicalSyncResult | null>(cached.result);
    const [error, setError] = useState<string | null>(cached.error);
    const [modalOpen, setModalOpen] = useState(false);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [preview, setPreview] = useState<AdminCanonicalSyncPreview | null>(null);
    const [mode, setMode] = useState<CanonicalSyncMode>('safe');

    useEffect(() => {
        SYNC_STATE_CACHE[kind] = { busy, result, error };
    }, [kind, busy, result, error]);

    const openPreviewModal = async () => {
        setModalOpen(true);
        setPreviewLoading(true);
        setError(null);
        try {
            const data =
                kind === 'knowledge'
                    ? await fetchCanonicalKnowledgeBasePreview()
                    : await fetchCanonicalBotRulesPreview();
            setPreview(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('canonicalSync.failed'));
        } finally {
            setPreviewLoading(false);
        }
    };

    const handleExecuteSync = async () => {
        setBusy(true);
        setError(null);
        try {
            const next =
                kind === 'knowledge'
                    ? await syncCanonicalKnowledgeBase(mode)
                    : await syncCanonicalBotRules(mode);
            setResult(next);
            setModalOpen(false);
            onSynced?.(next);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('canonicalSync.failed'));
        } finally {
            setBusy(false);
        }
    };

    const label =
        kind === 'knowledge'
            ? t('canonicalSync.kbButton')
            : t('canonicalSync.rulesButton');

    const modal = modalOpen ? (
        <div
            data-canonical-restore-modal
            className="fixed inset-0 z-[9995] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-[2px]"
            onClick={() => {
                if (!busy) setModalOpen(false);
            }}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label={t('canonicalSync.modalTitle')}
                onClick={(event) => event.stopPropagation()}
                className="admin-panel w-full max-w-lg rounded-xl p-5 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                            <RotateCcw className="h-5 w-5" />
                        </span>
                        <div>
                            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                                {t('canonicalSync.modalTitle')}
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                                {kind === 'knowledge'
                                    ? t('canonicalSync.modalSubtitleKb')
                                    : t('canonicalSync.modalSubtitleRules')}
                            </p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={() => setModalOpen(false)}
                        disabled={busy}
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                {previewLoading ? (
                    <div className="admin-subpanel mt-4 flex items-center gap-2 rounded-lg p-4 text-xs text-slate-600 dark:text-slate-300">
                        <RefreshCw className="h-4 w-4 animate-spin text-blue-600" />
                        <span>{t('canonicalSync.previewLoading')}</span>
                    </div>
                ) : (
                    preview && (
                        <div className="mt-4 space-y-3">
                            <div className="grid grid-cols-3 gap-2">
                                <div className="admin-subpanel rounded-lg p-2.5 text-center">
                                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                        {t('canonicalSync.diffNew')}
                                    </div>
                                    <div className="mt-0.5 text-lg font-bold text-blue-600 dark:text-blue-400">
                                        {Number(preview.will_create ?? 0)}
                                    </div>
                                </div>
                                <div className="admin-subpanel rounded-lg p-2.5 text-center">
                                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                        {t('canonicalSync.diffCustomized')}
                                    </div>
                                    <div className="mt-0.5 text-lg font-bold text-amber-600 dark:text-amber-400">
                                        {Number(preview.customized ?? 0) +
                                            Number(preview.deleted_or_archived ?? 0)}
                                    </div>
                                </div>
                                <div className="admin-subpanel rounded-lg p-2.5 text-center">
                                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                                        {t('canonicalSync.diffUnchanged')}
                                    </div>
                                    <div className="mt-0.5 text-lg font-bold text-emerald-600 dark:text-emerald-400">
                                        {Number(preview.unchanged ?? 0)}
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label
                                    onClick={() => setMode('safe')}
                                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-xs transition-colors ${
                                        mode === 'safe'
                                            ? 'border-blue-500 bg-blue-50/70 dark:border-blue-500 dark:bg-blue-950/40'
                                            : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="canonical-sync-mode"
                                        checked={mode === 'safe'}
                                        onChange={() => setMode('safe')}
                                        className="mt-0.5 accent-blue-600"
                                    />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-1.5 font-semibold text-slate-900 dark:text-slate-100">
                                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                                            <span>{t('canonicalSync.modeSafeTitle')}</span>
                                        </div>
                                        <p className="mt-0.5 text-slate-600 dark:text-slate-300">
                                            {t('canonicalSync.modeSafeBody')}
                                        </p>
                                    </div>
                                </label>

                                <label
                                    onClick={() => setMode('full_reset')}
                                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-xs transition-colors ${
                                        mode === 'full_reset'
                                            ? 'border-amber-500 bg-amber-50/70 dark:border-amber-500 dark:bg-amber-950/40'
                                            : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="canonical-sync-mode"
                                        checked={mode === 'full_reset'}
                                        onChange={() => setMode('full_reset')}
                                        className="mt-0.5 accent-amber-600"
                                    />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-1.5 font-semibold text-slate-900 dark:text-slate-100">
                                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                                            <span>{t('canonicalSync.modeResetTitle')}</span>
                                        </div>
                                        <p className="mt-0.5 text-slate-600 dark:text-slate-300">
                                            {t('canonicalSync.modeResetBody')}
                                        </p>
                                    </div>
                                </label>
                            </div>
                        </div>
                    )
                )}

                {error && (
                    <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200">
                        {error}
                    </div>
                )}

                <div className="mt-5 flex items-center justify-end gap-2">
                    <button
                        type="button"
                        onClick={() => setModalOpen(false)}
                        disabled={busy}
                        className="admin-subpanel rounded-lg px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        {t('common.cancel')}
                    </button>
                    <button
                        type="button"
                        onClick={() => void handleExecuteSync()}
                        disabled={busy || previewLoading}
                        data-canonical-confirm-submit
                        className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold text-white disabled:opacity-50 ${
                            mode === 'full_reset'
                                ? 'bg-amber-600 hover:bg-amber-700'
                                : 'bg-[#2170e4] hover:bg-blue-700'
                        }`}
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} />
                        {busy
                            ? t('canonicalSync.running')
                            : mode === 'full_reset'
                              ? t('canonicalSync.applyReset')
                              : t('canonicalSync.applySafe')}
                    </button>
                </div>
            </div>
        </div>
    ) : null;

    return (
        <div className="flex flex-wrap items-center gap-2" data-canonical-sync={kind}>
            <button
                type="button"
                onClick={() => void openPreviewModal()}
                disabled={busy}
                className={`admin-subpanel inline-flex items-center gap-1.5 rounded-lg font-semibold text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50 dark:text-slate-200 dark:hover:bg-slate-800 ${
                    compact ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-xs'
                }`}
            >
                <RotateCcw className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} />
                {busy ? t('canonicalSync.running') : label}
            </button>
            {result && (
                <span className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    {t('canonicalSync.done', {
                        created: result.created,
                        updated: result.updated,
                        restored: result.restored,
                        unchanged: result.unchanged,
                        total: result.total_active,
                    })}
                </span>
            )}
            {error && !modalOpen && (
                <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-[11px] font-medium text-red-700 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    {error}
                </span>
            )}
            {modal && typeof document !== 'undefined' && document.body
                ? createPortal(modal, document.body)
                : modal}
        </div>
    );
}
