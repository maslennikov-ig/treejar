# Noor pilot and model readiness — 31 October 2026

Delivered at 21:35 Moscow: main chat now selects **openai/gpt-6.1-sol / medium** in app and worker. Paid test cost **$0.001346 of $0.10**. Runtime/CI receipts and exact remaining client-pilot boundary are below.

Task: tj-3jcn. Baseline and observed live release: `0f9c97bd665258f4d13b007d915443cf681b0391`. Branch: `codex/noor-pilot-sol-20261031`. Initial audit/preparation was local and read-only. The later authorized provider test and model delivery are recorded in the final section; no customer sends or pilot/channel activation are included.

## Live observations, approximately 20:31–20:33 Moscow

Application, worker, database, Redis and nginx were up; health returned the release above and healthy dependencies. `bot_enabled=true`, restore mode true. Sender and outbound allowlist both equal test0665. Wazzup test0665 reports `qridle`; business9235 reports active. The global callback points to the customer audit receiver, with its private query omitted; callback auto-repair is disabled. These facts do not establish an unauthorized callback change. Do not turn the guard on against the intended customer router.

The latest persisted inbound is 19 October 19:08 UTC and assistant reply 19:09:57 UTC; no rows were found from 24 October onward. Absence in Noor storage is not absence of WhatsApp traffic or proof of client inactivity. Actual forwarding by the customer receiver remains unverified. Reconnecting0665 is necessary only if that channel will be used. A shared business-number pilot instead needs authorization/configuration of the active business channel at both inbound and outbound boundaries, and an explicit review of restore mode and worker registration.

The tj-asty source commit `c44cade` is an ancestor of live source `0f9c97b`; the old local-only labels are stale. Source inclusion does not prove current behavior or pilot acceptance.

## Pilot decisions and customer developer handoff

Published client page, version 2: https://aidevteam.ru/a/S1zQSadyVtJDNCkX2FO10BMX2c2ODIk0

Source: `docs/client-answers/noor-nikita-pilot-2026-10.html`. Customer developer prompt: `docs/prompts/2026-10-31-customer-claude-noor-pilot.md`.

The page recommends alternating eligible new leads 50/50 and keeping their owner for the ongoing dialogue. Even/odd dates remain a client choice, with timezone and even-date owner. It collects scope, duration/start, quote actions, separate CRM-write authority, delivery/assembly facts, comparison criteria, reviewers and technical/on-call ownership. Existing unfinished dialogues stay with the current owner. Submission collects decisions and does not activate customer replies. Partial or contradictory choices require clarification. Existing delivery-fee factual gap remains tracked in tj-z3hw.

Both assistants need one durable dialogue owner and coordinated final-send control, including greetings and scheduled follow-ups. Noor's internal locks, deduplication and manager takeover do not coordinate another bot. An inbound copy is insufficient; a stale answer after ownership transfer must be fenced out at the final send boundary. The prompt is self-contained for a customer developer without repository access. It begins with discovery/local changes, then returns exact activation and rollback steps for approval.

## Initial model inventory and proposed helper roles

Configuration below reflects the initial audit, before the separately authorized Sol probe; it is not evidence of earlier model invocation.

| Workload | Current configuration / source | Proposed role, not yet activated |
|---|---|---|
| Main chat, catalogue correction and relevant order subroutes | DB override and ENV both `openai/gpt-6-luna` | `openai/gpt-6.1-sol` after provider proof |
| Sales follow-ups | Main ENV Luna, import-time agent; restore-mode worker limits jobs | Unchanged in this slice; consider Sol separately for client-visible selling |
| Conversation summaries | Fast `deepseek/deepseek-v4-flash`; newest stored summary 19 October | GPT-6 Luna candidate |
| Ambiguous fact extraction | Fast DeepSeek; customer_facts_mode disabled | Luna candidate; enabling remains separate |
| Safety/repair reader | Pinned DeepSeek constant, independent of FAST ENV | GPT-6.1 Terra candidate, preserving the safety/output contract |
| Bot QA, red flags, manager QA | Each DB config selects DeepSeek; all three modes disabled | Terra candidate; enabling and evaluation remain separate |
| Response adaptation / AutoFAQ | Fast DeepSeek; FAQ fallback uses main ENV Luna | Luna candidate, with approval before publishing knowledge |
| Speech transcription | `openai/gpt-4o-mini-transcribe`, dedicated audio endpoint | Keep a speech model |
| Retrieval embeddings | Local `BAAI/bge-m3`, 1024 dimensions | Keep; migration needs an index rebuild and retrieval validation |

Locations: src/core/config.py; src/llm/safety.py; src/llm/message_processor.py; src/llm/conversation_summary.py; src/llm/fact_extractor.py; src/llm/repair_judge.py; src/quality/config.py; src/llm/response_adapter.py; src/integrations/voice/voxtral.py; src/rag/embeddings.py. Proposed tiers are validation hypotheses, not a measured sales-quality ranking. Existing Bot QA and Manager QA evaluate different populations/scales and are not an A/B comparison of Nikita and Noor.

