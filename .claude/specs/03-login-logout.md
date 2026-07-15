# Spec: Login and Logout

## Overview
This feature implements real session-based authentication for Spendly. Currently `GET /login` only renders a static form and `GET /logout` returns a placeholder string — neither actually authenticates a user. This step wires up `POST /login` to verify credentials against the `users` table and start a Flask session, and implements `GET /logout` to end that session. It also updates the shared navbar in `base.html` to reflect whether a visitor is signed in. This builds directly on registration (Step 2) and unblocks the profile page (Step 4) and any future route that needs to know "who is the current user."

## Depends on
- Database setup (`users` table with `name`, `email`, `password_hash` columns) — `database/db.py`
- Registration (Step 2) — users must be able to register before they can log in

## Routes
- `POST /login` — validate submitted email/password against the `users` table, verify the password hash, start a session on success, redirect to `/` on success or re-render `login.html` with an error on failure — public
- `GET /login` — already implemented, no behavior change; will now share a route function with the POST handler
- `GET /logout` — clear the session and redirect to `/` — logged-in (safe to call when logged out too; just redirects)

## Database changes
No new tables or columns. The `users` table already exists in `database/db.py`.

New helper function needed in `database/db.py` (no DB logic in `app.py`):
- `get_user_by_id(user_id)` — used by a context processor to look up the current user's name for the navbar

`get_user_by_email(email)` already exists (added in Step 2) and will be reused to look up the user during login.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change the hardcoded `action="/login"` to `action="{{ url_for('login') }}"` to comply with the no-hardcoded-URLs rule
  - `templates/base.html` — nav links become conditional: when a session is active, show the user's name and a "Sign out" link (`url_for('logout')`); when not, show the existing "Sign in" / "Get started" links

## Files to change
- `app.py` —
  - set `app.secret_key` (required for Flask sessions to work)
  - update the `login()` view to accept `GET` and `POST`; on `POST`, validate input, fetch the user via `get_user_by_email()`, verify the password with `check_password_hash`, store `user_id` in `session` on success, redirect to `/`, or re-render `login.html` with an error
  - implement `logout()` to call `session.clear()` and redirect to `/`
  - add a context processor (or `before_request`) that loads the current user via `get_user_by_id(session.get("user_id"))` and makes it available to all templates
- `database/db.py` — add `get_user_by_id(user_id)`
- `templates/login.html` — fix hardcoded form action to use `url_for()`
- `templates/base.html` — conditional nav based on logged-in state

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` already provides `check_password_hash`, and Flask's built-in `session` requires no new package.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`check_password_hash` for verification)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic inline in `app.py` — it belongs in `database/db.py`
- No hardcoded URLs in templates — always use `url_for()`
- Do not implement `/profile` (Step 4) or any other stub route beyond `/login` and `/logout`

## Definition of done
- [ ] `GET /login` still renders the form correctly
- [ ] Submitting valid credentials on `POST /login` logs the user in (session cookie set) and redirects to `/`
- [ ] Submitting an unknown email or wrong password re-renders `login.html` with an error and does not start a session
- [ ] Submitting with a missing/empty required field is rejected server-side and shows an error
- [ ] Visiting `GET /logout` while logged in clears the session and redirects to `/`
- [ ] Visiting `GET /logout` while logged out does not error — it just redirects to `/`
- [ ] Navbar shows "Sign in" / "Get started" when logged out, and the user's name / "Sign out" when logged in
- [ ] The login form's `action` attribute uses `url_for('login')`, not a hardcoded path
- [ ] No new pip packages were added to `requirements.txt`
