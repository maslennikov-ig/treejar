import assert from 'node:assert/strict';
import { mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

async function collectSourceFiles(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    const files = [];
    for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...(await collectSourceFiles(full)));
        } else if (/\.(ts|tsx)$/.test(entry.name)) {
            files.push(full);
        }
    }
    return files;
}

const STUBS = new Map([
    [
        '@/hooks/useMetrics',
        `
        export function useMetrics() {
            return {
                data: null,
                timeseries: null,
                loading: false,
                error: null,
                refetch: () => {},
            };
        }
    `,
    ],
    [
        '@/components/AcceptanceDemo',
        `
        import React from 'react';
        export default function AcceptanceDemo() {
            return React.createElement('div', { id: 'acceptance-demo-marker' }, 'acceptance demo');
        }
    `,
    ],
    [
        '@/components/charts/ConversationsChart',
        `export default function ConversationsChart() { return null; }`,
    ],
    [
        '@/components/charts/SegmentPieChart',
        `export default function SegmentPieChart() { return null; }`,
    ],
    [
        '@/components/charts/SalesBarChart',
        `export default function SalesBarChart() { return null; }`,
    ],
    [
        'framer-motion',
        `
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
    `,
    ],
    [
        'lucide-react',
        `
        function Icon() { return null; }
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
]);

const aliasPlugin = {
    name: 'onboarding-guide-stubs',
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

function assertValidLocalizedText(obj, context) {
    assert.ok(obj && typeof obj.ru === 'string' && obj.ru.trim().length > 0, `${context}.ru must be non-empty`);
    assert.ok(obj && typeof obj.en === 'string' && obj.en.trim().length > 0, `${context}.en must be non-empty`);
    assert.doesNotMatch(obj.en, /[А-Яа-яЁё]/, `${context}.en must not contain Cyrillic characters`);
    assert.doesNotMatch(obj.ru, /compose|рассыл/i, `${context}.ru must not contain banned broadcast words`);
    assert.doesNotMatch(obj.en, /compose|рассыл/i, `${context}.en must not contain banned broadcast words`);
}

const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-onboarding-guide-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { default as App } from './src/App';",
                "export { default as GuideView } from './src/views/GuideView';",
                "export { LanguageProvider } from './src/i18n';",
                "export { parseAdminRoute } from './src/hooks/useAdminRouter';",
                "export { TOUR_SEEN_STORAGE_KEY, resolveTourTrackParam } from './src/components/OnboardingTour';",
                "export * as guideData from './src/data/adminGuideData';",
            ].join('\n'),
            resolveDir: frontendRoot,
            loader: 'tsx',
        },
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [aliasPlugin],
        external: ['react', 'react-dom', 'react/jsx-runtime', 'react-dom/server'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'onboarding-guide-bundle.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const {
        App,
        GuideView,
        LanguageProvider,
        parseAdminRoute,
        TOUR_SEEN_STORAGE_KEY,
        resolveTourTrackParam,
        guideData,
    } = await import(pathToFileURL(bundlePath).href);

    // 1. Route parsing & URL alias normalization
    assert.equal(TOUR_SEEN_STORAGE_KEY, 'treejar_admin_tour_seen_v1');
    assert.equal(parseAdminRoute('?view=guide').view, 'guide');
    assert.equal(parseAdminRoute('?view=guide&tab=glossary').tab, 'glossary');
    assert.equal(parseAdminRoute('?view=help').view, 'guide');
    assert.equal(parseAdminRoute('?view=docs').view, 'guide');

    // 2. Tour query param resolution
    assert.equal(resolveTourTrackParam('1'), 'full');
    assert.equal(resolveTourTrackParam('true'), 'full');
    assert.equal(resolveTourTrackParam('full'), 'full');
    assert.equal(resolveTourTrackParam('daily_ops'), 'daily_ops');
    assert.equal(resolveTourTrackParam('teach_bot'), 'teach_bot');
    assert.equal(resolveTourTrackParam('quality_settings'), 'quality_settings');
    assert.equal(resolveTourTrackParam('unknown'), null);
    assert.equal(resolveTourTrackParam(null), null);

    // 3. Full App render on Guide view in RU and EN
    const htmlRu = renderToStaticMarkup(
        React.createElement(App, { initialView: 'guide', initialLang: 'ru' }),
    );
    assert.match(htmlRu, /data-guide-view=""/);
    assert.match(htmlRu, /data-guide-launchpad=""/);
    assert.match(htmlRu, /data-tour-trigger=""/);
    assert.doesNotMatch(htmlRu, /data-header-guide-btn/);
    assert.doesNotMatch(htmlRu, /data-header-refresh-btn/);
    assert.match(htmlRu, /data-admin-account-btn=""/);
    assert.match(htmlRu, /data-nav-item="guide"/);
    assert.match(htmlRu, /data-start-tour="full"/);
    assert.match(htmlRu, /data-start-tour="daily_ops"/);
    assert.match(htmlRu, /data-start-tour="teach_bot"/);
    assert.match(htmlRu, /data-start-tour="quality_settings"/);
    assert.match(htmlRu, /Справка и инструкции/);
    assert.match(htmlRu, /Запустить полный обзор кабинета \(14 шагов\)/);
    assert.doesNotMatch(htmlRu, /\btitle="/);

    const htmlEn = renderToStaticMarkup(
        React.createElement(App, { initialView: 'guide', initialLang: 'en' }),
    );
    assert.match(htmlEn, /Help &amp; Guide/);
    assert.match(htmlEn, /Start full dashboard tour \(14 steps\)/);
    assert.doesNotMatch(htmlEn, /[А-Яа-яЁё]/, 'English Guide render must not leak Cyrillic text');
    assert.doesNotMatch(htmlEn, /\btitle="/);

    // 4. Individual Guide tabs & search filtering
    for (const tab of ['playbooks', 'sections', 'glossary', 'faq']) {
        const tabHtml = renderToStaticMarkup(
            React.createElement(
                LanguageProvider,
                { initialLang: 'ru' },
                React.createElement(GuideView, {
                    activeTab: tab,
                    onTabChange: () => {},
                    onNavigate: () => {},
                    onStartTour: () => {},
                }),
            ),
        );
        assert.match(tabHtml, new RegExp(`data-guide-panel="${tab}"`));
        assert.doesNotMatch(tabHtml, /\btitle="/);
    }

    const filteredEmpty = renderToStaticMarkup(
        React.createElement(
            LanguageProvider,
            { initialLang: 'en' },
            React.createElement(GuideView, {
                activeTab: 'faq',
                globalSearch: 'zzzz-nonexistent-query-token',
                onTabChange: () => {},
                onNavigate: () => {},
                onStartTour: () => {},
            }),
        ),
    );
    assert.match(filteredEmpty, /No guide items match your search/);

    // 5. Validate all structured guide data & ensure every tour selector exists in src/
    const srcFiles = await collectSourceFiles(path.join(frontendRoot, 'src'));
    const combinedSrc = (
        await Promise.all(srcFiles.map((filePath) => readFile(filePath, 'utf8')))
    ).join('\n');

    for (const card of guideData.MINI_TOUR_CARDS) {
        assertValidLocalizedText(card.duration, `MINI_TOUR_CARDS[${card.id}].duration`);
        assertValidLocalizedText(card.role, `MINI_TOUR_CARDS[${card.id}].role`);
        assertValidLocalizedText(card.title, `MINI_TOUR_CARDS[${card.id}].title`);
        assertValidLocalizedText(card.summary, `MINI_TOUR_CARDS[${card.id}].summary`);
    }

    assert.equal(guideData.TOUR_TRACKS.full.length, 14, 'Full tour should walk through all 14 steps');
    const fullTourViews = new Set(
        guideData.TOUR_TRACKS.full.map((step) => step.route?.view).filter(Boolean),
    );
    for (const expectedView of [
        'overview',
        'conversations',
        'queuesQuality',
        'knowledge',
        'botRules',
        'catalog',
        'reports',
        'settings',
        'auditSystem',
        'acceptance',
        'guide',
    ]) {
        assert.ok(fullTourViews.has(expectedView), `Full tour must visit ${expectedView}`);
    }
    assert.equal(guideData.GUIDE_PLAYBOOKS.length, 9);
    assert.equal(guideData.GUIDE_GLOSSARY.length, 5);
    assert.equal(guideData.GUIDE_FAQ.length, 8);

    for (const [trackId, steps] of Object.entries(guideData.TOUR_TRACKS)) {
        assert.ok(Array.isArray(steps) && steps.length >= 4, `TOUR_TRACKS.${trackId} must have steps`);
        for (const step of steps) {
            assertValidLocalizedText(step.title, `TOUR_TRACKS.${trackId}.${step.id}.title`);
            assertValidLocalizedText(step.description, `TOUR_TRACKS.${trackId}.${step.id}.description`);
            if (step.selector) {
                const attrMatch = step.selector.match(/\[(data-[a-z0-9-]+)/i);
                assert.ok(attrMatch, `Selector ${step.selector} should use a stable data-* attribute`);
                assert.ok(
                    combinedSrc.includes(attrMatch[1]),
                    `Tour selector attribute ${attrMatch[1]} (${trackId}.${step.id}) must exist in frontend/admin/src`,
                );
            }
        }
    }

    for (const playbook of guideData.GUIDE_PLAYBOOKS) {
        assertValidLocalizedText(playbook.role, `GUIDE_PLAYBOOKS[${playbook.id}].role`);
        assertValidLocalizedText(playbook.duration, `GUIDE_PLAYBOOKS[${playbook.id}].duration`);
        assertValidLocalizedText(playbook.title, `GUIDE_PLAYBOOKS[${playbook.id}].title`);
        assertValidLocalizedText(playbook.goal, `GUIDE_PLAYBOOKS[${playbook.id}].goal`);
        assertValidLocalizedText(playbook.tip, `GUIDE_PLAYBOOKS[${playbook.id}].tip`);
        for (const [idx, step] of playbook.steps.entries()) {
            assertValidLocalizedText(step, `GUIDE_PLAYBOOKS[${playbook.id}].steps[${idx}]`);
        }
    }

    for (const sec of guideData.GUIDE_SECTIONS) {
        assertValidLocalizedText(sec.group, `GUIDE_SECTIONS[${sec.id}].group`);
        assertValidLocalizedText(sec.title, `GUIDE_SECTIONS[${sec.id}].title`);
        assertValidLocalizedText(sec.purpose, `GUIDE_SECTIONS[${sec.id}].purpose`);
        assertValidLocalizedText(sec.keyActions, `GUIDE_SECTIONS[${sec.id}].keyActions`);
        assertValidLocalizedText(sec.botImpact, `GUIDE_SECTIONS[${sec.id}].botImpact`);
    }

    for (const group of guideData.GUIDE_GLOSSARY) {
        assertValidLocalizedText(group.title, `GUIDE_GLOSSARY[${group.id}].title`);
        assertValidLocalizedText(group.subtitle, `GUIDE_GLOSSARY[${group.id}].subtitle`);
        for (const [idx, item] of group.items.entries()) {
            assertValidLocalizedText(item.badge, `GUIDE_GLOSSARY[${group.id}].items[${idx}].badge`);
            assertValidLocalizedText(item.meaning, `GUIDE_GLOSSARY[${group.id}].items[${idx}].meaning`);
        }
    }

    for (const faq of guideData.GUIDE_FAQ) {
        assertValidLocalizedText(faq.question, `GUIDE_FAQ[${faq.id}].question`);
        assertValidLocalizedText(faq.answer, `GUIDE_FAQ[${faq.id}].answer`);
    }

    for (const pipe of guideData.GUIDE_PIPELINE_STEPS) {
        assertValidLocalizedText(pipe.title, `GUIDE_PIPELINE_STEPS[${pipe.step}].title`);
        assertValidLocalizedText(pipe.detail, `GUIDE_PIPELINE_STEPS[${pipe.step}].detail`);
    }
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