## Sol compatibility, local candidate and remaining authority

OpenRouter public model/endpoint metadata on 31 October includes `openai/gpt-6.1-sol`, `openai/gpt-6.1-terra` and `openai/gpt-6-luna`, including tools, reasoning and structured outputs. `openai/gpt-6-terra` was absent. Base Sol input/output rates are $2/$10 per million tokens versus Luna $0.10/$0.50; cache writes, retries and token use prevent translating this 20x unit-price ratio directly to a conversation bill. The key had $1.131057066 remaining under its current limit. No top-up or limit change was attempted.

The local safety.py candidate adds explicit medium reasoning only for core_chat with the exact Sol ID. The future model switch uses the existing DB override; global ENV/default stays Luna to preserve follow-up and AutoFAQ fallback. Chat limits stay 3200 tokens / 90 seconds; current core_chat does not set temperature.

Five added regression cases cover Sol bounds/isolation plus DB override through the actual SDK HTTP serialization, synthetic tool result and final text, using MockTransport and an invalid host (no network). The focused safety module passed 48 tests. This is local adapter proof, not a real provider tool-cycle result.

Official OpenAI guidance says Sol tools require Responses; Noor currently uses OpenRouter's Chat adapter, and OpenRouter declares normalized tool support. Before switching, obtain approval for one short synthetic two-completion provider cycle, one fake product tool, no customer data/CRM/outgoing message, target budget $0.10. Explicitly suppress/intercept SDK, outer-agent AND production-adapter retries; the existing scenario meter is not a guaranteed monetary cap. Record generation IDs, finish reasons, token counts, latency and billed/unknown costs. If the current gateway cannot complete tools, present the smallest Responses adapter migration separately; do not strip tools or substitute another target.

After provider acceptance, proposed production action: deliver this narrow source candidate through the approved release path and update only `system_configs.openrouter_model_main` to `openai/gpt-6.1-sol`. Preserve the previous DB value and release for rollback. Do not change the audit callback, channel allowlists, helper models, disabled jobs or client pilot state. AGENTS.md requires explicit release/production authority. The customer pilot remains separately gated by submitted decisions, shared final-send coordination, authorized channel/restore-mode choices and fresh round-trip proof.

## Verification and delivery

- Artifact lint: 0 errors / 0 warnings. Responsive/layout checks passed at 400/800/1440 px in dark/light, no horizontal document overflow; screenshots visually inspected.
- Local browser test: partial-answer warning; 17 stable named fields serialized; one simulated host acknowledgement; final readonly state. No test values entered or submitted on the live client page.
- Published page inspected separately without entering answers; 31 named controls (17 unique names), 13 radios, 7 question containers, one enabled submit button; no answer entered.
- Safety module: 48/48 tests; metadata/repinning checks: 54/54 tests; affected Ruff/format, git diff and repinning checks pass. Full release suite and provider acceptance are not claimed.
- The model delivery is accepted below; client pilot work is separately tracked in tj-r62i. No client traffic was activated by the model switch.
- CLI wrapper encountered installed pnpm12 versus declared pnpm10; used the same installed tsx entrypoints directly without changing dependencies or package-manager configuration. Browser form test used a local HTTP preview and simulated host; its font-file console errors do not characterize production. Full file previews and the published page use the portal renderer.

## Sources

- https://openrouter.ai/api/v1/models
- https://openrouter.ai/api/v1/models/openai/gpt-6.1-sol/endpoints
- https://openrouter.ai/openai/gpt-6.1-sol
- https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-update-api-and-model-parameters
- https://openrouter.ai/docs/guides/features/tool-calling
- https://wazzup24.com/help/api/channels/

## Authorized Sol provider acceptance and delivery (same day)

The owner explicitly authorized a test within $0.10 and, if successful, deployment of the main-chat switch. The actual candidate OpenRouterTelemetryChatModel plus PydanticAI Agent completed the synthetic lookup tool and final sales reply through OpenRouter. Exactly two paid POSTs cost $0.000582 + $0.000764 = $0.001346. Both response usage and generation metadata agree. Actual SDK wire payloads carried exact Sol/medium, the controlled output ceiling, no temperature, pinned OpenAI/no fallback and maximum provider prices. A conservative predispatch reservation bounded cumulative calls under $0.10; SDK, agent and adapter retries were disabled. No real CRM/customer data or outgoing messages were used.

The first local observer stopped because the generation receipt was not indexed immediately, despite a successful tool-call completion. Initial evidence is retained in 2026-10-31-sol-provider-probe-initial.json. A later read confirmed the $0.000582 cost; the exact first response was replayed to the isolated SDK without another model POST, then the second paid completion finished successfully. Final receipt: 2026-10-31-sol-provider-probe.json. This preserves the failed observer rather than hiding or repaying it.

