# Spec: the client's ruler, and what 1400 human dialogues actually say

Written 2026-08-10 to hand the work on. Everything below is measured unless it
says otherwise, and where it is a hypothesis it says so.

## Where things stand

`main` is at `ffb8a2d`. Production is on `8b75888`. Two builds are committed and
**unmeasured**: `7c34d55` (the name gate removed, three prohibitions turned into
instructions) and `ffb8a2d` (this bridge). Gates on the committed tree: ruff,
ruff format over 421 files, mypy over 168 sources, pytest `3441 passed, 19
skipped`, `run_process_verification.sh` OK.

## The corpus

The client delivered `github.com/Viktor-admin-dev/treejar-dialogs-corpus`,
private. **1400 real WhatsApp dialogues** between Treejar's own salespeople and
real customers, 01.01.2026–14.07.2026, 19 945 messages (9 477 customer / 10 468
seller), 1393 English / 6 Arabic / 1 Russian. Unfiltered — the client's note
says so and the manager spread confirms it.

It now lives at `<git-common-dir>/codex-orchestration/treejar-dialogs-corpus`,
mode `0700`/`0600`. It was found on a world-readable `/tmp` path and moved.

Files: `dialogs.jsonl` (21 MB), `messages.csv`, `dialogs_summary.csv`,
`rubric.json`, `stats.json`, `ПОЯСНИТЕЛЬНАЯ_ЗАПИСКА.md`.

**Read the explanatory note before touching anything.** Four things in it are
load-bearing:

1. **The corpus is anti-patterns, not a benchmark.** The client says so in as
   many words. Mean **6.05/30**. Do not use it as an SFT set; a bot trained on
   it reproduces the behaviour the company is paying to replace.
2. **1247 of 1400 already carry an evaluation**, scored by
   `anthropic/claude-haiku-4.5` against the client's own 15-criterion rubric —
   the same fifteen ours came from. Scale 0/1/2, max 30, **no applicability**:
   every criterion is scored on every dialogue.
3. **The WhatsApp channel is only the entrance to the funnel.** 81% of dialogues
   carry a boilerplate footer handing out the seller's personal mobile; deals
   close by phone or in the Jebel Ali showroom. `outcome_visible_in_channel` is
   true for 192 of 1400. **~86% of outcomes are invisible.**
4. Dialogues were cut heuristically on a ≥7-day pause; manager attribution is
   approximate; attachments were not exported.

Pseudonymisation is done and verified by the client: phone hashes, masked names,
`<PHONE>`/`<EMAIL>`/`<URL>` substitution. **But client company names and deal
amounts remain in the message text.** The package is commercially sensitive.

## The finding that reset the headline

Our published 20.02 and their 6.05 were never the same measurement.

`calculate_weighted_score` drops the rules that did not apply and stretches the
surviving blocks back to /30 — right for build-versus-build. The client scores
all fifteen and lets an unearned criterion stand at zero. On **their**
convention the same 53 packets read:

| | /30 | interval |
|---|---|---|
| Noor, `8b75888`, 53 packets over 19 scenarios | **13.58** | ±1.11 on another scenario draw; ±0.26 on a re-read of this set |
| Treejar salespeople, 1247 evaluated dialogues | **6.05** | ≈±0.85 clustered by the 5 managers |

`raw_total` in `src/quality/schemas.py` is the only place that arithmetic
happens. `scripts/e2e_acceptance/score_raw_convention.py` prints it.

**The gap is 2.2×, not the 3.3× the two rulers implied**, and it is not yet a
measurement. Two confounds remain, and the work below exists to remove them.

### Confound 1 — the applicability map

The 106 reads behind 13.58 were handed a frozen map: *"rule 12 is not
applicable, return applicable=false"*. A reader told that does not go looking.
Mean applicable rules is 8.3 of 15, so **6.7 rules per packet carry a zero
nobody examined**. 13.58 is a lower bound of unknown tightness.

### Confound 2 — the judge

Theirs is `claude-haiku-4.5`; ours is an Opus-class blind panel.
`docs/reports/2026-08-07-repeated-scoring-and-the-second-reader.md` records a
**−3.8 systematic shift between two judges on identical text**. A shift that
size accounts for half of a 7.5-point gap.

