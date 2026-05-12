# Orchestrator Handoff

Updated: 2026-05-12
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains exact stock/price and order-execution truth.
- Communication-rules runtime policy is delivered in `main`: first deployed as `8312661c7e4f5468999355520d9c5eb349913868` by GitHub Actions run `25748539979`; runtime `/opt/noor/.release-sha` matched and post-deploy smoke passed (`verify_api.py` 7/0, health 200, `/dashboard/` anonymous 401, `/api/v1/admin/dashboard/metrics/` anonymous 401, Telegram bad secret 403).
- Telegram admin login private-chat flow is delivered: allowlisted Telegram users can request an admin CRM one-time login link in the bot private chat, and `/admin/login` keeps password fallback.
- Noor CRM admin production smoke/regression was completed after the Telegram admin login deployment. The latest admin regression fix batch was delivered in `main` before this tail closeout, including KB delete state handling, Auto-FAQ approval collision handling, Admin AI Quality Controls gating, and the Support view handler.
- Tail closeout task `tj-zi2t` is preserving useful leftover docs/research and integrating only the small safe admin light-theme chart fix. Stale/conflicting final27 implementation branches are not merged in this stream.
- `.codex/project-index.md` is restored as the stable repository navigation map; operational state stays in this handoff and stage history stays under `.codex/stages/`.

## Next recommended

Next stage id: none for communication-rules policy; `tj-7zq7` is delivered.
Recommended action: monitor normal Noor replies for adherence to the client communication rules. The client Russian source is preserved in `docs/04-sales-dialogue-guidelines.md`; `docs/02-tz-extended.md` keeps the client Google Doc pointer, though direct export currently returns a sign-in/storage-access page. The compact English runtime policy is wired through `src/llm/communication_policy.py` and `src/llm/prompts.py`. No admin `SystemPrompt` row was mutated because the code default now supplies `communication_rules_policy` when DB has no active override.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next requested product/runtime stage.
Focus if revisiting communication rules: verify live conversations respect the compact policy and only add an admin `SystemPrompt` override if an owner explicitly wants runtime editing rather than the code default.
Documentation: Context7 PydanticAI docs were checked for dynamic system prompt composition; no provider/model switch was made.
Asset Routing: Skills used: `orchestrator-stage`, `senior-prompt-engineer`, `test-driven-development`, `verification-before-completion`. Agents/personas: none. Catalog candidates: none.
Boundaries: no live WhatsApp test or admin prompt/config mutation was performed for `tj-7zq7`; deployment used the normal `main` GitHub Actions path after explicit approval.

## Explicit defers

- Extended referrals admin/reporting remains intentionally deferred until the client confirms referral policy and reporting requirements.
- `salePrice` remains raw-only until a separate approved sale policy exists; missing/invalid catalog `price` fails closed with manager escalation instead of using Zoho rate as customer-facing fallback.
- DeepSeek V4 Pro is intentionally not being pursued as a production model switch after A/B; the sandbox Bead was deleted earlier per user decision.
- Final acceptance still needs client decisions for UTM/source outbound Zoho field mapping, payment reminder templates/policy before enabling sends, referral rules or written exclusion, and any broader live WhatsApp/media/voice E2E scenarios.
- `codex/tj-final27-acceptance-integration` and child branches `codex/tj-final27-4-voice-audio-acceptance`, `codex/tj-final27-5-6-feedback-referrals`, `codex/tj-final27-7-qa-reporting`, and `codex/tj-final27-8-nonfunctional-readiness` are intentionally not merged by `tj-zi2t`; they are stale relative to `origin/main@01d7fd1` and need a dedicated rebase/integration stage before any delivery.
- Dirty stale worktrees `codex/full-crm-admin` and `codex/orchestration-project-index-baseline` are not merged as branches. Useful material is preserved selectively; deleting those worktrees requires explicit discard approval if local dirt remains.
- Generated temporary PDF render PNGs under `tmp/pdfs/` and duplicate `output/pdf/telegram-reset-instruction-ru.pdf` are not preserved because `docs/client/telegram-reset-instruction-ru.pdf` is already tracked.
