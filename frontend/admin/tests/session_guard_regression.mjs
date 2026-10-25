import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-session-guard-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/api/sessionGuard.ts'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'session-guard.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const {
        buildExpiredSessionLoginUrl,
        redirectOnAdminUnauthorized,
        resetAdminUnauthorizedRedirectForTests,
    } = await import(pathToFileURL(bundlePath).href);

    assert.equal(
        buildExpiredSessionLoginUrl('/dashboard/', ''),
        '/admin/login?reason=session_expired',
    );
    assert.equal(
        buildExpiredSessionLoginUrl('/dashboard', '?tour=1'),
        '/admin/login?next=%2Fdashboard%2F%3Ftour%3D1&reason=session_expired',
    );
    assert.equal(
        buildExpiredSessionLoginUrl('/dashboard/', '?view=guide'),
        '/admin/login?next=%2Fdashboard%2F%3Fview%3Dguide&reason=session_expired',
    );

    const assigned = [];
    Object.defineProperty(globalThis, 'location', {
        value: {
            pathname: '/dashboard/',
            search: '?view=guide',
            assign: (url) => assigned.push(url),
        },
        configurable: true,
    });

    resetAdminUnauthorizedRedirectForTests();
    assert.equal(redirectOnAdminUnauthorized({ status: 500 }), false);
    assert.deepEqual(assigned, []);

    assert.equal(redirectOnAdminUnauthorized({ status: 401 }), true);
    assert.equal(redirectOnAdminUnauthorized({ status: 401 }), true);
    assert.deepEqual(assigned, [
        '/admin/login?next=%2Fdashboard%2F%3Fview%3Dguide&reason=session_expired',
    ]);

    resetAdminUnauthorizedRedirectForTests();
    Object.defineProperty(globalThis, 'location', {
        value: {
            pathname: '/client-self-test/',
            search: '',
            assign: (url) => assigned.push(url),
        },
        configurable: true,
    });
    assert.equal(redirectOnAdminUnauthorized({ status: 401 }), false);
    assert.equal(assigned.length, 1);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
