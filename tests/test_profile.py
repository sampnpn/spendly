from werkzeug.security import generate_password_hash

from database.db import create_user, get_db, get_summary_stats


def _create_user(name="Test User", email="test@example.com", password="password123"):
    return create_user(name, email, generate_password_hash(password))


def _add_expenses(user_id, items):
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, '2026-07-01', 'test')",
        [(user_id, amount, category) for amount, category in items],
    )
    conn.commit()
    conn.close()


def test_profile_redirects_to_login_when_logged_out(client):
    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_returns_200_when_logged_in(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert response.status_code == 200


def test_profile_displays_user_info_card(client):
    user_id = _create_user(name="Sugam Rai", email="sugam@example.com")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Sugam Rai" in response.data
    assert b"sugam@example.com" in response.data
    assert b"SR" in response.data
    assert b"Member since" in response.data
    assert b"Nitish Sharma" not in response.data


def test_profile_displays_summary_stats(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    _add_expenses(user_id, [(10.50, "Food"), (5.25, "Food"), (40.00, "Bills")])

    response = client.get("/profile")

    assert b"Total spent" in response.data
    assert b"Transactions" in response.data
    assert b"Top category" in response.data

    stats = get_summary_stats(user_id)
    assert stats == {"total_spent": 55.75, "transaction_count": 3, "top_category": "Bills"}
    assert b"55.75" in response.data
    assert b"270.95" not in response.data


def test_summary_stats_ignores_other_users_expenses(client):
    user_id = _create_user()
    other_id = _create_user(name="Other", email="other@example.com")
    _add_expenses(user_id, [(10.00, "Food")])
    _add_expenses(other_id, [(500.00, "Shopping"), (20.00, "Shopping")])

    stats = get_summary_stats(user_id)

    assert stats == {"total_spent": 10.0, "transaction_count": 1, "top_category": "Food"}


def test_summary_stats_empty_user(client):
    user_id = _create_user()

    stats = get_summary_stats(user_id)

    assert stats == {"total_spent": 0.0, "transaction_count": 0, "top_category": "—"}


def _add_expense(user_id, expense_date, description, category="Food", amount=10.0):
    from database.db import get_db

    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


def test_profile_displays_transaction_history_rows(client):
    user_id = _create_user()
    other_id = _create_user(email="other@example.com")
    for day in range(1, 8):
        _add_expense(user_id, f"2026-07-{day:02d}", f"Item day {day}", amount=day)
    _add_expense(other_id, "2026-07-30", "Other user secret")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    html = client.get("/profile").get_data(as_text=True)

    for day in range(3, 8):
        assert f"Item day {day}" in html
    assert "Item day 2" not in html
    assert "Item day 1<" not in html
    assert "Other user secret" not in html
    assert html.index("Item day 7") < html.index("Item day 6") < html.index("Item day 3")
    assert "No transactions yet" not in html


def test_profile_transactions_empty_state(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"No transactions yet" in response.data


def test_profile_displays_category_breakdown(client):
    from database.db import get_category_breakdown, get_db

    user_id = _create_user()
    other_id = _create_user(email="other@example.com")
    conn = get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 30.00, "Food", "2026-07-01", "a"),
            (user_id, 10.00, "Food", "2026-07-02", "b"),
            (user_id, 50.00, "Bills", "2026-07-03", "c"),
            (user_id, 10.00, "Transport", "2026-07-04", "d"),
            (other_id, 999.00, "Shopping", "2026-07-05", "x"),
        ],
    )
    conn.commit()
    conn.close()

    assert get_category_breakdown(user_id) == [
        {"category": "Bills", "amount": 50.0, "percent": 50},
        {"category": "Food", "amount": 40.0, "percent": 40},
        {"category": "Transport", "amount": 10.0, "percent": 10},
    ]

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Category breakdown" in response.data
    assert b"50.00" in response.data
    assert b"40.00" in response.data
    assert b"Shopping" not in response.data
    section = response.data[response.data.index(b"Category breakdown"):]
    assert section.index(b"Bills") < section.index(b"Food") < section.index(b"Transport")


def test_profile_category_breakdown_empty_user(client):
    from database.db import get_category_breakdown

    user_id = _create_user()
    assert get_category_breakdown(user_id) == []

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert response.status_code == 200
    assert b"No expenses yet." in response.data


def test_profile_navbar_shows_logged_in_state(client):
    user_id = _create_user(name="Nav Profile User")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Nav Profile User" in response.data
    assert b"Sign out" in response.data
