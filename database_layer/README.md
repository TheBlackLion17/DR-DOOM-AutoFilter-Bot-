# Database module migration

The existing root `database.py` must remain unchanged while preparing a `database/` Python package: a folder named `database` would shadow `database.py` and break `import database as db` until migration is complete.

Future layout: `database/__init__.py`, `connection.py`, `queries.py`, `schema.py` with compatibility exports for `init_db`, `close_db`, `execute`, `fetchone`, `fetchall`.
