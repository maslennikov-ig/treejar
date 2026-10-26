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
    ['@/components/AcceptanceDemo', `
        import React from 'react';
        export default function AcceptanceDemo() {
            return React.createElement('div', { id: 'acceptance-demo-marker' }, 'acceptance demo');
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
        function Icon() {
            return null;
        }

        export const Activity = Icon;
        export const AlertTriangle = Icon;
        export const ArrowRight = Icon;
        export const ArrowUpRight = Icon;
        export const Award = Icon;
        export const BarChart3 = Icon;
        export const Bell = Icon;
        export const BookOpen = Icon;
        export const Bot = Icon;
        export const Boxes = Icon;
        export const CheckCircle2 = Icon;
        export const ChevronDown = Icon;
        export const ChevronLeft = Icon;
        export const ChevronRight = Icon;
        export const ClipboardCheck = Icon;
        export const ClipboardList = Icon;
        export const Clock = Icon;
        export const Code2 = Icon;
        export const Database = Icon;
        export const DollarSign = Icon;
        export const ExternalLink = Icon;
        export const FileText = Icon;
        export const FlaskConical = Icon;
        export const Gauge = Icon;
        export const HelpCircle = Icon;
        export const History = Icon;
        export const Inbox = Icon;
        export const Info = Icon;
        export const LifeBuoy = Icon;
        export const LogOut = Icon;
        export const MessageCircle = Icon;
        export const Moon = Icon;
        export const MoreHorizontal = Icon;
        export const Package = Icon;
        export const PanelRightOpen = Icon;
        export const Plus = Icon;
        export const RefreshCw = Icon;
        export const RotateCcw = Icon;
        export const Save = Icon;
        export const Search = Icon;
        export const Send = Icon;
        export const Settings = Icon;
        export const ShieldAlert = Icon;
        export const ShieldCheck = Icon;
        export const SlidersHorizontal = Icon;
        export const Sparkles = Icon;
        export const Star = Icon;
        export const Sun = Icon;
        export const Trash2 = Icon;
        export const TrendingUp = Icon;
        export const X = Icon;
        export const Zap = Icon;
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
        external: ['react', 'react-dom', 'react/jsx-runtime', 'react-dom/server'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'app-bundle.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { default: App } = await import(moduleUrl);
    const html = renderToStaticMarkup(React.createElement(App, { initialView: 'conversations' }));

    // Default language is Russian.
    assert.match(html, /Noor AI/);
    assert.match(html, /Клиенты и диалоги/);
    assert.match(html, /Очереди и качество/);
    assert.match(html, /Каталог и остатки/);
    assert.match(html, /Аудит и статус системы/);
    assert.match(html, /Телефон, имя, Zoho, SO/);
    assert.match(html, /Выберите клиента в списке слева, чтобы открыть переписку/);
    assert.match(html, /data-section-banner="conversations"/, 'Conversations view should start with a section banner');
    assert.match(html, /data-lang-toggle/, 'Header should render the RU | EN toggle');
    assert.match(html, /data-theme-toggle/, 'Header should render the Light/Dark theme toggle');
    assert.doesNotMatch(html, /data-sidebar-theme-toggle/, 'Sidebar must not duplicate the theme toggle');
    assert.doesNotMatch(html, /data-header-guide-btn/, 'Header must not duplicate the Guide button');
    assert.match(html, /data-admin-account-btn/, 'Header should render interactive admin account menu button');
    assert.match(html, /<input[^>]*type="search"[^>]*value=""/, 'Header search should be a controlled input');
    assert.doesNotMatch(html, /\btitle="/, 'Dashboard should not rely on native title tooltips');
    for (const englishLabel of ['Reset preview', 'Applied bot rules', 'Customers &amp; Conversations', 'Select a customer', 'Search...']) {
        assert.ok(!html.includes(englishLabel), `RU render should not contain English UI label: ${englishLabel}`);
    }

    // English render through the language provider.
    const htmlEn = renderToStaticMarkup(React.createElement(App, { initialLang: 'en', initialView: 'conversations' }));
    assert.match(htmlEn, /Customers &amp; Conversations/);
    assert.match(htmlEn, /Queues &amp; Quality/);
    assert.match(htmlEn, /Catalog &amp; Inventory/);
    assert.match(htmlEn, /Audit &amp; System Health/);
    assert.match(htmlEn, /Phone, name, Zoho, SO/);
    assert.match(htmlEn, /Select a customer on the left to inspect the full chat history/);
    assert.doesNotMatch(htmlEn, /[А-Яа-яЁё]/, 'EN render should not contain Cyrillic UI text');

    // Overview renders attention strip and error banner gracefully when metrics fail.
    const overviewHtml = renderToStaticMarkup(React.createElement(App, { initialView: 'overview' }));
    assert.match(overviewHtml, /data-overview-attention-bar/);
    assert.match(overviewHtml, /metrics failed/);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
