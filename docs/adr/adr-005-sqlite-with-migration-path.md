# ADR-005 — SQLite with an explicit migration path

## Context
The demo needs 90 days of per-device time series with zero infrastructure:
clone, `docker compose up`, working dashboard. Production would need
concurrent writers and a real server database.

## Decision
SQLite behind SQLAlchemy ORM (`services/database.py`). The application never
touches the dialect directly, so the connection string is the only
PostgreSQL-specific change. Schema evolution is owned by Alembic
(`migrations/`), with the baseline mirroring the current models and the URL
resolved from `ENERGY_ADVISOR_DB_PATH` — migrations always target the same
database the app would.

## Consequences
- Zero-infra onboarding; the database is a file that bootstrap can recreate.
- Existing databases created by `Base.metadata.create_all` adopt migrations
  with `alembic stamp head`; from then on, schema changes are versioned
  scripts instead of "it works on my machine".
- Cost: SQLite serializes writes — fine for one household and a demo API,
  wrong for multi-tenant. The swap point is documented and the ORM keeps it
  to a connection-string change, but data *migration* (not just schema) would
  still be real work.
