# Manager Guide: Noor AI Sales Bot

> **Version:** 1.1 | **Last updated:** September 2026

This guide is for sales managers at Treejar who work alongside the Noor AI bot. Noor handles initial customer inquiries in WhatsApp and automatically escalates conversations to you when human expertise is needed.

---

## Overview

**Noor** is an AI sales assistant that communicates with customers via WhatsApp. It:
- Greets customers and qualifies their needs
- Searches the product catalog and checks stock
- Generates commercial proposals (PDF quotations)
- Escalates to a human manager only when a critical situation requires one

Your role begins **after** Noor escalates — you take over the conversation in WhatsApp/Wazzup and close the deal.

---

## When Noor Transfers a Conversation to You

Noor will notify you via Telegram and pause the conversation only for these
customer-evidenced cases:

| Situation | Example |
|-----------|---------|
| Customer explicitly asks to speak with a person or requests a call | "Can I speak to a manager?" |
| Customer accepts a quotation that Noor has already sent; the acceptance is recorded for the current message | "I accept the quotation. Please proceed." |
| Customer reports an existing order, payment, refund, legal, or safety incident needing human action | "My order arrived damaged." |

A rare exception is uncertainty **after** an external quotation/order side effect:
Noor must stop rather than risk repeating that action. Ordinary sales questions,
large or B2B orders, custom requests, missing catalog details, frustration, and
questions about return/refund *policy* are not by themselves manager handoffs.
Noor should continue helping, clarify if needed, and offer to prepare a quotation.

---

## How to Receive Notifications

### Setup
1. Ensure you are added to the **Treejar Noor** Telegram group (ask your admin).
2. Notifications are sent automatically — no action needed on your part.

### What a Notification Looks Like
```
🚨 Escalation Alert

Phone: +97150***4567
Reason: Customer requested human
Conversation: [conversation-id]

A human manager has been notified and should review this conversation.
```

The phone number is **partially masked** for privacy. You'll see the full number in WhatsApp/Wazzup.

---

## How to Take Over a Conversation

1. **Open WhatsApp or Wazzup** — find the conversation using the customer's phone number from the Telegram alert.
2. **Read the conversation history** — Noor has already gathered key information (name, company, requirements).
3. **Send a warm handover message**, for example:
   > *"Hi [Name], I'm [Your Name] from Treejar. I've reviewed your conversation with our assistant and I'm happy to help you personally. How can I assist you today?"*
4. **Continue the sales process** — use the context Noor gathered (needs analysis, products discussed, budget clues).
5. **Update Zoho CRM** — log your touchpoints and update the deal stage.

### Best Practices
- **Never restart from zero** — Noor has already done the greeting and needs analysis. Build on it.
- **Acknowledge the bot** — customers appreciate transparency: *"Our AI assistant flagged this for personal attention."*
- **Be fast** — respond within 15 minutes of receiving the Telegram notification for best conversion.

---

## How to Return a Conversation to the Bot

In most cases, escalated conversations should be handled by you until closed. However, if a customer's issue is resolved and they have simple follow-up questions:

1. Ensure the conversation status is set to **resolved** in the admin panel.
2. Noor will automatically resume follow-up messages based on the configured schedule.
3. If unsure, contact your system administrator.

---

## Frequently Asked Questions

**Q: What if I miss a Telegram notification?**  
A: Check the Admin Panel at https://noor.starec.ai/admin/ → Escalations table. All pending escalations are listed there.

**Q: Can I see what Noor said before I took over?**  
A: Yes — the full conversation history is visible in WhatsApp/Wazzup and also in the Admin Panel (Conversations → Messages).

**Q: What does "escalation_status: pending" mean?**  
A: The bot has flagged the conversation but no manager has taken action yet. Please respond as soon as possible.

**Q: Who receives alerts?**
A: Noor notifies the general Telegram group; individual assignment is handled by the team leader.

**Q: Can the bot send messages while I'm handling a conversation?**  
A: No. Once escalated to `pending` or `in_progress`, the bot stops sending messages in that conversation.
