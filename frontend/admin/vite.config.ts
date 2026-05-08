import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig({
    plugins: [react(), tailwindcss()],
    base: '/dashboard/',
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks(id) {
                    const normalizedId = id.replaceAll(path.sep, '/');
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
