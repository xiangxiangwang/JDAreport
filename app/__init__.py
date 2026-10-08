import csv
import getpass
import hmac
import io
import os
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash

from .db import query_report, reports
from .i18n import TEXT, language, report_label, translate


def create_app(test_config=None):
    load_dotenv(interpolate=False)
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(SECRET_KEY=os.getenv("SECRET_KEY"), DEFAULT_LANGUAGE="en", SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true") == "true",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384,
                      STORE=str(Path(app.instance_path) / "users.sqlite3"))
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set SECRET_KEY to at least 32 random characters")
    Path(app.config["STORE"]).parent.mkdir(parents=True, exist_ok=True)

    def store():
        connection = sqlite3.connect(app.config["STORE"], timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    with closing(store()) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, password TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS attempts (source TEXT NOT NULL, stamp REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS attempt_source ON attempts(source, stamp);
            CREATE TABLE IF NOT EXISTS audit (stamp REAL NOT NULL, username TEXT NOT NULL, action TEXT NOT NULL, report_id INTEGER, row_count INTEGER);
        """)
        connection.commit()

    def audit(action, report_id=None, row_count=None):
        with closing(store()) as connection:
            connection.execute("INSERT INTO audit VALUES (?, ?, ?, ?, ?)", (time.time(), session.get("user", ""), action, report_id, row_count))
            connection.commit()

    @app.before_request
    def security():
        session.setdefault("csrf", secrets.token_urlsafe(32))
        if request.method == "POST" and not hmac.compare_digest(session["csrf"], request.form.get("csrf", "")):
            abort(400)
        if request.endpoint not in ("login", "static", "health", "set_language"):
            with closing(store()) as connection:
                user = connection.execute("SELECT version FROM users WHERE name=?", (session.get("user", ""),)).fetchone()
            if not user or user["version"] != session.get("version"):
                session.clear()
                return redirect(url_for("login"))

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.context_processor
    def localization():
        return {"t": translate, "language": language(), "report_label": report_label}

    @app.post("/language")
    def set_language():
        locale = request.form.get("language")
        if locale not in TEXT:
            abort(400)
        target = "home" if request.form.get("page") == "home" else "login"
        response = redirect(url_for(target))
        response.set_cookie("jda_language", locale, max_age=365 * 24 * 3600,
                            secure=app.config["SESSION_COOKIE_SECURE"], httponly=True, samesite="Lax")
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()[:100]
            source = request.remote_addr or "unknown"
            with closing(store()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM attempts WHERE stamp < ?", (time.time() - 900,))
                attempts = connection.execute("SELECT COUNT(*) FROM attempts WHERE source=?", (source,)).fetchone()[0]
                if attempts >= 10:
                    connection.commit()
                    return render_template("login.html", error=translate("login_throttled")), 429
                user = connection.execute("SELECT * FROM users WHERE name=?", (username,)).fetchone()
                if user and check_password_hash(user["password"], request.form.get("password", "")):
                    connection.commit()
                    session.clear()
                    session.update(user=username, version=user["version"], csrf=secrets.token_urlsafe(32))
                    session.permanent = True
                    audit("login")
                    return redirect(url_for("home"))
                connection.execute("INSERT INTO attempts VALUES (?, ?)", (source, time.time()))
                connection.commit()
            error = translate("login_invalid")
        return render_template("login.html", error=error)

    @app.post("/logout")
    def logout():
        audit("logout")
        session.clear()
        return redirect(url_for("login"))

    @app.route("/", methods=["GET", "POST"])
    def home():
        entries = reports()
        columns, rows, error, selected, limit = [], [], None, 0, 200
        if request.method == "POST":
            try:
                selected = int(request.form.get("report", "-1"))
                limit = max(1, min(int(request.form.get("limit", "200")), 1000))
                if not 0 <= selected < len(entries):
                    abort(400)
            except ValueError:
                abort(400)
            try:
                columns, rows = query_report(selected, limit)
            except Exception:
                audit("query_failed", selected)
                error = translate("query_failed")
            else:
                action = "export" if request.form.get("action") == "export" else "preview"
                audit(action, selected, len(rows))
                if action == "export":
                    output = io.StringIO()
                    writer = csv.writer(output)
                    def safe_cell(value):
                        value = "" if value is None else str(value)
                        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
                    writer.writerow([safe_cell(c) for c in columns])
                    writer.writerows([[safe_cell(v) for v in row] for row in rows])
                    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="jda-report.csv"'})
        return render_template("home.html", reports=entries, columns=columns, rows=rows, error=error, selected=selected, limit=limit)

    @app.cli.command("create-user")
    @click.argument("username")
    def create_user(username):
        """Create or reset an account; passwords are entered locally."""
        if not username.strip() or len(username) > 100:
            raise click.ClickException("Username must contain 1–100 characters")
        password = getpass.getpass("Password (12+ characters): ")
        if len(password) < 12 or password != getpass.getpass("Confirm password: "):
            raise click.ClickException("Passwords must match and contain at least 12 characters")
        with closing(store()) as connection:
            connection.execute("INSERT INTO users(name,password) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET password=excluded.password, version=users.version+1", (username, generate_password_hash(password)))
            connection.commit()
        click.echo("Account saved; previous sessions revoked.")

    @app.cli.command("delete-user")
    @click.argument("username")
    def delete_user(username):
        with closing(store()) as connection:
            connection.execute("DELETE FROM users WHERE name=?", (username,))
            connection.commit()
        click.echo("Account removed.")

    return app
