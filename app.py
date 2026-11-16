from datetime import date, datetime, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


DATE_FORMAT = "%Y-%m-%d"
PRESETS = ("this_month", "last_30_days", "this_year", "all")


def _parse_date(value):
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).strftime(DATE_FORMAT)
    except (ValueError, AttributeError):
        return None


def _resolve_date_filter(args, today):
    date_from = date_to = preset = error = None

    requested_preset = args.get("preset", "").strip()
    if requested_preset in PRESETS:
        preset = requested_preset
        if preset == "this_month":
            date_from = today.replace(day=1)
        elif preset == "last_30_days":
            # 30 days inclusive of today
            date_from = today - timedelta(days=29)
        elif preset == "this_year":
            date_from = today.replace(month=1, day=1)
        if preset != "all":
            date_from = date_from.strftime(DATE_FORMAT)
            date_to = today.strftime(DATE_FORMAT)
    else:
        raw_from = args.get("date_from", "").strip()
        raw_to = args.get("date_to", "").strip()
        date_from = _parse_date(raw_from) if raw_from else None
        date_to = _parse_date(raw_to) if raw_to else None
        if (raw_from and date_from is None) or (raw_to and date_to is None):
            error = "Invalid date ignored."
        if date_from and date_to and date_from > date_to:
            error = "Start date must be on or before end date."
            date_from = date_to = None

    return {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "error": error,
        "active": bool(date_from or date_to),
    }


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return {"current_user": None}
    return {"current_user": get_user_by_id(user_id)}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id") is not None:
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if "@" not in email or "." not in email.split("@")[-1]:
        return render_template("register.html", error="Please enter a valid email address.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    if get_user_by_email(email):
        return render_template("register.html", error="An account with that email already exists.")

    password_hash = generate_password_hash(password)
    create_user(name, email, password_hash)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") is not None:
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Email and password are required.")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if session.get("user_id") is None:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    initials = "".join(part[0] for part in user["name"].split()[:2]).upper()
    member_since = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    profile_user = {
        "name": user["name"],
        "email": user["email"],
        "initials": initials or "?",
        "member_since": member_since,
    }

    date_filter = _resolve_date_filter(request.args, date.today())
    date_from = date_filter["date_from"]
    date_to = date_filter["date_to"]
    user_id = session["user_id"]

    summary_stats = get_summary_stats(user_id, date_from, date_to)

    transactions = get_recent_transactions(
        user_id,
        limit=None if date_filter["active"] else 5,
        date_from=date_from,
        date_to=date_to,
    )

    category_breakdown = get_category_breakdown(user_id, date_from, date_to)

    return render_template(
        "profile.html",
        profile_user=profile_user,
        summary_stats=summary_stats,
        transactions=transactions,
        category_breakdown=category_breakdown,
        date_filter=date_filter,
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
