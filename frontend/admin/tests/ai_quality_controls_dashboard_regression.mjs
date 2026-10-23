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
    ['lucide-react', `
        import React from 'react';

        function Icon(props) {
            return React.createElement('svg', props);
        }

        export const AlertTriangle = Icon;
        export const Bell = Icon;
        export const Bot = Icon;
        export const CheckCircle2 = Icon;
        export const DollarSign = Icon;
        export const Gauge = Icon;
        export const HelpCircle = Icon;
        export const RefreshCw = Icon;
        export const Save = Icon;
        export const ShieldAlert = Icon;
        export const SlidersHorizontal = Icon;
    `],
]);

const aliasPlugin = {
    name: 'ai-quality-controls-stubs',
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

function makeScope(overrides = {}) {
    return {
        mode: 'disabled',
        transcript_mode: 'summary',
        model: 'xiaomi/mimo-v2-flash-20251210',
        daily_budget_cents: 100,
        max_calls_per_run: 1,
        max_calls_per_day: 5,
        retry: {
            max_attempts: 2,
            backoff_seconds: 60,
        },
        criteria: {},
        cache_telemetry_enabled: true,
        alert_on_failure: true,
        full_transcript_warning_override: false,
        glm5_warning_override: false,
        ...overrides,
    };
}

const defaultControls = {
    config: {
        bot_qa: makeScope(),
        manager_qa: makeScope(),
        red_flags: makeScope(),
    },
    warnings: [],
};

const riskyControls = {
    config: {
        bot_qa: makeScope(),
        manager_qa: makeScope({
            mode: 'manual',
            criteria: {
                first_response: true,
                deal_followup: false,
            },
        }),
        red_flags: makeScope({
            mode: 'scheduled',
            transcript_mode: 'full',
            model: 'z-ai/glm5-20260211',
            criteria: {
                unsafe_language: true,
                missed_escalation: false,
            },
            full_transcript_warning_override: true,
            glm5_warning_override: true,
        }),
    },
    warnings: [
        {
            scope: 'red_flags',
            code: 'full_transcript',
            severity: 'warning',
            message: 'Full transcript QA can send large conversations to the LLM and should stay exceptional.',
        },
        {
            scope: 'red_flags',
            code: 'glm5_qa',
            severity: 'warning',
            message: 'GLM-5 is expensive for QA automation and requires an explicit admin override.',
        },
    ],
};

const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-ai-quality-render-'));

const defaultCriteriaControls = {
    config: {
        bot_qa: makeScope({
            mode: 'manual',
            criteria: {
                greeting_and_identity: true,
                need_discovery_and_catalog: true,
                commercial_vat_and_quotation: false,
                tone_and_language: true,
            },
        }),
        manager_qa: makeScope({
            criteria: {
                response_speed_sla: true,
                handover_context_usage: true,
                professional_tone: true,
                commercial_terms_accuracy: true,
                closing_and_crm_hygiene: true,
            },
        }),
        red_flags: makeScope({
            mode: 'scheduled',
            criteria: {
                missing_identity: true,
                hard_deflection: true,
                unverified_commitment: true,
                ignored_question: true,
                bad_tone: true,
            },
        }),
    },
    warnings: [],
    usage_today: {
        bot_qa: { calls_today: 3, max_calls_per_day: 5, spend_cents_today: 42, daily_budget_cents: 100 },
        manager_qa: { calls_today: null, max_calls_per_day: 5, spend_cents_today: null, daily_budget_cents: 100 },
    },
};

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { default } from './src/components/AIQualityControlsPanel';",
                "export { LanguageProvider } from './src/i18n';",
            ].join('\n'),
            resolveDir: frontendRoot,
            loader: 'tsx',
        },
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [aliasPlugin],
        external: ['react', 'react-dom', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'ai-quality-controls.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { default: AIQualityControlsPanel, LanguageProvider } = await import(moduleUrl);

    const render = (controls, lang) => renderToStaticMarkup(
        React.createElement(
            LanguageProvider,
            { initialLang: lang },
            React.createElement(AIQualityControlsPanel, { initialControls: controls }),
        ),
    );

    const defaultHtml = render(defaultControls, 'en');

    assert.match(defaultHtml, /AI Quality Controls/);
    assert.match(defaultHtml, /Bot QA/);
    assert.match(defaultHtml, /Manager QA/);
    assert.match(defaultHtml, /Red Flags/);
    assert.match(defaultHtml, /Zero automation safe default/);
    assert.match(defaultHtml, /scheduled AI quality jobs open 0 LLM calls/);
    assert.match(defaultHtml, /Daily budget/);
    assert.match(defaultHtml, /Cache telemetry/);
    // Tooltips are instant custom popovers (data-tooltip), not native title attributes.
    assert.match(defaultHtml, /data-tooltip="Disabled and manual modes create zero scheduled automation/);
    assert.match(defaultHtml, /data-tooltip="Summary is the cost-safe default/);
    assert.match(defaultHtml, /data-tooltip="Non-core QA should use a fast model/);
    assert.match(defaultHtml, /data-tooltip="Cache telemetry records OpenRouter cached\/write token fields/);
    assert.doesNotMatch(defaultHtml, /\btitle="/);
    // Developer notes are replaced by business explanations of the three contours.
    assert.doesNotMatch(defaultHtml, /POST \/api\/v1\/quality\/reviews\//);
    assert.doesNotMatch(defaultHtml, /Existing internal endpoint/);
    assert.doesNotMatch(defaultHtml, /does not add one/);
    assert.match(defaultHtml, /data-ai-quality-contours/);
    assert.match(defaultHtml, /15-rule checklist/);
    assert.match(defaultHtml, /up to 20 points/);
    assert.match(defaultHtml, /Scans conversations in realtime/);
    // All scopes disabled → 1-click manual mode is offered.
    assert.match(defaultHtml, /Enable Manual Mode for All/);

    const warningHtml = render(riskyControls, 'en');

    assert.match(warningHtml, /Red flags:.*Full transcript QA can send large conversations/);
    assert.match(warningHtml, /Red flags:.*GLM-5 is expensive for QA automation/);
    assert.match(warningHtml, /Full transcript override warning/);
    assert.match(warningHtml, /GLM-5 override warning/);
    assert.match(warningHtml, /z-ai\/glm5-20260211/);
    assert.match(warningHtml, /Unsafe Language/);
    assert.match(warningHtml, /Missed Escalation/);

    const criteriaHtml = render(defaultCriteriaControls, 'en');
    for (const criterion of [
        'greeting_and_identity',
        'need_discovery_and_catalog',
        'commercial_vat_and_quotation',
        'tone_and_language',
        'response_speed_sla',
        'handover_context_usage',
        'professional_tone',
        'commercial_terms_accuracy',
        'closing_and_crm_hygiene',
        'missing_identity',
        'hard_deflection',
        'unverified_commitment',
        'ignored_question',
        'bad_tone',
    ]) {
        assert.match(criteriaHtml, new RegExp(`data-criterion="${criterion}"`), `criterion ${criterion} should render a checkbox`);
    }
    assert.match(criteriaHtml, /Greeting and identity/);
    assert.match(criteriaHtml, /data-tooltip="Rules 1–3/);
    assert.match(criteriaHtml, /score is rescaled to 20/);
    assert.match(criteriaHtml, /Calls today: 3 \/ 5 · spend today: \$0\.42 \/ \$1\.00/);
    assert.match(criteriaHtml, /Calls today: n\/a \/ 5 · spend today: n\/a \/ \$1\.00/);
    assert.match(criteriaHtml, /Enable Manual Mode for All/, 'manager_qa is still disabled');

    const ruHtml = render(defaultCriteriaControls, 'ru');
    assert.match(ruHtml, /Контроль качества AI/);
    assert.match(ruHtml, /Приветствие и представление/);
    assert.match(ruHtml, /Включить ручной режим для всех/);
    assert.match(ruHtml, /Вызовов сегодня: 3 \/ 5/);
    assert.match(ruHtml, /нет данных/);
    for (const englishLabel of ['Daily budget', 'Cache telemetry', 'Reload controls', 'Transcript mode', 'Criteria toggles', 'Greeting and identity']) {
        assert.ok(!ruHtml.includes(englishLabel), `RU panel should not contain English UI label: ${englishLabel}`);
    }
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
