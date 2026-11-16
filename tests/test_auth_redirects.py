import pytest


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_in_user_is_redirected_away(client, path):
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    for method in (client.get, client.post):
        response = method(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_out_user_can_see_forms(client, path):
    assert client.get(path).status_code == 200
