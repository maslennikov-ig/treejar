import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-dashboard-polish-'));

const read = (...parts) => readFile(path.join(frontendRoot, 'src', ...parts), 'utf8');

const STUBS = new Map([
    ['framer-motion', `
        import React from 'react';
        export const motion = new Proxy({}, {
            get(_target, prop) {
                return function MotionTag(props) {
                    const { initial, animate, transition, ...rest } = props;
                    return React.createElement(typeof prop === 'string' ? prop : 'div', rest, props.children);
                };
            },
        });
    `],
    ['lucide-react', `
        function Icon() { return null; }
        export const AlertTriangle = Icon;
        export const Bell = Icon;
        export const BookOpen = Icon;
        export const Bot = Icon;
        export const CheckCircle2 = Icon;
        export const ClipboardList = Icon;
        export const Clock = Icon;
        export const FileText = Icon;
        export const Gauge = Icon;
        export const HelpCircle = Icon;
        export const MessageCircle = Icon;
        export const Package = Icon;
        export const RefreshCw = Icon;
        export const RotateCcw = Icon;
        export const Save = Icon;
        export const Send = Icon;
        export const Share2 = Icon;
        export const ShieldAlert = Icon;
        export const ShieldCheck = Icon;
        export const SlidersHorizontal = Icon;
        export const TrendingUp = Icon;
        export const X = Icon;
    `],
]);

const stubPlugin = {
    name: 'polish-stubs',
    setup(buildContext) {
        buildContext.onResolve({ filter: /.*/ }, (args) => (STUBS.has(args.path) ? { path: args.path, namespace: 'stub' } : null));
        buildContext.onLoad({ filter: /.*/, namespace: 'stub' }, async (args) => ({ contents: STUBS.get(args.path), loader: 'js' }));
    },
};

try {
    const appSource = await read('App.tsx');
    const primitivesSource = await read('components', 'ui', 'Primitives.tsx');
    const panelSource = await read('components', 'AIQualityControlsPanel.tsx');

    // Header search: controlled input wired to the active view, Enter jumps to conversations.
    assert.match(appSource, /const \[globalSearchQuery, setGlobalSearchQuery\] = useState\(''\)/);
    assert.match(appSource, /value=\{globalSearchQuery\}/);
    assert.match(appSource, /onChange=\{\(event\) => setGlobalSearchQuery\(event\.target\.value\)\}/);
    assert.match(appSource, /event\.key === 'Enter' && !searchable/);
    assert.match(appSource, /navigate\(\{ view: 'conversations' \}\)/);
    for (const view of ['ConversationsView', 'QueuesQualityView', 'KnowledgeBaseView', 'BotRulesView', 'AuditSystemView']) {
        assert.match(appSource, new RegExp(`<${view}[\\s\\S]*?globalSearch=\\{globalSearchQuery\\}`), `${view} should receive the header search query`);
    }

    // Native title tooltips are gone.
    assert.doesNotMatch(appSource, /\stitle="Обновить"/);
    assert.doesNotMatch(panelSource, /\btitle=\{/);

    // Language and Theme providers.
    assert.match(appSource, /<LanguageProvider initialLang=\{initialLang\}>/);
    assert.match(appSource, /<ThemeProvider initialTheme=\{initialTheme\}>/);
    assert.match(appSource, /data-lang-toggle/);
    assert.match(appSource, /data-theme-toggle/);
    assert.match(appSource, /setLang\(code\)/);

    // Quality quick action in block notices.
    assert.match(primitivesSource, /export function QualityBlockNotice/);
    assert.match(primitivesSource, /<EnableManualModeButton/);

    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { buildEnableManualModePayload, scopesNeedingManualMode } from './src/components/EnableManualModeButton';",
                "export { default as CanonicalSyncButton } from './src/components/CanonicalSyncButton';",
                "export { LanguageProvider } from './src/i18n';",
            ].join('\n'),
            resolveDir: frontendRoot,
            loader: 'tsx',
        },
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [stubPlugin],
        external: ['react', 'react-dom', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });
    const bundlePath = path.join(tempDir, 'polish.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);
    const {
        buildEnableManualModePayload,
        scopesNeedingManualMode,
        CanonicalSyncButton,
        LanguageProvider,
    } = await import(pathToFileURL(bundlePath).href);

    // Only disabled scopes switch to manual; scheduled / daily_sample stay untouched.
    const config = {
        bot_qa: { mode: 'disabled' },
        manager_qa: { mode: 'scheduled' },
        red_flags: { mode: 'daily_sample' },
    };
    assert.deepEqual(buildEnableManualModePayload(config), { bot_qa: { mode: 'manual' } });
    assert.deepEqual(scopesNeedingManualMode(config), ['bot_qa']);
    assert.deepEqual(
        buildEnableManualModePayload({ bot_qa: { mode: 'disabled' }, manager_qa: { mode: 'disabled' }, red_flags: { mode: 'disabled' } }),
        { bot_qa: { mode: 'manual' }, manager_qa: { mode: 'manual' }, red_flags: { mode: 'manual' } },
    );
    assert.deepEqual(buildEnableManualModePayload(null), {});

    const render = (lang, element) => renderToStaticMarkup(React.createElement(LanguageProvider, { initialLang: lang }, element));
    const syncRu = render('ru', React.createElement(CanonicalSyncButton, { kind: 'knowledge' }));
    assert.match(syncRu, /Восстановить шаблоны БЗ/);
    const rulesEn = render('en', React.createElement(CanonicalSyncButton, { kind: 'botRules' }));
    assert.match(rulesEn, /Restore rule templates/);

    // Canonical sync calls the admin endpoint with mode and reports counts.
    const calls = [];
    globalThis.fetch = async (url, init) => {
        calls.push({ url: String(url), method: init?.method, body: init?.body ? JSON.parse(String(init.body)) : null });
        return new Response(JSON.stringify({
            ok: true, status: 'synced', mode: 'safe', created: 2, updated: 0, restored: 0, skipped_customized: 1, unchanged: 5, total_active: 8, detail: null,
        }), { status: 200, headers: { 'content-type': 'application/json' } });
    };
    const crmBuild = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/api/crm.ts'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });
    const crmPath = path.join(tempDir, 'crm.mjs');
    await writeFile(crmPath, crmBuild.outputFiles[0].text);
    const {
        syncCanonicalKnowledgeBase,
        syncCanonicalBotRules,
        fetchCanonicalKnowledgeBasePreview,
        executeConversationReset,
    } = await import(pathToFileURL(crmPath).href);
    const kbResult = await syncCanonicalKnowledgeBase('safe');
    await syncCanonicalBotRules('full_reset');
    await fetchCanonicalKnowledgeBasePreview();
    await executeConversationReset('abc');
    assert.equal(kbResult.total_active, 8);
    assert.deepEqual(calls.map((call) => [call.url, call.method, call.body]), [
        ['/api/v1/admin/knowledge-base/sync-canonical', 'POST', { mode: 'safe' }],
        ['/api/v1/admin/bot-rules/sync-canonical', 'POST', { mode: 'full_reset' }],
        ['/api/v1/admin/knowledge-base/sync-canonical/preview', undefined, null],
        ['/api/v1/admin/crm/conversations/abc/reset/execute', 'POST', { confirm: true }],
    ]);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
