# English everywhere, and a judge that costs what it is worth

Owner decisions of 2026-08-07, after the measurement round in
`docs/reports/2026-08-07-repeated-scoring-and-the-second-reader.md`:

1. **The quality judge becomes `z-ai/glm-5.2`.** A panel of Claude readers is
   accurate and far too expensive to run as a gate.
2. **Russian goes.** Everything technical is English only. The product itself
   operates in English and Arabic.

Both change the instrument, so they belong in one round and one re-baseline
rather than two.

## What is already true in the code

Facts, checked rather than assumed. Each one changes the work.

- **The model id is `z-ai/glm-5.2`.** It is already the code default for
  `openrouter_model_main` in `src/core/config.py`, though a stored
  `system_configs` row overrides the main sales route with
  `openai/gpt-5.6-luna`. The judge route is separate:
  `PATH_QUALITY_FINAL` in `src/llm/safety.py`.
- **There is a deliberate guard against exactly this.**
  `is_glm5_model_name` in `src/llm/safety.py` matches the substring `glm-5`,
  so `glm-5.2` trips it. `AIQualityScopeConfig.validate_risky_settings` then
  refuses the configuration unless `glm5_warning_override` is set, and
  `warnings_for_ai_quality_config` raises a `glm5_qa` warning reading *"GLM-5
  is expensive for QA automation and requires an explicit admin override."*
  **That guard says the opposite of the reason for this change, and it was
  written by someone who had looked at the rates.** Resolve it before
  implementing: either current pricing makes the guard stale and it should be
  narrowed to `glm-5` proper, or the guard is right and `glm-5.2` is not the
  cheap option it is being chosen for.
- **`glm-5.2` was rejected once, for a different job.** The battle of
  2026-07-27 scored it 88.5 against `glm-5`'s 94.0 for the *sales* route and
  recorded an unstable tail and weak grounding. In the same round it showed
  perfect JSON and schema compliance, perfect reliability, perfect tool
  arguments, and the best median latency. Those are judge properties, not sales
  properties, so this is not a contradiction — but the battle never measured
  **scoring variance**, which is the one property that decides whether a judge
  can gate a release.
- **`PATH_QUALITY_FINAL` passes no temperature at all.**
  `model_settings_for_path` builds `max_tokens`, `timeout` and `extra_body` and
  nothing else, so the judge runs at the provider default. The acceptance
  harness's own bounded judge in `scripts/e2e_acceptance/evaluators.py` refuses
  any judge whose temperature is not 0. This is `tj-swgu.10`'s free lever and
  belongs in this round.
- **The Russian surface is about 1,080 lines**: 675 in `src/`, 300 across 34
  test files, 103 in `scripts/`.

## Decision 1: the judge

Adopt `z-ai/glm-5.2` for `PATH_QUALITY_FINAL`, at temperature 0, and
characterise it before trusting it.

**No judge is adopted on a single pass.** That is the whole finding of
`tj-swgu.9`: the outgoing judge scored one unchanged transcript
`15.2 16.2 21.5 21.6 23.9`, and three materially different builds came out as
one number. A new judge is not better because it is cheaper or newer; it is
better if its repeated scoring of identical text moves less.

So the acceptance for this decision is a measurement, not a switch:

```
uv run python -m scripts.e2e_acceptance.score_uncertainty <run> [--against <run>]
```

k = 5 over the ten stored `5656c82` transcripts, giving the pooled sd and the
interval on the mean. Compare against the two readings already on record:

| instrument | judge sd | mean carries | mean |
|---|---|---|---|
| `deepseek-v4-flash`, measured | 3.8 | ±3.3 | 16.1 |
| five blind Claude readers, measured | 0.9 | ±0.3 | 12.3 |
| `z-ai/glm-5.2` | **unmeasured** | — | — |

The Claude panel is kept as a **reference reading, not as a gate**. It is the
one careful, repeat-backed scoring of these transcripts in existence, and it is
what tells us whether the cheap judge is merely consistent or actually right. A
judge can be perfectly repeatable and perfectly wrong; sd alone cannot see that.

Adopt `glm-5.2` if its sd is materially below 3.8 and its mean sits near the
reference. If it is repeatable but far from the reference, that is a finding
about the rubric prompt, not a reason to stop.

## Decision 2: English only

Three categories, and they are not the same change.

