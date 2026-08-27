---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
stream_owner: prod-relay-tls-worker
orchestration_level: inner_loop
scope_kind: foundation
immediate_consumer: root-orchestrator
public_facade: relay-and-noor-public-tls
bounded_acceptance: root-authorized-stale-lineage-retirement-plus-public-tls-readback
non_goals:
  - dns-nginx-certbot-firewall-systemd-or-certificate-mutation
  - certificate-renewal-dry-run-or-issuance
  - paid-or-provider-backed-validation
evidence:
  - none
task_id: tj-7w8f.2
epic_id: tj-7w8f
stage_id: tj-7w8f-prod-host-remediation
session_id: n/a
milestone: production-host-maintenance-health
milestone_status: accepted
agent_type: custom
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: production-TLS-and-ownership-risk-required-security-auditor-review-without-unauthorized-override
repo: treejar
branch: codex/prod-relay-tls-remediation
base_branch: main
base_commit: 25598101f33f47c9d1117499daeb1f4a02928046
worktree: /home/me/code/treejar/.worktrees/prod-relay-tls
write_zone:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.2.md
success_criteria:
  - relay-dns-public-certificate-local-lineage-and-challenge-owner-identified
  - repair-versus-retire-decision-supported-by-read-only-evidence
  - exact-proposed-remediation-rollback-and-verification-recorded-without-execution
  - noor-tls-separation-and-current-health-proven
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-7w8f-prod-host-remediation/stage-manifest.json
  - .codex/stages/tj-7w8f-prod-host-remediation/summary.md
selected_skills:
  - none
selected_agents:
  - security_auditor
catalog_candidates:
  - none
parallel_group: tj-7w8f-production-host-diagnostics
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: dedicated worktree and merged local branch removed by the stage cleanup entrypoint
risk_level: high
verification_tier: inner
risk_tags:
  - security
  - rollback
  - public-api
affected_surfaces:
  - api
invariants:
  - rollback
  - test-matrix
docs_impact: ops-deploy
docs_reviewed: updated
docs_review_notes: operational-diagnosis-remediation-and-rollback-are-recorded-in-this-artifact-only
verification:
  - two-independent-DoH-resolvers-for-relay-and-noor-A-AAAA-CNAME: passed
  - public-relay-HTTP-challenge-and-TLS-readback: passed
  - forced-Noor-IP-relay-HTTP-challenge-readback: passed
  - safe-systemd-journal-certbot-lineage-and-renewal-config-readback: passed
  - active-nginx-route-certificate-reference-and-port-owner-readback: passed
  - public-noor-health-and-TLS-verification: passed
  - scripts/orchestration/validate_artifact.py: passed
  - git-diff-check: passed
changed_files:
  - .codex/stages/tj-7w8f-prod-host-remediation/artifacts/tj-7w8f.2.md
explicit_defers:
  - remote-relay-host-certificate-renewal-automation-remains-owned-outside-treejar
---

# Summary

Решение: **safely retire stale lineage**, не чинить renewal на Noor-хосте.
`relay.starec.ai` сейчас принадлежит другому публичному хосту и обслуживается
его wildcard-сертификатом. Локальная single-name lineage на Noor VPS нигде в
активном nginx не используется, но остаётся в Certbot renewal inventory и дважды
в сутки переводит общий `certbot.service` в `failed`.

Production не менялся: DNS, nginx, Certbot config/lineage, сертификаты, firewall
и systemd state не редактировались; renew, dry-run и issuance не запускались.

Root outcome supersession (2026-08-27): the stale unused local lineage was later
backed up and retired. Local filesystem readback, Noor health/fingerprint, public
relay TLS, and a successful active Certbot service/timer state passed. The
worker-phase non-mutation statement and runbook below are retained as history,
not pending current work.

# Scope / Routing

Проанализирована только граница `relay.starec.ai` ↔ Noor VPS:

- публичные A/AAAA/CNAME, HTTP/HTTPS и подаваемые сертификаты relay и Noor;
- локальные Certbot lineage/renewal properties без private key, account ID,
  email или token values;
- активная nginx-конфигурация для relay/Noor, HTTP-01 path и владельцы портов
  80/443;
- bounded journal evidence по `certbot.service`.

Реальная конфигурация production и публичный readback приняты как источник
истины. Репозиторный код не менялся.

# Findings

## F1 — stale relay lineage ломает общий Certbot service

- **Severity / priority:** high, P1 operational maintenance risk.
- **Classification:** must-fix.
- **Confidence:** high.
- **Confirmed evidence:** Cloudflare и Google DoH независимо вернули
  `relay.starec.ai A=95.213.143.228`, без AAAA и CNAME. Noor VPS и
  `noor.starec.ai` имеют другой адрес: `95.216.204.189`.