Private rollback: /opt/noor/.hotfix-backups/tj-3jcn-sol-20261031T181216Z (environment, compose, previous policy, previous DB model row, protected settings and tagged app/worker images). Production activation is now authorized for this model change; the customer pilot/channel changes remain outside it. Next: canonical CI delivery, exact release and worker safety readback, then compare-and-set only the main DB setting. Runtime delivery proof will follow separately.

Initial canonical CI 41228818576 on b056e76 passed lint/types and 4857 tests but failed one process-verification test because this task's handoff addition exceeded the 200-line current-state limit (203 lines). Deployment was skipped and the live DB was not changed. The correction compacts only this task's entry, retains all prior project context, and re-pins declared current-state metadata. The original failed CI remains part of the evidence.

## Technical premortem for the authorized rollout

Verdict: GO WITH CONDITIONS — canonical checks must pass; exact runtime source/hash and protected settings must match before the single-row switch. Scope: main chat and existing DB-backed order subroutes. Source rollback and previous DB row are retained privately; no database restore or customer replay is required.

| Failure symptom | Evidence / mechanism | Detection and mitigation | Disposition / owner |
|---|---|---|---|
| Sol cannot complete catalogue tools | Concrete API compatibility risk; the real candidate SDK tool cycle now passes | Retain exact wire/usage/generation receipts; no silent model substitution | Preflight satisfied / root |
| Follow-up or helper behavior changes unintentionally | MAIN ENV also feeds follow-up/FAQ; other paths have independent pins | Change only DB override; assert unchanged ENV/FAST/voice/embedding and exact protected settings in both containers | Preflight / root |
| Higher cost or reply latency under real context | Sol unit prices differ; a short synthetic test is not a conversation-quality/cost benchmark | Keep existing 3200-token/90-second chat limits, medium effort, no broader job activation; preserve unknown-cost distinctions | Monitor when authorized traffic resumes / owner |
| Executor updates wrong row/release or widens WhatsApp traffic | Shared runtime has channel/guard/restore invariants | Exact SHA and policy hash, app+worker fingerprint equality, row lock and compare-and-set; retain previous row and old images | Preflight / root |

Recovery trigger: wrong effective model/policy, changed protected setting or unhealthy service. Revert only the changed main-model row to its saved JSON value; if source itself is faulty, restore the saved policy/previous app and worker images through the same safety checks. Preserve current customer data, queues, credentials and unrelated environment fields. Recovery confidence is based on exact saved artifacts and bounded config/image rollback; no destructive restore has been performed. Deployment gate is never bypassed after a failed check.

## Accepted production delivery

Canonical CI [41229254700](https://github.com/maslennikov-ig/treejar/actions/runs/41229254700) on **6df11eb29cb88bcb63c8aadb52398bcb507f2580** succeeded: lint, format, Mypy, **4858 tests passed / 27 skipped**, one real pgvector retrieval integration test, and standard deployment. The VPS helper preserved the test worker and recreated only app/worker; database, Redis and nginx retained their earlier start times. Public and host health reported the exact new release with healthy dependencies.

A bounded row-lock/compare-and-set changed exactly one setting from JSON string `openai/gpt-6-luna` to `openai/gpt-6.1-sol`. Both deployed processes' real `_LazyModelRuntime` factories then selected Sol, medium reasoning and 3200 output tokens; source policy SHA256 matched the tested candidate. ENV content is byte-identical to the saved pre-release file. FAST, voice, embedding, restore mode, channel/allowlist and disabled callback guard remained unchanged. All five containers run with zero restarts/OOM; no new logged errors were observed after release.

Final OpenRouter key readback confirms daily usage and total-usage delta **$0.001346**, exactly matching the two generation receipts; BYOK usage remains zero. Sum of both conservative predispatch reservations was $0.095410, also below the owner's $0.10 ceiling. No further model POST was made for activation/readback. The original failed observer and the initial failed CI are retained, not counted as successful acceptance.

Durable evidence: `2026-10-31-sol-provider-probe.json`, `2026-10-31-sol-provider-probe-initial.json`, `2026-10-31-sol-provider-probe-script.py.txt`, `2026-10-31-sol-runtime-readback.json`, `2026-10-31-sol-activation-script.py.txt`. Private rollback row/settings/images/environment and the activation receipt remain under `/opt/noor/.hotfix-backups/tj-3jcn-sol-20261031T181216Z`.

The customer audit callback is still in use. No business-channel expansion, pilot allocation, customer send, history replay, CRM write or helper-model change was included. The main ENV fallback remains Luna deliberately; current DB-backed main conversation selects Sol. Existing follow-up/FAQ fallback behavior therefore remains independent. The source-only documentation follow-up does not require another container rollout; live code identity remains 6df11eb.

Explicit defer: **tj-r62i** owns the customer-choice gate and coordinated Nikita/Noor pilot. Delivery-fee facts remain with existing tj-z3hw. No additional production action is queued by closing tj-3jcn.

docs-reviewed: updated - client questionnaire, developer handoff, model map and provider/runtime/recovery evidence retained.
graph-reviewed: no-change-needed - scoped reasoning policy and runtime setting only; no module or stable entrypoint change.
