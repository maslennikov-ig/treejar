# Primary model switch to GPT-6 Luna

Task: tj-qr32. Owner requested openai/gpt-6-luna, reasoning medium.
Status: deployed and read back on app and worker, 2026-09-23 11:10 UTC.
Code release: 6ae4c0ea4e61fe8bab77a0b9db59f015c4bf1d70.
Source branch: codex/gpt6-luna-main (pushed).

## Scope and evidence

- Primary DB setting and environment fallback now select openai/gpt-6-luna.
- Core chat/followup explicitly send reasoning.effort=medium. Auxiliary model
  remains deepseek/deepseek-v4-flash; legacy GLM low policy remains for rollback.
- The running previous release was 1dd3b05. Remote main af15d72 differed only
  in documentation; both changed source files matched before deployment.
- Minimal source overlays on each existing image preserve all dependencies
  and prior runtime changes. App and worker only were recreated.
- Independent fresh DB reads in both containers return the requested model;
  actual core settings resolve to medium. Both source hashes match the commit.
- Health returns the exact code release, healthy DB and Redis. Both containers
  are running with zero restarts. Worker starts only process_incoming_batch;
  test-channel restore mode, disabled cron and embedding warmup remain intact.
- Environment comparison proves only OPENROUTER_MODEL_MAIN changed. Sender
  configuration remains equal to its allowlist; test0665 boundary is unchanged.

## Acceptance and limits

43 focused safety tests passed; Ruff check/format and Mypy on both changed
source files passed. Initial shared-venv pytest import mismatch was resolved by
creating an isolated worktree environment. No full suite was required.

Official OpenAI model documentation lists medium support and an endpoint-specific
function-calling restriction. OpenRouter model/endpoints metadata lists both
reasoning and tools. One isolated compatibility request through the existing
OpenRouter account, with medium and require_parameters, returned the expected
record_name tool call in 1.54 seconds. No tool was executed and no customer
message was sent. Provider-reported cost: USD 0.0000155. This single probe was
performed as switch compatibility validation; no further paid probes were run.
Reasoning usage was zero on this trivial probe, so it establishes request/tool
compatibility, not the depth of reasoning or real customer-answer quality.

No WhatsApp end-to-end conversation was generated. Fresh tester-authored traffic
is still needed to assess customer-answer quality and latency on the real prompt.
The apostrophe extraction/error-opening defect remains separately tracked as
tj-pmbv; changing the model does not repair that code.

## Recovery

Backup: /opt/noor/.hotfix-backups/tj-qr32-20260923 (private directory).
- env-before: previous environment, secrets retained only on server.
- source-before.tar.gz: previous two source files and release marker.
- Images: noor-rollback:tj-qr32-app and noor-rollback:tj-qr32-worker.
- Previous DB openrouter_model_main: z-ai/glm-5.3-flash.

Rollback must restore only this DB key with an expected-current-value check,
the two source files/release marker and the main-model env line; preserve any
subsequent unrelated environment changes. Retag rollback images as noor-app and
noor-worker, then recreate only app/worker with --no-build --no-deps. Recheck
health and test-worker restrictions. Never restore conversation/customer data.

## Integration defer

Task tj-3nvu tracks integration into main before any standard deployment.
The repo contract requires explicit merge authority; current work was requested
as a live model switch. Source and deployment receipt are pushed on the dedicated
branch. A main-based deployment before integration would lose the explicit medium
code setting (the provider currently defaults to medium, but this is not a pin).

## Authorized integration and regression repair

Owner subsequently authorized Push, Merge, Deploy and several post-deploy tests.
Initial main CI found a stale expected default and mutable handoff digest; those
were corrected without changing frozen evidence. The original Nadia case also
requires tj-pmbv: accept typographic apostrophes and suppress additive questions
on generation-error replies. Five focused regressions cover all three apostrophe
forms and failed generation with known/unknown names. Final release verification
and bounded live model cases are pending.
