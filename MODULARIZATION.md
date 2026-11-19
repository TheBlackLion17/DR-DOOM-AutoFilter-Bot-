# Samantha modularization plan

This branch introduces the future directory layout **without changing runtime code**.

1. Preserve a backup of the working `bot.py` and MySQL schema.
2. Extract services with compatibility imports and tests.
3. Convert `database.py` to a package atomically (Python import shadowing).
4. Register Telegram handlers from `plugins/` explicitly using a shared Pyrogram Client.
5. Test `/start`, `/search`, indexing, admin permissions, forced subscription, PM delivery and deletion timers.
6. Merge into `main` only after staging verification; do not deploy this branch automatically.

Never commit `.env`, Pyrogram `.session` files or database credentials.
