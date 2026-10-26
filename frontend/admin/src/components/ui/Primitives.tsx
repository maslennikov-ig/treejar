import type { ComponentType, ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import EnableManualModeButton, { scopesNeedingManualMode } from '@/components/EnableManualModeButton';
import { HelpTooltip, SectionInfoBanner } from '@/components/HelpTooltip';
import type { QualityControlBlock } from '@/hooks/useAIQualityControlBlock';
import { useI18n } from '@/i18n';
import type { TranslateFn, TranslationKey } from '@/i18n';

export type BadgeTone = 'slate' | 'gray' | 'blue' | 'emerald' | 'green' | 'amber' | 'red';
export type StatusTone = 'gray' | 'amber' | 'green' | 'blue';
export type ActionMessage = { tone: 'success' | 'error' | 'info'; text: string };
export type AIQualityControlBlockState = QualityControlBlock;

export function cx(...values: Array<string | false | null | undefined>): string {
    return values.filter(Boolean).join(' ');
}

export function errorMessage(error: unknown, t: TranslateFn): string {
    return error instanceof Error ? error.message : t('common.unknownError');
}

export function stripHtml(text: string): string {
    return text.replace(/<[^>]+>/g, '').trim();
}

export function matchesQuery(
    query: string,
    ...values: Array<string | number | null | undefined>
): boolean {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return values.some(
        (value) =>
            value !== null &&
            value !== undefined &&
            String(value).toLowerCase().includes(needle),
    );
}

export function Badge({
    label,
    children,
    tone = 'slate',
}: {
    label?: string;
    children?: ReactNode;
    tone?: BadgeTone;
}) {
    const tones: Record<BadgeTone, string> = {
        slate: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
        gray: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
        blue: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800',
        emerald:
            'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
        green: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
        amber: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
        red: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/60 dark:text-red-300 dark:border-red-800',
    };
    return (
        <span
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}
        >
            {children ?? label}
        </span>
    );
}

export function ViewBanner({
    view,
    actions,
    defaultCollapsed = true,
}: {
    view: string;
    actions?: ReactNode;
    defaultCollapsed?: boolean;
}) {
    const { t } = useI18n();
    return (
        <SectionInfoBanner
            storageKey={view}
            title={t(`banner.${view}.title` as TranslationKey)}
            description={t(`banner.${view}.body` as TranslationKey)}
            runtime={t(`banner.${view}.runtime` as TranslationKey)}
            defaultCollapsed={defaultCollapsed}
            actions={actions}
        />
    );
}

export function Panel({
    title,
    subtitle,
    help,
    icon: Icon,
    action,
    actions,
    children,
    className = '',
}: {
    title?: string;
    subtitle?: string;
    help?: string;
    icon?: ComponentType<{ size?: number; className?: string }>;
    action?: ReactNode;
    actions?: ReactNode;
    children: ReactNode;
    className?: string;
}) {
    const headerAction = action ?? actions;
    return (
        <section className={`admin-panel rounded-xl p-5 shadow-xs ${className}`}>
            {(title || subtitle || headerAction) && (
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                        {Icon && (
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent-primary)]">
                                <Icon size={18} />
                            </div>
                        )}
                        <div>
                            {title && (
                                <h3 className="flex items-center gap-1.5 text-sm font-bold text-slate-900 dark:text-slate-100">
                                    <span>{title}</span>
                                    {help && <HelpTooltip text={help} />}
                                </h3>
                            )}
                            {subtitle && (
                                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                    {subtitle}
                                </p>
                            )}
                        </div>
                    </div>
                    {headerAction}
                </div>
            )}
            {children}
        </section>
    );
}

export function StatusCard({
    title,
    value,
    note,
    help,
    tone = 'gray',
}: {
    title: string;
    value: number | string;
    note: string;
    help?: string;
    tone?: StatusTone;
}) {
    const tones: Record<StatusTone, string> = {
        gray: 'border-slate-200 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-900/60',
        amber: 'border-amber-300 bg-amber-50/70 dark:border-amber-800/70 dark:bg-amber-950/35',
        green: 'border-emerald-300 bg-emerald-50/70 dark:border-emerald-800/70 dark:bg-emerald-950/35',
        blue: 'border-blue-300 bg-blue-50/70 dark:border-blue-800/70 dark:bg-blue-950/35',
    };
    return (
        <div className={cx('rounded-xl border p-4', tones[tone])}>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                <span>{title}</span>
                {help && <HelpTooltip text={help} />}
            </p>
            <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{note}</p>
        </div>
    );
}

