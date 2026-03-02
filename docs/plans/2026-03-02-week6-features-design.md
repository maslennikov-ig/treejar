# Design Document: Week 6 Features
**Date:** 2026-03-02
**Topic:** Context Enrichment, Personal Discounts, Escalation & Follow-ups

## 1. Context Enrichment (Hybrid Approach)
**Goal:** Empower the AI agent with the client's CRM history before initiating a dialogue, but keep the solution scalable.
- **Mechanism:** When a new user message arrives, the system queries Zoho CRM for the `Phone` number if the `Conversation` indicates a known user but lacks cached context.
- **Caching:** The CRM response (Name, Segment, Orders) is serialized and stored in a short-lived cache (e.g., Redis TTL 1-2 hours) and injected dynamically into the `system_prompt`.
- **Real-time Sync:** The agent retains the existing `lookup_customer` Tool, enabling it to pull the absolute latest information mid-conversation if requested.

## 2. Personal Pricing & Discounts (Config-driven)
**Goal:** Reward returning/VIP clients and B2B segments with automatic percentage discounts.
- **Mechanism:** A static, configurable dictionary maps the 9 Zoho CRM Segments to their respective discount percentages (e.g., `{"Wholesale": 15, "Horeca": 10}`).
- **Integration:** The `get_stock` and `search_products` LLM Tools (and the quotation generator) will intercept the CRM-resolved Segment for the active conversation and calculate the discounted price before presenting it to the LLM.
- **Future-proofing:** This dictionary will be transitioned to the database (Admin Panel) in Week 7.

## 3. Manager Escalation (Soft Escalation via LLM Classifier)
**Goal:** Hand over conversations to human managers based on 18 specific triggers seamlessly.
- **Mechanism:** We employ an LLM-based classifier during the message processing pipeline.
- **Flow:** 
  1. The fast Haiku model parses the user intent and checks against the list of 18 triggers (e.g., "Customer requests human", "B2B client", "Complaining", "Requests drawings").
  2. If a trigger is hit, the system transitions the `Conversation` database model to an `Escalated` state.
  3. A notification (containing the chat history excerpt) is sent to the sales team via Telegram / Wazzup API.
  4. "Soft Escalation" means the bot continues to chat normally but explicitly notifies the user: "I've cc'd my human colleague who will join us shortly."

## 4. Automatic 24-hour Follow-ups (LLM-driven)
**Goal:** Restart stalled conversations efficiently without relying on paid HSM templates.
- **Constraint check:** The Wazzup "Max" tier doesn't enforce the strict Meta 24-hour HSM barrier, allowing dynamic text messages anytime.
- **Mechanism:** A scheduled ARQ/Cron background job runs every hour.
- **Flow:**
  1. It queries the DB for active conversations where `last_message_at` matches the follow-up threshold (24 hours, 3 days, 7 days).
  2. It passes the conversation context to the LLM with a specific generation prompt: "Draft a polite follow-up acknowledging the previous quotes/discussion".
  3. The LLM generates the customized text, and it's sent natively via `messaging_client.send_text`.
