# Docker Maintenance Design

## Context

The canonical VPS has enough free disk to stay online, but Docker storage is clearly bloated:

- active runtime files in `/opt/noor` are small
- system journals and apt cache are small
- Docker images and BuildKit cache dominate disk usage

Current observed state on 2026-04-07:

- disk usage: ~66%
- Docker images: ~181 GB, ~171 GB reclaimable
- Docker build cache: ~168 GB, ~149 GB reclaimable

The correct fix is targeted Docker maintenance, not broad filesystem cleanup.

## Options

### 1. Manual one-off cleanup only

Pros:
- immediate recovery
- minimal repo work

Cons:
- disk bloat returns
- operator knowledge stays tribal

### 2. Aggressive scheduled prune of everything unused

Pros:
- maximum free space

Cons:
- every deploy loses all warm cache
- slower rebuilds
- higher operational surprise

### 3. Conservative scheduled cleanup plus manual aggressive mode

Pros:
- good long-term hygiene
- predictable rebuild cost
- still allows deep cleanup when needed
- no root/systemd dependency if installed via user cron

Cons:
- slightly more implementation work

## Decision

Choose option 3.

## Contract

1. Add `scripts/docker-maintenance.sh`.
   - default mode: dry-run
   - `--apply`: execute cleanup
   - `--aggressive`: reclaim all unused builder cache and all unused images
   - default scheduled mode:
     - bound builder cache with `docker builder prune --max-used-space ... --reserved-space ...`
     - prune unused images older than a retention window
   - never prune Docker volumes
   - always print before/after disk data and verify the local health endpoint

2. Add `scripts/install-docker-maintenance-cron.sh`.
   - install an idempotent managed block into the current user's crontab
   - write logs into `/opt/noor/logs/maintenance`
   - schedule once per day during off-hours

3. Update admin docs.
   - explain safe cleanup
   - explain cron installation and manual aggressive cleanup

4. Run one aggressive cleanup now on the canonical VPS.

## Rationale

We avoid `docker system prune --volumes` because live Postgres/Redis data sits in volumes and the reclaimable gain there is small. The real bloat is builder cache and old unused images, so maintenance should target exactly those resources.
