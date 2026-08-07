# Issuing authority for a live acceptance run

`tj-hr0z`. The S01–S10 production acceptance cannot start without an authority
bundle, nothing in the repository writes one, and no document said how to make
one. That is why `tj-ee5f.1` has been blocked since 2026-07-28: the last bundle
expired at 17:12 that day and nobody knew how to issue the next.

This is not bureaucracy for its own sake. A live run sends real WhatsApp
messages and writes real records into Zoho. Two of the eight input files carry
evidence collected independently of whoever executes the run, which is what
stops the executing agent from authorising itself. Keep that property.

## Who does what

**The owner issues.** Writing `authorization-v1.json` is the act of granting
permission; an agent that writes it has granted itself permission and the
control is gone.

**An agent may prepare.** Everything except the grant is mechanical and can be
gathered on request: the runtime identity, the channel and recipient, the
current store digests.

## The generator

`scripts/e2e_acceptance/prepare_live_authority.py` assembles the bundle. It does
not decide anything: every permission-bearing field is copied from a decisions
file the owner writes, which is what its tests pin.

```
uv run python scripts/e2e_acceptance/prepare_live_authority.py --template  > decisions.json
uv run python scripts/e2e_acceptance/prepare_live_authority.py --identity-template > identity.json
# owner edits decisions.json; an agent fills identity.json from live readbacks
uv run python scripts/e2e_acceptance/prepare_live_authority.py \
    --decisions decisions.json --identity identity.json
```

The default template grants nothing: zero quotas, no permissions, the local
fake adapter. An owner who edits only the targets gets a dry gate, deliberately.

## The nine files

They live in `<protected-root>/live-authority-inputs/<run-id>/`, mode `0600`,
no symlinks. The path set is validated exactly, so all nine must be present
and nothing else.

`runtime-transport.json` arrived on 2026-07-29, the day after the last bundle
was issued, which is why no bundle in the archive contains it and why the
generator is pinned against `live_authority.INPUT_REFS` rather than a list of
its own.

| file | who fills it | what it is |
|---|---|---|
| `authorization-v1.json` | **owner** | the grant: window, quotas, targets, permissions |
| `preflight-observation.json` | agent, from live readbacks | observed runtime identity plus the readback bundle digest |
| `preflight-request.json` | agent | what the preflight intends to check |
| `store-identities.json` | agent | current anchor / raw / tracked store root digests |
| `adapter-ids.json` | owner decides | `fake-local-adapter` for a dry gate, the real adapters for a live run |
| `authorized-action-specs.json` | owner decides | empty for a dry gate, one spec per permitted action for a live run |
| `execution-authorities.json` | owner decides | cleanup owner and retention authority |
| `collector-ids.json` | agent | which collector produced the readbacks |
| `runtime-transport.json` | owner decides | the webhook origin, the SSH host, and the commands the collector runs there |

## Identity must match the deployed build

`authorization-v1.json.expected_identity` pins the runtime the result will be
attributed to, and the preflight refuses if the live runtime disagrees. That is
the mechanism that makes an acceptance result mean something: it is valid for
one build and stops being valid the moment `src/` deploys again or a model
changes.

Ask an agent for the current values before issuing. Read on 2026-08-07 they were:

```
repository_commit     c977b0791c7d37ae61f3dc65de0fc6268f187088
deployed_release_sha  c977b0791c7d37ae61f3dc65de0fc6268f187088
ci_run_id             github-actions-31155865127
endpoint              https://noor.starec.ai
app_version           0.4.0
migration_head        2026_06_04_customer_memory
main_model            openai/gpt-5.6-luna     (system_configs row)
fast_model            deepseek/deepseek-v4-flash  (code default, no row)
```

Note that `main_model` is a `system_configs` row, not `settings.*`. The settings
value in production is still `z-ai/glm-5.2`, and non-core paths resolve from it.

## The window is short on purpose

`_receipt_window` caps the usable window at five minutes from the moment the
bundle is read, whatever `expires_at` says. Issue the bundle and start the run
in the same sitting. The 2026-07-28 bundle was issued at 16:51 and expired at
17:12; it is not reusable and not repairable.

## Dry gate or live run — the difference is in three fields

The 2026-07-28 bundle was a **dry gate**: `permissions: []`, `callback_types:
[]`, every quota `0`, `cleanup_method:
gate-only-zero-external-action-no-cleanup-required`, and among the stop
conditions *stop before any external action*. It verified identity and
readbacks and deliberately executed nothing. That is why the last acceptance
published as `BLOCKED` — by construction, not by failure.

A run that actually scores S01–S10 needs non-zero quotas, real permissions and
callback types, and a cleanup method that can undo what it creates. Those are
the fields where a mistake sends real messages to a real person and leaves real
rows in Zoho, so they are the owner's to set.

## Running it

Once the bundle is in place, the chain is:

```
uv run python scripts/run_noor_e2e_acceptance.py authorize-live   --repo-root . --protected-root <root> --run-id <id>
uv run python scripts/run_noor_e2e_acceptance.py prepare          --repo-root . --protected-root <root> --run-id <id> --run-plan <plan>
uv run python scripts/run_noor_e2e_acceptance.py preflight        --repo-root . --protected-root <root> --run-id <id> --baseline <baseline> --run-plan <plan>
...execute...
uv run python scripts/run_noor_e2e_acceptance.py finalize         --repo-root . --protected-root <root> --run-id <id> --run-plan <plan>
uv run python scripts/run_noor_e2e_acceptance.py verify-run       --repo-root . --run-id <id> --report-output <path>
```

An agent can drive all of it. It stops at `authorize-live` without the bundle,
which is the point.

## What actually produced every score so far

Be clear-eyed about this chain: everything after `authorize-live` needs a
`--run-plan`, a sealed `ProtectedRunPlan` carrying one pre-digested action spec
per external effect across all 29 executions. Nothing in the repository writes
one, so no run has ever gone through it.

Every real number — 2026-07-30, 2026-08-03, 2026-08-07 — came from the scenario
runner in the protected `remediation-live` tree: it posts the S01–S10 turns at
the production webhook, reads the conversations back through the admin API, and
scores each one with the product's own evaluator (`evaluate_conversation`, the
same code path that scores real customer chats). S09 and S10 use the real
recipient so the Zoho records and the PDF are genuine; S01–S08 use a per-run
phone suffix so they cannot reach anyone.

The authority bundle is still the thing that authorises that run and pins the
identity the score belongs to. It is not, today, what executes it. Say which
path a report used, because only the scenario-runner numbers are comparable to
each other.

## How to accept the result

`verify-run` writes the report. Read four things:

1. **Identity matched.** If the preflight passed, the score belongs to the
   build named above and to no other.
2. **The score against 24.0/30.** The last real number was 18.4/30 with
   functional failures in S01, S03, S04, S05, S08 and S10, on the previous
   model and a build a week older than today's.
3. **Coverage.** A low-coverage evaluation is blocking and cannot publish a
   normal result; the report shows coverage and normalized denominators.
4. **Outcome per scenario**, one of `PASS`, `FAIL`, `BLOCKED`,
   `EXCLUDED_BY_CLIENT`. A `BLOCKED` scenario is not a pass.

The result stays valid until the next deploy that touches `src/` or a model
change. Both invalidate the identity pin, and the run has to be repeated.
