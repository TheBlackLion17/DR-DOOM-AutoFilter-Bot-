from pathlib import Path
from datetime import datetime
import shutil

p = Path("bot.py")
s = p.read_text()

marker = "# ===== RANDOM START REACTIONS V1 ====="

if marker in s:
    raise SystemExit("Start reactions already installed.")

anchor = '@bot.on_message(filters.command("start") & filters.private)'

if anchor not in s:
    raise SystemExit("Start handler not found. No changes made.")

helper = '''
# ===== RANDOM START REACTIONS V1 =====

import random
from pyrogram.raw.functions.messages import SendReaction
from pyrogram.raw.types import ReactionEmoji


START_REACTIONS = [
    "⚡", "❤️", "🔥", "🥰", "😍",
    "🎉", "🤩", "😎", "👀", "🫡"
]


async def react_to_start(message):
    emoji = random.choice(START_REACTIONS)

    try:
        peer = await bot.resolve_peer(message.chat.id)

        await bot.invoke(
            SendReaction(
                peer=peer,
                msg_id=message.id,
                reaction=[ReactionEmoji(emoticon=emoji)]
            )
        )

    except Exception as exc:
        log.warning("Start reaction failed: %s", exc)


'''

s = s.replace(anchor, helper + anchor, 1)

# Insert reaction at the beginning of the existing start handler.
start = s.index(anchor)
body_start = s.index("\n", start)
next_line = s.index("\n", body_start + 1)

# Confirm expected function definition.
definition = s[body_start + 1:next_line]

if not definition.startswith("async def "):
    raise SystemExit("Unexpected start handler layout.")

s = (
    s[:next_line + 1]
    + "    await react_to_start(msg)\n"
    + s[next_line + 1:]
)

compile(s, str(p), "exec")

backup = Path(
    "bot.py.before-start-reactions-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(s)

print("✅ Random start reactions installed.")
print("Backup:", backup)
