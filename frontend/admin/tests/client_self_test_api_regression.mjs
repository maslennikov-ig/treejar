import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-client-self-test-api-'));

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
        return new Response(JSON.stringify({ ok: true, submitted_count: 2 }), {
            status: 200,
            headers: {
                'content-type': 'application/json',
            },
        });
    };

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { submitClientSelfTest } = await import(moduleUrl);

    Object.defineProperty(globalThis, 'location', {
        value: { pathname: '/client-self-test/' },
        configurable: true,
    });

    const response = await submitClientSelfTest({
        tester_name: 'Customer owner',
        overall_comment: 'Done',
        items: [
            {
                id: 'catalog',
                title: 'Каталог',
                status: 'passed',
                note: '',
            },
            {
                id: 'quotation',
                title: 'Quotation approval',
                status: 'failed',
                note: 'Wrong buttons',
            },
        ],
    });

    assert.deepEqual(response, { ok: true, submitted_count: 2 });
    assert.equal(calls[0].url, '/api/v1/client-self-test/submit');
    assert.equal(calls[0].init.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].init.body), {
        tester_name: 'Customer owner',
        overall_comment: 'Done',
        items: [
            {
                id: 'catalog',
                title: 'Каталог',
                status: 'passed',
                note: '',
            },
            {
                id: 'quotation',
                title: 'Quotation approval',
                status: 'failed',
                note: 'Wrong buttons',
            },
        ],
    });

    Object.defineProperty(globalThis, 'location', {
        value: { pathname: '/dashboard/' },
        configurable: true,
    });

    await submitClientSelfTest({
        tester_name: 'Admin',
        overall_comment: null,
        items: [
            {
                id: 'catalog',
                title: 'Каталог',
                status: 'passed',
                note: '',
            },
        ],
    });

    assert.equal(calls[1].url, '/api/v1/admin/client-self-test/submit');
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
