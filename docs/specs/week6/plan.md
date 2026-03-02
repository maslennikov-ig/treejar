# Week 6 Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Context Enrichment (hybrid CRM caching), Personal Discounts based on Segment, Soft Escalation logic, and Automatic Follow-ups.

**Architecture:** Leverage Redis for fast customer context caching. Inject context via PydanticAI system prompt dependencies. Add an Escalate API and background cron job (ARQ) for follow-ups and CRM syncing. 

**Tech Stack:** FastAPI, PydanticAI, SQLAlchemy (asyncpg), ARQ, Redis, Pytest.

---

### Task 1: Context Enrichment Cache & Utilities

**Files:**
- Create: `src/core/cache.py`
- Test: `tests/test_core_cache.py`

**Step 1: Write the failing test**
```python
import pytest
from src.core.cache import get_cached_crm_profile, set_cached_crm_profile

@pytest.mark.asyncio
async def test_crm_profile_cache(redis_client):
    phone = "+971501234567"
    profile = {"Name": "Test", "Segment": "VIP"}
    
    # Should be empty initially
    assert await get_cached_crm_profile(redis_client, phone) is None
    
    # Should save and retrieve
    await set_cached_crm_profile(redis_client, phone, profile, ttl=3600)
    cached = await get_cached_crm_profile(redis_client, phone)
    assert cached == profile
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_core_cache.py -v`
Expected: FAIL with ModuleNotFoundError or AssertionError

**Step 3: Write minimal implementation**
```python
# src/core/cache.py
import json
from typing import Any

async def get_cached_crm_profile(redis_client: Any, phone: str) -> dict[str, Any] | None:
    data = await redis_client.get(f"crm_profile:{phone}")
    if data:
        return json.loads(data)
    return None

async def set_cached_crm_profile(redis_client: Any, phone: str, profile: dict[str, Any], ttl: int = 3600) -> None:
    await redis_client.set(f"crm_profile:{phone}", json.dumps(profile), ex=ttl)
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_core_cache.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add tests/test_core_cache.py src/core/cache.py
git commit -m "feat: add CRM profile redis caching utility"
```

---

### Task 2: Fetch CRM Profile in Message Pipeline

**Files:**
- Modify: `src/llm/engine.py:340-365`
- Test: `tests/test_services_chat.py` 

**Step 1: Write the failing test**
```python
# in tests/test_services_chat.py
# (Needs mocking ZohoCRMClient and redis)
```
*Note: We assume existing chat tests will be updated to mock the CRM fetching.*

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_services_chat.py -v`

**Step 3: Write minimal implementation**
Edit `src/llm/engine.py` in `process_message`:
```python
    # After loading Conversation, fetch CRM context
    crm_context = None
    if crm_client and conv.phone:
        from src.core.cache import get_cached_crm_profile, set_cached_crm_profile
        crm_context = await get_cached_crm_profile(redis, conv.phone)
        if not crm_context:
            contact = await crm_client.find_contact_by_phone(conv.phone)
            if contact:
                crm_context = {"Name": f"{contact.get('First_Name', '')} {contact.get('Last_Name', '')}", "Segment": contact.get('Segment', 'Unknown')}
                await set_cached_crm_profile(redis, conv.phone, crm_context)
            else:
                crm_context = {"Segment": "Unknown"}
                
    # Update SalesDeps to include crm_context
    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=embedding_engine,
        zoho_inventory=zoho_client,
        zoho_crm=crm_client,
        messaging_client=messaging_client,
        pii_map=pii_map,
        crm_context=crm_context # <-- ADD THIS TO SalesDeps dataclass
    )
```
Update `inject_system_prompt` to include `ctx.deps.crm_context` in the returned string.

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/llm/engine.py tests/test_services_chat.py
git commit -m "feat: inject cached CRM profile into LLM context"
```

---

### Task 3: Personal Pricing (Discounts) Logic

**Files:**
- Create: `src/core/discounts.py`
- Modify: `src/llm/engine.py` (update `get_stock` and `perform_search_products`)
- Test: `tests/test_core_discounts.py`

**Step 1: Write the failing test**
```python
import pytest
from src.core.discounts import apply_discount, get_discount_percentage

def test_get_discount_percentage():
    assert get_discount_percentage("Wholesale") == 15
    assert get_discount_percentage("Developer") == 5
    assert get_discount_percentage("Unknown") == 0

def test_apply_discount():
    assert apply_discount(100.0, "Wholesale") == 85.0
    assert apply_discount(100.0, "Unknown") == 100.0
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_core_discounts.py -v`

**Step 3: Write minimal implementation**
```python
# src/core/discounts.py
DISCOUNTS = {
    "Wholesale": 15,
    "Retail chain B2B": 15,
    "Horeca": 10,
    "Design Agency": 10,
    "Developer": 5
}

def get_discount_percentage(segment: str) -> int:
    return DISCOUNTS.get(segment, 0)

def apply_discount(price: float, segment: str) -> float:
    discount = get_discount_percentage(segment)
    return price * (1 - (discount / 100.0))
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_core_discounts.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/core/discounts.py tests/test_core_discounts.py
git commit -m "feat: add segment based discount resolver"
```

---

### Task 4: Integration of Discounts into LLM Tools

**Files:**
- Modify: `src/llm/engine.py` (search_products, get_stock tools)
- Test: `tests/test_services_tools.py`

**Step 1: Write the failing test**
*(Focus on checking if tools read `ctx.deps.crm_context["Segment"]` and apply the discount function to the returned price strings).*

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
In `src/llm/engine.py:perform_search_products`:
```python
from src.core.discounts import apply_discount
# ...
    segment = ctx.deps.crm_context.get("Segment", "Unknown") if ctx.deps.crm_context else "Unknown"
    for r in results.products:
        discounted_price = apply_discount(r.price, segment)
        desc = f"Name: {r.name_en}\nSKU: {r.sku}\nPrice: {discounted_price:.2f} {r.currency} (Your segment price)\nDescription: {r.description_en}"
        formatted_results.append(desc)
```
Update `get_stock` and `create_quotation` similarly to respect the calculated rate.

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/ -v`

**Step 5: Commit**
```bash
git add src/llm/engine.py
git commit -m "feat: apply segment discounts dynamically in LLM tools"
```

---

### Task 5: Escalation Model and Endpoints
*(Detailed implementation skipped here for brevity, to be executed by subagent)*

### Task 6: Soft Escalation LLM Triggers
*(Detailed implementation skipped here for brevity, to be executed by subagent)*

### Task 7: ARQ Follow-up Background Tasks
*(Detailed implementation skipped here for brevity, to be executed by subagent)*

---

### Task 8: LLM Models Admin DB Config

**Files:**
- Create: `src/models/system_config.py`
- Create: `alembic/versions/xxxx_system_config.py`
- Modify: `src/core/config.py` (or where models are accessed)
- Modify: `src/llm/engine.py` (Read config from DB instead of settings)
- Test: `tests/test_models_config.py`

**Step 1:** Write the failing test for `get_llm_config`.
**Step 2:** Run test to verify it fails.
**Step 3:** Write minimal implementation (SystemConfig model with key-value or specific columns like `main_model_name` and `fast_model_name`).
**Step 4:** Run test to verify it passes.
**Step 5:** Integrate into `engine.py` and run all tests.
