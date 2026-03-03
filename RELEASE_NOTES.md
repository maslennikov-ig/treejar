# Release Notes

User-facing release notes.

## v0.2.10

_Released on 2026-03-03_

---

_This release was automatically generated from 2 commits._

## v0.2.10

_Released on 2026-03-03_

---

_This release was automatically generated from 1 commits._

## v0.2.9

_Released on 2026-03-03_

### ✨ New Features

- **admin**: Implement metrics and settings, fix code review bugs
- **admin**: Implement SQLAdmin views and authentication for Phase 1
- Add SystemConfig DB mechanism for configurable LLMs
- **followup**: Implement ARQ cron job for automatic follow-ups
- **escalation**: Implement llm-based soft escalation triggers
- Add soft escalation model and endpoints (Task 5)
- Apply CRM segment discounts in LLM tools
- Add segment based discount resolver
- Inject cached CRM profile into LLM context
- Add CRM profile redis caching utility
- Merge Week 5 quotation generation (PDF, Jinja2, create_quotation LLM tool, sale orders)
- Implement create_sale_order with proper signature in ZohoInventoryClient
- Implement bulk stock check API endpoint
- Add create_quotation LLM tool with pdf generation and messaging integration
- Add create draft sale order to inventory provider
- Add jinja2 quotation template and styles
- Add async pdf generator service using weasyprint
- **crm**: Implement zoho crm client, api endpoints, and llm tools

### 🔧 Improvements

- **admin**: Convert SystemConfig to JSONB, aggregate metrics via ARQ cron

### 🐛 Bug Fixes

- **admin**: Secure password comparison and fix deptry config
- Resolve all ruff lint (139 errors) and mypy type errors (9 errors)
- Update tests for merged quotation branch (messaging_client, pdf mock, tuple unpack)
- Ruff lint fixes, mypy type fix, restore and add edge-case tests
- **crm**: Use object format for Deal Contact_Name lookup field per v8 API
- Resolve mypy and ruff lint issues in test files

---

_This release was automatically generated from 44 commits._

## v0.2.8

_Released on 2026-02-25_

### ✨ New Features

- Implement Week 2 — Zoho Inventory sync, RAG pipeline, embeddings

### 🐛 Bug Fixes

- Complete remaining code review fixes + expand test coverage to 53 tests
- Apply code review fixes — async embeddings, client lifecycle, null filters

---

_Generated from 6 commits._

## v0.2.7

_Released on 2026-02-23_

### ✨ New Features

- Switch LLM to DeepSeek V3.2, add model rationale for client

### 🐛 Bug Fixes

- Zoho EU URLs in .env.example, add missing config vars

---

_Generated from 3 commits._

## v0.2.6

_Released on 2026-02-23_

### ✨ New Features

- Project kickoff — full skeleton with all models, schemas, API stubs

### 🔒 Security

- Remove sensitive files from tracking, update client guide

### 🐛 Bug Fixes

- **Documentation**: премия 100K единоразово при финальной сдаче

---

_Generated from 10 commits._
