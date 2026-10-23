import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-router-theme-'));

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { parseAdminUrl, buildAdminSearch } from './src/hooks/useAdminRouter';",
                "export { THEME_STORAGE_KEY } from './src/theme';",
            ].join('\n'),
            resolveDir: frontendRoot,
            loader: 'tsx',
        },
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        external: ['react', 'react-dom', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'router-theme.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const { parseAdminUrl, buildAdminSearch, THEME_STORAGE_KEY } = await import(moduleUrl);

    assert.equal(THEME_STORAGE_KEY, 'treejar_admin_theme');

    // Legacy view ids map cleanly to unified Variant 1B views and tabs.
    const queuesRoute = parseAdminUrl('?view=queues');
    assert.equal(queuesRoute.view, 'queuesQuality');
    assert.equal(queuesRoute.tab, 'escalations');

    const qualityRoute = parseAdminUrl('?view=quality');
    assert.equal(qualityRoute.view, 'queuesQuality');
    assert.equal(qualityRoute.tab, 'ai_rubric');

    const supportRoute = parseAdminUrl('?view=support');
    assert.equal(supportRoute.view, 'auditSystem');
    assert.equal(supportRoute.tab, 'system');

    // Deep-linked conversation filters round-trip cleanly.
    const convRoute = parseAdminUrl('?view=conversations&id=conv-42&language=en&escalation=pending');
    assert.equal(convRoute.view, 'conversations');
    assert.equal(convRoute.id, 'conv-42');
    assert.equal(convRoute.language, 'en');
    assert.equal(convRoute.escalation, 'pending');

    const serialized = buildAdminSearch(convRoute);
    assert.match(serialized, /view=conversations/);
    assert.match(serialized, /id=conv-42/);
    assert.match(serialized, /language=en/);
    assert.match(serialized, /escalation=pending/);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
