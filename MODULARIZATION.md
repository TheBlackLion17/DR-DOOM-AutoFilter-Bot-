# Samantha AutoFilter modularization

`bot.py` is the entry point. `core.py` holds shared state, helpers and startup/shutdown. `plugins/` contains extracted handlers; `plugins/register.py` preserves their original Pyrogram registration order.

The original `database.py`, `parser.py`, `ags_indexer.py`, and `samantha_logs.py` remain at root for compatibility. **Do not create a `database/` package until imports are migrated atomically** because it shadows `database.py`.

Before deployment: run `python -m compileall -q bot.py core.py plugins`; perform live staging checks for `/start`, `/search`, pagination, forced subscription, admin panel, channel indexing, PM delivery and deletion timers. Keep `.env`, sessions and database files outside Git.

This refactor is untested against Telegram and MySQL; `main` and VPS are unchanged.