export function ActionMessageBox({ message }: { message: ActionMessage }) {
    const classes: Record<ActionMessage['tone'], string> = {
        success:
            'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200',
        error: 'border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200',
        info: 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-200',
    };
    return (
        <div className={cx('rounded-lg border px-4 py-3 text-xs font-medium', classes[message.tone])}>
            {message.text}
        </div>
    );
}

export function RefreshButton({
    loading,
    label,
    onClick,
}: {
    loading: boolean;
    label?: string;
    onClick: () => void;
}) {
    const { t } = useI18n();
    return (
        <button
            type="button"
            disabled={loading}
            onClick={onClick}
            className="admin-subpanel inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:text-slate-200 dark:hover:bg-slate-800"
        >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>{label ?? t('common.refresh')}</span>
        </button>
    );
}

export function SideListPanel({
    title,
    icon: Icon,
    items,
    empty,
}: {
    title: string;
    icon: ComponentType<{ size?: number; className?: string }>;
    items: { key: string; title: string; meta: string }[];
    empty: string;
}) {
    return (
        <div className="admin-subpanel rounded-xl p-4">
            <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100">
                <Icon size={16} className="text-[var(--accent-primary)]" />
                <p className="text-sm font-semibold">{title}</p>
            </div>
            <div className="mt-3 space-y-2">
                {items.length > 0 ? (
                    items.map((item) => (
                        <div
                            key={item.key}
                            className="admin-panel rounded-lg px-3 py-2.5"
                        >
                            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                                {item.title}
                            </p>
                            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                                {item.meta}
                            </p>
                        </div>
                    ))
                ) : (
                    <div className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
                        {empty}
                    </div>
                )}
            </div>
        </div>
    );
}

export function JsonPreview({ title, value }: { title: string; value: unknown }) {
    return (
        <div>
            <p className="mb-1.5 text-[11px] font-semibold uppercase text-slate-500 dark:text-slate-400">
                {title}
            </p>
            <pre className="max-h-[240px] overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-5 text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
                {JSON.stringify(value ?? null, null, 2)}
            </pre>
        </div>
    );
}

export function InspectorBlock({
    title,
    help,
    children,
}: {
    title: string;
    help?: string;
    children: ReactNode;
}) {
    return (
        <section className="admin-panel rounded-xl p-4">
            <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
                <span>{title}</span>
                {help && <HelpTooltip text={help} />}
            </h3>
            <div className="mt-3 space-y-2">{children}</div>
        </section>
    );
}

export function Field({ label: labelText, value }: { label: string; value: string }) {
    return (
        <div className="flex items-start justify-between gap-3 text-xs">
            <span className="text-slate-500 dark:text-slate-400">{labelText}</span>
            <span className="max-w-[220px] break-words text-right font-medium text-slate-900 dark:text-slate-100">
                {value}
            </span>
        </div>
    );
}

export function IconButton({
    icon: Icon,
    label: labelText,
    disabled,
    danger,
    onClick,
}: {
    icon: ComponentType<{ size?: number }>;
    label: string;
    disabled?: boolean;
    danger?: boolean;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            disabled={disabled}
            onClick={onClick}
            className={cx(
                'inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
                danger
                    ? 'border-red-300 bg-red-50/70 text-red-700 hover:bg-red-100 dark:border-red-800 dark:bg-red-950/50 dark:text-red-300'
                    : 'admin-subpanel text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800',
            )}
        >
            <Icon size={14} />
            <span>{labelText}</span>
        </button>
    );
}

export function StateLine({
    text,
    tone = 'gray',
}: {
    text: string;
    tone?: 'gray' | 'red';
}) {
    return (
        <div
            className={cx(
                'm-3 rounded-lg px-3 py-2 text-xs',
                tone === 'red'
                    ? 'border border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200'
                    : 'admin-subpanel text-slate-600 dark:text-slate-300',
            )}
        >
            {text}
        </div>
    );
}

