import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig({
    plugins: [react(), tailwindcss()],
    base: '/dashboard/',
    resolve: {
        alias: {
            '@': path.resolve(import.meta.dirname, './src'),
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    const normalizedId = id.replaceAll(path.sep, '/');
                    if (normalizedId.endsWith('/src/i18n.tsx')) {
                        return 'i18n';
                    }
                    if (!normalizedId.includes('/node_modules/')) {
                        return undefined;
                    }
                    if (
                        normalizedId.includes('/node_modules/react/') ||
                        normalizedId.includes('/node_modules/react-dom/')
                    ) {
                        return 'vendor';
                    }
                    if (normalizedId.includes('/node_modules/recharts/')) {
                        return 'charts';
                    }
                    if (normalizedId.includes('/node_modules/framer-motion/')) {
                        return 'motion';
                    }
                    if (normalizedId.includes('/node_modules/lucide-react/')) {
                        return 'icons';
                    }
                    if (normalizedId.includes('/node_modules/driver.js/')) {
                        return 'tour';
                    }
                    return undefined;
                },
            },
        },
    },
    server: {
        port: 3001,
        proxy: {
            '/api': 'http://localhost:8000',
        },
    },
});
