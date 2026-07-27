# Noor Extended Model Battle

**Date:** 2026-07-27  
**Stage:** `tj-5e3k`  
**Runtime:** OpenRouter  
**Production changed:** no

## Decision

- Core sales: keep `z-ai/glm-5`. It is the only candidate that passed every
  sales hard gate in this round and it also led the weighted score.
- Fast/system: use `deepseek/deepseek-v4-pro` as the practical hardening
  target, with reasoning disabled, strict schema validation, and bounded
  fallback. No system candidate passed the accepted semantic release gate, so
  this is not an unguarded production-switch recommendation.
- Do not select `z-ai/glm-5.2` for either route or DeepSeek V4 Pro for sales
  from this evidence.

## Method

The extended profile reran all baselines in one provider window:

- 12 fixed synthetic sales cases × 2 repetitions × 4 candidates = 96 runs;
- 24 fixed synthetic system cases × 2 repetitions × 4 candidates = 192 runs.

Calls were shuffled deterministically and executed sequentially. Sales used
provider-default reasoning. System calls requested disabled reasoning and
required support for tools, tool choice, response format, reasoning, and
structured outputs. All model IDs and required parameters were present in the
live OpenRouter catalog before inference. The disable request was honored by
GLM-5.2 and both DeepSeek candidates; Nex-N2-Mini returned reasoning tokens in
all 48 runs, which is recorded as control noncompliance.

The sales answers were scored as anonymous A/B/C/D responses before the reveal
key was read. Each candidate occupied each label exactly six times. A fresh
reviewer covered all 24 case/repetition groups and all 96 answers. System
results used deterministic JSON parsing, JSON Schema validation, semantic
golden fields, tool arguments, reliability, and latency.

## Core Sales Results

| Candidate | Weighted | Blind quality | Objective | p50 | p95 | Hard gates |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `z-ai/glm-5` | **93.975** | **93.50%** | 90.22% | 7.959s | **10.710s** | **pass** |
| `deepseek/deepseek-v4-pro` | 90.276 | 86.33% | **90.72%** | 9.189s | 12.484s | fail |
| `z-ai/glm-5.2` | 88.539 | 90.83% | 87.66% | **4.978s** | 14.114s | fail |
| `deepseek/deepseek-v4-flash` | 86.265 | 90.00% | 90.57% | 9.042s | 20.061s | fail |

All candidates had 100% first-pass provider reliability and correct tool
routes/arguments. The hard-gate difference came from factual and commercial
grounding:

- GLM-5 had no deterministic or blind critical failure.
- GLM-5.2 correctly described null stock as unconfirmed. Its one blind
  critical finding was an unsupported showroom-trial claim.
- DeepSeek V4 Pro had four blind critical findings: an unsupported product
  health benefit, showroom trials/viewings, and fabric samples.
- DeepSeek V4 Flash had one blind critical finding: it claimed an alternative
  product was in stock without inventory evidence.

GLM-5.2 produced the best median but an unstable tail, and its grounding
failure blocks the route. DeepSeek V4 Pro was faster at p95 than Flash but less
trustworthy in the blinded review. GLM-5 is both the strict and practical
sales winner.

## Fast/System Results

| Candidate | Weighted | JSON/schema | Semantic | Tools | Reliability | p50 | p95 | Hard gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `deepseek/deepseek-v4-pro` | **85.353** | **100%** | 72.82% | **100%** | **100%** | 2.776s | 12.168s | fail |
| `deepseek/deepseek-v4-flash` | 84.133 | **100%** | **73.79%** | **100%** | **100%** | 2.764s | 15.298s | fail |
| `nex-agi/nex-n2-mini` | 80.603 | 70% | 64.08% | **100%** | 85.42% | 2.644s | **5.799s** | fail |
| `z-ai/glm-5.2` | 78.786 | **100%** | 65.53% | **100%** | **100%** | **2.379s** | 36.206s | fail |

No candidate reached the accepted 95% semantic gate.

- DeepSeek V4 Pro is the strongest overall practical candidate: perfect
  first-pass JSON/schema, reliability, reasoning-control compliance, and tool
  arguments. Its semantic accuracy trails Flash by 0.97 percentage points,
  while its p95 is 20.5% faster. It consistently failed `system-red-03`.
- DeepSeek V4 Flash has the best semantic accuracy and the same perfect
  JSON/schema, reliability, control compliance, and tool results. It is the
  quality runner-up and consistently failed `system-red-01`, with a slower
  p95.
- Nex-N2-Mini was fastest at p95, but seven of 48 first attempts returned
  provider 502 errors and required retries. It returned reasoning tokens in
  all 48 runs despite the disable request, produced only 70% first-pass
  JSON/schema success, and consistently failed three cases.
- GLM-5.2 had perfect JSON/schema, reliability, and tool arguments, but weak
  fact extraction (35% semantic accuracy) and severe tail instability:
  36.206s p95 and a 93.783s maximum.

Category-level semantic accuracy reinforces the practical choice:

| Category | V4 Flash | V4 Pro | Nex N2 Mini | GLM 5.2 |
| --- | ---: | ---: | ---: | ---: |
| Fact extraction | **58.33%** | 55.00% | 46.67% | 35.00% |
| Red flags | 40.00% | **60.00%** | 10.00% | 55.00% |
| FAQ candidate | **65.38%** | 61.54% | 57.69% | 61.54% |
| Summary | **85.00%** | 80.00% | 72.50% | 70.00% |
| Translation | 94.44% | 91.67% | 94.44% | **97.22%** |
| Tool arguments | **100%** | **100%** | **100%** | **100%** |

## Operational Recommendation

1. Keep GLM-5 as the Noor sales model.
2. Continue the fast/system hardening task with DeepSeek V4 Pro as the primary
   candidate and V4 Flash as the semantic reference.
   Preserve reasoning-disabled requests, endpoint parameter enforcement,
   strict schema validation, and fallback.
3. Harden the system prompt/contracts for fact extraction, red flags, FAQ
   candidates, and summaries, then rerun the same 24-case suite. Adoption
   requires at least 97.5% first-pass JSON/schema, 95% semantic accuracy, no
   consistently failing case, and no critical tool-argument error.
4. Keep `tj-b93r`: GLM-5 passed this round, but the earlier accepted run found
   a weak-catalog grounding defect. A stochastic pass does not invalidate that
   regression evidence.
5. Do not advance GLM-5.2, and do not use DeepSeek V4 Pro for sales.

## Limitations

- This is a synthetic contract benchmark, not live customer traffic.
- Two repetitions expose repeat failures but do not estimate rare production
  tails precisely.
- Provider routing and model implementations can change after the recorded
  window.
- Exact semantic fields intentionally penalize extra, missing, or inferred
  facts; the 95% release gate represents Noor's structured-work contract, not
  general conversational intelligence.
- Weighted scores compare candidates inside this accepted profile. Hard gates
  take precedence over the numeric ranking.
- Cost was not used as a decision criterion.

## Evidence

- Raw and derived artifacts:
  `.codex/stages/tj-5e3k/results/`.
- Harness: `scripts/model_battle.py`.
- Fixed cases: `scripts/model_battle_cases.py`.
- Focused tests: `tests/test_scripts_model_battle.py`.
- Previous accepted baseline report:
  `docs/reports/model-battle-2026-07-27.md`.
