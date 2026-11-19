from pathlib import Path

p = Path("bot.py")
s = p.read_text()

marker = "# ===== TEMARI WELCOME MESSAGE EDITOR ====="

if marker in s:
    raise SystemExit("Welcome editor already installed.")

required = [
    "async def get_start_picture():",
    "async def send_start_welcome(msg):",
    "async def ensure_start_picture_table():",
    "def welcome_text(user):",
]

missing = [x for x in required if x not in s]

if missing:
    raise SystemExit(
        "Start-picture manager is not fully installed: "
        + ", ".join(missing)
    )

# Preserve the original default welcome message.
s = s.replace(
    "def welcome_text(user):",
    "def default_welcome_text(user):",
    1
)

anchor = "async def send_start_welcome(msg):"

editor = '''
# ===== TEMARI WELCOME MESSAGE EDITOR =====

async def welcome_text(user):
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings "
        "WHERE setting_key=%s",
        ("welcome_message",)
    )

    if row and row["setting_value"]:
        name = user.first_name if user else "Friend"

        return row["setting_value"].replace(
            "{name}", name
        )

    return default_welcome_text(user)


@bot.on_message(
    filters.command(["setwelcome", "editwelcome"])
    & filters.private
)
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
            "or send:\\n"
            "/setwelcome Your welcome message\\n\\n"
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
        "✅ Welcome message updated!\\n"
        "Send /start to preview."
    )


@bot.on_message(
    filters.command("viewwelcome") & filters.private
)
async def view_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        await welcome_text(msg.from_user),
        reply_markup=welcome_keyboard()
    )


@bot.on_message(
    filters.command("resetwelcome") & filters.private
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


'''

s = s.replace(anchor, editor + anchor, 1)

# Update photo and text welcome responses.
start = s.index("async def send_start_welcome(msg):")
end = s.index(
    "@bot.on_message(",
    start
)

section = s[start:end]

section = section.replace(
    "welcome_text(msg.from_user)",
    "await welcome_text(msg.from_user)"
)

s = s[:start] + section + s[end:]

# Update home button response.
start = s.index("async def temari_menu(")
end = s.index(
    "@bot.on_message(filters.command('help'))",
    start
)

section = s[start:end]

section = section.replace(
    "welcome_text(q.from_user)",
    "await welcome_text(q.from_user)"
)

s = s[:start] + section + s[end:]

compile(s, str(p), "exec")
p.write_text(s)

print("Welcome message editor installed successfully.")
