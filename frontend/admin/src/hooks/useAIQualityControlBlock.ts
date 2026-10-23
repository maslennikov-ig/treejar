import { useCallback, useEffect, useState } from 'react';
import { fetchAIQualityControls } from '@/api/operators';
import { useI18n } from '@/i18n';
import type { TranslateFn } from '@/i18n';
import type {
    AIQualityControlsConfig,
    AIQualityScopeConfig,
    AIQualityScopeKey,
} from '@/types/operators';

export interface QualityControlBlock {
    blocked: boolean;
    message: string | null;
    reason: string | null;
    config: AIQualityControlsConfig | null;
    scope: AIQualityScopeKey;
    reload: () => void;
    refresh: () => void;
}

export function qualityControlBlockMessage(
    scopeConfig: AIQualityScopeConfig,
    labelText: string,
    t: TranslateFn,
): string | null {
    if (scopeConfig.mode === 'disabled') {
        return t('qcBlock.disabled', { label: labelText });
    }
    if (scopeConfig.daily_budget_cents <= 0) {
        return t('qcBlock.zeroBudget', { label: labelText });
    }
    if (scopeConfig.max_calls_per_run <= 0) {
        return t('qcBlock.zeroPerRun', { label: labelText });
    }
    if (scopeConfig.max_calls_per_day <= 0) {
        return t('qcBlock.zeroPerDay', { label: labelText });
    }
    return null;
}

/** Maps backend manual-run gate reasons to a localized hint. */
export function localizeQualityGateError(message: string, t: TranslateFn): string {
    if (message.includes('daily_budget_exhausted')) {
        return `${message} ${t('qcBlock.budgetExhausted')}`;
    }
    if (message.includes('daily_call_quota_exhausted')) {
        return `${message} ${t('qcBlock.quotaExhausted')}`;
    }
    return message;
}

export function useAIQualityControlBlock(
    scope: AIQualityScopeKey,
    labelText: string,
): QualityControlBlock {
    const { t } = useI18n();
    const [config, setConfig] = useState<AIQualityControlsConfig | null>(null);
    const [version, setVersion] = useState(0);

    useEffect(() => {
        let mounted = true;
        fetchAIQualityControls()
            .then((response) => {
                if (mounted) setConfig(response.config);
            })
            .catch(() => {
                if (mounted) setConfig(null);
            });
        return () => {
            mounted = false;
        };
    }, [version]);

    const reload = useCallback(() => setVersion((current) => current + 1), []);
    const message = config ? qualityControlBlockMessage(config[scope], labelText, t) : null;
    return {
        blocked: Boolean(message),
        message,
        reason: message,
        config,
        scope,
        reload,
        refresh: reload,
    };
}
