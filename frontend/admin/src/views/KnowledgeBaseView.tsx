import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    BookOpen,
    CheckCircle2,
    Inbox,
    Plus,
    RefreshCw,
    Save,
    Search,
    Sparkles,
    Trash2,
} from 'lucide-react';
import {
    approveKnowledgeBaseCandidate,
    createKnowledgeBaseEntry,
    fetchKnowledgeBaseCandidates,
    fetchKnowledgeBaseEntries,
    previewKnowledgeBaseEntry,
    reindexKnowledgeBaseEntry,
    rejectKnowledgeBaseCandidate,
    softDeleteKnowledgeBaseEntry,
    updateKnowledgeBaseEntry,
} from '@/api/crm';
import CanonicalSyncButton, { runCanonicalSync } from '@/components/CanonicalSyncButton';
import type { CanonicalSyncKind } from '@/components/CanonicalSyncButton';
import { HelpTooltip } from '@/components/HelpTooltip';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Drawer from '@/components/ui/Drawer';
import {
    Badge,
    Field,
    FieldLabel,
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
    AdminKnowledgeBaseCandidate,
    AdminKnowledgeBasePreview,
    AdminKnowledgeBaseRead,
    AdminKnowledgeBaseWrite,
} from '@/types/crm';

export const autoSeededCanonicalKinds = new Set<CanonicalSyncKind>();

const EMPTY_KB_FORM: AdminKnowledgeBaseWrite = {
    source: 'manual',
    title: '',
    content: '',
    language: 'en',
    category: 'faq',
};

const KB_CATEGORIES = [
    { value: 'faq', labelRu: 'FAQ (Частые вопросы)', labelEn: 'FAQ' },
    { value: 'delivery', labelRu: 'Доставка и сборка', labelEn: 'Delivery & assembly' },
    { value: 'warranty', labelRu: 'Гарантия и возврат', labelEn: 'Warranty & returns' },
    { value: 'payment', labelRu: 'Оплата и VAT 5%', labelEn: 'Payment & 5% VAT' },
    { value: 'showroom', labelRu: 'Шоурум и контакты', labelEn: 'Showroom & contacts' },
    { value: 'b2b', labelRu: 'B2B, КП и опт', labelEn: 'B2B, quotations & bulk' },
    { value: 'about', labelRu: 'О компании Treejar', labelEn: 'About Treejar' },
    { value: 'policy', labelRu: 'Политика и правила', labelEn: 'Policies & terms' },
] as const;

export function entryToForm(entry: AdminKnowledgeBaseRead): AdminKnowledgeBaseWrite {
    return {
        source: entry.source,
        title: entry.title,
        content: entry.content,
        language: entry.language === 'ar' ? 'ar' : 'en',
        category: entry.category || 'faq',
    };
}

function isKbFormDirty(
    form: AdminKnowledgeBaseWrite,
    selected: AdminKnowledgeBaseRead | null,
): boolean {
    const baseline = selected ? entryToForm(selected) : EMPTY_KB_FORM;
    return (
        form.title.trim() !== baseline.title.trim() ||
        form.content.trim() !== baseline.content.trim() ||
        form.language !== baseline.language ||
        (form.category || 'faq') !== (baseline.category || 'faq')
    );
}

interface KnowledgeBaseViewProps {
    globalSearch?: string;
    selectedId?: string;
    onSelectId?: (id: string) => void;
    onCandidatesCountChange?: (count: number) => void;
}

