# Noor AI CRM Dashboard Stitch References

Source project: `11608146445598504169`

Downloaded assets:
- HTML exports: `html/*.html`
- Screen captures: `screenshots/*.png`

Canonical screens used for implementation:
- `overview-dashboard.11ae808d41994373aed58e5308137615`
- `clients-dialogs-workspace.e4fcd967a8b5492dbb6be99ea6102294`
- `knowledge-editor.9aadd01c15cc4bef97109d946286ef40`
- `queues-escalations-faq.18700c84d0a34995a2b942cb304d9773`
- `catalog-sync.31629e31b6204efc9424f878ec926737`
- `quality-qa-analytics.2f21a06d03aa4095b9c2994e65b2b39e`
- `reports-sales-analytics.f7b9dd1c360d43519dd8d78614cf3da6`
- `settings-system-config.cf1fc90dc3c0419dbbc6a2035049d02e`
- `audit-security-changes.1722df303bf9447d8c2669b3c87e6f40`

Design adaptation notes:
- Keep the Stitch shell: dark left nav, light operational canvas, compact cards, 3-panel conversation and editor workspaces.
- Treat duplicate Stitch screens as variants only; the app uses the real Noor admin sections and existing APIs.
- Do not add manual customer message composition in v1.
- Destructive or externally visible actions keep explicit confirmation.
