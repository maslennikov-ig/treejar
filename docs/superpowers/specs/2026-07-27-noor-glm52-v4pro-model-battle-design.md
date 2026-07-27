# Noor GLM 5.2 / DeepSeek V4 Pro Model Battle Design

**Date:** 2026-07-27
**Beads:** `tj-5e3k`
**Runtime:** OpenRouter; production configuration unchanged

## Goal

Extend the accepted Noor benchmark with the newly available
`z-ai/glm-5.2` and `deepseek/deepseek-v4-pro`, then select the strongest
candidate independently for:

1. core sales chat;
2. fast structured and helper work.

The new round reruns every baseline in the same provider window. Previous
results remain historical evidence, not latency baselines for this decision.

## Candidate Matrix

Core sales:

- `z-ai/glm-5` — current sales baseline;
- `z-ai/glm-5.2`;
- `deepseek/deepseek-v4-flash`;
- `deepseek/deepseek-v4-pro`.

Fast/system:

- `nex-agi/nex-n2-mini` — prior fast baseline;
- `z-ai/glm-5.2`;
- `deepseek/deepseek-v4-flash`;
- `deepseek/deepseek-v4-pro`.

The sales route uses provider-default reasoning consistently. The fast/system
route requests disabled reasoning consistently because Noor needs compact
structured responses and this was the accepted profile in the prior round.
Observed reasoning tokens are recorded separately so provider/model
noncompliance is visible rather than assumed away.

## Test Contract

- Reuse the accepted 12 sales and 24 system cases without changing their
  evidence, expected outcomes, rubrics, or hard gates.
- Run every case twice for every candidate.
- Shuffle candidate order deterministically and execute calls sequentially.
- Require OpenRouter endpoints that support every requested parameter.
- Preserve raw responses, timings, retry history, schema and semantic results,
  blind labels, and scoring inputs.
- Score sales responses anonymously before reading the reveal key, with each
  candidate occupying A/B/C/D exactly six times.
- Rank candidates even if none passes every release gate, but label a route
  winner as safe only when its hard correctness gates pass.

The full round contains 96 sales calls and 192 system calls.

## Decision Rules

Sales keeps the accepted weighting: hard correctness 45%, blinded sales
quality 25%, tool/route efficiency 15%, and latency 15%.

Fast/system keeps the accepted weighting: JSON/schema and semantic correctness
50%, reliability 20%, tool/system quality 15%, and latency 15%.

Hard gates and tie handling remain unchanged so the extension is directly
comparable with the accepted benchmark. The durable report must distinguish:

- strict safe winner;
- comparative leader when all candidates miss a release gate;
- practical tie;
- route-specific operational caveats.

## Safety and Non-goals

- No customer transcripts, identifiers, messages, or live traffic.
- No production route/configuration change.
- No Zoho, Wazzup, database, deployment, or other business-system mutation.
- No claim that a synthetic benchmark alone authorizes deployment.
- Provider availability and required parameters are verified before paid
  inference calls.