- **Confirmed evidence:** публичный relay подаёт `CN=*.starec.ai`, serial
  `0581AB4B6CADE73AEBB3AD59056B63C292E5`, SHA-256 fingerprint
  `D4:4A:71:33:1C:EA:DE:6A:6F:C8:81:47:7C:7C:65:6C:50:C3:1D:8F:9A:F9:4A:DA:87:46:6A:4F:2C:16:21:55`, valid through
  `2026-10-05T17:51:06Z`. Это не локальный Certbot certificate
  `relay.starec.ai`, serial `5D896D81EE6C15184B2C0A9D21AF13C9A60`, valid
  only through `2026-09-17T22:47:48Z`.
- **Confirmed evidence:** локальный renewal использует
  `authenticator=webroot`, `webroot_path=/var/www/html`, но в active
  `nginx -T` отсутствуют и `server_name relay.starec.ai`, и ссылка на
  `/etc/letsencrypt/live/relay.starec.ai/`. Порты 80/443 Noor VPS принадлежат
  nginx.
- **Confirmed evidence:** неизвестный HTTP-01 probe на публичном relay получает
  301 на HTTPS, затем 200 `text/html` размером 456 bytes; SHA-256 тела совпадает
  с корнем relay. То есть remote endpoint отдаёт application shell вместо
  challenge token. Forced request на Noor IP тоже получает redirect от default
  vhost, а не `/var/www/html` token.
- **Confirmed evidence:** `certbot.service` завершался с `status=1/FAILURE`
  на каждом просмотренном timer run с 2026-08-20 по 2026-08-26; journal называет
  единственной неуспешной lineage `/etc/letsencrypt/live/relay.starec.ai/` и
  `Some challenges have failed`. Timer остаётся active.
- **Failure path / prerequisite:** пока public DNS ведёт на `95.213.143.228`,
  Let's Encrypt HTTP-01 никогда не читает `/var/www/html` Noor VPS. Даже перенос
  DNS на Noor сам по себе не починит renewal без отдельного relay vhost.
- **Impact:** лишний локальный certificate не угрожает текущему публичному relay
  напрямую, но делает общий renewal unit красным и может скрыть реальный сбой
  другой lineage. Контроль сейчас только detective; preventive cleanup — удалить
  stale lineage из inventory.

### Smallest remediation and expected risk reduction

После отдельной root-авторизации выполнить **только локальное удаление stale
lineage**. DNS, remote relay, nginx и действующие сертификаты не менять. Это
убирает единственный подтверждённый failing renewal и не затрагивает live relay
или Noor.

Команды ниже — proposal; в этой диагностике они не выполнялись. Запускать из
авторизованной root shell на `noor-hetzner`:

```bash
set -euo pipefail
umask 077

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir=/root/letsencrypt-retired/relay.starec.ai
backup="$backup_dir/relay.starec.ai-$stamp.tar.gz"

install -d -m 0700 "$backup_dir"
tar -C / -czpf "$backup" \
  etc/letsencrypt/renewal/relay.starec.ai.conf \
  etc/letsencrypt/archive/relay.starec.ai \
  etc/letsencrypt/live/relay.starec.ai
chmod 0600 "$backup"
sha256sum "$backup" > "$backup.sha256"
chmod 0600 "$backup.sha256"

nginx -T 2>/dev/null | grep -q '/etc/letsencrypt/live/relay\.starec\.ai/' \
  && { echo 'ABORT: active nginx reference exists'; exit 1; } \
  || true

certbot delete --cert-name relay.starec.ai --non-interactive
systemctl reset-failed certbot.service

printf 'rollback_backup=%s\n' "$backup"
```

Trade-off: root-only backup содержит старый private key, поэтому он должен
оставаться mode `0600`, только на host и под существующей backup-retention
политикой. `certbot delete` — локальная операция; certificate revoke не нужен и
не предлагается.

### Rollback

Rollback нужен только при обнаружении неизвестного consumer. Использовать
точный `rollback_backup`, напечатанный remediation-командой:

```bash
set -euo pipefail
umask 077
backup=/root/letsencrypt-retired/relay.starec.ai/relay.starec.ai-<STAMP>.tar.gz

sha256sum -c "$backup.sha256"
systemctl stop certbot.timer
tar -C / -xzpf "$backup"
certbot certificates
systemctl reset-failed certbot.service
systemctl start certbot.timer
systemctl is-active certbot.timer
```

Rollback восстанавливает прежнее failing renewal и потому является временным:
после него нужно отдельно определить неизвестного consumer либо перенести
renewal на хост `95.213.143.228`.

