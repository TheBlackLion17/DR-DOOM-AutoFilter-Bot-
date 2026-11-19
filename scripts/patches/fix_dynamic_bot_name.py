from pathlib import Path
from datetime import datetime
import shutil

p = Path("bot.py")
s = p.read_text()

marker = "# ===== BOTFATHER DYNAMIC BRANDING V2 ====="

if marker in s:
    raise SystemExit("Dynamic branding V2 already installed.")

anchor = "async def send_start_welcome(msg):"

if anchor not in s:
    raise SystemExit("Welcome handler not found.")

helper = '''
# ===== BOTFATHER DYNAMIC BRANDING V2 =====

async def botfather_name():
    me = await bot.get_me()
    return me.first_name or "Telegram Bot"


async def apply_bot_branding(text):
    name = await botfather_name()

    # Support editable placeholders in custom welcome messages.
    text = text.replace("{bot_name}", name)
    text = text.replace("{BOT_NAME}", name)

    # Replace previous Temari branding.
    text = text.replace("TEMARI", name)
    text = text.replace("Temari", name)

    return text


'''

s = s.replace(anchor, helper + anchor, 1)

# Apply branding when the welcome text is generated.
# This preserves the existing default and custom welcome settings.
s = s.replace(
    "caption=await welcome_text(msg.from_user),",
    "caption=await apply_bot_branding("
    "await welcome_text(msg.from_user)),"
)

s = s.replace(
    "        await welcome_text(msg.from_user),\n"
    "        reply_markup=",
    "        await apply_bot_branding("
    "await welcome_text(msg.from_user)),\n"
    "        reply_markup="
)

# Update callback-navigation page text before editing.
needle = "    await temari_edit_page(q, text, keyboard)"

if needle in s:
    s = s.replace(
        needle,
        "    text = await apply_bot_branding(text)\n"
        "    await temari_edit_page(q, text, keyboard)",
        1
    )
else:
    raise SystemExit("Callback navigation handler not found.")

# Validate the entire file before replacing it.
compile(s, str(p), "exec")

backup = Path(
    "bot.py.before-branding-v2-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(s)

print("✅ Dynamic BotFather branding installed.")
print("Backup:", backup)
