from pathlib import Path

p = Path("bot.py")
s = p.read_text()

marker = "# ===== TEMARI ADMIN PANEL V1 ====="

if marker in s:
    raise SystemExit("Admin panel already installed.")

required = [
    "async def get_start_picture():",
    "async def welcome_text(user):",
    "def welcome_keyboard():",
    "async def send_start_welcome(msg):",
]

missing = [x for x in required if x not in s]
if missing:
    raise SystemExit("Missing dependencies: " + ", ".join(missing))

anchor = "@bot.on_message(filters.command('help'))"
if anchor not in s:
    raise SystemExit("Help handler not found.")

code = '''
# ===== TEMARI ADMIN PANEL V1 =====

def temari_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📝 Welcome Message",
                callback_data="ta:welcome"
            ),
            InlineKeyboardButton(
                "🖼️ Welcome Picture",
                callback_data="ta:picture"
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Menu Links",
                callback_data="ta:links"
            ),
            InlineKeyboardButton(
                "👁️ Preview Welcome",
                callback_data="ta:preview"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Bot Statistics",
                callback_data="ta:stats"
            ),
            InlineKeyboardButton(
                "🔄 Reset Welcome",
                callback_data="ta:reset"
            )
        ]
    ])


def temari_admin_back():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "⬅️ Back to Settings",
            callback_data="ta:home"
        )
    ]])


@bot.on_message(
    filters.command("adminpanel") & filters.private
)
async def temari_admin_panel(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        "⚙️ **TEMARI ADMIN SETTINGS**\\n\\n"
        "Choose what you want to manage.",
        reply_markup=temari_admin_keyboard()
    )


@bot.on_callback_query(filters.regex(r"^ta:"))
async def temari_admin_callback(_, q):
    if not q.from_user or q.from_user.id not in ADMINS:
        return await q.answer(
            "Admins only.",
            show_alert=True
        )

    action = q.data.split(":", 1)[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            "⚙️ **TEMARI ADMIN SETTINGS**\\n\\n"
            "Choose what you want to manage.",
            reply_markup=temari_admin_keyboard()
        )

    if action == "welcome":
        await q.answer()
        return await q.message.edit_text(
            "📝 **WELCOME MESSAGE SETTINGS**\\n\\n"
            "To change the message, reply to your "
            "new text with:\\n"
            "`/setwelcome`\\n\\n"
            "Other commands:\\n"
            "/viewwelcome — Preview\\n"
            "/resetwelcome — Restore default",
            reply_markup=temari_admin_back()
        )

    if action == "picture":
        await q.answer()
        return await q.message.edit_text(
            "🖼️ **WELCOME PICTURE SETTINGS**\\n\\n"
            "Reply to a photo with:\\n"
            "`/setstartpic`\\n\\n"
            "Other commands:\\n"
            "/editstartpic — Replace picture\\n"
            "/viewstartpic — View picture\\n"
            "/delstartpic — Remove picture",
            reply_markup=temari_admin_back()
        )

    if action == "links":
        await q.answer()
        return await q.message.edit_text(
            "🔗 **MENU LINKS**\\n\\n"
            "Link editing will be configured next.\\n"
            "Your existing menu buttons remain unchanged.",
            reply_markup=temari_admin_back()
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
                reply_markup=welcome_keyboard()
            )

        return await bot.send_message(
            q.from_user.id,
            message,
            reply_markup=welcome_keyboard()
        )

    if action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total, "
            "COUNT(DISTINCT source_channel) AS channels "
            "FROM files"
        )
        await q.answer()
        return await q.message.edit_text(
            "📊 **TEMARI STATISTICS**\\n\\n"
            f"📁 Indexed files: {row['total']}\\n"
            f"📡 Source channels: {row['channels']}",
            reply_markup=temari_admin_back()
        )

    if action == "reset":
        await q.answer()
        return await q.message.edit_text(
            "🔄 **RESET WELCOME MESSAGE**\\n\\n"
            "To restore the default welcome text, "
            "send /resetwelcome.\\n\\n"
            "This does not delete your welcome picture.",
            reply_markup=temari_admin_back()
        )

    await q.answer()


'''

s = s.replace(anchor, code + anchor, 1)

compile(s, str(p), "exec")
p.write_text(s)

print("Temari admin panel installed successfully.")
