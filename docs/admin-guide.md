# Admin Guide: Noor AI Sales Bot

> **Version:** 1.0 | **Last updated:** March 2026  
> **Audience:** System administrators and technical leads

---

## 1. Accessing the Admin Panel

| Environment | URL |
|-------------|-----|
| **Production** | https://noor.starec.ai/admin/ |
| **Development** | https://dev.noor.starec.ai/admin/ |

**Credentials** are stored in the server's `.env` file:
```ini
ADMIN_USERNAME=your_admin_user
ADMIN_PASSWORD=your_secure_password
```

> ⚠️ Always test changes on **dev.noor.starec.ai** before applying to production.

---

## 2. Managing Tables

The Admin Panel provides CRUD access to all 6 database tables:

| Table | Purpose | Key Filters |
|-------|---------|-------------|
| **Conversations** | All WhatsApp dialogues | Status, language, date range |
| **Messages** | Individual messages per conversation | Role (user/assistant), date |
| **Products** | Synced Zoho Inventory catalog | Category, is_active, stock |
| **Quality Reviews** | AI-evaluated dialogue scores | Score range, rating, date |
| **Escalations** | Escalated conversations | Status (pending/in_progress/resolved) |
| **Knowledge Base** | Indexed FAQ, rules, values | Source, category |

### Filtering and Search
- Use the **search bar** at the top of each table for text search.
- Use **column filters** (funnel icon) for status, date range, score.
- Columns marked with a sort arrow can be sorted by clicking the header.

### Exporting Data
1. Navigate to any table (e.g., Conversations).
2. Click the **"Export"** button in the top-right area.
3. A CSV file will be downloaded with all visible records.

---

## 3. Editing System Prompts

The bot's behavior is controlled by system prompts stored in the **System Prompts** table.

### How to Update a Prompt
1. Navigate to **Admin → System Prompts**.
2. Click the prompt you want to edit (e.g., `sales_agent_main`).
3. Edit the `content` field in the inline editor.
4. Click **Save** — the version number increments automatically.

### Versioning
- Every save creates a new version (`version` field auto-increments).
- Previous versions are kept in the database for rollback.
- To **roll back**: find the previous version record, copy its `content`, paste into the latest record, and save.

### Best Practices
- **Test on dev first**: deploy the updated prompt to `dev.noor.starec.ai`, send test messages, verify behavior.
- **Document changes**: add a comment in the `notes` field explaining what changed and why.
- **One change at a time**: avoid changing multiple prompts simultaneously.

---

## 4. Bot Configuration (SystemConfig)

Key runtime settings are stored in **Admin → System Config** as key-value pairs (JSONB).

| Key | Default | Description |
|-----|---------|-------------|
| `escalation_threshold` | `10` | Quality score below which a quality alert is sent to Telegram |
| `followup_timeout_hours` | `24` | Hours of inactivity before the first follow-up message |
| `followup_schedule_days` | `[1, 3, 7, 30, 90]` | Follow-up schedule in days after last contact |
| `max_context_messages` | `5` | Number of recent messages kept in LLM context |

### How to Edit a Config Value
1. Go to **Admin → System Config**.
2. Find the key (e.g., `escalation_threshold`).
3. Click Edit → update the `value` field (must be valid JSON).
4. Save.

> **Important:** Config changes for the ARQ worker take effect on the **next job run** (up to 1 hour). To apply immediately, restart the worker: `docker compose restart worker`.

---

## 5. Syncing the Product Catalog

Products are synced from Zoho Inventory automatically every hour.

### Manual Sync
If you need to force an immediate sync (e.g., after a large catalog update):
```bash
curl -X POST https://noor.starec.ai/api/v1/products/sync \
  -H "X-API-Key: YOUR_API_KEY"
```
The sync runs in the background and typically completes in 2-5 minutes for ~856 SKUs.

---

## 6. Monitoring and Health Checks

### Health Endpoint
```
GET https://noor.starec.ai/api/v1/health
```
Returns `{"status": "ok"}` if the app and database are reachable.

### Docker Logs (via SSH)
```bash
ssh root@136.243.71.213

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
| Out of disk space | `df -h` on VPS | Clean Docker volumes/logs |

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

### Rollback a Deployment
If a new deployment causes issues:
```bash
# SSH into VPS
ssh root@136.243.71.213

# Go to the project directory
cd /path/to/treejar

# Roll back to previous commit
git log --oneline -5   # find the previous good commit
git reset --hard <commit-hash>
docker compose up -d --build
```

---

## 8. Contact for Support

- **Technical issues**: Contact the development team via Telegram.
- **Zoho/Wazzup issues**: Check credentials in `.env` and Zoho API console.
- **Weekly demo**: Fridays at 11:00 MSK, Zoom ID: 584 425 2807.
