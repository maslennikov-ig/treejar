# October tester epic completion and delivery

Status: IN PROGRESS. Date:2026-10-14. Parent:tj-i2b1.
Owner instruction: identify and remove repeated audit callback changes and
finish all incomplete work from the independent review. This authorizes the
reviewed product/CI correction delivery to canonical Noor, preserving test0665.
It does not authorize unrelated account credential rotation or warehouse writes.

## Scope and ownership

| Stream | Owner | Source / write zone | Proof / rollback |
|---|---|---|---|
| Runtime callback writer tj-zc6k | root | provider/audit investigation; only proven obsolete setter | canonical provider readback through prior trigger; no credential changes without account facts |
| Runtime-doc trigger tj-7ize | fix_ci_runtime_docs | isolated worker4b032c7; workflow + workflow tests | runtimeFAQ/rules/report/source cases |
| Product integration/release tj-i2b1 | root | codex/tj-i2b1-complete-20261014;4b032c7 plus owned CI correction and handoff/report | existing accepted four fixes; canonical release CI, source/worker/channel readback and actual fresh receipt |

Primary dirty main and all unrelated worktrees are preserved. Source4b032c7
has independent4555passed/20gatedskips,Ruff/format/Mypy194/process evidence.
The CI worker is independent of root routing investigation; root owns final
integration, acceptance and deployment. Model inherited; no second reader.

## Technical premortem

Verdict: GO WITH CONDITIONS for product delivery; competing writer removal
requires identified process/access or a bounded account-side owner action.
- Confirmed: callback repeatedly returns to audit despite minute restoration.
  More frequent overwriting does not establish stable delivery. Keep guard;
  resolve the competing writer through the provider's credential boundary.
- Confirmed: dirty main is checked out. Legacy .agent deploy helper insists
  on checking out main again and cannot preserve this owner's work. Use the
  same isolated integration pattern in the dedicated release worktree, push
  only a proven descendant of fresh origin/main; canonical CI invokes the
  existing scripts/vps-deploy.sh including its test-worker preservation gate.
- Confirmed: stacked source contains39-file consistency/migration changes;
  reused full source acceptance applies, but final canonical release CI must
  include the new workflow. Migration adds indexes; no existing data rewrite.
- Plausible: resource pressure during Docker rebuild. Retain live old images
  and source, preserve DB/Redis/nginx and allow active inbound job drainage.
- Executor error: stale callback/subscriptions, wrong channel or guard flag,
  stale local main, or accepting provider sent as handset receipt. Bind
  source/remote identity, retain protected config fingerprint and require
  current provider plus actual tester receipt for product completion.

Rollback preflight: snapshot effective safety fields, env0600, release/source,
compose and tagged app/worker images before authorized push/deploy. On failed
rollout restore owned previous source/compose/images and unchanged environment
without rewinding customer DB or queues; compatible additive indexes can remain.
Existing delta activation stays off and monitoring remains at current setting.

## Current observations

- Audit host resolves to46.225.136.202, different from canonical Noor95.216.204.189.
  Owner confirms no SSH access to the audit host. No setter found in bounded
  readable /opt,/srv,/etc/cron.d source scan other than Noor's recovery guard
  and retained inactive receipts. Actor/process remains UNKNOWN.
- Owner asks whether bot-server controls can block it. Bot-server firewall
  cannot enforce authorization on the provider's PATCH/webhooks endpoint.
  Account-side integration/credential control needs fresh owner account facts;
  no speculative access/credential change will be performed.

## Results

CI worker40f1ba0 integrated as6d4663f; root reviewed the full diff. Forty-two
focused tests pass; root final metadata/CI checks pending.

Rollback bundle: `/opt/noor/.hotfix-backups/tj-i2b1-20261014T065944Z`
(env/files0600, directory0700). Retained images:
`noor-i2b1-rollback-app:20261014t065944z` and
`noor-i2b1-rollback-worker:20261014t065944z`. Preflight14Oct06:58UTC:
live d2de7b3; protected fingerprint57552c05d85e1647b59f56d07c77006bc55662af82cbc8add38491c263cbae0a;
guard/restoretrue, stockdeltafalse;0restarts/OOMfalse;82GB free disk.
Memory headroom1130MB and swapfull; monitor rebuild, preserve old runtime.

Provider observation06:58:18/38/58audit,06:59:18Noor,06:59:38/58audit
proves restoration does not remain stable. Owner confirms no Wazzup admin
access. Account-side removal of the external writer is an explicit access
blocker; product/CI delivery continues without rotating shared credentials.

## Final local acceptance before authorized push

Root-selected CI/traceability set:96passed1.45s; affected Ruff/format pass,
process/diff pass. Full4555/20and Ruff/format/Mypy194source evidence on4b032c7
is reused: `git diff4b032c7 -- src migrations scripts docker-compose.yml` is
empty; only CI workflow/test and review/delivery documentation changed.
Canonical full release CI remains required after main push.

SSH authentication with the existing owner key succeeds as maslennikov-ig;
no GitHub permission expansion or OAuth refresh is needed. Remote main32c95f6
is an ancestor; root-owned dedicated source is clean before publish.
No local-main checkout/reset or legacy helper --force is used.
