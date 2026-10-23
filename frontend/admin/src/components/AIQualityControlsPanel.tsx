import { useCallback, useEffect, useState } from 'react';
import {
    AlertTriangle,
    Bot,
    CheckCircle2,
    DollarSign,
    Gauge,
    RefreshCw,
    Save,
    ShieldAlert,
    SlidersHorizontal,
} from 'lucide-react';
import {
    fetchAIQualityControls,
    updateAIQualityControls,
} from '@/api/operators';
import EnableManualModeButton from '@/components/EnableManualModeButton';
import { HelpTooltip } from '@/components/HelpTooltip';
import { useI18n } from '@/i18n';
import type {
    AIQualityControlsConfig,
    AIQualityControlsResponse,
    AIQualityMode,
    AIQualityScopeConfig,
    AIQualityScopeKey as AIQualityScope,
    AIQualityScopeUsage as AIQualityScopeUsageToday,
    AIQualityTranscriptMode,
} from '@/types/operators';

const AI_QUALITY_SCOPES: AIQualityScope[] = ['bot_qa', 'manager_qa', 'red_flags'];
const AI_QUALITY_MODES: AIQualityMode[] = ['disabled', 'manual', 'daily_sample', 'scheduled'];
const AI_QUALITY_TRANSCRIPT_MODES: AIQualityTranscriptMode[] = ['disabled', 'summary', 'full'];
const AI_QUALITY_MODELS: string[] = [
    'google/gemini-3.1-flash-lite-preview',
    'openai/gpt-5.4-mini',
    'z-ai/glm5-20260211',
];

interface Props {
    initialControls?: AIQualityControlsResponse | null;
}

interface StatusMessage {
    tone: 'success' | 'error';
    text: string;
}

