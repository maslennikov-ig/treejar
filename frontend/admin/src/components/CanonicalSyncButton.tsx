import { useEffect, useState } from 'react';
import { syncCanonicalBotRules, syncCanonicalKnowledgeBase } from '@/api/crm';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { AdminCanonicalSyncResult } from '@/types/crm';

export type CanonicalSyncKind = 'knowledge' | 'botRules';

const inFlightByKind: Partial<Record<CanonicalSyncKind, Promise<AdminCanonicalSyncResult>>> = {};
const lastResultByKind: Partial<Record<CanonicalSyncKind, AdminCanonicalSyncResult>> = {};
const lastErrorByKind: Partial<Record<CanonicalSyncKind, string>> = {};
const listeners = new Set<() => void>();

function notifyListeners() {
    for (const listener of listeners) {
        listener();
    }
}

export async function runCanonicalSync(kind: CanonicalSyncKind): Promise<AdminCanonicalSyncResult> {
    const existing = inFlightByKind[kind];
    if (existing) {
        return existing;
    }
    delete lastErrorByKind[kind];
    const promise = (kind === 'knowledge' ? syncCanonicalKnowledgeBase() : syncCanonicalBotRules())
        .then((response) => {
            lastResultByKind[kind] = response;
            delete inFlightByKind[kind];
            notifyListeners();
            return response;
        })
        .catch((err) => {
            lastErrorByKind[kind] = err instanceof Error ? err.message : String(err);
            delete inFlightByKind[kind];
            notifyListeners();
            throw err;
        });
    inFlightByKind[kind] = promise;
    notifyListeners();
    return promise;
}

/**
 * Button that loads the canonical Treejar knowledge base or bot rules through
 * the admin API (after a localized confirm), persists in-flight/result state
 * across tab switches, shows the result counts inline and lets the caller
 * refetch its list.
 */
export default function CanonicalSyncButton({
    kind,
    onSynced,
    prominent = false,
    tone = 'light',
}: {
    kind: CanonicalSyncKind;
    onSynced?: (result: AdminCanonicalSyncResult) => void | Promise<void>;
    prominent?: boolean;
    tone?: 'light' | 'dark';
}) {
    const { t } = useI18n();
    const [, setTick] = useState(0);
    const busy = Boolean(inFlightByKind[kind]);
    const result = lastResultByKind[kind] ?? null;
    const error = lastErrorByKind[kind] ?? null;

    useEffect(() => {
        const listener = () => setTick((count) => count + 1);
        listeners.add(listener);
        const activePromise = inFlightByKind[kind];
        if (activePromise && onSynced) {
            void activePromise.then((res) => onSynced(res)).catch(() => undefined);
        }
        return () => {
            listeners.delete(listener);
        };
    }, [kind, onSynced]);

    const buttonLabel = kind === 'knowledge' ? t('sync.kbButton') : t('sync.rulesButton');
    const helpText = kind === 'knowledge' ? t('sync.kbHelp') : t('sync.rulesHelp');
    const confirmText = kind === 'knowledge' ? t('sync.kbConfirm') : t('sync.rulesConfirm');

    async function handleClick() {
        if (!globalThis.confirm(confirmText)) return;
        try {
            const response = await runCanonicalSync(kind);
            await onSynced?.(response);
        } catch {
            // Error is stored in lastErrorByKind[kind] and rendered below.
        }
    }

    const buttonClass = tone === 'dark'
        ? 'inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/15 disabled:opacity-50'
        : prominent
            ? 'inline-flex items-center justify-center gap-2 rounded-md bg-[#0058be] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#004395] disabled:opacity-50'
            : 'inline-flex items-center justify-center gap-2 rounded-md border border-[#adc6ff] bg-[#eff4ff] px-3 py-2 text-sm font-medium text-[#004395] transition hover:bg-[#dfe9ff] disabled:opacity-50';

    return (
        <div className="space-y-2" data-canonical-sync={kind}>
            <div className="inline-flex items-center gap-1.5">
                <button type="button" disabled={busy} onClick={() => void handleClick()} className={buttonClass}>
                    {busy ? t('sync.running') : buttonLabel}
                </button>
                <HelpTooltip text={helpText} tone={tone} />
            </div>
            {result && (
                <p
                    className={tone === 'dark' ? 'text-xs text-emerald-200' : 'text-xs leading-5 text-[#166534]'}
                    data-canonical-sync-result=""
                >
                    {t('sync.result', {
                        created: result.created,
                        updated: result.updated,
                        restored: result.restored,
                        unchanged: result.unchanged,
                        total: result.total_active,
                    })}
                    {result.detail ? ` ${result.detail}` : ''}
                </p>
            )}
            {error && <p className="text-xs text-[#be123c]">{error}</p>}
        </div>
    );
}