One free calibration check is already done and comes out in the client's favour:
on `greeting_name_company`, where ground truth is deterministic (does the
seller's text contain "Treejar"), their judge gives **zero false 2s** and 3.2%
false 0s.

## What reframes the claim

**Rules 12, 14 and 15 — collect contacts, close the deal, agree the next contact
— were applicable in 2 reads of 106.** Our acceptance scenarios never reach the
conversion phase. Decomposing the gap by criterion, **+8.57 of the +7.50 sits in
criteria 1–9**, and the bot is net **−1.26** across the conversion criteria.

What the evidence supports is a claim about **openings**. It does not support a
claim about selling, and no report may make one.

**And the comparison is partly against a template.** Verified directly against
`dialogs.jsonl`: **87.2%** of evaluated dialogues (1088/1247) contain a WhatsApp
Business auto-responder. With it the human mean is **6.40**, without it **3.65**.
On `collect_contacts` the auto-responder scores **0.76** and our bot **0.02** —
on the single criterion that turns a thread into a lead we lose to a canned
template by a factor of 38. That is the most actionable sentence available and
it belongs in the report.

## The work

Phases 0 and 1 are delivered in `ffb8a2d`. What follows is ordered; each item
names what closes it.

### `tj-vz7o.3` — the map-free re-read *(P0, no authority needed)*

Re-read the **same 53 stored packets** with a rubric that has no applicability
concept, so both sides of the bridge are measured the same way. This is the arm
that turns 13.58 from a lower bound into a number.

- `RUBRIC-RAW.md` derived from `EVALUATION_PROMPT` (`src/quality/evaluator.py:129`)
  with the NOT APPLICABLE paragraph and the `applicable`/`n_a` fields removed,
  and an added instruction to score all fifteen on the transcript alone.
- 53 packets × 2 independent blind reads = 106 reads, ≤13 packets per reader.
  Readers see the transcript and nothing else: no map, no build id, no baseline,
  no other reader's scores.
- **Done when:** `score_raw_convention.py` runs over the new scores directory,
  every score file carries exactly 15 criteria and no `n_a`, reader disagreement
  is printed, and the delta against 13.58 is stated with its interval.

### `tj-vz7o.4` — the judge bridge *(P0, needs authority for paid calls)*

Run the client's judge over our 53 packets. 53 `claude-haiku-4.5` calls. This is
the only arm with no extrapolation: exactly one thing differs.

- Ask the client for their evaluator prompt — their note §8 offers it. If it has
  not arrived within a day, reconstruct from `rubric.json`, which ships all
  0/1/2 anchors, and **label the output "reconstructed from rubric.json anchors,
  not the client's prompt"**.
- Feed the raw transcript only. Do not hand the judge an applicability map.
- **Done when:** the judge shift on our own packets is stated with an interval,
  and the bridged gap replaces 13.58−6.05 everywhere it appears.

### `tj-vz7o.5` — the paired arm on the corpus *(P1, no authority, depends on .3)*

Our panel over a stratified sample of the corpus, paired against the client's
stored score on the same dialogue.

- Deterministic seeded sample: **12 dialogues × 5 bands** of the client's score
  (0–2, 3–5, 6–8, 9–11, 12+) = 60, 2 blind reads each = 120 reads. The 12+ band
  holds only 32 dialogues — sample it exhaustively and report the smaller n.
- Estimate the shift **per band, never as one constant**. Both judges agree
  trivially at the floor (25 dialogues score exactly 0), so a constant fitted at
  a mean of 6.05 understates the shift at our 13.58.
- Cross-check against `tj-vz7o.4`. Agreement means the judge constant is
  genre-independent; disagreement **is** the genre effect and is a finding.
- **Done when:** a per-band shift table exists with intervals, and it is stated
  whether the two arms agree.

### `tj-vz7o.6` — the metric the rubric cannot see *(P1, no authority)*

922 of 1400 dialogues end with the seller unanswered; **478 end with the
customer unanswered**. The fifteen criteria score none of this.

Compute over the corpus and over our packets: the share of customer messages
that receive a substantive reply, and time to first reply. This is probably a
stronger claim than 13.58 versus 6.05, because it names a failure the client can
see in their own CRM.

- **Done when:** both figures exist for both sides with their denominators, and
  the corpus figure is reconciled against the client's own `continuity` counts.

### `tj-vz7o.7` — a scenario set drawn from real openings *(P1, no authority)*

The real opening distribution, measured: of 1358 dialogues with a customer
message, **525 (39%) are one identical Google Ads lead template**, 146 are an
attachment only, and 687 are natural text with a **median of 21 characters**.

- Take 15–20 natural openers stratified by length from those 687 into the
  acceptance set. This is the zone where we measured the failure: `R06` 8.10,
  `R07` 7.35, `R09` 10.50.
- Do not claim "a scenario set of 1400 real openings". It is one template, one
  photograph, or four words — and the photograph openings cannot be reproduced
  at all, because attachments were not exported.
- A scenario-set change and a build change never ship in the same measured
  round. Freeze the set and take its baseline first.
- **Done when:** the set is frozen with its selection seed recorded, and a
  baseline exists on it.

### `tj-vz7o.8` — rule 11, stopped and put to the owner *(P2, decision)*

Rule 11 is applicable in 16 reads of 106 and scores **0.00**. Taking it to a
perfect 2 everywhere it applies moves the raw mean by `8×2/53 = 0.30`, against a
reader disagreement of 1.58 — **a fifth of the instrument's noise floor. It is
unmeasurable by construction.** It is worth 0.05 of the 7.50 gap. The owner has
forbidden the bot to offer a discount, so the ceiling is structural.

Put three dispositions to the owner in writing and require a choice:

- **(a)** drop it and rescale both sides to /28;
- **(b)** redefine it as *"a verified package total or lead-time commitment,
  with no price concession"* — the only version the bot can honestly earn, and
  it needs a data source we do not have;
- **(c)** keep it and **print beside every score** that policy caps the ceiling
  at 28.

Until (b) has a source, (c) is the honest default. A stated cap is a policy; an
unexplained zero is a defect.

### `tj-vz7o.9` — rubric validity, put to the client *(P2, decision)*

Four criteria that no human earned in seven months: `sincere_compliment` **0.00**
across all 1247, `drill_and_hole` 0.01, `ask_company_activity` 0.02,
`discount_bonus` 0.05. Eight of thirty points. Either the criteria are wrong, or
the judge cannot detect them, or the method is not practised.

Frame it as a question to the client using their own numbers, not as our
opinion. Note the other direction too: on `ask_company_activity` our bot already
scores 0.75 against their 0.02. That is not a defect, it is the differentiator.

**Also request from the client:** their evaluator prompt (§8); the attachments,
because "can you share some pictures" is the single most common unanswered
customer question and the export dropped exactly that artefact; and the Zoho
deal export keyed on `crm_deal_id`, for real outcomes.

## What we never claim

- **Nothing about conversion, revenue, deal size or close rate.** 86% of
  outcomes are off-channel. There is no outcome variable, therefore no outcome
  claim — not "we expect", not "consistent with".
- **Nothing about the bot closing deals.** Rules 12/14/15 were applicable in 1
  packet of 53.
- **That a rubric score predicts an outcome.** Untested here and everywhere.
- Disclose without being asked: the denominator is **1247, not 1400** (the 153
  unevaluated have a median of 2 messages); the human figure is clustered on
  **5 managers with one desk at 67%**; the 7-day cut is heuristic; attachments
  are missing; and our 53 packets are **19 scenarios**, not 53 observations.

## Rules of engagement

Seven were paid for in the previous rounds and still hold. Three are new.

1. A rubric change and a build change never ship in the same measured round.
2. Compare a shape with itself, and only over the same scenarios.
3. A condition on the world is a guard; a condition on what Noor thinks she did
   is a leak.
4. Generation is stochastic — compare k runs, never one.
5. Read two transcripts by eye every round. Three of the last round's findings
   came from that and from nothing else.
6. The model reads the customer; code owns the catalog.
7. A deterministic guarantee beats a directive — and this model follows an
   instruction where it loses a prohibition (owner, 2026-08-10).
8. **Two rulers exist and they are not interchangeable.** Every client-facing
   number goes through `raw_total`. Every internal build comparison goes through
   `calculate_weighted_score`. Never subtract across them.
9. **A denominator travels with every number.** 53 packets are 19 scenarios;
   1400 dialogues are 1247 evaluated across 5 managers.
10. **No corpus text enters the working tree.** Derived artefacts carry
    `dialog_id` and integers. There are no commit hooks in this repository and
    `.gitignore` does not match `dialogs.jsonl`;
    `tests/test_corpus_stays_outside_the_repository.py` is the only net.
