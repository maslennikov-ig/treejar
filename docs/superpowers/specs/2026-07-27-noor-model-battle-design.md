# Noor Model Battle Design

**Date:** 2026-07-27
**Beads:** `tj-0j7o`
**Runtime:** OpenRouter, production configuration unchanged

## Goal

Select the best model independently for two Noor routes:

1. core sales chat: `z-ai/glm-5` versus
   `deepseek/deepseek-v4-flash`;
2. fast/background work: `nex-agi/nex-n2-mini` versus
   `deepseek/deepseek-v4-flash`.

The decision must combine correctness, route/tool behavior, task quality,
reliability, and latency. A faster model cannot win after a critical factual,
commercial, schema, or tool-argument failure.

## Non-goals

- No production model or routing change.
- No customer traffic, WhatsApp sends, Zoho mutations, or database writes.
- No use of real customer transcripts or identifiers.
- No comparison with the removed `xiaomi/mimo-v2-flash`.
- No cost optimization decision; provider-reported usage may be retained only
  as diagnostic evidence.

## Common Test Contract

- All prompts and evidence are synthetic and fixed in the repository.
- Candidate order is deterministically shuffled.
- Each case runs twice.
- Calls are sequential so candidates do not contend for the same client,
  connection, or rate limit during latency measurement.
- Both candidates in a route receive equivalent model settings and the same
  prompt, tools, evidence, output limit, and retry contract.
- Raw responses, timings, validation results, and blinded labels are preserved
  in stage evidence.
- OpenRouter endpoint selection requires support for every sent parameter, so
  strict schema/tool behavior cannot be silently dropped by provider routing.
- Transient provider failures are recorded. One bounded retry may measure
  recoverability, but first-pass reliability remains a separate metric.

## Battle A: Core Sales Chat

Twelve cases cover:

- ordinary FAQ/process guidance;
- product recommendation from fixed catalog evidence;
- two-product comparison;
- exact current stock;
- order intent without quotation creation;
- explicit manager/discount escalation;
- Arabic response quality;
- weak catalog match and truthful clarification;
- one/two-option cap;
- catalog price versus operational Zoho rate;
- missing stock or catalog mismatch;
- concise next-step follow-up.

Some cases expose simulated tools with fixed responses. The harness measures:

- correct tool selection and arguments;
- number of tool rounds;
- final response latency;
- factual and commercial constraints;
- language and requested option count;
- quotation/escalation boundaries;
- clarity, persuasion, trust, concision, and quality of the next step.

Hard sales gates:

- zero invented price, stock, discount, delivery, or payment claims;
- zero incorrect quote/order/escalation action;
- correct language in every language-constrained case;
- all critical tool arguments grounded in the case evidence.

After deterministic scoring, outputs are presented under blinded labels for a
pairwise qualitative review. Model identity is revealed only after the review
is recorded. Five dimensions are scored from 1 to 5: clarity, factual trust,
persuasion, concision, and next-step quality.

## Battle B: Fast/System Work

Twenty-four cases represent current Noor helper workloads:

- customer-fact extraction;
- quality/red-flag classification;
- FAQ candidate extraction;
- conversation summary;
- manager-response adaptation;
- English/Arabic translation;
- tool/function selection and arguments.

Structured cases use an explicit JSON Schema through OpenRouter
`response_format`. The harness records:

- response success and latency;
- first-pass JSON parse success;
- JSON Schema validation;
- semantic field accuracy against golden values;
- enum, null, quantity, language, and duplicate handling;
- tool name and argument correctness;
- retry requirement and recovered result;
- unsupported parameter or provider failure.

Hard system gates:

- no consistently failing case;
- no critical tool-argument error;
- at least `97.5%` first-pass JSON/schema success;
- at least `95%` semantic accuracy across scored fields.

Correctness and reliability decide first; latency breaks a quality-equivalent
result.

## Scoring and Winner Selection

Core sales score:

- hard correctness: 45%;
- blinded sales quality: 25%;
- tool/route efficiency: 15%;
- latency: 15%.

Fast/system score:

- JSON/schema and semantic correctness: 50%;
- reliability/retry behavior: 20%;
- tool/system task quality: 15%;
- latency: 15%.

A route winner is selected only if its hard gates pass. If both pass, the
weighted score decides; a difference below two percentage points is reported
as a practical tie unless one candidate has a material p95 or reliability
advantage. If neither passes, the result is “no safe replacement”.

## Evidence and Safety

The durable report includes case-level aggregate scores, p50/p95/max, failure
classes, blinded review, winner rationale, and limitations. Raw evidence
contains no keys, credentials, PII, or production identifiers.

The benchmark authorizes bounded paid inference calls only. Any production
model switch remains a separate release decision requiring explicit approval.
