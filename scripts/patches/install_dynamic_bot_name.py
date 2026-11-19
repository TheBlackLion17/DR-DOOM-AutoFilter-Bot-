from pathlib import Path
from datetime import datetime
import shutil
import re

p = Path("bot.py")
s = p.read_text()

marker = "# ===== DYNAMIC BOTFATHER NAME V1 ====="

if marker in s:
    raise SystemExit("Dynamic bot name already installed.")

anchor = "def default_welcome_text(user):"

if anchor not in s:
    raise SystemExit("Welcome function not found.")

# Add helper to retrieve the latest Telegram bot display name.
helper = '''
# ===== DYNAMIC BOTFATHER NAME V1 =====

async def current_bot_name():
    me = await bot.get_me()
    return me.first_name or "Telegram Bot"


'''

s = s.replace(anchor, helper + anchor, 1)

# Convert the default welcome function to async.
s = s.replace(
    "def default_welcome_text(user):",
    "async def default_welcome_text(user):",
    1
)

start = s.index("async def default_welcome_text(user):")
end = s.index(
    "@bot.on_message(filters.command(\"start\")",
    start
)

section = s[start:end]

section = section.replace(
    '    name = user.first_name if user else "Friend"',
    '    name = user.first_name if user else "Friend"\n'
    '    bot_name = await current_bot_name()',
    1
)

section = section.replace(
    "TEMARI",
    "{bot_name}"
)

# Convert string literals containing the dynamic name to f-strings.
section = re.sub(
    r'(?m)^(\s*)"(.*\{bot_name\}.*)"',
    r'\\1f"\\2"',
    section
)

s = s[:start] + section + s[end:]

# Update calls to the now-async welcome function.
s = re.sub(
    r'(?<!await )default_welcome_text\(([^()\n]+)\)',
    r'await default_welcome_text(\1)',
    s
)

# Protect the function definition if matched.
s = s.replace(
    "async def await default_welcome_text(user):",
    "async def default_welcome_text(user):"
)

# Replace visible static branding in string literals.
s = s.replace(
    '"🌻 **TEMARI AUTO FILTER**',
    'f"🌻 **{await current_bot_name()}**'
)

s = s.replace(
    '"🎬 **TEMARI COMMANDS**',
    'f"🎬 **{await current_bot_name()} COMMANDS**'
)

s = s.replace(
    '"⚙️ **TEMARI ADMIN SETTINGS**',
    'f"⚙️ **{await current_bot_name()} ADMIN SETTINGS**'
)

s = s.replace(
    '"🔗 **TEMARI MENU LINKS**',
    'f"🔗 **{await current_bot_name()} MENU LINKS**'
)

# Validate before saving.
compile(s, str(p), "exec")

backup = Path(
    "bot.py.before-dynamic-name-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(s)

print("✅ Dynamic BotFather name installed.")
print("Backup:", backup)
