import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    FlaskConical,
    Plus,
    RefreshCw,
    Save,
    Search,
    SlidersHorizontal,
    Trash2,
} from 'lucide-react';
import {
    archiveBotRule,
    createBotRule,
    fetchBotRules,
    previewBotRules,
    reindexBotRule,
    updateBotRule,
} from '@/api/crm';
import CanonicalSyncButton, { runCanonicalSync } from '@/components/CanonicalSyncButton';
import { HelpTooltip } from '@/components/HelpTooltip';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Drawer from '@/components/ui/Drawer';
import {
    Badge,
    Field,
    IconButton,
    Input,
    InspectorBlock,
    Select,
    StateLine,
    TextArea,
    ViewBanner,
    cx,
    errorMessage,
} from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/Toast';
import { useI18n } from '@/i18n';
import type {
    AdminBotRulePreviewResponse,
    AdminBotRuleRead,
    AdminBotRuleWrite,
} from '@/types/crm';
import { autoSeededCanonicalKinds } from '@/views/KnowledgeBaseView';

const EMPTY_BOT_RULE_FORM: AdminBotRuleWrite = {
    title: '',
    type: 'playbook',
    status: 'draft',
    priority: 100,
    scope: 'global',
    stage: null,
    language: null,
    segment: null,
    instruction: '',
    trigger_examples: [],
};

const CANONICAL_RULE_TITLES = new Set([
    'Identity and disclosure: Noor from Treejar',
    'Strict language matching (EN / AR / RU)',
    'No fabricated discounts or unverified stock',
    'UAE 5% VAT and AED currency clarity',
    'Mandatory escalation triggers',
    'Consultative B2B qualification before quoting',
    'Complementary office furniture cross-sell',
    'Concise WhatsApp-friendly formatting',
]);

export function ruleToForm(rule: AdminBotRuleRead): AdminBotRuleWrite {
    const scope = (rule.scope as AdminBotRuleWrite['scope']) || 'global';
    const isGlobal = scope === 'global';
    return {
        title: rule.title || '',
        type: (rule.type as AdminBotRuleWrite['type']) || 'playbook',
        status: (rule.status as AdminBotRuleWrite['status']) || 'active',
        priority: rule.priority ?? 100,
        scope,
        stage: isGlobal ? null : rule.stage ?? null,
        language: isGlobal ? null : rule.language === 'ar' || rule.language === 'en' ? rule.language : null,
        segment: isGlobal ? null : rule.segment ?? null,
        instruction: rule.instruction || '',
        trigger_examples: Array.isArray(rule.trigger_examples) ? rule.trigger_examples : [],
    };
}

function isRuleFormDirty(
    form: AdminBotRuleWrite,
    selected: AdminBotRuleRead | null,
): boolean {
    const baseline = selected ? ruleToForm(selected) : EMPTY_BOT_RULE_FORM;
    return (
        form.title.trim() !== baseline.title.trim() ||
        form.type !== baseline.type ||
        form.status !== baseline.status ||
        form.priority !== baseline.priority ||
        form.scope !== baseline.scope ||
        (form.stage || null) !== (baseline.stage || null) ||
        (form.language || null) !== (baseline.language || null) ||
        (form.segment || null) !== (baseline.segment || null) ||
        form.instruction.trim() !== baseline.instruction.trim() ||
        form.trigger_examples.join('\n') !== baseline.trigger_examples.join('\n')
    );
}

interface BotRulesViewProps {
    globalSearch?: string;
    selectedId?: string;
    onSelectId?: (id: string) => void;
}

