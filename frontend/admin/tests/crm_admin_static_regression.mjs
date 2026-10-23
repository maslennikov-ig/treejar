import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const appSource = await readFile(path.join(frontendRoot, 'src', 'App.tsx'), 'utf8');
const sidebarSource = await readFile(path.join(frontendRoot, 'src', 'components', 'Sidebar.tsx'), 'utf8');
const themeSource = await readFile(path.join(frontendRoot, 'src', 'theme.tsx'), 'utf8');
const canonicalBtnSource = await readFile(path.join(frontendRoot, 'src', 'components', 'CanonicalSyncButton.tsx'), 'utf8');
const overviewSource = await readFile(path.join(frontendRoot, 'src', 'views', 'OverviewView.tsx'), 'utf8');
const conversationsSource = await readFile(path.join(frontendRoot, 'src', 'views', 'ConversationsView.tsx'), 'utf8');
const queuesQualitySource = await readFile(path.join(frontendRoot, 'src', 'views', 'QueuesQualityView.tsx'), 'utf8');
const kbSource = await readFile(path.join(frontendRoot, 'src', 'views', 'KnowledgeBaseView.tsx'), 'utf8');
const botRulesSource = await readFile(path.join(frontendRoot, 'src', 'views', 'BotRulesView.tsx'), 'utf8');
const catalogSource = await readFile(path.join(frontendRoot, 'src', 'views', 'CatalogView.tsx'), 'utf8');
const reportsSource = await readFile(path.join(frontendRoot, 'src', 'views', 'ReportsView.tsx'), 'utf8');
const auditSystemSource = await readFile(path.join(frontendRoot, 'src', 'views', 'AuditSystemView.tsx'), 'utf8');
const apiSource = await readFile(path.join(frontendRoot, 'src', 'api', 'crm.ts'), 'utf8');
const typeSource = await readFile(path.join(frontendRoot, 'src', 'types', 'crm.ts'), 'utf8');
const i18nSource = await readFile(path.join(frontendRoot, 'src', 'i18n.tsx'), 'utf8');

function assertDictionaryEntry(key, text, message) {
    const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const escapedText = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(i18nSource, new RegExp(`'${escapedKey}': '${escapedText}`), message ?? `i18n should map ${key} to ${text}`);
}

// 1. Variant 1B Navigation: 9 sections in 3 groups
const NAV_LABELS = {
    'nav.overview': 'Обзор',
    'nav.conversations': 'Клиенты и диалоги',
    'nav.queuesQuality': 'Очереди и качество',
    'nav.knowledge': 'База знаний',
    'nav.botRules': 'Правила бота',
    'nav.catalogInventory': 'Каталог и остатки',
    'nav.reports': 'Отчеты',
    'nav.settings': 'Настройки',
    'nav.auditSystem': 'Аудит и статус системы',
};
for (const [key, label] of Object.entries(NAV_LABELS)) {
    assert.match(sidebarSource, new RegExp(`labelKey: '${key.replace('.', '\\.')}'`), `Sidebar navigation should include ${key}`);
    assertDictionaryEntry(key, label, `i18n should include ${label}`);
}
for (const groupKey of ['nav.group.operations', 'nav.group.knowledge', 'nav.group.system']) {
    assert.match(sidebarSource, new RegExp(`groupKey: '${groupKey.replaceAll('.', '\\.')}'`), `Sidebar should render group ${groupKey}`);
}

