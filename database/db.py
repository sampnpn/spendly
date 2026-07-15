import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "expense_tracker.db")

CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row


def seed_db():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    if row["count"] > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    first_of_month = date.today().replace(day=1)
    offsets = [0, 3, 6, 9, 13, 16, 20, 24]
    dates = [(first_of_month + timedelta(days=o)).strftime("%Y-%m-%d") for o in offsets]

    sample_expenses = [
        ("Food", 45.50, "Grocery shopping"),
        ("Transport", 20.00, "Bus pass"),
        ("Bills", 85.00, "Electricity bill"),
        ("Health", 32.75, "Pharmacy"),
        ("Entertainment", 15.00, "Movie tickets"),
        ("Shopping", 60.00, "New shoes"),
        ("Other", 12.50, "Miscellaneous"),
        ("Food", 38.25, "Restaurant dinner"),
    ]
    rows = [
        (user_id, amount, category, expense_date, description)
        for (category, amount, description), expense_date in zip(sample_expenses, dates)
    ]

    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
