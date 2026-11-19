# Samantha AutoFilter — modularization (PR #2)

## Current development layout

- `bot.py`: entry point, imports `plugins.register` before startup.
- `core.py`: shared state, helpers, lifecycle and compatibility layer. **Not fully decomposed yet.**
- `plugins/`: extracted Telegram handlers. `start.py`, `settings.py`, and `filters.py` currently expose compatibility wrappers around existing implementations.
- `database/connection.py`: active MySQL connection and existing schema. `models.py` and `queries.py` are scaffolding/compatibility layers.
- `services/`: active parser, AGS indexer and Telegram operational logging.
- `tests/test_modular_smoke.py`: offline import, handler and parser checks.

## Local validation (does not connect to Telegram or MySQL)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m compileall -q bot.py core.py plugins database services tests
python -m unittest discover -s tests -v
```

The smoke tests supply dummy environment values only in the test process; do not use production credentials for testing. A successful offline test is **not** proof of live behavior.

## Staging validation checklist

1. Use a separate test bot token and separate MySQL database. Do not run another process with the production bot token.
2. Confirm startup and shutdown, `/start`, forced subscription and verification.
3. Confirm search, pagination, deep-link navigation and private-only file delivery.
4. Confirm automatic deletion after the configured timeout.
5. Confirm admin management, welcome settings, live channel indexing and resumable scans.
6. Confirm Telegram operational logs, permissions, and error handling.
7. Only after tests pass, remove obsolete root-level duplicate files and compatibility wrappers.

**Safety:** PR #2 is not ready to merge or deploy. The live VPS and `main` branch are unaffected. Never commit `.env`, Telegram session strings/files or MySQL dumps.