const DEFAULT_CRITERIA_KEYS: Record<AIQualityScope, string[]> = {
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

function formatCriterionFallback(key: string): string {
    return key
        .split('_')
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
}

function criteriaKeysFor(scope: AIQualityScope, criteria: Record<string, boolean>): string[] {
    const configured = Object.keys(criteria);
    if (configured.length === 0) {
        return DEFAULT_CRITERIA_KEYS[scope];
    }
    const defaults = DEFAULT_CRITERIA_KEYS[scope].filter((key) => key in criteria);
    const custom = configured.filter((key) => !DEFAULT_CRITERIA_KEYS[scope].includes(key)).sort();
    return [...defaults, ...custom];
}

function formatUsd(cents: number | null | undefined): string {
    if (cents === null || cents === undefined) {
        return 'n/a';
    }
    return `$${(cents / 100).toFixed(2)}`;
}

function modeBadgeClasses(mode: AIQualityMode): string {
    if (mode === 'disabled') {
        return 'border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300';
    }
    if (mode === 'manual') {
        return 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-300';
    }
    return 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300';
}

export default function AIQualityControlsPanel({ initialControls = null }: Props) {
    const { t, tx } = useI18n();
    const [controls, setControls] = useState<AIQualityControlsResponse | null>(initialControls);
    const [draft, setDraft] = useState<AIQualityControlsConfig | null>(
        initialControls ? cloneConfig(initialControls.config) : null,
    );
    const [loading, setLoading] = useState<boolean>(initialControls === null);
    const [saving, setSaving] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [status, setStatus] = useState<StatusMessage | null>(null);

    const applyResponse = useCallback((next: AIQualityControlsResponse) => {
        setControls(next);
        setDraft(cloneConfig(next.config));
    }, []);

    const loadControls = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const next = await fetchAIQualityControls();
            applyResponse(next);
        } catch (err) {
            setError(err instanceof Error ? err.message : t('aiqc.loadFailed'));
        } finally {
            setLoading(false);
        }
    }, [applyResponse, t]);

    useEffect(() => {
        if (initialControls !== null) {
            return;
        }
        void loadControls();
    }, [initialControls, loadControls]);

    const updateScope = <K extends keyof AIQualityScopeConfig>(
        scope: AIQualityScope,
        field: K,
        value: AIQualityScopeConfig[K],
    ) => {
        setDraft((current) => {
            if (!current) {
                return current;
            }
            const nextScope: AIQualityScopeConfig = {
                ...current[scope],
                [field]: value,
            };
            if (field === 'transcript_mode' && value === 'summary') {
                nextScope.full_transcript_warning_override = false;
            }
            if (field === 'model' && value !== 'z-ai/glm5-20260211' && value !== 'z-ai/glm-5') {
                nextScope.glm5_warning_override = false;
            }
            return {
                ...current,
                [scope]: nextScope,
            };
        });
    };

    const updateRetry = (
        scope: AIQualityScope,
        field: keyof AIQualityScopeConfig['retry'],
        rawValue: string,
    ) => {
        const parsed = Number.parseInt(rawValue, 10);
        const value = Number.isNaN(parsed) ? 0 : parsed;
        setDraft((current) => {
            if (!current) {
                return current;
            }
            return {
                ...current,
                [scope]: {
                    ...current[scope],
                    retry: {
                        ...current[scope].retry,
                        [field]: value,
                    },
                },
            };
        });
    };

    const updateNumberField = (
        scope: AIQualityScope,
        field: 'daily_budget_cents' | 'max_calls_per_run' | 'max_calls_per_day',
        rawValue: string,
    ) => {
        const parsed = Number.parseInt(rawValue, 10);
        updateScope(scope, field, Number.isNaN(parsed) ? 0 : parsed);
    };

    const updateUsdBudgetField = (scope: AIQualityScope, rawUsd: string) => {
        const parsed = Number.parseFloat(rawUsd);
        const cents = Number.isNaN(parsed) ? 0 : Math.max(0, Math.round(parsed * 100));
        updateScope(scope, 'daily_budget_cents', cents);
    };

    const toggleCriterion = (scope: AIQualityScope, key: string, enabled: boolean) => {
        setDraft((current) => {
            if (!current) {
                return current;
            }
            const baseCriteria: Record<string, boolean> = {};
            for (const criterionKey of criteriaKeysFor(scope, current[scope].criteria)) {
                baseCriteria[criterionKey] = current[scope].criteria[criterionKey] ?? true;
            }
            baseCriteria[key] = enabled;
            return {
                ...current,
                [scope]: {
                    ...current[scope],
                    criteria: baseCriteria,
                },
            };
        });
    };

    const handleSave = async () => {
        if (!draft) {
            return;
        }
        setSaving(true);
        setStatus(null);
        try {
            const saved = await updateAIQualityControls(draft);
            applyResponse(saved);
            setStatus({
                tone: 'success',
                text: t('aiqc.saved'),
            });
        } catch (err) {
            setStatus({
                tone: 'error',
                text: err instanceof Error ? err.message : t('aiqc.saveFailed'),
            });
        } finally {
            setSaving(false);
        }
    };

    const warnings = controls?.warnings ?? [];
    const allDisabled =
        draft !== null &&
        AI_QUALITY_SCOPES.every((scope) => draft[scope].mode === 'disabled');

    const scopeLabel = (scope: AIQualityScope): string => {
        if (scope === 'bot_qa') return t('aiqc.scope.bot_qa.label');
        if (scope === 'manager_qa') return t('aiqc.scope.manager_qa.label');
        return t('aiqc.scope.red_flags.label');
    };

    const scopeShortName = (scope: AIQualityScope): string => {
        if (scope === 'bot_qa') return t('aiqc.scope.bot_qa');
        if (scope === 'manager_qa') return t('aiqc.scope.manager_qa');
        return t('aiqc.scope.red_flags.short');
    };

    const scopeDescription = (scope: AIQualityScope): string => {
        if (scope === 'bot_qa') return t('aiqc.scope.bot_qa.desc');
        if (scope === 'manager_qa') return t('aiqc.scope.manager_qa.desc');
        return t('aiqc.scope.red_flags.desc');
    };

    const scopeDetail = (scope: AIQualityScope): string => {
        if (scope === 'bot_qa') return t('aiqc.scope.bot_qa.detail');
        if (scope === 'manager_qa') return t('aiqc.scope.manager_qa.detail');
        return t('aiqc.scope.red_flags.detail');
    };

    const modeLabel = (mode: AIQualityMode): string => tx(`aiqc.mode.${mode}`, mode);
    const transcriptLabel = (mode: AIQualityTranscriptMode): string =>
        tx(`aiqc.transcript.${mode}`, mode);

    const criterionLabel = (scope: AIQualityScope, key: string): string =>
        tx(
            `crit.${scope}.${key}`,
            tx(`crit.common.${key}`, formatCriterionFallback(key)),
        );

    const criterionHelp = (scope: AIQualityScope, key: string): string =>
        tx(`crit.${scope}.${key}.help`, '');

    const renderUsageLine = (
        scope: AIQualityScope,
        scopeConfig: AIQualityScopeConfig,
    ): string => {
        const usage: AIQualityScopeUsageToday | undefined = controls?.usage_today?.[scope];
        const na = t('aiqc.na');
        const calls =
            usage && usage.calls_today !== null && usage.calls_today !== undefined
                ? String(usage.calls_today)
                : na;
        const maxCalls = String(usage?.max_calls_per_day ?? scopeConfig.max_calls_per_day);
        const spend =
            usage && usage.spend_cents_today !== null && usage.spend_cents_today !== undefined
                ? formatUsd(usage.spend_cents_today)
                : na;
        const budget = formatUsd(usage?.daily_budget_cents ?? scopeConfig.daily_budget_cents);
        return t('aiqc.usageLine', { calls, maxCalls, spend, budget });
    };

    // Total daily budget and spend across all 3 scopes for Simple Mode Card 1
    const totalBudgetCents = draft
        ? draft.bot_qa.daily_budget_cents +
          draft.manager_qa.daily_budget_cents +
          draft.red_flags.daily_budget_cents
        : 0;
    const totalSpendCents = controls?.usage_today
        ? (controls.usage_today.bot_qa?.spend_cents_today ?? 0) +
          (controls.usage_today.manager_qa?.spend_cents_today ?? 0) +
          (controls.usage_today.red_flags?.spend_cents_today ?? 0)
        : 0;
    const budgetPct =
        totalBudgetCents > 0
            ? Math.min(100, Math.round((totalSpendCents / totalBudgetCents) * 100))
            : 0;

    return (
        <section className="admin-panel rounded-2xl p-5 shadow-xs">
            <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 lg:flex-row lg:items-center lg:justify-between dark:border-slate-800">
                <div>
                    <div className="flex items-center gap-2 text-xs font-semibold tracking-wider text-blue-600 uppercase dark:text-blue-400">
                        <SlidersHorizontal className="h-4 w-4" />
                        {t('aiqc.eyebrow')}
                    </div>
                    <h2 className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
                        {t('aiqc.title')}
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">
                        {t('aiqc.subtitle')}
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <EnableManualModeButton
                        config={draft}
                        onDone={applyResponse}
                    />
                    <button
                        type="button"
                        onClick={() => void loadControls()}
                        disabled={loading || saving}
                        className="admin-subpanel inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-100 disabled:opacity-50 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                        {t('aiqc.reload')}
                    </button>
                    <button
                        type="button"
                        onClick={() => void handleSave()}
                        disabled={!draft || loading || saving}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-[#2170e4] px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
                    >
                        <Save className="h-3.5 w-3.5" />
                        {saving ? t('aiqc.saving') : t('aiqc.save')}
                    </button>
                </div>
            </div>

            {error && (
                <div className="mt-4 flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-xs text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {status && (
                <div
                    className={`mt-4 flex items-center gap-2 rounded-xl border px-4 py-3 text-xs ${
                        status.tone === 'success'
                            ? 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200'
                            : 'border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200'
                    }`}
                >
                    {status.tone === 'success' ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                    ) : (
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                    )}
                    <span>{status.text}</span>
                </div>
            )}

            {draft && (
                <div className="mt-4 space-y-4">
                    {/* Variant 6A: 3 Simple Summary Cards */}
                    <div
                        data-aiqc-simple-cards
                        className="grid grid-cols-1 gap-3 md:grid-cols-3"
                    >
                        <div className="admin-subpanel rounded-xl p-4">
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                    {t('aiqc.simple.budgetTitle')}
                                </span>
                                <span className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 font-mono text-xs font-bold text-blue-700 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                                    <DollarSign className="h-3 w-3" />
                                    {formatUsd(totalSpendCents)} / {formatUsd(totalBudgetCents)}
                                </span>
                            </div>
                            <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">
                                {t('aiqc.simple.budgetDesc')}
                            </p>
                            <div className="mt-3">
                                <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                                    <span>{t('aiqc.simple.budgetUsed')}</span>
                                    <span className="font-mono font-semibold">{budgetPct}%</span>
                                </div>
                                <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                                    <div
                                        className="h-full rounded-full bg-[#2170e4] transition-all"
                                        style={{ width: `${Math.max(4, budgetPct)}%` }}
                                    />
                                </div>
                                <div className="mt-2.5 flex items-center justify-between gap-2 text-xs">
                                    <span className="text-slate-600 dark:text-slate-300">
                                        {t('aiqc.simple.perContourUsd')}
                                    </span>
                                    <input
                                        type="number"
                                        min={0}
                                        max={50}
                                        step={0.25}
                                        value={(draft.bot_qa.daily_budget_cents / 100).toFixed(2)}
                                        onChange={(event) =>
                                            updateUsdBudgetField('bot_qa', event.target.value)
                                        }
                                        className="admin-input w-24 rounded-lg px-2 py-1 text-right font-mono text-xs"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="admin-subpanel rounded-xl p-4">
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                    {t('aiqc.simple.botQaTitle')}
                                </span>
                                <span
                                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${modeBadgeClasses(
                                        draft.bot_qa.mode,
                                    )}`}
                                >
                                    {modeLabel(draft.bot_qa.mode)}
                                </span>
                            </div>
                            <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">
                                {t('aiqc.simple.botQaDesc')}
                            </p>
                            <div className="mt-3 flex items-center gap-2">
                                <select
                                    value={draft.bot_qa.mode}
                                    onChange={(event) =>
                                        updateScope(
                                            'bot_qa',
                                            'mode',
                                            event.target.value as AIQualityMode,
                                        )
                                    }
                                    className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                >
                                    {AI_QUALITY_MODES.map((mode) => (
                                        <option key={mode} value={mode}>
                                            {modeLabel(mode)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div className="admin-subpanel rounded-xl p-4">
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                    {t('aiqc.simple.managerAndAlertsTitle')}
                                </span>
                                <span
                                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${modeBadgeClasses(
                                        draft.manager_qa.mode,
                                    )}`}
                                >
                                    {modeLabel(draft.manager_qa.mode)}
                                </span>
                            </div>
                            <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-300">
                                {t('aiqc.simple.managerAndAlertsDesc')}
                            </p>
                            <div className="mt-3 flex items-center gap-2">
                                <select
                                    value={draft.manager_qa.mode}
                                    onChange={(event) =>
                                        updateScope(
                                            'manager_qa',
                                            'mode',
                                            event.target.value as AIQualityMode,
                                        )
                                    }
                                    className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                >
                                    {AI_QUALITY_MODES.map((mode) => (
                                        <option key={mode} value={mode}>
                                            {modeLabel(mode)}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </div>

                    <div
                        className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 text-xs ${
                            allDisabled
                                ? 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300'
                                : 'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200'
                        }`}
                    >
                        <div className="flex items-center gap-2 font-medium">
                            <Bot className="h-4 w-4 shrink-0" />
                            <span>
                                {allDisabled ? t('aiqc.zeroDefault') : t('aiqc.activeModes')}
                            </span>
                        </div>
                        <span className="text-[11px] text-slate-500 dark:text-slate-400">
                            {t('aiqc.zeroCallsHint')}
                        </span>
                    </div>

                    {warnings.length > 0 && (
                        <div className="space-y-2 rounded-xl border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
                            <div className="flex items-center gap-2 font-semibold">
                                <ShieldAlert className="h-4 w-4 shrink-0" />
                                {t('aiqc.activeWarnings')}
                            </div>
                            <ul className="list-disc space-y-1 pl-5">
                                {warnings.map((warning) => (
                                    <li key={`${warning.scope}-${warning.code}`}>
                                        <span className="font-medium">
                                            {scopeShortName(warning.scope)}:
                                        </span>{' '}
                                        {tx(`aiqc.warning.${warning.code}`, warning.message)}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Collapsible Engineer Settings (Variant 6A) */}
                    <details
                        data-advanced-engineer-settings
                        className="admin-subpanel group rounded-2xl p-4"
                    >
                        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-xs font-bold text-slate-800 select-none dark:text-slate-100">
                            <span className="inline-flex items-center gap-2">
                                <SlidersHorizontal className="h-4 w-4 text-[#2170e4]" />
                                {t('aiqc.engineerSettingsToggle')}
                            </span>
                            <span className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                {t('aiqc.engineerSettingsHint')}
                            </span>
                        </summary>

                        <div className="mt-4 space-y-4 border-t border-slate-200 pt-4 dark:border-slate-700">
                            <div
                                data-ai-quality-contours
                                className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-600 md:grid-cols-3 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                            >
                                {AI_QUALITY_SCOPES.map((scope) => (
                                    <div key={scope} className="space-y-1">
                                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                                            {scopeLabel(scope)}
                                        </div>
                                        <p className="leading-relaxed">{scopeDetail(scope)}</p>
                                    </div>
                                ))}
                            </div>

                            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                                {AI_QUALITY_SCOPES.map((scope) => {
                                    const scopeConfig = draft[scope];
                                    const criteriaKeys = criteriaKeysFor(scope, scopeConfig.criteria);
                                    return (
                                        <div
                                            key={scope}
                                            className="admin-panel space-y-4 rounded-xl p-4"
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                                                        {scopeLabel(scope)}
                                                    </h3>
                                                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                                        {scopeDescription(scope)}
                                                    </p>
                                                </div>
                                                <span
                                                    className={`rounded-full border px-2.5 py-1 text-xs font-medium ${modeBadgeClasses(
                                                        scopeConfig.mode,
                                                    )}`}
                                                >
                                                    {modeLabel(scopeConfig.mode)}
                                                </span>
                                            </div>

                                            <div
                                                data-usage-today={scope}
                                                className="admin-subpanel rounded-lg px-3 py-2 text-xs text-slate-600 dark:text-slate-300"
                                            >
                                                {renderUsageLine(scope, scopeConfig)}
                                            </div>

                                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span className="flex items-center gap-1">
                                                        {t('aiqc.field.mode')}
                                                        <HelpTooltip text={t('aiqc.tooltip.mode')} />
                                                    </span>
                                                    <select
                                                        value={scopeConfig.mode}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'mode',
                                                                event.target.value as AIQualityMode,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-3 py-2 text-xs"
                                                    >
                                                        {AI_QUALITY_MODES.map((mode) => (
                                                            <option key={mode} value={mode}>
                                                                {modeLabel(mode)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </label>

                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span className="flex items-center gap-1">
                                                        {t('aiqc.field.transcriptMode')}
                                                        <HelpTooltip text={t('aiqc.tooltip.transcriptMode')} />
                                                    </span>
                                                    <select
                                                        value={scopeConfig.transcript_mode}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'transcript_mode',
                                                                event.target.value as AIQualityTranscriptMode,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-3 py-2 text-xs"
                                                    >
                                                        {AI_QUALITY_TRANSCRIPT_MODES.map((mode) => (
                                                            <option key={mode} value={mode}>
                                                                {transcriptLabel(mode)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </label>
                                            </div>

                                            <label className="block space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                <span className="flex items-center gap-1">
                                                    {t('aiqc.field.model')}
                                                    <HelpTooltip text={t('aiqc.tooltip.model')} />
                                                </span>
                                                <select
                                                    value={scopeConfig.model}
                                                    onChange={(event) =>
                                                        updateScope(
                                                            scope,
                                                            'model',
                                                            event.target.value,
                                                        )
                                                    }
                                                    className="admin-input w-full rounded-lg px-3 py-2 text-xs"
                                                >
                                                    {AI_QUALITY_MODELS.map((model) => (
                                                        <option key={model} value={model}>
                                                            {model}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>

                                            <div className="grid grid-cols-3 gap-2">
                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span className="flex items-center gap-1">
                                                        <DollarSign className="h-3 w-3" />
                                                        {t('aiqc.field.dailyBudget')}
                                                    </span>
                                                    <input
                                                        type="number"
                                                        min={0}
                                                        max={5000}
                                                        value={scopeConfig.daily_budget_cents}
                                                        onChange={(event) =>
                                                            updateNumberField(
                                                                scope,
                                                                'daily_budget_cents',
                                                                event.target.value,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                                    />
                                                    <span className="block text-[11px] text-slate-500">
                                                        {formatUsd(scopeConfig.daily_budget_cents)} /{' '}
                                                        {t('aiqc.perDay')}
                                                    </span>
                                                </label>

                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span className="flex items-center gap-1">
                                                        <Gauge className="h-3 w-3" />
                                                        {t('aiqc.field.callsPerRun')}
                                                    </span>
                                                    <input
                                                        type="number"
                                                        min={0}
                                                        max={25}
                                                        value={scopeConfig.max_calls_per_run}
                                                        onChange={(event) =>
                                                            updateNumberField(
                                                                scope,
                                                                'max_calls_per_run',
                                                                event.target.value,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                                    />
                                                </label>

                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span>{t('aiqc.field.callsPerDay')}</span>
                                                    <input
                                                        type="number"
                                                        min={0}
                                                        max={100}
                                                        value={scopeConfig.max_calls_per_day}
                                                        onChange={(event) =>
                                                            updateNumberField(
                                                                scope,
                                                                'max_calls_per_day',
                                                                event.target.value,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                                    />
                                                </label>
                                            </div>

                                            <div className="grid grid-cols-2 gap-2">
                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span>{t('aiqc.field.retryAttempts')}</span>
                                                    <input
                                                        type="number"
                                                        min={1}
                                                        max={3}
                                                        value={scopeConfig.retry.max_attempts}
                                                        onChange={(event) =>
                                                            updateRetry(
                                                                scope,
                                                                'max_attempts',
                                                                event.target.value,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                                    />
                                                </label>

                                                <label className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                                                    <span>{t('aiqc.field.backoffSeconds')}</span>
                                                    <input
                                                        type="number"
                                                        min={0}
                                                        max={600}
                                                        value={scopeConfig.retry.backoff_seconds}
                                                        onChange={(event) =>
                                                            updateRetry(
                                                                scope,
                                                                'backoff_seconds',
                                                                event.target.value,
                                                            )
                                                        }
                                                        className="admin-input w-full rounded-lg px-2.5 py-1.5 text-xs"
                                                    />
                                                </label>
                                            </div>

                                            <div className="space-y-2 border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="font-medium">
                                                        {t('aiqc.criteriaToggles')}
                                                    </span>
                                                    <HelpTooltip text={tx(`aiqc.criteriaHelp.${scope}`, '')} />
                                                </div>
                                                <p className="text-[11px] leading-relaxed text-slate-500">
                                                    {tx(`aiqc.criteriaHelp.${scope}`, '')}
                                                </p>
                                                <div className="grid grid-cols-1 gap-1.5">
                                                    {criteriaKeys.map((key) => {
                                                        const enabled = scopeConfig.criteria[key] ?? true;
                                                        const help = criterionHelp(scope, key);
                                                        return (
                                                            <div
                                                                key={key}
                                                                className="admin-subpanel flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5"
                                                            >
                                                                <label className="flex min-w-0 flex-1 items-center gap-2">
                                                                    <input
                                                                        type="checkbox"
                                                                        data-criterion={key}
                                                                        checked={enabled}
                                                                        onChange={(event) =>
                                                                            toggleCriterion(
                                                                                scope,
                                                                                key,
                                                                                event.target.checked,
                                                                            )
                                                                        }
                                                                        className="h-3.5 w-3.5 rounded accent-blue-600"
                                                                    />
                                                                    <span className="truncate font-medium text-slate-800 dark:text-slate-200">
                                                                        {criterionLabel(scope, key)}
                                                                    </span>
                                                                </label>
                                                                {help && <HelpTooltip text={help} />}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>

                                            <div className="space-y-2 border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
                                                <label className="flex items-center justify-between gap-2">
                                                    <span className="flex items-center gap-1">
                                                        {t('aiqc.cacheTelemetry')}
                                                        <HelpTooltip text={t('aiqc.tooltip.cacheTelemetry')} />
                                                    </span>
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.cache_telemetry_enabled}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'cache_telemetry_enabled',
                                                                event.target.checked,
                                                            )
                                                        }
                                                        className="h-4 w-4 rounded accent-blue-600"
                                                    />
                                                </label>

                                                <label className="flex items-center justify-between gap-2">
                                                    <span>{t('aiqc.alertOnFailure')}</span>
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.alert_on_failure}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'alert_on_failure',
                                                                event.target.checked,
                                                            )
                                                        }
                                                        className="h-4 w-4 rounded accent-blue-600"
                                                    />
                                                </label>

                                                <label className="flex items-center justify-between gap-2 text-amber-700 dark:text-amber-300">
                                                    <span>{t('aiqc.fullTranscriptOverride')}</span>
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.full_transcript_warning_override}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'full_transcript_warning_override',
                                                                event.target.checked,
                                                            )
                                                        }
                                                        className="h-4 w-4 rounded accent-amber-500"
                                                    />
                                                </label>

                                                <label className="flex items-center justify-between gap-2 text-amber-700 dark:text-amber-300">
                                                    <span>{t('aiqc.glm5Override')}</span>
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.glm5_warning_override}
                                                        onChange={(event) =>
                                                            updateScope(
                                                                scope,
                                                                'glm5_warning_override',
                                                                event.target.checked,
                                                            )
                                                        }
                                                        className="h-4 w-4 rounded accent-amber-500"
                                                    />
                                                </label>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </details>
                </div>
            )}
        </section>
    );
}
