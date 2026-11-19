"""Samantha menus handlers. Shared state and helpers live in core."""
from core import *


async def start(_, msg):
    slog.emit_background("👤 <b>Bot /start</b>\nUser: <code>%s</code>" % msg.from_user.id, key=f"start:{msg.from_user.id}", cooldown=3600)
    await react_to_start(msg)
    # Preserve existing file-delivery deep links.
    if len(msg.command) > 1 and msg.command[1].startswith("file_"):
        try:
            file_id = int(msg.command[1][5:])
        except ValueError:
            return await msg.reply_text("Invalid file link.")

        return await deliver(msg.from_user.id, file_id, msg)

    if not await is_subscribed(msg.from_user.id):
        return await msg.reply_text(
            "🔒 **DR. DOOM — FORCE SUBSCRIPTION**\n\n"
            "Join all required channels below to access the bot.\n\n"
            "After joining, tap Verify Subscription.",
            reply_markup=doom_fsub_keyboard()
        )

    await send_start_welcome(msg)



# ===== TEMARI CALLBACK NAVIGATION V1 =====


async def temari_menu(_, q):
    action = q.data.split(":", 1)[1]

    if action == "home":
        text = await welcome_text(q.from_user)
        keyboard = await welcome_keyboard()

    elif action in ("help", "search"):
        text = (
            "🎬 **TEMARI COMMANDS**\n\n"
            "🔎 /search name — Search all files\n"
            "🎥 /movies name — Search movies\n"
            "📺 /series name — Search series\n"
            "📜 /help — Show commands\n\n"
            "You can also send a movie or series "
            "name directly."
        )
        keyboard = temari_nav_keyboard()

    elif action == "top":
        rows = await db.fetchall(
            "SELECT title, COUNT(*) AS total "
            "FROM files "
            "WHERE title IS NOT NULL AND title != '' "
            "GROUP BY title "
            "ORDER BY total DESC LIMIT 10"
        )

        text = "🔥 **MOST INDEXED TITLES**\n\n"

        if rows:
            for i, row in enumerate(rows, 1):
                title = str(row["title"] or "Unknown")
                title = title.replace("\n", " ")[:55]
                text += (
                    f"{i}. {title} "
                    f"({row['total']})\n"
                )
        else:
            text += "No indexed titles yet."

        keyboard = temari_nav_keyboard()

    elif action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total FROM files"
        )

        total = row["total"] if row else 0

        text = (
            "📊 **TEMARI STATISTICS**\n\n"
            f"📁 Indexed files: {total}"
        )
        keyboard = temari_nav_keyboard()

    elif action == "premium":
        text = (
            "💎 **TEMARI PREMIUM**\n\n"
            "Premium features are coming soon!"
        )
        keyboard = temari_nav_keyboard()

    elif action == "about":
        text = (
            "🌻 **TEMARI AUTO FILTER**\n\n"
            "🎬 Movies & Series Search\n"
            "📁 MySQL File Indexing\n"
            "🔒 Private File Delivery\n"
            "⏳ Automatic File Deletion\n\n"
            "💖 Powered by Temari"
        )
        keyboard = temari_nav_keyboard()

    else:
        return await q.answer(
            "Unknown menu option.",
            show_alert=True
        )

    # Telegram photo captions have a 1024-character limit.
    if q.message.photo and len(text) > 1000:
        text = text[:990] + "\n..."

    await q.answer()
    text = await apply_bot_branding(text)
    await temari_edit_page(q, text, keyboard)


# ===== START PICTURE MANAGER =====


async def set_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    content = msg.text.partition(" ")[2].strip()

    if not content and msg.reply_to_message:
        content = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ""
        )

    if not content:
        return await msg.reply_text(
            "Reply to a text message with /setwelcome "
            "or send:\n"
            "/setwelcome Your welcome message\n\n"
            "Use {name} for the user's first name."
        )

    if len(content) > 1024:
        return await msg.reply_text(
            "Welcome message must be 1024 characters "
            "or fewer to support photo captions."
        )

    await db.execute(
        """
        INSERT INTO bot_settings
        (setting_key, setting_value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
        setting_value=VALUES(setting_value)
        """,
        ("welcome_message", content)
    )

    await msg.reply_text(
        "✅ Welcome message updated!\n"
        "Send /start to preview."
    )


async def view_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        await apply_bot_branding(await welcome_text(msg.from_user)),
        reply_markup=await welcome_keyboard()
    )


