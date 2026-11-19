# Samantha AutoFilter — folder organization (PR #2)

The original implementation is preserved. This is a file move, **not** a modular rewrite.

## Active runtime layout

```text
bot.py
config.py
database/
  __init__.py
  database.py
services/
  __init__.py
  ags_indexer.py
  parser.py
  samantha_logs.py
plugins/
  README.md
assets/
  README.md
utils/
  README.md
requirements.txt
README.md
```

The original source contents of `database.py`, `ags_indexer.py`, `parser.py`, and `samantha_logs.py` were copied byte-for-byte into their category folders. `database/__init__.py` preserves the `import database as db` API used by the original bot and indexer. The only edits to `bot.py` are three import paths pointing to `services/`. All handlers, messages, functions, SQL, settings, and bot identity remain unchanged.

The `plugins/` folder is a placeholder because the original handlers are inside `bot.py`; extracting them would change the original file, contrary to the user's request.

## Verification

GitHub Actions compiles the new layout and compares the moved source bytes with `main`, and checks that `bot.py` differs only in the three required import lines. Live Telegram/MySQL testing has **not** been performed. Do not deploy until a staging run passes.

## Archived support scripts

All original root-level installer, patch, fix, and diagnostic scripts were relocated **without changing their source contents**:

- `scripts/patches/`: one-off `install_*.py`, `fix_*.py`, and `add_auto_channel.py` source patchers
- `scripts/diagnostics/`: `check_*.py`, `discover_effects.py`, and `test_*.py` manual diagnostics
- `scripts/maintenance/`: `generate_session.py`
- `scripts/setup/`: `install.sh`

These are not live plugins. **Do not run the patch scripts on the production VPS**: many edit `bot.py` directly, and some contain hardcoded paths to `/opt/autofilter_bot/bot.py`. Run them only deliberately from a disposable checkout, after reviewing each script. Scripts using `Path("bot.py")` expect the current working directory to be the repository root. Python scripts importing root `config.py` may require `PYTHONPATH=.` when launched by file path. The relocated `install.sh` is not a verified deployment entrypoint and may require path adjustments. None of these scripts is executed by the bot at startup.
