"""Samantha admin handlers. Shared state and helpers live in core."""
from core import *


async def doom_addadmin(_, msg):
    if not msg.from_user or not await doom_owner(msg.from_user.id):
        return await msg.reply_text("Owner only.")

    try:
        uid = int(msg.command[1])
        if uid <= 0:
            raise ValueError
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /addadmin 123456789")

    await db.execute(
        "INSERT IGNORE INTO doom_admins(user_id) VALUES(%s)",
        (uid,)
    )
    DYNAMIC_ADMINS.add(uid)
    slog.emit_background(f"🛡️ <b>admin added</b>\nActor: <code>{msg.from_user.id}</code>\nTarget: <code>{uid}</code>")
    await msg.reply_text(f"✅ Admin added: `{uid}`")


async def doom_deladmin(_, msg):
    if not msg.from_user or not await doom_owner(msg.from_user.id):
        return await msg.reply_text("Owner only.")

    try:
        uid = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /deladmin 123456789")

    if uid in ADMINS:
        return await msg.reply_text(
            "This admin is configured in .env and cannot be removed here."
        )

    await db.execute(
        "DELETE FROM doom_admins WHERE user_id=%s",
        (uid,)
    )
    DYNAMIC_ADMINS.discard(uid)
    slog.emit_background(f"🛡️ <b>admin removed</b>\nActor: <code>{msg.from_user.id}</code>\nTarget: <code>{uid}</code>")
    await msg.reply_text(f"✅ Admin removed: `{uid}`")


async def doom_admin_list(_, msg):
    if not admin(None, None, msg):
        return
    ids = sorted(DYNAMIC_ADMINS)
    await msg.reply_text(
        "👑 DR. DOOM ADMINS\n\n" +
        "\n".join(str(x) for x in ids)
    )


async def doom_addfsub(_, msg):
    if not admin(None, None, msg):
        return

    parts = msg.text.split(maxsplit=3)
    if len(parts) != 4:
        return await msg.reply_text(
            "Usage:\n"
            "/addfsub -1001234567890 ChannelName https://t.me/channel"
        )

    try:
        cid = int(parts[1])
    except ValueError:
        return await msg.reply_text("Invalid channel ID.")

    title = parts[2]
    link = parts[3].strip()

    if not link.startswith(("https://t.me/", "https://telegram.me/")):
        return await msg.reply_text("Invalid Telegram join link.")

    try:
        chat = await bot.get_chat(cid)
        me = await bot.get_me()
        membership = await bot.get_chat_member(cid, me.id)
        status = str(membership.status).lower()
        if "administrator" not in status and "owner" not in status:
            return await msg.reply_text(
                "Make the bot an admin in this channel first."
            )
    except Exception as exc:
        log.warning("Force-sub channel validation failed: %s", exc)
        return await msg.reply_text(
            "Bot cannot access this channel. Add it as an admin first."
        )

    await db.execute(
        """INSERT INTO doom_fsub(channel_id,title,invite_link)
           VALUES(%s,%s,%s)
           ON DUPLICATE KEY UPDATE
           title=VALUES(title),
           invite_link=VALUES(invite_link)""",
        (cid, title, link)
    )
    await load_doom_access()
    await msg.reply_text(f"✅ Force-sub channel added: {title}")
    slog.emit_background(f"🛡️ <b>force-sub added</b>\nActor: <code>{msg.from_user.id}</code>")


async def doom_delfsub(_, msg):
    if not admin(None, None, msg):
        return

    try:
        cid = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /delfsub -1001234567890")

    await db.execute(
        "DELETE FROM doom_fsub WHERE channel_id=%s",
        (cid,)
    )
    await load_doom_access()
    await msg.reply_text("✅ Force-sub channel removed.")
    slog.emit_background(f"🛡️ <b>force-sub removed</b>\nActor: <code>{msg.from_user.id}</code>")


async def doom_fsub_list(_, msg):
    if not admin(None, None, msg):
        return

    if not FSUB_CHANNELS:
        return await msg.reply_text("No dynamic force-sub channels.")

    await msg.reply_text(
        "📢 REQUIRED CHANNELS\n\n" +
        "\n".join(
            f"{c['title']} — {c['channel_id']}"
            for c in FSUB_CHANNELS
        )
    )


async def doom_verify_fsub(_, q):
    if not q.from_user:
        return await q.answer("User unavailable.", show_alert=True)

    if not await is_subscribed(q.from_user.id):
        return await q.answer(
            "Please join every required channel first.",
            show_alert=True
        )

    await q.answer("Subscription verified!")

    await q.message.delete()

    await send_start_welcome(q.message)


