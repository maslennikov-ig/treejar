import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const STUBS = new Map([
    ['@/hooks/useMetrics', `
        export function useMetrics() {
            return {
                data: null,
                timeseries: null,
                loading: false,
                error: 'metrics failed',
                refetch: () => {},
            };
        }
    `],
    ['@/components/OperatorCenter', `
        import React from 'react';
        export default function OperatorCenter() {
            return React.createElement('div', { id: 'operator-center-marker' }, 'operator center');
        }
    `],
    ['@/components/StatCard', `
        export default function StatCard() {
            return null;
        }
    `],
    ['@/components/charts/ConversationsChart', `
        export default function ConversationsChart() {
            return null;
        }
    `],
    ['@/components/charts/SegmentPieChart', `
        export default function SegmentPieChart() {
            return null;
        }
    `],
    ['@/components/charts/SalesBarChart', `
        export default function SalesBarChart() {
            return null;
        }
    `],
    ['framer-motion', `
        import React from 'react';

        function passthroughTag(tag) {
            return React.forwardRef(function MotionTag(props, ref) {
                return React.createElement(tag, { ...props, ref }, props.children);
            });
        }

        export const motion = new Proxy({}, {
            get(_target, prop) {
                return passthroughTag(typeof prop === 'string' ? prop : 'div');
            }
        });

        export function AnimatePresence(props) {
            return React.createElement(React.Fragment, null, props.children);
        }
    `],
    ['lucide-react', `
        import React from 'react';

        function Icon() {
            return null;
        }

        export const MessageCircle = Icon;
        export const Users = Icon;
        export const TrendingUp = Icon;
        export const DollarSign = Icon;
        export const Activity = Icon;
        export const Star = Icon;
        export const Clock = Icon;
        export const AlertTriangle = Icon;
        export const RefreshCw = Icon;
    `],
]);

const aliasPlugin = {
    name: 'app-regression-stubs',
    setup(buildContext) {
        buildContext.onResolve({ filter: /.*/ }, (args) => {
            if (STUBS.has(args.path)) {
                return { path: args.path, namespace: 'stub' };
            }
            return null;
        });

        buildContext.onLoad({ filter: /.*/, namespace: 'stub' }, async (args) => ({
            contents: STUBS.get(args.path),
            loader: 'js',
        }));
    },
};

const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-app-render-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/App.tsx'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [aliasPlugin],
        external: ['react', 'react/jsx-runtime', 'react-dom/server'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'app-bundle.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { default: App } = await import(moduleUrl);
    const html = renderToStaticMarkup(React.createElement(App));

    assert.match(
        html,
        /operator-center-marker/,
        'OperatorCenter should render even when metrics data is unavailable',
    );
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