**A. What we write.** Owner-facing report text, alert text, quality-review
prose, admin labels. This is the bulk and it is safe to change.
`src/services/report_localization.py` is the easy half: a presentation-only
map from English enum values to Russian labels, with no locale switch. Remove
the translation and the English values already flow through. The harder half is
`src/quality/evaluator.py`, where `EVALUATION_PROMPT` carries the fifteen
criteria in Russian and instructs the model to answer in Russian, plus
`build_summary_text` and the fallbacks in `src/quality/schemas.py`.

**B. Technical artifacts.** Specs, reports, handoff, Beads, code comments. Most
are already English. `docs/superpowers/specs/2026-08-03-...-spec-ru.md` is a
Russian duplicate of its English sibling and should go.

**C. What we recognise from a customer.** This is the one that is not obviously
in scope, and it needs an owner answer before anything is deleted.
`src/llm/engine.py` and `src/llm/verified_answers.py` carry Russian *input*
patterns: affirmations (`да`, `нет`, `ок`, `спасибо`), quotation vocabulary
(`кп`, `коммерческое предложение`, `счёт`, `инвойс`), price objections
(`дорого`, `дешевле`). These do not produce a single Russian character for a
customer; they make the bot understand one who writes Russian.

> **Open question for the owner.** Removing these is the strict reading of
> "the product operates in English and Arabic". Keeping them costs nothing and
> only helps. **Recommendation: keep the input patterns, remove all Russian
> output.** Before deciding either way, count Russian-language conversations in
> the production database — it is a read-only query and it settles the question
> with a fact instead of a preference.

## Sequencing, and why it is not free

Changing the rubric prompt from Russian to English changes the judge's input.
The 12.3 ± 0.3 reference was taken against the Russian criteria. So:

1. Land the language change and the judge change together.
2. Re-baseline once, with repeats, on the new judge and the new prompt.
3. Only then read any number as evidence about the dialogue.

Doing them in two rounds means re-baselining twice and holding two dead
baselines. Doing them together means one honest number at the end.

The fifteen criteria may be **translated but not altered in substance**. They
are the customer's, and `tj-swgu.10` already records that only the scale and
the judge are ours.

## Work packages

| | package | depends on | notes |
|---|---|---|---|
| P0 | Resolve the `glm5_qa` cost guard against current rates | — | may invalidate the whole premise |
| P0 | Count Russian conversations in production; settle category C | — | read-only query |
| P1 | `PATH_QUALITY_FINAL` temperature 0 | — | `tj-swgu.10`, one line |
| P1 | Translate `EVALUATION_PROMPT`, `RED_FLAG_PROMPT`, and the manager evaluator | — | substance unchanged |
| P1 | Remove `report_localization.py` and its callers' Russian | — | largest, lowest risk |
| P1 | `schemas.py` summary headers and fallbacks | — | |
| P2 | Tests: 34 files asserting Russian strings | the above | mechanical, large |
| P2 | Technical artifacts, including the `-spec-ru` duplicate | — | |
| P1 | Point `PATH_QUALITY_FINAL` at `z-ai/glm-5.2` | cost guard | config, not code |
| P0 | Characterise the new judge at k=5 and re-baseline | all of the above | the acceptance |

## What must not change

- Customer-facing English and Arabic. This round removes no customer-visible
  capability in either.
- The fifteen criteria in substance.
- Frozen `AC-01..AC-30` and its digest.
- The product system prompt does not grow; per-turn `runtime_directives` only.
- Sealed acceptance rounds are superseded, never rewritten. The corrected
  figures belong in `tj-swgu.13`, not in edits to the reports that published
  them.
- No PII, provider or message identifier, or captured wording in any report.

## Acceptance

- `z-ai/glm-5.2` has a measured pooled sd over the ten stored transcripts at
  k = 5, published with the interval it implies for the mean, and the decision
  to adopt or reject cites that number rather than cost alone.
- No Cyrillic remains in `src/`, `tests/`, `scripts/` or `docs/`, except any
  customer-input patterns the owner explicitly chose to keep under category C.
- The full suite, Ruff, Ruff format, Mypy and
  `scripts/orchestration/run_process_verification.sh` are green.
- The re-baselined mean is stated with its uncertainty, and no conclusion in
  the round rests on a movement smaller than that uncertainty.

## Open questions

1. Does current OpenRouter pricing make the `glm5_qa` guard stale, or is
   `glm-5.2` genuinely the expensive option the guard says it is?
2. Category C: keep Russian customer-input recognition, or remove it?
3. Does the owner still want Russian-language *reports* delivered anywhere —
   Telegram alerts in particular — or is English acceptable there too?
