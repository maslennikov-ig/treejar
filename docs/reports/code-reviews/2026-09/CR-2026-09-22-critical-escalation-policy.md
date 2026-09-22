# Code Review: Critical-only escalation policy

**Date**: 2026-09-22
**Scope**: Local branch changes for `tj-bltw`
**Files**: 10 | **Changes**: +877 / -211

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 0    | 0      | 0   |
| Improvements | —        | 0    | 0      | 0   |

**Verdict**: PASS

The final diff consistently gates both tool exposure and tool execution through
one deterministic critical-case policy. Noncritical repair and catalog failures
remain observable without pausing the customer conversation. During review,
negated human and quotation requests plus English and Arabic product-manager
phrases were added to the regression matrix before acceptance.

## Issues

No open issues found.

## Improvements

No required improvements found within this change.

## Positive Patterns

- `src/llm/escalation_policy.py` centralizes the allowlist and returns a typed,
  canonical decision rather than trusting the model-provided reason or type.
- `src/llm/engine.py` applies defense in depth: noncritical turns do not receive
  the escalation tool, and direct tool calls are checked again.
- `src/llm/message_processor.py` keeps failed reply repair autonomous by default,
  while preserving existing active handoffs and genuinely critical turns.
- Regression coverage includes explicit human requests, accepted quotations,
  incidents, negations, product-title false positives, missing catalog evidence,
  the Nadia/no-chairs path, and pre-generation name capture.

## Escalation

The shared conversation runtime policy changes, but there is no schema,
migration, public API, dependency, deployment, or production-state change.

## Validation

- Diff whitespace: PASS (`git diff --check`)
- Lint: PASS (`uv run ruff check src/ tests/`)
- Format: PASS (`uv run ruff format --check src/ tests/`)
- Type check: PASS (`uv run mypy src/`, 181 source files)
- Focused acceptance: PASS (781 tests)
