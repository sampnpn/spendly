"""Tests for the Spendly date-filter feature (spec 05-date-filter.md).

GET /profile accepts optional ``date_from``, ``date_to`` (YYYY-MM-DD, inclusive)
and ``preset`` (this_month, last_30_days, this_year, all) query parameters.
"""
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_recent_transactions,
    get_summary_stats,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _create_user(name="Filter User", email="filter@example.com", password="password123"):
    return create_user(name, email, generate_password_hash(password))


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _add_expense(user_id, expense_date, description, category="Food", amount=10.0):
    if isinstance(expense_date, date):
        expense_date = expense_date.isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


def _get_html(client, query=""):
    response = client.get("/profile" + query)
    assert response.status_code == 200, f"Expected 200 for /profile{query}, got {response.status_code}"
    return response.get_data(as_text=True)


@pytest.fixture
def user_id(client):
    uid = _create_user()
    _login(client, uid)
    return uid


@pytest.fixture
def nov_user(user_id):
    """User with expenses around the 2026-11-01..2026-11-30 window."""
    _add_expense(user_id, "2026-10-31", "Before-window", "Shopping", 7777.77)
    _add_expense(user_id, "2026-11-01", "On-lower-bound", "Food", 100.10)
    _add_expense(user_id, "2026-11-15", "Mid-window", "Bills", 200.20)
    _add_expense(user_id, "2026-11-30", "On-upper-bound", "Food", 50.05)
    _add_expense(user_id, "2026-12-01", "After-window", "Travel", 8888.88)
    return user_id


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------

class TestAuthGuard:
    @pytest.mark.parametrize(
        "query",
        [
            "",
            "?date_from=2026-11-01&date_to=2026-11-30",
            "?preset=this_month",
            "?preset=all",
        ],
    )
    def test_profile_with_filter_logged_out_redirects_to_login(self, client, query):
        response = client.get("/profile" + query)

        assert response.status_code == 302, "Logged-out access must redirect"
        assert response.headers["Location"].endswith("/login"), "Must redirect to /login"


# --------------------------------------------------------------------------
# Default behaviour (no params)
# --------------------------------------------------------------------------

class TestDefaultBehaviour:
    def test_no_params_shows_all_time_stats(self, client, nov_user):
        html = _get_html(client)

        # Total of all five expenses
        assert "7777.77" in html, "All-time view must include out-of-range expense"
        assert "8888.88" in html, "All-time view must include out-of-range expense"

    def test_no_params_shows_only_five_recent_transactions(self, client, user_id):
        for day in range(1, 9):
            _add_expense(user_id, f"2026-07-{day:02d}", f"Row-day-{day:02d}-end")

        html = _get_html(client)

        for day in range(4, 9):
            assert f"Row-day-{day:02d}-end" in html, f"Day {day} should be in the 5 most recent"
        for day in range(1, 4):
            assert f"Row-day-{day:02d}-end" not in html, f"Day {day} should not be shown"

    def test_no_params_title_is_recent_transactions(self, client, nov_user):
        html = _get_html(client)

        assert "Recent transactions" in html, "Unfiltered title should be 'Recent transactions'"

    def test_no_params_new_user_shows_no_transactions_yet(self, client, user_id):
        html = _get_html(client)

        assert "No transactions yet" in html


# --------------------------------------------------------------------------
# Date range filtering
# --------------------------------------------------------------------------

