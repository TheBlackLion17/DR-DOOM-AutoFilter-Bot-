from pathlib import Path
from datetime import datetime
import shutil

p = Path("bot.py")
s = p.read_text()

marker = "# ===== TEMARI CALLBACK NAVIGATION V1 ====="

if marker in s:
    raise SystemExit("Callback navigation already installed.")

start_marker = '@bot.on_callback_query(filters.regex(r"^tm:"))'
end_marker = "# ===== START PICTURE MANAGER ====="

if start_marker not in s or end_marker not in s:
    raise SystemExit("Required handler markers missing. No changes made.")

start = s.index(start_marker)
end = s.index(end_marker, start)

code = r'''
# ===== TEMARI CALLBACK NAVIGATION V1 =====

from pyrogram.errors import MessageNotModified


def temari_nav_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Back", callback_data="tm:home"
            ),
            InlineKeyboardButton(
                "🏠 Home", callback_data="tm:home"
            )
        ]
    ])


async def temari_edit_page(q, text, keyboard):
    try:
        if q.message.photo:
            return await q.message.edit_caption(
                caption=text,
                reply_markup=keyboard
            )

        return await q.message.edit_text(
            text,
            reply_markup=keyboard
        )

    except MessageNotModified:
        return None


@bot.on_callback_query(filters.regex(r"^tm:"))
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
    await temari_edit_page(q, text, keyboard)


'''

updated = s[:start] + code + s[end:]

compile(updated, str(p), "exec")

backup = Path(
    "bot.py.before-callback-navigation-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(updated)

print("✅ Temari callback navigation installed.")
print("Backup:", backup)