async def doom_fsub_panel_callback(_, q):
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    action = q.data.split(":", 1)[1]
    uid = q.from_user.id

    if action == "home":
        await q.answer()
        return await doom_show_fsub_panel(q.message)

    if action == "add":
        DOOM_FSUB_PENDING[uid] = {
            "action": "add",
            "step": "channel_id"
        }
        await q.answer()
        return await q.message.reply_text(
            "➕ **ADD FORCE SUB CHANNEL**\n\n"
            "Send the Telegram channel ID.\n\n"
            "Example: `-1004435370184`\n\n"
            "Send /cancel to stop."
        )

    if action == "remove":
        if not FSUB_CHANNELS:
            return await q.answer(
                "No additional channels.",
                show_alert=True
            )

        rows = [
            [
                InlineKeyboardButton(
                    "❌ " + str(c["title"])[:35],
                    callback_data="dfsub:del:" + str(c["channel_id"])
                )
            ]
            for c in FSUB_CHANNELS
        ]
        rows.append([
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="dfsub:home"
            )
        ])

        await q.answer()
        return await q.message.edit_text(
            "➖ **REMOVE CHANNEL**\n\n"
            "Tap a channel to remove it.",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    if action == "list":
        lines = ["📋 **REQUIRED CHANNELS**", ""]

        if FORCE_CHANNEL:
            lines.append(f"Main: `{FORCE_CHANNEL}`")

        for c in FSUB_CHANNELS:
            lines.append(
                f"• {c['title']} — `{c['channel_id']}`"
            )

        if not FORCE_CHANNEL and not FSUB_CHANNELS:
            lines.append("No required channels.")

        await q.answer()
        return await q.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="dfsub:home"
                )
            ]])
        )

    if action == "link":
        DOOM_FSUB_PENDING[uid] = {
            "action": "main_link"
        }
        await q.answer()
        return await q.message.reply_text(
            "🔗 **EDIT MAIN CHANNEL JOIN LINK**\n\n"
            "Send the public Telegram URL or private invite link.\n\n"
            "Example: `https://t.me/YourChannel`\n\n"
            "Send /cancel to stop."
        )

    if action.startswith("del:"):
        try:
            cid = int(action.split(":", 1)[1])
        except ValueError:
            return await q.answer("Invalid channel.", show_alert=True)

        if cid not in [
            int(c["channel_id"]) for c in FSUB_CHANNELS
        ]:
            return await q.answer(
                "Channel not found.",
                show_alert=True
            )

        await db.execute(
            "DELETE FROM doom_fsub WHERE channel_id=%s",
            (cid,)
        )
        await load_doom_access()

        await q.answer("Channel removed.")
        return await doom_show_fsub_panel(q.message)


async def doom_fsub_pending_handler(_, msg):
    if not msg.from_user:
        return

    uid = msg.from_user.id
    state = DOOM_FSUB_PENDING.get(uid)

    if not state:
        return

    if uid not in DYNAMIC_ADMINS:
        DOOM_FSUB_PENDING.pop(uid, None)
        return

    text = (msg.text or "").strip()

    if text == "/cancel":
        DOOM_FSUB_PENDING.pop(uid, None)
        await msg.reply_text("Cancelled.")
        raise StopPropagation

    if text.startswith("/"):
        return

    action = state["action"]

    if action == "main_link":
        if not text.startswith(
            ("https://t.me/", "https://telegram.me/")
        ):
            await msg.reply_text(
                "Send a valid Telegram channel URL."
            )
            raise StopPropagation

        # Save the link in MySQL, not .env.
        await db.execute(
            "INSERT INTO bot_settings "
            "(setting_key, setting_value) "
            "VALUES (%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            "setting_value=VALUES(setting_value)",
            ("doom_main_fsub_link", text)
        )

        DOOM_FSUB_PENDING.pop(uid, None)

        await msg.reply_text(
            "✅ Main channel join link saved."
        )
        raise StopPropagation

    if action == "add":
        step = state["step"]

        if step == "channel_id":
            try:
                cid = int(text)
                if cid >= 0:
                    raise ValueError
            except ValueError:
                await msg.reply_text(
                    "Invalid channel ID. Send a negative channel ID."
                )
                raise StopPropagation

            state["channel_id"] = cid
            state["step"] = "title"

            await msg.reply_text(
                "Send a channel name.\n"
                "Example: Updates"
            )
            raise StopPropagation

        if step == "title":
            if len(text) > 255:
                await msg.reply_text(
                    "Channel name is too long."
                )
                raise StopPropagation

            state["title"] = text
            state["step"] = "link"

            await msg.reply_text(
                "Send the Telegram join link."
            )
            raise StopPropagation

        if step == "link":
            if not text.startswith(
                ("https://t.me/", "https://telegram.me/")
            ):
                await msg.reply_text(
                    "Invalid Telegram URL."
                )
                raise StopPropagation

            cid = state["channel_id"]

            try:
                me = await bot.get_me()
                member = await bot.get_chat_member(cid, me.id)
                status = str(member.status).lower()

                if not (
                    "administrator" in status or
                    "owner" in status
                ):
                    await msg.reply_text(
                        "Make DR. DOOM an admin in "
                        "this channel first."
                    )
                    raise StopPropagation
            except RPCError as exc:
                await msg.reply_text(
                    "Cannot access channel: " + str(exc)
                )
                raise StopPropagation

            await db.execute(
                "INSERT INTO doom_fsub "
                "(channel_id,title,invite_link) "
                "VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE "
                "title=VALUES(title), "
                "invite_link=VALUES(invite_link)",
                (cid, state["title"], text)
            )

            await load_doom_access()
            DOOM_FSUB_PENDING.pop(uid, None)

            await msg.reply_text(
                "✅ Force-sub channel added successfully."
            )
            raise StopPropagation


