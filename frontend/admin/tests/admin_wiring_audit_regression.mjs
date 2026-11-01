import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-wiring-audit-'));

const read = (...parts) => readFile(path.join(frontendRoot, 'src', ...parts), 'utf8');

const STUBS = new Map([
    [
        'lucide-react',
        `
        function Icon() { return null; }
        export default new Proxy({}, { get: () => Icon });
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
    `,
    ],
    [
        'framer-motion',
        `
        import React from 'react';
        export const motion = new Proxy({}, {
            get(_target, prop) {
                return function MotionTag(props) {
                    return React.createElement(typeof prop === 'string' ? prop : 'div', props, props.children);
                };
            },
        });
        export function AnimatePresence(props) {
            return React.createElement(React.Fragment, null, props.children);
        }
    `,
    ],
    ['@/components/charts/ConversationsChart', `export default function ConversationsChart() { return null; }`],
    ['@/components/charts/SegmentPieChart', `export default function SegmentPieChart() { return null; }`],
    ['@/components/charts/SalesBarChart', `export default function SalesBarChart() { return null; }`],
]);

const stubPlugin = {
    name: 'wiring-audit-stubs',
    setup(buildContext) {
        buildContext.onResolve({ filter: /.*/ }, (args) =>
            STUBS.has(args.path) ? { path: args.path, namespace: 'stub' } : null,
        );
        buildContext.onLoad({ filter: /.*/, namespace: 'stub' }, async (args) => ({
            contents: STUBS.get(args.path),
            loader: 'js',
        }));
    },
};

