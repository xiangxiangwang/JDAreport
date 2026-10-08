import os
from dotenv import dotenv_values
from deploy import configure


def test_hidden_password_survives_special_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(configure, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_EXPANSION", "must-not-expand")
    monkeypatch.setattr("sys.argv", ["configure.py", "--db-host", "example.invalid", "--db-name", "example", "--db-user", "readonly"])
    (tmp_path / ".env.example").write_text("SECRET_KEY=\nREPORT_OBJECTS=[]\n")
    password = "literal-${TEST_EXPANSION}-'quoted'\\tail"
    monkeypatch.setattr(configure.getpass, "getpass", lambda prompt: password)
    class Cursor:
        def execute(self, sql):
            assert sql == "SELECT 1"
        def fetchone(self):
            return (1,)
    class Connection:
        def cursor(self):
            assert os.environ["DB_PASSWORD"] == password
            return Cursor()
        def close(self):
            pass
    monkeypatch.setattr("app.db.connect", Connection)
    for key in ["SECRET_KEY", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "REPORT_OBJECTS"]:
        monkeypatch.setenv(key, "old-value")
    configure.main()
    values = dotenv_values(tmp_path / ".env", interpolate=False)
    assert values["DB_PASSWORD"] == password
    assert len(values["SECRET_KEY"]) == 64
