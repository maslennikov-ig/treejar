import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-ai-quality-api-'));

function makeResponse() {
    return {
        config: {
            bot_qa: {
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
            },
            manager_qa: {
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
            },
            red_flags: {
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
            },
        },
        warnings: [],
    };
}

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/api/operators.ts'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'operators-api.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const calls = [];
    globalThis.fetch = async (url, init) => {
        calls.push({ url: String(url), init });
        return new Response(JSON.stringify(makeResponse()), {
            status: 200,
            headers: {
                'content-type': 'application/json',
            },
        });
    };

    const moduleUrl = pathToFileURL(bundlePath).href;
    const {
        fetchAIQualityControls,
        updateAIQualityControls,
    } = await import(moduleUrl);

    await fetchAIQualityControls();
    assert.equal(calls[0].url, '/api/v1/admin/ai-quality-controls');
    assert.equal(calls[0].init.method, undefined);

    await updateAIQualityControls({
        bot_qa: {
            mode: 'manual',
            transcript_mode: 'summary',
            daily_budget_cents: 0,
            max_calls_per_run: 0,
            max_calls_per_day: 0,
            retry: {
                max_attempts: 2,
                backoff_seconds: 120,
            },
            criteria: {
                greeting: true,
            },
            cache_telemetry_enabled: true,
            alert_on_failure: false,
        },
    });

    assert.equal(calls[1].url, '/api/v1/admin/ai-quality-controls');
    assert.equal(calls[1].init.method, 'PATCH');
    assert.deepEqual(JSON.parse(calls[1].init.body), {
        bot_qa: {
            mode: 'manual',
            transcript_mode: 'summary',
            daily_budget_cents: 0,
            max_calls_per_run: 0,
            max_calls_per_day: 0,
            retry: {
                max_attempts: 2,
                backoff_seconds: 120,
            },
            criteria: {
                greeting: true,
            },
            cache_telemetry_enabled: true,
            alert_on_failure: false,
        },
    });
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
