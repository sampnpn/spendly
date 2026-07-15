import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app import app as flask_app
from database.db import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr("database.db.DB_PATH", str(db_path))

    with flask_app.app_context():
        init_db()

    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client