// 2. Theme system (Light & Dark themes without mixed dark sidebar in light mode)
assert.match(themeSource, /treejar_admin_theme/, 'ThemeProvider should persist to treejar_admin_theme');
assert.doesNotMatch(sidebarSource, /bg-slate-950|bg-\[#131b2e\]/, 'Sidebar must not hardcode dark surface in light theme');
assert.match(appSource, /<ThemeProvider\b/, 'App should wrap with ThemeProvider');

// 3. Variant 5A Overview Bento Grid
assert.match(overviewSource, /data-overview-attention-bar/, 'Overview should render attention strip');
assert.match(overviewSource, /data-overview-bento-grid/, 'Overview should render Bento grid');
assert.match(overviewSource, /lg:col-span-7/, 'Left Bento column should span 7/12');
assert.match(overviewSource, /lg:col-span-5/, 'Right Bento column should span 5/12');

// 4. Variant 4A Conversations: 2 columns + CRM Drawer + typed RESET
assert.match(conversationsSource, /lg:grid-cols-\[340px_minmax\(420px,1fr\)\]/, 'Conversations should use 2-column layout');
assert.match(conversationsSource, /<Drawer/, 'Conversations should render CRM & details in a right Drawer');
assert.match(conversationsSource, /requireTypedText="RESET"/, 'Customer reset must require typing RESET');
assert.match(conversationsSource, /executeConversationReset\(detail\.id\)/);
assert.match(conversationsSource, /closeConversationEscalation\(openEsc\.id\)/);
assert.match(conversationsSource, /useAIQualityControlBlock\('bot_qa', 'Bot QA'\)/);

// 5. Variant 1B Queues & Quality (3 tabs: escalations, manager_deals, ai_rubric)
assert.match(queuesQualitySource, /closeConversationEscalation/);
assert.match(queuesQualitySource, /fetchPendingManagerReviews/);
assert.match(queuesQualitySource, /evaluateManagerReview/);
assert.match(queuesQualitySource, /useAIQualityControlBlock\('manager_qa', 'Manager QA'\)/);
assert.match(queuesQualitySource, /BOT_QA_RUBRIC_ITEMS/, 'Queues & Quality should include the 15-criterion Noor rubric reference');

// 6. Variant 2A & 3A Knowledge Base & Bot Rules
assert.match(kbSource, /lg:grid-cols-\[minmax\(320px,35%\)_1fr\]/, 'KB should use 35/65 Master-Detail layout');
assert.match(kbSource, /<CanonicalSyncButton kind="knowledge"/);
assert.match(kbSource, /runCanonicalSync\('knowledge', 'safe'\)/, 'KB should auto-seed canonical templates when empty');
assert.match(botRulesSource, /lg:grid-cols-\[minmax\(320px,35%\)_1fr\]/, 'Bot Rules should use 35/65 Master-Detail layout');
assert.match(botRulesSource, /<CanonicalSyncButton kind="botRules"/);
assert.match(botRulesSource, /form\.scope !== 'global'/, 'Bot Rules should hide stage/language/segment when scope is global');
assert.match(canonicalBtnSource, /fetchCanonicalKnowledgeBasePreview/);
assert.match(canonicalBtnSource, /fetchCanonicalBotRulesPreview/);

// 7. Catalog, Reports, Audit & System Health
assert.match(catalogSource, /fetchCatalogStatus/);
assert.match(catalogSource, /syncProducts/);
assert.match(reportsSource, /generateOperationsReport/);
assert.match(auditSystemSource, /fetchSystemHealth/);

// 8. Global safety invariants
assert.match(sidebarSource, /t\('app\.monitoringMode'\)/);
assertDictionaryEntry('app.monitoringMode', 'Режим мониторинга');
for (const source of [appSource, conversationsSource, queuesQualitySource, kbSource, botRulesSource]) {
    assert.doesNotMatch(source, /globalThis\.alert\(/, 'Views must not use alert(JSON)');
    assert.doesNotMatch(source, /globalThis\.confirm\(/, 'Views must use ConfirmDialog instead of browser confirm()');
}
for (const source of [appSource, i18nSource]) {
    assert.doesNotMatch(source, /compose/i);
    assert.doesNotMatch(source, /Создать рассылку/);
    assert.doesNotMatch(source, /рассыл/i);
}

// 9. API & Types contract
for (const apiPath of [
    '/crm/customers',
    '/crm/conversations/',
    '/crm/escalations',
    '/catalog/status',
    '/crm/audit',
    '/system/health',
    '/knowledge-base/entries',
    '/knowledge-base/candidates',
    '/knowledge-base/sync-canonical',
    '/knowledge-base/sync-canonical/preview',
    '/bot-rules/rules',
    '/bot-rules/preview',
    '/bot-rules/sync-canonical',
    '/bot-rules/sync-canonical/preview',
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
    'AdminCanonicalSyncPreview',
    'AdminCatalogStatusResponse',
    'AdminSystemHealthResponse',
]) {
    assert.match(typeSource, new RegExp(`interface ${typeName}`));
}
