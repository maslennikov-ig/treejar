# Noor model battle: GLM-5, DeepSeek V4 Flash, Nex-N2-Mini

Date: 2026-07-27
Stage: `tj-0j7o`
Provider: OpenRouter
Production routing changed: no

## Executive decision

1. Keep `z-ai/glm-5` for the core sales route.
2. Use `deepseek/deepseek-v4-flash` as the preferred replacement candidate for
   the unavailable fast model, with reasoning disabled and with structured
   validation/fallback guards.
3. Do not select `nex-agi/nex-n2-mini` as the default structured-output model.
   Its speed advantage does not compensate for its JSON/schema failure rate.

The strict release gate returned `no_safe_replacement` in both battles. This
does not mean that the candidates were equivalent:

- sales: GLM-5 clearly led on latency with equivalent objective and blinded
  quality, but each candidate produced one blind-review critical failure;
- fast/system: DeepSeek alone met the 97.5% JSON/schema threshold, while both
  candidates missed the 95% semantic threshold.

The recommendations above are therefore comparative product choices, not
authorization for an unguarded production switch.

## Test contract

- 12 synthetic sales cases, two repetitions, two candidates: 48 runs.
- 24 synthetic system cases, two repetitions, two candidates: 96 runs.
- Candidate order was deterministically shuffled; requests ran sequentially.
- No customer data, production traffic, Wazzup calls, Zoho calls, or database
  writes were used.
- OpenRouter routing required endpoints supporting every sent parameter.
- First-pass reliability, retries, raw responses, tool calls, and latency were
  preserved.
- Sales quality was reviewed under A/B labels before the model key was opened.
- Fast/system candidates ran with `reasoning.enabled=false`, matching the
  intended low-latency structured helper role.

An initial diagnostic system run with provider-default reasoning is preserved
under `initial_system_default_reasoning/`. It showed that hidden reasoning
could consume the output budget and produce blank or truncated JSON, especially
on Nex. It is not used for the final comparison.

## Battle A: core sales

| Metric | GLM-5 | DeepSeek V4 Flash |
|---|---:|---:|
| Weighted score | **92.879** | 85.395 |
| Objective correctness | **88.99%** | 88.83% |
| Blinded quality | **91.33%** | 91.00% |
| Tool/route score | 100% | 100% |
| First-pass reliability | 100% | 100% |
| p50 latency | **7.326 s** | 9.491 s |
| p95 latency | **11.229 s** | 21.962 s |
| Maximum latency | **19.675 s** | 35.935 s |

Blind critical findings:

- GLM-5, `sales-08` repetition 2: after an empty catalog result, it suggested
  unsupported pod sizes that Treejar “may carry”.
- DeepSeek, `sales-03` repetition 1: it offered a showroom visit or virtual
  walkthrough not supported by the scenario.

Strict outcome: `no_safe_replacement`, because both candidates had one
blind-review critical failure.

Comparative decision: **GLM-5 wins the sales route.** Quality was effectively
tied, while GLM-5 had about half the p95 latency and a lower maximum. DeepSeek
did not provide a quality gain that would justify replacing the current model.

Required guard before calling the sales route fully battle-clean:

- when catalog evidence is empty or incomplete, constrain the final response
  to clarification and manager/catalog follow-up without suggesting unverified
  sizes, services, or availability.

## Battle B: fast/system work

| Metric | DeepSeek V4 Flash | Nex-N2-Mini |
|---|---:|---:|
| Weighted score | 82.962 | **84.144** |
| First-pass JSON/schema | **97.5% (39/40)** | 72.5% (29/40) |
| Semantic field accuracy | **71.84%** | 64.08% |
| Tool argument pass rate | 100% | 100% |
| First-pass provider reliability | 100% | 100% |
| p50 latency | 3.966 s | **2.409 s** |
| p95 latency | 14.804 s | **5.553 s** |
| Maximum latency | 18.997 s | **7.606 s** |
| Consistently failing cases | 1 | 3 |

The weighted total favors Nex by 1.182 points because of latency. That number
cannot be used as a release decision: Nex failed the explicit structured-output
hard gate by 25 percentage points and returned 11 invalid/empty/truncated JSON
responses out of 40 structured runs.

DeepSeek returned one invalid structured response and met the 97.5% schema
gate exactly. It also had higher semantic field accuracy and fewer consistently
failing cases. Its main weaknesses were:

- red-flag classification;
- canonical fact keys/scopes;
- FAQ response-versus-question separation;
- sales-stage classification.

Strict outcome: `no_safe_replacement`, because neither candidate reached 95%
semantic accuracy and both had at least one consistently failing case.

Comparative decision: **DeepSeek V4 Flash is the preferred fast/system
candidate.** JSON correctness is a prerequisite for this route, so Nex's speed
advantage cannot override its schema failures. DeepSeek should not be enabled
as an unguarded global fast model until the task prompts and downstream
validation cover the observed semantic failures.

## Recommended implementation boundary

For the next engineering stage:

1. Keep the main sales configuration on `z-ai/glm-5`.
2. Replace the stale Xiaomi default in code/config with
   `deepseek/deepseek-v4-flash`, but keep deployment as a separate approval.
3. Configure fast structured calls with reasoning disabled and require provider
   support for all request parameters.
4. Add focused contract tests for the failing fact, red-flag, FAQ, and summary
   cases.
5. Preserve Pydantic/schema validation and use a bounded fallback for invalid
   or semantically rejected results.
6. Re-run the 24-case system suite after prompt/validator fixes. The release
   target remains at least 97.5% JSON/schema and 95% semantic accuracy.

## Limitations

- Synthetic evidence cannot reproduce the complete distribution of live
  customer conversations.
- Two repetitions are enough to expose large failures, not to estimate rare
  provider incidents precisely.
- Latency reflects the OpenRouter/provider snapshot on 2026-07-27.
- The benchmark intentionally did not optimize or compare cost.
- The semantic score enforces canonical downstream contracts; natural-language
  fields allow bounded paraphrases, while keys, enums, nulls, quantities, and
  route actions remain strict.

## Evidence

Durable raw and derived evidence is stored in
`.codex/stages/tj-0j7o/results/`:

- `sales_results.jsonl`, `sales_scored_results.jsonl`;
- `system_results.jsonl`;
- `sales_blind_review.json`, `sales_blind_scores.json`,
  `sales_blind_key.json`;
- `sales_scored_aggregate.json`, `system_aggregate.json`;
- `route_decisions.json`, `model_catalog.json`, `run_manifest.json`;
- `initial_system_default_reasoning/`.
