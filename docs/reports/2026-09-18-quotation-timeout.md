# Quotation confirmation timeout

Task: tj-3egt. Status: deployed and verified.
Owner's standing delivery request is Push, Merge, Deploy; preserve test-only
channel/worker. No additional paid probes, synthetic messages or data repairs.

## Incident evidence

Live release before repair:4abe835; public health, database and Redis healthy.
Conversation33f3ee6f-e509-40b3-a288-4d0d2e803249, Sep18UTC:
-13:13 customer requested quotation and supplied delivery address.
-13:14:22 create_quotation called, but returned before persistence or vendor
  activity. Current metadata contains no recorded quote consent/workflow,
  quotation number, proposal or sale order identifier.
-13:15:28 next turn (confirmed) started; OpenRouter200 logged13:15:34.875.
-13:16:58.608 core_chat failed at its90-second deadline. No recorded quotation
  tool/vendor activity occurred during this failed turn. HTTP200 alone does not
  prove a completed usable model response. Exact provider-side cause unavailable.

## Repair and safety boundary

Bound each non-stream core-chat completion and retry that same model request
once, preserving messages/tool results and the original total deadline. Never
restart the whole sales agent: earlier tool side effects must not repeat.
Use one shared attempt budget for timeout and provider finish-error recovery.
Suppress nested SDK retries for this bounded path; preserve cancellation.
Unknown cost of an incomplete attempt remains explicitly unknown.

Quotation tool guidance now tells the model to record consent already expressed
in the current message rather than ask the customer to repeat it. Email is
listed among existing mandatory fields; validation/business rules unchanged.
Tool start/end/outcome/duration logs omit customer arguments and identify which
execution phase timed out on future incidents.

Premortem: GO WITH CONDITIONS. Bounded retries only before a completion is
handed to agent tool execution; no replay of create_quotation or sends. Preserve
90-second core run deadline, outer chat deadline, model and reasoning settings.
Cancel propagates. Test a completed tool followed by a stalled completion.
Deploy through the already-guarded app-only entrypoint, preserving existing
test-only worker settings; save source/image rollback and read back exact SHA.

## Local acceptance and rollback

4,073 tests passed,20skipped; Ruff check/format and Mypy180source files passed.
Seven new transport/agent cases cover hanging completion recovery, no tool
replay, bounded retries shared with in-band provider failures, outerdeadline,
cancellation and unchanged non-core behavior. No paid provider calls.

Per-completion bound35s; totalcore90s unchanged. Failed retry cost can be unknown
and is marked as such rather than asserted zero. Model and reasoning unchanged.

Rollback backup: `/opt/noor/.hotfix-backups/tj-3egt-20260918`. Restore
source-before.tar.gz and compose-rollback.yml for app/worker only, using preserved
images noor-rollback:tj-3egt-app and noor-rollback:tj-3egt-worker. Previous live
release4abe835. Preserve environment, database activity and held messages.

## Delivery verification

Fast-forward merged and pushed to main. Runtime release:
`74ae14c789c909763b4150a4b22e296dd8abdd38`.
[CI 35360991418](https://github.com/maslennikov-ig/treejar/actions/runs/35360991418)
succeeded, including deployment: 4,066 passed, 27 skipped on CI; lint and types
passed. Local Python environment: 4,073 passed, 20 skipped.

Public health returned this exact release SHA with healthy database and Redis.
All three changed source hashes match in both running app and worker containers;
both have zero restarts. Environment fingerprint unchanged. Worker startup lists
only process_incoming_batch and confirms restore mode, disabled cron and warmup.
Existing test-channel restrictions remain in place.

No additional paid probes or outbound test messages were sent. Local mocked
transport tests prove recovery and no tool replay; successful live quotation
creation after this release still requires the tester's normal scenario.
Private acceptance logs and source hashes: ~/.local/state/treejar/tj-3egt/.
