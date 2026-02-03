---
name: generate-estimate
description: Generate commercial proposals (estimates) with pricing packages, benefits, risks, and timeline. Flexible skill that adapts to any IT project type.
allowed-tools: Read, WebSearch
---

# Generate Estimate

Generate structured commercial proposals for IT projects. The skill provides a framework — the model thinks about specifics (team, benefits, risks) for each unique project.

## When to Use

- Creating commercial proposals for client projects
- Generating estimates for any IT project (web, mobile, AI, integrations, etc.)
- Building multi-package pricing structures
- Documenting project scope with timeline

## Core Principle

**DO NOT use rigid templates.** Each project is unique. The model should:
- Analyze the project requirements
- Think about what team composition fits THIS project
- Generate benefits relevant to THIS client's business
- Identify risks specific to THIS tech stack and integrations

## Instructions

### Step 1: Understand the Project

Gather from user:
- Project name and description
- Target audience / client business
- Key features and integrations
- Budget constraints (if any)

### Step 2: Design Packages

Create 2-4 pricing packages (e.g., MVP → Business → Enterprise):
- Each package builds on the previous
- Define modules with hour estimates
- Think: what makes sense for THIS project?

### Step 3: Calculate Costs

For each package:
- Sum module hours
- Apply hourly rate (ask user or use default ~1500 ₽/h)
- Estimate timeline based on team size

### Step 4: Generate Business Benefits

**Think fresh for each project.** Consider:
- What problems does this solve for the client?
- What's the ROI / payback potential?
- How does each package level add value?
- What competitive advantages does it provide?

Write 4-5 compelling benefits per package in business language.

### Step 5: Compose the Team

**Think about what THIS project needs:**
- What roles are required? (Backend, Frontend, DevOps, QA, PM, Designer, etc.)
- What seniority levels?
- How many hours per role?

Don't use a fixed template — a simple API integration doesn't need the same team as a complex AI platform.

### Step 6: Identify Risks

**Analyze THIS project's specific risks:**
- What integrations might be problematic?
- What are the technical unknowns?
- What depends on the client?
- What could affect timeline?

Include mitigation strategies for each risk.

### Step 7: Add Operating Costs (if applicable)

For projects with ongoing costs (LLM APIs, hosting, SaaS):
- Load current pricing from `data/llm-models.json`
- Calculate monthly costs for different usage scenarios
- Provide recommendations

### Step 8: Assemble Document

Generate markdown with sections:
1. Project overview
2. Packages with modules, hours, costs
3. Business benefits (per package)
4. Team composition
5. Comparison table
6. Operating costs (if applicable)
7. Risks and mitigation
8. Timeline
9. What's not included
10. Guarantees
11. Next steps

## Reference Data

### LLM Models (for AI projects)

Load from `data/llm-models.json` — contains current OpenRouter pricing for:
- DeepSeek V3.2 (recommended for cost efficiency)
- Gemini 3 Flash
- Kimi K2
- GPT-5.2 / GPT-5.2 mini
- Claude 4 Sonnet
- Xiaomi MiMo-V2-Flash (free tier available)

### Template

Use `templates/estimate.md` as a structural guide, but adapt freely.

## Output Format

Markdown document ready to send to client.

```json
{
  "success": true,
  "markdown": "# Commercial Proposal: ...",
  "metadata": {
    "packages": 3,
    "priceRange": {"min": 200000, "max": 600000, "currency": "₽"},
    "timeline": "6-12 weeks"
  }
}
```

## Examples

### Example 1: AI Sales Bot

**Input**: "AI bot for WhatsApp sales automation, furniture store, Arabic/English"

**Model thinks**:
- Team: Architect, Backend (LLM integration), DevOps
- Benefits: 24/7 availability, instant responses, multilingual support, CRM integration
- Risks: WhatsApp API changes, LLM quality for Arabic, voice message handling
- Packages: Basic (text only) → Business (voice + proposals) → Premium (analytics)

### Example 2: E-commerce Platform

**Input**: "Online store with AI recommendations, 10K products"

**Model thinks**:
- Team: Backend, Frontend, DevOps, QA, Designer
- Benefits: Increased average order, personalization, inventory optimization
- Risks: Data migration, recommendation quality, performance at scale
- Packages: MVP (catalog + cart) → Growth (recommendations) → Enterprise (full analytics)

### Example 3: Simple API Integration

**Input**: "Connect CRM with accounting system"

**Model thinks**:
- Team: Backend developer only, maybe part-time QA
- Benefits: No manual data entry, real-time sync, error reduction
- Risks: API limitations, data format mismatches
- Packages: Maybe just one package — it's a simple project

## Validation

- [ ] Project understood correctly
- [ ] Packages make sense for this project type
- [ ] Benefits are specific to client's business (not generic)
- [ ] Team composition fits the project scope
- [ ] Risks are relevant to the tech stack
- [ ] Calculations are correct
- [ ] Document is complete and professional

## Anti-Patterns

**DON'T:**
- Copy-paste same benefits for every project
- Use identical team for all projects
- List generic risks that don't apply
- Over-engineer simple projects
- Under-scope complex projects

**DO:**
- Think fresh about each project
- Adapt structure to project complexity
- Write benefits in client's business language
- Be honest about risks and uncertainties
