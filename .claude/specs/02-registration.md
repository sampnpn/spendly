# Spec: Registration

## Overview
This feature implements real user registration for Spendly. Currently `GET /register` only renders a static form — submitting it does nothing. This step wires the form up to actually create a user: validating input, hashing the password, checking for duplicate emails, and persisting the new user to the `users` table. This is the first step where the app writes user-provided data to the database, and it unblocks login (Step 3) and everything downstream that depends on an authenticated user existing.

## Depends on
- Database setup (`users` table with `name`, `email`, `password_hash`, `created_at` columns already created in `database/db.py`).

## Routes
- `POST /register` — validate submitted name/email/password, hash the password, create the user, redirect to `/login` on success or re-render the form with an error on failure — public
- `GET /register` — already implemented, no behavior change; will now share a route function with the POST handler

## Database changes
No new tables or columns. The `users` table already exists in `database/db.py` with the required columns (`name`, `email`, `password_hash`, `created_at`).

New helper functions needed in `database/db.py` (no DB logic in `app.py`):
- `create_user(name, email, password_hash)` — inserts a new user, returns the new user id
- `get_user_by_email(email)` — used to check for duplicate emails before insert

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — change the hardcoded `action="/register"` to `action="{{ url_for('register') }}"` to comply with the no-hardcoded-URLs rule; the existing `{% if error %}` block already renders validation/duplicate-email errors, no markup changes needed there

## Files to change
- `app.py` — update the `register()` view to accept `GET` and `POST`, validate form input, call the new `database/db.py` helpers, hash the password with werkzeug, and redirect to `/login` on success
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — fix hardcoded form action to use `url_for()`

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` is already imported in `database/db.py` and used for password hashing.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic inline in `app.py` — it belongs in `database/db.py`
- No hardcoded URLs in templates — always use `url_for()`

## Definition of done
- [ ] `GET /register` still renders the form correctly
- [ ] Submitting the form with valid name, email, and password creates a new row in `users` with the password stored as a werkzeug hash (not plaintext)
- [ ] Submitting an email that already exists re-renders `register.html` with an error message and does not create a duplicate row
- [ ] Submitting with a missing/empty required field is rejected server-side (not just relying on HTML5 `required`) and shows an error
- [ ] On successful registration, the user is redirected to `/login`
- [ ] The form's `action` attribute uses `url_for('register')`, not a hardcoded path
- [ ] No new pip packages were added to `requirements.txt`
