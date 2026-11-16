# Spec: Date Filter for Profile Page

## Overview
Adds a date-range filter to the `/profile` page so users can narrow their summary stats, transaction list, and category breakdown to a chosen period. Step 4 built the profile UI and the follow-up commit wired it to real data, but everything is currently all-time. A filter bar (from/to date inputs plus quick presets such as "This month" and "Last 30 days") lets users see where their money went in a specific window. The filter is driven by GET query parameters so filtered views are bookmarkable and need no JavaScript.

## Depends on
- Step 1: Database setup (`expenses` table with `date` stored as `YYYY-MM-DD`)
- Step 2: Registration
- Step 3: Login + Logout (session-based auth)
- Step 4: Profile page (template, `get_summary_stats`, `get_recent_transactions`, `get_category_breakdown`)

## Routes
No new routes. `GET /profile` is extended to accept optional query parameters — logged-in only (unchanged):
- `date_from` — `YYYY-MM-DD`, inclusive lower bound
- `date_to` — `YYYY-MM-DD`, inclusive upper bound
- `preset` — optional, one of `this_month`, `last_30_days`, `this_year`, `all`; resolved server-side into `date_from`/`date_to`

Invalid or malformed dates are ignored (treated as no bound) and a flash-style inline message is shown. If `date_from` is later than `date_to`, show an inline error and fall back to the unfiltered view.

## Database changes
No database changes. The existing `expenses.date` column (TEXT, `YYYY-MM-DD`) sorts and compares correctly as a string, so `date >= ? AND date <= ?` works without schema changes or new indexes.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — add a filter bar (GET form with two `<input type="date">` fields, Apply and Clear controls, and preset links built with `url_for('profile', preset=...)`); show the active range as a label near the stats; empty-state text distinguishes "no transactions in this range" from "no transactions yet"; section title "Recent transactions" becomes "Transactions" when filtered

## Files to change
- `app.py` — `profile()` reads and validates `date_from`, `date_to`, `preset`; resolves presets; passes the range to the DB helpers; passes `filter` context (active values, error message) to the template
- `database/db.py` — add optional `date_from=None, date_to=None` parameters to `get_summary_stats`, `get_recent_transactions`, and `get_category_breakdown`; build the WHERE clause by appending fixed SQL fragments with `?` placeholders only when a bound is supplied
- `static/css/profile.css` — styles for the filter bar, preset chips, and error message
- `tests/test_profile.py` — add filter test cases (or add a new `tests/test_date_filter.py`)

## Files to create
- None (optionally `tests/test_date_filter.py`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — user-supplied dates must only reach SQL as `?` parameters; the WHERE clause may be assembled from fixed string fragments, never from request values
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`; the route only validates input, calls helpers, and renders
- Validate dates with `datetime.strptime(value, "%Y-%m-%d")` in the route; never pass unvalidated strings to the DB helpers
- Filters apply only to the logged-in user's expenses (`user_id = ?` always remains in the query)
- Use `url_for()` for all links, including presets — no hardcoded URLs
- Vanilla HTML form only; no JS required (any JS goes in `static/js/main.js`, vanilla)
- No inline `<style>` tags; keep the existing inline `width` on breakdown bars as-is, add no new inline styles
- Do not implement the add/edit/delete expense stubs
- Default behaviour with no query params must be identical to today (all-time, same 5 recent transactions)

## Definition of done
- [ ] `/profile` with no query params renders exactly as before (all-time stats, 5 recent transactions)
- [ ] `/profile?date_from=2026-11-01&date_to=2026-11-30` shows only expenses in that range in stats, transactions table, and category breakdown
- [ ] Both bounds are inclusive (an expense dated exactly on `date_from` or `date_to` appears)
- [ ] Only `date_from` set → expenses on/after that date; only `date_to` set → expenses on/before that date
- [ ] Filter inputs are pre-filled with the active values after submit
- [ ] Each preset link ("This month", "Last 30 days", "This year", "All time") shows the correct range
- [ ] A range with no expenses shows zero totals, "—" top category, and a "no transactions in this range" empty state
- [ ] `date_from` later than `date_to` shows an error message and the unfiltered view
- [ ] Malformed values (e.g. `date_from=abc`, `date_to=2026-13-45`) do not cause a 500 and are ignored
- [ ] A SQL-injection attempt in a date param (e.g. `date_from=' OR 1=1 --`) does not change results or error
- [ ] "Clear" resets to the unfiltered view
- [ ] One user never sees another user's expenses under any filter
- [ ] Visiting `/profile` while logged out still redirects to `/login`
- [ ] No hex colour values added to templates or `profile.css` — only CSS variables
- [ ] `pytest` passes, including new filter tests