## F2 — Noor TLS отделён и сейчас здоров

- **Severity / classification:** informational, optional/nit.
- **Confidence:** high.
- `noor.starec.ai A=95.216.204.189`, без AAAA/CNAME; адрес совпадает с public IP
  Noor VPS.
- Public Noor и local Certbot inventory совпадают по certificate serial
  `062CA81B41A06CB2D46FB456725785EA7C1E`; public certificate valid through
  `2026-10-27T19:16:12Z`, SHA-256 fingerprint
  `E2:B2:1D:51:0C:01:2F:BA:35:B4:7A:E8:A4:8A:A7:3F:51:D4:D4:3C:B2:98:49:68:82:35:B9:82:70:B4:DF:9E`.
- Active Noor vhost имеет собственные `server_name`, certificate/key paths и
  HTTP-01 location rooted at `/var/www/html`; relay lineage не referenced.
- `https://noor.starec.ai/api/v1/health` вернул HTTP 200 с TLS verification 0;
  OpenSSL verification returned `0 (ok)`.
- Поэтому удаление неиспользуемой relay lineage не требует nginx reload и не
  имеет пути к Noor certificate. Integration-edge контроль — fingerprint и
  health должны остаться неизменными до/после cleanup.

# Verification

## Выполненные read-only проверки

- Cloudflare DoH и Google DoH: одинаковые A/AAAA/CNAME ответы для relay и Noor.
- `curl` public relay HTTP, HTTP-01 probe и HTTPS: remote IP и application-shell
  fallback подтверждены без вывода body.
- `openssl s_client`/`openssl x509`: public certificate subject, serial,
  fingerprint и expiry прочитаны для relay и Noor.
- `systemctl show`, bounded sanitized `journalctl`, sanitized renewal configs и
  `certbot certificates`: failing lineage и различие сертификатов подтверждены.
- `nginx -T` с безопасной фильтрацией и `ss -ltnp`: активного relay vhost/cert
  reference нет; Noor route и nginx ownership подтверждены.
- Noor health returned HTTP 200; certificate verification passed.

## Предлагаемая post-remediation verification

Не запускать ручной `renew`, `dry-run` или issuance. Сначала доказать локальный
cleanup и неизменность Noor, затем прочитать результат следующего штатного timer
run:

```bash
set -euo pipefail

test ! -e /etc/letsencrypt/renewal/relay.starec.ai.conf
test ! -e /etc/letsencrypt/live/relay.starec.ai
test ! -e /etc/letsencrypt/archive/relay.starec.ai
nginx -T 2>/dev/null | grep -q '/etc/letsencrypt/live/relay\.starec\.ai/' \
  && { echo 'FAIL: stale active reference'; exit 1; } \
  || true
nginx -t
systemctl is-active certbot.timer

curl -fsS --max-time 15 -o /dev/null \
  -w 'noor_http=%{http_code} tls_verify=%{ssl_verify_result}\n' \
  https://noor.starec.ai/api/v1/health
echo | openssl s_client -connect noor.starec.ai:443 \
  -servername noor.starec.ai -verify_return_error 2>/dev/null \
  | openssl x509 -noout -serial -fingerprint -sha256 -enddate

systemctl show certbot.timer certbot.service \
  -p ActiveState -p SubState -p Result -p LastTriggerUSec -p NextElapseUSecRealtime
journalctl -u certbot.service --since '<RETIREMENT_UTC>' --no-pager \
  | grep -E 'relay\.starec\.ai|renew|failure|failed|error' || true
```

Expected Noor fingerprint is the value in F2. The final journal check must be
performed only after `LastTriggerUSec` advances naturally; absence of a relay
attempt and `Result=success` close the maintenance failure without an extra
provider call.

# Delivery / Cleanup

This worker produced an artifact-only handoff. The root orchestrator later
completed and verified the retirement, accepted the evidence, and removed the
merged local branch and worktree.

# Risks / Follow-ups / Explicit Defers

- **Immediate containment:** no emergency relay action is required while the
  remote wildcard certificate remains valid through 2026-10-05. Do not stop the
  shared Certbot timer; that would weaken renewal coverage for eight valid local
  lineages.
- **Remote-owner follow-up:** the owner of `95.213.143.228` must independently
  retain renewal responsibility for the served wildcard certificate. Static
  review of Noor cannot verify its renewal configuration.
- **Residual risk:** public relay depends entirely on the remote host and its
  wildcard renewal. We proved current DNS/TLS/challenge behavior, not the remote
  host's certificate automation or rollback.
- No full security assurance is claimed from this bounded read-only review.
