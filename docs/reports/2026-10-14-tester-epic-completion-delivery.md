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

## Canonical release and runtime proof

Published main source589f3024cfcf002063b120ab315fb0564956b680 through the
existing owner SSH credential. Canonical CI38526089347 completedSUCCESS:
changes/lint/type-check/test/semantic-evidence/deploy allSUCCESS. Full CI
4584passed/27gatedskips74.69s; semantic gate completed independently.
Deployment safely recreated only app+worker at07:08:29UTC.

Readback07:11:39UTC: both containers release589f302,health/dependenciesOK;
protected fingerprint57552c05d85e1647b59f56d07c77006bc55662af82cbc8add38491c263cbae0a
unchanged. .env byte-identical to private rollback original; guard/restoretrue,
stockdeltafalse, normal main modelopenai/gpt-6-luna, expected function/cron
allowlist.0restarts/OOMfalse; DB/Redis/nginx start times unchanged.
Additive index migration2026_10_13_fk_query_indexes is the sole DB head,
all5expected indexes present. Accepted media source hash exactly matches.

No provider credential/key/access changes or competing process shutdown was
performed. Provider at07:11:39still returned audit host; its source remains
blocked by account/audit access. Owner now requested fresh natural three-turn
acceptance on...0921; actual arrival/summary/held state/photos are pending.
Do not close tj-i2b1 or claim bot delivery until that proof arrives.

## Additional runtime acceptance

Pure deployed media filter on the retained actual coffee-table reply and
current catalogrows: pending3,kept00-07015316/00-07015317,WalnutDallas excluded.
No message send was made. Both desired public image HEADs return200,image/jpeg.
This proves deployed filtering/file availability, not handset receipt.

Read-only collect_runtime_snapshot at07:15:32UTC with awareUTC observation and
SQL READONLY returned45stale pending escalations,0dependencyfailures,0queue
depth. Monitoring flagfalse unchanged; no notification or monitoring cron was
activated. This closes source/runtime bugtj-535g without altering old records.

Docs-reviewed:updated - current handoff, release/rollback, owner/provider action.
Graph-reviewed:no-change-needed - no enabled task-owned graph or stable
entrypoint changes; existing project index reviewed and retained.

## Scoped cleanup

Completed CI worker40f1ba0 is patch-equivalent to main6d4663f (`git cherry`
negative); all three owned files are byte-identical to published main. Clean
worktree with no untracked work was removed without force; exact local ref
was deleted by expected-old-SHA compare. Native worker completed, no process
was killed. Root delivery checkout is retained for pending owner acceptance;
other agents' checkouts, original private feedback and guide are retained.
Primary tracked-user diff still SHA256
7e23c1c0227f95dee93a666a1b37afe90f3fddf48d03cb6f21561630801d9af0.

At07:16:48UTC there were no postdeploy natural owner...0921 messages or
outbound rows. This is not a delivery pass; requested actual acceptance is
still pending. No old-message replay, synthetic customer send or paid
acceptance run was used.

## Fresh owner delivery and reopened live defects

Owner...0921 sent all three requested tests as one message (not three turns).
Provider message7564f1ad-2b65-4a41-aab1-d9888fab0fbe reached Noor at
07:24:07.207113UTC; worker completed07:26:08.759UTC. Text784fdcf7-2626-40b9-939a-d7df0a1358bb
and four actual photo sends succeeded, including CT1065OakDevon/WengeMagic.
Owner confirmed the text and photos arrived. Caption-only audit rows are not
additional sends.

The same check failed product acceptance: exact three-unitLUMA was called
unconfirmed; consentnot_requested, selected_itemsempty, budgetnull persisted
although the text promised quotationhold and the selected quantities. No
quotation/CRM effect was created. Children.1/.2/.3 reopened; .4photos retained
its proven provider and owner receipt. This receipt cannot prove multi-turn
retention because the owner supplied all inputs in one message.

## Bounded live correction

Leaf fix_suffix_catalog_match owns only verified_answers.py and its test in
codex/tj-i2b1-match-suffix-20261014 (base589f302). fefe098/dcbe232 accepted
as dfb80cb/ba592be: adjacent trailing/using counts now bind to a namedmodel
with exactfinish, unitcapacity and arithmetic. Subsequent contradictory
quantities/models, ambiguous capacities and wrongfinishes remain nearby.
Independent review's sentence-tail and numericmodel240 findings corrected;
84focused checks passed. CT1065 two-finish requests now require each full finish on a matching
row with the same base title/capacity; shapes/types/dimensions stay constrained.
Leaf5111370 accepted as54d3c5a;102focused checks,18new variants passed.

