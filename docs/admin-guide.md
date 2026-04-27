# Admin Guide: Noor AI Sales Bot

> **Version:** 1.0 | **Last updated:** March 2026  
> **Audience:** System administrators and technical leads

---

## 1. Accessing the Admin Panel

| Environment | URL |
|-------------|-----|
| **Primary** | https://noor.starec.ai/admin/ |
| **Dashboard** | https://noor.starec.ai/dashboard/ |

**Credentials** are stored in the server's `.env` file:
```ini
ADMIN_USERNAME=your_admin_user
ADMIN_PASSWORD=your_secure_password
API_KEY=your_internal_endpoint_secret
```

`/admin/` and `/dashboard/` now share the same admin session cookie. Login through `/admin/login`, then use the dashboard and SQLAdmin in the same browser session.

`/dashboard/` is the operator-facing surface: it combines KPI analytics with protected action panels for catalog sync, Telegram health checks, weekly report generation, and manager-review workflows.

`API_KEY` is still required for protected internal API routes on the canonical environment, including `/api/v1/crm/*`, `/api/v1/quality/*`, `/api/v1/reports/*`, `/api/v1/referrals/*`, `/api/v1/notifications/*`, and `/api/v1/manager-reviews/*`.

> ⚠️ The project currently uses a main-only workflow. Treat `https://noor.starec.ai` as the canonical environment and validate changes there in a controlled manner.

---

## 2. Managing Tables

The current SQLAdmin surface exposes 13 runtime models. Read-heavy/generated tables are intentionally read-only; only operational configuration surfaces remain editable.

| Table | Purpose | Key Filters |
|-------|---------|-------------|
| **Conversations** | All WhatsApp dialogues | Status, language, date range |
| **Conversation Summaries** | Persistent compact summaries of older dialogue history | Model, version |
| **Messages** | Individual messages per conversation | Role (user/assistant), date |
| **Products** | Synced canonical catalog records | Category, is_active, stock |
| **Quality Reviews** | AI-evaluated dialogue scores | Score range, rating, date |
| **Escalations** | Escalated conversations | Status (pending/in_progress/resolved) |
| **Manager Reviews** | AI evaluation of manager follow-up after escalation | Manager, rating, date |
| **Knowledge Base** | Indexed FAQ, rules, values | Source, category |
| **System Config** | Runtime key/value settings | Key, updated_at |
| **System Prompts** | Prompt rows currently stored in DB | Name, version, active flag |
| **Metrics Snapshots** | Periodic aggregated metric snapshots | Period, updated_at |
| **Referrals** | Referral code records | Status, phones, created_at |
| **Feedback** | Post-sale feedback records | Ratings, recommend, created_at |

### Filtering and Search
- Use the **search bar** at the top of each table for text search.
- Use **column filters** (funnel icon) for status, date range, score.
- Columns marked with a sort arrow can be sorted by clicking the header.

### Editing Policy
- **Read-only by design:** Conversations, Conversation Summaries, Messages, Products, Quality Reviews, Manager Reviews, Metrics Snapshots, Referrals, Feedback.
- **Editable for operators:** Escalations, Knowledge Base, System Config, System Prompts.
- Treat Products as synchronized external truth. Use sync actions instead of manual row edits.

---

## 3. Editing System Prompts

The bot's behavior is controlled by system prompts stored in the **System Prompts** table.

### Current Truth
- The versioned prompt workflow lives in the authenticated admin API (`/api/v1/admin/prompts/*`).
- The SQLAdmin table view shows current prompt rows, but direct row edits are not the versioned workflow.

### Versioning
- Versioned updates create a new row, increment `version`, and inactivate the previous row.
- Previous versions remain in the table for rollback/reference.

### Best Practices
- **Test carefully on the canonical environment**: deploy the updated prompt to `https://noor.starec.ai`, send controlled test messages, and verify behavior before broader use.
- **Document changes externally**: there is no `notes` field on `system_prompts`; record prompt intent in the change log or stage notes.
- **One change at a time**: avoid changing multiple prompts simultaneously.

---

## 4. Bot Configuration (SystemConfig)

Key runtime settings are stored in **Admin → System Config** as key-value pairs (JSONB).

| Key | Default | Description |
|-----|---------|-------------|
| `followup_timeout_hours` | `24` | Hours of inactivity before the first follow-up message |
| `followup_schedule_days` | `[1, 3, 7, 30, 90]` | Follow-up schedule in days after last contact |
| `max_context_messages` | `5` | Number of recent messages kept in LLM context |

### Quality Review Delivery

Bot quality monitoring now uses a **hybrid owner-facing flow**:
- **Realtime warning** is sent only for critical red flags.
- **Final quality review** is sent for every matured bot dialogue when either:
  - the conversation is `closed`, or
  - there were no new messages for **3 hours**
- Final reviews use the preserved **0–30** rating scale with the current thresholds:
  - `excellent`: `26–30`
  - `good`: `20–25.9`
  - `satisfactory`: `14–19.9`
  - `poor`: `<14`

There is no separate admin threshold key for bot quality alerts anymore. Telegram delivery is driven by the fixed red-flag rules and the mature-dialogue final-review logic above.

### How to Edit a Config Value
1. Go to **Admin → System Config**.
2. Find the key you want to change (for example, `followup_timeout_hours`).
3. Click Edit → update the `value` field (must be valid JSON).
4. Save.

> **Important:** Config changes for the ARQ worker take effect on the **next job run** (up to 1 hour). To apply immediately, restart the worker: `docker compose restart worker`.

---

## 5. Dashboard Operator Center

