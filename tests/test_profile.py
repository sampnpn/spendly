from werkzeug.security import generate_password_hash

from database.db import create_user


def _create_user(name="Test User", email="test@example.com", password="password123"):
    return create_user(name, email, generate_password_hash(password))


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
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Nitish Sharma" in response.data
    assert b"nitish@example.com" in response.data
    assert b"Member since" in response.data


def test_profile_displays_summary_stats(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Total spent" in response.data
    assert b"Transactions" in response.data
    assert b"Top category" in response.data


def test_profile_displays_transaction_history_rows(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Grocery shopping at Bhat-Bhateni" in response.data
    assert b"Bus pass top-up" in response.data
    assert b"Electricity bill" in response.data
    assert response.data.count(b"badge") >= 3


def test_profile_displays_category_breakdown(client):
    user_id = _create_user()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Category breakdown" in response.data
    assert b"Food" in response.data
    assert b"Bills" in response.data
    assert b"Transport" in response.data


def test_profile_navbar_shows_logged_in_state(client):
    user_id = _create_user(name="Nav Profile User")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/profile")

    assert b"Nav Profile User" in response.data
    assert b"Sign out" in response.data
