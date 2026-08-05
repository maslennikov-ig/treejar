Target: Claude opus-5 orchestrator
Audience: manual launcher, fresh session, Treejar repository

Goal: Deliver stage `tj-feet` — a sales assistant that cannot assert a product fact it has no source for and cannot act against an explicit customer refusal — up to and including the re-run sealed comparison, then stop and report so the owner makes the final model decision.

Success criteria:
- `tj-feet.1` .. `tj-feet.8` closed on their own stated acceptance criteria; `tj-feet.9` closed or recorded as a measured negative result.
- Failure class (b) is eliminated, not detected: the quotation tool is absent from the offered set while consent is declined, proven by a focused regression that first fails.
- Failure class (a): a claim whose field path is absent from the retrieved row cannot reach the customer; an unknown attribute yields a useful partial answer, never a refusal.
- Failure class (c): the labelled assumption that was wrongly failed now passes and the vague unsourced claim that was wrongly passed now fails.
- The seven `tj-feet.5` metrics are reported separately with denominators in EN, AR and RU, with a baseline recorded before `.2` and `.3` land.
- Repo gates from `.codex/orchestrator.toml` pass once at stage acceptance.

Context:
Read in order: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, then
`docs/superpowers/specs/2026-08-05-sales-grounding-and-tool-obedience-spec.md`.
That specification carries the defect analysis, the exact source locations, the owner decisions of 2026-08-05, the claim taxonomy, the metric list and the rejected approaches. Do not re-derive them.
Supporting evidence, read only if a decision needs it: `docs/reports/2026-08-05-grounding-remediation-proposal.md` and `docs/Research/grounding-2026-08/` (two external research runs plus a README naming where they agree and where they disagree).
Beads holds the task truth: `bd show tj-feet` and each child. Dependencies are already wired; `bd ready` gives the correct entry points, which are `tj-feet.1`, `.2` and `.4`.
Three cross-links matter. `tj-2pkk` (GH #54, blocked since 2026-06-16 on the product owner) is the production-catalog form of the same seating-capacity ambiguity that `tj-feet.7` fixes in fixtures; `tj-feet.1` produces the evidence it has been waiting for. `tj-b93r` overlaps `tj-feet.3` — check before implementing either, do not duplicate the regression. `tj-ee5f.15` is blocked by `tj-feet.8` and is not yours.

Constraints:
- Write zone: `src/dialogue/`, `src/llm/engine.py`, `src/quality/`, `scripts/model_battle*`, their tests, and stage documents. Preserve unrelated and untracked work.
- The product system prompt must not grow. Frozen `AC-01..AC-30` and its digest stay unchanged. Public REST/webhook contracts and the database schema stay unchanged.
- Sealed rounds are superseded, never rewritten; protected evidence stays outside Git.
- No PII, provider or message identifiers, or exact captured wording in any report.
- The rejected list in the specification is binding. In particular: no lexical backstop over reply text, no per-message ensembles, no abstention fine-tuning, no knowledge graph, no whole-response blocking, and no determinizing past the point where the model stops doing the language work.
- Order is deliberate. Deterministic elimination precedes probabilistic detection; `tj-feet.9` does not start before `tj-feet.5` yields a scale.
- Ask the owner for missing product intent when two outcomes stay plausible and the answer changes acceptance or scope. Ask separately, naming the exact action, before any externally visible or hard-to-reverse step.

Output:
Per task, a behaviour-first result: what changed in customer-visible terms, the focused command that proves it, and the failing-then-passing evidence. At stage acceptance, one packet: the seven metrics against their baseline, the re-run comparison result with every critical failure read by hand against the actual model context before acceptance, as the previous round did, actual provider cost reconciled against the reservation, and what was deliberately left undone. Update `.codex/handoff.md`, the stage summary and Beads before delivery.

Stop:
- Before the paid provider calls of `tj-feet.8`. Report the estimate and wait.
- After `tj-feet.8` reports its winner. The final model decision is the owner's; `tj-ee5f.15` and `tj-ee5f.1` are separate authority gates and are not part of this stage.
- Before any push, deploy, production readback, production mutation, Zoho/PDF/Wazzup effect, live message, or secrets/access change.
- If `tj-feet.1` shows catalog attribute completeness low enough that `tj-feet.3` would mostly produce "not specified": report the number and ask before building on it.
