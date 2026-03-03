# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.10] - 2026-03-03

### Other
- **release**: v0.2.10 (2ff3ef2)
- update project files (b56742e)


## [0.2.10] - 2026-03-03

### Other
- update project files (b56742e)


## [0.2.9] - 2026-03-03

### Added
- **admin**: implement metrics and settings, fix code review bugs (a4efd86)
- **admin**: implement SQLAdmin views and authentication for Phase 1 (ad5c157)
- Add SystemConfig DB mechanism for configurable LLMs (3d478df)
- **followup**: implement ARQ cron job for automatic follow-ups (6de33d5)
- **escalation**: implement llm-based soft escalation triggers (c1c099a)
- add soft escalation model and endpoints (Task 5) (2b38b26)
- apply CRM segment discounts in LLM tools (bb9a2ed)
- add segment based discount resolver (d94dcfb)
- inject cached CRM profile into LLM context (99fee49)
- add CRM profile redis caching utility (bd24d01)
- merge Week 5 quotation generation (PDF, Jinja2, create_quotation LLM tool, sale orders) (463fd92)
- implement create_sale_order with proper signature in ZohoInventoryClient (62d6a52)
- implement bulk stock check API endpoint (e283931)
- add create_quotation LLM tool with pdf generation and messaging integration (4a249f0)
- add create draft sale order to inventory provider (d21bbed)
- add jinja2 quotation template and styles (0a2d5c5)
- add async pdf generator service using weasyprint (62a533b)
- **crm**: implement zoho crm client, api endpoints, and llm tools (7814df1)

### Changed
- **admin**: convert SystemConfig to JSONB, aggregate metrics via ARQ cron (5e6df1a)

### Fixed
- **admin**: secure password comparison and fix deptry config (495396d)
- resolve all ruff lint (139 errors) and mypy type errors (9 errors) (e2d2c59)
- update tests for merged quotation branch (messaging_client, pdf mock, tuple unpack) (dafcb72)
- ruff lint fixes, mypy type fix, restore and add edge-case tests (78197a7)
- **crm**: use object format for Deal Contact_Name lookup field per v8 API (c3fe188)
- resolve mypy and ruff lint issues in test files (93a40f1)

### Other
- update docs (820ead4)
- add prompt for week 7 session (dc1c18f)
- restore [x] for Week 5 — code exists in feature/quotation-generation worktree (8eb50a2)
- correct false-positive [x] marks in Week 5 (not yet implemented) (6aee8f0)
- mark Week 4 CRM and Inventory tasks as completed (58f7c0f)
- add explicit tests for CRM/Inventory LLM tools (90e4e59)
- remove unused import in tests (6247ce6)
- add weasyprint and jinja2 dependencies (eec9b7c)
- ignore .worktrees directory (774393d)
- Fix LLM pricing comparison in progress report (55e9abf)
- Fix RAG and LLM verification scripts (cdc98f3)
- mark Phase 1a (Week 1-3) as completed and up progress stats (e6a8c47)
- **dev-guide**: explicitly document mandatory pre-push checks (d30a7dc)
- add deptry to dev dependencies and configure ignore rules (a4ffd91)
- add tests to reach 91% coverage (690c2c3)
- Add Supabase security and pricing arguments to client response (b86edf8)
- Push manual updates to client response file (ea45a50)
- Add Supabase vs PostgreSQL explanation to client response (c406397)
- Update documentation with new client infrastructure details (cdac7be)


## [0.2.8] - 2026-02-25

### Added
- implement Week 2 — Zoho Inventory sync, RAG pipeline, embeddings (170a1a2)

### Fixed
- complete remaining code review fixes + expand test coverage to 53 tests (820cc96)
- apply code review fixes — async embeddings, client lifecycle, null filters (d7ecf2a)

### Other
- **docs**: add 1 file(s),update 1 file(s),remove 1 file(s) (952b79d)
- add progress report for client (Week 1-2 summary) (7ad16b5)
- feat/rag: zoho inventory sync and postgres vector search (c94258b)


## [0.2.7] - 2026-02-23

### Added
- switch LLM to DeepSeek V3.2, add model rationale for client (7361c57)

### Fixed
- Zoho EU URLs in .env.example, add missing config vars (519cfdc)

### Other
- sync 5 knowledge docs from client repo, update task plan (3a92127)


## [0.2.6] - 2026-02-23

### Security
- remove sensitive files from tracking, update client guide (ac5adb0)

### Added
- project kickoff — full skeleton with all models, schemas, API stubs (4b3222a)

### Fixed
- **docs**: премия 100K единоразово при финальной сдаче (0707a34)

### Other
- **docs**: add 2 file(s) (2f84629)
- add option 2 for Supabase setup (share login, we configure) (dc5d8be)
- move task-plan.md to gitignore (internal doc) (0958ffd)
- add task plan with checkboxes + update client guide (d072a70)
- clean up repo — remove PDFs/CSV, update .gitignore, rewrite client guide (d28fd31)
- синхронизировать цены во всех документах (600K + 100K) (b2224bd)
- **noor**: обновить КП v4.0 + ответ заказчику (e8da672)

