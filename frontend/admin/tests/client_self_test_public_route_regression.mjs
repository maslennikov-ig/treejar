import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-client-self-test-route-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/routes.ts'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'routes.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { getAppRouteMode } = await import(moduleUrl);

    assert.equal(getAppRouteMode('/client-self-test/'), 'acceptance-public');
    assert.equal(getAppRouteMode('/client-self-test/review'), 'acceptance-public');
    assert.equal(getAppRouteMode('/dashboard/'), 'dashboard');
    assert.equal(getAppRouteMode('/dashboard/assets/index.js'), 'dashboard');
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