export function FieldLabel({
    label,
    help,
    tooltip,
    children,
}: {
    label: string;
    help?: string;
    tooltip?: string;
    children?: ReactNode;
}) {
    const resolvedHelp = help ?? tooltip;
    if (children) {
        return (
            <label className="block">
                <span className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-slate-600 uppercase dark:text-slate-300">
                    <span>{label}</span>
                    {resolvedHelp && <HelpTooltip text={resolvedHelp} />}
                </span>
                {children}
            </label>
        );
    }
    return (
        <span className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>{label}</span>
            {resolvedHelp && <HelpTooltip text={resolvedHelp} />}
        </span>
    );
}

export function Input({
    label,
    help,
    value,
    onChange,
}: {
    label: string;
    help?: string;
    value: string;
    onChange: (value: string) => void;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <input
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="admin-input mt-1 h-9 w-full rounded-lg px-3 text-sm outline-none"
            />
        </label>
    );
}

export function TextArea({
    label,
    help,
    value,
    onChange,
    className,
}: {
    label: string;
    help?: string;
    value: string;
    onChange: (value: string) => void;
    className?: string;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <textarea
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className={cx(
                    'admin-input mt-1 w-full rounded-lg px-3 py-2 text-sm leading-6 outline-none',
                    className,
                )}
            />
        </label>
    );
}

export function Select({
    label,
    help,
    value,
    options,
    onChange,
}: {
    label: string;
    help?: string;
    value: string;
    options: { label: string; value: string }[];
    onChange: (value: string) => void;
}) {
    return (
        <label className="block">
            <FieldLabel label={label} help={help} />
            <select
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="admin-input mt-1 h-9 w-full rounded-lg px-3 text-sm outline-none"
            >
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        </label>
    );
}

export function SegmentedControl<T extends string>({
    items,
    value,
    onChange,
}: {
    items: { label: string; value: T }[];
    value: T;
    onChange: (value: T) => void;
}) {
    return (
        <div className="admin-subpanel flex rounded-lg p-0.5">
            {items.map((item) => (
                <button
                    key={item.value}
                    type="button"
                    aria-pressed={item.value === value}
                    onClick={() => onChange(item.value)}
                    className={cx(
                        'rounded-md px-2.5 py-1 text-xs font-semibold transition',
                        item.value === value
                            ? 'bg-[var(--accent-primary)] text-white shadow-2xs'
                            : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
                    )}
                >
                    {item.label}
                </button>
            ))}
        </div>
    );
}

export function EmptyBox({ text }: { text: string }) {
    return (
        <div className="admin-subpanel rounded-lg border-dashed p-6 text-center text-xs text-slate-500 dark:text-slate-400">
            {text}
        </div>
    );
}

export function PaginationBar({
    page,
    pages,
    total,
    onPageChange,
}: {
    page: number;
    pages: number;
    total: number;
    onPageChange: (page: number) => void;
}) {
    const { t } = useI18n();
    return (
        <div className="flex items-center justify-between border-t border-slate-200 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <span>{t('common.recordsCount', { count: total })}</span>
            <div className="flex items-center gap-1.5">
                <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => onPageChange(page - 1)}
                    className="admin-subpanel rounded px-2 py-1 text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                    ←
                </button>
                <span>
                    {page} / {Math.max(pages, 1)}
                </span>
                <button
                    type="button"
                    disabled={page >= pages}
                    onClick={() => onPageChange(page + 1)}
                    className="admin-subpanel rounded px-2 py-1 text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                    →
                </button>
            </div>
        </div>
    );
}

export function QualityBlockNotice({
    block,
    className = 'mb-3',
}: {
    block: QualityControlBlock;
    className?: string;
}) {
    const msg = block.message ?? block.reason;
    if (!msg) return null;
    const canEnable = scopesNeedingManualMode(block.config).length > 0;
    return (
        <div
            className={cx(
                className,
                'flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200',
            )}
            data-quality-block=""
        >
            <span>{msg}</span>
            {canEnable && (
                <EnableManualModeButton
                    config={block.config}
                    onDone={() => block.reload()}
                />
            )}
        </div>
    );
}
