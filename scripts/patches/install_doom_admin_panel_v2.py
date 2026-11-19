from pathlib import Path
from datetime import datetime
import py_compile

p = Path("/opt/autofilter_bot/bot.py")
original = p.read_text()

if "DR_DOOM_ADMIN_PANEL_V2" in original:
    raise SystemExit("Already installed.")

s = original

# Replace only the existing admin keyboard.
start = s.index("def temari_admin_keyboard():")
end = s.index("\n\ndef temari_admin_back():", start)

keyboard = '''
# ===== DR_DOOM_ADMIN_PANEL_V2 =====

def temari_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📝 Welcome Message",
                callback_data="ta:welcome"
            ),
            InlineKeyboardButton(
                "🖼️ Welcome Picture",
                callback_data="ta:picture"
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Menu Links",
                callback_data="ta:links"
            ),
            InlineKeyboardButton(
                "👁️ Preview Welcome",
                callback_data="ta:preview"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Bot Statistics",
                callback_data="ta:stats"
            ),
            InlineKeyboardButton(
                "🔄 Reset Welcome",
                callback_data="ta:reset"
            )
        ],
        [
            InlineKeyboardButton(
                "👑 Manage Admins",
                callback_data="ta:admins"
            ),
            InlineKeyboardButton(
                "📢 Force Sub Channels",
                callback_data="ta:fsub"
            )
        ]
    ])
'''

s = s[:start] + keyboard + s[end:]

# Insert management pages into existing callback handler.
needle = '    if action == "welcome":'

if needle not in s:
    raise SystemExit("Admin callback insertion point missing.")

pages = '''
    if action == "admins":
        if q.from_user.id != OWNER_ID:
            return await q.answer(
                "Only the owner can manage admins.",
                show_alert=True
            )

        ids = sorted(DYNAMIC_ADMINS)

        text = (
            "👑 **DR. DOOM ADMIN MANAGEMENT**\\n\\n"
            "Current admins:\\n"
            + "\\n".join(f"• `{uid}`" for uid in ids)
            + "\\n\\n"
            "**Add admin:**\\n"
            "`/addadmin 123456789`\\n\\n"
            "**Remove admin:**\\n"
            "`/deladmin 123456789`\\n\\n"
            "**List admins:** /admins"
        )

        await q.answer()
        return await q.message.edit_text(
            text,
            reply_markup=temari_admin_back()
        )

    if action == "fsub":
        lines = [
            "📢 **DR. DOOM FORCE SUB CHANNELS**",
            "",
        ]

        if FORCE_CHANNEL:
            lines.append(
                f"Main channel: `{FORCE_CHANNEL}`"
            )

        if FSUB_CHANNELS:
            lines.append("")
            lines.append("Additional channels:")

            for channel in FSUB_CHANNELS:
                lines.append(
                    f"• {channel['title']} "
                    f"— `{channel['channel_id']}`"
                )
        else:
            lines.append("")
            lines.append("No additional channels.")

        lines.extend([
            "",
            "**Add channel:**",
            "`/addfsub -1001234567890 Updates https://t.me/channel`",
            "",
            "**Remove channel:**",
            "`/delfsub -1001234567890`",
            "",
            "**List channels:** /fsublist",
            "",
            "The bot must be an administrator "
            "in every required channel."
        ])

        await q.answer()
        return await q.message.edit_text(
            "\\n".join(lines),
            reply_markup=temari_admin_back()
        )

'''

callback_start = s.index(
    "async def temari_admin_callback("
)

position = s.index(needle, callback_start)

s = s[:position] + pages + s[position:]

# Rebrand the admin panel headings.
s = s.replace(
    "TEMARI ADMIN SETTINGS",
    "DR. DOOM ADMIN SETTINGS"
)

backup = p.with_name(
    "bot.py.before-admin-panel-v2-" +
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

print("✅ DR. DOOM admin panel upgraded.")
print("✅ Existing settings preserved.")
print("✅ Syntax verified.")
print("Backup:", backup)
