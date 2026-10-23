import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, X } from 'lucide-react';

export interface ConfirmDialogProps {
    open: boolean;
    title: string;
    description: React.ReactNode;
    confirmLabel: string;
    cancelLabel?: string;
    tone?: 'danger' | 'primary' | 'amber';
    danger?: boolean;
    requireTypedText?: string;
    typedPlaceholder?: string;
    busy?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

export function ConfirmDialog({
    open,
    title,
    description,
    confirmLabel,
    cancelLabel = 'Отмена',
    tone = 'primary',
    danger = false,
    requireTypedText,
    typedPlaceholder,
    busy = false,
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {
    const [typed, setTyped] = useState('');
    const effectiveTone = danger ? 'danger' : tone;

    useEffect(() => {
        if (!open) {
            setTyped('');
            return;
        }
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !busy) {
                onCancel();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, busy, onCancel]);

    if (!open) {
        return null;
    }

    const canConfirm = !requireTypedText || typed.trim() === requireTypedText;
    const confirmClasses =
        effectiveTone === 'danger'
            ? 'bg-red-600 text-white hover:bg-red-700'
            : effectiveTone === 'amber'
              ? 'bg-amber-600 text-white hover:bg-amber-700'
              : 'bg-[#2563eb] text-white hover:bg-blue-700';

    const dialog = (
        <div
            data-confirm-dialog
            className="fixed inset-0 z-[9995] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-[2px]"
            onClick={() => {
                if (!busy) onCancel();
            }}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label={title}
                onClick={(event) => event.stopPropagation()}
                className="admin-panel w-full max-w-md rounded-xl p-5 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                        <span
                            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                                effectiveTone === 'danger'
                                    ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                                    : effectiveTone === 'amber'
                                      ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                                      : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                            }`}
                        >
                            <AlertTriangle className="h-5 w-5" />
                        </span>
                        <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                            {title}
                        </h3>
                    </div>
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={busy}
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                    {description}
                </div>

                {requireTypedText && (
                    <div className="mt-4">
                        <input
                            type="text"
                            value={typed}
                            onChange={(event) => setTyped(event.target.value)}
                            placeholder={typedPlaceholder ?? requireTypedText}
                            data-confirm-input
                            className="admin-input w-full rounded-lg px-3 py-2 font-mono text-sm focus:border-red-500 focus:outline-none"
                        />
                    </div>
                )}

                <div className="mt-5 flex items-center justify-end gap-2">
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={busy}
                        className="admin-subpanel rounded-lg px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={busy || !canConfirm}
                        data-confirm-submit
                        className={`rounded-lg px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${confirmClasses}`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );

    if (typeof document !== 'undefined' && document.body) {
        return createPortal(dialog, document.body);
    }
    return dialog;
}

export default ConfirmDialog;
