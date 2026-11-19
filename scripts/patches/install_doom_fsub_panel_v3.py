from pathlib import Path
from datetime import datetime
import py_compile

p = Path("bot.py")
original = p.read_text()
marker = "DR_DOOM_FSUB_PANEL_V3"

if marker in original:
    raise SystemExit("Already installed.")

required = [
    "async def temari_admin_callback(",
    '    if action == "fsub":',
    "def temari_admin_back():",
    "FSUB_CHANNELS",
    "DYNAMIC_ADMINS",
]

for item in required:
    if item not in original:
        raise SystemExit(f"Missing: {item}")

s = original

# Replace existing Force Sub page with interactive menu.
start = s.index('    if action == "fsub":')
end = s.index('    if action == "welcome":', start)

new_page = '''
    if action == "fsub":
        await q.answer()
        return await doom_show_fsub_panel(q.message)

'''

s = s[:start] + new_page + s[end:]

# Insert new handlers before the admin panel keyboard.
position = s.index("def temari_admin_keyboard():")

feature = '''
# ===== DR_DOOM_FSUB_PANEL_V3 =====

DOOM_FSUB_PENDING = {}


def doom_fsub_panel_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Add Channel",
                callback_data="dfsub:add"
            ),
            InlineKeyboardButton(
                "➖ Remove Channel",
                callback_data="dfsub:remove"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 View Channels",
                callback_data="dfsub:list"
            ),
            InlineKeyboardButton(
                "🔗 Edit Join Link",
                callback_data="dfsub:link"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back to Settings",
                callback_data="ta:home"
            )
        ]
    ])


async def doom_show_fsub_panel(message):
    lines = [
        "📢 **DR. DOOM FORCE SUB SETTINGS**",
        "",
        f"Main channel: `{FORCE_CHANNEL}`",
        f"Additional channels: {len(FSUB_CHANNELS)}",
        "",
        "Choose an option below."
    ]

    await message.edit_text(
        "\\n".join(lines),
        reply_markup=doom_fsub_panel_keyboard()
    )


@bot.on_callback_query(filters.regex(r"^dfsub:"))
async def doom_fsub_panel_callback(_, q):
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    action = q.data.split(":", 1)[1]
    uid = q.from_user.id

    if action == "home":
        await q.answer()
        return await doom_show_fsub_panel(q.message)

    if action == "add":
        DOOM_FSUB_PENDING[uid] = {
            "action": "add",
            "step": "channel_id"
        }
        await q.answer()
        return await q.message.reply_text(
            "➕ **ADD FORCE SUB CHANNEL**\\n\\n"
            "Send the Telegram channel ID.\\n\\n"
            "Example: `-1004435370184`\\n\\n"
            "Send /cancel to stop."
        )

    if action == "remove":
        if not FSUB_CHANNELS:
            return await q.answer(
                "No additional channels.",
                show_alert=True
            )

        rows = [
            [
                InlineKeyboardButton(
                    "❌ " + str(c["title"])[:35],
                    callback_data="dfsub:del:" + str(c["channel_id"])
                )
            ]
            for c in FSUB_CHANNELS
        ]
        rows.append([
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="dfsub:home"
            )
        ])

        await q.answer()
        return await q.message.edit_text(
            "➖ **REMOVE CHANNEL**\\n\\n"
            "Tap a channel to remove it.",
            reply_markup=InlineKeyboardMarkup(rows)
        )

    if action == "list":
        lines = ["📋 **REQUIRED CHANNELS**", ""]

        if FORCE_CHANNEL:
            lines.append(f"Main: `{FORCE_CHANNEL}`")

        for c in FSUB_CHANNELS:
            lines.append(
                f"• {c['title']} — `{c['channel_id']}`"
            )

        if not FORCE_CHANNEL and not FSUB_CHANNELS:
            lines.append("No required channels.")

        await q.answer()
        return await q.message.edit_text(
            "\\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="dfsub:home"
                )
            ]])
        )

    if action == "link":
        DOOM_FSUB_PENDING[uid] = {
            "action": "main_link"
        }
        await q.answer()
        return await q.message.reply_text(
            "🔗 **EDIT MAIN CHANNEL JOIN LINK**\\n\\n"
            "Send the public Telegram URL or private invite link.\\n\\n"
            "Example: `https://t.me/YourChannel`\\n\\n"
            "Send /cancel to stop."
        )

    if action.startswith("del:"):
        try:
            cid = int(action.split(":", 1)[1])
        except ValueError:
            return await q.answer("Invalid channel.", show_alert=True)

        if cid not in [
            int(c["channel_id"]) for c in FSUB_CHANNELS
        ]:
            return await q.answer(
                "Channel not found.",
                show_alert=True
            )

        await db.execute(
            "DELETE FROM doom_fsub WHERE channel_id=%s",
            (cid,)
        )
        await load_doom_access()

        await q.answer("Channel removed.")
        return await doom_show_fsub_panel(q.message)


@bot.on_message(filters.private & filters.text, group=-5)
async def doom_fsub_pending_handler(_, msg):
    if not msg.from_user:
        return

    uid = msg.from_user.id
    state = DOOM_FSUB_PENDING.get(uid)

    if not state:
        return

    if uid not in DYNAMIC_ADMINS:
        DOOM_FSUB_PENDING.pop(uid, None)
        return

    text = (msg.text or "").strip()

    if text == "/cancel":
        DOOM_FSUB_PENDING.pop(uid, None)
        await msg.reply_text("Cancelled.")
        raise StopPropagation

    if text.startswith("/"):
        return

    action = state["action"]

    if action == "main_link":
        if not text.startswith(
            ("https://t.me/", "https://telegram.me/")
        ):
            await msg.reply_text(
                "Send a valid Telegram channel URL."
            )
            raise StopPropagation

        # Save the link in MySQL, not .env.
        await db.execute(
            "INSERT INTO bot_settings "
            "(setting_key, setting_value) "
            "VALUES (%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            "setting_value=VALUES(setting_value)",
            ("doom_main_fsub_link", text)
        )

        DOOM_FSUB_PENDING.pop(uid, None)

        await msg.reply_text(
            "✅ Main channel join link saved."
        )
        raise StopPropagation

    if action == "add":
        step = state["step"]

        if step == "channel_id":
            try:
                cid = int(text)
                if cid >= 0:
                    raise ValueError
            except ValueError:
                await msg.reply_text(
                    "Invalid channel ID. Send a negative channel ID."
                )
                raise StopPropagation

            state["channel_id"] = cid
            state["step"] = "title"

            await msg.reply_text(
                "Send a channel name.\\n"
                "Example: Updates"
            )
            raise StopPropagation

        if step == "title":
            if len(text) > 255:
                await msg.reply_text(
                    "Channel name is too long."
                )
                raise StopPropagation

            state["title"] = text
            state["step"] = "link"

            await msg.reply_text(
                "Send the Telegram join link."
            )
            raise StopPropagation

        if step == "link":
            if not text.startswith(
                ("https://t.me/", "https://telegram.me/")
            ):
                await msg.reply_text(
                    "Invalid Telegram URL."
                )
                raise StopPropagation

            cid = state["channel_id"]

            try:
                me = await bot.get_me()
                member = await bot.get_chat_member(cid, me.id)
                status = str(member.status).lower()

                if not (
                    "administrator" in status or
                    "owner" in status
                ):
                    await msg.reply_text(
                        "Make DR. DOOM an admin in "
                        "this channel first."
                    )
                    raise StopPropagation
            except RPCError as exc:
                await msg.reply_text(
                    "Cannot access channel: " + str(exc)
                )
                raise StopPropagation

            await db.execute(
                "INSERT INTO doom_fsub "
                "(channel_id,title,invite_link) "
                "VALUES (%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE "
                "title=VALUES(title), "
                "invite_link=VALUES(invite_link)",
                (cid, state["title"], text)
            )

            await load_doom_access()
            DOOM_FSUB_PENDING.pop(uid, None)

            await msg.reply_text(
                "✅ Force-sub channel added successfully."
            )
            raise StopPropagation
'''

# This handler uses StopPropagation, already imported
# by the existing TEMARI menu editor.
if "from pyrogram import StopPropagation" not in s:
    raise SystemExit("StopPropagation import missing.")

s = s[:position] + feature + "\n\n" + s[position:]

backup = p.with_name(
    "bot.py.before-fsub-panel-v3-" +
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

print("✅ Interactive Force Sub panel installed.")
print("✅ Syntax verified.")
print("Backup:", backup)
