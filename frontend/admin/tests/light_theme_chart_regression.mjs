import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');

const indexCss = await readFile(path.join(frontendRoot, 'src', 'index.css'), 'utf8');
const indexHtml = await readFile(path.join(frontendRoot, 'index.html'), 'utf8');
const chartTheme = await readFile(path.join(frontendRoot, 'src', 'components', 'charts', 'chartTheme.ts'), 'utf8');
const chartFiles = [
    'ConversationsChart.tsx',
    'SegmentPieChart.tsx',
    'SalesBarChart.tsx',
];

for (const token of [
    '--admin-chart-surface',
    '--admin-chart-border',
    '--admin-chart-title',
    '--admin-chart-muted',
    '--admin-chart-grid',
    '--admin-chart-axis',
    '--admin-chart-tooltip-bg',
]) {
    assert.match(indexCss, new RegExp(token), `Light theme should define ${token}`);
}

assert.match(indexCss, /:where\(\.dark, \.dark \*\)/, 'Dark overrides should be opt-in through the dark class');
assert.match(indexCss, /\.admin-chart-card/, 'Chart card surface should be rendered by a real CSS class');
assert.doesNotMatch(indexHtml, /<html[^>]*class="dark"/, 'Light theme should not be disabled by a hard-coded dark class');
assert.match(chartTheme, /var\(--admin-chart-grid\)/, 'Grid color should come from theme tokens');
assert.match(chartTheme, /var\(--admin-chart-axis\)/, 'Axis color should come from theme tokens');
assert.match(chartTheme, /var\(--admin-chart-tooltip-bg\)/, 'Tooltip background should come from theme tokens');
assert.match(chartTheme, /CHART_CARD_CLASS/, 'Chart panels should share a theme-aware card class');
assert.match(chartTheme, /admin-chart-card/, 'Chart panels should use the real CSS card class');

for (const file of chartFiles) {
    const source = await readFile(path.join(frontendRoot, 'src', 'components', 'charts', file), 'utf8');
    assert.match(source, /CHART_CARD_CLASS/, `${file} should use the shared theme-aware chart card class`);
    assert.doesNotMatch(source, /from-slate-800\/50|to-slate-900\/50/, `${file} should not force dark chart panels in light mode`);
    assert.doesNotMatch(source, /border-white\/\[0\.08\]/, `${file} should not use dark-only borders in light mode`);
    assert.doesNotMatch(source, /text-slate-200/, `${file} should not force dark-title text in light mode`);
}
