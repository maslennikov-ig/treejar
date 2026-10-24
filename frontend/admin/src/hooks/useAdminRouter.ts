import { useCallback, useEffect, useState } from 'react';
import type { AdminViewId } from '@/components/Sidebar';

export interface AdminRouteState {
    view: AdminViewId;
    tab?: string;
    id?: string;
    filter?: string;
    language?: string;
    status?: string;
    stage?: string;
    escalation?: string;
}

const VALID_VIEWS: ReadonlySet<AdminViewId> = new Set([
    'overview',
    'conversations',
    'queuesQuality',
    'knowledge',
    'botRules',
    'catalog',
    'reports',
    'settings',
    'auditSystem',
    'guide',
    'acceptance',
]);

function normalizeView(rawView: string | null): { view: AdminViewId; defaultTab?: string } {
    if (!rawView) {
        return { view: 'conversations' };
    }
    if (rawView === 'queues') {
        return { view: 'queuesQuality', defaultTab: 'escalations' };
    }
    if (rawView === 'quality') {
        return { view: 'queuesQuality', defaultTab: 'ai_rubric' };
    }
    if (rawView === 'audit') {
        return { view: 'auditSystem', defaultTab: 'audit' };
    }
    if (rawView === 'support') {
        return { view: 'auditSystem', defaultTab: 'system' };
    }
    if (rawView === 'help' || rawView === 'docs') {
        return { view: 'guide' };
    }
    if (VALID_VIEWS.has(rawView as AdminViewId)) {
        return { view: rawView as AdminViewId };
    }
    return { view: 'conversations' };
}

export function parseAdminRoute(search: string): AdminRouteState {
    const params = new URLSearchParams(search);
    const { view, defaultTab } = normalizeView(params.get('view'));
    return {
        view,
        tab: params.get('tab') || defaultTab || undefined,
        id: params.get('id') || undefined,
        filter: params.get('filter') || undefined,
        language: params.get('language') || undefined,
        status: params.get('status') || undefined,
        stage: params.get('stage') || undefined,
        escalation: params.get('escalation') || undefined,
    };
}

export const parseAdminUrl = parseAdminRoute;

export function buildAdminSearch(state: AdminRouteState): string {
    const params = new URLSearchParams();
    params.set('view', state.view);
    if (state.tab) params.set('tab', state.tab);
    if (state.id) params.set('id', state.id);
    if (state.filter) params.set('filter', state.filter);
    if (state.language) params.set('language', state.language);
    if (state.status) params.set('status', state.status);
    if (state.stage) params.set('stage', state.stage);
    if (state.escalation) params.set('escalation', state.escalation);
    const str = params.toString();
    return str ? `?${str}` : '';
}

export function useAdminRouter(defaultView: AdminViewId = 'conversations') {
    const [route, setRouteState] = useState<AdminRouteState>(() => {
        if (typeof window === 'undefined') {
            return { view: defaultView };
        }
        if (!window.location.search) {
            return { view: defaultView };
        }
        return parseAdminRoute(window.location.search);
    });

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const onPopState = () => {
            setRouteState(parseAdminRoute(window.location.search));
        };
        window.addEventListener('popstate', onPopState);
        return () => window.removeEventListener('popstate', onPopState);
    }, []);

    const navigate = useCallback((next: Partial<AdminRouteState> & { view?: AdminViewId }, replace = false) => {
        setRouteState((current) => {
            const viewChanged = next.view && next.view !== current.view;
            const merged: AdminRouteState = viewChanged
                ? {
                      view: next.view!,
                      tab: next.tab,
                      id: next.id,
                      filter: next.filter,
                      language: next.language,
                      status: next.status,
                      stage: next.stage,
                      escalation: next.escalation,
                  }
                : {
                      ...current,
                      ...next,
                  };
            if (typeof window !== 'undefined' && window.history) {
                const search = buildAdminSearch(merged);
                const url = `${window.location.pathname}${search}${window.location.hash || ''}`;
                try {
                    if (replace) {
                        window.history.replaceState(null, '', url);
                    } else {
                        window.history.pushState(null, '', url);
                    }
                } catch {
                    // Ignore in restricted environments.
                }
            }
            return merged;
        });
    }, []);

    return { route, navigate };
}
