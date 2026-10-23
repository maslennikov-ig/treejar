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
        export const Save = Icon;
        export const Send = Icon;
        export const Share2 = Icon;
        export const ShieldAlert = Icon;
        export const SlidersHorizontal = Icon;
        export const TrendingUp = Icon;
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
    const operatorSource = await read('components', 'OperatorCenter.tsx');
    const panelSource = await read('components', 'AIQualityControlsPanel.tsx');

    // Header search: controlled input wired to the active view, Enter jumps to conversations.
    assert.match(appSource, /const \[globalSearchQuery, setGlobalSearchQuery\] = useState\(''\)/);
    assert.match(appSource, /value=\{globalSearchQuery\}/);
    assert.match(appSource, /onChange=\{\(event\) => setGlobalSearchQuery\(event\.target\.value\)\}/);
    assert.match(appSource, /event\.key === 'Enter' && !searchable/);
    assert.match(appSource, /setActiveView\('conversations'\)/);
    for (const view of ['ConversationsView', 'QueuesView', 'KnowledgeBaseView', 'BotRulesView', 'AuditView']) {
        assert.match(appSource, new RegExp(`<${view} globalSearch=\\{globalSearchQuery\\}`), `${view} should receive the header search query`);
    }
    assert.match(appSource, /<QualityView refetch=\{refetch\} globalSearch=\{globalSearchQuery\}/);

    // No alert(JSON) and a section banner on all 11 views.
    assert.doesNotMatch(appSource, /globalThis\.alert\(/);
    for (const view of ['overview', 'conversations', 'queues', 'knowledge', 'botRules', 'catalog', 'quality', 'reports', 'settings', 'audit', 'support']) {
        assert.match(appSource, new RegExp(`<ViewBanner\\s+view="${view}"`), `${view} should render a SectionInfoBanner`);
    }
    // Native title tooltips are gone (rendered-HTML checks live in the App/panel render tests).
    assert.doesNotMatch(appSource, /\stitle="Обновить"/);
    assert.doesNotMatch(panelSource, /\btitle=\{/);

    // Language toggle and provider.
    assert.match(appSource, /<LanguageProvider initialLang=\{initialLang\}>/);
    assert.match(appSource, /data-lang-toggle/);
    assert.match(appSource, /setLang\(code\)/);

    // Quality quick action in Conversations / Queues / Quality block notices.
    assert.match(appSource, /function QualityBlockNotice/);
    assert.match(appSource, /<EnableManualModeButton config=\{block\.config\}/);
    assert.ok((appSource.match(/<QualityBlockNotice block=/g) ?? []).length >= 3, 'block notice should appear in Conversations, Queues and Quality');

    // Operator Center: canonical sync + manual-mode quick action.
    assert.match(operatorSource, /<CanonicalSyncButton kind="knowledge"/);
    assert.match(operatorSource, /<CanonicalSyncButton kind="botRules"/);
    assert.match(operatorSource, /<EnableManualModeButton/);
    assert.match(operatorSource, /useI18n/);

    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { buildEnableManualModePayload, scopesNeedingManualMode } from './src/components/EnableManualModeButton';",
                "export { default as CanonicalSyncButton } from './src/components/CanonicalSyncButton';",
                "export { default as OperatorCenter } from './src/components/OperatorCenter';",
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
        OperatorCenter,
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
    assert.match(syncRu, /Синхронизировать базу Treejar/);
    const rulesEn = render('en', React.createElement(CanonicalSyncButton, { kind: 'botRules' }));
    assert.match(rulesEn, /Load canonical Treejar rules/);

    // Canonical sync calls the admin endpoint after confirm and reports counts.
    const calls = [];
    globalThis.fetch = async (url, init) => {
        calls.push({ url: String(url), method: init?.method });
        return new Response(JSON.stringify({
            ok: true, status: 'synced', created: 2, updated: 1, restored: 1, unchanged: 4, total_active: 8, detail: null,
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
    const { syncCanonicalKnowledgeBase, syncCanonicalBotRules, executeConversationReset } = await import(pathToFileURL(crmPath).href);
    const kbResult = await syncCanonicalKnowledgeBase();
    await syncCanonicalBotRules();
    await executeConversationReset('abc');
    assert.equal(kbResult.total_active, 8);
    assert.deepEqual(calls.map((call) => [call.url, call.method]), [
        ['/api/v1/admin/knowledge-base/sync-canonical', 'POST'],
        ['/api/v1/admin/bot-rules/sync-canonical', 'POST'],
        ['/api/v1/admin/crm/conversations/abc/reset/execute', 'POST'],
    ]);

    // Operator Center renders localized in both languages.
    const operatorRu = render('ru', React.createElement(OperatorCenter, { onMetricsRefresh: () => {} }));
    assert.match(operatorRu, /Центр оператора/);
    assert.match(operatorRu, /Базовые данные Treejar/);
    assert.match(operatorRu, /Загрузить правила Treejar/);
    const operatorEn = render('en', React.createElement(OperatorCenter, { onMetricsRefresh: () => {} }));
    assert.match(operatorEn, /Operator Center/);
    assert.match(operatorEn, /Sync canonical Treejar KB/);
    assert.doesNotMatch(operatorEn, /[А-Яа-яЁё]/);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
