from werkzeug.security import generate_password_hash

from database.db import create_user


def _create_user(name="Test User", email="test@example.com", password="password123"):
    return create_user(name, email, generate_password_hash(password))


def test_get_login_renders_form(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"<form" in response.data


def test_post_login_with_valid_credentials_logs_in(client):
    _create_user(email="valid@example.com", password="password123")

    response = client.post(
        "/login", data={"email": "valid@example.com", "password": "password123"}
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        assert sess["user_id"] is not None


def test_post_login_with_unknown_email_shows_error(client):
    response = client.post(
        "/login", data={"email": "nobody@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_post_login_with_wrong_password_shows_same_error(client):
    _create_user(email="wrongpass@example.com", password="correctpassword")

    response = client.post(
        "/login", data={"email": "wrongpass@example.com", "password": "incorrectpassword"}
    )

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_post_login_with_missing_fields_shows_required_error(client):
    response = client.post("/login", data={"email": "", "password": ""})

    assert response.status_code == 200
    assert b"Email and password are required." in response.data

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_clears_session_and_redirects(client):
    user_id = _create_user(email="logout@example.com", password="password123")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/logout")

    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_while_already_logged_out_does_not_error(client):
    response = client.get("/logout")

    assert response.status_code == 302


def test_navbar_shows_signed_out_links_by_default(client):
    response = client.get("/")

    assert b"Sign in" in response.data
    assert b"Get started" in response.data


def test_navbar_shows_user_name_and_sign_out_when_logged_in(client):
    user_id = _create_user(name="Nav User", email="navuser@example.com", password="password123")

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    response = client.get("/")

    assert b"Nav User" in response.data
    assert b"Sign out" in response.data
