import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export interface DrawerProps {
    open: boolean;
    title: string;
    subtitle?: string;
    widthClass?: string;
    widthClassName?: string;
    onClose: () => void;
    children: React.ReactNode;
}

export function Drawer({
    open,
    title,
    subtitle,
    widthClass,
    widthClassName,
    onClose,
    children,
}: DrawerProps) {
    const resolvedWidth = widthClassName || widthClass || 'max-w-lg';

    useEffect(() => {
        if (!open) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose]);

    if (!open) {
        return null;
    }

    const content = (
        <div
            data-drawer
            className="fixed inset-0 z-[9980] flex justify-end bg-slate-950/40 backdrop-blur-[1px]"
            onClick={onClose}
        >
            <aside
                role="dialog"
                aria-modal="true"
                aria-label={title}
                onClick={(event) => event.stopPropagation()}
                className={`admin-panel flex h-full w-full ${resolvedWidth} flex-col border-l shadow-2xl`}
            >
                <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                    <div className="min-w-0">
                        <h3 className="truncate text-base font-bold text-slate-900 dark:text-slate-100">
                            {title}
                        </h3>
                        {subtitle && (
                            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                {subtitle}
                            </p>
                        )}
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        data-drawer-close
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
            </aside>
        </div>
    );

    if (typeof document !== 'undefined' && document.body) {
        return createPortal(content, document.body);
    }
    return content;
}

export default Drawer;
