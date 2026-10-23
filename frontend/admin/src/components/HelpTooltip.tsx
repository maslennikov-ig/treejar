import React, { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { useI18n } from '../i18n';

export interface HelpTooltipProps {
    text: string;
    label?: string;
    className?: string;
}

interface PopoverPosition {
    top: number;
    left: number;
    placement: 'top' | 'bottom';
}

const POPOVER_WIDTH = 288;
const VIEWPORT_MARGIN = 12;

export function HelpTooltip({ text, label = '?', className = '' }: HelpTooltipProps) {
    const id = useId();
    const triggerRef = useRef<HTMLButtonElement | null>(null);
    const [open, setOpen] = useState(false);
    const [pinned, setPinned] = useState(false);
    const [position, setPosition] = useState<PopoverPosition>({
        top: 0,
        left: 0,
        placement: 'top',
    });

    const updatePosition = () => {
        const trigger = triggerRef.current;
        if (!trigger || typeof window === 'undefined') {
            return;
        }
        const rect = trigger.getBoundingClientRect();
        const half = POPOVER_WIDTH / 2;
        const center = rect.left + rect.width / 2;
        const maxLeft = Math.max(
            VIEWPORT_MARGIN + half,
            window.innerWidth - VIEWPORT_MARGIN - half,
        );
        const left = Math.min(Math.max(center, VIEWPORT_MARGIN + half), maxLeft);
        const placement = rect.top > 130 ? 'top' : 'bottom';
        const top = placement === 'top' ? rect.top - 8 : rect.bottom + 8;
        setPosition({ top, left, placement });
    };

    const show = () => {
        updatePosition();
        setOpen(true);
    };

    useEffect(() => {
        if (!open) {
            return;
        }
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setPinned(false);
                setOpen(false);
            }
        };
        const onPointerDown = (event: MouseEvent) => {
            if (!triggerRef.current?.contains(event.target as Node)) {
                setPinned(false);
                setOpen(false);
            }
        };
        const onViewportChange = () => updatePosition();
        window.addEventListener('keydown', onKeyDown);
        window.addEventListener('mousedown', onPointerDown);
        window.addEventListener('scroll', onViewportChange, true);
        window.addEventListener('resize', onViewportChange);
        return () => {
            window.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('mousedown', onPointerDown);
            window.removeEventListener('scroll', onViewportChange, true);
            window.removeEventListener('resize', onViewportChange);
        };
    }, [open]);

    const visible = open || pinned;
    const popover = (
        <span
            id={id}
            role="tooltip"
            aria-hidden={!visible}
            style={{
                position: 'fixed',
                top: `${position.top}px`,
                left: `${position.left}px`,
                width: `${POPOVER_WIDTH}px`,
                maxWidth: 'calc(100vw - 24px)',
                zIndex: 9999,
                opacity: visible ? 1 : 0,
                transform:
                    position.placement === 'top'
                        ? 'translate(-50%, -100%)'
                        : 'translate(-50%, 0)',
            }}
            className={`admin-tooltip pointer-events-none rounded-lg px-3 py-2 text-left text-xs font-normal normal-case tracking-normal leading-relaxed shadow-xl transition-opacity duration-[40ms] ${
                visible ? 'opacity-100' : 'opacity-0'
            }`}
        >
            {text}
        </span>
    );

    return (
        <span className={`relative inline-flex items-center align-middle ${className}`}>
            <button
                ref={triggerRef}
                type="button"
                aria-label={text}
                aria-expanded={visible}
                aria-describedby={visible ? id : undefined}
                data-tooltip={text}
                onMouseEnter={show}
                onMouseLeave={() => {
                    if (!pinned) {
                        setOpen(false);
                    }
                }}
                onFocus={show}
                onBlur={() => {
                    if (!pinned) {
                        setOpen(false);
                    }
                }}
                onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    updatePosition();
                    setPinned((current) => {
                        const next = !current;
                        setOpen(next);
                        return next;
                    });
                }}
                className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-[10px] font-bold leading-none text-slate-600 transition-colors duration-[40ms] hover:border-[#2170e4] hover:bg-[#2170e4] hover:text-white focus:border-[#2170e4] focus:bg-[#2170e4] focus:text-white focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
                {label}
            </button>
            {typeof document !== 'undefined' && document.body
                ? createPortal(popover, document.body)
                : popover}
        </span>
    );
}

export interface SectionInfoBannerProps {
    storageKey: string;
    title: string;
    description: string;
    runtime: string;
    actions?: React.ReactNode;
    defaultCollapsed?: boolean;
}

export function SectionInfoBanner({
    storageKey,
    title,
    description,
    runtime,
    actions,
    defaultCollapsed = false,
}: SectionInfoBannerProps) {
    const { t } = useI18n();
    const fullKey = `treejar_admin_banner_${storageKey}`;
    const [collapsed, setCollapsed] = useState<boolean>(() => {
        try {
            const stored = globalThis.localStorage?.getItem(fullKey);
            if (stored === '1') return true;
            if (stored === '0') return false;
            return defaultCollapsed;
        } catch {
            return defaultCollapsed;
        }
    });

    const toggle = () => {
        setCollapsed((current) => {
            const next = !current;
            try {
                globalThis.localStorage?.setItem(fullKey, next ? '1' : '0');
            } catch {
                // Ignore storage quota / privacy mode failures.
            }
            return next;
        });
    };

    return (
        <section
            data-section-banner={storageKey}
            className="admin-panel mb-3 rounded-xl px-3.5 py-2 shadow-2xs"
        >
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-blue-50 text-xs font-bold text-[#2170e4] dark:bg-blue-950/60 dark:text-blue-400">
                        i
                    </span>
                    <h2 className="truncate text-xs font-bold text-slate-900 dark:text-slate-100">
                        {title}
                    </h2>
                    <HelpTooltip text={`${description} ${t('banner.runtimePrefix')} ${runtime}`} />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {actions}
                    <button
                        type="button"
                        onClick={toggle}
                        aria-expanded={!collapsed}
                        className="admin-subpanel rounded-lg px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                        {collapsed ? t('banner.expand') : t('banner.collapse')}
                    </button>
                </div>
            </div>
            {!collapsed && (
                <div className="mt-2 grid gap-2 border-t border-slate-100 pt-2 text-xs leading-relaxed text-slate-600 md:grid-cols-[1.5fr_1fr] dark:border-slate-800 dark:text-slate-300">
                    <p>{description}</p>
                    <p className="admin-subpanel rounded-lg px-3 py-1.5 text-[11px]">
                        <span className="font-semibold text-slate-900 dark:text-slate-100">
                            {t('banner.runtimePrefix')}{' '}
                        </span>
                        {runtime}
                    </p>
                </div>
            )}
        </section>
    );
}
