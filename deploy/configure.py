"""Configure database access interactively without exposing passwords in argv."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values, load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host", required=True)
    parser.add_argument("--db-name", required=True)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-port", type=int, default=1433)
    args = parser.parse_args()
    if not 1 <= args.db_port <= 65535:
        parser.error("Database port must be between 1 and 65535")
    os.chdir(ROOT)
    path = ROOT / ".env"
    if not path.exists():
        path.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)
    current = dotenv_values(path, interpolate=False)
    password = getpass.getpass("Database password (hidden): ")
    if not password:
        raise SystemExit("Empty password; configuration was not changed.")
    settings = {
        "DB_HOST": args.db_host, "DB_PORT": str(args.db_port),
        "DB_NAME": args.db_name, "DB_USER": args.db_user, "DB_PASSWORD": password,
    }
    if not current.get("SECRET_KEY"):
        settings["SECRET_KEY"] = secrets.token_hex(32)
    # Write in place: replacing the file would lose its restricted Windows ACL.
    current.update(settings)
    def quoted(value):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    path.write_text("".join(key + "=" + quoted(value or "") + "\n" for key, value in current.items()), encoding="utf-8")
    del password, settings
    load_dotenv(path, override=True, interpolate=False)
    try:
        from app.db import connect
        connection = connect()
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
        finally:
            connection.close()
    except Exception as exc:
        print(f"Configuration saved. Connection verification failed ({type(exc).__name__}).")
        print("Check the ODBC driver, credentials, network, port and certificate with your administrator.")
        raise SystemExit(1)
    print("Database login and SELECT 1 succeeded. Reporting-object permissions are not yet verified.")


if __name__ == "__main__":
    main()
