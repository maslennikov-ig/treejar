# Prompt: tj-final27.4 Controlled Voice E2E Agent

Use `$orchestrator-stage` in `/home/me/code/treejar`. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-27-final-delivery-completion.md`, `.codex/stages/tj-final27/summary.md`, and this prompt first.

You are running the approval-only voice/audio acceptance pass for Bead `tj-final27.4` against `https://noor.starec.ai`.

## Approval Gate

Do not send any live WhatsApp voice/audio/media message until the user explicitly approves all of:

- exact test phone and channel;
- unique synthetic suffix prefix;
- English and/or Arabic voice sample text;
- whether admin/DB readback may inspect audio/transcription/usage rows;
- stop conditions and cleanup expectations.

If any item is missing, stop before live messages and return an artifact marking live voice E2E deferred pending approval.

## Scope After Approval

Use only the approved test identity and unique suffixes beginning `tj-final27-voice`. Cover:

1. Runtime/API smoke:
   - current production release SHA and run id if available;
   - `/api/v1/health`;
   - anonymous `/dashboard/`, `/admin/`, and protected conversation API auth guards.
2. English voice:
   - send one short approved voice note asking for a normal product recommendation;
   - verify the bot answers based on the transcribed content, not just on the existence of audio.
3. Arabic voice:
   - send one short approved Arabic voice note asking for a normal product recommendation;
   - verify the bot answers in Arabic and remains commercially safe.
4. Audit/readback:
   - read the corresponding `messages` rows through approved admin/API/DB readback;
   - verify inbound voice/audio `message_type`, `audio_url`, `transcription`, `model`, `tokens_in`, `tokens_out`, and `cost` when provider usage/cost is returned;
   - verify outbound bot reply audit rows and conversation state.
5. Final pending count:
   - count only the approved `tj-final27-voice` synthetic conversations;
   - verify no unexpected pending escalation remains.

## Hard Guardrails

Do not run:

- `scripts/verify_wazzup.py`;
- broad production suites;
- deploys, prod/staging config changes, secret changes, or permission changes;
- payment reminder sends/templates;
- referral or feedback live branches;
- arbitrary media uploads outside the approved voice samples;
- oversized-audio or intentionally corrupted-audio production tests.

Oversized and unreadable audio behavior is covered by local unit tests. Do not simulate it in production by uploading large or malformed files.

Do not print or store raw secrets. Use existing approved access paths only.

## Evidence Required

Create artifact `.codex/stages/tj-final27/artifacts/tj-final27.4-voice-e2e.md` or append to the active `tj-final27.4` artifact with:

- approval text/date and exact allowed scenarios;
- runtime SHA and run id if available;
- commands and readback methods used;
- phone suffixes and conversation IDs;
- transcription snippets sufficient to prove EN/AR content was understood;
- model/tokens/cost values when available;
- outbound audit evidence;
- pending count;
- explicit skipped guardrail actions.

If approval is not present, do not run live E2E. Record the defer as: `Live voice E2E deferred pending explicit approval for phone/channel/suffix/scenarios`.
