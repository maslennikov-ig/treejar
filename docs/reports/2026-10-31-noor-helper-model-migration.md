# Noor helper/checker model migration — 31 October 2026

Task: `tj-199k`. Owner requests Luna for service processes, Terra for answer
checks and quality evaluation, with voice/search and disabled processes preserved.
Primary Sol delivery `tj-3jcn` remains accepted; pilot launch is separate `tj-r62i`.
This report will distinguish prepared source from accepted runtime delivery.

## Selected routes

| Workload | Selected model | Configuration |
|---|---|---|
| DB-backed main chat | `openai/gpt-6.1-sol` | Existing DB override retained |
| Summary, fact extraction, manager response adapter, AutoFAQ | `openai/gpt-6-luna` | FAST default and live ENV |
| Follow-up and AutoFAQ fallback | `openai/gpt-6-luna` | Existing MAIN ENV retained |
| Flagged-answer repair/check | `openai/gpt-6.1-terra` | Explicit checker constant, independent of FAST |
| Bot QA, red flags, manager QA | `openai/gpt-6.1-terra` | Checker route defaults plus exact existing DB model fields |
| Voice | `openai/gpt-4o-mini-transcribe` | Unchanged dedicated audio endpoint |
| Search embeddings | Local `BAAI/bge-m3`, 1024 dimensions | Unchanged |

Explicit caller/admin overrides remain authoritative. Source defaults do not
silently overwrite existing DB controls. Only the three requested stored model
fields are changed operationally; their modes, budgets, criteria and all other
keys must compare equal. Disabled processes are not executed to test them.

## Compatibility and local proof

Official [OpenAI migration guidance](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-update-api-and-model-parameters)
confirms `none` reasoning support for Luna/Terra. The normalized OpenRouter
chat gateway is the existing transport; no SDK/endpoint migration is included.
Current [Luna endpoint metadata](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints)
and [Terra endpoint metadata](https://openrouter.ai/api/v1/models/openai/gpt-6.1-terra/endpoints)
advertise tools and structured outputs; neither advertises temperature.

Bounded non-core Luna/Terra paths explicitly request `reasoning.effort=none`
and omit unsupported temperature, including after runtime settings merging.
This preserves output budgets/timeouts and avoids spending a short JSON budget
on reasoning. Existing core Luna/Sol reasoning policies remain unchanged.
Temperature-zero policy remains available for other supported models; no claim
of identical sampling variance or improved semantic quality is made for Terra.
The repair prompt now says independent model, as Sol and Terra share a vendor.

Focused acceptance: **216 passed**, including actual PydanticAI/OpenRouter SDK
serialization and output validation with `httpx.MockTransport` for Luna fact
extraction, Terra repair and Terra red flags. Existing main Sol tool-cycle,
voice configuration, full/manager QA, override and disabled-control tests pass.
Ruff, format and Mypy (198 source files) pass. Provider metadata GETs are free;
**no paid inference POST** or customer message is made in this task. Previous
Sol's USD0.10 probe authority is not reused for other models. Local SDK proof
does not establish gateway behavior, production latency or conversation quality.

## Technical premortem and recovery

Verdict: GO WITH CONDITIONS — canonical CI, private rollback and exact runtime
readback must pass before this migration is accepted.
Blast radius: FAST -> import-time helper agents; checker routing -> repair/QA;
live ENV -> app/worker recreation; QA DB JSON -> future disabled evaluations.

| Symptom | Evidence / mechanism | Detection and mitigation | Disposition / owner |
|---|---|---|---|
| Helpers changed but QA still uses DeepSeek | Confirmed DB model overrides | Exact row lock/CAS of only 3 model fields, compare every other JSON key | Preflight / root |
| Structured output missing or request rejected | New model, bounded JSON output, different supported parameters | Metadata and real SDK mocked payload proof; none reasoning, unchanged limits/retries; retain fallback | Preflight, then monitor actual authorized traffic / root |
| Unexpected cost or score variance | New vendor/model price and sampling; no live benchmark | Retain all budgets/attempts, disabled modes and provider-cost telemetry; no quality improvement claim | Monitor when used / owner |
| Wrong channel/disabled flag changes during rollout | Shared runtime, partial ENV/source/DB rollout | Compare full effective settings except FAST, full configs except exact QA model edits, worker registrations and app/worker equality | Preflight / root |
| Executor applies stale source or overwrites concurrent config | Nonatomic deployment/config steps | Exact release SHA, fresh base, compare-and-set, stop on mismatch; private old ENV/source/images/configs | Preflight / root |

Order: save current private state and images; source release through canonical
CI at unchanged ENV; verify release; replace only FAST ENV value and recreate
app/worker with preserved test-worker boundaries; CAS only the existing QA JSON
model fields; verify all effective settings and unchanged disabled gates.

Recovery trigger: failed health, wrong effective model, unexpected settings or
registration difference. Restore only the requested QA model fields using CAS
against the written value; restore saved ENV and previous app/worker images and
source with the same test-worker safety checks. Primary Sol stays selected.
Do not restore the database, replay messages, flush queues or change channels.
Exact previous values/images are retained privately; recovery is bounded to
this task, with no destructive recovery drill or promised duration.

## Delivery evidence

Private baseline saved at `/opt/noor/.hotfix-backups/tj-199k-helpers-20261031T190556Z`.
Previous source, ENV, compose, full settings/configs and tagged app/worker images
are retained. Redacted receipt: `2026-10-31-helper-model-preflight.json`.
Metadata receipt: `2026-10-31-helper-model-metadata.json`.
Pending canonical CI and live readback; local preparation alone is not delivery.

Initial CI `41232676259` on `df9ffe3` stopped delivery: 4861 passed / 27 skipped,
one test failed because it assumed FAST always differs from MAIN ENV fallback.
Both requested helper/default routes can now be Luna. The test now explicitly
sets main Sol and proves fact extraction still uses FAST; no runtime fix or
test gate suppression is required. The failed CI remains in the audit trail.

docs-reviewed: updated - route map, limitations, runtime acceptance and rollback.
graph-reviewed: no-change-needed - existing model routing and controls only.
