import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const chartsDir = path.join(frontendRoot, 'src', 'components', 'charts');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-dashboard-charts-'));

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
    ['recharts', `
        import React from 'react';
        function Box(props) { return React.createElement('div', { 'data-recharts': 'stub' }, props.children); }
        function Nothing() { return null; }
        export const ResponsiveContainer = Box;
        export const PieChart = Box;
        export const Pie = Box;
        export const Cell = Nothing;
        export const Tooltip = Nothing;
        export const Legend = Nothing;
    `],
]);

const stubPlugin = {
    name: 'chart-stubs',
    setup(buildContext) {
        buildContext.onResolve({ filter: /.*/ }, (args) => (STUBS.has(args.path) ? { path: args.path, namespace: 'stub' } : null));
        buildContext.onLoad({ filter: /.*/, namespace: 'stub' }, async (args) => ({ contents: STUBS.get(args.path), loader: 'js' }));
    },
};

const metrics = {
    period: 'all_time',
    total_conversations: 120,
    unique_customers: 90,
    new_vs_returning: { new: 70, returning: 20 },
    by_segment: {},
    by_language: { en: 80, ar: 40 },
    target_vs_nontarget: { target: 75, nontarget: 45 },
    escalation_count: 30,
    escalation_reasons: {
        'Customer requested a quotation for 40 chairs': 9,
        'Wants to talk to a human manager': 6,
        'Delivery to Abu Dhabi next week?': 5,
        'Custom table not in catalog': 4,
        'Urgent complaint about late order': 3,
        'Misc question': 3,
    },
    noor_sales: { count: 8, amount: 40000 },
    post_escalation_sales: { count: 4, amount: 20000 },
    conversion_rate: 10,
    average_deal_value: 5000,
    avg_conversation_length: 12.4,
    avg_quality_score: 24,
    avg_response_time_ms: 1200,
    llm_cost_usd: 3.21,
    avg_manager_score: 16,
    avg_manager_response_time_seconds: 300,
    manager_deal_conversion_rate: 20,
    manager_leaderboard: [],
    feedback_count: 5,
    avg_rating_overall: 4.6,
    avg_rating_delivery: 4.2,
    nps_score: 60,
    recommend_rate: 80,
};

