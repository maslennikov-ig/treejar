import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type AdminTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'treejar_admin_theme';

export interface ThemeContextValue {
    theme: AdminTheme;
    setTheme: (next: AdminTheme) => void;
    toggleTheme: () => void;
}

function readStoredTheme(fallback: AdminTheme = 'light'): AdminTheme {
    try {
        const stored = globalThis.localStorage?.getItem(THEME_STORAGE_KEY);
        if (stored === 'light' || stored === 'dark') {
            return stored;
        }
    } catch {
        // Ignore storage errors in SSR/test environments.
    }
    return fallback;
}

function applyDocumentTheme(theme: AdminTheme): void {
    if (typeof document === 'undefined') {
        return;
    }
    const root = document.documentElement;
    const body = document.body;
    root.setAttribute('data-theme', theme);
    if (theme === 'dark') {
        root.classList.add('dark');
        body?.classList.add('dark');
    } else {
        root.classList.remove('dark');
        body?.classList.remove('dark');
    }
}

const ThemeContext = createContext<ThemeContextValue>({
    theme: 'light',
    setTheme: () => {},
    toggleTheme: () => {},
});

export function ThemeProvider({
    initialTheme,
    children,
}: {
    initialTheme?: AdminTheme;
    children: React.ReactNode;
}) {
    const [theme, setThemeState] = useState<AdminTheme>(() =>
        initialTheme ?? readStoredTheme('light'),
    );

    useEffect(() => {
        applyDocumentTheme(theme);
    }, [theme]);

    const setTheme = (next: AdminTheme) => {
        setThemeState(next);
        try {
            globalThis.localStorage?.setItem(THEME_STORAGE_KEY, next);
        } catch {
            // Ignore storage errors in restricted environments.
        }
        applyDocumentTheme(next);
    };

    const toggleTheme = () => {
        setTheme(theme === 'light' ? 'dark' : 'light');
    };

    const value = useMemo<ThemeContextValue>(
        () => ({ theme, setTheme, toggleTheme }),
        [theme],
    );

    return (
        <ThemeContext.Provider value={value}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme(): ThemeContextValue {
    return useContext(ThemeContext);
}
