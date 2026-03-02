# Specification: Week 6 (Escalation & Personal Pricing)

## 1. Context Enrichment
- **Requirement:** Inject the customer's purchase history and CRM profile into the LLM context.
- **Solution (Hybrid):** 
  - On receiving a message, immediately fetch the CRM contact by `Phone` via `ZohoCRMClient.find_contact_by_phone()`.
  - Also fetch their closed-won Deals via CRM (or use `Segments`).
  - Serialize this explicitly into a string (e.g. `[CRM PROFILE: Name, Segment, Recent Purchases]`) and prepend it to the LLM's `system_prompt` or user message context.
  - Cache this profile in Redis (`ttl=3600`) keyed by `phone` to minimize CRM API calls.

## 2. Personal Pricing & Discounts
- **Requirement:** Apply percentage discounts based on the CRM `Segment` field.
- **Solution:**
  - Create `src/core/discounts.py` mapping: 
    - `Wholesale`: 15%
    - `Retail chain B2B`: 15%
    - `Horeca`: 10%
    - `Design Agency`: 10%
    - `Developer`: 5%
    - (Others: 0%)
  - When the LLM tools `get_stock`, `search_products`, or `create_quotation` are called, they must retrieve the current user's CRM segment (from the Conversation or the Redis cache) and apply the discount to the `price` / `rate` before responding to the LLM or generating the PDF.

## 3. Manager Escalation (Soft Escalation)
- **Requirement:** Hand over the chat to a human based on 18 triggers while keeping the bot alive but indicating a human is joined.
- **Solution:**
  - Update `Conversation` model: add `escalation_status` enum (`none`, `pending`, `resolved`).
  - Create a new API router/endpoint: `POST /api/v1/conversations/{id}/escalate` for manual actions (like from the admin panel).
  - Modify `src/llm/engine.py`: Integrate an escalation evaluation prompt into the fast-extraction Haiku model (or as an early step in processing). If the 18 specific triggers (B2B, negativity, >10k AED, etc.) match, shift `escalation_status` to `pending`.
  - Notification logic: Create `src/integrations/notifications/` with a Telegram or Wazzup simple push to the manager group containing the last 5 messages and the escalation reason.

## 4. Automatic Follow-ups
- **Requirement:** Send follow-up messages after 24h, 3d, 7d of inactivity.
- **Solution:**
  - Create an ARQ Cron job `src/worker/cron.py` (or similar) that runs hourly.
  - Query `Conversation` for `last_message_at` exactly matching thresholds (within a 1-hour window).
  - Extract the last 5 messages. Call the `sales_agent` with a system override: "Draft a polite follow-up acknowledging the previous quotes/discussion. Make it a single short paragraph."
  - Send the generated text via `messaging_client.send_text`.
