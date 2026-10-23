import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { CheckCircle2, AlertTriangle, Info, X } from 'lucide-react';

export type ToastTone = 'success' | 'error' | 'info';

export interface ToastItem {
    id: string;
    tone: ToastTone;
    message: string;
}

export interface ToastContextValue {
    toasts: ToastItem[];
    showToast: (toast: { tone?: ToastTone; message: string }) => void;
    pushToast: (toast: { tone?: ToastTone; message: string }) => void;
    dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
    toasts: [],
    showToast: () => {},
    pushToast: () => {},
    dismissToast: () => {},
});

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);

    const dismissToast = useCallback((id: string) => {
        setToasts((current) => current.filter((item) => item.id !== id));
    }, []);

    const showToast = useCallback(
        ({ tone = 'success', message }: { tone?: ToastTone; message: string }) => {
            const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
            setToasts((current) => [...current.slice(-3), { id, tone, message }]);
            if (typeof window !== 'undefined') {
                window.setTimeout(() => {
                    dismissToast(id);
                }, 3800);
            }
        },
        [dismissToast],
    );

    const value = useMemo(
        () => ({ toasts, showToast, pushToast: showToast, dismissToast }),
        [toasts, showToast, dismissToast],
    );

    return (
        <ToastContext.Provider value={value}>
            {children}
            {toasts.length > 0 && (
                <div
                    data-toast-container
                    className="fixed right-4 bottom-4 z-[9990] flex flex-col gap-2"
                >
                    {toasts.map((toast) => (
                        <div
                            key={toast.id}
                            role="status"
                            className={`admin-panel flex max-w-sm items-center gap-2.5 rounded-xl px-4 py-3 text-xs font-medium shadow-xl ${
                                toast.tone === 'error'
                                    ? 'border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/90 dark:text-red-100'
                                    : toast.tone === 'info'
                                      ? 'border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/90 dark:text-blue-100'
                                      : 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/90 dark:text-emerald-100'
                            }`}
                        >
                            {toast.tone === 'error' ? (
                                <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
                            ) : toast.tone === 'info' ? (
                                <Info className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
                            ) : (
                                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                            )}
                            <span className="flex-1 leading-snug">{toast.message}</span>
                            <button
                                type="button"
                                onClick={() => dismissToast(toast.id)}
                                className="rounded p-0.5 opacity-70 hover:opacity-100"
                            >
                                <X className="h-3.5 w-3.5" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </ToastContext.Provider>
    );
}

export function useToast(): ToastContextValue {
    return useContext(ToastContext);
}
