# Orchestrator Handoff

Updated: 2026-05-12
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains exact stock/price and order-execution truth.
- Latest deployed baseline before this tail closeout is `main@01d7fd16b5174c6f15b7e81eb7e78a380497b1b1` (`docs(orchestration): record prelaunch e2e closeout`), delivered by GitHub Actions run `25715145758`; runtime `/opt/noor/.release-sha` matched and post-deploy smoke passed (`verify_api.py` 7/0, `/dashboard/` anonymous 401, bad Telegram token 401, health 200).
- Telegram admin login private-chat flow is delivered: allowlisted Telegram users can request an admin CRM one-time login link in the bot private chat, and `/admin/login` keeps password fallback.
- Noor CRM admin production smoke/regression was completed after the Telegram admin login deployment. The latest admin regression fix batch was delivered in `main` before this tail closeout, including KB delete state handling, Auto-FAQ approval collision handling, Admin AI Quality Controls gating, and the Support view handler.
- Tail closeout task `tj-zi2t` is preserving useful leftover docs/research and integrating only the small safe admin light-theme chart fix. Stale/conflicting final27 implementation branches are not merged in this stream.
- `.codex/project-index.md` is restored as the stable repository navigation map; operational state stays in this handoff and stage history stays under `.codex/stages/`.

## Next recommended

Next stage id: create a fresh Beads task/stage for the communication-rules compliance work.
Recommended action: start from current `origin/main` after `tj-zi2t` lands. First locate the client's Russian communication rules, translate/condense them into an English runtime policy artifact, then wire them into the agent behavior with focused tests. Do not mix this with stale `tj-final27` integration branches.

## Starter prompt for next orchestrator

Use $orchestrator-stage. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `.codex/project-index.md`, and the relevant prompt/LLM files first.
Worktree: create a fresh isolated worktree from current `origin/main`.
Task: find the client-provided communication rules, determine where current agent instructions are built, and implement a token-efficient English policy layer that makes the agent follow those rules without bloating the main prompt. Add targeted tests for the most important rule failures. If the rules are in Russian, preserve the original source and add a concise English runtime version.
Documentation: use MCP Context7 only if implementation touches version-sensitive library/framework/API behavior; otherwise no external docs are needed.
Asset Routing: Skills: `orchestrator-stage`, `senior-prompt-engineer` if useful for policy compression, `systematic-debugging` if reproducing a rule failure. Agents/personas: none unless the user explicitly authorizes subagents. Catalog candidates: none.
Boundaries: no deploy, production mutation, broad live WhatsApp testing, or prompt rewrite beyond the communication-rules scope without explicit approval.

## Explicit defers

- Extended referrals admin/reporting remains intentionally deferred until the client confirms referral policy and reporting requirements.
- `salePrice` remains raw-only until a separate approved sale policy exists; missing/invalid catalog `price` fails closed with manager escalation instead of using Zoho rate as customer-facing fallback.
- DeepSeek V4 Pro is intentionally not being pursued as a production model switch after A/B; the sandbox Bead was deleted earlier per user decision.
- Final acceptance still needs client decisions for UTM/source outbound Zoho field mapping, payment reminder templates/policy before enabling sends, referral rules or written exclusion, and any broader live WhatsApp/media/voice E2E scenarios.
- `codex/tj-final27-acceptance-integration` and child branches `codex/tj-final27-4-voice-audio-acceptance`, `codex/tj-final27-5-6-feedback-referrals`, `codex/tj-final27-7-qa-reporting`, and `codex/tj-final27-8-nonfunctional-readiness` are intentionally not merged by `tj-zi2t`; they are stale relative to `origin/main@01d7fd1` and need a dedicated rebase/integration stage before any delivery.
- Dirty stale worktrees `codex/full-crm-admin` and `codex/orchestration-project-index-baseline` are not merged as branches. Useful material is preserved selectively; deleting those worktrees requires explicit discard approval if local dirt remains.
- Generated temporary PDF render PNGs under `tmp/pdfs/` and duplicate `output/pdf/telegram-reset-instruction-ru.pdf` are not preserved because `docs/client/telegram-reset-instruction-ru.pdf` is already tracked.
