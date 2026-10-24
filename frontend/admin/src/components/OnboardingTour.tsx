import { useCallback, useEffect, useRef } from 'react';
import { driver } from 'driver.js';
import type { DriveStep, Driver } from 'driver.js';
import type { AdminViewId } from '@/components/Sidebar';
import { TOUR_TRACKS, pickText } from '@/data/adminGuideData';
import type { TourTrackId } from '@/data/adminGuideData';
import type { AdminRouteState } from '@/hooks/useAdminRouter';
import { useI18n } from '@/i18n';

export const TOUR_SEEN_STORAGE_KEY = 'treejar_admin_tour_seen_v1';

const VALID_TRACKS: ReadonlySet<TourTrackId> = new Set([
    'full',
    'daily_ops',
    'teach_bot',
    'quality_settings',
]);

export function resolveTourTrackParam(rawValue: string | null): TourTrackId | null {
    if (!rawValue) return null;
    const normalized = rawValue.trim();
    if (normalized === '1' || normalized.toLowerCase() === 'true') {
        return 'full';
    }
    if (VALID_TRACKS.has(normalized as TourTrackId)) {
        return normalized as TourTrackId;
    }
    return null;
}

function hasSeenOnboardingTour(): boolean {
    try {
        if (typeof window === 'undefined' || !window.localStorage) return true;
        return window.localStorage.getItem(TOUR_SEEN_STORAGE_KEY) === '1';
    } catch {
        return true;
    }
}

function markOnboardingTourSeen(): void {
    try {
        if (typeof window === 'undefined' || !window.localStorage) return;
        window.localStorage.setItem(TOUR_SEEN_STORAGE_KEY, '1');
    } catch {
        // Ignore storage write errors in private/restricted browsers.
    }
}

export interface UseOnboardingTourOptions {
    navigate: (next: Partial<AdminRouteState> & { view?: AdminViewId }, replace?: boolean) => void;
}

export function useOnboardingTour({ navigate }: UseOnboardingTourOptions) {
    const { lang, t } = useI18n();
    const driverRef = useRef<Driver | null>(null);
    const rafRef = useRef<number | null>(null);

    const stopActiveTour = useCallback(() => {
        if (rafRef.current !== null && typeof window !== 'undefined') {
            window.cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
        }
        if (driverRef.current) {
            try {
                driverRef.current.destroy();
            } catch {
                // Ignore cleanup errors.
            }
            driverRef.current = null;
        }
    }, []);

    const startTour = useCallback(
        (trackId: TourTrackId = 'full') => {
            if (typeof window === 'undefined' || typeof document === 'undefined') {
                return;
            }

            stopActiveTour();
            markOnboardingTourSeen();

            const specs = TOUR_TRACKS[trackId] ?? TOUR_TRACKS.full;
            if (specs.length === 0) return;

            const navigateAndMove = (drv: Driver, targetIndex: number) => {
                if (targetIndex < 0 || targetIndex >= specs.length) {
                    drv.destroy();
                    return;
                }
                const targetSpec = specs[targetIndex];
                if (targetSpec.route) {
                    navigate(targetSpec.route);
                    rafRef.current = window.requestAnimationFrame(() => {
                        rafRef.current = window.requestAnimationFrame(() => {
                            rafRef.current = null;
                            if (drv.isActive()) {
                                drv.moveTo(targetIndex);
                            }
                        });
                    });
                } else {
                    drv.moveTo(targetIndex);
                }
            };

            const steps: DriveStep[] = specs.map((spec) => ({
                ...(spec.selector ? { element: spec.selector } : {}),
                popover: {
                    title: pickText(spec.title, lang),
                    description: pickText(spec.description, lang),
                    ...(spec.side ? { side: spec.side } : {}),
                    ...(spec.align ? { align: spec.align } : {}),
                },
            }));

            const drv = driver({
                animate: true,
                smoothScroll: true,
                allowClose: true,
                allowKeyboardControl: true,
                overlayOpacity: 0.62,
                stagePadding: 8,
                stageRadius: 12,
                popoverOffset: 12,
                waitForElement: 700,
                popoverClass: 'noor-tour-popover',
                showProgress: true,
                progressText: t('tour.progress'),
                nextBtnText: t('tour.btnNext'),
                prevBtnText: t('tour.btnPrev'),
                doneBtnText: t('tour.btnDone'),
                closeBtnLabel: t('tour.btnClose'),
                steps,
                onNextClick: (_el, _step, opts) => {
                    const current = opts.state.activeIndex ?? 0;
                    if (current + 1 >= specs.length) {
                        opts.driver.destroy();
                        return;
                    }
                    navigateAndMove(opts.driver, current + 1);
                },
                onPrevClick: (_el, _step, opts) => {
                    const current = opts.state.activeIndex ?? 0;
                    if (current <= 0) return;
                    navigateAndMove(opts.driver, current - 1);
                },
                onDestroyed: () => {
                    if (driverRef.current === drv) {
                        driverRef.current = null;
                    }
                },
            });

            driverRef.current = drv;

            const firstSpec = specs[0];
            if (firstSpec.route) {
                navigate(firstSpec.route);
                rafRef.current = window.requestAnimationFrame(() => {
                    rafRef.current = window.requestAnimationFrame(() => {
                        rafRef.current = null;
                        drv.drive(0);
                    });
                });
            } else {
                drv.drive(0);
            }
        },
        [lang, navigate, stopActiveTour, t],
    );

    // Auto-start on explicit ?tour=... parameter or on first browser visit.
    useEffect(() => {
        if (typeof window === 'undefined' || typeof document === 'undefined') {
            return;
        }

        const params = new URLSearchParams(window.location.search);
        if (params.get('notour') === '1') {
            return;
        }

        const requestedTrack = resolveTourTrackParam(params.get('tour'));
        if (requestedTrack) {
            params.delete('tour');
            const nextQuery = params.toString();
            const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}${window.location.hash || ''}`;
            try {
                window.history.replaceState(null, '', nextUrl);
            } catch {
                // Ignore history errors in restricted environments.
            }
            const timer = window.setTimeout(() => {
                startTour(requestedTrack);
            }, 280);
            return () => window.clearTimeout(timer);
        }

        if (!hasSeenOnboardingTour()) {
            const timer = window.setTimeout(() => {
                startTour('full');
            }, 450);
            return () => window.clearTimeout(timer);
        }

        return undefined;
        // Run once on initial mount so switching RU/EN mid-session does not re-trigger auto-start.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => () => stopActiveTour(), [stopActiveTour]);

    return {
        startTour,
        stopTour: stopActiveTour,
    };
}
