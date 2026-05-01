export type AppRouteMode = 'dashboard' | 'acceptance-public';

export function getAppRouteMode(pathname: string = globalThis.location?.pathname ?? ''): AppRouteMode {
    return pathname.startsWith('/client-self-test') ? 'acceptance-public' : 'dashboard';
}