try {
    const pieSource = await readFile(path.join(chartsDir, 'SegmentPieChart.tsx'), 'utf8');
    const pieTags = [...pieSource.matchAll(/<Pie\b[\s\S]*?>/g)].map((match) => match[0]);
    assert.ok(pieTags.length > 0, 'SegmentPieChart should render a <Pie>');
    for (const tag of pieTags) {
        assert.doesNotMatch(tag, /\slabel(=|\s|>)/, 'Radial <Pie label=...> clips at narrow widths and must not be used');
    }
    assert.match(pieSource, /innerRadius=\{38\}/);
    assert.match(pieSource, /outerRadius=\{56\}/);
    assert.match(pieSource, /paddingAngle=\{3\}/);
    assert.doesNotMatch(pieSource, /grid-cols-2/, 'Donuts should stack vertically instead of a fixed two-column grid');

    const appSource = await readFile(path.join(frontendRoot, 'src', 'App.tsx'), 'utf8');
    const overview = appSource.slice(appSource.indexOf('function OverviewView'), appSource.indexOf('function SupportView'));
    assert.match(overview, /<EscalationReasonsChart byReason=\{data\.escalation_by_reason\} rawReasons=\{data\.escalation_reasons\}/);
    assert.match(overview, /<FunnelEfficiencyChart data=\{data\}/);

    for (const file of ['ConversationsChart.tsx', 'SalesBarChart.tsx']) {
        const source = await readFile(path.join(chartsDir, file), 'utf8');
        assert.match(source, /useI18n/, `${file} should be localized`);
        assert.doesNotMatch(source, />Conversations<|>Sales & Escalation<|'Noor Sales'|name="New"/, `${file} should not hard-code English labels`);
    }

    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { default as SegmentPieChart } from './src/components/charts/SegmentPieChart';",
                "export { default as EscalationReasonsChart, groupEscalationReasons } from './src/components/charts/EscalationReasonsChart';",
                "export { default as FunnelEfficiencyChart } from './src/components/charts/FunnelEfficiencyChart';",
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
        external: ['react', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });
    const bundlePath = path.join(tempDir, 'charts.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);
    const {
        SegmentPieChart,
        EscalationReasonsChart,
        FunnelEfficiencyChart,
        groupEscalationReasons,
        LanguageProvider,
    } = await import(pathToFileURL(bundlePath).href);

    const render = (lang, element) => renderToStaticMarkup(React.createElement(LanguageProvider, { initialLang: lang }, element));

    // Donut legends: localized names, exact counts and one-decimal percentages.
    const pieRu = render('ru', React.createElement(SegmentPieChart, { byLanguage: metrics.by_language, targetVsNontarget: metrics.target_vs_nontarget }));
    assert.match(pieRu, /Классификация диалогов/);
    assert.match(pieRu, /По языкам/);
    assert.match(pieRu, /Целевые и нецелевые/);
    assert.match(pieRu, /Английский \(EN\)/);
    assert.match(pieRu, /Арабский \(AR\)/);
    assert.match(pieRu, /Нецелевые/);
    assert.match(pieRu, /80 · 66,7%/);
    assert.match(pieRu, /45 · 37,5%/);
    const pieEn = render('en', React.createElement(SegmentPieChart, { byLanguage: metrics.by_language, targetVsNontarget: metrics.target_vs_nontarget }));
    assert.match(pieEn, /English \(EN\)/);
    assert.match(pieEn, /Arabic \(AR\)/);
    assert.match(pieEn, /Non-target/);
    assert.match(pieEn, /40 · 33\.3%/);
    assert.match(pieEn, /data-segment-legend/);
    assert.doesNotMatch(pieEn, /[А-Яа-яЁё]/);

    // Escalation reasons: server categories when present, keyword fallback otherwise.
    const grouped = groupEscalationReasons(metrics.escalation_reasons);
    assert.deepEqual(grouped, {
        quotation_bulk: 9,
        human_request: 6,
        delivery_terms: 5,
        custom_out_of_catalog: 4,
        urgent_complaint: 3,
        other: 3,
    });
    const escFallback = render('en', React.createElement(EscalationReasonsChart, { rawReasons: metrics.escalation_reasons }));
    assert.match(escFallback, /Escalation reasons/);
    assert.match(escFallback, /Quotation &amp; bulk orders/);
    assert.match(escFallback, /9 · 30\.0%/);
    assert.match(escFallback, /keyword grouping/);
    assert.match(escFallback, /Show raw reasons \(6\)/);
    const escServer = render('ru', React.createElement(EscalationReasonsChart, {
        byReason: { quotation_bulk: 2, human_request: 1, delivery_terms: 0, custom_out_of_catalog: 0, urgent_complaint: 1, other: 0 },
        rawReasons: {},
    }));
    assert.match(escServer, /Причины эскалаций/);
    assert.match(escServer, /КП и оптовые заказы/);
    assert.match(escServer, /2 · 50,0%/);
    assert.doesNotMatch(escServer, /группировка по ключевым словам/);
    const escEmpty = render('en', React.createElement(EscalationReasonsChart, { rawReasons: {} }));
    assert.match(escEmpty, /No escalations in this period/);

    // Funnel: steps, step conversion and secondary KPIs.
    const funnelEn = render('en', React.createElement(FunnelEfficiencyChart, {
        data: { ...metrics, sales_stage_distribution: { greeting: 10, quoting: 5, needs_analysis: 5 } },
    }));
    assert.match(funnelEn, /Funnel &amp; efficiency/);
    assert.match(funnelEn, /All conversations/);
    assert.match(funnelEn, /Deals won/);
    assert.match(funnelEn, /62\.5% of previous step/);
    assert.match(funnelEn, /40\.0% of previous step/);
    assert.match(funnelEn, /5,000 AED/);
    assert.match(funnelEn, /70 \/ 20/);
    assert.match(funnelEn, /\$3\.21/);
    assert.match(funnelEn, /4\.6 \/ 4\.2 \/5/);
    assert.match(funnelEn, /Sales stages/);
    assert.match(funnelEn, /Needs analysis/);
    assert.doesNotMatch(funnelEn, /[А-Яа-яЁё]/);
    const funnelRu = render('ru', React.createElement(FunnelEfficiencyChart, { data: metrics }));
    assert.match(funnelRu, /Воронка и эффективность/);
    assert.match(funnelRu, /Расход AI/);
    assert.doesNotMatch(funnelRu, /Этапы продаж/, 'Stage distribution is optional and hidden when absent');
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
