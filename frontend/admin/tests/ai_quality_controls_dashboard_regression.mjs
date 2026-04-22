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

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/components/AIQualityControlsPanel.tsx'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [aliasPlugin],
        external: ['react', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'ai-quality-controls.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { default: AIQualityControlsPanel } = await import(moduleUrl);

    const defaultHtml = renderToStaticMarkup(
        React.createElement(AIQualityControlsPanel, { initialControls: defaultControls }),
    );

    assert.match(defaultHtml, /AI Quality Controls/);
    assert.match(defaultHtml, /Bot QA/);
    assert.match(defaultHtml, /Manager QA/);
    assert.match(defaultHtml, /Red Flags/);
    assert.match(defaultHtml, /Zero automation safe default/);
    assert.match(defaultHtml, /scheduled AI quality jobs open 0 LLM calls/);
    assert.match(defaultHtml, /Daily budget/);
    assert.match(defaultHtml, /Cache telemetry/);
    assert.match(defaultHtml, /title="Disabled and manual modes create zero scheduled automation/);
    assert.match(defaultHtml, /title="Summary is the cost-safe default/);
    assert.match(defaultHtml, /title="Non-core QA should use a fast model/);
    assert.match(defaultHtml, /title="Cache telemetry records OpenRouter cached\/write token fields/);
    assert.match(defaultHtml, /POST \/api\/v1\/quality\/reviews\//);
    assert.match(defaultHtml, /does not add one/);

    const warningHtml = renderToStaticMarkup(
        React.createElement(AIQualityControlsPanel, { initialControls: riskyControls }),
    );

    assert.match(warningHtml, /Red flags:.*Full transcript QA can send large conversations/);
    assert.match(warningHtml, /Red flags:.*GLM-5 is expensive for QA automation/);
    assert.match(warningHtml, /Full transcript override warning/);
    assert.match(warningHtml, /GLM-5 override warning/);
    assert.match(warningHtml, /z-ai\/glm5-20260211/);
    assert.match(warningHtml, /Unsafe Language/);
    assert.match(warningHtml, /Missed Escalation/);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
