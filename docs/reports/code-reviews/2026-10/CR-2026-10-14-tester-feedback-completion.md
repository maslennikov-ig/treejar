# Review: October tester epic completion

Date: 2026-10-14. Reviewed source: `4b032c718888f6393b5bbc9a50e2b7f7f78e7041`
(`codex/project-consistency-20261013`, stacked on `e7074ca`).
User request: independently verify the agent completion report.
Verdict: local implementation verified; epic completion NOT established.
`tj-i2b1` correctly remains `in_progress`. Its four source-fix children are
closed locally; their closure does not assert production delivery.

## Findings

### P1 operational gap: competing Wazzup callback changes remain active

Existing task: `tj-zc6k` (outside the product epic).
Five direct provider GETs at UTC 06:39:36, 06:39:48, 06:40:00, 06:40:12 and
06:40:24 returned HTTP200 and host `audit.treejartrading.ae`, not the approved
Noor callback. Subscription flags were unchanged. The worker completed ten
scheduled guard checks between 06:32:01 and06:41:00; all returned `restored`.
The deployed implementation reads back the canonical URI and subscriptions
before returning that status. It is therefore repeatedly recovering a route
that does not remain canonical; the process/person responsible is UNKNOWN.
This is evidence of unstable routing, not proof that the guard is disabled.

Fresh worker readback: guard enabled, restore mode enabled, sender equals
allowlist, guard function and minute cron registered. Guard source SHA256
`17c03fea44cc4969f909f0686ab02571608c752bd1a22f486c018b8c1ac13db1`
matches the checked source. Hourly notification limits and the existing
minute recovery policy are unchanged. Resolve the competing writer under its
own authority; another speculative overwrite loop is not an acceptance proof.

### P2 source defect: runtime-document exceptions use `paths-ignore`

Task: `tj-7ize`, discovered from the epic; not a new epic child.
File: `.github/workflows/ci.yml:6-13` and `:16-23` in source4b032c7.
The new `!docs/faq.md` and `!docs/04-sales-dialogue-guidelines.md` entries are
placed inside `paths-ignore`, while `docs/**` and all Markdown remain ignored.
GitHub documents ordered inclusion/exclusion through `paths`; `paths-ignore`
is exclusion-only. The additions therefore do not establish the intended
runtime-doc-only trigger. The deployment classifier added later in the job
cannot help when the workflow is skipped. `src/llm/company_faq.py` and
`src/rag/indexer.py` consume these files. Current workflow tests check list
membership, not the runtime-doc-only versus report-only trigger behaviour.

Use a documented ordered `paths` filter (including the runtime-document
exceptions after broad exclusions), or trigger the workflow and classify the
change inside it. Verify the two runtime documents and ordinary reports as
separate cases. This is a docs-only delivery hole; the code-bearing candidate
would still satisfy its existing trigger.

Primary reference:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore

## Independently verified local evidence

- Executable/test source4b032c7 was unchanged throughout review; worktree clean.
- Full pytest: **4555 passed,20 skipped**,175.81s. Real integration/provider
  checks were gated; this does not prove handset delivery or production DB
  migration application.
- Command used: `UV_PROJECT_ENVIRONMENT=/home/me/code/treejar/.venv
  PYTHONPATH=/home/me/code/treejar/.worktrees/project-consistency-20261013
  APP_ENV=test DATABASE_URL=postgresql+asyncpg://fake:fake@127.0.0.1:1/fake
  REDIS_URL=redis://127.0.0.1:1 uv run --no-sync python -m pytest tests/
  -q --tb=short --import-mode=importlib`.
- Full Ruff check passed,431 files formatted, Mypy194 source files passed.
- `scripts/orchestration/run_process_verification.sh` passed; diff check passed.
- The accepted structured-title media correction is byte-identical to e7074ca:
  `src/llm/response_runtime.py` SHA256
  `4791f460397e86d8e9acfccc0372eb761b391be630e974670f8af3804d57fac0`.
- Live read-only DB schema matches the new ManagerReview/Referral timestamp
  mapping, including preexisting manager_reviews.updated_at. No live schema
  mutation or migration execution was performed.

## Delivery and acceptance evidence

Fresh remote read: main=`32c95f6b71d213937938ea1b91f21be7f7e720fd`;
published tester branch=`e7074ca8d29be22ab3d548a396cde8a81fd3eae5`;
no remote `codex/project-consistency-20261013` ref. No Actions run found for
source4b032c7/the stacked branch. Local verification is not canonical release CI.

Fresh health and both container release files report
`d2de7b3f47260cbb88114fc42f8cb6c85e27832d`; Redis/PostgreSQL health OK.
The four product fixes have not been deployed. No fresh receipt of corrected
summaries/quotation holds/photos on that candidate can be asserted.
The earlier owner confirmation established guard-era text delivery only; the
owner then reported missing photographs, which created child4.

Completion requires authorized release delivery and canonical CI, source/app/
worker/guard/channel readback, and fresh affected-scenario plus actual-photo
receipt. Existing product merge/deploy authority is still pending according
to the current handoff. Keep the epic open. Resolve the newly tracked CI
finding with the candidate owner and retain tj-zc6k as an explicit runtime gap.

## Review actions and limits

No production callback PATCH, deploy, credential/access change, real-user
message, paid model call or history replay was performed. Existing worker
reconciliation continued independently. Customer state, queues, unrelated
checkouts and the candidate source were preserved. This audit has a dedicated
local documentation branch; the candidate was not merged or published by it.
