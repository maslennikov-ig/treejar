import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '@/i18n';

const TOOLTIP_WIDTH = 288;
const VIEWPORT_MARGIN = 8;

interface TooltipPosition {
    top: number;
    left: number;
    width: number;
    placement: 'top' | 'bottom';
}

function computeTooltipPosition(rect: DOMRect): TooltipPosition {
    const viewportWidth = typeof window === 'undefined' ? 1024 : window.innerWidth;
    const width = Math.min(TOOLTIP_WIDTH, viewportWidth - VIEWPORT_MARGIN * 2);
    const centered = rect.left + rect.width / 2 - width / 2;
    const left = Math.max(VIEWPORT_MARGIN, Math.min(centered, viewportWidth - width - VIEWPORT_MARGIN));
    // Flip below the trigger when there is not enough room above it.
    const placement: TooltipPosition['placement'] = rect.top > 180 ? 'top' : 'bottom';
    const top = placement === 'top' ? rect.top - 8 : rect.bottom + 8;
    return { top, left, width, placement };
}

/**
 * Accessible "?" help icon. Opens instantly on hover, focus or click (no native
 * `title` delay), closes on mouse leave, blur or Escape, and is positioned with
 * `position: fixed` + viewport clamping so it never clips inside scroll panes.
 */
export function HelpTooltip({
    text,
    label,
    className,
    tone = 'light',
}: {
    text: string;
    label?: string;
    className?: string;
    tone?: 'light' | 'dark';
}) {
    const [open, setOpen] = useState(false);
    const [position, setPosition] = useState<TooltipPosition | null>(null);
    const buttonRef = useRef<HTMLButtonElement | null>(null);
    const tooltipId = useId();

    const show = useCallback(() => {
        const element = buttonRef.current;
        if (element) {
            setPosition(computeTooltipPosition(element.getBoundingClientRect()));
        }
        setOpen(true);
    }, []);

    const hide = useCallback(() => setOpen(false), []);

    useEffect(() => {
        if (!open || typeof document === 'undefined') return undefined;
        function onKeyDown(event: KeyboardEvent) {
            if (event.key === 'Escape') setOpen(false);
        }
        function onScroll() {
            setOpen(false);
        }
        document.addEventListener('keydown', onKeyDown);
        window.addEventListener('scroll', onScroll, true);
        window.addEventListener('resize', onScroll);
        return () => {
            document.removeEventListener('keydown', onKeyDown);
            window.removeEventListener('scroll', onScroll, true);
            window.removeEventListener('resize', onScroll);
        };
    }, [open]);

    function handleClick(event: ReactMouseEvent<HTMLButtonElement>) {
        // Do not toggle surrounding <label>/row handlers.
        event.preventDefault();
        event.stopPropagation();
        show();
    }

    const style: CSSProperties | undefined = position
        ? {
            position: 'fixed',
            top: position.top,
            left: position.left,
            width: position.width,
            transform: position.placement === 'top' ? 'translateY(-100%)' : undefined,
            zIndex: 9999,
            opacity: 1,
        }
        : undefined;

    const tooltipNode = open && position ? (
        <span
            id={tooltipId}
            role="tooltip"
            style={style}
            className="pointer-events-none whitespace-normal rounded-md border border-[#1e293b] bg-[#0b1c30] px-3 py-2 text-left text-xs font-normal normal-case leading-5 tracking-normal text-white opacity-100 shadow-xl transition-opacity duration-[40ms]"
        >
            {text}
        </span>
    ) : null;

    return (
        <span className={['relative inline-flex align-middle', className].filter(Boolean).join(' ')}>
            <button
                ref={buttonRef}
                type="button"
                aria-label={label ?? text}
                aria-describedby={open ? tooltipId : undefined}
                aria-expanded={open}
                data-tooltip={text}
                onMouseEnter={show}
                onMouseLeave={hide}
                onFocus={show}
                onBlur={hide}
                onClick={handleClick}
                className={
                    tone === 'dark'
                        ? 'inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-slate-500 text-[10px] font-bold leading-none text-slate-300 hover:border-emerald-300 hover:text-emerald-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400'
                        : 'inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[#9aa3b5] text-[10px] font-bold leading-none text-[#596179] hover:border-[#0058be] hover:text-[#0058be] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0058be]'
                }
            >
                ?
            </button>
            {tooltipNode && (typeof document !== 'undefined' && document.body ? createPortal(tooltipNode, document.body) : tooltipNode)}
        </span>
    );
}

function readCollapsed(storageKey: string, fallback: boolean): boolean {
    try {
        if (typeof window === 'undefined' || !window.localStorage) return fallback;
        const stored = window.localStorage.getItem(`treejar_admin_banner_${storageKey}`);
        if (stored === '1') return true;
        if (stored === '0') return false;
    } catch {
        // Storage may be unavailable (private mode); keep the default.
    }
    return fallback;
}

function writeCollapsed(storageKey: string, value: boolean): void {
    try {
        if (typeof window === 'undefined' || !window.localStorage) return;
        window.localStorage.setItem(`treejar_admin_banner_${storageKey}`, value ? '1' : '0');
    } catch {
        // Ignore storage failures.
    }
}

/**
 * Collapsible section guide shown at the top of every dashboard view: what the
 * section does and how it connects to the live Noor runtime.
 */
export function SectionInfoBanner({
    storageKey,
    title,
    description,
    runtime,
    actions,
    defaultCollapsed = false,
}: {
    storageKey: string;
    title: string;
    description: string;
    runtime?: string;
    actions?: ReactNode;
    defaultCollapsed?: boolean;
}) {
    const { t } = useI18n();
    const [collapsed, setCollapsed] = useState(() => readCollapsed(storageKey, defaultCollapsed));
    const bodyId = useId();

    function toggle() {
        setCollapsed((current) => {
            const next = !current;
            writeCollapsed(storageKey, next);
            return next;
        });
    }

    return (
        <div
            data-section-banner={storageKey}
            className="border-b border-[#dbe5ff] bg-[#f3f7ff] px-6 py-3 text-sm text-[#27324a]"
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#0058be] text-[11px] font-bold text-white">
                        i
                    </span>
                    <div className="min-w-0">
                        <p className="font-semibold text-[#0b1c30]">{title}</p>
                        {!collapsed && (
                            <div id={bodyId} className="mt-1 space-y-1 leading-6">
                                <p>{description}</p>
                                {runtime && (
                                    <p className="text-[#3f465c]">
                                        <span className="font-medium text-[#0b1c30]">{t('banner.runtimeLabel')}</span> {runtime}
                                    </p>
                                )}
                                {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
                            </div>
                        )}
                    </div>
                </div>
                <button
                    type="button"
                    onClick={toggle}
                    aria-expanded={!collapsed}
                    aria-controls={bodyId}
                    className="shrink-0 rounded-md border border-[#c6d3f5] bg-white px-2.5 py-1 text-xs font-medium text-[#0058be] hover:bg-[#eaf1ff]"
                >
                    {collapsed ? t('banner.expand') : t('banner.collapse')}
                </button>
            </div>
        </div>
    );
}

export default HelpTooltip;
