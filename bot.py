#!/usr/bin/env python3
"""Safely update DR-DOOM AutoFilter bot.py without touching its other features."""
from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('bot.py')
if not path.is_file():
    raise SystemExit(f'Cannot find {path}. Run in the bot project directory.')
source = path.read_text(encoding='utf-8')
start = source.find('async def deliver(')
end = source.find('@bot.on_callback_query', start)
if start < 0 or end < 0:
    raise SystemExit('Could not identify deliver() boundaries; no changes made.')
new_deliver = '''async def deliver(user_id, file_id, origin=None):
    if not await is_subscribed(user_id):
        keyboard = join_keyboard(file_id)
        if origin is not None and origin.chat and origin.chat.id == user_id:
            await origin.reply_text(
                "Please join the required channel first.",
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                user_id,
                "Please join the required channel first.",
                reply_markup=keyboard
            )
        return

    row = await db.fetchone(
        "SELECT * FROM files WHERE id=%s", (file_id,)
    )
    if not row:
        await bot.send_message(user_id, "File not found.")
        return

    caption = doom_file_caption(row)
    sent = None

    try:
        sent = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=row["source_channel"],
            message_id=row["source_message"],
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except (RPCError, ValueError, KeyError) as exc:
        log.warning(
            "Source copy failed for file %s from %s/%s: %s",
            file_id, row["source_channel"], row["source_message"], exc
        )

    if sent is None:
        options = {"caption": caption, "parse_mode": ParseMode.HTML}
        try:
            media_type = row["media_type"]
            stored_file_id = row["file_id"]
            if media_type == "video":
                sent = await bot.send_video(user_id, stored_file_id, **options)
            elif media_type == "audio":
                sent = await bot.send_audio(user_id, stored_file_id, **options)
            elif media_type == "animation":
                sent = await bot.send_animation(user_id, stored_file_id, **options)
            else:
                sent = await bot.send_document(user_id, stored_file_id, **options)
        except (RPCError, ValueError, KeyError) as exc:
            log.warning("Stored media delivery failed for file %s: %s", file_id, exc)
            await bot.send_message(
                user_id,
                "File is temporarily unavailable. Contact an admin."
            )
            return

    try:
        note = await bot.send_message(
            user_id,
            f"⏳ This file and notice will be deleted after "
            f"{DELETE_SECONDS // 60} minute(s)."
        )
    except RPCError as exc:
        log.warning("Deletion notice failed: %s", exc)
        schedule_delete(user_id, [sent.id])
    else:
        schedule_delete(user_id, [sent.id, note.id])


'''
updated = source[:start] + new_deliver + source[end:]
old = "history = Client('history_reader',api_id=int(CFG['API_ID']),api_hash=CFG['API_HASH'],session_string=CFG['USER_SESSION'],in_memory=True)"
new = '''history = Client(
            "history_reader",
            api_id=int(CFG["API_ID"]),
            api_hash=CFG["API_HASH"],
            session_string=CFG["USER_SESSION"],
            in_memory=True,
            no_updates=True
        )'''
if old in updated:
    updated = updated.replace(old, new, 1)
elif 'no_updates=True' not in updated:
    raise SystemExit('History-reader initialization differs; no changes made.')
try:
    ast.parse(updated, filename=str(path))
except SyntaxError as exc:
    raise SystemExit(f'Updated code did not pass syntax validation: {exc}')
backup = path.with_name(path.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(path, backup)
path.write_text(updated, encoding='utf-8')
print(f'Updated complete file: {path}')
print(f'Backup: {backup}')
print('Syntax: OK')
print('Changes: private delivery fallback + history reader no_updates=True')
