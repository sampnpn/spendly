import re
from datetime import date, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import _resolve_date_filter
from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_recent_transactions,
    get_summary_stats,
)

ROOT = Path(__file__).resolve().parent.parent

# (date, category, amount, description)
SEED = [
    ("2026-10-31", "Food", 10.00, "oct-last"),
    ("2026-11-01", "Bills", 20.00, "nov-first"),
    ("2026-11-15", "Food", 30.00, "nov-mid"),
    ("2026-11-30", "Health", 40.00, "nov-last"),
    ("2026-12-01", "Shopping", 50.00, "dec-first"),
]


def _create_user(email="test@example.com"):
    return create_user("Test User", email, generate_password_hash("password123"))


def _add(user_id, rows):
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, amount, category, d, desc) for d, category, amount, desc in rows],
    )
    conn.commit()
    conn.close()


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _seeded(client):
    user_id = _create_user()
    _add(user_id, SEED)
    _login(client, user_id)
    return user_id


def _get(client, **params):
    return client.get("/profile", query_string=params)


# ---------------------------------------------------------------- route

def test_logged_out_redirects_to_login(client):
    response = _get(client, date_from="2026-11-01")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_no_params_is_unfiltered_with_five_rows(client):
    user_id = _create_user()
    _add(user_id, SEED + [("2026-09-01", "Other", 1.00, "sep-extra")])
    _login(client, user_id)

    response = _get(client)

    assert response.status_code == 200
    assert b"Recent transactions" in response.data
    assert b"dec-first" in response.data
    assert b"sep-extra" not in response.data  # 6th row, beyond limit of 5
    assert b"151.00" in response.data


def test_range_filters_stats_table_and_breakdown(client):
    _seeded(client)

    response = _get(client, date_from="2026-11-01", date_to="2026-11-30")
    html = response.data

    assert response.status_code == 200
    assert b"nov-first" in html and b"nov-mid" in html and b"nov-last" in html
    assert b"oct-last" not in html and b"dec-first" not in html
    assert b"90.00" in html  # 20 + 30 + 40
    assert b"Shopping" not in html
    assert b">Transactions</h2>" in html