async def temari_admin_panel(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        "⚙️ **DR. DOOM ADMIN SETTINGS**\n\n"
        "Choose what you want to manage.",
        reply_markup=temari_admin_keyboard()
    )


async def temari_admin_callback(_, q):
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer(
            "Admins only.",
            show_alert=True
        )

    action = q.data.split(":", 1)[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            "⚙️ **DR. DOOM ADMIN SETTINGS**\n\n"
            "Choose what you want to manage.",
            reply_markup=temari_admin_keyboard()
        )


    if action == "admins":
        if q.from_user.id != OWNER_ID:
            return await q.answer(
                "Only the owner can manage admins.",
                show_alert=True
            )

        ids = sorted(DYNAMIC_ADMINS)

        text = (
            "👑 **DR. DOOM ADMIN MANAGEMENT**\n\n"
            "Current admins:\n"
            + "\n".join(f"• `{uid}`" for uid in ids)
            + "\n\n"
            "**Add admin:**\n"
            "`/addadmin 123456789`\n\n"
            "**Remove admin:**\n"
            "`/deladmin 123456789`\n\n"
            "**List admins:** /admins"
        )

        await q.answer()
        return await q.message.edit_text(
            text,
            reply_markup=temari_admin_back()
        )


    if action == "fsub":
        await q.answer()
        return await doom_show_fsub_panel(q.message)

    if action == "welcome":
        await q.answer()
        return await q.message.edit_text(
            "📝 **WELCOME MESSAGE SETTINGS**\n\n"
            "To change the message, reply to your "
            "new text with:\n"
            "`/setwelcome`\n\n"
            "Other commands:\n"
            "/viewwelcome — Preview\n"
            "/resetwelcome — Restore default",
            reply_markup=temari_admin_back()
        )

    if action == "picture":
        await q.answer()
        return await q.message.edit_text(
            "🖼️ **WELCOME PICTURE SETTINGS**\n\n"
            "Reply to a photo with:\n"
            "`/setstartpic`\n\n"
            "Other commands:\n"
            "/editstartpic — Replace picture\n"
            "/viewstartpic — View picture\n"
            "/delstartpic — Remove picture",
            reply_markup=temari_admin_back()
        )

    if action == "links":
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\n\\n"
            "Select a link to edit:",
            reply_markup=await menu_links_keyboard()
        )

    if action == "preview":
        await q.answer()
        picture = await get_start_picture()
        message = await welcome_text(q.from_user)

        if picture:
            return await bot.send_photo(
                q.from_user.id,
                picture,
                caption=message,
                reply_markup=await welcome_keyboard()
            )

        return await bot.send_message(
            q.from_user.id,
            message,
            reply_markup=await welcome_keyboard()
        )

    if action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total, "
            "COUNT(DISTINCT source_channel) AS channels "
            "FROM files"
        )
        await q.answer()
        return await q.message.edit_text(
            "📊 **TEMARI STATISTICS**\n\n"
            f"📁 Indexed files: {row['total']}\n"
            f"📡 Source channels: {row['channels']}",
            reply_markup=temari_admin_back()
        )

    if action == "reset":
        await q.answer()
        return await q.message.edit_text(
            "🔄 **RESET WELCOME MESSAGE**\n\n"
            "To restore the default welcome text, "
            "send /resetwelcome.\n\n"
            "This does not delete your welcome picture.",
            reply_markup=temari_admin_back()
        )

    await q.answer()




# ===== TEMARI MENU EDITOR V2 =====
