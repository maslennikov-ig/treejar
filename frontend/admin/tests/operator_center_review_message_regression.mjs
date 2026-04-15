import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-review-message-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/components/operatorCenterMessages.ts'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'operator-center-messages.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { buildManagerReviewMessage } = await import(moduleUrl);

    const detail = {
        total_score: 17,
        max_score: 20,
    };

    assert.deepEqual(
        buildManagerReviewMessage('Amina', detail, null),
        {
            tone: 'success',
            text: 'Amina scored 17/20.',
        },
    );

    assert.deepEqual(
        buildManagerReviewMessage('Amina', detail, 'Failed to load operator controls.'),
        {
            tone: 'info',
            text: 'Amina scored 17/20. Review saved, but operator data failed to refresh.',
        },
    );
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