def test_bounds_are_inclusive(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-01", date_to="2026-11-30").data

    assert b"nov-first" in html  # exactly date_from
    assert b"nov-last" in html  # exactly date_to


def test_only_date_from(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-30").data

    assert b"nov-last" in html and b"dec-first" in html
    assert b"nov-mid" not in html


def test_only_date_to(client):
    _seeded(client)

    html = _get(client, date_to="2026-11-01").data

    assert b"oct-last" in html and b"nov-first" in html
    assert b"nov-mid" not in html


def test_filter_shows_all_rows_not_just_five(client):
    user_id = _create_user()
    _add(user_id, [("2026-11-%02d" % d, "Food", 1.00, "row-%02d" % d) for d in range(1, 9)])
    _login(client, user_id)

    html = _get(client, date_from="2026-11-01", date_to="2026-11-30").data

    for d in range(1, 9):
        assert b"row-%02d" % d in html


def test_inputs_are_prefilled(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-01", date_to="2026-11-30").data

    assert b'value="2026-11-01"' in html
    assert b'value="2026-11-30"' in html


def test_empty_range(client):
    _seeded(client)

    html = _get(client, date_from="2030-01-01", date_to="2030-01-31").data

    assert b"No transactions in this range" in html
    assert b"No expenses in this range." in html
    assert b"0.00" in html
    assert "—".encode() in html


def test_unfiltered_empty_state_unchanged(client):
    _login(client, _create_user())

    html = _get(client).data

    assert b"No transactions yet" in html
    assert b"No expenses yet." in html


def test_from_after_to_shows_error_and_unfiltered(client):
    _seeded(client)

    html = _get(client, date_from="2026-12-01", date_to="2026-11-01").data

    assert b"Start date must be on or before end date." in html
    assert b"dec-first" in html and b"oct-last" in html


def test_malformed_dates_do_not_error(client):
    _seeded(client)

    for params in (
        {"date_from": "abc"},
        {"date_to": "2026-13-45"},
        {"date_from": "2026-02-30"},
        {"date_from": "", "date_to": ""},
        {"preset": "bogus"},
    ):
        assert _get(client, **params).status_code == 200


def test_valid_bound_still_applies_when_other_invalid(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-30", date_to="abc").data

    assert b"Invalid date ignored." in html
    assert b"nov-last" in html and b"dec-first" in html
    assert b"nov-mid" not in html


def test_sql_injection_attempt_is_harmless(client):
    _seeded(client)

    response = _get(client, date_from="' OR 1=1 --")

    assert response.status_code == 200
    assert b"oct-last" in response.data  # unfiltered, nothing leaked or broken


def test_non_padded_date_is_normalized(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-1", date_to="2026-11-30").data

    assert b"nov-first" in html
    assert b"oct-last" not in html


def test_clear_link_points_to_plain_profile(client):
    _seeded(client)

    html = _get(client, date_from="2026-11-01").data

    assert b'href="/profile" class="btn-ghost"' in html


def test_preset_all_is_unfiltered(client):
    _seeded(client)

    html = _get(client, preset="all").data

    assert b"oct-last" in html and b"dec-first" in html


def test_preset_this_month_route(client):
    user_id = _create_user()
    today = date.today()
    first = today.replace(day=1)
    _add(user_id, [
        (today.isoformat(), "Food", 5.00, "today-row"),
        (first.isoformat(), "Food", 5.00, "first-row"),
        ((first - timedelta(days=1)).isoformat(), "Food", 5.00, "prev-month-row"),
    ])
    _login(client, user_id)

    html = _get(client, preset="this_month").data

    assert b"today-row" in html and b"first-row" in html
    assert b"prev-month-row" not in html
    assert b"is-active" in html


def test_preset_overrides_date_params(client):
    _seeded(client)

    html = _get(client, preset="all", date_from="2026-11-30").data

    assert b"oct-last" in html


def test_users_are_isolated(client):
    user_id = _seeded(client)
    other = _create_user("other@example.com")
    _add(other, [("2026-11-15", "Other", 999.00, "other-user-row")])

    html = _get(client, date_from="2026-11-01", date_to="2026-11-30").data

    assert b"other-user-row" not in html
    assert b"999.00" not in html
    assert get_summary_stats(user_id, "2026-11-01", "2026-11-30")["total_spent"] == 90.00


# ---------------------------------------------------------- resolver

def test_resolver_presets_with_fixed_today():
    today = date(2026, 11, 16)

    this_month = _resolve_date_filter({"preset": "this_month"}, today)
    assert (this_month["date_from"], this_month["date_to"]) == ("2026-11-01", "2026-11-16")

    last_30 = _resolve_date_filter({"preset": "last_30_days"}, today)
    assert (last_30["date_from"], last_30["date_to"]) == ("2026-10-18", "2026-11-16")

    this_year = _resolve_date_filter({"preset": "this_year"}, today)
    assert (this_year["date_from"], this_year["date_to"]) == ("2026-01-01", "2026-11-16")

    all_time = _resolve_date_filter({"preset": "all"}, today)
    assert all_time["date_from"] is None and all_time["date_to"] is None
    assert all_time["active"] is False


def test_resolver_ignores_unknown_preset():
    result = _resolve_date_filter({"preset": "bogus"}, date(2026, 11, 16))
    assert result["preset"] is None and result["active"] is False


# ----------------------------------------------------------- db helpers

def test_db_helpers_accept_date_range(client):
    user_id = _seeded(client)

    stats = get_summary_stats(user_id, "2026-11-01", "2026-11-30")
    assert stats["transaction_count"] == 3
    assert stats["top_category"] == "Food" or stats["top_category"] == "Health"
    assert stats["top_category"] == "Health"  # 40 > 30 > 20, all-time top would be Food/Shopping

    rows = get_recent_transactions(user_id, limit=None, date_from="2026-11-01", date_to="2026-11-30")
    assert [r["description"] for r in rows] == ["nov-last", "nov-mid", "nov-first"]

    breakdown = get_category_breakdown(user_id, "2026-11-01", "2026-11-30")
    assert {b["category"] for b in breakdown} == {"Health", "Food", "Bills"}


# --------------------------------------------------------------- styles

def test_no_hex_colours_added():
    for path in ("static/css/profile.css", "templates/profile.html"):
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", (ROOT / path).read_text()), path
