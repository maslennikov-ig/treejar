import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-client-self-test-state-'));

const stubs = new Map([
    ['@/api/operators', `
        export async function submitClientSelfTest() {
            return { ok: true, submitted_count: 0 };
        }
    `],
    ['lucide-react', `
        function Icon() {
            return null;
        }

        export const AlertTriangle = Icon;
        export const CheckCircle2 = Icon;
        export const CircleDashed = Icon;
        export const ClipboardCheck = Icon;
        export const MinusCircle = Icon;
        export const Send = Icon;
        export const XCircle = Icon;
    `],
]);

const aliasPlugin = {
    name: 'client-self-test-stubs',
    setup(buildContext) {
        buildContext.onResolve({ filter: /.*/ }, (args) => {
            if (stubs.has(args.path)) {
                return { path: args.path, namespace: 'stub' };
            }
            return null;
        });

        buildContext.onLoad({ filter: /.*/, namespace: 'stub' }, async (args) => ({
            contents: stubs.get(args.path),
            loader: 'js',
        }));
    },
};

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/components/AcceptanceDemo.tsx'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        plugins: [aliasPlugin],
        external: ['react', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });

    const bundlePath = path.join(tempDir, 'acceptance-demo.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);

    const moduleUrl = pathToFileURL(bundlePath).href;
    const {
        CLIENT_SELF_TEST_SCENARIOS,
        CLIENT_SELF_TEST_STORAGE_KEY,
        buildClientSelfTestSubmitPayload,
        createInitialClientSelfTestItems,
        updateClientSelfTestItem,
    } = await import(moduleUrl);

    assert.equal(CLIENT_SELF_TEST_STORAGE_KEY, 'treejar-client-self-test-v1');
    assert.ok(
        CLIENT_SELF_TEST_SCENARIOS.length >= 10,
        'client acceptance demo should cover the full controlled scenario set',
    );

    const titles = CLIENT_SELF_TEST_SCENARIOS.map((scenario) => scenario.title);
    assert.ok(titles.includes('Неполный invoice/proforma без лишней эскалации'));
    assert.ok(titles.includes('Quotation/proforma с подтверждением менеджера'));
    assert.ok(titles.includes('Длинный Telegram-контекст сохраняет последнюю реплику'));

    const initial = createInitialClientSelfTestItems();
    assert.equal(initial.length, CLIENT_SELF_TEST_SCENARIOS.length);
    assert.ok(initial.every((item) => item.status === 'not_tested'));

    const updated = updateClientSelfTestItem(initial, CLIENT_SELF_TEST_SCENARIOS[1].id, {
        status: 'passed',
        note: 'Matched expected stock answer',
    });

    assert.equal(updated[1].status, 'passed');
    assert.equal(updated[1].note, 'Matched expected stock answer');
    assert.equal(initial[1].status, 'not_tested', 'state updates must be immutable');

    const payload = buildClientSelfTestSubmitPayload({
        testerName: 'Owner',
        overallComment: 'Ready',
        items: updated,
    });

    assert.equal(payload.tester_name, 'Owner');
    assert.equal(payload.overall_comment, 'Ready');
    assert.equal(payload.items.length, CLIENT_SELF_TEST_SCENARIOS.length);
    assert.equal(payload.items[1].title, CLIENT_SELF_TEST_SCENARIOS[1].title);
    assert.equal(payload.items[1].status, 'passed');
}
finally {
    await rm(tempDir, { recursive: true, force: true });
}
