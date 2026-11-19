from pathlib import Path
from datetime import datetime
import re
import shutil

p = Path("bot.py")
s = p.read_text()

if "# ===== TEMARI MENU EDITOR V2 =====" in s:
    raise SystemExit("Menu Editor V2 is already installed.")

checks = [
    "def welcome_keyboard():",
    "# ===== TEMARI MENU LINKS V1 =====",
    "@bot.on_message(filters.command('help'))",
    "reply_markup=await menu_links_keyboard()",
]

for check in checks:
    if check not in s:
        raise SystemExit(f"Missing expected code: {check}")

# Keep the original keyboard as a fallback.
s = s.replace(
    "def welcome_keyboard():",
    "def base_welcome_keyboard():",
    1
)

# Existing call sites need to await the new DB-backed keyboard.
s = s.replace(
    "reply_markup=welcome_keyboard()",
    "reply_markup=await welcome_keyboard()"
)

start = s.index("# ===== TEMARI MENU LINKS V1 =====")
end = s.index(
    "@bot.on_message(filters.command('help'))",
    start
)

new_code = '''
# ===== TEMARI MENU EDITOR V2 =====

from urllib.parse import urlsplit
from pyrogram import StopPropagation

TEMARI_LINKS = {
    "search": ("🔎 MOVIE SEARCH GROUP", "search_group_link"),
    "updates": ("📢 UPDATES CHANNEL", "updates_link"),
    "premium": ("💎 PREMIUM", "premium_link"),
    "support": ("🛡️ SUPPORT", "support_link"),
    "website": ("🌐 WEBSITE", "website_link"),
    "botupdates": ("🖥️ BOT UPDATES", "bot_updates_link"),
}

pending_menu_links = {}


async def get_menu_link(key):
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings WHERE setting_key=%s",
        (key,)
    )
    return row["setting_value"] if row else None


async def save_menu_link(key, value):
    await db.execute(
        "INSERT INTO bot_settings(setting_key, setting_value) "
        "VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
        (key, value)
    )


async def delete_menu_setting(key):
    await db.execute(
        "DELETE FROM bot_settings WHERE setting_key=%s",
        (key,)
    )


async def button_settings(code):
    default, url_key = TEMARI_LINKS[code]
    name = await get_menu_link("menu_name_" + code)
    url = await get_menu_link(url_key)
    visible = await get_menu_link("menu_visible_" + code)
    return (
        name or default,
        url,
        visible != "0"
    )


async def welcome_keyboard():
    original = base_welcome_keyboard()
    rows = []

    search_name, search_url, search_visible = await button_settings("search")
    premium_name, premium_url, premium_visible = await button_settings("premium")

    for row in original.inline_keyboard:
        updated = []

        for button in row:
            action = getattr(button, "callback_data", None)
            label = button.text

            if action == "tm:search" and "MOVIE SEARCH GROUP" in label:
                if not search_visible:
                    continue
                updated.append(
                    InlineKeyboardButton(
                        search_name,
                        url=search_url
                    ) if search_url else InlineKeyboardButton(
                        search_name,
                        callback_data="tm:search"
                    )
                )

            elif action == "tm:premium" and label == "💎 PREMIUM":
                if not premium_visible:
                    continue
                updated.append(
                    InlineKeyboardButton(
                        premium_name,
                        url=premium_url
                    ) if premium_url else InlineKeyboardButton(
                        premium_name,
                        callback_data="tm:premium"
                    )
                )

            else:
                updated.append(button)

        if updated:
            rows.append(updated)

    for code in ("updates", "support", "website", "botupdates"):
        name, url, visible = await button_settings(code)

        if visible and url:
            rows.append([
                InlineKeyboardButton(name, url=url)
            ])

    return InlineKeyboardMarkup(rows)


async def menu_links_keyboard():
    rows = []

    for code in TEMARI_LINKS:
        name, url, visible = await button_settings(code)
        status = "✅" if visible else "🚫"

        rows.append([
            InlineKeyboardButton(
                f"{status} {name}",
                callback_data=f"tl2:open:{code}"
            )
        ])

    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data="ta:home")
    ])

    return InlineKeyboardMarkup(rows)


async def menu_button_editor(code):
    name, url, visible = await button_settings(code)

    text = (
        f"⚙️ **EDIT MENU BUTTON**\\\\n\\\\n"
        f"Name: {name}\\\\n"
        f"URL: {url or 'Not set'}\\\\n"
        f"Visible: {'Yes' if visible else 'No'}\\\\n\\\\n"
        "Choose an option:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✏️ Edit Name",
                callback_data=f"tl2:name:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔗 Edit URL",
                callback_data=f"tl2:url:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "👁️ Show / Hide",
                callback_data=f"tl2:toggle:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Reset Button",
                callback_data=f"tl2:reset:{code}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="tl2:list"
            )
        ]
    ])

    return text, keyboard


@bot.on_callback_query(filters.regex(r"^tl2:"))
async def temari_editor_callback(_, q):
    if not q.from_user or q.from_user.id not in ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    parts = q.data.split(":")
    action = parts[1]

    if action == "list":
        pending_menu_links.pop(q.from_user.id, None)
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\\\n\\\\nSelect a button:",
            reply_markup=await menu_links_keyboard()
        )

    if len(parts) != 3 or parts[2] not in TEMARI_LINKS:
        return await q.answer("Invalid button.", show_alert=True)

    code = parts[2]

    if action in ("name", "url"):
        pending_menu_links[q.from_user.id] = (code, action)

        await q.answer()
        return await q.message.reply_text(
            ("✏️ Send the new button name." if action == "name"
             else "🔗 Send the new HTTPS URL.") +
            "\\\\nSend /cancel to cancel."
        )

    if action == "toggle":
        current = await get_menu_link("menu_visible_" + code)
        await save_menu_link(
            "menu_visible_" + code,
            "1" if current == "0" else "0"
        )

    elif action == "reset":
        _, url_key = TEMARI_LINKS[code]

        for key in (
            "menu_name_" + code,
            "menu_visible_" + code,
            url_key
        ):
            await delete_menu_setting(key)

    elif action != "open":
        return await q.answer("Invalid action.")

    pending_menu_links.pop(q.from_user.id, None)
    text, keyboard = await menu_button_editor(code)

    await q.answer()
    return await q.message.edit_text(
        text,
        reply_markup=keyboard
    )


@bot.on_message(
    filters.command("cancel") & filters.private,
    group=-1
)
async def cancel_menu_edit(_, msg):
    if not msg.from_user or msg.from_user.id not in pending_menu_links:
        return

    pending_menu_links.pop(msg.from_user.id, None)
    await msg.reply_text("✅ Menu editing cancelled.")
    raise StopPropagation


@bot.on_message(
    filters.private & filters.text & ~filters.regex(r"^/"),
    group=-1
)
async def capture_menu_link(_, msg):
    if not msg.from_user:
        return

    user_id = msg.from_user.id

    if user_id not in ADMINS:
        return

    pending = pending_menu_links.get(user_id)

    if not pending:
        return

    code, action = pending
    value = msg.text.strip()

    if action == "name":
        if not value or len(value) > 60 or "\\\\n" in value:
            await msg.reply_text(
                "❌ Name must be 1–60 characters on one line."
            )
            raise StopPropagation

        await save_menu_link("menu_name_" + code, value)

    elif action == "url":
        parsed = urlsplit(value)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(c.isspace() for c in value)
            or len(value) > 500
        ):
            await msg.reply_text(
                "❌ Send a valid HTTPS URL."
            )
            raise StopPropagation

        _, url_key = TEMARI_LINKS[code]
        await save_menu_link(url_key, value)

    pending_menu_links.pop(user_id, None)

    text, keyboard = await menu_button_editor(code)

    await msg.reply_text(
        "✅ **Button updated successfully!**\\\\n\\\\n" + text,
        reply_markup=keyboard
    )

    raise StopPropagation


'''

s = s[:start] + new_code + s[end:]

# Validate new Python code before touching the live file.
compile(s, str(p), "exec")

backup = Path(
    "bot.py.before-menu-editor-v2-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(s)

print("✅ Temari Menu Editor V2 installed.")
print("Backup:", backup)
