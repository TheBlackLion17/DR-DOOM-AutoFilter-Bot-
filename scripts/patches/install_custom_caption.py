from pathlib import Path
from datetime import datetime
import py_compile

p = Path("/opt/autofilter_bot/bot.py")
source = p.read_text()

marker = "# ===== DR_DOOM_CUSTOM_FILE_CAPTION_V1 ====="

if marker in source:
    raise SystemExit("Custom caption already installed.")

start = source.find("async def deliver(user_id,file_id,origin=None):")
end = source.find("\n\n@bot.on_callback_query(", start)

if start < 0 or end < 0:
    raise SystemExit("Delivery function not found. No changes made.")

backup = p.with_name(
    "bot.py.before-custom-caption-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

replacement = '''
# ===== DR_DOOM_CUSTOM_FILE_CAPTION_V1 =====

def doom_file_caption(row):
    import html

    def safe(value):
        return html.escape(str(value or "Unknown"))

    filename = (
        row.get("file_name")
        or row.get("filename")
        or "Telegram File"
    )

    size = row.get("file_size") or 0

    try:
        size = float(size)
        if size >= 1073741824:
            size_text = f"{size / 1073741824:.2f} GB"
        elif size >= 1048576:
            size_text = f"{size / 1048576:.2f} MB"
        elif size >= 1024:
            size_text = f"{size / 1024:.2f} KB"
        elif size:
            size_text = f"{int(size)} B"
        else:
            size_text = "Unknown"
    except (TypeError, ValueError):
        size_text = "Unknown"

    language = safe(row.get("language"))
    quality = safe(row.get("quality"))

    caption = (
        f"🎬 <b>{safe(filename)}</b>\\\\n\\\\n"
        "╭──── ⚡ DR. DOOM ⚡ ────╮\\\\n"
        f"│ 📦 Size: {size_text}\\\\n"
        f"│ 🌐 Language: {language}\\\\n"
        f"│ 🎞 Quality: {quality}\\\\n"
        "╰──────────────────────╯\\\\n\\\\n"
        "🔥 <b>POWERED BY DR. DOOM</b>"
    )

    return caption[:1024]


async def deliver(user_id,file_id,origin=None):
    if not await is_subscribed(user_id):
        if origin:
            await origin.reply_text(
                "Please join the required channel first.",
                reply_markup=join_keyboard(file_id)
            )
        else:
            await bot.send_message(
                user_id,
                "Please join the required channel first.",
                reply_markup=join_keyboard(file_id)
            )
        return

    row = await db.fetchone(
        "SELECT * FROM files WHERE id=%s",
        (file_id,)
    )

    if not row:
        return await bot.send_message(
            user_id,
            "File not found."
        )

    caption = doom_file_caption(row)

    try:
        sent = await bot.copy_message(
            user_id,
            row["source_channel"],
            row["source_message"],
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

    except RPCError:
        try:
            options = {
                "caption": caption,
                "parse_mode": enums.ParseMode.HTML
            }

            media_type = row["media_type"]

            if media_type == "video":
                sent = await bot.send_video(
                    user_id, row["file_id"], **options
                )
            elif media_type == "audio":
                sent = await bot.send_audio(
                    user_id, row["file_id"], **options
                )
            elif media_type == "animation":
                sent = await bot.send_animation(
                    user_id, row["file_id"], **options
                )
            else:
                sent = await bot.send_document(
                    user_id, row["file_id"], **options
                )

        except RPCError as exc:
            log.warning("Delivery failed: %s", exc)
            return await bot.send_message(
                user_id,
                "File is temporarily unavailable. Contact an admin."
            )

    note = await bot.send_message(
        user_id,
        f"⏳ This file and notice will be deleted after "
        f"{DELETE_SECONDS//60} minute(s)."
    )

    schedule_delete(user_id, [sent.id, note.id])
'''

updated = source[:start] + replacement + source[end:]

# Ensure the ParseMode enum is accessible without modifying imports.
updated = updated.replace(
    "parse_mode=enums.ParseMode.HTML",
    'parse_mode="html"'
)
updated = updated.replace(
    '"parse_mode": enums.ParseMode.HTML',
    '"parse_mode": "html"'
)

backup.write_text(source)
p.write_text(updated)

try:
    py_compile.compile(str(p), doraise=True)
except Exception:
    p.write_text(source)
    raise

print("Backup:", backup)
print("Custom caption installed successfully.")
print("Python syntax verified.")
