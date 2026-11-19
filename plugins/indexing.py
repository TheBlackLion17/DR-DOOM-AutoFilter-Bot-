"""Samantha indexing handlers. Shared state and helpers live in core."""
import core
from core import *


async def channel_index(_, msg):
    if msg.chat.id in CHANNELS:
        try:
            await index_message(msg)
        except Exception:
            log.exception('Indexing failed for %s/%s',msg.chat.id,msg.id)
            slog.emit_background(f"❌ <b>Live indexing failed</b>\nChannel: <code>{msg.chat.id}</code>\nMessage: <code>{msg.id}</code>", key=f"live-index-failure:{msg.chat.id}", cooldown=60)



# ===== TEMARI WELCOME MENU =====


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
            success, reason = await register_source_channel(channel)

            if not success:
                return await msg.reply_text(
                    f"❌ {reason}"
                )

            await msg.reply_text(
                "✅ New database channel registered!\\n"
                f"Channel: {channel}\\n"
                "Select Start / Resume Scan to begin."
            )

        return await msg.reply_text(
            f"📁 TEMARI INDEX MANAGER\n\n"
            f"Selected channel: {channel}",
            reply_markup=index_channel_menu(channel)
        )

    await msg.reply_text(
        "📁 TEMARI — INDEX MANAGER\n\n"
        "Select a database channel:",
        reply_markup=index_menu()
    )


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
            "📁 TEMARI — INDEX MANAGER\n\n"
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
            f"📁 TEMARI INDEX MANAGER\n\n"
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
        if not core.history:
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
            f"✅ Scan started / resumed\n"
            f"Channel: {channel}\n\n"
            f"Use Detailed Report to monitor progress.",
            reply_markup=index_channel_menu(channel)
        )


async def progress(_, msg):
    if not admin(None, None, msg):
        return

    try:
        channel = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text(
            "Usage: /progress -1001234567890"
        )

    row = await db.fetchone(
        "SELECT * FROM ags_scan_state WHERE channel_id=%s",
        (channel,)
    )

    if not row:
        return await msg.reply_text(
            "No AGS scan recorded for this channel."
        )

    running = (
        channel in scans
        and not scans[channel].done()
    )

    await msg.reply_text(
        f"📊 AGS Index Progress\n"
        f"Channel: {channel}\n"
        f"Status: {row['status']}\n"
        f"Scanned: {row['scanned']}\n"
        f"Indexed/updated: {row['indexed']}\n"
        f"Skipped: {row['skipped']}\n"
        f"Checkpoint: {row['next_offset_id']}\n"
        f"Running: {running}"
    )