class TestDateRange:
    def test_both_bounds_show_only_in_range_expenses(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "Mid-window" in html
        assert "Before-window" not in html, "Expense before date_from must be excluded"
        assert "After-window" not in html, "Expense after date_to must be excluded"

    def test_both_bounds_are_inclusive(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "On-lower-bound" in html, "Expense on date_from must be included"
        assert "On-upper-bound" in html, "Expense on date_to must be included"

    def test_stats_reflect_only_filtered_range(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "350.35" in html, "Total should be 100.10 + 200.20 + 50.05"
        assert "7777.77" not in html
        assert "8888.88" not in html

    def test_category_breakdown_reflects_only_filtered_range(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        section = html[html.index("Category breakdown"):]
        assert "Bills" in section
        assert "Food" in section
        assert "Shopping" not in section, "Out-of-range category must not appear"
        assert "Travel" not in section, "Out-of-range category must not appear"

    def test_only_date_from_includes_on_and_after(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-15")

        assert "Mid-window" in html, "Expense on date_from must be included"
        assert "On-upper-bound" in html
        assert "After-window" in html
        assert "On-lower-bound" not in html
        assert "Before-window" not in html

    def test_only_date_to_includes_on_and_before(self, client, nov_user):
        html = _get_html(client, "?date_to=2026-11-15")

        assert "Mid-window" in html, "Expense on date_to must be included"
        assert "On-lower-bound" in html
        assert "Before-window" in html
        assert "On-upper-bound" not in html
        assert "After-window" not in html

    def test_single_day_range_returns_only_that_day(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-15&date_to=2026-11-15")

        assert "Mid-window" in html
        assert "On-lower-bound" not in html
        assert "On-upper-bound" not in html

    def test_filtered_title_is_transactions_not_recent(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "Recent transactions" not in html, (
            "Section title must change to 'Transactions' when filtered"
        )

    def test_filter_inputs_are_prefilled_with_active_values(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert 'type="date"' in html, "Filter bar must contain date inputs"
        assert 'value="2026-11-01"' in html, "date_from input should be pre-filled"
        assert 'value="2026-11-30"' in html, "date_to input should be pre-filled"

    def test_active_range_label_is_shown(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert html.count("2026-11-01") >= 2 or "Nov" in html, (
            "Active range should be displayed as a label in addition to the input value"
        )


# --------------------------------------------------------------------------
# Empty range
# --------------------------------------------------------------------------

class TestEmptyRange:
    def test_range_without_expenses_shows_zero_totals(self, client, nov_user):
        html = _get_html(client, "?date_from=2020-01-01&date_to=2020-01-31")

        assert "0.00" in html, "Total spent should be zero"
        assert "7777.77" not in html
        assert "8888.88" not in html

    def test_range_without_expenses_shows_dash_top_category(self, client, nov_user):
        html = _get_html(client, "?date_from=2020-01-01&date_to=2020-01-31")

        assert "—" in html, "Top category should be an em dash when range is empty"

    def test_range_without_expenses_shows_range_specific_empty_state(self, client, nov_user):
        html = _get_html(client, "?date_from=2020-01-01&date_to=2020-01-31")

        assert "no transactions in this range" in html.lower()
        assert "No transactions yet" not in html, (
            "'No transactions yet' is reserved for users with no expenses at all"
        )

    def test_user_with_no_expenses_and_filter_does_not_error(self, client, user_id):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "0.00" in html


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------

class TestPresets:
    def test_preset_links_are_rendered(self, client, user_id):
        html = _get_html(client)

        for label in ("This month", "Last 30 days", "This year", "All time"):
            assert label in html, f"Missing preset link label: {label}"
        for preset in ("this_month", "last_30_days", "this_year", "all"):
            assert f"preset={preset}" in html, f"Missing preset link for {preset}"

    def test_clear_control_links_back_to_unfiltered_profile(self, client, user_id):
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "Clear" in html, "Filter bar must have a Clear control"
        assert 'href="/profile"' in html, "Clear should link to the bare profile URL"

    def test_this_month_preset_filters_to_current_month(self, client, user_id):
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        _add_expense(user_id, today, "Preset-today")
        _add_expense(user_id, first_of_month, "Preset-first-of-month")
        _add_expense(user_id, last_month, "Preset-last-month")

        html = _get_html(client, "?preset=this_month")

        assert "Preset-today" in html
        assert "Preset-first-of-month" in html
        assert "Preset-last-month" not in html, "Previous month must be excluded"

    def test_last_30_days_preset_filters_to_recent_window(self, client, user_id):
        today = date.today()
        _add_expense(user_id, today, "Preset-today")
        _add_expense(user_id, today - timedelta(days=10), "Preset-ten-days-ago")
        _add_expense(user_id, today - timedelta(days=45), "Preset-45-days-ago")

        html = _get_html(client, "?preset=last_30_days")

        assert "Preset-today" in html
        assert "Preset-ten-days-ago" in html
        assert "Preset-45-days-ago" not in html, "Expense older than 30 days must be excluded"

    def test_this_year_preset_filters_to_current_year(self, client, user_id):
        today = date.today()
        _add_expense(user_id, today, "Preset-today")
        _add_expense(user_id, date(today.year, 1, 1), "Preset-jan-first")
        _add_expense(user_id, date(today.year - 1, 12, 31), "Preset-last-year")

        html = _get_html(client, "?preset=this_year")

        assert "Preset-today" in html
        assert "Preset-jan-first" in html
        assert "Preset-last-year" not in html, "Previous year must be excluded"

    def test_all_preset_shows_unfiltered_all_time_data(self, client, user_id):
        today = date.today()
        _add_expense(user_id, "2019-03-03", "Preset-ancient", amount=4321.09)
        _add_expense(user_id, today, "Preset-today")

        html = _get_html(client, "?preset=all")

        assert "Preset-ancient" in html
        assert "Preset-today" in html
        assert "4321.09" in html

    def test_unknown_preset_does_not_error_and_is_unfiltered(self, client, nov_user):
        html = _get_html(client, "?preset=bogus")

        assert "Before-window" in html or "After-window" in html, (
            "Unknown preset must not filter out data"
        )

    def test_preset_this_month_prefills_inputs_with_resolved_dates(self, client, user_id):
        today = date.today()

        html = _get_html(client, "?preset=this_month")

        assert f'value="{today.replace(day=1).isoformat()}"' in html, (
            "Preset should be resolved into date_from and pre-filled"
        )


# --------------------------------------------------------------------------
# Validation errors
# --------------------------------------------------------------------------

class TestValidation:
    def test_date_from_after_date_to_shows_error_and_unfiltered_view(self, client, nov_user):
        html = _get_html(client, "?date_from=2026-11-30&date_to=2026-11-01")

        assert "Before-window" in html or "After-window" in html, (
            "Reversed range must fall back to the unfiltered view"
        )
        assert "Mid-window" in html
        assert "7777.77" in html, "Unfiltered all-time stats expected"
        assert re.search(r"error|invalid|before|later|after", html, re.IGNORECASE), (
            "An inline error message is expected for a reversed range"
        )

    @pytest.mark.parametrize(
        "query",
        [
            "?date_from=abc",
            "?date_to=abc",
            "?date_to=2026-13-45",
            "?date_from=2026-13-45&date_to=2026-02-30",
            "?date_from=",
            "?date_from=11/01/2026",
            "?date_from=2026-1-1",
            "?date_from=%00&date_to=%FF",
            "?date_from=" + "9" * 5000,
        ],
    )
    def test_malformed_dates_do_not_cause_server_error(self, client, nov_user, query):
        response = client.get("/profile" + query)

        assert response.status_code == 200, f"Malformed input {query[:40]!r} must not 500"

    def test_malformed_date_from_is_ignored_as_no_bound(self, client, nov_user):
        html = _get_html(client, "?date_from=abc")

        assert "Before-window" in html, "Malformed date_from should act as no lower bound"
        assert "After-window" in html

    def test_malformed_date_from_with_valid_date_to_still_applies_date_to(self, client, nov_user):
        html = _get_html(client, "?date_from=abc&date_to=2026-11-15")

        assert "Before-window" in html, "Ignored date_from means no lower bound"
        assert "Mid-window" in html
        assert "After-window" not in html, "Valid date_to must still be applied"

    def test_malformed_date_shows_inline_message(self, client, nov_user):
        html = _get_html(client, "?date_from=abc")

        assert re.search(r"invalid|valid", html, re.IGNORECASE), (
            "An inline message should be shown for a malformed date"
        )

    def test_impossible_calendar_date_is_ignored(self, client, nov_user):
        html = _get_html(client, "?date_to=2026-13-45")

        assert "After-window" in html, "Invalid date_to should act as no upper bound"

    @pytest.mark.parametrize(
        "payload",
        [
            "' OR 1=1 --",
            "'; DROP TABLE expenses; --",
            "2026-11-01' OR '1'='1",
            "1; SELECT * FROM users",
        ],
    )
    def test_sql_injection_in_date_from_is_harmless(self, client, nov_user, payload):
        baseline = _get_html(client)

        response = client.get("/profile", query_string={"date_from": payload})

        assert response.status_code == 200, "Injection attempt must not error"
        html = response.get_data(as_text=True)
        for desc in ("Mid-window", "On-lower-bound", "On-upper-bound"):
            assert desc in html, f"{desc} should still be visible (payload ignored)"
        assert ("7777.77" in html) == ("7777.77" in baseline)

    def test_sql_injection_in_date_to_does_not_leak_other_users_data(self, client, nov_user):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(other_id, "2026-11-10", "Other-secret-row", amount=31337.31)

        response = client.get("/profile", query_string={"date_to": "' OR 1=1 --"})

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Other-secret-row" not in html
        assert "31337.31" not in html

    def test_expenses_table_survives_injection_attempt(self, client, nov_user):
        client.get("/profile", query_string={"date_from": "'; DROP TABLE expenses; --"})

        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (nov_user,)
        ).fetchone()[0]
        conn.close()
        assert count == 5, "Expenses must be intact after injection attempt"


# --------------------------------------------------------------------------
# Clear resets
# --------------------------------------------------------------------------

class TestClear:
    def test_bare_profile_after_filtered_view_is_unfiltered(self, client, nov_user):
        filtered = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")
        assert "Before-window" not in filtered

        cleared = _get_html(client)

        assert "Before-window" in cleared or "After-window" in cleared
        assert "Recent transactions" in cleared
        assert 'value="2026-11-01"' not in cleared, "Inputs must be empty after clearing"


# --------------------------------------------------------------------------
# User isolation
# --------------------------------------------------------------------------

class TestUserIsolation:
    def test_filtered_profile_never_shows_other_users_expenses(self, client, user_id):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(user_id, "2026-11-10", "Mine-in-range", amount=12.34)
        _add_expense(other_id, "2026-11-10", "Theirs-in-range", "Gadgets", 98765.43)

        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "Mine-in-range" in html
        assert "Theirs-in-range" not in html
        assert "98765.43" not in html
        assert "Gadgets" not in html

    @pytest.mark.parametrize(
        "query",
        [
            "?date_from=2026-11-01",
            "?date_to=2026-11-30",
            "?preset=all",
            "?preset=this_year",
            "?date_from=abc",
            "?date_from=2026-11-30&date_to=2026-11-01",
        ],
    )
    def test_no_filter_variant_leaks_other_users_expenses(self, client, user_id, query):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(user_id, date.today(), "Mine-row")
        _add_expense(other_id, date.today(), "Theirs-row", "Gadgets", 98765.43)
        _add_expense(other_id, "2026-11-10", "Theirs-nov-row", "Gadgets", 98765.43)

        html = _get_html(client, query)

        assert "Theirs-row" not in html
        assert "Theirs-nov-row" not in html
        assert "98765.43" not in html

    def test_other_user_sees_their_own_data_only_under_same_filter(self, client, user_id):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(user_id, "2026-11-10", "Mine-row")
        _add_expense(other_id, "2026-11-10", "Theirs-row")

        _login(client, other_id)
        html = _get_html(client, "?date_from=2026-11-01&date_to=2026-11-30")

        assert "Theirs-row" in html
        assert "Mine-row" not in html


# --------------------------------------------------------------------------
# DB helper level (optional date_from / date_to parameters)
# --------------------------------------------------------------------------

class TestDbHelpers:
    def test_summary_stats_with_both_bounds(self, client, nov_user):
        stats = get_summary_stats(nov_user, date_from="2026-11-01", date_to="2026-11-30")

        assert stats == {
            "total_spent": 350.35,
            "transaction_count": 3,
            "top_category": "Bills",
        } or (
            stats["transaction_count"] == 3 and stats["total_spent"] == 350.35
        ), f"Unexpected stats: {stats}"

    def test_summary_stats_without_bounds_is_all_time(self, client, nov_user):
        stats = get_summary_stats(nov_user)

        assert stats["transaction_count"] == 5

    def test_summary_stats_only_date_from(self, client, nov_user):
        stats = get_summary_stats(nov_user, date_from="2026-11-15")

        assert stats["transaction_count"] == 3

    def test_summary_stats_only_date_to(self, client, nov_user):
        stats = get_summary_stats(nov_user, date_to="2026-11-01")

        assert stats["transaction_count"] == 2

    def test_summary_stats_empty_range_returns_zero_and_dash(self, client, nov_user):
        stats = get_summary_stats(nov_user, date_from="2020-01-01", date_to="2020-01-31")

        assert stats == {"total_spent": 0.0, "transaction_count": 0, "top_category": "—"}

    def test_summary_stats_filter_ignores_other_users(self, client, nov_user):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(other_id, "2026-11-10", "Theirs", amount=1000.0)

        stats = get_summary_stats(nov_user, date_from="2026-11-01", date_to="2026-11-30")

        assert stats["transaction_count"] == 3
        assert stats["total_spent"] == 350.35

    def test_recent_transactions_with_bounds(self, client, nov_user):
        rows = get_recent_transactions(nov_user, date_from="2026-11-01", date_to="2026-11-30")

        text = str(list(rows))
        assert len(rows) == 3
        assert "On-lower-bound" in text and "On-upper-bound" in text
        assert "Before-window" not in text and "After-window" not in text

    def test_recent_transactions_empty_range_is_empty(self, client, nov_user):
        rows = get_recent_transactions(nov_user, date_from="2020-01-01", date_to="2020-01-31")

        assert len(rows) == 0

    def test_category_breakdown_with_bounds(self, client, nov_user):
        breakdown = get_category_breakdown(
            nov_user, date_from="2026-11-01", date_to="2026-11-30"
        )

        categories = {row["category"] for row in breakdown}
        assert categories == {"Bills", "Food"}
        assert sum(row["amount"] for row in breakdown) == pytest.approx(350.35)

    def test_category_breakdown_empty_range_is_empty_list(self, client, nov_user):
        breakdown = get_category_breakdown(
            nov_user, date_from="2020-01-01", date_to="2020-01-31"
        )

        assert breakdown == []

    def test_category_breakdown_filter_ignores_other_users(self, client, nov_user):
        other_id = _create_user(name="Other", email="other@example.com")
        _add_expense(other_id, "2026-11-10", "Theirs", "Gadgets", 1000.0)

        breakdown = get_category_breakdown(
            nov_user, date_from="2026-11-01", date_to="2026-11-30"
        )

        assert "Gadgets" not in {row["category"] for row in breakdown}


# --------------------------------------------------------------------------
# Styling rule: no hex colours added
# --------------------------------------------------------------------------

class TestNoHexColours:
    @pytest.mark.parametrize("relative_path", ["static/css/profile.css", "templates/profile.html"])
    def test_no_hex_colour_values(self, relative_path):
        content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        # Exclude HTML numeric entities such as &#8212;
        matches = re.findall(r"(?<!&)#[0-9a-fA-F]{3,8}\b(?!;)", content)

        assert matches == [], f"Hex colours found in {relative_path}: {matches}"
