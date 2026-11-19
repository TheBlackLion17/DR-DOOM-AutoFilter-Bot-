"""Samantha AutoFilter entry point. Register handlers before starting Pyrogram."""
import asyncio
from core import main
import plugins.register  # noqa: F401 - registers Telegram handlers

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
