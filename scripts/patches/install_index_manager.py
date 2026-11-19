from pathlib import Path

p = Path("bot.py")
s = p.read_text()

start = s.index(
    "@bot.on_message(filters.command('index')"
)
end = s.index(
    "@bot.on_message(filters.command('progress')",
    start
)

replacement = '''
# ===== TEMARI INTERACTIVE INDEX MANAGER =====

import time
from types import SimpleNamespace

index_started_at = {}


def index_admin(user):
    return bool(user) and admin(
        None, None, SimpleNamespace(from_user=user)
    )


def index_menu():
    buttons = [
        [InlineKeyboardButton(
            f"📁 Channel {channel}",
            callback_data=f"im:channel:{channel}"
        )]
        for channel in sorted(CHANNELS)
    ]
    return InlineKeyboardMarkup(buttons)


def index_channel_menu(channel):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "▶️ Start / Resume Scan",
            callback_data=f"im:start:{channel}"
        )],
        [InlineKeyboardButton(
            "📊 Detailed Report",
            callback_data=f"im:report:{channel}"
        )],
        [InlineKeyboardButton(
            "🔄 Refresh",
            callback_data=f"im:channel:{channel}"
        )],
        [InlineKeyboardButton(
            "⬅️ All Channels",
            callback_data="im:home"
        )]
    ])


async def index_report(channel):
    row = await db.fetchone(
        "SELECT * FROM ags_scan_state WHERE channel_id=%s",
        (channel,)
    )

    stored = await db.fetchone(
        "SELECT COUNT(*) AS total FROM files "
        "WHERE source_channel=%s",
        (channel,)
    )

    running = (
        channel in scans and not scans[channel].done()
    )

    if not row:
        return (
            f"📊 TEMARI INDEX REPORT\\\\n\\\\n"
            f"Channel: {channel}\\\\n"
            f"Status: Not started\\\\n"
            f"Stored files: {stored['total']}\\\\n"
            f"Use Start / Resume Scan to begin."
        )

    elapsed = index_started_at.get(channel)
    if elapsed is not None and running:
        duration = int(time.monotonic() - elapsed)
        elapsed_text = f"{duration // 60}m {duration % 60}s"
    else:
        elapsed_text = "Not recorded"

    status = "running" if running else row["status"]

    return (
        f"📊 TEMARI — INDEX REPORT\\\\n\\\\n"
        f"📁 Channel: {channel}\\\\n"
        f"📌 Status: {status}\\\\n\\\\n"
        f"🔎 Scanned: {row['scanned']}\\\\n"
        f"✅ Indexed/updated: {row['indexed']}\\\\n"
        f"⏭ Skipped: {row['skipped']}\\\\n"
        f"📦 Stored files: {stored['total']}\\\\n"
        f"📍 Checkpoint: {row['next_offset_id']}\\\\n"
        f"⏱ Current run: {elapsed_text}\\\\n"
        f"🔄 Active task: {running}\\\\n\\\\n"
        f"Duplicate and failure totals are not separately "
        f"tracked by the current indexer."
    )


async def index_completion_notice(channel, user_id, task):
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception:
        log.exception("Index task failed: %s", channel)
    finally:
        index_started_at.pop(channel, None)

    try:
        report = await index_report(channel)
        await bot.send_message(
            user_id,
            "🏁 Scan task finished\\\\n\\\\n" + report
        )
    except Exception:
        log.exception("Could not send scan report")


@bot.on_message(filters.command('index') & filters.private)
async def index_command(_, msg):
    if not index_admin(msg.from_user):
        return

    if len(msg.command) > 1:
        try:
            channel = int(msg.command[1])
        except ValueError:
            return await msg.reply_text(
                "Usage: /index or /index <channel_id>"
            )

        if channel not in CHANNELS:
            return await msg.reply_text(
                "Channel not listed in SOURCE_CHANNELS."
            )

        return await msg.reply_text(
            f"📁 TEMARI INDEX MANAGER\\\\n\\\\n"
            f"Selected channel: {channel}",
            reply_markup=index_channel_menu(channel)
        )

    await msg.reply_text(
        "📁 TEMARI — INDEX MANAGER\\\\n\\\\n"
        "Select a database channel:",
        reply_markup=index_menu()
    )


@bot.on_callback_query(filters.regex(r'^im:'))
async def index_manager_callback(_, q):
    if not index_admin(q.from_user):
        return await q.answer(
            "Admins only", show_alert=True
        )

    parts = q.data.split(":")
    action = parts[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            "📁 TEMARI — INDEX MANAGER\\\\n\\\\n"
            "Select a database channel:",
            reply_markup=index_menu()
        )

    try:
        channel = int(parts[2])
    except (IndexError, ValueError):
        return await q.answer("Invalid channel", show_alert=True)

    if channel not in CHANNELS:
        return await q.answer(
            "Channel not configured", show_alert=True
        )

    if action == "channel":
        await q.answer()
        return await q.message.edit_text(
            f"📁 TEMARI INDEX MANAGER\\\\n\\\\n"
            f"Selected channel: {channel}",
            reply_markup=index_channel_menu(channel)
        )

    if action == "report":
        await q.answer()
        return await q.message.edit_text(
            await index_report(channel),
            reply_markup=index_channel_menu(channel)
        )

    if action == "start":
        if not history:
            return await q.answer(
                "USER_SESSION is not configured",
                show_alert=True
            )

        if channel in scans and not scans[channel].done():
            return await q.answer(
                "Scan already running",
                show_alert=True
            )

        task = asyncio.create_task(scan_channel(channel))
        scans[channel] = task
        index_started_at[channel] = time.monotonic()

        asyncio.create_task(
            index_completion_notice(
                channel, q.from_user.id, task
            )
        )

        await q.answer("Scan started")
        await q.message.edit_text(
            f"✅ Scan started / resumed\\\\n"
            f"Channel: {channel}\\\\n\\\\n"
            f"Use Detailed Report to monitor progress.",
            reply_markup=index_channel_menu(channel)
        )


'''

s = s[:start] + replacement + s[end:]
p.write_text(s)
print("Interactive index manager installed.")
