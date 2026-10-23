import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-i18n-'));

async function listSources(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    const files = [];
    for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) files.push(...await listSources(full));
        else if (/\.(tsx?|mjs)$/.test(entry.name)) files.push(full);
    }
    return files;
}

try {
    const result = await build({
        absWorkingDir: frontendRoot,
        entryPoints: ['src/i18n.tsx'],
        bundle: true,
        format: 'esm',
        platform: 'node',
        write: false,
        external: ['react', 'react/jsx-runtime'],
        tsconfig: path.join(frontendRoot, 'tsconfig.json'),
    });
    const bundlePath = path.join(tempDir, 'i18n.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);
    const { DICTIONARIES, translate, createI18nValue, LANG_STORAGE_KEY } = await import(pathToFileURL(bundlePath).href);

    const ruKeys = Object.keys(DICTIONARIES.ru).sort();
    const enKeys = Object.keys(DICTIONARIES.en).sort();
    assert.deepEqual(enKeys, ruKeys, 'ru and en dictionaries must have identical key sets');
    assert.ok(ruKeys.length > 400, `expected a full dictionary, got ${ruKeys.length} keys`);
    assert.equal(LANG_STORAGE_KEY, 'treejar_admin_lang');

    const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
    for (const key of ruKeys) {
        const ruText = DICTIONARIES.ru[key];
        const enText = DICTIONARIES.en[key];
        assert.ok(ruText.trim(), `ru.${key} must not be empty`);
        assert.ok(enText.trim(), `en.${key} must not be empty`);
        assert.doesNotMatch(enText, /[А-Яа-яЁё]/, `en.${key} must not contain Cyrillic: ${enText}`);
        assert.deepEqual(placeholders(enText), placeholders(ruText), `placeholders differ for ${key}`);
    }

    // Every section banner exists for all 11 views (keys are built dynamically in App.tsx).
    for (const view of ['overview', 'conversations', 'queues', 'knowledge', 'botRules', 'catalog', 'quality', 'reports', 'settings', 'audit', 'support']) {
        for (const part of ['title', 'body', 'runtime']) {
            assert.ok(DICTIONARIES.ru[`banner.${view}.${part}`], `missing banner.${view}.${part}`);
        }
    }
    // Every AI quality criterion has a label and explanation.
    const criteria = {
        bot_qa: ['greeting_and_identity', 'need_discovery_and_catalog', 'commercial_vat_and_quotation', 'tone_and_language'],
        manager_qa: ['response_speed_sla', 'handover_context_usage', 'professional_tone', 'commercial_terms_accuracy', 'closing_and_crm_hygiene'],
        red_flags: ['missing_identity', 'hard_deflection', 'unverified_commitment', 'ignored_question', 'bad_tone'],
    };
    for (const [scope, keys] of Object.entries(criteria)) {
        assert.ok(DICTIONARIES.ru[`aiqc.criteriaHelp.${scope}`]);
        for (const key of keys) {
            assert.ok(DICTIONARIES.ru[`crit.${scope}.${key}`], `missing label crit.${scope}.${key}`);
            assert.ok(DICTIONARIES.ru[`crit.${scope}.${key}.help`], `missing help crit.${scope}.${key}.help`);
        }
    }

    // Every static t('key') used in the sources exists in the dictionary.
    for (const file of await listSources(path.join(frontendRoot, 'src'))) {
        const source = await readFile(file, 'utf8');
        for (const match of source.matchAll(/\bt\('([^']+)'/g)) {
            assert.ok(match[1] in DICTIONARIES.ru, `${path.relative(frontendRoot, file)} uses unknown key ${match[1]}`);
        }
    }

    assert.equal(translate('ru', 'metric.customersCount', { count: 7 }), 'Клиентов: 7');
    assert.equal(translate('en', 'metric.customersCount', { count: 7 }), 'Customers: 7');
    assert.equal(translate('ru', 'nav.overview'), 'Обзор');
    assert.equal(translate('en', 'nav.overview'), 'Overview');

    const ru = createI18nValue('ru');
    const en = createI18nValue('en');
    assert.equal(ru.formatDuration(45), '45 с');
    assert.equal(en.formatDuration(45), '45s');
    assert.equal(ru.formatDuration(90), '1,5 мин');
    assert.equal(en.formatDuration(90), '1.5 min');
    assert.equal(en.formatDuration(null), '—');
    assert.equal(en.formatNumber(66.666, 1), '66.7');
    assert.equal(ru.formatNumber(66.666, 1), '66,7');
    assert.equal(ru.label('needs_analysis'), 'Потребности');
    assert.equal(en.label('needs_analysis'), 'Needs analysis');
    assert.equal(en.label('custom_code'), 'custom code');
    assert.equal(en.tx('missing.key', 'Fallback'), 'Fallback');
    assert.match(en.formatDateTime('2026-10-23T10:00:00Z'), /2026/);
    assert.match(ru.formatDateTime('2026-10-23T10:00:00Z'), /2026/);
    assert.match(ru.formatDateTime('2026-10-23T10:00:00Z'), /окт/);
    assert.match(en.formatDateTime('2026-10-23T10:00:00Z'), /Oct/);
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
