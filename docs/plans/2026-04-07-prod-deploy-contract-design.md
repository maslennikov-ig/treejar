# Production Deploy Contract Design

## Context

The live Noor runtime is hosted in `/opt/noor`, but the repository deploy flow still assumes a git checkout in `/opt/treejar-prod` and a Docker Compose project name of `treejar-prod`.

That assumption is false in production:

- `/opt/treejar-prod` does not exist on the VPS
- `/opt/noor` is the canonical runtime path
- `/opt/noor` is a runtime snapshot, not a git checkout
- the active Docker Compose project name is `noor`

This drift breaks GitHub Actions deploys and leaves operator docs inconsistent.

## Options

### 1. Keep git-based deploys and re-clone production as a repo

Pros:
- small workflow change
- familiar operator flow

Cons:
- reintroduces mutable git state on the server
- depends on remote git credentials and checkout hygiene
- conflicts with the current reality of `/opt/noor` as a runtime snapshot

### 2. Artifact-based deploy into `/opt/noor`

Pros:
- matches the live server topology
- removes remote git dependency entirely
- makes each deploy explicit and reproducible from CI
- keeps secrets and operational state local to the server

Cons:
- requires a more capable deploy script
- rollback must use deployment backups instead of `git reset`

### 3. Full release-directory + symlink switch

Pros:
- strongest atomic deploy story
- clean rollback semantics

Cons:
- larger migration
- changes path assumptions across compose, docs, and operator tooling
- higher immediate operational risk than needed for this fix

## Decision

Choose option 2.

The repository should standardize on:

- canonical runtime path: `/opt/noor`
- deploy transport: CI-built release archive
- runtime update method: extract to staging, rsync into `/opt/noor`
- compose project name: derived from target directory basename (`noor`)
- rollback source: timestamped pre-deploy backups under `/opt/noor/.hotfix-backups`

## Resulting Contract

1. GitHub Actions packages a release archive from the tracked repository contents plus release metadata files.
2. CI uploads the archive and the repo version of `scripts/vps-deploy.sh` to a temporary VPS directory.
3. `scripts/vps-deploy.sh`:
   - validates required commands
   - validates `/opt/noor/.env`
   - extracts the release archive to a temporary staging directory
   - saves a rollback backup of the current live tree
   - syncs the staged release into `/opt/noor` while preserving operational directories and secrets
   - runs `docker compose --project-name noor up -d --build`
   - verifies `http://127.0.0.1:8002/api/v1/health`
4. Operator docs reference `/opt/noor`, artifact deploys, and backup-based rollback.

## Scope

In scope:

- `.github/workflows/ci.yml`
- `scripts/vps-deploy.sh`
- `scripts/setup-vps.sh`
- operator docs and deploy memory
- a regression test for deploy-script behavior

Out of scope:

- full release-directory + symlink migration
- deterministic CPU-only image/build optimization
- non-production environments
