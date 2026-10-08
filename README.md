# JDA Report

An authenticated SQL Server reporting workspace with account management, administrator-configured report objects, bounded previews, and CSV export.

The interface defaults to English. The header language bar switches between English and Chinese and remembers the choice on the same browser, including after sign-out. For custom reports, optionally configure `label_en` and `label_zh` alongside `label`; database column names and values are preserved.

Daily reports can be configured privately using `REPORT_QUERIES_FILE`. The interface provides date and approved-warehouse filters and opens the first daily report on sign-in. Administrator-authored query definitions use `kind: daily`, labels, a warehouse allowlist, and a SELECT beginning with `SELECT TOP (?)`. Parameters are the row limit, warehouse, inclusive start timestamp and exclusive next-day timestamp. Live query definitions stay outside the public repository. Preview and CSV export use the same filters and remain subject to the row limit.

## Development

Requires Python 3.12 or 3.13. Create a virtual environment and install dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Set a random `SECRET_KEY` of at least 32 characters in your local `.env`. Enter database connection settings and approved reporting objects locally. Never commit credentials, connection details, certificate keys, query results, or database exports.

Create an account using an interactive password prompt:

```sh
.venv/bin/python -m flask --app app:create_app create-user yourname
```

Passwords require at least 12 characters. Running the same command resets that account's password and revokes previous sessions. `delete-user yourname` removes an account.

```sh
.venv/bin/python serve.py
.venv/bin/python -m pytest -q
```

Use your own environment configuration for access and deployment. Secure cookies require HTTPS; local HTTP development must remain on the loopback interface and use `COOKIE_SECURE=false`.

## Reporting

`REPORT_OBJECTS` is a JSON array of administrator-approved objects, with `label`, `schema`, and `object` fields. No production object names are bundled. All accounts share this configured report list.

The application issues bounded SELECT queries rather than accepting submitted SQL. Previews and exports are limited to 1,000 rows; no ordering is assumed, and these are not complete business reports. Define dedicated parameterized reports for full exports, filters, or stable ordering.

CSV exports use UTF-8 BOM and protect against spreadsheet formula prefixes. Database accounts must be restricted by the DBA: read-only connection intent does not enforce database permissions.

## Collaboration

Use feature branches and pull requests. GitHub Actions runs automated tests without connecting to production databases. Deployment notes and environment configuration belong in your private operational documentation.
