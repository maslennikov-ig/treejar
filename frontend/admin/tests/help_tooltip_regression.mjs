import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, '..');
const tempDir = await mkdtemp(path.join(frontendRoot, '.tmp-help-tooltip-'));

try {
    const source = await readFile(path.join(frontendRoot, 'src', 'components', 'HelpTooltip.tsx'), 'utf8');
    // Instant open/close handlers and a sub-50ms transition; no native title delay.
    for (const handler of ['onMouseEnter', 'onMouseLeave', 'onFocus', 'onBlur', 'onClick']) {
        assert.match(source, new RegExp(handler), `HelpTooltip should handle ${handler}`);
    }
    assert.match(source, /'Escape'/, 'HelpTooltip should close on Escape');
    assert.match(source, /duration-\[40ms\]/, 'Tooltip transition should be below 50ms');
    assert.match(source, /position: 'fixed'/, 'Tooltip should escape clipping containers');
    assert.match(source, /zIndex:\s*9999/, 'Tooltip should use high zIndex above charts and overlays');
    assert.match(source, /createPortal/, 'Tooltip should portal to document.body when available');
    assert.match(source, /window\.innerWidth/, 'Tooltip should clamp to the viewport');
    assert.doesNotMatch(source, /\btitle=/, 'HelpTooltip must not use the native title attribute');

    const result = await build({
        absWorkingDir: frontendRoot,
        stdin: {
            contents: [
                "export { HelpTooltip, SectionInfoBanner } from './src/components/HelpTooltip';",
                "export { LanguageProvider } from './src/i18n';",
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

    const bundlePath = path.join(tempDir, 'help-tooltip.mjs');
    await writeFile(bundlePath, result.outputFiles[0].text);
    const { HelpTooltip, SectionInfoBanner, LanguageProvider } = await import(pathToFileURL(bundlePath).href);

    const tooltipHtml = renderToStaticMarkup(
        React.createElement(HelpTooltip, { text: 'Explains the metric' }),
    );
    assert.match(tooltipHtml, /<button[^>]*type="button"/);
    assert.match(tooltipHtml, /aria-label="Explains the metric"/);
    assert.match(tooltipHtml, /data-tooltip="Explains the metric"/);
    assert.match(tooltipHtml, />\?<\/button>/);
    assert.doesNotMatch(tooltipHtml, /\btitle="/);

    const bannerHtml = (lang) => renderToStaticMarkup(
        React.createElement(
            LanguageProvider,
            { initialLang: lang },
            React.createElement(SectionInfoBanner, {
                storageKey: 'knowledge',
                title: 'Knowledge title',
                description: 'What it does',
                runtime: 'How it reaches Noor',
                actions: React.createElement('button', { type: 'button' }, 'Action'),
            }),
        ),
    );
    const ruBanner = bannerHtml('ru');
    assert.match(ruBanner, /data-section-banner="knowledge"/);
    assert.match(ruBanner, /Knowledge title/);
    assert.match(ruBanner, /What it does/);
    assert.match(ruBanner, /How it reaches Noor/);
    assert.match(ruBanner, /Связь с живым Noor:/);
    assert.match(ruBanner, /Свернуть/);
    assert.match(ruBanner, /aria-expanded="true"/);
    assert.match(ruBanner, />Action</);
    const enBanner = bannerHtml('en');
    assert.match(enBanner, /Live Noor link:/);
    assert.match(enBanner, /Collapse/);
    assert.match(source, /treejar_admin_banner_\$\{storageKey\}/, 'Banner collapse state should persist per storageKey');
} finally {
    await rm(tempDir, { recursive: true, force: true });
}
