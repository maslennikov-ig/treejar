# October 13 tester feedback corrections

Parent task: `tj-i2b1`. Local candidate on `codex/tester-feedback-20261013`.
Base: `32c95f6`; final code: `9570c1d`.
Production is still `d2de7b3`; this product correction has not been deployed.

## Source and task coverage

The submitted AiDevTeam artifact `angela-noor-testing-guide-2026-10`, version1,
was received at `2026-10-13T15:27:52.309Z`. Five scenarios were marked passed
by the tester; scenarios1 and4 have remarks. The sanitized submitted source is
`docs/client-answers/2026-10-13-tester-feedback/submitted-feedback.json`.
Original portal JSON/Markdown are retained privately outside the checkout with
0600 permissions; access links, older drafts and contact details are excluded
from Git. Portal records were not edited or reset.

| Task | Observed problem | Correction and proof |
| --- | --- | --- |
| `tj-i2b1.1` | Generic furnishing gets a missing-exact-set disclaimer; two matching walnut LUMA units for eight people are called a mismatch | Broad needs retain only specific actual gaps, not an invented missing named item. Named quantity × per-unit capacity is checked separately; original customer quantity can recover a shortened model search. Wrong model, finish, explicit per-unit capacity and incomplete coverage remain negative cases. |
| `tj-i2b1.2` | Requested twelve-person update receives only an acknowledgement | Requirement tool returns the current committed selection and retained budget; main and existing repair prompts carry the summary obligation. The connected output guard now recognizes a retained customer budget, so “same budget” no longer deletes a valid summary. Historical catalog prices and replaced budgets remain blocked. |
| `tj-i2b1.3` | Replay exposes quoted literal refusal rejected, or a promised quote hold not actually recorded | One presentation quote pair is removed only if its unchanged inner excerpt occurs in the current message. Paraphrases/history remain rejected, and quotation-on-table/shortfall/proposal gates remain. Explicit refusal must be persisted before replying. Held quotation wording no longer causes a false completion error. |

Read-only production messages confirmed the exact reported replies in archived
conversation `ecaa8c22-8c5d-44be-a43f-ac351f939735`, including the correction
at15:13UTC and acknowledgement at15:14:43. The saved quantity was already3
and budget6000; this was not a lost message or missing quantity write.

## Acceptance

Root-selected local acceptance: **1264 passed**, no skips, in7.14s:

```sh
python -m pytest tests/test_llm_engine.py tests/test_verified_answers.py \
  tests/test_record_customer_requirements.py tests/test_customer_intent_tools.py \
  tests/test_decision_state.py tests/test_search_products_named_references.py \
  tests/test_llm_repair_judge.py tests/test_tester_feedback_regressions.py \
  tests/test_model_owned_intent.py tests/test_scenario_replay.py \
  tests/test_llm_grounding_output.py -q --tb=short --import-mode=importlib
```

Execution reused the existing root venv, set `PYTHONPATH` to the task checkout,
`APP_ENV=test` and unreachable fake database/Redis URLs. Whole-source/test Ruff
and format checks passed (431files); Mypy passed194source files; diff check passed.
Mutable handoff traceability is repinned with the official helper; its focused
manifest checks accompany the final documentation commit.

The normal bot model was replayed through the actual reply/state/rendering
pipeline with all database, ranking, Zoho, CRM, WhatsApp and Telegram effects
intercepted. The final receipt is
`2026-10-13-tester-feedback-model-replay.json`, code `5c7273a`.
All four declared checks passed, and the root independently read the complete
output, state and side-effect ledger. Final state: quantity3, budget6000,
quotation **declined**, no quotation or external customer/CRM effect.

The final customer reply includes:

> Updated requirements

- 12 people:3LUMA9719-4 walnut workstations.
- Budget AED6000; fixture catalog total AED5649, remainder AED351.
- Dubai delivery/installation context, with cost/schedule/address unconfirmed.
- Quotation remains on hold.

No “exact requested furniture set not confirmed” caveat appears. The earlier
replays exposed literal-refusal omission and, crucially, a raw complete summary
being reduced to “When do you need the workstations?” by the price guard. Their
receipts remain separately named `-initial`, `-second`, `-third`; they are
diagnostic history, not final acceptance.

Four bounded runs cost **USD0.02932057 total**, below the original USD0.05
ceiling. They called only the existing main model; the root was the acceptance
reader and no paid second reader was added. The final later `9570c1d` change is
only the completion diagnostic: it does not change the model prompt, text,
state or sends. Its exact observed line and genuine completion negatives pass
in the final local set; no additional model rerun was needed for logging.

This is model/pipeline proof with intercepted boundaries. Lexical fixture
ranking and a September catalog snapshot do not establish current production
RAG ordering, stock, real PDF creation or handset receipt. The tester's five
passed scenarios are her source feedback, not five new post-fix live runs.

## Root review and premortem

Review outcome: local acceptance passed; no unresolved in-scope code finding.
Existing components/entrypoints remain; no dependency, migration, model switch,
legacy semantic router or customer-facing deterministic template was added.

Verdict: GO WITH CONDITIONS — integration/deployment requires owner authority,
canonical CI and runtime/channel readback, followed by the affected natural test.

| Risk | Evidence / affected boundary | Mitigation and proof |
| --- | --- | --- |
| Validated summary erased as invented money | Confirmed by third replay raw vs final text; current-message-only evidence omitted retained budget | Carry only retained customer budget; rendered-summary and unrelated/stale monetary negatives pass. |
| Quoted evidence becomes new authorization | Plausible if normalization changed meaning; persistent consent tools | Exact unchanged current substring only; forged, paraphrased, blank and no-offer grant negatives pass. No permission inference is added. |
| Aggregate headcount masks a wrong product/finish/unit capacity | Confirmed old8vs4 error; named-product matcher shared by search/media | Same-model quantity/coverage only, with explicit wrong finish/unit/mixed cases retained. |
| Broad search wording hides a true unsupported requirement | Plausible contract consumer regression | Preserve specific missing family/property and no-full-coverage constraints; genuine mismatch tests pass. |
| Replay mistaken for live delivery | Confirmed intercepted providers/catalog limitations | Report model/pipeline, deployment, provider and tester receipt separately. |
| Executor deploys from dirty or unrelated work | Plausible shared repository/server boundary | Dedicated clean task branch, owned-only integration; preserve primary dirty work, server flags and held queues. |

Rollback after an authorized release is a code rollout to the prior verified
runtime, retaining current customer data and the enabled Wazzup guard. No data
reset/backfill, queue replay or consent rollback is needed: stored structures
are unchanged and the normalized evidence is an existing literal substring.
Before deployment, keep a fresh source/image rollback and protected settings
fingerprint; rebuild/recreate app+worker through the normal preserving helper.

## Delivery and ownership

The two narrow read-only maps ran concurrently while the root retrieved and
correlated feedback. Capacity work owned only `verified_answers.py` and its test
module in a separate clean worktree. Worker commits994b05e/6b5087c were reviewed
and integrated as59fada9/d6d84c6; root owned the shared search/reply contracts,
intent persistence, output guard, acceptance and docs.

Product deployment and fresh tester acceptance are still pending. Existing
`tj-vqcc` postdeployment natural-message proof and `tj-zc6k` external-writer
attribution remain separate; the questionnaire was submitted before guard rollout.

docs-reviewed: updated - sanitized feedback, replay fixture, report and current handoff.
graph-reviewed: no-change-needed - no enabled task-owned graph; existing boundaries retained.
