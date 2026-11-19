from pathlib import Path

p = Path("bot.py")
s = p.read_text()

start = s.index(
    "@bot.on_message(filters.command('start') & filters.private)"
)

end = s.index(
    "@bot.on_message(filters.command('help'))",
    start
)

new_code = '''
# ===== TEMARI WELCOME MENU =====

def welcome_keyboard():
    username = CFG["BOT_USERNAME"].lstrip("@")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠", callback_data="tm:home"),
            InlineKeyboardButton("🛡️", callback_data="tm:help"),
            InlineKeyboardButton("💳", callback_data="tm:premium"),
            InlineKeyboardButton("🚀", callback_data="tm:about"),
            InlineKeyboardButton("🖥️", callback_data="tm:stats")
        ],
        [
            InlineKeyboardButton(
                "🔎 MOVIE SEARCH GROUP",
                callback_data="tm:search"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ ADD ME TO YOUR GROUP",
                url=f"https://t.me/{username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton("📜 COMMANDS", callback_data="tm:help"),
            InlineKeyboardButton("🔥 TOP SEARCHING", callback_data="tm:top")
        ],
        [
            InlineKeyboardButton("💎 PREMIUM", callback_data="tm:premium"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="tm:about")
        ]
    ])


def welcome_text(user):
    name = user.first_name if user else "Friend"

    return (
        f"🌻 **HEY {name}, WELCOME TO TEMARI!**\\\\n\\\\n"
        "🎬 **I AM YOUR MOVIES & SERIES AUTO FILTER BOT**\\\\n\\\\n"
        "✨ Search movies and series instantly.\\\\n"
        "📁 Browse indexed files.\\\\n"
        "🔒 Receive files in private chat.\\\\n"
        "⏳ Automatic file deletion.\\\\n\\\\n"
        "🚀 **ADD ME TO YOUR GROUP AND ENJOY!**\\\\n\\\\n"
        "━━━━━━━━━━━━━━━━━━\\\\n"
        "💖 **POWERED BY TEMARI**"
    )


@bot.on_message(filters.command("start") & filters.private)
async def start(_, msg):
    # Preserve existing file-delivery deep links.
    if len(msg.command) > 1 and msg.command[1].startswith("file_"):
        try:
            file_id = int(msg.command[1][5:])
        except ValueError:
            return await msg.reply_text("Invalid file link.")

        return await deliver(msg.from_user.id, file_id, msg)

    await msg.reply_text(
        welcome_text(msg.from_user),
        reply_markup=welcome_keyboard()
    )


@bot.on_callback_query(filters.regex(r"^tm:"))
async def temari_menu(_, q):
    action = q.data.split(":", 1)[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            welcome_text(q.from_user),
            reply_markup=welcome_keyboard()
        )

    if action in ("help", "search"):
        await q.answer()

        return await q.message.reply_text(
            "🎬 **TEMARI COMMANDS**\\\\n\\\\n"
            "🔎 /search name — Search all files\\\\n"
            "🎥 /movies name — Search movies\\\\n"
            "📺 /series name — Search series\\\\n"
            "📜 /help — Show commands\\\\n\\\\n"
            "You can also send a movie or series name directly."
        )

    if action == "top":
        rows = await db.fetchall(
            "SELECT title, COUNT(*) AS total "
            "FROM files "
            "WHERE title IS NOT NULL AND title != '' "
            "GROUP BY title "
            "ORDER BY total DESC LIMIT 10"
        )

        if not rows:
            return await q.answer("No indexed titles yet.", show_alert=True)

        text = "🔥 **MOST INDEXED TITLES**\\\\n\\\\n"

        for i, row in enumerate(rows, 1):
            text += f"{i}. {row['title']} ({row['total']})\\\\n"

        await q.answer()
        return await q.message.reply_text(text)

    if action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total FROM files"
        )

        await q.answer()

        return await q.message.reply_text(
            f"📊 **TEMARI STATISTICS**\\\\n\\\\n"
            f"📁 Indexed files: {row['total']}"
        )

    if action == "premium":
        return await q.answer(
            "Premium features are coming soon!",
            show_alert=True
        )

    if action == "about":
        await q.answer()

        return await q.message.reply_text(
            "🌻 **TEMARI AUTO FILTER**\\\\n\\\\n"
            "🎬 Movies & Series Search\\\\n"
            "📁 MySQL File Indexing\\\\n"
            "🔒 Private File Delivery\\\\n"
            "⏳ Automatic File Deletion\\\\n\\\\n"
            "💖 Powered by Temari"
        )

    await q.answer()


'''

s = s[:start] + new_code + s[end:]

compile(s, str(p), "exec")
p.write_text(s)

print("Temari welcome menu installed successfully.")
