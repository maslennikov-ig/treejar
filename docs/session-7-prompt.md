# Prompt for the Next Session (Week 7: Admin Panel Development)

**Copy and paste the text below into your new AI context window:**

***

**Context:**
We are developing the **TreeJar AI Chatbot**, an AI-powered sales agent built with **FastAPI, PydanticAI, PostgreSQL, Redis, and ARQ**. It integrates deeply with **Wazzup (WhatsApp)** and **Zoho CRM/Inventory**.

**What has been done so far:**
We successfully implemented Weeks 1-6. The bot can retrieve products, generate semantic RAG answers, identify customer stages, quote prices, sync inventory, handle escalations (manager notifications), and run background automated follow-ups. We also implemented a dynamic `SystemConfig` in the database to manage LLM models without editing `.env`.  
The codebase currently has **147 passing tests (~90% coverage)**, with zero lint or type checking errors. The `main` branch is clean.

**Current Goal (Week 7: Admin Panel):**
We are starting **Week 7** which focuses on building an admin panel visualization layer directly over our existing database.
Our goals:
1. Integrate `sqladmin` (with SQLAlchemy) to provide a CRUD interface for:
   - Conversations & Messages
   - Product Catalog
   - Quotations & Deals
   - System Configurations (LLM parameters)
   - Prompt Management (managing system prompts from DB rather than hardcoded)
2. Add a `Metrics dashboard` summarizing tokens used, deals won, etc.

**Instructions for the AI:**
1. Please adopt the persona of an expert Lead Principal Engineer.
2. Read the project constitution rules to understand my strict workflow (`bd` issues, TDD, strict code quality). You must always verify before claiming success.
3. Review `docs/task-plan.md` to see the Week 7 overview.
4. Review the detailed specification and plan for Week 7 located in `docs/specs/week7/spec.md` and `docs/specs/week7/plan.md`. 
5. Start initiating the subagent workflow. Create a `bd` task for the first piece of the Admin panel implementation, use the `executing-plans` skill, write the tests (TDD), and implement the SQLAdmin integration.

Please confirm you understand the context and are ready to execute the first task of Week 7.
