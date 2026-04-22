import { useCallback, useEffect, useState, type ChangeEvent, type ReactNode } from 'react';
import {
    AlertTriangle,
    Bell,
    Bot,
    CheckCircle2,
    DollarSign,
    Gauge,
    HelpCircle,
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

const MODE_OPTIONS: { value: AIQualityMode; label: string }[] = [
    { value: 'disabled', label: 'Disabled' },
    { value: 'manual', label: 'Manual' },
    { value: 'daily_sample', label: 'Daily sample' },
    { value: 'scheduled', label: 'Scheduled' },
];

const TRANSCRIPT_OPTIONS: { value: AIQualityTranscriptMode; label: string }[] = [
    { value: 'disabled', label: 'Disabled' },
    { value: 'summary', label: 'Summary' },
    { value: 'full', label: 'Full transcript' },
];

const MODE_HELP = 'Disabled and manual modes create zero scheduled automation. Daily sample and scheduled modes can spend provider budget, bounded by per-run and daily call caps.';
const TRANSCRIPT_HELP = 'Summary is the cost-safe default. Full transcript can send large conversations to the LLM and requires explicit warning acknowledgement.';
const MODEL_HELP = 'Non-core QA should use a fast model. GLM-5 is reserved for high-value sales chat and is expensive for background QA.';
const BUDGET_HELP = 'Daily budget is stored in cents. Setting it to 0 blocks QA LLM calls for that scope.';
const CALL_CAP_HELP = 'Max calls per run and per day bound how much automation can execute even when a scheduler fires frequently.';
const RETRY_HELP = 'Retries can repeat provider calls. The backend allows at most 2 attempts with bounded backoff.';
const CACHE_HELP = 'Cache telemetry records OpenRouter cached/write token fields for observability; it is not a safety limit.';
const ALERT_HELP = 'Alert on failure lets final QA failures surface to admins instead of becoming silent background cost.';

const SCOPE_META: {
    key: AIQualityScopeKey;
    label: string;
    shortLabel: string;
    description: string;
    icon: LucideIcon;
    accentClass: string;
    badgeClass: string;
}[] = [
    {
        key: 'bot_qa',
        label: 'Bot QA',
        shortLabel: 'Bot QA',
        description: 'Final assistant quality review for customer conversations.',
        icon: Bot,
        accentClass: 'text-emerald-300',
        badgeClass: 'bg-emerald-500/10 text-emerald-300',
    },
    {
        key: 'manager_qa',
        label: 'Manager QA',
        shortLabel: 'Manager QA',
        description: 'Resolved escalation review and manager coaching scores.',
        icon: CheckCircle2,
        accentClass: 'text-blue-300',
        badgeClass: 'bg-blue-500/10 text-blue-300',
    },
    {
        key: 'red_flags',
        label: 'Red Flags',
        shortLabel: 'Red flags',
        description: 'Realtime scan for complaints, risk language, and missed escalation signals.',
        icon: ShieldAlert,
        accentClass: 'text-amber-200',
        badgeClass: 'bg-amber-500/10 text-amber-200',
    },
];

interface AIQualityControlsPanelProps {
    initialControls?: AIQualityControlsResponse | null;
}

function messageClasses(tone: MessageTone): string {
    switch (tone) {
        case 'success':
            return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300';
        case 'error':
            return 'border-red-500/20 bg-red-500/10 text-red-300';
        default:
            return 'border-amber-500/20 bg-amber-500/10 text-amber-200';
    }
}

function formatBudget(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`;
}

function formatCriteriaLabel(key: string): string {
    return key
        .replace(/[_-]+/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isGlm5Model(model: string): boolean {
    const normalized = model.toLowerCase();
    return normalized.includes('glm-5') || normalized.includes('glm5');
}

function scopeName(scope: AIQualityScopeKey): string {
    return SCOPE_META.find((item) => item.key === scope)?.shortLabel ?? scope;
}

function automationLabel(scopeConfig: AIQualityScopeConfig): string {
    switch (scopeConfig.mode) {
        case 'disabled':
            return 'Zero automation';
        case 'manual':
            return 'Manual only';
        case 'daily_sample':
            return 'Daily sample';
        case 'scheduled':
            return 'Scheduled';
    }
}

function automationBadgeClass(scopeConfig: AIQualityScopeConfig): string {
    switch (scopeConfig.mode) {
        case 'disabled':
            return 'bg-emerald-500/10 text-emerald-300';
        case 'manual':
            return 'bg-blue-500/10 text-blue-300';
        case 'daily_sample':
            return 'bg-amber-500/10 text-amber-200';
        case 'scheduled':
            return 'bg-red-500/10 text-red-300';
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
            <span
                aria-label={tooltip}
                title={tooltip}
                className="inline-flex"
            >
                <HelpCircle size={14} className="text-slate-500" />
            </span>
        </span>
    );
}

function baseInputClass(): string {
    return 'mt-2 w-full rounded-xl border border-white/[0.08] bg-slate-950/70 px-3 py-2 text-sm text-white outline-none transition focus:border-emerald-400/60 disabled:opacity-50';
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
    const [controls, setControls] = useState<AIQualityControlsResponse | null>(initialControls);
    const [draft, setDraft] = useState<AIQualityControlsConfig | null>(
        initialControls ? cloneConfig(initialControls.config) : null,
    );
    const [loading, setLoading] = useState(initialControls === null);
    const [savingScope, setSavingScope] = useState<AIQualityScopeKey | null>(null);
    const [message, setMessage] = useState<{ tone: MessageTone; text: string } | null>(null);

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
                text: err instanceof Error ? err.message : 'Failed to load AI Quality Controls.',
            });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (initialControls) {
            setControls(initialControls);
            setDraft(cloneConfig(initialControls.config));
            setLoading(false);
            return;
        }

        void loadControls();
    }, [initialControls, loadControls]);

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
            setControls(response);
            setDraft(cloneConfig(response.config));
            setMessage({
                tone: 'success',
                text: `${scopeName(scope)} controls saved.`,
            });
        } catch (err) {
            setMessage({
                tone: 'error',
                text: err instanceof Error ? err.message : `Failed to save ${scopeName(scope)} controls.`,
            });
        } finally {
            setSavingScope(null);
        }
    }

    const effectiveConfig = draft ?? controls?.config ?? null;
    const allAutomationDisabled = effectiveConfig
        ? SCOPE_META.every((item) => effectiveConfig[item.key].mode === 'disabled')
        : false;

    return (
        <section className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-5 xl:col-span-2">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <div className="flex items-center gap-2 text-white">
                        <SlidersHorizontal size={18} className="text-emerald-300" />
                        <h3 className="text-lg font-semibold">AI Quality Controls</h3>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-slate-400">
                        Admin-owned controls for bot QA, manager QA, and red-flag review cost.
                    </p>
                </div>
                <button
                    onClick={() => void loadControls()}
                    disabled={loading || savingScope !== null}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/[0.08] disabled:opacity-50"
                >
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    Reload controls
                </button>
            </div>

            {loading && (
                <div className="mt-5 rounded-xl border border-white/[0.06] bg-slate-900/60 px-4 py-4 text-sm text-slate-400">
                    Loading AI Quality Controls...
                </div>
            )}

            {effectiveConfig && allAutomationDisabled && (
                <div className="mt-5 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-200">
                    <div className="flex items-start gap-3">
                        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-300" />
                        <div>
                            <p className="font-medium text-emerald-100">Zero automation safe default</p>
                            <p className="mt-1 text-emerald-200/80">
                                All scopes are disabled, so scheduled AI quality jobs open 0 LLM calls until an admin saves another mode.
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
                            className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
                        >
                            <AlertTriangle size={16} className="mr-2 inline text-amber-200" />
                            <span className="font-medium">{scopeName(warning.scope)}:</span> {warning.message}
                        </div>
                    ))}
                </div>
            )}

            {message && (
                <div className={`mt-5 rounded-xl border px-4 py-3 text-sm ${messageClasses(message.tone)}`}>
                    {message.text}
                </div>
            )}

            {effectiveConfig && (
                <>
                    <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
                        {SCOPE_META.map((meta) => {
                            const scopeConfig = effectiveConfig[meta.key];
                            const Icon = meta.icon;
                            const criteriaEntries = Object.entries(scopeConfig.criteria).sort(([left], [right]) => left.localeCompare(right));
                            const showFullTranscriptWarning = scopeConfig.transcript_mode === 'full';
                            const showGlmWarning = isGlm5Model(scopeConfig.model);

                            return (
                                <div key={meta.key} className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <div className="flex items-center gap-2 text-white">
                                                <Icon size={17} className={meta.accentClass} />
                                                <h4 className="text-base font-semibold">{meta.label}</h4>
                                            </div>
                                            <p className="mt-2 text-sm text-slate-400">{meta.description}</p>
                                        </div>
                                        <span className={`rounded-xl px-3 py-2 text-xs font-medium ${automationBadgeClass(scopeConfig)}`}>
                                            {automationLabel(scopeConfig)}
                                        </span>
                                    </div>

                                    <div className="mt-4 grid grid-cols-1 gap-3">
                                        <label htmlFor={scopeFieldId(meta.key, 'mode')} className="text-sm font-medium text-slate-300">
                                            <TooltippedLabel tooltip={MODE_HELP}>Mode</TooltippedLabel>
                                            <select
                                                id={scopeFieldId(meta.key, 'mode')}
                                                value={scopeConfig.mode}
                                                onChange={(event) => handleModeChange(meta.key, event.target.value as AIQualityMode)}
                                                className={baseInputClass()}
                                            >
                                                {MODE_OPTIONS.map((option) => (
                                                    <option key={option.value} value={option.value}>{option.label}</option>
                                                ))}
                                            </select>
                                        </label>

                                        <label htmlFor={scopeFieldId(meta.key, 'transcript')} className="text-sm font-medium text-slate-300">
                                            <TooltippedLabel tooltip={TRANSCRIPT_HELP}>Transcript mode</TooltippedLabel>
                                            <select
                                                id={scopeFieldId(meta.key, 'transcript')}
                                                value={scopeConfig.transcript_mode}
                                                onChange={(event) => handleTranscriptChange(meta.key, event.target.value as AIQualityTranscriptMode)}
                                                className={baseInputClass()}
                                            >
                                                {TRANSCRIPT_OPTIONS.map((option) => (
                                                    <option key={option.value} value={option.value}>{option.label}</option>
                                                ))}
                                            </select>
                                        </label>

                                        {showFullTranscriptWarning && (
                                            <label className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-3 text-sm text-amber-100">
                                                <span className="flex items-start gap-2">
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.full_transcript_warning_override}
                                                        onChange={(event) => handleBooleanChange(meta.key, 'full_transcript_warning_override', event.target.checked)}
                                                        className="mt-1"
                                                    />
                                                    <span>
                                                        <span className="font-medium">Full transcript override warning</span>
                                                        <span className="mt-1 block text-amber-100/80">
                                                            Full transcript mode can send large conversations to the LLM and should stay exceptional.
                                                        </span>
                                                    </span>
                                                </span>
                                            </label>
                                        )}

                                        <label htmlFor={scopeFieldId(meta.key, 'model')} className="text-sm font-medium text-slate-300">
                                            <TooltippedLabel tooltip={MODEL_HELP}>Model</TooltippedLabel>
                                            <input
                                                id={scopeFieldId(meta.key, 'model')}
                                                type="text"
                                                value={scopeConfig.model}
                                                onChange={(event) => handleModelChange(meta.key, event.target.value)}
                                                className={baseInputClass()}
                                            />
                                        </label>

                                        {showGlmWarning && (
                                            <label className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-3 text-sm text-red-100">
                                                <span className="flex items-start gap-2">
                                                    <input
                                                        type="checkbox"
                                                        checked={scopeConfig.glm5_warning_override}
                                                        onChange={(event) => handleBooleanChange(meta.key, 'glm5_warning_override', event.target.checked)}
                                                        className="mt-1"
                                                    />
                                                    <span>
                                                        <span className="font-medium">GLM-5 override warning</span>
                                                        <span className="mt-1 block text-red-100/80">
                                                            GLM-5 is expensive for QA automation and requires explicit admin acknowledgement.
                                                        </span>
                                                    </span>
                                                </span>
                                            </label>
                                        )}

                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                                            <label htmlFor={scopeFieldId(meta.key, 'budget')} className="text-sm font-medium text-slate-300">
                                                <TooltippedLabel tooltip={BUDGET_HELP}>Daily budget</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'budget')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.daily_budget_cents}
                                                    onChange={(event) => handleNumberChange(meta.key, 'daily_budget_cents', event)}
                                                    className={baseInputClass()}
                                                />
                                                <span className="mt-1 block text-xs text-slate-500">{formatBudget(scopeConfig.daily_budget_cents)}</span>
                                            </label>

                                            <label htmlFor={scopeFieldId(meta.key, 'per-run')} className="text-sm font-medium text-slate-300">
                                                <TooltippedLabel tooltip={CALL_CAP_HELP}>Max/run</TooltippedLabel>
                                                <input
                                                    id={scopeFieldId(meta.key, 'per-run')}
                                                    type="number"
                                                    min={0}
                                                    value={scopeConfig.max_calls_per_run}
                                                    onChange={(event) => handleNumberChange(meta.key, 'max_calls_per_run', event)}
                                                    className={baseInputClass()}
                                                />
                                            </label>

                                            <label htmlFor={scopeFieldId(meta.key, 'per-day')} className="text-sm font-medium text-slate-300">
                                                <TooltippedLabel tooltip={CALL_CAP_HELP}>Max/day</TooltippedLabel>
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
                                            <label htmlFor={scopeFieldId(meta.key, 'retry-attempts')} className="text-sm font-medium text-slate-300">
                                                <TooltippedLabel tooltip={RETRY_HELP}>Retry attempts</TooltippedLabel>
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

                                            <label htmlFor={scopeFieldId(meta.key, 'retry-backoff')} className="text-sm font-medium text-slate-300">
                                                <TooltippedLabel tooltip={RETRY_HELP}>Backoff seconds</TooltippedLabel>
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
                                            <label className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-3 text-sm text-slate-300">
                                                <TooltippedLabel tooltip={CACHE_HELP}>Cache telemetry</TooltippedLabel>
                                                <input
                                                    type="checkbox"
                                                    checked={scopeConfig.cache_telemetry_enabled}
                                                    onChange={(event) => handleBooleanChange(meta.key, 'cache_telemetry_enabled', event.target.checked)}
                                                />
                                            </label>

                                            <label className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-3 text-sm text-slate-300">
                                                <TooltippedLabel tooltip={ALERT_HELP}>Alert on failure</TooltippedLabel>
                                                <input
                                                    type="checkbox"
                                                    checked={scopeConfig.alert_on_failure}
                                                    onChange={(event) => handleBooleanChange(meta.key, 'alert_on_failure', event.target.checked)}
                                                />
                                            </label>
                                        </div>

                                        <div className="rounded-xl border border-white/[0.06] bg-slate-950/50 px-3 py-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <p className="text-sm font-medium text-white">Criteria toggles</p>
                                                <span className={`rounded-lg px-2.5 py-1 text-xs font-medium ${meta.badgeClass}`}>
                                                    {criteriaEntries.length}
                                                </span>
                                            </div>
                                            <div className="mt-3 space-y-2">
                                                {criteriaEntries.length > 0 ? criteriaEntries.map(([criterion, enabled]) => (
                                                    <label key={criterion} className="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm text-slate-300">
                                                        <span>{formatCriteriaLabel(criterion)}</span>
                                                        <input
                                                            type="checkbox"
                                                            checked={enabled}
                                                            onChange={(event) => handleCriteriaChange(meta.key, criterion, event.target.checked)}
                                                        />
                                                    </label>
                                                )) : (
                                                    <div className="rounded-lg border border-dashed border-white/[0.08] px-3 py-4 text-sm text-slate-500">
                                                        No criteria JSON exposed for this scope.
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => void handleSaveScope(meta.key)}
                                            disabled={savingScope !== null}
                                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/15 disabled:opacity-50"
                                        >
                                            {savingScope === meta.key ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
                                            Save {meta.shortLabel}
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="mt-5 rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
                        <div className="flex items-center gap-2 text-white">
                            <Gauge size={17} className="text-blue-300" />
                            <h4 className="text-base font-semibold">Manual trigger surfaces</h4>
                        </div>
                        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-white">
                                    <DollarSign size={15} className="text-emerald-300" />
                                    Bot QA
                                </div>
                                <p className="mt-2 text-sm text-slate-400">
                                    Existing internal endpoint: POST /api/v1/quality/reviews/ with an explicit conversation_id.
                                </p>
                            </div>
                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-white">
                                    <Bell size={15} className="text-blue-300" />
                                    Manager QA
                                </div>
                                <p className="mt-2 text-sm text-slate-400">
                                    Use the Manager Review Queue Evaluate actions below; they call the existing admin evaluate endpoint.
                                </p>
                            </div>
                            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
                                <div className="flex items-center gap-2 text-sm font-medium text-white">
                                    <AlertTriangle size={15} className="text-amber-200" />
                                    Red flags
                                </div>
                                <p className="mt-2 text-sm text-slate-400">
                                    No existing admin manual trigger endpoint is exposed, so this dashboard does not add one.
                                </p>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </section>
    );
}
