from pathlib import Path

p = Path("bot.py")
s = p.read_text()

marker = "# ===== TEMARI INTERACTIVE INDEX MANAGER ====="
assert marker in s, "Index manager not found"

helper = '''
# ===== AUTOMATIC SOURCE CHANNEL REGISTRATION =====

import os
import re
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError

async def register_source_channel(channel):
    global CHANNELS

    if channel in CHANNELS:
        return True, "Channel already registered."

    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(channel, me.id)

        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            return False, "Make Temari an administrator first."

        await bot.get_chat(channel)

    except RPCError as exc:
        log.warning(
            "Channel verification failed for %s: %s",
            channel, exc
        )
        return False, "Cannot verify Temari as channel admin."

    env_path = "/opt/autofilter_bot/.env"

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(
        r"(?m)^SOURCE_CHANNELS=(.*)$",
        content
    )

    if not match:
        return False, "SOURCE_CHANNELS missing from .env"

    existing = [
        x.strip()
        for x in match.group(1).strip().strip('"').split(",")
        if x.strip()
    ]

    channels = list(dict.fromkeys(existing + [str(channel)]))

    replacement = "SOURCE_CHANNELS=" + ",".join(channels)

    content = (
        content[:match.start()]
        + replacement
        + content[match.end():]
    )

    temp_path = env_path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)

    os.chmod(temp_path, 0o600)
    os.replace(temp_path, env_path)

    CHANNELS.add(channel)

    return True, "Channel registered successfully."


'''

if "async def register_source_channel(" not in s:
    s = s.replace(marker, helper + marker, 1)

old = '''        if channel not in CHANNELS:
            return await msg.reply_text(
                "Channel not listed in SOURCE_CHANNELS."
            )

        return await msg.reply_text('''

new = '''        if channel not in CHANNELS:
            success, reason = await register_source_channel(channel)

            if not success:
                return await msg.reply_text(
                    f"❌ {reason}"
                )

            await msg.reply_text(
                "✅ New database channel registered!\\\\n"
                f"Channel: {channel}\\\\n"
                "Select Start / Resume Scan to begin."
            )

        return await msg.reply_text('''

assert old in s, "Expected /index handler not found"

s = s.replace(old, new, 1)

p.write_text(s)

print("Automatic channel registration installed.")
