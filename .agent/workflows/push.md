---
description: Create release (version bump + changelog) — NOT deployment
---

Create a new version release with changelog. **This is NOT deployment!**

- For **Dev deploy**: just `/push` (auto-deploys to Dev via branch push)
- For **Stage/Prod deploy**: use `/deploy` (merges to master via Worktree → triggers Blue/Green on VPS)

**Features:**
- Auto-detects version bump type from conventional commits
- **Generates dual changelogs:** `CHANGELOG.md` and `RELEASE_NOTES.md`
- Updates project version in relevant locations
- Creates git tag and pushes to origin
- Full rollback support on errors

**Usage:**
// turbo-all
bash .agent/scripts/release.sh $ARGUMENTS --yes
