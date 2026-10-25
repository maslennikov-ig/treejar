let redirectingToLogin = false;

export function buildExpiredSessionLoginUrl(
    pathname: string,
    search: string = '',
): string {
    const safePath = pathname.startsWith('/dashboard')
        ? pathname === '/dashboard'
            ? '/dashboard/'
            : pathname
        : '/dashboard/';
    const target = `${safePath}${search || ''}`;
    const params = new URLSearchParams();
    if (target !== '/dashboard/') {
        params.set('next', target);
    }
    params.set('reason', 'session_expired');
    return `/admin/login?${params.toString()}`;
}

export function redirectOnAdminUnauthorized(
    response: Pick<Response, 'status'>,
): boolean {
    if (response.status !== 401) {
        return false;
    }
    const loc = globalThis.location;
    if (
        !loc ||
        typeof loc.pathname !== 'string' ||
        !loc.pathname.startsWith('/dashboard') ||
        typeof loc.assign !== 'function'
    ) {
        return false;
    }
    if (redirectingToLogin) {
        return true;
    }
    redirectingToLogin = true;
    loc.assign(buildExpiredSessionLoginUrl(loc.pathname, loc.search ?? ''));
    return true;
}

export function resetAdminUnauthorizedRedirectForTests(): void {
    redirectingToLogin = false;
}
