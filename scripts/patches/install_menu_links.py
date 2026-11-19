from pathlib import Path

p = Path("bot.py")
s = p.read_text()

if "# ===== TEMARI MENU LINKS V1 =====" in s:
    raise SystemExit("Menu links already installed.")

required = [
    "async def get_start_picture():",
    "def welcome_keyboard():",
    'if action == "links":',
    "async def temari_admin_callback",
]

missing = [x for x in required if x not in s]
if missing:
    raise SystemExit("Missing: " + ", ".join(missing))

anchor = "@bot.on_message(filters.command('help'))"

code = '''
# ===== TEMARI MENU LINKS V1 =====

TEMARI_LINKS = {
    "search": ("🔎 Search Group", "search_group_link"),
    "updates": ("📢 Updates Channel", "updates_link"),
    "premium": ("💎 Premium Link", "premium_link"),
    "support": ("🛡️ Support Link", "support_link"),
    "website": ("🌐 Website", "website_link"),
    "botupdates": ("🖥️ Bot Updates", "bot_updates_link"),
}

pending_menu_links = {}


async def get_menu_link(key):
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings "
        "WHERE setting_key=%s",
        (key,)
    )
    return row["setting_value"] if row else None


async def save_menu_link(key, value):
    await db.execute(
        "INSERT INTO bot_settings "
        "(setting_key, setting_value) "
        "VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "setting_value=VALUES(setting_value)",
        (key, value)
    )


async def menu_links_keyboard():
    rows = []

    for code, (label, key) in TEMARI_LINKS.items():
        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"tl:edit:{code}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data="ta:home"
        )
    ])

    return InlineKeyboardMarkup(rows)


@bot.on_callback_query(filters.regex(r"^tl:"))
async def temari_links_callback(_, q):
    if not q.from_user or q.from_user.id not in ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    parts = q.data.split(":")

    if len(parts) != 3 or parts[1] != "edit":
        return await q.answer("Invalid action.")

    code = parts[2]

    if code not in TEMARI_LINKS:
        return await q.answer("Unknown link.")

    label, key = TEMARI_LINKS[code]
    current = await get_menu_link(key)

    pending_menu_links[q.from_user.id] = code

    await q.answer()

    await q.message.reply_text(
        f"🔗 **EDIT {label}**\\n\\n"
        f"Current link: {current or 'Not set'}\\n\\n"
        "Send the new HTTPS link as your next message.\\n"
        "Send /cancel to cancel."
    )


@bot.on_message(
    filters.command("cancel") & filters.private
)
async def cancel_menu_edit(_, msg):
    if msg.from_user.id not in ADMINS:
        return

    pending_menu_links.pop(msg.from_user.id, None)
    await msg.reply_text("Cancelled.")


@bot.on_message(
    filters.private
    & filters.text
    & ~filters.regex(r"^/")
, group=-1)
async def capture_menu_link(_, msg):
    if not msg.from_user:
        return

    user_id = msg.from_user.id

    if user_id not in ADMINS:
        return

    code = pending_menu_links.get(user_id)

    if not code:
        return

    url = msg.text.strip()

    if (
        not url.startswith("https://")
        or len(url) > 500
        or any(c.isspace() for c in url)
    ):
        await msg.reply_text(
            "Invalid link. Send a complete HTTPS URL."
        )
        msg.stop_propagation()
        return

    label, key = TEMARI_LINKS[code]

    await save_menu_link(key, url)

    pending_menu_links.pop(user_id, None)

    await msg.reply_text(
        f"✅ **{label} updated!**\\n\\n{url}"
    )

    msg.stop_propagation()


'''

if anchor not in s:
    raise SystemExit("Help handler not found.")

s = s.replace(anchor, code + anchor, 1)

old = """    if action == "links":
        await q.answer()
        return await q.message.edit_text(
            "🔗 **MENU LINKS**\\n\\n"
            "Link editing will be configured next.\\n"
            "Your existing menu buttons remain unchanged.",
            reply_markup=temari_admin_back()
        )"""
new = '''    if action == "links":
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\\\n\\\\n"
            "Select a link to edit:",
            reply_markup=await menu_links_keyboard()
        )'''

if old not in s:
    raise SystemExit(
        "Menu Links placeholder not found. "
        "No changes saved."
    )

s = s.replace(old, new, 1)

compile(s, str(p), "exec")
p.write_text(s)

print("Menu Links Manager installed.")
