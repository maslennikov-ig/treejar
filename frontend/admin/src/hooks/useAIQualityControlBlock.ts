import { useCallback, useEffect, useMemo, useState } from 'react';
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
    loading: boolean;
    loadError: string | null;
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

export function resolveQualityControlBlockState(params: {
    config: AIQualityControlsConfig | null;
    loading: boolean;
    loadError: string | null;
    scope: AIQualityScopeKey;
    labelText: string;
    t: TranslateFn;
}): { blocked: boolean; message: string | null } {
    const { config, loading, loadError, scope, labelText, t } = params;
    if (loadError) {
        return {
            blocked: true,
            message: t('qcBlock.loadError', { detail: loadError }),
        };
    }
    if (!config) {
        return {
            blocked: true,
            message: loading ? null : t('qcBlock.loadError', { detail: t('common.unknownError') }),
        };
    }
    const message = qualityControlBlockMessage(config[scope], labelText, t);
    return {
        blocked: Boolean(message),
        message,
    };
}

export function useAIQualityControlBlock(
    scope: AIQualityScopeKey,
    labelText: string,
): QualityControlBlock {
    const { t } = useI18n();
    const [config, setConfig] = useState<AIQualityControlsConfig | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [version, setVersion] = useState(0);

    useEffect(() => {
        let mounted = true;
        setLoading(true);
        setLoadError(null);
        fetchAIQualityControls()
            .then((response) => {
                if (!mounted) return;
                setConfig(response.config);
                setLoadError(null);
            })
            .catch((err) => {
                if (!mounted) return;
                setConfig(null);
                setLoadError(err instanceof Error ? err.message : t('common.unknownError'));
            })
            .finally(() => {
                if (mounted) setLoading(false);
            });
        return () => {
            mounted = false;
        };
    }, [version, t]);

    const reload = useCallback(() => setVersion((current) => current + 1), []);
    const { blocked, message } = useMemo(
        () =>
            resolveQualityControlBlockState({
                config,
                loading,
                loadError,
                scope,
                labelText,
                t,
            }),
        [config, loading, loadError, scope, labelText, t],
    );

    return useMemo(
        () => ({
            blocked,
            loading,
            loadError,
            message,
            reason: message,
            config,
            scope,
            reload,
            refresh: reload,
        }),
        [blocked, loading, loadError, message, config, scope, reload],
    );
}
