from pathlib import Path

p = Path("bot.py")
s = p.read_text()

if "# ===== START PICTURE MANAGER =====" in s:
    raise SystemExit("Start picture manager already installed.")

anchor = "@bot.on_message(filters.command('help'))"

if anchor not in s:
    raise SystemExit("Help handler not found. No changes made.")

manager = '''
# ===== START PICTURE MANAGER =====

async def ensure_start_picture_table():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT
        )
    """)


async def get_start_picture():
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings "
        "WHERE setting_key=%s",
        ("start_picture",)
    )
    return row["setting_value"] if row else None


async def send_start_welcome(msg):
    picture = await get_start_picture()

    if picture:
        try:
            return await msg.reply_photo(
                photo=picture,
                caption=welcome_text(msg.from_user),
                reply_markup=welcome_keyboard()
            )
        except RPCError:
            log.exception("Failed to send welcome picture")

    return await msg.reply_text(
        welcome_text(msg.from_user),
        reply_markup=welcome_keyboard()
    )


@bot.on_message(
    filters.command(["setstartpic", "editstartpic"])
    & filters.private
)
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
        "✅ Temari welcome picture saved successfully!\\n"
        "Send /start to see it."
    )


@bot.on_message(filters.command("delstartpic") & filters.private)
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


@bot.on_message(filters.command("viewstartpic") & filters.private)
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


'''

s = s.replace(anchor, manager + anchor, 1)

# Replace the existing text-only welcome response.
old = '''    await msg.reply_text(
        welcome_text(msg.from_user),
        reply_markup=welcome_keyboard()
    )'''

if old not in s:
    raise SystemExit(
        "Existing /start welcome response not found. "
        "No changes made."
    )

s = s.replace(
    old,
    "    await send_start_welcome(msg)",
    1
)

# Initialize settings after MySQL is connected.
init_anchor = "    await ensure_search_table()"

if init_anchor not in s:
    raise SystemExit("Database initialization not found.")

s = s.replace(
    init_anchor,
    init_anchor + "\n    await ensure_start_picture_table()",
    1
)

compile(s, str(p), "exec")
p.write_text(s)

print("Start picture manager installed.")
