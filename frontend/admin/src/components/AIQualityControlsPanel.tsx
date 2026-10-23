import { useCallback, useEffect, useState, type ChangeEvent, type ReactNode } from 'react';
import {
    AlertTriangle,
    Bot,
    CheckCircle2,
    Gauge,
    RefreshCw,
    Save,
    ShieldAlert,
    SlidersHorizontal,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
    fetchAIQualityControls,
    updateAIQualityControls,
} from '@/api/operators';
import EnableManualModeButton, { scopesNeedingManualMode } from '@/components/EnableManualModeButton';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type { TranslationKey } from '@/i18n';
import type {
    AIQualityControlsConfig,
    AIQualityControlsResponse,
    AIQualityControlsUpdate,
    AIQualityMode,
    AIQualityScopeConfig,
    AIQualityScopeKey,
    AIQualityTranscriptMode,
} from '@/types/operators';

type MessageTone = 'success' | 'error' | 'info';

const MODE_OPTIONS: { value: AIQualityMode; labelKey: TranslationKey }[] = [
    { value: 'disabled', labelKey: 'aiqc.mode.disabled' },
    { value: 'manual', labelKey: 'aiqc.mode.manual' },
    { value: 'daily_sample', labelKey: 'aiqc.mode.daily_sample' },
    { value: 'scheduled', labelKey: 'aiqc.mode.scheduled' },
];

const TRANSCRIPT_OPTIONS: { value: AIQualityTranscriptMode; labelKey: TranslationKey }[] = [
    { value: 'disabled', labelKey: 'aiqc.transcript.disabled' },
    { value: 'summary', labelKey: 'aiqc.transcript.summary' },
    { value: 'full', labelKey: 'aiqc.transcript.full' },
];

/** Canonical criteria order per scope (backend backfills these defaults). */
export const DEFAULT_CRITERIA_ORDER: Record<AIQualityScopeKey, string[]> = {
    bot_qa: [
        'greeting_and_identity',
        'need_discovery_and_catalog',
        'commercial_vat_and_quotation',
        'tone_and_language',
    ],
    manager_qa: [
        'response_speed_sla',
        'handover_context_usage',
        'professional_tone',
        'commercial_terms_accuracy',
        'closing_and_crm_hygiene',
    ],
    red_flags: [
        'missing_identity',
        'hard_deflection',
        'unverified_commitment',
        'ignored_question',
        'bad_tone',
    ],
};

const SCOPE_META: {
    key: AIQualityScopeKey;
    labelKey: TranslationKey;
    shortLabelKey: TranslationKey;
    descriptionKey: TranslationKey;
    icon: LucideIcon;
    accentClass: string;
    badgeClass: string;
}[] = [
    {
        key: 'bot_qa',
        labelKey: 'aiqc.scope.bot_qa',
        shortLabelKey: 'aiqc.scope.bot_qa',
        descriptionKey: 'aiqc.scope.bot_qa.description',
        icon: Bot,
        accentClass: 'text-[#009668]',
        badgeClass: 'bg-emerald-500/10 text-[#009668]',
    },
    {
        key: 'manager_qa',
        labelKey: 'aiqc.scope.manager_qa',
        shortLabelKey: 'aiqc.scope.manager_qa',
        descriptionKey: 'aiqc.scope.manager_qa.description',
        icon: CheckCircle2,
        accentClass: 'text-[#0058be]',
        badgeClass: 'bg-blue-500/10 text-[#0058be]',
    },
    {
        key: 'red_flags',
        labelKey: 'aiqc.scope.red_flags',
        shortLabelKey: 'aiqc.scope.red_flags.short',
        descriptionKey: 'aiqc.scope.red_flags.description',
        icon: ShieldAlert,
        accentClass: 'text-[#92400e]',
        badgeClass: 'bg-amber-500/10 text-[#92400e]',
    },
];

