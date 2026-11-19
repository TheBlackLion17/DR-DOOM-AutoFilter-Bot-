# Telegram handlers

Planned modules: `start.py`, `admin.py`, `search.py`, `delivery.py`, `indexing.py`, `settings.py`, and `filters.py`.

Move decorated handlers together with their dependencies, register them explicitly on the shared Pyrogram client, and avoid circular imports. The current `bot.py` remains the working entry point until the migration is tested.
