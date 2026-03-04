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
                manualChunks: {
                    vendor: ['react', 'react-dom'],
                    charts: ['recharts'],
                    motion: ['framer-motion'],
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
