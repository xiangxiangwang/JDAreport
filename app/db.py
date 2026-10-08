import json
import os
from contextlib import closing
from datetime import date, datetime, time, timedelta
from pathlib import Path


def reports():
    entries = json.loads(os.getenv("REPORT_OBJECTS", "[]"))
    if not isinstance(entries, list):
        raise ValueError("REPORT_OBJECTS must be an array")
    path = Path(os.getenv("REPORT_QUERIES_FILE", "instance/report_queries.json"))
    if path.is_file():
        configured = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(configured, list):
            raise ValueError("Report query configuration must be an array")
        entries.extend(configured)
    for entry in entries:
        keys = ("label", "sql") if entry.get("kind") == "daily" else ("label", "schema", "object")
        for key in keys:
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ValueError("Invalid report configuration")
        if entry.get("kind") == "daily":
            if not entry["sql"].lstrip().upper().startswith("SELECT TOP (?)"):
                raise ValueError("Daily queries must begin with a bounded SELECT")
            if not isinstance(entry.get("warehouses"), list) or not entry["warehouses"] or any(not isinstance(w, str) or not w for w in entry["warehouses"]):
                raise ValueError("Daily reports require approved warehouses")
    return entries


def identifier(value):
    return "[" + value.replace("]", "]]") + "]"


def odbc_value(value):
    return "{" + value.replace("}", "}}") + "}"


def connect():
    import pyodbc
    fields = {
        "DRIVER": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        "SERVER": os.environ["DB_HOST"] + "," + str(int(os.getenv("DB_PORT", "1433"))),
        "DATABASE": os.environ["DB_NAME"],
        "UID": os.environ["DB_USER"],
        "PWD": os.environ["DB_PASSWORD"],
        "Encrypt": "yes",
        "TrustServerCertificate": "yes" if os.getenv("DB_TRUST_CERTIFICATE") == "true" else "no",
        "ApplicationIntent": "ReadOnly",
        "APP": "JDA Report",
    }
    connection = pyodbc.connect(";".join(k + "=" + odbc_value(v) for k, v in fields.items()), timeout=5, autocommit=True)
    connection.timeout = 15
    return connection


def query_report(index, limit, report_date=None, warehouse=None):
    entries = reports()
    if not 0 <= index < len(entries):
        raise ValueError("Unknown report")
    entry = entries[index]
    cap = max(1, min(int(limit), 1000))
    params = ()
    if entry.get("kind") == "daily":
        day = date.fromisoformat(report_date)
        if warehouse not in entry["warehouses"]:
            raise ValueError("Warehouse is not approved for this report")
        start = datetime.combine(day, time.min)
        sql = entry["sql"]
        params = (cap, warehouse, start, start + timedelta(days=1))
    else:
        # Identifiers come only from administrator configuration, never submitted SQL.
        sql = f"SELECT TOP ({cap}) * FROM {identifier(entry['schema'])}.{identifier(entry['object'])}"
    with closing(connect()) as connection:
        cursor = connection.cursor()
        cursor.execute("SET LOCK_TIMEOUT 5000")
        cursor.execute(sql, *params) if params else cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = [[None if value is None else str(value) for value in row] for row in cursor.fetchmany(1000)]
    return columns, rows
