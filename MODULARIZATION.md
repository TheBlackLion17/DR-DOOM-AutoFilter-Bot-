# Samantha AutoFilter — layout-only PR #2

The user's requirement is to keep the **original production `bot.py` unchanged**, including all functions, handlers, messages and names. The file in this branch was restored from `main` with the same Git blob SHA.

The current Python runtime imports `database.py`, `ags_indexer.py`, `parser.py` and `samantha_logs.py` from the repository root. They remain in place, unchanged. Moving them would require changing import paths in the original `bot.py`, contrary to the requested no-code-change constraint.

The folders `plugins/`, `services/`, `assets/`, `utils/`, and `database_layer/` are organizational/documentation placeholders only. They are **not** replacement runtime packages. In particular, do not create a root `database/` Python package while the original `database.py` remains in use: Python import resolution could break the original bot.

To get a fully modular folder layout, explicit permission to modify imports and split code would be necessary. This PR intentionally does not do that.

## Validation

```bash
python -m compileall -q bot.py config.py database.py ags_indexer.py parser.py samantha_logs.py
python -m unittest discover -s tests -v
```

Never deploy or merge without verifying the original runtime. No Telegram token, MySQL data, VPS files or production branch were changed by this layout-only cleanup.
