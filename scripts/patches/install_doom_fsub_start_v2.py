from pathlib import Path
from datetime import datetime
import py_compile

p = Path("bot.py")
original = p.read_text()

marker = "DR_DOOM_FSUB_START_V2"

if marker in original:
    raise SystemExit("Already installed.")

start = original.index("async def start(_, msg):")
end = original.index("\n\n# ===== TEMARI CALLBACK NAVIGATION", start)

section = original[start:end]

old = "    await send_start_welcome(msg)"

if section.count(old) != 1:
    raise SystemExit("Welcome call not found exactly once.")

section = section.replace(
    old,
    """    if not await is_subscribed(msg.from_user.id):
        return await msg.reply_text(
            "🔒 **DR. DOOM — FORCE SUBSCRIPTION**\\n\\n"
            "Join all required channels below to access the bot.\\n\\n"
            "After joining, tap Verify Subscription.",
            reply_markup=doom_fsub_keyboard()
        )

    await send_start_welcome(msg)""",
    1
)

helper = '''
# ===== DR_DOOM_FSUB_START_V2 =====

def doom_fsub_keyboard():
    rows = []

    if FORCE_CHANNEL and CFG.get("FORCE_SUB_LINK", "").startswith(
        ("https://t.me/", "https://telegram.me/")
    ):
        rows.append([
            InlineKeyboardButton(
                "📢 Join Main Channel",
                url=CFG["FORCE_SUB_LINK"]
            )
        ])

    for channel in FSUB_CHANNELS:
        rows.append([
            InlineKeyboardButton(
                "📢 " + str(channel["title"])[:45],
                url=channel["invite_link"]
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "✅ Verify Subscription",
            callback_data="doom:verify_fsub"
        )
    ])

    return InlineKeyboardMarkup(rows)


@bot.on_callback_query(filters.regex(r"^doom:verify_fsub$"))
async def doom_verify_fsub(_, q):
    if not q.from_user:
        return await q.answer("User unavailable.", show_alert=True)

    if not await is_subscribed(q.from_user.id):
        return await q.answer(
            "Please join every required channel first.",
            show_alert=True
        )

    await q.answer("Subscription verified!")

    await q.message.delete()

    await send_start_welcome(q.message)
'''

s = original[:start] + section + original[end:]

# Insert helper before start handler.
position = s.index("async def start(_, msg):")

# Keep its decorator attached to the start handler.
decorator = s.rfind("@bot.on_message(", 0, position)

if decorator < 0:
    raise SystemExit("Start decorator not found.")

s = s[:decorator] + helper + "\n\n" + s[decorator:]

backup = p.with_name(
    "bot.py.before-fsub-start-v2-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

backup.write_text(original)
p.write_text(s)

try:
    py_compile.compile(str(p), doraise=True)
except Exception:
    p.write_text(original)
    raise

print("✅ /start force subscription installed.")
print("✅ Verify Subscription button installed.")
print("✅ Syntax verified.")
print("Backup:", backup)
