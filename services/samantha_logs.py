"""Non-blocking Telegram operational logging for Samantha AutoFilter.

Usage:
    import samantha_logs as logs
    await logs.start(bot)
    await logs.user_started(message.from_user)
    await logs.delivery_success(user_id, row)
    await logs.delivery_failed(user_id, row, exc)
    await logs.admin_action(user_id, command)
    await logs.index_event("completed", channel_id, scanned=100, indexed=90)
"""
import asyncio
import logging
import os
import time
from html import escape

from pyrogram.errors import FloodWait
from pyrogram.enums import ParseMode

logger = logging.getLogger("samantha.logs")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1002801544620"))
_client = None
_last = {}
_tasks = set()


def _safe(value, limit=180):
    return escape(str(value if value is not None else "-")[:limit])


async def emit(message, *, key=None, cooldown=0):
    """Never interrupt normal bot operations if logging fails."""
    if _client is None or not LOG_CHANNEL:
        return False
    now = time.monotonic()
    if key and now - _last.get(key, float("-inf")) < cooldown:
        return False
    if key:
        _last[key] = now
    try:
        await _client.send_message(
            LOG_CHANNEL,
            message[:4000],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return True
    except FloodWait as exc:
        logger.warning("Telegram log channel rate limited for %ss", exc.value)
    except Exception as exc:
        logger.warning("Telegram log failed: %s", exc)
    return False


def emit_background(message, **kwargs):
    """Schedule optional logs without blocking the caller."""
    try:
        task = asyncio.create_task(emit(message, **kwargs))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    except RuntimeError:
        logger.warning("No running event loop for log")


async def start(client):
    global _client
    _client = client
    return await emit("🟢 <b>Samantha AutoFilter started</b>\n🤖 @agsfilterV3_bot")


async def stop():
    await emit("🔴 <b>Samantha AutoFilter stopping</b>")


async def user_started(user):
    if user is None:
        return
    await emit(
        "👤 <b>Bot /start</b>\n"
        f"User: <code>{_safe(user.id)}</code>\n"
        f"Name: {_safe(user.first_name)}",
        key=f"start:{user.id}", cooldown=3600,
    )


async def delivery_success(user_id, row):
    await emit(
        "📤 <b>File delivered</b>\n"
        f"User: <code>{_safe(user_id)}</code>\n"
        f"File: {_safe(row.get('file_name'))}\n"
        f"Source: <code>{_safe(row.get('source_channel'))}</code>",
    )


async def delivery_failed(user_id, row, exc):
    await emit(
        "❌ <b>Delivery failed</b>\n"
        f"User: <code>{_safe(user_id)}</code>\n"
        f"File: {_safe(row.get('file_name'))}\n"
        f"Error: {_safe(exc, 350)}",
        key=f"failure:{type(exc).__name__}:{str(exc)[:80]}",
        cooldown=30,
    )


async def admin_action(user_id, command):
    await emit(
        "🛡️ <b>Admin action</b>\n"
        f"Admin: <code>{_safe(user_id)}</code>\n"
        f"Command: {_safe(command)}",
    )


async def index_event(event, channel_id, *, scanned=None, indexed=None, skipped=None, error=None):
    await emit(
        f"📚 <b>Index { _safe(event, 30) }</b>\n"
        f"Channel: <code>{_safe(channel_id)}</code>\n"
        f"Scanned: {_safe(scanned)} | Indexed: {_safe(indexed)} | Skipped: {_safe(skipped)}"
        + (f"\nError: {_safe(error, 300)}" if error is not None else ""),
        key=f"index:{event}:{channel_id}",
        cooldown=60 if event == "progress" else 0,
    )
