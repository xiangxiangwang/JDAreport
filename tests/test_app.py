import json
import sqlite3
import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from app.db import identifier, odbc_value


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_OBJECTS", json.dumps([{"label": "Test view", "schema": "dbo", "object": "TestView"}]))
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret-" * 4, "SESSION_COOKIE_SECURE": False, "STORE": str(tmp_path / "users.db")})
    with sqlite3.connect(app.config["STORE"]) as db:
        db.execute("INSERT INTO users(name,password) VALUES (?,?)", ("tester", generate_password_hash("testing-password")))
    return app


def csrf(client):
    client.get("/login")
    with client.session_transaction() as session:
        return session["csrf"]


def login(client):
    return client.post("/login", data={"csrf": csrf(client), "username": "tester", "password": "testing-password"})


def test_requires_login_and_csrf(app):
    client = app.test_client()
    assert client.get("/").status_code == 302
    assert client.post("/login", data={"username": "tester"}).status_code == 400
    assert login(client).status_code == 302
    assert client.get("/").status_code == 200
    assert client.post("/", data={"report": "0"}).status_code == 400


def test_account_revocation(app):
    client = app.test_client()
    login(client)
    with sqlite3.connect(app.config["STORE"]) as db:
        db.execute("UPDATE users SET version=version+1")
    assert client.get("/").status_code == 302


def test_login_throttle(app):
    client = app.test_client()
    token = csrf(client)
    for _ in range(10):
        assert client.post("/login", data={"csrf": token, "username": "bad", "password": "bad"}).status_code == 200
    assert client.post("/login", data={"csrf": token, "username": "bad", "password": "bad"}).status_code == 429


def test_export_cap_and_formula_protection(app, monkeypatch):
    calls = []
    def query(index, limit):
        calls.append((index, limit))
        return ["value"], [["=HYPERLINK(\"example\")"], ["  @formula"], [None], ["中文"]]
    monkeypatch.setattr("app.query_report", query)
    client = app.test_client()
    login(client)
    with client.session_transaction() as session:
        token = session["csrf"]
    response = client.post("/", data={"csrf": token, "report": "0", "limit": "999999", "action": "export"})
    assert response.status_code == 200
    assert calls == [(0, 1000)]
    assert response.data.startswith(b"\xef\xbb\xbf")
    assert "'  @formula" in response.get_data(as_text=True)
    assert "'=HYPERLINK" in response.get_data(as_text=True)
    with sqlite3.connect(app.config["STORE"]) as db:
        assert db.execute("SELECT row_count FROM audit WHERE action='export'").fetchone()[0] == 4


def test_rejects_unapproved_report(app, monkeypatch):
    def forbidden(*args):
        pytest.fail("Unapproved report reached the database")
    monkeypatch.setattr("app.query_report", forbidden)
    client = app.test_client()
    login(client)
    with client.session_transaction() as session:
        token = session["csrf"]
    for index in ["-1", "1", "0;DROP TABLE users"]:
        assert client.post("/", data={"csrf": token, "report": index}).status_code == 400


def test_errors_do_not_expose_database_details(app, monkeypatch):
    def broken(*args):
        raise RuntimeError("private-password-and-host")
    monkeypatch.setattr("app.query_report", broken)
    client = app.test_client()
    login(client)
    with client.session_transaction() as session:
        token = session["csrf"]
    response = client.post("/", data={"csrf": token, "report": "0"})
    assert b"private-password-and-host" not in response.data
    assert "查询未完成" in response.get_data(as_text=True)


def test_sql_escaping():
    assert identifier("x]; DROP") == "[x]]; DROP]"
    assert odbc_value("pass};UID=other") == "{pass}};UID=other}"


def test_real_query_is_bounded_select(monkeypatch):
    from app import db
    monkeypatch.setenv("REPORT_OBJECTS", '[{"label":"Example","schema":"dbo","object":"a]b"}]')
    statements = []
    class Cursor:
        description = [("value",)]
        def execute(self, sql):
            statements.append(sql)
        def fetchmany(self, cap):
            assert cap == 1000
            return [(1,)]
    class Connection:
        def cursor(self):
            return Cursor()
        def close(self):
            pass
    monkeypatch.setattr(db, "connect", Connection)
    assert db.query_report(0, 2000) == (["value"], [["1"]])
    assert statements == ["SET LOCK_TIMEOUT 5000", "SELECT TOP (1000) * FROM [dbo].[a]]b]"]
