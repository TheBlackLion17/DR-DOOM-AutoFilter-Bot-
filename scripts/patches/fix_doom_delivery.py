from pathlib import Path
from datetime import datetime
import py_compile

p = Path("/opt/autofilter_bot/bot.py")
s = p.read_text()

if "DR_DOOM_CUSTOM_FILE_CAPTION_V1" not in s:
    raise SystemExit("Custom caption section not found.")

backup = p.with_name(
    "bot.py.before-delivery-fix-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

# Import the correct Pyrogram parse mode.
if "from pyrogram.enums import ParseMode" not in s:
    s = "from pyrogram.enums import ParseMode\n" + s

# Correct both copy_message and fallback send methods.
s = s.replace(
    'parse_mode="html"',
    'parse_mode=ParseMode.HTML'
)

s = s.replace(
    '"parse_mode": "html"',
    '"parse_mode": ParseMode.HTML'
)

# Fix literal escaped newlines in the custom caption only.
start = s.index("def doom_file_caption(row):")
end = s.index("\n\nasync def deliver(", start)

section = s[start:end]
section = section.replace(r'\\n', r'\n')
s = s[:start] + section + s[end:]

backup.write_text(p.read_text())
p.write_text(s)

try:
    py_compile.compile(str(p), doraise=True)
except Exception:
    p.write_text(backup.read_text())
    raise

print("✅ Delivery fix installed.")
print("✅ Parse mode corrected.")
print("✅ Caption newlines corrected.")
print("✅ Python syntax verified.")
print("Backup:", backup)