export default function BotRulesView({
    globalSearch = '',
    selectedId: externalSelectedId,
    onSelectId,
}: BotRulesViewProps) {
    const { t, label } = useI18n();
    const { pushToast } = useToast();

    const [rules, setRules] = useState<AdminBotRuleRead[]>([]);
    const [selected, setSelected] = useState<AdminBotRuleRead | null>(null);
    const [form, setForm] = useState<AdminBotRuleWrite>(EMPTY_BOT_RULE_FORM);
    const [preview, setPreview] = useState<AdminBotRulePreviewResponse | null>(null);
    const [search, setSearch] = useState(globalSearch);
    const [status, setStatus] = useState('active');
    const [testMessage, setTestMessage] = useState('Customer says: I need 20 chairs for my office');
    const [loaded, setLoaded] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [sandboxOpen, setSandboxOpen] = useState(false);
    const [archiveConfirmOpen, setArchiveConfirmOpen] = useState(false);
    const [pendingSelectRule, setPendingSelectRule] = useState<AdminBotRuleRead | 'new' | null>(null);

    useEffect(() => {
        setSearch(globalSearch);
    }, [globalSearch]);

    const isDirty = useMemo(() => isRuleFormDirty(form, selected), [form, selected]);

    const load = useCallback(async () => {
        const params = new URLSearchParams({ page_size: '50' });
        if (search.trim()) params.set('search', search.trim());
        if (status) params.set('status', status);
        let payload = await fetchBotRules(params);
        if (
            !search.trim() &&
            status === 'active' &&
            payload.items.length === 0 &&
            !autoSeededCanonicalKinds.has('botRules')
        ) {
            autoSeededCanonicalKinds.add('botRules');
            try {
                await runCanonicalSync('botRules', 'safe');
                payload = await fetchBotRules(params);
            } catch {
                // Keep empty state visible if background auto-seed fails.
            }
        }
        setRules(payload.items);
        setLoaded(true);
        if (!selected && payload.items.length > 0) {
            const match = externalSelectedId
                ? payload.items.find((item) => item.id === externalSelectedId) ?? payload.items[0]
                : payload.items[0];
            if (match) {
                setSelected(match);
                setForm(ruleToForm(match));
            }
        }
    }, [externalSelectedId, search, selected, status]);

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err, t)));
    }, [load, t]);

    function applySelection(target: AdminBotRuleRead | 'new') {
        if (target === 'new') {
            setSelected(null);
            setForm(EMPTY_BOT_RULE_FORM);
            setPreview(null);
            onSelectId?.('');
        } else {
            setSelected(target);
            setForm(ruleToForm(target));
            setPreview(null);
            onSelectId?.(target.id);
        }
        setPendingSelectRule(null);
    }

    function requestSelection(target: AdminBotRuleRead | 'new') {
        if (target !== 'new' && selected?.id === target.id) return;
        if (isDirty) {
            setPendingSelectRule(target);
            return;
        }
        applySelection(target);
    }

    function handleScopeChange(nextScope: AdminBotRuleWrite['scope']) {
        if (nextScope === 'global') {
            setForm({
                ...form,
                scope: 'global',
                stage: null,
                language: null,
                segment: null,
            });
        } else {
            setForm({
                ...form,
                scope: nextScope,
            });
        }
    }

    async function handlePreview() {
        setBusy(true);
        try {
            const result = await previewBotRules({
                message: testMessage,
                stage: form.scope === 'global' ? null : form.stage,
                language: form.scope === 'global' ? null : form.language,
                segment: form.scope === 'global' ? null : form.segment,
            });
            setPreview(result);
            setSandboxOpen(true);
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleSave() {
        setBusy(true);
        setError(null);
        const normalizedPayload: AdminBotRuleWrite =
            form.scope === 'global'
                ? { ...form, stage: null, language: null, segment: null }
                : form;
        try {
            const saved = selected
                ? await updateBotRule(selected.id, normalizedPayload)
                : await createBotRule(normalizedPayload);
            setSelected(saved);
            setForm(ruleToForm(saved));
            onSelectId?.(saved.id);
            pushToast({
                tone: 'success',
                message: t('botRules.savedToast'),
            });
            await load();
        } catch (err) {
            const msg = errorMessage(err, t);
            setError(msg);
            pushToast({ tone: 'error', message: msg });
        } finally {
            setBusy(false);
        }
    }

    async function confirmArchiveRule() {
        if (!selected) return;
        setBusy(true);
        try {
            await archiveBotRule(selected.id);
            setSelected(null);
            setForm(EMPTY_BOT_RULE_FORM);
            setPreview(null);
            setArchiveConfirmOpen(false);
            pushToast({
                tone: 'info',
                message: t('botRules.archivedToast'),
            });
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleReindex() {
        if (!selected) return;
        setBusy(true);
        try {
            const updated = await reindexBotRule(selected.id);
            setSelected(updated);
            pushToast({
                tone: 'success',
                message: t('botRules.reindexedToast'),
            });
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleCanonicalSynced() {
        setSelected(null);
        await load();
    }

    function renderRuleSourceBadge(titleText: string) {
        if (CANONICAL_RULE_TITLES.has(titleText)) {
            return <Badge label={t('kb.source.canonical')} tone="blue" />;
        }
        return <Badge label={t('kb.source.manual')} tone="gray" />;
    }

    return (
        <>
            <ViewBanner
                view="botRules"
                actions={
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setSandboxOpen(true)}
                            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                            data-open-rules-sandbox=""
                        >
                            <FlaskConical size={13} className="text-[var(--accent-primary)]" />
                            <span>{t('botRules.previewTitle')}</span>
                        </button>
                        <CanonicalSyncButton kind="botRules" onSynced={handleCanonicalSynced} />
                    </div>
                }
            />

            {/* Variant 2A: 2-Column Master-Detail Layout (35% List + 65% Wide Editor) */}
            <section
                className="grid h-[calc(100vh-112px)] grid-cols-1 lg:grid-cols-[minmax(320px,35%)_1fr] overflow-hidden"
                data-bot-rules-master-detail=""
            >
                {/* Left Column: Search, Status Filter & Rule List (35%) */}
                <div className="flex flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-hidden">
                    <div className="space-y-2.5 border-b border-[var(--border-subtle)] p-3.5">
                        <div className="flex items-center gap-1.5">
                            <div className="relative flex-1">
                                <Search
                                    size={15}
                                    className="pointer-events-none absolute left-3 top-2.5 text-[var(--text-muted)]"
                                />
                                <input
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    placeholder={t('botRules.searchPlaceholder')}
                                    className="h-9 w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                />
                            </div>
                            <HelpTooltip text={t('botRules.searchHelp')} />
                        </div>

                        <div className="flex items-center gap-2">
                            <select
                                value={status}
                                onChange={(event) => setStatus(event.target.value)}
                                aria-label={t('common.status')}
                                className="h-8 flex-1 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                            >
                                <option value="">{t('common.allStatuses')}</option>
                                <option value="active">{t('conv.filterActive')}</option>
                                <option value="draft">{t('botRules.filterDrafts')}</option>
                                <option value="archived">{t('status.archived')}</option>
                            </select>
                            <button
                                type="button"
                                onClick={() => requestSelection('new')}
                                className="inline-flex h-8 items-center gap-1 rounded-md bg-[var(--accent-primary)] px-2.5 text-xs font-semibold text-white hover:opacity-95"
                                data-bot-rules-new=""
                            >
                                <Plus size={14} />
                                {t('botRules.newRule')}
                            </button>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                        {loaded && rules.length === 0 && (
                            status === 'active' && !search.trim() ? (
                                <div className="m-4 space-y-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface)] p-4 text-sm text-[var(--text-secondary)]">
                                    <p className="font-semibold text-[var(--text-primary)]">
                                        {t('botRules.emptyTitle')}
                                    </p>
                                    <p>{t('botRules.emptyBody')}</p>
                                    <CanonicalSyncButton
                                        kind="botRules"
                                        prominent
                                        onSynced={handleCanonicalSynced}
                                    />
                                </div>
                            ) : (
                                <StateLine text={t('botRules.empty')} />
                            )
                        )}
                        {rules.map((rule) => {
                            const isSelected = selected?.id === rule.id;
                            return (
                                <button
                                    key={rule.id}
                                    type="button"
                                    onClick={() => requestSelection(rule)}
                                    className={cx(
                                        'block w-full px-4 py-3 text-left transition',
                                        isSelected
                                            ? 'bg-[var(--accent-soft)]'
                                            : 'hover:bg-[var(--bg-hover)]',
                                    )}
                                    data-bot-rule-row={rule.id}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="truncate text-sm font-semibold text-[var(--text-primary)]">
                                            {rule.title}
                                        </p>
                                        <Badge
                                            label={label(rule.status)}
                                            tone={
                                                rule.status === 'active'
                                                    ? 'green'
                                                    : rule.status === 'draft'
                                                        ? 'amber'
                                                        : 'gray'
                                            }
                                        />
                                    </div>
                                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">
                                        {rule.instruction}
                                    </p>
                                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                                        {renderRuleSourceBadge(rule.title)}
                                        <span>·</span>
                                        <span className="font-semibold text-[var(--text-secondary)]">
                                            P{rule.priority}
                                        </span>
                                        <span>·</span>
                                        <span>{label(rule.type)}</span>
                                        <span>·</span>
                                        <span>{label(rule.scope)}</span>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Right Column: Wide Editor (65%) */}
                <div className="flex flex-col overflow-y-auto bg-[var(--bg-app)] p-5">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <SlidersHorizontal size={17} className="text-[var(--accent-primary)]" />
                            <h3 className="flex items-center gap-1.5 text-base font-semibold text-[var(--text-primary)]">
                                {selected ? selected.title : t('botRules.newRule')}
                                <HelpTooltip text={t('botRules.editorHelp')} />
                            </h3>
                            {isDirty && (
                                <Badge label={t('common.unsavedChanges')} tone="amber" />
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-[var(--text-muted)]">{t('kb.field.source')}:</span>
                            {renderRuleSourceBadge(selected?.title ?? form.title)}
                        </div>
                    </div>

                    {error && <StateLine text={error} tone="red" />}

                    <div className="space-y-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 shadow-xs">
                        <Input
                            label={t('botRules.field.title')}
                            help={t('botRules.help.title')}
                            value={form.title}
                            onChange={(value) => setForm({ ...form, title: value })}
                        />

                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <Select
                                label={t('botRules.field.type')}
                                help={t('botRules.help.type')}
                                value={form.type}
                                options={[
                                    { label: t('status.hard_rule'), value: 'hard_rule' },
                                    { label: t('status.playbook'), value: 'playbook' },
                                    { label: t('status.upsell_rule'), value: 'upsell_rule' },
                                    { label: t('status.style_rule'), value: 'style_rule' },
                                    { label: t('status.escalation_rule'), value: 'escalation_rule' },
                                ]}
                                onChange={(value) =>
                                    setForm({ ...form, type: value as AdminBotRuleWrite['type'] })
                                }
                            />

                            <Select
                                label={t('common.status')}
                                help={t('botRules.help.status')}
                                value={form.status}
                                options={[
                                    { label: t('status.draft'), value: 'draft' },
                                    { label: t('botRules.statusActive'), value: 'active' },
                                    { label: t('status.archived'), value: 'archived' },
                                ]}
                                onChange={(value) =>
                                    setForm({ ...form, status: value as AdminBotRuleWrite['status'] })
                                }
                            />

                            <Input
                                label={t('botRules.field.priority')}
                                help={t('botRules.help.priority')}
                                value={String(form.priority)}
                                onChange={(value) =>
                                    setForm({ ...form, priority: Number(value) || 0 })
                                }
                            />

                            <Select
                                label={t('botRules.field.scope')}
                                help={t('botRules.help.scope')}
                                value={form.scope}
                                options={[
                                    { label: t('status.global'), value: 'global' },
                                    { label: t('status.stage'), value: 'stage' },
                                    { label: t('status.language'), value: 'language' },
                                    { label: t('status.segment'), value: 'segment' },
                                    { label: t('status.conversation'), value: 'conversation' },
                                ]}
                                onChange={(value) =>
                                    handleScopeChange(value as AdminBotRuleWrite['scope'])
                                }
                            />
                        </div>

                        {/* Conditional Scope Conditions: only rendered when scope !== 'global' (AC08) */}
                        {form.scope !== 'global' && (
                            <div
                                className="grid grid-cols-1 gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3.5 sm:grid-cols-3"
                                data-bot-rule-scope-conditions=""
                            >
                                <Select
                                    label={t('conv.field.stage')}
                                    help={t('botRules.help.stage')}
                                    value={form.stage || ''}
                                    options={[
                                        { label: t('common.any'), value: '' },
                                        { label: t('status.greeting'), value: 'greeting' },
                                        { label: t('status.qualifying'), value: 'qualifying' },
                                        { label: t('status.needs_analysis'), value: 'needs_analysis' },
                                        { label: t('status.solution'), value: 'solution' },
                                        { label: t('status.quoting'), value: 'quoting' },
                                        { label: t('status.closing'), value: 'closing' },
                                    ]}
                                    onChange={(value) => setForm({ ...form, stage: value || null })}
                                />

                                <Select
                                    label={t('common.language')}
                                    help={t('botRules.help.language')}
                                    value={form.language || ''}
                                    options={[
                                        { label: t('common.any'), value: '' },
                                        { label: 'EN', value: 'en' },
                                        { label: 'AR', value: 'ar' },
                                    ]}
                                    onChange={(value) =>
                                        setForm({
                                            ...form,
                                            language: value === 'ar' || value === 'en' ? value : null,
                                        })
                                    }
                                />

                                <Input
                                    label={t('botRules.field.segment')}
                                    help={t('botRules.help.segment')}
                                    value={form.segment || ''}
                                    onChange={(value) =>
                                        setForm({ ...form, segment: value || null })
                                    }
                                />
                            </div>
                        )}

                        <TextArea
                            label={t('botRules.field.instruction')}
                            help={t('botRules.help.instruction')}
                            value={form.instruction}
                            onChange={(value) => setForm({ ...form, instruction: value })}
                            className="min-h-[200px]"
                        />

                        <TextArea
                            label={t('botRules.field.triggers')}
                            help={t('botRules.help.triggers')}
                            value={form.trigger_examples.join('\n')}
                            onChange={(value) =>
                                setForm({
                                    ...form,
                                    trigger_examples: value
                                        .split('\n')
                                        .map((item) => item.trim())
                                        .filter(Boolean),
                                })
                            }
                            className="min-h-[90px]"
                        />

                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    disabled={busy || !form.title.trim() || !form.instruction.trim()}
                                    onClick={() => void handleSave()}
                                    className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white hover:opacity-95 disabled:opacity-50"
                                    data-bot-rule-save-btn=""
                                >
                                    <Save size={15} />
                                    <span>{t('common.saveAndIndex')}</span>
                                </button>
                                <IconButton
                                    icon={Search}
                                    label={t('common.preview')}
                                    disabled={busy}
                                    onClick={() => void handlePreview()}
                                />
                                <IconButton
                                    icon={RefreshCw}
                                    label={t('common.reindex')}
                                    disabled={!selected || busy}
                                    onClick={() => void handleReindex()}
                                />
                            </div>

                            <IconButton
                                icon={Trash2}
                                label={t('botRules.archive')}
                                disabled={!selected || busy}
                                onClick={() => setArchiveConfirmOpen(true)}
                                danger
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* Rule Sandbox Slide-over Drawer */}
            <Drawer
                open={sandboxOpen}
                title={t('botRules.previewTitle')}
                subtitle={t('botRules.previewHelp')}
                onClose={() => setSandboxOpen(false)}
                widthClassName="max-w-lg"
            >
                <div className="space-y-4" data-bot-rules-sandbox-drawer="">
                    <InspectorBlock title={t('botRules.previewTitle')} help={t('botRules.previewHelp')}>
                        <TextArea
                            label={t('botRules.testMessage')}
                            help={t('botRules.help.testMessage')}
                            value={testMessage}
                            onChange={setTestMessage}
                            className="min-h-[100px]"
                        />
                        <div className="pt-1">
                            <button
                                type="button"
                                disabled={busy}
                                onClick={() => void handlePreview()}
                                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-50"
                            >
                                <Search size={13} />
                                {t('common.preview')}
                            </button>
                        </div>
                        <Field label={t('botRules.applied')} value={String(preview?.rule_count ?? 0)} />
                        {preview?.applied_rules.map((rule) => (
                            <div
                                key={rule.id}
                                className="border-b border-[var(--border-subtle)] py-2"
                            >
                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                    {rule.title}
                                </p>
                                <p className="mt-1 text-xs text-[var(--text-muted)]">
                                    P{rule.priority} · {label(rule.type)}
                                </p>
                            </div>
                        ))}
                    </InspectorBlock>

                    <InspectorBlock title={t('botRules.promptBlock')} help={t('botRules.promptBlockHelp')}>
                        <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-md border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 text-xs leading-5 text-[var(--text-primary)]">
                            {preview?.prompt_block || '[BOT OPERATING RULES]'}
                        </pre>
                    </InspectorBlock>
                </div>
            </Drawer>

            {/* Unsaved Changes Guard Modal */}
            <ConfirmDialog
                open={Boolean(pendingSelectRule)}
                title={t('common.unsavedChangesTitle')}
                description={t('common.unsavedChangesDesc')}
                confirmLabel={t('common.discardChanges')}
                cancelLabel={t('common.stayHere')}
                danger
                onConfirm={() => {
                    if (pendingSelectRule) applySelection(pendingSelectRule);
                }}
                onCancel={() => setPendingSelectRule(null)}
            />

            {/* Archive Rule Confirm Modal */}
            <ConfirmDialog
                open={archiveConfirmOpen}
                title={t('botRules.archive')}
                description={t('botRules.confirmArchive')}
                confirmLabel={t('botRules.archive')}
                cancelLabel={t('common.cancel')}
                danger
                busy={busy}
                onConfirm={() => void confirmArchiveRule()}
                onCancel={() => setArchiveConfirmOpen(false)}
            />
        </>
    );
}
