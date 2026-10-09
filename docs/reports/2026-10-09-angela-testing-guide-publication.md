# Angela's Noor testing guide — portal publication

Date: 2026-10-09 (Europe/Moscow).
Source branch: `codex/angela-testing-guide-20261009`.
Base: `36c86137a51d2e6485db92c28ec057fe26f03339`.

## Delivered content

- Portal project: `treejar`; artifact: `angela-noor-testing-guide-2026-10`; version: 1.
- Source: `docs/client-answers/angela-noor-testing-guide-2026-10.html`.
- Content SHA-256: `4d992474b1ba4e8ef4f170e7d8f2efa5d20ef026b60996b65761541d8d578d95`.
- Restored the seven scenarios from the existing Angela guide, grouped into four independent WhatsApp routes.
- Added 14 copy actions and 14 per-step reply fields, seven outcome selectors, seven scenario notes, tester identity/date and a final comment.
- Added the test WhatsApp entry link, clean-dialogue instructions, photo resend and quotation duplicate checks.
- The existing September artifact, its version, links and saved draft were independently compared before/after publication and remained identical.

## Verification

- Artifact linter: 0 errors, 0 warnings.
- Preview layout: 400, 800, 1440 pixels with both browser colour preferences; no horizontal overflow, minimum text 12 pixels. Mobile and desktop screenshots visually inspected.
- Browser checks: seven scenarios, 14 reply fields/copy actions, seven initially unanswered outcomes, unique IDs, named controls, one submit action. All copy buttons passed.
- Local host fixture: draft restore, partial-submission warning and final read-only state passed. These are local checks, not live submit evidence.
- Live browser: actual draft POST returned HTTP 200; a separate authenticated portal read confirmed the exact field values. Reload restored the same values.
- Live draft used a separate token labelled technical verification. Its latest draft was cleared; no submit request or Telegram notification occurred.
- The Angela link was independently checked empty and editable; its copy action worked; browser errors: 0.
- Live publication succeeded with HTTP 200, version 1. Page and screenshots checked in a real browser.

The page is published and usable. This acceptance checks the instruction and its forms; it does not score the sales bot or execute WhatsApp/quotation scenarios.

## Operational notes

- Bearer links and API secrets are excluded from this report. Private publish/QA receipts are under ignored `.tmp/current/`, mode 0600. The client link is provided in the user-facing delivery.
- The standard wrapper encountered a pre-existing pnpm version mismatch (required 10.33.4, installed 12.4.2). Used the installed tsx runtime and existing portal validation/preview tools without changing package configuration. Publication used the documented portal REST API with canonical `source_repo=treejar`.
- No runtime code or deployment was changed.
