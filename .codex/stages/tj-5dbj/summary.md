# Stage Summary

Stage ID: `tj-5dbj`
Status: `closed`
Updated: 2026-04-14
Baseline: `main@d1eb3f5118cb1cfa4bb5816fdce7c7bd6efe059e`

## Outcome

- `tj-5dbj` is closed as the runtime/deploy hardening stage for deterministic `/opt/noor` rebuilds and CPU-only packaging.
- Docker and CI now install from the locked `uv` environment instead of drifting through ad hoc package resolution.
- Linux lock resolution for `torch` is pinned to the CPU wheel index, with a contract test guarding against accidental CUDA/NVIDIA dependencies.
- Repo-local process and stage closeout entrypoints now remain usable on hosts where `python3` is older than 3.11 by re-executing through `uv`.
- `scripts/vps-deploy.sh` is portable on macOS bash and checks `.env` before command preflight, keeping runtime/deploy work isolated from product logic.

## Linked Artifacts

- [`.codex/stages/tj-5dbj/artifacts/tj-5dbj.md`](./artifacts/tj-5dbj.md)

## Next Step

- Start a new stage only with fresh live/runtime evidence or a separately prioritized operational track.
- Treat host-local WeasyPrint library provisioning as machine setup, not as repo-local application logic.
