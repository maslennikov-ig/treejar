import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const appSource = await readFile(path.join(frontendRoot, 'src', 'App.tsx'), 'utf8');
const apiSource = await readFile(path.join(frontendRoot, 'src', 'api', 'crm.ts'), 'utf8');
const typeSource = await readFile(path.join(frontendRoot, 'src', 'types', 'crm.ts'), 'utf8');

for (const label of [
    'Обзор',
    'Клиенты и диалоги',
    'Очереди',
    'База знаний',
    'Правила бота',
    'Каталог',
    'Качество',
    'Отчеты',
    'Настройки',
    'Аудит',
]) {
    assert.match(appSource, new RegExp(label), `CRM navigation should include ${label}`);
}

assert.match(appSource, /grid h-\[calc\(100vh-145px\)\] grid-cols-\[320px_minmax\(360px,1fr\)_340px\]/);
assert.match(appSource, /bg-\[#131b2e\]/);
assert.match(appSource, /bg-\[#2170e4\]/);
assert.match(appSource, /Noor AI/);
assert.match(appSource, /fetchPendingManagerReviews/);
assert.match(appSource, /fetchAIQualityControls/);
assert.match(appSource, /generateOperationsReport/);
assert.match(appSource, /syncProducts/);
assert.match(appSource, /Reset preview/);
assert.match(appSource, /globalThis\.confirm\('Показать preview reset/);
assert.match(appSource, /globalThis\.confirm\('Удалить запись мягко\?'/);
assert.match(appSource, /handleDelete\(selected\)/);
assert.match(appSource, /globalThis\.confirm\('Архивировать правило бота\?'/);
assert.match(appSource, /Applied bot rules/);
assert.match(appSource, /useAIQualityControlBlock\('bot_qa', 'Bot QA'\)/);
assert.match(appSource, /useAIQualityControlBlock\('manager_qa', 'Manager QA'\)/);
assert.match(appSource, /отключена в Admin AI Quality Controls/);
assert.match(appSource, /setActiveView\('support'\)/);
assert.match(appSource, /function SupportView/);
assert.match(appSource, /Режим мониторинга/);
assert.doesNotMatch(appSource, /compose/i);
assert.doesNotMatch(appSource, /Создать рассылку/);
assert.doesNotMatch(appSource, /рассыл/i);

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