try {
    const [
        appSource,
        queuesSource,
        botRulesSource,
        crmApiSource,
        operatorsApiSource,
        guideSource,
        panelSource,
    ] = await Promise.all([
        read('App.tsx'),
        read('views', 'QueuesQualityView.tsx'),
        read('views', 'BotRulesView.tsx'),
        read('api', 'crm.ts'),
        read('api', 'operators.ts'),
        read('data', 'adminGuideData.ts'),
        read('components', 'AIQualityControlsPanel.tsx'),
    ]);

    // 1. Static architecture & dead-code checks (tj-id6m.12, AD-02, AD-07, AD-30, AD-31)
    assert.match(appSource, /const OverviewView = lazy\(\(\) => import\('@\/views\/OverviewView'\)\)/);
    assert.match(appSource, /const ConversationsView = lazy\(\(\) => import\('@\/views\/ConversationsView'\)\)/);
    assert.match(appSource, /const QueuesQualityView = lazy\(\(\) => import\('@\/views\/QueuesQualityView'\)\)/);
    assert.match(appSource, /const GuideView = lazy\(\(\) => import\('@\/views\/GuideView'\)\)/);
    assert.match(appSource, /<Suspense fallback=\{<ViewLoadingFallback \/>}>/);
    assert.match(appSource, /useMetrics\(\s*period,\s*activeView === 'overview',?\s*\)/);

    // QueuesQualityView must not depend on the full managerQa object in loadQueues useCallback
    assert.doesNotMatch(
        queuesSource,
        /\[escalationFilter,\s*managerQa,\s*onCountsChange,\s*t\]/,
        'loadQueues must not re-create on every managerQa state transition',
    );
    assert.doesNotMatch(
        botRulesSource,
        /CANONICAL_RULE_TITLES/,
        'BotRulesView must derive canonical badges from server metadata rather than hardcoded titles',
    );
    assert.match(botRulesSource, /value:\s*'company_details'/);
    assert.match(botRulesSource, /value:\s*'feedback'/);

    // Dead API wrappers removed (AD-31)
    assert.doesNotMatch(operatorsApiSource, /fetchRecentFeedback|fetchReferralPolicy/);
    assert.doesNotMatch(
        crmApiSource,
        /fetchCanonicalKnowledgeBaseStatus|fetchCanonicalBotRulesStatus/,
    );

    // Guide /client-self-test route accuracy (AD-30)
    assert.match(guideSource, /\/client-self-test/);
    assert.doesNotMatch(guideSource, /\b\/test\b/);

    // AI QC numeric bounds aligned with backend (AD-21)
    assert.match(panelSource, /max=\{200\}/);
    assert.match(panelSource, /max=\{100\}/);
    assert.match(panelSource, /max=\{500\}/);
    assert.match(panelSource, /max=\{3600\}/);

    // 2. Behavioral unit & API contract tests across exported helpers
    const bundleResult = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { createI18nValue } from './src/i18n';",
                "export { resolveQualityControlBlockState } from './src/hooks/useAIQualityControlBlock';",
                "export { parseAdminRoute, buildAdminSearch } from './src/hooks/useAdminRouter';",
                "export { FALLBACK_AI_QUALITY_MODELS, resolveScopeModelOptions, allowedModesForScope } from './src/components/AIQualityControlsPanel';",
                "export { BOT_QA_RUBRIC_ITEMS, buildEscalationsQueueParams } from './src/views/QueuesQualityView';",
                "export { periodToDateFrom } from './src/views/OverviewView';",
                "export { CANONICAL_DEAL_STATUSES, buildDirtyConversationPatch, resolveDealStatusOptions } from './src/views/ConversationsView';",
                "export { getBotRuleSourceKind } from './src/views/BotRulesView';",
                "export { KB_CATEGORIES } from './src/views/KnowledgeBaseView';",
                "export { isCatalogSyncQueuedResponse } from './src/views/CatalogView';",
                "export { contourStatusTone, localizeAuditAction } from './src/views/AuditSystemView';",
                "export { testBotRule, updateAdminConversation } from './src/api/crm';",
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

    const bundlePath = path.join(tempDir, 'wiring-audit-bundle.mjs');
    await writeFile(bundlePath, bundleResult.outputFiles[0].text);

    const {
        createI18nValue,
        resolveQualityControlBlockState,
        parseAdminRoute,
        buildAdminSearch,
        FALLBACK_AI_QUALITY_MODELS,
        resolveScopeModelOptions,
        allowedModesForScope,
        BOT_QA_RUBRIC_ITEMS,
        buildEscalationsQueueParams,
        periodToDateFrom,
        CANONICAL_DEAL_STATUSES,
        buildDirtyConversationPatch,
        resolveDealStatusOptions,
        getBotRuleSourceKind,
        KB_CATEGORIES,
        isCatalogSyncQueuedResponse,
        contourStatusTone,
        localizeAuditAction,
        testBotRule,
        updateAdminConversation,
    } = await import(pathToFileURL(bundlePath).href);

    const i18nEn = createI18nValue('en');
    const i18nRu = createI18nValue('ru');

    // AD-02 & AD-28: Quality control block fails closed when loading or when controls fetch fails
    const loadingBlock = resolveQualityControlBlockState({
        config: null,
        loading: true,
        loadError: null,
        scope: 'manager_qa',
        labelText: 'Manager QA',
        t: i18nEn.t,
    });
    assert.equal(loadingBlock.blocked, true);
    assert.equal(loadingBlock.message, null);

    const errorBlock = resolveQualityControlBlockState({
        config: null,
        loading: false,
        loadError: 'HTTP 503',
        scope: 'manager_qa',
        labelText: 'Manager QA',
        t: i18nEn.t,
    });
    assert.equal(errorBlock.blocked, true);
    assert.match(errorBlock.message ?? '', /HTTP 503/);

    const activeManualBlock = resolveQualityControlBlockState({
        config: {
            manager_qa: {
                mode: 'manual',
                daily_budget_cents: 500,
                max_calls_per_run: 10,
                max_calls_per_day: 25,
            },
        },
        loading: false,
        loadError: null,
        scope: 'manager_qa',
        labelText: 'Manager QA',
        t: i18nEn.t,
    });
    assert.equal(activeManualBlock.blocked, false);
    assert.equal(activeManualBlock.message, null);

    // AD-03 & AD-08: Escalations 'all' omits status; 15-rule rubric sums to 30
    assert.equal(buildEscalationsQueueParams('all').has('status'), false);
    assert.equal(buildEscalationsQueueParams('open').get('status'), 'open');
    assert.equal(buildEscalationsQueueParams('resolved').get('status'), 'resolved');
    assert.equal(BOT_QA_RUBRIC_ITEMS.length, 15);
    assert.equal(
        BOT_QA_RUBRIC_ITEMS.reduce((sum, item) => sum + item.maxPoints, 0),
        30,
    );

    // AD-07 & AD-22: Canonical bot rule badge uses source_type/canonical_key + single-rule test API
    assert.equal(
        getBotRuleSourceKind({
            source_type: 'canonical_treejar',
            canonical_key: 'identity_noor',
            is_canonical_customized: false,
        }),
        'canonical',
    );
    assert.equal(
        getBotRuleSourceKind({
            source_type: 'canonical_treejar',
            canonical_key: 'identity_noor',
            is_canonical_customized: true,
        }),
        'canonical_customized',
    );
    assert.equal(
        getBotRuleSourceKind({
            source_type: 'manual',
            canonical_key: null,
            is_canonical_customized: false,
        }),
        'manual',
    );

    // AD-04 / tj-id6m.4: Dirty-field CRM PATCH & legacy DealStatus preservation
    assert.deepEqual(CANONICAL_DEAL_STATUSES, ['pending', 'in_progress', 'delivered', 'cancelled']);
    const legacyDetail = {
        customer_name: 'Old Name',
        status: 'active',
        sales_stage: 'quoting',
        escalation_status: 'none',
        deal_status: 'New Lead',
    };
    assert.deepEqual(
        buildDirtyConversationPatch(legacyDetail, {
            editName: 'Old Name',
            editStatus: 'active',
            editStage: 'quoting',
            editEscalation: 'none',
            editDealStatus: 'New Lead',
        }),
        {},
        'Clean CRM form must produce an empty patch',
    );
    assert.deepEqual(
        buildDirtyConversationPatch(legacyDetail, {
            editName: 'Updated Name',
            editStatus: 'active',
            editStage: 'quoting',
            editEscalation: 'none',
            editDealStatus: 'New Lead',
        }),
        { customer_name: 'Updated Name' },
        'Editing customer_name must not resend untouched legacy deal_status',
    );
    const dealOptions = resolveDealStatusOptions('New Lead');
    assert.ok(
        dealOptions.some((opt) => opt.value === 'New Lead' && opt.isLegacy === true),
        'Legacy Zoho DealStatus must remain selectable with legacy annotation',
    );
    for (const canonicalStatus of CANONICAL_DEAL_STATUSES) {
        assert.ok(dealOptions.some((opt) => opt.value === canonicalStatus && opt.isLegacy === false));
    }

    // AD-05 & AD-20 / tj-id6m.3: AI QC model options preserve openai/gpt-6.1-terra, available_models, and custom (current)
    assert.ok(FALLBACK_AI_QUALITY_MODELS.includes('openai/gpt-6.1-terra'));
    assert.ok(FALLBACK_AI_QUALITY_MODELS.includes('z-ai/glm-5.2'));

    const serverModelOpts = resolveScopeModelOptions(
        'openai/gpt-6.1-terra',
        ['google/gemini-3-flash-preview', 'openai/gpt-6.1-terra', 'z-ai/glm-5.2'],
        'openai/gpt-6.1-terra',
    );
    assert.deepEqual(
        serverModelOpts.map((opt) => opt.value),
        ['google/gemini-3-flash-preview', 'openai/gpt-6.1-terra', 'z-ai/glm-5.2'],
    );
    assert.equal(serverModelOpts[1].isCustomCurrent, false);

    const customCurrentOpts = resolveScopeModelOptions(
        'anthropic/claude-custom-eval',
        ['google/gemini-3-flash-preview', 'openai/gpt-6.1-terra'],
        'openai/gpt-6.1-terra',
    );
    assert.deepEqual(customCurrentOpts[0], {
        value: 'anthropic/claude-custom-eval',
        isCustomCurrent: true,
    });

    const redFlagModes = allowedModesForScope('red_flags', 'daily_sample');
    assert.deepEqual(
        redFlagModes.map((item) => item.value),
        ['disabled', 'daily_sample', 'scheduled'],
    );
    const legacyRedFlagModes = allowedModesForScope('red_flags', 'manual');
    assert.ok(legacyRedFlagModes.some((item) => item.value === 'manual' && item.isLegacyManual === true));
    const botQaModes = allowedModesForScope('bot_qa', 'manual');
    assert.ok(botQaModes.some((item) => item.value === 'manual' && item.isLegacyManual === false));

    // AD-13: Overview periodToDateFrom & router date_from roundtrip
    const fixedNowMs = Date.parse('2026-10-15T12:00:00Z');
    assert.equal(periodToDateFrom('day', fixedNowMs), '2026-10-14');
    assert.equal(periodToDateFrom('week', fixedNowMs), '2026-10-08');
    assert.equal(periodToDateFrom('month', fixedNowMs), '2026-09-15');
    assert.equal(periodToDateFrom('all_time', fixedNowMs), undefined);

    const parsedRoute = parseAdminRoute('?view=conversations&filter=deals&date_from=2026-10-08');
    assert.equal(parsedRoute.view, 'conversations');
    assert.equal(parsedRoute.filter, 'deals');
    assert.equal(parsedRoute.date_from, '2026-10-08');
    assert.match(buildAdminSearch(parsedRoute), /date_from=2026-10-08/);

    // AD-15, AD-16, AD-24, AD-27: Audit actions, contour red tone, Catalog queued response, KB products category
    assert.equal(contourStatusTone('ok'), 'green');
    assert.equal(contourStatusTone('warning'), 'amber');
    assert.equal(contourStatusTone('error'), 'red');
    assert.notEqual(
        localizeAuditAction('escalation.create', i18nRu.t),
        localizeAuditAction('escalation.close', i18nRu.t),
    );
    assert.notEqual(
        localizeAuditAction('quality.manager_review', i18nEn.t),
        localizeAuditAction('quality.bot_review', i18nEn.t),
    );
    assert.equal(localizeAuditAction('products.sync', i18nEn.t), 'Trigger catalog sync');

    assert.equal(
        isCatalogSyncQueuedResponse({
            status: 'queued',
            synced: 0,
            created: 0,
            updated: 0,
            errors: 0,
            deactivated: 0,
            embeddings_generated: 0,
        }),
        true,
    );
    assert.equal(
        isCatalogSyncQueuedResponse({
            synced: 12,
            created: 2,
            updated: 10,
            errors: 0,
            deactivated: 0,
            embeddings_generated: 12,
        }),
        false,
    );
    assert.ok(KB_CATEGORIES.some((cat) => cat.value === 'products'));

    // Network call verification for testBotRule & dirty updateConversation
    const apiCalls = [];
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
        apiCalls.push({
            url: String(url),
            method: init?.method,
            body: init?.body ? JSON.parse(String(init.body)) : null,
        });
        return new Response(
            JSON.stringify({ applied_rules: [], prompt_block: '', rule_count: 0 }),
            { status: 200, headers: { 'content-type': 'application/json' } },
        );
    };
    try {
        await testBotRule('rule-draft-1', {
            message: 'Need 20 chairs',
            stage: 'company_details',
            language: 'en',
            segment: null,
        });
        const dirtyPatch = buildDirtyConversationPatch(legacyDetail, {
            editName: 'Noor Client',
            editStatus: 'active',
            editStage: 'quoting',
            editEscalation: 'none',
            editDealStatus: 'New Lead',
        });
        await updateAdminConversation('conv-99', dirtyPatch);

        assert.deepEqual(apiCalls, [
            {
                url: '/api/v1/admin/bot-rules/rules/rule-draft-1/test',
                method: 'POST',
                body: {
                    message: 'Need 20 chairs',
                    stage: 'company_details',
                    language: 'en',
                    segment: null,
                },
            },
            {
                url: '/api/v1/admin/crm/conversations/conv-99',
                method: 'PATCH',
                body: { customer_name: 'Noor Client' },
            },
        ]);
    } finally {
        globalThis.fetch = originalFetch;
    }
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
