import json
import os
from contextlib import closing


def reports():
    entries = json.loads(os.getenv("REPORT_OBJECTS", "[]"))
    if not isinstance(entries, list):
        raise ValueError("REPORT_OBJECTS must be an array")
    for entry in entries:
        for key in ("label", "schema", "object"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise ValueError("Invalid report configuration")
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


def query_report(index, limit):
    entries = reports()
    if not 0 <= index < len(entries):
        raise ValueError("Unknown report")
    entry = entries[index]
    # Identifiers come only from administrator configuration, never submitted SQL.
    sql = f"SELECT TOP ({max(1, min(int(limit), 1000))}) * FROM {identifier(entry['schema'])}.{identifier(entry['object'])}"
    with closing(connect()) as connection:
        cursor = connection.cursor()
        cursor.execute("SET LOCK_TIMEOUT 5000")
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = [[None if value is None else str(value) for value in row] for row in cursor.fetchmany(1000)]
    return columns, rows
