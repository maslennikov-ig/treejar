# Task 3 live transport stream report

Status: complete; no external network or SSH operation was performed.

## Changed files

- `scripts/e2e_acceptance/live_transport.py`
- `tests/test_e2e_acceptance_live_transport.py`

## Behaviour

- `OneShotWazzupWebhookTransport` accepts only the exact HTTPS Wazzup inbound
  endpoint and one strict inbound-text payload, makes one POST with redirects
  disabled, and reports every post-dispatch exception as uncertain without
  logging endpoint or body.
- `ReadOnlySshTransport` freezes a host alias and source-command allowlist,
  rejects shell/mutation-capable vocabulary, uses a fixed timeout and
  `shell=False`, exposes command identities/digests, and fails closed on
  timeout or a non-zero exit.

## Verification

- RED: `uv run --extra dev pytest tests/test_e2e_acceptance_live_transport.py -q --tb=short` failed with the missing module (9 failures).
- RED: the focused secret-output test failed while a post-dispatch exception
  retained its raw cause, then passed after suppression.
- GREEN: the same focused command passed `9 passed` after implementation.
- `uv run --extra dev ruff check ...`, `ruff format --check ...`, and
  `git diff --check` passed.

## Residual risk

No production host alias, source-command inventory, protected authorization
binding, or real I/O was configured or verified locally; those require the
separate authorized execution stream.