The dashboard is no longer metrics-only. It now includes the operator controls that map to the current admin/runtime workflow.

### Catalog Sync
- Use **Dashboard → Operator Center → Catalog Sync**.
- This workflow is implemented in the dashboard operator center, not as a SQLAdmin custom action.
- **Run Treejar Sync** is the recommended path because Treejar Catalog API remains the canonical catalog source of truth.
- **Run Zoho Sync** exists only as a legacy operational path.
- Both actions queue the background job under the same shared admin session used for `/admin/`.

### Telegram Notifications
- Use **Dashboard → Operator Center → Telegram Notifications** to verify whether Telegram is configured.
- The panel shows masked token/chat values and exposes **Send test message**.
- This is the safe operator entrypoint for notification health; the raw internal notification API still exists behind `API_KEY`.

### CRM Attribution And Returning Customers
- Inbound source/UTM data is stored locally in conversation metadata under `source_attribution`.
- The first captured attribution is preserved as `original`; repeat contacts update `latest` only.
- Zoho CRM outbound source/UTM custom-field mapping is intentionally disabled until the client confirms exact Zoho field API names.
- Returning-customer CRM context sent to the LLM/admin surfaces is bounded to name, segment, and one recent status; full transcripts are not injected.

### Weekly Operations Report
- Use **Dashboard → Operator Center → Weekly Operations Report** to refresh the 7-day summary.
- The panel surfaces:
  - dialogues and conversion,
  - escalation volume and tracked reasons,
  - top mentioned products,
  - manager-review KPIs and top managers,
  - the Telegram-formatted report preview.

### Manager Review Queue
- Use **Dashboard → Operator Center → Manager Review Queue** to see resolved escalations still waiting for evaluation.
- Each pending item can be evaluated directly from the dashboard.
- The same panel also shows the latest completed manager reviews, including score, rating, and response time.

### Direct API Note
- `POST /api/v1/products/sync` remains protected and should be treated as an implementation detail behind the dashboard/admin session, not as an open maintenance shortcut.
- Referral operations remain protected internal APIs for now. The extended referral admin/reporting surface from the original specification is still optional and is intentionally not exposed in the dashboard at this stage.

---

## 6. Monitoring and Health Checks

### Health Endpoint
```
GET https://noor.starec.ai/api/v1/health
```
Returns `{"status": "ok"}` if the app and database are reachable.

### Docker Logs (via SSH)
```bash
ssh -p 2222 noor-dev@95.216.204.189

cd /opt/noor

# App server logs (FastAPI)
docker compose logs -f app --tail=100

# Background worker logs (ARQ)
docker compose logs -f worker --tail=100

# Redis logs  
docker compose logs -f redis

# All services
docker compose logs -f --tail=50
```

### Daily Telegram Summary
Every morning at 06:00 UTC, Noor sends a daily summary to the configured Telegram chat. It includes:
- Total conversations in the last 24 hours
- Escalation count
- Average quality score
- LLM cost estimate

If the summary stops arriving, check the worker logs.

---

## 7. Emergency Procedures

| Problem | First Step | If Still Failing |
|---------|-----------|-----------------|
| Bot not responding | `docker compose logs worker --tail=50` | `docker compose restart worker` |
| Slow responses | `docker compose stats` (check CPU/RAM) | `docker compose restart app` |
| Zoho sync failing | Check `ZOHO_REFRESH_TOKEN` in `.env` | Re-generate Zoho OAuth token |
| Database connection error | `docker compose ps db` | `docker compose restart db` |
| Out of disk space | `df -h` and `docker system df` on VPS | Run Docker maintenance cleanup |

### Restarting Services
```bash
# Restart a single service
docker compose restart app
docker compose restart worker

# Full restart (production)
docker compose up -d --build

# View resource usage
docker compose stats
```

### Docker Maintenance
For disk cleanup on the canonical host, prefer the repo-managed maintenance script over ad-hoc prune commands:

```bash
ssh -p 2222 noor-dev@95.216.204.189
cd /opt/noor

# Preview what the script would do
bash scripts/docker-maintenance.sh

# Conservative cleanup: keep recent cache, remove old unused images
bash scripts/docker-maintenance.sh --apply

# Aggressive one-off cleanup: reclaim all unused builder cache and all unused images
bash scripts/docker-maintenance.sh --apply --aggressive
```

To install the daily automatic cleanup under the `noor-dev` user crontab:

```bash
ssh -p 2222 noor-dev@95.216.204.189
cd /opt/noor
bash scripts/install-docker-maintenance-cron.sh
crontab -l
```

The managed cron job writes logs into `/opt/noor/logs/maintenance/`.

### Rollback a Deployment
If a new deployment causes issues:
```bash
# SSH into VPS
ssh -p 2222 noor-dev@95.216.204.189

# Go to the runtime directory
cd /opt/noor

# List recent deployment backups
ls -1t .hotfix-backups/deploy-*.tar.gz | head

# Restore the desired backup archive through the deploy script
bash scripts/vps-deploy.sh \
  --archive .hotfix-backups/<backup-file>.tar.gz \
  --target-dir /opt/noor \
  --health-url http://127.0.0.1:8002/api/v1/health
```

> Production deploys are artifact-based into `/opt/noor`. The live runtime is not a git checkout, so `git reset --hard` is not a supported rollback path on the VPS.

---

## 8. Contact for Support

- **Technical issues**: Contact the development team via Telegram.
- **Zoho/Wazzup issues**: Check credentials in `.env` and Zoho API console.
- **Weekly demo**: Fridays at 11:00 MSK, Zoom ID: 584 425 2807.