async def reset_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await db.execute(
        "DELETE FROM bot_settings WHERE setting_key=%s",
        ("welcome_message",)
    )

    await msg.reply_text(
        "✅ Default welcome message restored."
    )



# ===== BOTFATHER DYNAMIC BRANDING V2 =====


async def set_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    photo = None

    if msg.reply_to_message and msg.reply_to_message.photo:
        photo = msg.reply_to_message.photo

    if not photo:
        return await msg.reply_text(
            "📸 Reply to a photo with /setstartpic "
            "or /editstartpic."
        )

    await db.execute("""
        INSERT INTO bot_settings(setting_key, setting_value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
        setting_value=VALUES(setting_value)
    """, ("start_picture", photo.file_id))

    await msg.reply_text(
        "✅ Temari welcome picture saved successfully!\n"
        "Send /start to see it."
    )


async def delete_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await db.execute(
        "DELETE FROM bot_settings WHERE setting_key=%s",
        ("start_picture",)
    )

    await msg.reply_text(
        "✅ Welcome picture removed. "
        "The /start menu will use text again."
    )


async def view_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    picture = await get_start_picture()

    if not picture:
        return await msg.reply_text(
            "No welcome picture is currently configured."
        )

    await msg.reply_photo(
        picture,
        caption="📸 Current Temari welcome picture"
    )



# ===== TEMARI ADMIN PANEL V1 =====


# ===== DR_DOOM_ADMIN_PANEL_V2 =====


# ===== DR_DOOM_FSUB_PANEL_V3 =====


async def temari_editor_callback(_, q):
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    parts = q.data.split(":")
    action = parts[1]

    if action == "list":
        pending_menu_links.pop(q.from_user.id, None)
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\n\\nSelect a button:",
            reply_markup=await menu_links_keyboard()
        )

    if len(parts) != 3 or parts[2] not in TEMARI_LINKS:
        return await q.answer("Invalid button.", show_alert=True)

    code = parts[2]

    if action in ("name", "url"):
        pending_menu_links[q.from_user.id] = (code, action)

        await q.answer()
        return await q.message.reply_text(
            ("✏️ Send the new button name." if action == "name"
             else "🔗 Send the new HTTPS URL.") +
            "\\nSend /cancel to cancel."
        )

    if action == "toggle":
        current = await get_menu_link("menu_visible_" + code)
        await save_menu_link(
            "menu_visible_" + code,
            "1" if current == "0" else "0"
        )

    elif action == "reset":
        _, url_key = TEMARI_LINKS[code]

        for key in (
            "menu_name_" + code,
            "menu_visible_" + code,
            url_key
        ):
            await delete_menu_setting(key)

    elif action != "open":
        return await q.answer("Invalid action.")

    pending_menu_links.pop(q.from_user.id, None)
    text, keyboard = await menu_button_editor(code)

    await q.answer()
    return await q.message.edit_text(
        text,
        reply_markup=keyboard
    )


async def cancel_menu_edit(_, msg):
    if not msg.from_user or msg.from_user.id not in pending_menu_links:
        return

    pending_menu_links.pop(msg.from_user.id, None)
    await msg.reply_text("✅ Menu editing cancelled.")
    raise StopPropagation


async def capture_menu_link(_, msg):
    if not msg.from_user:
        return

    user_id = msg.from_user.id

    if user_id not in DYNAMIC_ADMINS:
        return

    pending = pending_menu_links.get(user_id)

    if not pending:
        return

    code, action = pending
    value = msg.text.strip()

    if action == "name":
        if not value or len(value) > 60 or "\\n" in value:
            await msg.reply_text(
                "❌ Name must be 1–60 characters on one line."
            )
            raise StopPropagation

        await save_menu_link("menu_name_" + code, value)

    elif action == "url":
        parsed = urlsplit(value)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(c.isspace() for c in value)
            or len(value) > 500
        ):
            await msg.reply_text(
                "❌ Send a valid HTTPS URL."
            )
            raise StopPropagation

        _, url_key = TEMARI_LINKS[code]
        await save_menu_link(url_key, value)

    pending_menu_links.pop(user_id, None)

    text, keyboard = await menu_button_editor(code)

    await msg.reply_text(
        "✅ **Button updated successfully!**\\n\\n" + text,
        reply_markup=keyboard
    )

    raise StopPropagation
