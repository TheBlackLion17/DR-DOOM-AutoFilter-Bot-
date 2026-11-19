from pathlib import Path
from datetime import datetime

p = Path("/opt/autofilter_bot/bot.py")
s = p.read_text()

start = s.find("async def send_start_welcome(msg):")
end = s.find("\n\n@bot.on_message(", start)

if start == -1 or end == -1:
    raise SystemExit("ERROR: Welcome function not found. No changes made.")

if "DR_DOOM_WELCOME_EFFECT_V1" in s:
    raise SystemExit("Already installed. No changes made.")

backup = p.with_name(
    "bot.py.before-welcome-effect-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

new_code = '''
# ===== DR_DOOM_WELCOME_EFFECT_V1 =====

import asyncio
import json
import os
import random
import urllib.request

WELCOME_EFFECTS = [
    "5159385139981059251",  # Heart
    "5104841245755180586",  # Fire
    "5046509860389126442",  # Celebration
]

async def send_welcome_with_effect(msg, picture, caption, keyboard):
    token = os.environ.get("BOT_TOKEN") or CFG.get("BOT_TOKEN")

    if not token:
        raise RuntimeError("BOT_TOKEN missing")

    buttons = []

    if keyboard:
        for row in keyboard.inline_keyboard:
            new_row = []
            for button in row:
                item = {"text": button.text}

                if button.url:
                    item["url"] = button.url
                elif button.callback_data:
                    item["callback_data"] = button.callback_data
                elif button.switch_inline_query is not None:
                    item["switch_inline_query"] = button.switch_inline_query
                elif button.switch_inline_query_current_chat is not None:
                    item["switch_inline_query_current_chat"] = (
                        button.switch_inline_query_current_chat
                    )
                else:
                    raise ValueError("Unsupported welcome button type")

                new_row.append(item)

            buttons.append(new_row)

    payload = {
        "chat_id": msg.chat.id,
        "message_effect_id": random.choice(WELCOME_EFFECTS),
        "reply_markup": {"inline_keyboard": buttons},
    }

    if picture:
        payload["photo"] = picture
        payload["caption"] = caption
        method = "sendPhoto"
    else:
        payload["text"] = caption
        method = "sendMessage"

    def request():
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            result = json.load(response)

        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))

        return result

    return await asyncio.to_thread(request)


async def send_start_welcome(msg):
    picture = await get_start_picture()
    caption = await apply_bot_branding(
        await welcome_text(msg.from_user)
    )
    keyboard = await welcome_keyboard()

    try:
        return await send_welcome_with_effect(
            msg, picture, caption, keyboard
        )
    except Exception:
        log.exception("Animated welcome failed; using original sender")

    if picture:
        try:
            return await msg.reply_photo(
                photo=picture,
                caption=caption,
                reply_markup=keyboard
            )
        except RPCError:
            log.exception("Failed to send welcome picture")

    return await msg.reply_text(
        caption,
        reply_markup=keyboard
    )
'''

backup.write_text(s)
p.write_text(s[:start] + new_code + s[end:])

print("Backup:", backup)
print("Animated welcome effect patch installed.")
