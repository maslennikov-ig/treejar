# Login Popup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the hero login button into a centered, prominent CTA that opens a premium glassmorphism popup modal for authentication, matching the site's styling.

**Architecture:** We will modify `App.tsx` to add a new `LoginModal` component using Framer Motion. The modal will contain a standard HTML form that POSTs credentials to `/admin/login`, allowing seamless integration with SQLAdmin's existing authentication backend.

**Tech Stack:** React, Tailwind CSS, Framer Motion, HTML Form Submission.

---

### Task 1: Create the Login Modal Component

**Files:**
- Modify: `frontend/landing/src/App.tsx`

**Step 1: Write the failing test**
Since there are no frontend unit tests configured in this Vite scaffold, our "failing test" will be running the build command to ensure TypeScript throws an error if we use undefined state, and then we will write the actual code. We'll rely on our existing backend tests `test_landing_page.py` for serving.

Run: `cd frontend/landing && npm run build`
Expected: PASS (Baseline check)

**Step 2: Write minimal implementation**
We will add the `LoginModal` component to `App.tsx`.
- Add state `isLoginModalOpen` to `App`.
- Create `LoginModal` component with `user`, `lock`, `x` icons.
- The `LoginModal` will render an `<form method="POST" action="/admin/login">`.
- It will have inputs for `username` and `password`.

**Step 3: Run test to verify it passes**
Run: `cd frontend/landing && npm run build`
Expected: PASS

**Step 4: Commit**
```bash
git add frontend/landing/src/App.tsx
git commit -m "feat(landing): add glassmorphism login modal component"
```

---

### Task 2: Update Hero Button & Header Button

**Files:**
- Modify: `frontend/landing/src/App.tsx`

**Step 1: Write the failing test**
Run: `cd frontend/landing && npm run build`

**Step 2: Write minimal implementation**
- Update `handleLogin` to `setIsLoginModalOpen(true)` instead of redirecting.
- In `Hero`, modify the layout:
  - Remove `max-w-2xl` from the text container and center the text (`text-center mx-auto`).
  - Make the "Войти" button significantly larger (`text-xl px-10 py-5`), centered, and add prominent glow (`shadow-brand-orange/50`).
  - Hide the abstract chat visualization (`hidden`) or place it below if it doesn't fit the centered layout well. Given the current design, completely centering the Hero and hiding the side graphic gives the cleanest login-focused look.

**Step 3: Run test to verify it passes**
Run: `cd frontend/landing && npm run build && cd ../.. && uv run pytest tests/test_landing_page.py`
Expected: PASS

**Step 4: Commit**
```bash
git add frontend/landing/src/App.tsx
git commit -m "style(landing): center hero layout and enlarge login button"
```
