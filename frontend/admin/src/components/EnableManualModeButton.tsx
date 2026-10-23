import { useState } from 'react';
import { updateAIQualityControls } from '@/api/operators';
import { useI18n } from '@/i18n';
import type {
    AIQualityControlsConfig,
    AIQualityControlsResponse,
    AIQualityControlsUpdate,
    AIQualityScopeKey,
} from '@/types/operators';

export const AI_QUALITY_SCOPES: AIQualityScopeKey[] = ['bot_qa', 'manager_qa', 'red_flags'];

/** Scopes that are currently `disabled` and would move to `manual`. */
export function scopesNeedingManualMode(config: AIQualityControlsConfig | null | undefined): AIQualityScopeKey[] {
    if (!config) return [];
    return AI_QUALITY_SCOPES.filter((scope) => config[scope]?.mode === 'disabled');
}

/**
 * PATCH payload that switches only disabled scopes to manual mode; scheduled and
 * daily-sample scopes keep their mode.
 */
export function buildEnableManualModePayload(
    config: AIQualityControlsConfig | null | undefined,
): AIQualityControlsUpdate {
    const payload: AIQualityControlsUpdate = {};
    for (const scope of scopesNeedingManualMode(config)) {
        payload[scope] = { mode: 'manual' };
    }
    return payload;
}

export default function EnableManualModeButton({
    config,
    onDone,
    tone = 'light',
}: {
    config: AIQualityControlsConfig | null | undefined;
    onDone?: (response: AIQualityControlsResponse) => void;
    tone?: 'light' | 'dark';
}) {
    const { t } = useI18n();
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const pending = scopesNeedingManualMode(config);

    if (pending.length === 0) return null;

    async function handleClick() {
        setBusy(true);
        setError(null);
        try {
            const response = await updateAIQualityControls(buildEnableManualModePayload(config));
            onDone?.(response);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('common.unknownError'));
        } finally {
            setBusy(false);
        }
    }

    return (
        <span className="inline-flex flex-col gap-1" data-enable-manual-mode="">
            <button
                type="button"
                disabled={busy}
                onClick={() => void handleClick()}
                className={
                    tone === 'dark'
                        ? 'inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/15 px-3 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/25 disabled:opacity-50'
                        : 'inline-flex items-center justify-center gap-2 rounded-md bg-[#0058be] px-3 py-2 text-sm font-medium text-white transition hover:bg-[#004395] disabled:opacity-50'
                }
            >
                {busy ? t('aiqc.enablingManual') : t('aiqc.enableManualAll')}
            </button>
            {error && <span className="text-xs text-[#be123c]">{error}</span>}
        </span>
    );
}
