from pathlib import Path
from datetime import datetime
import py_compile

p = Path("/opt/autofilter_bot/bot.py")
original = p.read_text()

if "DR_DOOM_ADMIN_FSUB_V1" in original:
    raise SystemExit("Already installed.")

start = original.index("def admin(_, __, msg):")
end = original.index("\n\ndef media_info(", start)

admin_patch = '''
# ===== DR_DOOM_ADMIN_FSUB_V1 =====
OWNER_ID = int(CFG["ADMINS"].split(",")[0].strip())
DYNAMIC_ADMINS = set(ADMINS)
FSUB_CHANNELS = []

def admin(_, __, msg):
    return bool(
        msg.from_user and
        msg.from_user.id in DYNAMIC_ADMINS
    )

async def load_doom_access():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doom_admins (
            user_id BIGINT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS doom_fsub (
            channel_id BIGINT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            invite_link VARCHAR(512) NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    admins = await db.fetchall(
        "SELECT user_id FROM doom_admins"
    )
    DYNAMIC_ADMINS.clear()
    DYNAMIC_ADMINS.update(ADMINS)
    DYNAMIC_ADMINS.update(
        int(r["user_id"]) for r in admins
    )

    channels = await db.fetchall(
        "SELECT * FROM doom_fsub ORDER BY added_at"
    )
    FSUB_CHANNELS[:] = channels

async def doom_access_allowed(user_id):
    return user_id in DYNAMIC_ADMINS

async def doom_owner(user_id):
    return user_id == OWNER_ID

@bot.on_message(filters.command("addadmin") & filters.private)
async def doom_addadmin(_, msg):
    if not msg.from_user or not await doom_owner(msg.from_user.id):
        return await msg.reply_text("Owner only.")

    try:
        uid = int(msg.command[1])
        if uid <= 0:
            raise ValueError
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /addadmin 123456789")

    await db.execute(
        "INSERT IGNORE INTO doom_admins(user_id) VALUES(%s)",
        (uid,)
    )
    DYNAMIC_ADMINS.add(uid)
    await msg.reply_text(f"✅ Admin added: `{uid}`")

@bot.on_message(filters.command("deladmin") & filters.private)
async def doom_deladmin(_, msg):
    if not msg.from_user or not await doom_owner(msg.from_user.id):
        return await msg.reply_text("Owner only.")

    try:
        uid = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /deladmin 123456789")

    if uid in ADMINS:
        return await msg.reply_text(
            "This admin is configured in .env and cannot be removed here."
        )

    await db.execute(
        "DELETE FROM doom_admins WHERE user_id=%s",
        (uid,)
    )
    DYNAMIC_ADMINS.discard(uid)
    await msg.reply_text(f"✅ Admin removed: `{uid}`")

@bot.on_message(filters.command("admins") & filters.private)
async def doom_admin_list(_, msg):
    if not admin(None, None, msg):
        return
    ids = sorted(DYNAMIC_ADMINS)
    await msg.reply_text(
        "👑 DR. DOOM ADMINS\\n\\n" +
        "\\n".join(str(x) for x in ids)
    )

@bot.on_message(filters.command("addfsub") & filters.private)
async def doom_addfsub(_, msg):
    if not admin(None, None, msg):
        return

    parts = msg.text.split(maxsplit=3)
    if len(parts) != 4:
        return await msg.reply_text(
            "Usage:\\n"
            "/addfsub -1001234567890 ChannelName https://t.me/channel"
        )

    try:
        cid = int(parts[1])
    except ValueError:
        return await msg.reply_text("Invalid channel ID.")

    title = parts[2]
    link = parts[3].strip()

    if not link.startswith(("https://t.me/", "https://telegram.me/")):
        return await msg.reply_text("Invalid Telegram join link.")

    try:
        chat = await bot.get_chat(cid)
        me = await bot.get_me()
        membership = await bot.get_chat_member(cid, me.id)
        status = str(membership.status).lower()
        if "administrator" not in status and "owner" not in status:
            return await msg.reply_text(
                "Make the bot an admin in this channel first."
            )
    except Exception as exc:
        log.warning("Force-sub channel validation failed: %s", exc)
        return await msg.reply_text(
            "Bot cannot access this channel. Add it as an admin first."
        )

    await db.execute(
        """INSERT INTO doom_fsub(channel_id,title,invite_link)
           VALUES(%s,%s,%s)
           ON DUPLICATE KEY UPDATE
           title=VALUES(title),
           invite_link=VALUES(invite_link)""",
        (cid, title, link)
    )
    await load_doom_access()
    await msg.reply_text(f"✅ Force-sub channel added: {title}")

@bot.on_message(filters.command("delfsub") & filters.private)
async def doom_delfsub(_, msg):
    if not admin(None, None, msg):
        return

    try:
        cid = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text("Usage: /delfsub -1001234567890")

    await db.execute(
        "DELETE FROM doom_fsub WHERE channel_id=%s",
        (cid,)
    )
    await load_doom_access()
    await msg.reply_text("✅ Force-sub channel removed.")

@bot.on_message(filters.command("fsublist") & filters.private)
async def doom_fsub_list(_, msg):
    if not admin(None, None, msg):
        return

    if not FSUB_CHANNELS:
        return await msg.reply_text("No dynamic force-sub channels.")

    await msg.reply_text(
        "📢 REQUIRED CHANNELS\\n\\n" +
        "\\n".join(
            f"{c['title']} — {c['channel_id']}"
            for c in FSUB_CHANNELS
        )
    )
'''

s = original[:start] + admin_patch + original[end:]

start = s.index("async def is_subscribed(user_id):")
end = s.index("\n\ndef display_name(", start)

fsub_patch = '''
async def is_subscribed(user_id):
    if user_id in DYNAMIC_ADMINS:
        return True

    channel_ids = []
    if FORCE_CHANNEL:
        channel_ids.append(FORCE_CHANNEL)

    channel_ids.extend(
        int(c["channel_id"]) for c in FSUB_CHANNELS
    )

    for cid in dict.fromkeys(channel_ids):
        try:
            member = await bot.get_chat_member(cid, user_id)
            status = str(member.status).lower()
            if (
                "banned" in status or
                "left" in status or
                "kicked" in status
            ):
                return False
        except UserNotParticipant:
            return False
        except RPCError as exc:
            log.warning("Subscription check %s failed: %s", cid, exc)
            return False

    return True


def join_keyboard(file_id=None):
    rows = []

    if FORCE_CHANNEL and CFG.get("FORCE_SUB_LINK"):
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

    if file_id is not None:
        rows.append([
            InlineKeyboardButton(
                "🔄 Check Subscription",
                callback_data=f"get:{file_id}"
            )
        ])

    return InlineKeyboardMarkup(rows) if rows else None
'''

s = s[:start] + fsub_patch + s[end:]

# Load access tables before bot startup.
# Find the actual startup initialization rather than assuming its location.
needle = "await ensure_search_table()"
if needle not in s:
    raise SystemExit(
        "Startup hook not found. No changes written. "
        "Please share the bot startup function."
    )

s = s.replace(
    needle,
    needle + "\n    await load_doom_access()",
    1
)

# Existing admin panels must recognize newly added admins.
s = s.replace(
    "q.from_user.id not in ADMINS",
    "q.from_user.id not in DYNAMIC_ADMINS"
)
s = s.replace(
    "user_id not in ADMINS",
    "user_id not in DYNAMIC_ADMINS"
)

backup = p.with_name(
    "bot.py.before-admin-fsub-" +
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

print("✅ Admin and force-sub upgrade installed.")
print("✅ Python syntax verified.")
print("Backup:", backup)
