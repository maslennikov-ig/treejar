# Code Review: Telegram reset webhook reconciliation

**Date**: 2026-09-22
**Scope**: restore-mode startup webhook reconciliation and focused regressions
**Base**: `origin/main` at `90966f2868137d78d7bfd0e863f97fdf7921c92f`
**Files**: 4 implementation/test files | **Changes**: +53 / -12 before this report

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 0    | 0      | 0   |
| Improvements | —        | 0    | 0      | 0   |

**Verdict**: PASS

The change restores canonical Telegram webhook registration during
`TEST_CHANNEL_RESTORE_MODE` while keeping the existing authenticated handler
restriction. Command-menu synchronization is suppressed in that mode, so the
change does not advertise the normal manager actions while they are disabled.

## Issues

None.

## Improvements

None required for this focused repair.

## Positive Patterns

- `src/main.py:31` preserves the restore-mode boundary and changes only startup
  registration behavior.
- `src/integrations/notifications/telegram_webhook.py:46` keeps the existing
  derived secret, canonical URL, bounded Telegram client timeout, and allowed
  update list.
- The focused tests cover both lifecycle dispatch and the absence of command-menu
  publication in restore mode.

## Escalation

This crosses an external webhook and authentication boundary. Review confirmed
that inbound requests still require the derived secret, configured admin chat,
requester binding, and explicit reset confirmation. Production `setWebhook` and
deployment remain separate, owner-authorized actions and were not performed.

## Validation

- Focused pytest: PASS, 61 passed.
- Ruff check and format check on changed Python files: PASS.
- Mypy on changed runtime modules: PASS.
- Production diagnosis was read-only: Telegram remained registered to the stale
  relay and reported a timeout; Noor had no pending reset token or new reset.
