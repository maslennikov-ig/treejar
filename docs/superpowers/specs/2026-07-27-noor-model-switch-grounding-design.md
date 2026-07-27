# Noor Model Switch and Grounding Design

**Date:** 2026-07-27  
**Owner:** `tj-j13d`  
**Status:** approved direction; implementation pending

## Goal

Switch Noor's core sales model from `z-ai/glm-5` to `z-ai/glm-5.2` and every
default fast/helper route from `xiaomi/mimo-v2-flash` to
`deepseek/deepseek-v4-flash`. At the same boundary, replace open-ended
anti-hallucination wording with one evidence-grounding contract and an
explicit registry of authorized commercial capabilities.

## Corrected Evaluation Context

The model-battle harness did not include Treejar's full FAQ capability
evidence. Repository truth confirms that customers may visit the UAE showroom
and that samples may be arranged depending on project requirements. Therefore
showroom and conditional-sample suggestions are not automatically production
hallucinations.

The durable safety defects that remain relevant are:

- claiming stock or a ready alternative without an inventory result;
- deriving health, certification, warranty, delivery, payment, discount, or
  other commercial facts without an explicit source;
- presenting conditional or manager-controlled capabilities as guaranteed.

The model switch is an explicit product decision. It is not presented as a
claim that GLM-5.2 passed every prior synthetic hard gate.

## Grounding Contract

Noor may make a customer-visible factual claim only when it is supported by at
least one source available in the current run:

1. tool output;
2. injected FAQ or knowledge-base evidence;
3. verified CRM, quotation, order, or conversation state;
4. an approved capability entry in the runtime policy.

Noor may offer a next step only when the capability registry authorizes that
action. Missing evidence is not negative evidence: Noor should say that the
detail is unconfirmed, ask one useful clarification, invoke the appropriate
tool, or use the existing manager handoff. It must not fill the gap with a
plausible industry assumption.

This is an allowlist rule over sources and actions, not an attempt to enumerate
every sentence a model could invent.

## Capability Registry

The compact runtime policy will distinguish four authorization modes:

- `direct`: safe to state or offer from approved company facts, such as the
  UAE showroom location;
- `conditional`: may be offered with its condition preserved, such as samples
  depending on project requirements;
- `tool_required`: stock, operational price, quotation, and order status must
  come from their existing tools;
- `manager_required`: discounts, exceptional terms, and any unsupported
  commitment use the existing manager path.

Product benefits remain evidence-bound. Medical or certification claims are
not inferred from ordinary product features.

The registry will live with the existing communication/verified-answer policy
rather than create a second policy subsystem. The generated prompt block is
included in every core sales run, including stage-specific prompts loaded from
the database.

## Runtime Flow and Fallback

1. `build_system_prompt()` injects the immutable grounding contract after the
   database-provided base prompt so a stale editable prompt cannot remove it.
2. Existing deterministic routes and tools remain authoritative for stock,
   price, quotations, order status, showroom location, and manager handoff.
3. When evidence is missing, the model uses the shared safe fallback:
   distinguish unknown from unavailable, avoid a commitment, and select a
   verified tool, clarification, or handoff.
4. Tool execution remains the only way to mutate operational state. The model
   switch does not grant new tools or permissions.

The first implementation will not add a second model call to judge every
answer; that would add latency and another probabilistic failure point.
Focused deterministic guards remain appropriate for exact high-risk routes.

## Model Configuration

- `OPENROUTER_MODEL_MAIN=z-ai/glm-5.2`
- `OPENROUTER_MODEL_FAST=deepseek/deepseek-v4-flash`
- DeepSeek V4 Flash requests reasoning disabled where the provider path
  supports the parameter.
- Repository defaults, `.env.example`, configuration tests, and the protected
  production `.env` must agree after deployment.

Existing explicit admin overrides remain valid and are not silently rewritten.

## Verification

Implementation uses TDD for:

- default main and fast model identities;
- routing core paths to GLM-5.2 and helper/background paths to V4 Flash;
- reasoning-disable provider settings for V4 Flash without affecting other
  providers;
- immutable inclusion of the grounding contract;
- capability modes for showroom, conditional samples, tool-required stock, and
  manager-required commitments;
- safe unknown/unconfirmed fallback wording;
- preservation of database prompt customization and existing tools.

Before deployment:

- focused LLM/configuration tests;
- affected integration tests;
- full repository release gates;
- one combined correctness and improvement review;
- provider capability preflight and bounded synthetic model smoke checks.

After authorized deployment:

- read back the release and the two model variables without exposing secrets;
- rebuild/restart the application through the canonical deployment path;
- verify app, worker, Redis, PostgreSQL, and public health;
- run bounded synthetic FAQ, product-grounding, missing-stock, structured JSON,
  and fallback checks without customer data or outbound WhatsApp messages;
- stop and roll back if health, structured output, grounding, or provider
  reliability fails.

## Deployment and Rollback

Deployment is explicitly authorized for this task. The protected production
`.env` is backed up before changing exactly the two model variables. The
release archive preserves credentials and unrelated operational state.

Rollback restores both the previous release and the two prior model variables,
then repeats health and bounded smoke verification.

No real customer conversation, quotation, Zoho mutation, or outbound
WhatsApp message is part of this acceptance boundary.

## Acceptance Criteria

- Core sales defaults to GLM-5.2.
- Fast/helper routes default to DeepSeek V4 Flash with reasoning disabled
  where supported.
- One immutable grounding contract and one capability registry govern
  customer-visible claims and proposed actions.
- Showroom and conditional samples remain allowed according to the FAQ.
- Stock, price, quote, order, and exceptional commitments retain their
  tool/manager gates.
- Local release gates and bounded provider checks pass.
- Production deploy, model readback, health, and synthetic post-deploy checks
  pass without customer-facing side effects.
- Rollback evidence and the previous model values are preserved.