Root994d6f1 owns intent state-write recovery. Nullable/omitted evidence captures
only current customer text verbatim; provided strings and individual detail
proofs retain exact literal checks. No intent is inferred from words by code.
Registered rejected writes are ModelRetry feedback, logged rejected without
arguments. Unsaved field groups must be covered by successful writes before
final output or quotation effects; unrelated/no-op writes cannot bypass them.
Explicit policy-prohibited fields use the pre-existing permitted alternative,
without forcing false consent. Existing per-tool/output retry limits and
core-chat deadline remain; no whole-agent retry or paidsecondreader is added.
Direct Python descriptive-result contracts remain unchanged.

Root selected acceptance1378passed; wholeRuff/format432files and Mypy194
passed. Real FunctionModel cases cover literal repair, ignored refusal,
wrong-field/no-op bypass, retainedbudget, same-batch stalegrant quotation,
policy recovery and nullable current evidence. Final leaf delta is integrated; canonical fullreleaseCI and fresh live
acceptance remain required.

Read-only live base/communication/qualifying prompt caches match code defaults
byte-for-byte. Read-only five-row current catalog subset supplies CT1065 and
LUMA to the new fixture; it is not complete provider/retrieval evidence.
Original feedback and private prompts/receipts remain outside Git.

Three further normal-model intercepted runs cost0.00792468,0.00754472 and
0.00394965USD, bringing all seven original-budget smoke runs to0.04873962USD
(<0.05). First confirmed the noncontiguous joinedquotes failure. Second
correctly blocked unresolved writes but repeated model copying exhausted
retries. Third chose evidence=null and tools confirmed3LUMA/budget6000/
consentdeferred, but the pre-call budget guard stopped before final output.
None is a complete new model/delivery pass. No more paid smoke calls are
planned in this budget; actual postdeploy customer acceptance remains required.

Live rollback refresh at08:18:37UTC: private bundle
/opt/noor/.hotfix-backups/tj-i2b1-live-20261014T081837Z (dir0700/files0600),
source589f302; imagesnoor-i2b1-live-rollback-app:20261014t081837z and
noor-i2b1-live-rollback-worker:20261014t081837z retained. App/worker0restarts,
OOMfalse; DB/Redis/nginx starttimes unchanged.1462MBavailable/82GBdiskfree.
EnvironmentSHA5ab1406c4e331be7baa03b7412dd8749f065b5c88a28d348e0607b5a7d021948
retained; do not rewind customer DB/queues on rollback.

## Correction release/runtime acceptance

Main527fe1fa6f0df91aa309121ab9719c3e4c11faa4 deployed app+worker08:44:42UTC.
CanonicalCI38536867395SUCCESS:4671passed/27gatedskips91.32s; lint/typecheck/
changes/deploySUCCESS. Semantic-evidence jobskipped; no new independent
bridge/model pass is claimed. Root source1378/format432/Mypy194 and10repin
tests passed.

Live readback08:48:37UTC and independentworker source check: all six owned/
protectedsource hashes match; both releases527fe1f; .env byte-identical to
08:18rollback, protectedfingerprint57552c05 unchanged. Guard/restoretrue,
stockdeltafalse, mainmodelgpt6luna, queue0, publichealthDB/RedisOK. App/worker
0restarts/OOMfalse; DB/Redis/nginx starttimes unchanged.

Provider still returns audit host; externalwriter remainsblockedwithout
account/admin/audit access. Guard code/registration retained; no key changed.
At08:52:26UTC no postcorrection natural owner message/outbound row yet; old
emptyselection/nullbudget/notrequestedconsent unchanged. This is a baseline,
not current acceptance. Owner was asked one fresh two-unit/budget6000/held/
CTphotos message; a separate no-budget-number update will prove retention.

Completed catalog worker5111370 is clean and all three commits patch-equivalent
to freshmain527fe1f; two owned files identical. Removed withoutforce; exact
localref deletion used expected-oldSHA5111370. Root deliverycheckout retained
for real acceptance; unrelated branches/worktrees/private originals retained.
