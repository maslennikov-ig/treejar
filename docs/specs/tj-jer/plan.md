# Integrate AI Studio Landing Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate the Vite-based React landing page into the existing FastAPI backend, serving it from the root `/` path.

**Architecture:** The landing page code will be moved to `frontend/landing`. The `Dockerfile` will be updated with a multi-stage build: first using Node to build the Vite app, then copying the `dist/` directory into the Python runtime image. FastAPI will be configured to serve these static files. Nginx will be updated to route `/` traffic to the FastAPI app instead of redirecting to `/admin/`.

**Tech Stack:** FastAPI, React, Vite, Docker, Nginx, Pytest.

---

### Task 1: Move Frontend Code & Update Dockerfile

**Files:**
- Create/Move: `frontend/landing/` (from `../../.tmp/aistudio`)
- Modify: `Dockerfile`
- Modify: `docker-compose.dev.yml` (to ensure it builds correctly)

**Step 1: Move the frontend code**
```bash
mkdir -p frontend
cp -r ../../.tmp/aistudio frontend/landing
rm -rf frontend/landing/node_modules
```

**Step 2: Update Dockerfile for Multi-stage Build**
Modify `Dockerfile` to add a node build stage at the top:
```dockerfile
# --- Node Build Stage ---
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend/landing
COPY frontend/landing/package*.json ./
RUN npm install
COPY frontend/landing/ ./
RUN npm run build
```
And in the final `app` stage, before the entrypoint:
```dockerfile
COPY --from=frontend-builder /app/frontend/landing/dist /app/frontend/landing/dist
```

**Step 3: Commit**
```bash
git add frontend/landing Dockerfile
git commit -m "build: add frontend build stage to Dockerfile"
```

---

### Task 2: Setup FastAPI SPA Routing & Tests

**Files:**
- Modify: `src/main.py`
- Modify: `tests/api/test_main.py` (or create if it doesn't exist)

**Step 1: Write the failing test**
Create or edit `tests/test_main.py` (or similar root test file):
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_landing_page_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/test_main.py -v`
Expected: FAIL (currently `/` might return 404 since Nginx handled the redirect, or FastAPI has no route for `/`).

**Step 3: Write minimal implementation in `src/main.py`**
At the bottom of `src/main.py`, before `app = create_app()`:

```python
    import os
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Ensure the directory exists so FastAPI doesn't crash on startup during local dev
    os.makedirs("frontend/landing/dist", exist_ok=True)
    if not os.path.exists("frontend/landing/dist/index.html"):
        with open("frontend/landing/dist/index.html", "w") as f:
            f.write("<html><body>Mock Index</body></html>")

    app.mount("/assets", StaticFiles(directory="frontend/landing/dist/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        dist_dir = "frontend/landing/dist"
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add src/main.py tests/test_main.py
git commit -m "feat: serve landing page SPA from root route"
```

---

### Task 3: Update Nginx Configuration

**Files:**
- Modify: `nginx/conf.d/default.conf`

**Step 1: Write the failing behavior (mental check)**
Currently Nginx redirects `/` to `/admin/`. We need it to pass `/` to the app.

**Step 2: Write implementation**
In `nginx/conf.d/default.conf`:
Replace:
```nginx
    location = / {
        return 301 /admin/;
    }
```
With:
```nginx
    location / {
        proxy_pass http://app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
```
*(Make sure to keep the `/api/`, `/docs`, `/admin/` location blocks intact above this catch-all).*

**Step 3: Commit**
```bash
git add nginx/conf.d/default.conf
git commit -m "chore: update nginx to proxy root to fastapi app"
```

---

### Task 4: Verify Integration Locally

**Step 1: Build and run the Dev container**
Run: `docker compose -f docker-compose.dev.yml up --build -d`

**Step 2: Curl the endpoints**
Run: `curl -I http://localhost:8001/`
Expected: HTTP/1.1 200 OK (and not a 301 redirect)

Run: `curl -I http://localhost:8001/admin/`
Expected: HTTP/1.1 200 OK

**Step 3: Cleanup temporary directory**
Run: `rm -rf ../../.tmp/aistudio`

**Step 4: Commit**
```bash
git add ../../.tmp/aistudio (as a deletion if it was tracked, though likely it's in .gitignore)
git commit -m "chore: remove temporary aistudio prototype"
```