interface AIQualityControlsPanelProps {
    initialControls?: AIQualityControlsResponse | null;
}

function messageClasses(tone: MessageTone): string {
    switch (tone) {
        case 'success':
            return 'border-emerald-500/20 bg-emerald-500/10 text-[#009668]';
        case 'error':
            return 'border-red-500/20 bg-red-500/10 text-[#be123c]';
        default:
            return 'border-amber-500/20 bg-amber-500/10 text-[#92400e]';
    }
}

function formatBudget(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`;
}

export function formatCriteriaLabel(key: string): string {
    return key
        .replace(/[_-]+/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isGlm5Model(model: string): boolean {
    const normalized = model.toLowerCase();
    return normalized.includes('glm-5') || normalized.includes('glm5');
}

function orderedCriteria(scope: AIQualityScopeKey, criteria: Record<string, boolean>): [string, boolean][] {
    const known = DEFAULT_CRITERIA_ORDER[scope].filter((key) => key in criteria);
    const extra = Object.keys(criteria)
        .filter((key) => !DEFAULT_CRITERIA_ORDER[scope].includes(key))
        .sort((left, right) => left.localeCompare(right));
    return [...known, ...extra].map((key) => [key, criteria[key]]);
}

function automationLabelKey(scopeConfig: AIQualityScopeConfig): TranslationKey {
    switch (scopeConfig.mode) {
        case 'disabled':
            return 'aiqc.automation.disabled';
        case 'manual':
            return 'aiqc.automation.manual';
        case 'daily_sample':
            return 'aiqc.automation.daily_sample';
        case 'scheduled':
            return 'aiqc.automation.scheduled';
    }
}

function automationBadgeClass(scopeConfig: AIQualityScopeConfig): string {
    switch (scopeConfig.mode) {
        case 'disabled':
            return 'bg-emerald-500/10 text-[#009668]';
        case 'manual':
            return 'bg-blue-500/10 text-[#0058be]';
        case 'daily_sample':
            return 'bg-amber-500/10 text-[#92400e]';
        case 'scheduled':
            return 'bg-red-500/10 text-[#be123c]';
    }
}

function TooltippedLabel({
    children,
    tooltip,
}: {
    children: ReactNode;
    tooltip: string;
}) {
    return (
        <span className="inline-flex items-center gap-1.5">
            {children}
            <HelpTooltip text={tooltip} />
        </span>
    );
}

function baseInputClass(): string {
    return 'mt-2 w-full rounded-md border border-[#c6c6cd] bg-white px-3 py-2 text-sm text-[#0b1c30] outline-none transition focus:border-emerald-400/60 disabled:opacity-50';
}

function scopeFieldId(scope: AIQualityScopeKey, field: string): string {
    return `ai-quality-${scope}-${field}`;
}

function cloneConfig(config: AIQualityControlsConfig): AIQualityControlsConfig {
    return {
        bot_qa: {
            ...config.bot_qa,
            retry: { ...config.bot_qa.retry },
            criteria: { ...config.bot_qa.criteria },
        },
        manager_qa: {
            ...config.manager_qa,
            retry: { ...config.manager_qa.retry },
            criteria: { ...config.manager_qa.criteria },
        },
        red_flags: {
            ...config.red_flags,
            retry: { ...config.red_flags.retry },
            criteria: { ...config.red_flags.criteria },
        },
    };
}

export default function AIQualityControlsPanel({
    initialControls = null,
}: AIQualityControlsPanelProps) {
    const { t, tx } = useI18n();
    const [controls, setControls] = useState<AIQualityControlsResponse | null>(initialControls);
    const [draft, setDraft] = useState<AIQualityControlsConfig | null>(
        initialControls ? cloneConfig(initialControls.config) : null,
    );
    const [loading, setLoading] = useState(initialControls === null);
    const [savingScope, setSavingScope] = useState<AIQualityScopeKey | null>(null);
    const [message, setMessage] = useState<{ tone: MessageTone; text: string } | null>(null);

    const scopeName = useCallback(
        (scope: AIQualityScopeKey): string => {
            const meta = SCOPE_META.find((item) => item.key === scope);
            return meta ? t(meta.shortLabelKey) : scope;
        },
        [t],
    );

    const loadControls = useCallback(async () => {
        setLoading(true);
        setMessage(null);
        try {
            const response = await fetchAIQualityControls();
            setControls(response);
            setDraft(cloneConfig(response.config));
        } catch (err) {
            setMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('aiqc.loadFailed'),
            });
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        if (initialControls) {
            setControls(initialControls);
            setDraft(cloneConfig(initialControls.config));
            setLoading(false);
            return;
        }

        void loadControls();
    }, [initialControls, loadControls]);

    function applyResponse(response: AIQualityControlsResponse): void {
        setControls(response);
        setDraft(cloneConfig(response.config));
    }

    function updateDraftScope(
        scope: AIQualityScopeKey,
        updater: (current: AIQualityScopeConfig) => AIQualityScopeConfig,
    ): void {
        setDraft((current) => {
            if (!current) {
                return current;
            }
            return {
                ...current,
                [scope]: updater(current[scope]),
            };
        });
    }

    function handleModeChange(scope: AIQualityScopeKey, value: AIQualityMode): void {
        updateDraftScope(scope, (current) => ({
            ...current,
            mode: value,
        }));
    }

    function handleTranscriptChange(
        scope: AIQualityScopeKey,
        value: AIQualityTranscriptMode,
    ): void {
        updateDraftScope(scope, (current) => ({
            ...current,
            transcript_mode: value,
            full_transcript_warning_override:
                value === 'full' ? current.full_transcript_warning_override : false,
        }));
    }

    function handleModelChange(scope: AIQualityScopeKey, value: string): void {
        updateDraftScope(scope, (current) => ({
            ...current,
            model: value,
            glm5_warning_override: isGlm5Model(value) ? current.glm5_warning_override : false,
        }));
    }

    function handleNumberChange(
        scope: AIQualityScopeKey,
        field: 'daily_budget_cents' | 'max_calls_per_run' | 'max_calls_per_day',
        event: ChangeEvent<HTMLInputElement>,
    ): void {
        const value = Number(event.target.value);
        updateDraftScope(scope, (current) => ({
            ...current,
            [field]: Number.isFinite(value) ? value : 0,
        }));
    }

    function handleRetryChange(
        scope: AIQualityScopeKey,
        field: 'max_attempts' | 'backoff_seconds',
        event: ChangeEvent<HTMLInputElement>,
    ): void {
        const value = Number(event.target.value);
        updateDraftScope(scope, (current) => ({
            ...current,
            retry: {
                ...current.retry,
                [field]: Number.isFinite(value) ? value : 0,
            },
        }));
    }

    function handleBooleanChange(
        scope: AIQualityScopeKey,
        field: 'cache_telemetry_enabled' | 'alert_on_failure' | 'full_transcript_warning_override' | 'glm5_warning_override',
        checked: boolean,
    ): void {
        updateDraftScope(scope, (current) => ({
            ...current,
            [field]: checked,
        }));
    }

    function handleCriteriaChange(
        scope: AIQualityScopeKey,
        criterion: string,
        checked: boolean,
    ): void {
        updateDraftScope(scope, (current) => ({
            ...current,
            criteria: {
                ...current.criteria,
                [criterion]: checked,
            },
        }));
    }

    async function handleSaveScope(scope: AIQualityScopeKey): Promise<void> {
        if (!draft) {
            return;
        }

        setSavingScope(scope);
        setMessage(null);
        try {
            const payload: AIQualityControlsUpdate = {
                [scope]: draft[scope],
            };
            const response = await updateAIQualityControls(payload);
            applyResponse(response);
            setMessage({
                tone: 'success',
                text: t('aiqc.saved', { scope: scopeName(scope) }),
            });
        } catch (err) {
            setMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : t('aiqc.saveFailed', { scope: scopeName(scope) }),
            });
        } finally {
            setSavingScope(null);
        }
    }

    function usageLine(scope: AIQualityScopeKey): string | null {
        const usage = controls?.usage_today?.[scope];
        if (!usage) return null;
        const na = t('aiqc.na');
        return t('aiqc.usageLine', {
            calls: usage.calls_today === null ? na : String(usage.calls_today),
            maxCalls: String(usage.max_calls_per_day),
            spend: usage.spend_cents_today === null ? na : formatBudget(usage.spend_cents_today),
            budget: formatBudget(usage.daily_budget_cents),
        });
    }

    const effectiveConfig = draft ?? controls?.config ?? null;
    const allAutomationDisabled = effectiveConfig
        ? SCOPE_META.every((item) => effectiveConfig[item.key].mode === 'disabled')
        : false;
    const savedConfig = controls?.config ?? null;
    const hasDisabledScopes = scopesNeedingManualMode(savedConfig).length > 0;

    return (
        <section className="rounded-md border border-[#e5eeff] bg-white p-5 xl:col-span-2" data-ai-quality-controls="">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2 text-[#0b1c30]">
                        <SlidersHorizontal size={18} className="text-[#009668]" />
                        <h3 className="text-lg font-semibold">{t('aiqc.title')}</h3>
                        <HelpTooltip text={t('aiqc.titleHelp')} />
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-[#45464d]">
                        {t('aiqc.subtitle')}
                    </p>
                </div>
                <div className="flex flex-wrap items-start gap-2">
                    {hasDisabledScopes && (
                        <EnableManualModeButton
                            config={savedConfig}
                            onDone={(response) => {
                                applyResponse(response);
                                setMessage({ tone: 'success', text: t('aiqc.manualEnabled') });
                            }}
                        />
                    )}
                    <button
                        type="button"
                        onClick={() => void loadControls()}
                        disabled={loading || savingScope !== null}
                        className="inline-flex items-center justify-center gap-2 rounded-md border border-[#c6c6cd] bg-white px-4 py-2 text-sm font-medium text-[#3f465c] transition hover:bg-[#f2f4f7] disabled:opacity-50"
                    >
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                        {t('aiqc.reload')}
                    </button>
                </div>
            </div>

            {loading && (
                <div className="mt-5 rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-4 py-4 text-sm text-[#45464d]">
                    {t('aiqc.loading')}
                </div>
            )}

            {effectiveConfig && allAutomationDisabled && (
                <div className="mt-5 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-4 py-4 text-sm text-[#166534]">
                    <div className="flex items-start gap-3">
                        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-[#009668]" />
                        <div>
                            <p className="font-medium text-[#166534]">{t('aiqc.zeroTitle')}</p>
                            <p className="mt-1 text-[#166534]">
                                {t('aiqc.zeroBody')}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {controls && controls.warnings.length > 0 && (
                <div className="mt-5 space-y-2">
                    {controls.warnings.map((warning) => (
                        <div
                            key={`${warning.scope}-${warning.code}`}
                            className="rounded-md border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-[#92400e]"
                        >
                            <AlertTriangle size={16} className="mr-2 inline text-[#92400e]" />
                            <span className="font-medium">{scopeName(warning.scope)}:</span>{' '}
                            {tx(`aiqc.warning.${warning.code}`, warning.message)}
                        </div>
                    ))}
                </div>
            )}

            {message && (
                <div className={`mt-5 rounded-md border px-4 py-3 text-sm ${messageClasses(message.tone)}`}>
                    {message.text}
                </div>
            )}

            {effectiveConfig && (
                <>
                    <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
                        {SCOPE_META.map((meta) => {
                            const scopeConfig = effectiveConfig[meta.key];
                            const Icon = meta.icon;
                            const criteriaEntries = orderedCriteria(meta.key, scopeConfig.criteria);
                            const showFullTranscriptWarning = scopeConfig.transcript_mode === 'full';
                            const showGlmWarning = isGlm5Model(scopeConfig.model);
                            const usage = usageLine(meta.key);

                            return (
                                <div key={meta.key} className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4" data-ai-quality-scope={meta.key}>
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <div className="flex items-center gap-2 text-[#0b1c30]">
                                                <Icon size={17} className={meta.accentClass} />
                                                <h4 className="text-base font-semibold">{t(meta.labelKey)}</h4>
                                            </div>
                                            <p className="mt-2 text-sm text-[#45464d]">{t(meta.descriptionKey)}</p>
                                        </div>
                                        <span className={`rounded-md px-3 py-2 text-xs font-medium ${automationBadgeClass(scopeConfig)}`}>
                                            {t(automationLabelKey(scopeConfig))}
                                        </span>
                                    </div>

                                    {usage && (
                                        <p className="mt-3 rounded-md border border-[#e5eeff] bg-white px-3 py-2 text-xs text-[#3f465c]" data-ai-quality-usage={meta.key}>
                                            {usage}
                                        </p>
                                    )}

                                    <div className="mt-4 grid grid-cols-1 gap-3">
                                        <label htmlFor={scopeFieldId(meta.key, 'mode')} className="text-sm font-medium text-[#3f465c]">
                                            <TooltippedLabel tooltip={t('aiqc.help.mode')}>{t('aiqc.field.mode')}</TooltippedLabel>
                                            <select
                                                id={scopeFieldId(meta.key, 'mode')}
                                                value={scopeConfig.mode}
                                                onChange={(event) => handleModeChange(meta.key, event.target.value as AIQualityMode)}
                                                className={baseInputClass()}
                                            >
                                                {MODE_OPTIONS.map((option) => (
                                                    <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
                                                ))}
                                            </select>
                                        </label>

                                        <label htmlFor={scopeFieldId(meta.key, 'transcript')} className="text-sm font-medium text-[#3f465c]">
                                            <TooltippedLabel tooltip={t('aiqc.help.transcript')}>{t('aiqc.field.transcript')}</TooltippedLabel>
                                            <select
                                                id={scopeFieldId(meta.key, 'transcript')}
                                                value={scopeConfig.transcript_mode}
                                                onChange={(event) => handleTranscriptChange(meta.key, event.target.value as AIQualityTranscriptMode)}
                                                className={baseInputClass()}
                                            >
                                                {TRANSCRIPT_OPTIONS.map((option) => (
                                                    <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
                                                ))}
                                            </select>
                                        </label>

                                        {showFullTranscriptWarning && (
                                            <label className="rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-3 text-sm text-[#92400e]">
                                                <span className="flex items-start gap-2">
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.full_transcript_warning_override}
                                                        onChange={(event) => handleBooleanChange(meta.key, 'full_transcript_warning_override', event.target.checked)}
                                                        className="mt-1"
                                                    />
                                                    <span>
                                                        <span className="font-medium">{t('aiqc.fullOverrideTitle')}</span>
                                                        <span className="mt-1 block text-[#92400e]">
                                                            {t('aiqc.fullOverrideBody')}
                                                        </span>
                                                    </span>
                                                </span>
                                            </label>
                                        )}

                                        <label htmlFor={scopeFieldId(meta.key, 'model')} className="text-sm font-medium text-[#3f465c]">
                                            <TooltippedLabel tooltip={t('aiqc.help.model')}>{t('aiqc.field.model')}</TooltippedLabel>
                                            <input
                                                id={scopeFieldId(meta.key, 'model')}
                                                type="text"
                                                value={scopeConfig.model}
                                                onChange={(event) => handleModelChange(meta.key, event.target.value)}
                                                className={baseInputClass()}
                                            />
                                        </label>

                                        {showGlmWarning && (
                                            <label className="rounded-md border border-red-500/20 bg-red-500/10 px-3 py-3 text-sm text-[#be123c]">
                                                <span className="flex items-start gap-2">
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.glm5_warning_override}
                                                        onChange={(event) => handleBooleanChange(meta.key, 'glm5_warning_override', event.target.checked)}
                                                        className="mt-1"
                                                    />
                                                    <span>
                                                        <span className="font-medium">{t('aiqc.glmOverrideTitle')}</span>
                                                        <span className="mt-1 block text-[#be123c]">
                                                            {t('aiqc.glmOverrideBody')}
                                                        </span>
                                                    </span>
                                                </span>
                                            </label>
                                        )}

                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                                            <label htmlFor={scopeFieldId(meta.key, 'budget')} className="text-sm font-medium text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.budget')}>{t('aiqc.field.budget')}</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'budget')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.daily_budget_cents}
                                                    onChange={(event) => handleNumberChange(meta.key, 'daily_budget_cents', event)}
                                                    className={baseInputClass()}
                                                />
                                                <span className="mt-1 block text-xs text-[#7c839b]">{formatBudget(scopeConfig.daily_budget_cents)}</span>
                                            </label>

                                            <label htmlFor={scopeFieldId(meta.key, 'per-run')} className="text-sm font-medium text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.callCap')}>{t('aiqc.field.perRun')}</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'per-run')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.max_calls_per_run}
                                                    onChange={(event) => handleNumberChange(meta.key, 'max_calls_per_run', event)}
                                                    className={baseInputClass()}
                                                />
                                            </label>

                                            <label htmlFor={scopeFieldId(meta.key, 'per-day')} className="text-sm font-medium text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.callCap')}>{t('aiqc.field.perDay')}</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'per-day')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.max_calls_per_day}
                                                    onChange={(event) => handleNumberChange(meta.key, 'max_calls_per_day', event)}
                                                    className={baseInputClass()}
                                                />
                                            </label>
                                        </div>

                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                            <label htmlFor={scopeFieldId(meta.key, 'retry-attempts')} className="text-sm font-medium text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.retry')}>{t('aiqc.field.retryAttempts')}</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'retry-attempts')}
                                                    type="number"
                                                    min={1}
                                                    max={2}
                                                    value={scopeConfig.retry.max_attempts}
                                                    onChange={(event) => handleRetryChange(meta.key, 'max_attempts', event)}
                                                    className={baseInputClass()}
                                                />
                                            </label>

                                            <label htmlFor={scopeFieldId(meta.key, 'retry-backoff')} className="text-sm font-medium text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.retry')}>{t('aiqc.field.backoff')}</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'retry-backoff')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.retry.backoff_seconds}
                                                    onChange={(event) => handleRetryChange(meta.key, 'backoff_seconds', event)}
                                                    className={baseInputClass()}
                                                />
                                            </label>
                                        </div>

                                        <div className="grid grid-cols-1 gap-2">
                                            <label className="flex items-center justify-between gap-3 rounded-md border border-[#e5eeff] bg-white px-3 py-3 text-sm text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.cache')}>{t('aiqc.field.cache')}</TooltippedLabel>
                                                <input
                                                    type="checkbox"
                                                    checked={scopeConfig.cache_telemetry_enabled}
                                                    onChange={(event) => handleBooleanChange(meta.key, 'cache_telemetry_enabled', event.target.checked)}
                                                />
                                            </label>

                                            <label className="flex items-center justify-between gap-3 rounded-md border border-[#e5eeff] bg-white px-3 py-3 text-sm text-[#3f465c]">
                                                <TooltippedLabel tooltip={t('aiqc.help.alert')}>{t('aiqc.field.alert')}</TooltippedLabel>
                                                <input
                                                    type="checkbox"
                                                    checked={scopeConfig.alert_on_failure}
                                                    onChange={(event) => handleBooleanChange(meta.key, 'alert_on_failure', event.target.checked)}
                                                />
                                            </label>
                                        </div>

                                        <div className="rounded-md border border-[#e5eeff] bg-[#f8f9ff] px-3 py-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <p className="flex items-center gap-1.5 text-sm font-medium text-[#0b1c30]">
                                                    {t('aiqc.criteriaTitle')}
                                                    <HelpTooltip text={t(`aiqc.criteriaHelp.${meta.key}` as TranslationKey)} />
                                                </p>
                                                <span className={`rounded-lg px-2.5 py-1 text-xs font-medium ${meta.badgeClass}`}>
                                                    {criteriaEntries.filter(([, enabled]) => enabled).length}/{criteriaEntries.length}
                                                </span>
                                            </div>
                                            <div className="mt-3 space-y-2">
                                                {criteriaEntries.length > 0 ? criteriaEntries.map(([criterion, enabled]) => {
                                                    const help = tx(`crit.${meta.key}.${criterion}.help`, '');
                                                    return (
                                                        <label
                                                            key={criterion}
                                                            data-criterion={criterion}
                                                            className="flex items-center justify-between gap-3 rounded-lg border border-[#e5eeff] bg-white px-3 py-2 text-sm text-[#3f465c]"
                                                        >
                                                            <span className="inline-flex items-center gap-1.5">
                                                                <span>{tx(`crit.${meta.key}.${criterion}`, formatCriteriaLabel(criterion))}</span>
                                                                {help && <HelpTooltip text={help} />}
                                                            </span>
                                                            <input
                                                                type="checkbox"
                                                                checked={enabled}
                                                                onChange={(event) => handleCriteriaChange(meta.key, criterion, event.target.checked)}
                                                            />
                                                        </label>
                                                    );
                                                }) : (
                                                    <div className="rounded-lg border border-dashed border-[#c6c6cd] px-3 py-4 text-sm text-[#7c839b]">
                                                        {t('aiqc.noCriteria')}
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <button
                                            type="button"
                                            onClick={() => void handleSaveScope(meta.key)}
                                            disabled={savingScope !== null}
                                            className="inline-flex items-center justify-center gap-2 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-[#166534] transition hover:bg-emerald-500/15 disabled:opacity-50"
                                        >
                                            {savingScope === meta.key ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
                                            {t('aiqc.saveScope', { scope: t(meta.shortLabelKey) })}
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="mt-5 rounded-md border border-[#e5eeff] bg-[#f8f9ff] p-4" data-ai-quality-contours="">
                        <div className="flex items-center gap-2 text-[#0b1c30]">
                            <Gauge size={17} className="text-[#0058be]" />
                            <h4 className="text-base font-semibold">{t('aiqc.contoursTitle')}</h4>
                        </div>
                        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
                            <div className="rounded-md border border-[#e5eeff] bg-white px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-[#0b1c30]">
                                    <Bot size={15} className="text-[#009668]" />
                                    {t('aiqc.scope.bot_qa')}
                                </div>
                                <p className="mt-2 text-sm text-[#45464d]">{t('aiqc.contour.bot_qa')}</p>
                            </div>
                            <div className="rounded-md border border-[#e5eeff] bg-white px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-[#0b1c30]">
                                    <CheckCircle2 size={15} className="text-[#0058be]" />
                                    {t('aiqc.scope.manager_qa')}
                                </div>
                                <p className="mt-2 text-sm text-[#45464d]">{t('aiqc.contour.manager_qa')}</p>
                            </div>
                            <div className="rounded-md border border-[#e5eeff] bg-white px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-[#0b1c30]">
                                    <AlertTriangle size={15} className="text-[#92400e]" />
                                    {t('aiqc.scope.red_flags')}
                                </div>
                                <p className="mt-2 text-sm text-[#45464d]">{t('aiqc.contour.red_flags')}</p>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </section>
    );
}
