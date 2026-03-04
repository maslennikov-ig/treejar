# Feature: Integrate AI Studio Landing Page (tj-jer)

## Background
The project currently has a Vite-based React landing page prototype located in `.tmp/aistudio`. We need to integrate this landing page into the main FastAPI application so that it is served from the root path (`/`) without requiring a separate web server in production. 

## Requirements
1. The landing page code should be moved from `.tmp/aistudio` to a permanent location within the project, e.g., `frontend/` or `client/`.
2. The UI must be refined according to the user's requested changes:
   - Max width up to 1440px.
   - Replace "Start for free" with "Войти".
   - Remove "Watch Demo".
   - Add developer credit in footer.
   - Use correct local logo.
   *(Note: These UI changes were already applied in the `.tmp/aistudio` prototype during Phase 1.5, so we just need to copy the updated files).*
3. The Dockerfile must be updated to build the Vite app using Node.js in an intermediate stage and copy the resulting static files (`dist/`) into the final Python image.
4. FastAPI application (`main.py` or equivalent routing file) must be updated to serve these static files at the `/` route using `StaticFiles`, with a fallback to `index.html` for client-side routing.
5. Nginx configuration (`nginx/conf.d/default.conf`) must be updated to stop redirecting `/` to `/admin/` and instead pass `/` to the FastAPI app.
6. The `.tmp/aistudio` directory must be permanently deleted.
7. Following TDD, appropriate tests must verify that the root endpoint (`/`) returns the HTML content of the landing page.

## Acceptance Criteria
- `docker compose -f docker-compose.dev.yml up --build` successfully builds the image containing both Python and Node/Vite build steps.
- Accessing `http://localhost:8001/` returns the React landing page.
- Accessing `http://localhost:8001/admin/` returns the SQLAdmin panel.
- Accessing `http://localhost:8001/api/docs` returns the FastAPI Swagger UI.
- `make test` or `pytest` passes all existing and new tests.
