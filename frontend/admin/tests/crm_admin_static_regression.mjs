import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const appSource = await readFile(path.join(frontendRoot, 'src', 'App.tsx'), 'utf8');
const apiSource = await readFile(path.join(frontendRoot, 'src', 'api', 'crm.ts'), 'utf8');
const typeSource = await readFile(path.join(frontendRoot, 'src', 'types', 'crm.ts'), 'utf8');
const i18nSource = await readFile(path.join(frontendRoot, 'src', 'i18n.tsx'), 'utf8');

function assertDictionaryEntry(key, text, message) {
    const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const escapedText = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(i18nSource, new RegExp(`'${escapedKey}': '${escapedText}`), message ?? `i18n should map ${key} to ${text}`);
}

const NAV_LABELS = {
    'nav.overview': 'Обзор',
    'nav.conversations': 'Клиенты и диалоги',
    'nav.queues': 'Очереди',
    'nav.knowledge': 'База знаний',
    'nav.botRules': 'Правила бота',
    'nav.catalog': 'Каталог',
    'nav.quality': 'Качество',
    'nav.reports': 'Отчеты',
    'nav.settings': 'Настройки',
    'nav.audit': 'Аудит',
};
for (const [key, label] of Object.entries(NAV_LABELS)) {
    assert.match(appSource, new RegExp(`labelKey: '${key.replace('.', '\\.')}'`), `CRM navigation should include ${key}`);
    assertDictionaryEntry(key, label, `CRM navigation should include ${label}`);
}

assert.match(appSource, /grid h-\[calc\(100vh-145px\)\] grid-cols-\[320px_minmax\(360px,1fr\)_340px\]/);
assert.match(appSource, /bg-\[#131b2e\]/);
assert.match(appSource, /bg-\[#2170e4\]/);
assert.match(appSource, /Noor AI/);
assert.match(appSource, /fetchPendingManagerReviews/);
assert.match(appSource, /fetchAIQualityControls/);
assert.match(appSource, /generateOperationsReport/);
assert.match(appSource, /syncProducts/);
assert.match(appSource, /t\('conv\.action\.resetPreview'\)/);
assertDictionaryEntry('conv.action.resetPreview', 'Reset preview');
assert.match(appSource, /globalThis\.confirm\(t\('conv\.confirmResetPreview'\)\)/);
assertDictionaryEntry('conv.confirmResetPreview', 'Показать предпросмотр сброса');
assert.match(appSource, /globalThis\.confirm\(t\('kb\.confirmDelete'\)\)/);
assertDictionaryEntry('kb.confirmDelete', 'Удалить запись мягко?');
assert.match(appSource, /handleDelete\(selected\)/);
assert.match(appSource, /globalThis\.confirm\(t\('botRules\.confirmArchive'\)\)/);
assertDictionaryEntry('botRules.confirmArchive', 'Архивировать правило бота?');
assert.match(appSource, /t\('conv\.inspector\.appliedRules'\)/);
assertDictionaryEntry('conv.inspector.appliedRules', 'Applied bot rules');
assert.match(appSource, /useAIQualityControlBlock\('bot_qa', 'Bot QA'\)/);
assert.match(appSource, /useAIQualityControlBlock\('manager_qa', 'Manager QA'\)/);
assertDictionaryEntry('qcBlock.disabled', '{label} отключена в «Контроль качества AI»');
assertDictionaryEntry('qcBlock.disabled', '{label} is disabled in AI Quality Controls');
assert.match(appSource, /setActiveView\('support'\)/);
assert.match(appSource, /function SupportView/);
assert.match(appSource, /t\('app\.monitoringMode'\)/);
assertDictionaryEntry('app.monitoringMode', 'Режим мониторинга');
for (const source of [appSource, i18nSource]) {
    assert.doesNotMatch(source, /compose/i);
    assert.doesNotMatch(source, /Создать рассылку/);
    assert.doesNotMatch(source, /рассыл/i);
}

// Reset preview is a structured card wired to the existing execute endpoint.
assert.doesNotMatch(appSource, /globalThis\.alert\(/, 'Reset preview must not use alert(JSON)');
assert.match(appSource, /function ResetPreviewCard/);
assert.match(appSource, /executeConversationReset\(detail\.id\)/);
assert.match(apiSource, /\/reset\/execute/);
assert.match(apiSource, /confirm: true/);

// Canonical Treejar sync endpoints.
assert.match(apiSource, /'\/knowledge-base\/sync-canonical'/);
assert.match(apiSource, /'\/bot-rules\/sync-canonical'/);
assert.match(appSource, /<CanonicalSyncButton kind="knowledge"/);
assert.match(appSource, /<CanonicalSyncButton kind="botRules"/);

for (const apiPath of [
    '/crm/customers',
    '/crm/conversations/',
    '/crm/audit',
    '/knowledge-base/entries',
    '/knowledge-base/candidates',
    '/bot-rules/rules',
    '/bot-rules/preview',
]) {
    assert.match(apiSource, new RegExp(apiPath.replaceAll('/', '\\/')));
}

assert.ok(
    apiSource.includes('/knowledge-base/candidates/${candidateId}/reject'),
    'CRM API should expose Auto-FAQ reject endpoint',
);

for (const typeName of [
    'AdminConversationDetail',
    'AdminTimelineMessage',
    'AdminKnowledgeBaseRead',
    'AdminKnowledgeBaseCandidate',
    'AdminBotRuleRead',
    'AdminBotRulePreviewResponse',
    'AdminBotRuleApplied',
    'AdminActionAuditRead',
]) {
    assert.match(typeSource, new RegExp(`interface ${typeName}`));
}
