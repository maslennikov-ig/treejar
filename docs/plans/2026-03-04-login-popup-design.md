# Login Popup Design

## Overview
The user requested a more integrated and premium login experience instead of simply redirecting to the `/admin/login` page. We will modify the frontend landing page to include a custom Login Popup (modal) that looks cohesive with the rest of the site. The Hero section will also be adjusted to emphasize the Login button.

## Selected Options
1. **Hero Button (Option B)**: The 2-column layout in the Hero section remains, but the "Войти" (Start / Login) button will be enlarged to fill the width (or be significantly more prominent) in the left text column, with heavier visual weight (shadows, gradients, hover effects).
2. **Login Process (Option A - Popup)**: A modal over the landing page with a glassmorphism backdrop. The form will submit the credentials.

## Technical Implementation Details

### 1. Frontend Modifications (`frontend/landing/src/App.tsx`)
- **Login Button Upgrade**: Increase padding, font size, and add a subtle glowing shadow and an animated hover effect (e.g., using Framer Motion) to the primary "Войти" button in the Hero section.
- **Login Modal Component**: 
  - Create a new `LoginModal` component using Framer Motion for smooth enter/exit animations.
  - The modal will have an `AnimatePresence` wrapper.
  - Background overlay: `bg-black/40 backdrop-blur-sm`.
  - Modal box: White background with rounded corners (`rounded-3xl`), matching the site's aesthetic.
  - Form Fields: Username and Password inputs with modern borders, icons (if applicable), and focus rings.
  - Submit Button: Reuses the brand orange color but features an active loading state.
  - Error Handling: Inline error message display (e.g., "Invalid username or password") if the login fails.

### 2. Login Flow integration with SQLAdmin
- Since `SQLAdmin` uses a traditional form submission to `/admin/login` and expects a `application/x-www-form-urlencoded` POST request, the frontend's login form will be structured as a standard HTML `<form>` that POSTs directly to `/admin/login`.
- Specifically, the form will act as follows:
  ```html
  <form method="POST" action="/admin/login">
    <input name="username" type="text" />
    <input name="password" type="password" />
    <button type="submit">Login</button>
  </form>
  ```
- This approach bypasses the need to write custom Fetch/XHR logic and CORS handling. The browser will handle the POST natively. Upon successful credentials, SQLAdmin's auth backend will set the `admin_session` cookie and issue a 302 Redirect to `/admin/`, transporting the user seamlessly into the admin panel.
- If the login fails, SQLAdmin natively redirects back to `/admin/login`. To improve UX, we can either accept this default fallback (the user sees the normal admin login page on error) OR we can use Javascript `fetch` with `redirect: 'manual'` or handle the response. Given the desire for a premium feel, doing a Fetch POST is better:
  - We use `fetch('/admin/login', { method: 'POST', body: new URLSearchParams(formData) })`.
  - Check `response.url` or `response.ok`. If the URL ends with `/admin/`, login was successful -> manually `window.location.href = '/admin/'`.
  - If it redirects to `/admin/login` or returns 400, show an error.

### 3. State Management
- `isLoginModalOpen` state added to `App.tsx`.
- The `handleLogin` function will toggle this state instead of setting `window.location.href`.

## Trade-offs
- Writing custom fetch logic for the login allows us to keep the user on the landing page if the password is wrong, showing a nice inline red error, which adheres to the premium UX requirement.

## Success Criteria
- The "Войти" button in the Hero section is larger and more prominent.
- Clicking "Войти" in the header or Hero opens the Popup.
- Successful login within the popup immediately redirects to `/admin/`.
- Failed login shows a unified error in the popup without a page refresh.
