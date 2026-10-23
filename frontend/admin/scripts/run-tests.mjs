#!/usr/bin/env node
// Runs every frontend regression script in tests/*.mjs sequentially and stops at the first failure.
import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const testsDir = path.join(frontendRoot, 'tests');
const scripts = readdirSync(testsDir).filter((name) => name.endsWith('.mjs')).sort();

if (scripts.length === 0) {
    console.error('No frontend regression scripts found in tests/.');
    process.exit(1);
}

for (const [index, script] of scripts.entries()) {
    const started = Date.now();
    const result = spawnSync(process.execPath, [path.join(testsDir, script)], {
        cwd: frontendRoot,
        stdio: 'inherit',
    });
    const elapsed = Date.now() - started;
    if (result.status !== 0) {
        console.error(`✗ ${script} failed (exit ${result.status ?? result.signal})`);
        process.exit(result.status || 1);
    }
    console.log(`✓ [${index + 1}/${scripts.length}] ${script} (${elapsed} ms)`);
}

console.log(`All ${scripts.length} frontend regression scripts passed.`);