export default function KnowledgeBaseView({
    globalSearch = '',
    selectedId: externalSelectedId,
    onSelectId,
    onCandidatesCountChange,
}: KnowledgeBaseViewProps) {
    const { t, lang, label } = useI18n();
    const { pushToast } = useToast();

    const [entries, setEntries] = useState<AdminKnowledgeBaseRead[]>([]);
    const [candidates, setCandidates] = useState<AdminKnowledgeBaseCandidate[]>([]);
    const [selected, setSelected] = useState<AdminKnowledgeBaseRead | null>(null);
    const [form, setForm] = useState<AdminKnowledgeBaseWrite>(EMPTY_KB_FORM);
    const [preview, setPreview] = useState<AdminKnowledgeBasePreview | null>(null);
    const [search, setSearch] = useState(globalSearch);
    const [categoryFilter, setCategoryFilter] = useState('');
    const [loaded, setLoaded] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [candidatesDrawerOpen, setCandidatesDrawerOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeBaseRead | null>(null);
    const [rejectTargetId, setRejectTargetId] = useState<string | null>(null);
    const [pendingSelectEntry, setPendingSelectEntry] = useState<AdminKnowledgeBaseRead | 'new' | null>(null);

    useEffect(() => {
        setSearch(globalSearch);
    }, [globalSearch]);

    const isDirty = useMemo(() => isKbFormDirty(form, selected), [form, selected]);

    const load = useCallback(async () => {
        const params = new URLSearchParams({ page_size: '50' });
        if (search.trim()) params.set('search', search.trim());
        if (categoryFilter) params.set('category', categoryFilter);

        let [entryPayload, candidatePayload] = await Promise.all([
            fetchKnowledgeBaseEntries(params),
            fetchKnowledgeBaseCandidates(new URLSearchParams({ status: 'needs_confirmation' })),
        ]);

        if (
            !search.trim() &&
            !categoryFilter &&
            entryPayload.items.length === 0 &&
            !autoSeededCanonicalKinds.has('knowledge')
        ) {
            autoSeededCanonicalKinds.add('knowledge');
            try {
                await runCanonicalSync('knowledge', 'safe');
                entryPayload = await fetchKnowledgeBaseEntries(params);
            } catch {
                // Keep empty state visible if background auto-seed fails.
            }
        }

        setEntries(entryPayload.items);
        setCandidates(candidatePayload.items);
        onCandidatesCountChange?.(candidatePayload.items.length);
        setLoaded(true);

        if (!selected && entryPayload.items.length > 0) {
            const match = externalSelectedId
                ? entryPayload.items.find((item) => item.id === externalSelectedId) ?? entryPayload.items[0]
                : entryPayload.items[0];
            if (match) {
                setSelected(match);
                setForm(entryToForm(match));
            }
        }
    }, [categoryFilter, externalSelectedId, onCandidatesCountChange, search, selected]);

    useEffect(() => {
        load().catch((err: unknown) => setError(errorMessage(err, t)));
    }, [load, t]);

    function applySelection(target: AdminKnowledgeBaseRead | 'new') {
        if (target === 'new') {
            setSelected(null);
            setForm(EMPTY_KB_FORM);
            setPreview(null);
            onSelectId?.('');
        } else {
            setSelected(target);
            setForm(entryToForm(target));
            setPreview(null);
            onSelectId?.(target.id);
        }
        setPendingSelectEntry(null);
    }

    function requestSelection(target: AdminKnowledgeBaseRead | 'new') {
        if (target !== 'new' && selected?.id === target.id) return;
        if (isDirty) {
            setPendingSelectEntry(target);
            return;
        }
        applySelection(target);
    }

    async function handlePreview() {
        setBusy(true);
        try {
            setPreview(await previewKnowledgeBaseEntry(form));
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleSave() {
        setBusy(true);
        setError(null);
        try {
            const saved = selected
                ? await updateKnowledgeBaseEntry(selected.id, form)
                : await createKnowledgeBaseEntry(form);
            setSelected(saved);
            setForm(entryToForm(saved));
            onSelectId?.(saved.id);
            pushToast({
                tone: 'success',
                message: t('kb.savedToast'),
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

    async function handleDelete(entry: AdminKnowledgeBaseRead | null) {
        if (!entry) return;
        setDeleteTarget(entry);
    }

    async function confirmDeleteEntry() {
        if (!deleteTarget) return;
        setBusy(true);
        try {
            await softDeleteKnowledgeBaseEntry(deleteTarget.id);
            setEntries((current) => current.filter((item) => item.id !== deleteTarget.id));
            setSelected(null);
            setForm(EMPTY_KB_FORM);
            setPreview(null);
            setDeleteTarget(null);
            pushToast({
                tone: 'info',
                message: t('kb.deletedToast'),
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
            const updated = await reindexKnowledgeBaseEntry(selected.id);
            setSelected(updated);
            pushToast({
                tone: 'success',
                message: t('kb.reindexedToast'),
            });
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function handleApprove(candidateId: string) {
        setBusy(true);
        try {
            const entry = await approveKnowledgeBaseCandidate(candidateId);
            setSelected(entry);
            setForm(entryToForm(entry));
            pushToast({
                tone: 'success',
                message: t('queues.approved'),
            });
            await load();
        } catch (err) {
            setError(errorMessage(err, t));
        } finally {
            setBusy(false);
        }
    }

    async function confirmRejectCandidate() {
        if (!rejectTargetId) return;
        setBusy(true);
        try {
            await rejectKnowledgeBaseCandidate(rejectTargetId, { reason: 'admin_rejected' });
            setCandidates((current) => current.filter((candidate) => candidate.id !== rejectTargetId));
            setRejectTargetId(null);
            pushToast({
                tone: 'info',
                message: t('queues.rejected'),
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

    function renderSourceBadge(source: string) {
        if (source === 'canonical_treejar') {
            return <Badge label={t('kb.source.canonical')} tone="blue" />;
        }
        if (source === 'canonical_treejar_custom') {
            return <Badge label={t('kb.source.customized')} tone="amber" />;
        }
        if (source === 'auto_faq') {
            return <Badge label="Auto-FAQ" tone="green" />;
        }
        return <Badge label={t('kb.source.manual')} tone="gray" />;
    }

    return (
        <>
            <ViewBanner
                view="knowledge"
                actions={
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setCandidatesDrawerOpen(true)}
                            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                            data-open-autofaq-drawer=""
                        >
                            <Sparkles size={13} className="text-[var(--accent-primary)]" />
                            <span>
                                {t('kb.autoFaqButton', { count: candidates.length })}
                            </span>
                        </button>
                        <CanonicalSyncButton kind="knowledge" onSynced={handleCanonicalSynced} />
                    </div>
                }
            />

            {/* Variant 2A: 2-Column Master-Detail Layout (35% List + 65% Wide Editor) */}
            <section
                className="grid h-[calc(100vh-112px)] grid-cols-1 lg:grid-cols-[minmax(320px,35%)_1fr] overflow-hidden"
                data-kb-master-detail=""
            >
                {/* Left Column: Search, Category Filter & Article List (35%) */}
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
                                    placeholder={t('kb.searchPlaceholder')}
                                    className="h-9 w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                />
                            </div>
                            <HelpTooltip text={t('kb.searchHelp')} />
                        </div>

                        <div className="flex items-center gap-2">
                            <select
                                value={categoryFilter}
                                onChange={(event) => setCategoryFilter(event.target.value)}
                                aria-label={t('kb.field.category')}
                                className="h-8 flex-1 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-input)] px-2.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)]"
                                data-kb-category-filter=""
                            >
                                <option value="">{t('kb.allCategories')}</option>
                                {KB_CATEGORIES.map((cat) => (
                                    <option key={cat.value} value={cat.value}>
                                        {lang === 'ru' ? cat.labelRu : cat.labelEn}
                                    </option>
                                ))}
                            </select>
                            <button
                                type="button"
                                onClick={() => requestSelection('new')}
                                className="inline-flex h-8 items-center gap-1 rounded-md bg-[var(--accent-primary)] px-2.5 text-xs font-semibold text-white hover:opacity-95"
                                data-kb-new-entry=""
                            >
                                <Plus size={14} />
                                {t('kb.newEntry')}
                            </button>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                        {loaded && entries.length === 0 && (
                            <div className="m-4 space-y-3 rounded-lg border border-dashed border-[var(--border-strong)] bg-[var(--bg-surface)] p-4 text-sm text-[var(--text-secondary)]">
                                <p className="font-semibold text-[var(--text-primary)]">{t('kb.emptyTitle')}</p>
                                <p>{t('kb.emptyBody')}</p>
                                <CanonicalSyncButton kind="knowledge" prominent onSynced={handleCanonicalSynced} />
                            </div>
                        )}
                        {entries.map((entry) => {
                            const isSelected = selected?.id === entry.id;
                            return (
                                <button
                                    key={entry.id}
                                    type="button"
                                    onClick={() => requestSelection(entry)}
                                    className={cx(
                                        'block w-full px-4 py-3 text-left transition',
                                        isSelected
                                            ? 'bg-[var(--accent-soft)]'
                                            : 'hover:bg-[var(--bg-hover)]',
                                    )}
                                    data-kb-entry-row={entry.id}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="truncate text-sm font-semibold text-[var(--text-primary)]">
                                            {entry.title}
                                        </p>
                                        <Badge
                                            label={entry.has_embedding ? t('kb.indexed') : t('kb.notIndexed')}
                                            tone={entry.has_embedding ? 'green' : 'amber'}
                                        />
                                    </div>
                                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">
                                        {entry.content}
                                    </p>
                                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
                                        {renderSourceBadge(entry.source)}
                                        <span>·</span>
                                        <span className="uppercase font-medium">{entry.language}</span>
                                        <span>·</span>
                                        <span>{entry.category || 'faq'}</span>
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
                            <BookOpen size={17} className="text-[var(--accent-primary)]" />
                            <h3 className="flex items-center gap-1.5 text-base font-semibold text-[var(--text-primary)]">
                                {selected ? selected.title : t('kb.newEntry')}
                                <HelpTooltip text={t('kb.editorHelp')} />
                            </h3>
                            {isDirty && (
                                <Badge label={t('common.unsavedChanges')} tone="amber" />
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-[var(--text-muted)]">{t('kb.field.source')}:</span>
                            {renderSourceBadge(selected?.source ?? form.source)}
                        </div>
                    </div>

                    {error && <StateLine text={error} tone="red" />}

                    <div className="space-y-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 shadow-xs">
                        <Input
                            label={t('kb.field.title')}
                            help={t('kb.help.title')}
                            value={form.title}
                            onChange={(value) => setForm({ ...form, title: value })}
                        />

                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                            <div>
                                <FieldLabel label={t('kb.field.source')} help={t('kb.help.source')} />
                                <div
                                    className="mt-1 flex h-9 items-center rounded-md border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-medium text-[var(--text-secondary)]"
                                    data-kb-source-badge=""
                                >
                                    {renderSourceBadge(selected?.source ?? form.source)}
                                </div>
                            </div>

                            <Select
                                label={t('common.language')}
                                help={t('kb.help.language')}
                                value={form.language}
                                options={[
                                    { label: 'EN (English)', value: 'en' },
                                    { label: 'AR (العربية)', value: 'ar' },
                                ]}
                                onChange={(value) => setForm({ ...form, language: value as 'en' | 'ar' })}
                            />

                            <Select
                                label={t('kb.field.category')}
                                help={t('kb.help.category')}
                                value={form.category || 'faq'}
                                options={KB_CATEGORIES.map((cat) => ({
                                    value: cat.value,
                                    label: lang === 'ru' ? cat.labelRu : cat.labelEn,
                                }))}
                                onChange={(value) => setForm({ ...form, category: value || 'faq' })}
                            />
                        </div>

                        <TextArea
                            label={t('kb.field.content')}
                            help={t('kb.help.content')}
                            value={form.content}
                            onChange={(value) => setForm({ ...form, content: value })}
                            className="min-h-[260px]"
                        />

                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    disabled={busy || !form.title.trim() || !form.content.trim()}
                                    onClick={() => void handleSave()}
                                    className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-white hover:opacity-95 disabled:opacity-50"
                                    data-kb-save-btn=""
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
                                label={t('kb.softDelete')}
                                disabled={!selected || busy}
                                onClick={() => void handleDelete(selected)}
                                danger
                            />
                        </div>
                    </div>

                    {/* Preview & Duplicate Check Result (shown below editor when previewed) */}
                    {preview && (
                        <div className="mt-4">
                            <InspectorBlock title={t('kb.previewTitle')} help={t('kb.previewHelp')}>
                                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                    <Field
                                        label={t('kb.embedding')}
                                        value={preview.embedding_ready ? t('kb.ready') : '—'}
                                    />
                                    <Field
                                        label={t('kb.duplicate')}
                                        value={preview.duplicate ? t('common.yes') : t('common.no')}
                                    />
                                    <Field
                                        label={t('kb.similarity')}
                                        value={
                                            preview.duplicate_similarity
                                                ? preview.duplicate_similarity.toFixed(3)
                                                : '—'
                                        }
                                    />
                                    <Field
                                        label={t('kb.unsafe')}
                                        value={preview.unsafe_reasons.join(', ') || '—'}
                                    />
                                </div>
                            </InspectorBlock>
                        </div>
                    )}
                </div>
            </section>

            {/* Slide-over Drawer for Auto-FAQ Candidates (Variant 2A) */}
            <Drawer
                open={candidatesDrawerOpen}
                title={t('kb.autoFaqTitle')}
                subtitle={t('kb.autoFaqHelp')}
                onClose={() => setCandidatesDrawerOpen(false)}
                widthClassName="max-w-lg"
            >
                <div className="space-y-3" data-autofaq-candidates-drawer="">
                    {candidates.length === 0 && (
                        <div className="rounded-lg border border-dashed border-[var(--border-subtle)] p-6 text-center text-sm text-[var(--text-muted)]">
                            <Inbox size={24} className="mx-auto mb-2 text-[var(--text-muted)]" />
                            {t('kb.noCandidates')}
                        </div>
                    )}
                    {candidates.map((candidate) => (
                        <div
                            key={candidate.id}
                            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 space-y-2"
                        >
                            <div className="flex items-start justify-between gap-2">
                                <p className="text-sm font-semibold text-[var(--text-primary)]">
                                    {candidate.question}
                                </p>
                                <Badge label={label(candidate.status)} tone="blue" />
                            </div>
                            <p className="text-xs leading-5 text-[var(--text-secondary)]">
                                {candidate.answer}
                            </p>
                            <div className="flex items-center justify-between gap-2 pt-2">
                                <span className="text-xs text-[var(--text-muted)]">
                                    {candidate.language.toUpperCase()}
                                </span>
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => setRejectTargetId(candidate.id)}
                                        className="rounded-md border border-rose-500/30 bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-rose-600 dark:text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"
                                    >
                                        {t('common.reject')}
                                    </button>
                                    <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => void handleApprove(candidate.id)}
                                        className="inline-flex items-center gap-1 rounded-md bg-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white hover:opacity-95 disabled:opacity-50"
                                    >
                                        <CheckCircle2 size={13} />
                                        {t('common.approve')}
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </Drawer>

            {/* Unsaved Changes Guard Modal */}
            <ConfirmDialog
                open={Boolean(pendingSelectEntry)}
                title={t('common.unsavedChangesTitle')}
                description={t('common.unsavedChangesDesc')}
                confirmLabel={t('common.discardChanges')}
                cancelLabel={t('common.stayHere')}
                danger
                onConfirm={() => {
                    if (pendingSelectEntry) applySelection(pendingSelectEntry);
                }}
                onCancel={() => setPendingSelectEntry(null)}
            />

            {/* Soft Delete Confirm Modal */}
            <ConfirmDialog
                open={Boolean(deleteTarget)}
                title={t('kb.softDelete')}
                description={t('kb.confirmDelete')}
                confirmLabel={t('kb.softDelete')}
                cancelLabel={t('common.cancel')}
                danger
                busy={busy}
                onConfirm={() => void confirmDeleteEntry()}
                onCancel={() => setDeleteTarget(null)}
            />

            {/* Reject Auto-FAQ Candidate Confirm Modal */}
            <ConfirmDialog
                open={Boolean(rejectTargetId)}
                title={t('common.reject')}
                description={t('kb.confirmRejectCandidate')}
                confirmLabel={t('common.reject')}
                cancelLabel={t('common.cancel')}
                danger
                busy={busy}
                onConfirm={() => void confirmRejectCandidate()}
                onCancel={() => setRejectTargetId(null)}
            />
        </>
    );
}
