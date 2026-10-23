import { useState } from 'react';
import { syncCanonicalBotRules, syncCanonicalKnowledgeBase } from '@/api/crm';
import { useI18n } from '@/i18n';
import type { AdminCanonicalSyncResult } from '@/types/crm';

export type CanonicalSyncKind = 'knowledge' | 'botRules';

/**
 * Button that loads the canonical Treejar knowledge base or bot rules through
 * the admin API (after a localized confirm), shows the result counts inline and
 * lets the caller refetch its list.
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
    const [busy, setBusy] = useState(false);
    const [result, setResult] = useState<AdminCanonicalSyncResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const buttonLabel = kind === 'knowledge' ? t('sync.kbButton') : t('sync.rulesButton');
    const confirmText = kind === 'knowledge' ? t('sync.kbConfirm') : t('sync.rulesConfirm');

    async function handleClick() {
        if (!globalThis.confirm(confirmText)) return;
        setBusy(true);
        setError(null);
        try {
            const response = kind === 'knowledge'
                ? await syncCanonicalKnowledgeBase()
                : await syncCanonicalBotRules();
            setResult(response);
            await onSynced?.(response);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('common.unknownError'));
        } finally {
            setBusy(false);
        }
    }

    const buttonClass = tone === 'dark'
        ? 'inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/15 disabled:opacity-50'
        : prominent
            ? 'inline-flex items-center justify-center gap-2 rounded-md bg-[#0058be] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#004395] disabled:opacity-50'
            : 'inline-flex items-center justify-center gap-2 rounded-md border border-[#adc6ff] bg-[#eff4ff] px-3 py-2 text-sm font-medium text-[#004395] transition hover:bg-[#dfe9ff] disabled:opacity-50';

    return (
        <div className="space-y-2" data-canonical-sync={kind}>
            <button type="button" disabled={busy} onClick={() => void handleClick()} className={buttonClass}>
                {busy ? t('sync.running') : buttonLabel}
            </button>
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
