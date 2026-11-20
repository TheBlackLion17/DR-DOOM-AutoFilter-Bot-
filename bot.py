from pyrogram.enums import ParseMode
import asyncio
import logging
import re

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, UserNotParticipant, RPCError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from services import ags_indexer
from services import samantha_logs as slog
from services import group_tracker
from services import broadcast
from services import user_tracker
from config import CFG, ADMINS, CHANNELS, FORCE_CHANNEL, DELETE_SECONDS, PAGE_SIZE
from services.parser import parse_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('autofilter')
bot = Client('autofilter_bot', api_id=int(CFG['API_ID']), api_hash=CFG['API_HASH'], bot_token=CFG['BOT_TOKEN'])
history = None
scans = {}
cleanup_tasks = set()



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
    slog.emit_background(f"🛡️ <b>admin added</b>\nActor: <code>{msg.from_user.id}</code>\nTarget: <code>{uid}</code>")
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
    slog.emit_background(f"🛡️ <b>admin removed</b>\nActor: <code>{msg.from_user.id}</code>\nTarget: <code>{uid}</code>")
    await msg.reply_text(f"✅ Admin removed: `{uid}`")

@bot.on_message(filters.command("admins") & filters.private)
async def doom_admin_list(_, msg):
    if not admin(None, None, msg):
        return
    ids = sorted(DYNAMIC_ADMINS)
    await msg.reply_text(
        "👑 DR. DOOM ADMINS\n\n" +
        "\n".join(str(x) for x in ids)
    )

@bot.on_message(filters.command("addfsub") & filters.private)
async def doom_addfsub(_, msg):
    if not admin(None, None, msg):
        return

    parts = msg.text.split(maxsplit=3)
    if len(parts) != 4:
        return await msg.reply_text(
            "Usage:\n"
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
    slog.emit_background(f"🛡️ <b>force-sub added</b>\nActor: <code>{msg.from_user.id}</code>")

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
    slog.emit_background(f"🛡️ <b>force-sub removed</b>\nActor: <code>{msg.from_user.id}</code>")

@bot.on_message(filters.command("fsublist") & filters.private)
async def doom_fsub_list(_, msg):
    if not admin(None, None, msg):
        return

    if not FSUB_CHANNELS:
        return await msg.reply_text("No dynamic force-sub channels.")

    await msg.reply_text(
        "📢 REQUIRED CHANNELS\n\n" +
        "\n".join(
            f"{c['title']} — {c['channel_id']}"
            for c in FSUB_CHANNELS
        )
    )


def media_info(msg):
    for typ in ('document', 'video', 'audio', 'animation'):
        obj = getattr(msg, typ, None)
        if obj and getattr(obj, 'file_id', None):
            return typ, obj
    return None, None


async def index_message(msg):
    typ, media = media_info(msg)
    if not media or not msg.chat:
        return False
    filename = getattr(media, 'file_name', None) or (msg.caption or '')[:200] or f'{typ}_{msg.id}'
    parsed = parse_name(filename)
    result = await db.execute('''INSERT INTO files
        (file_unique_id,file_id,source_channel,source_message,file_name,title,kind,season,episode,quality,language,file_size,media_type,caption)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE file_id=VALUES(file_id), file_name=VALUES(file_name),
        title=VALUES(title), kind=VALUES(kind), season=VALUES(season), episode=VALUES(episode),
        quality=VALUES(quality), language=VALUES(language), caption=VALUES(caption)''',
        (media.file_unique_id,media.file_id,msg.chat.id,msg.id,filename[:1024],parsed['title'],parsed['kind'],parsed['season'],parsed['episode'],parsed['quality'],parsed['language'],getattr(media,'file_size',0) or 0,typ,msg.caption))
    if result:
        slog.emit_background(
            "📥 <b>File indexed</b>\n"
            f"Channel: <code>{msg.chat.id}</code>\n"
            f"Message: <code>{msg.id}</code>",
            key=f"indexed:{msg.chat.id}", cooldown=60,
        )
    return bool(result)



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


def display_name(row):
    extra = []
    if row['season'] is not None:
        extra.append(f"S{row['season']:02d}")
    if row['episode'] is not None:
        extra.append(f"E{row['episode']:02d}")
    for key in ('quality','language'):
        if row[key]:
            extra.append(str(row[key]))
    return (row['title'][:34] + ('…' if len(row['title']) > 34 else '')) + (' • ' + ' • '.join(extra) if extra else '')


def filters_sql(query, kind='all', quality='all', language='all'):
    where = ['(title LIKE %s OR file_name LIKE %s)']
    pattern = '%' + query[:100].replace('%','\\%').replace('_','\\_') + '%'
    args = [pattern,pattern]
    if kind in ('movie','series'):
        where.append('kind=%s')
        args.append(kind)
    if quality != 'all':
        where.append('quality=%s')
        args.append(quality)
    if language != 'all':
        where.append('language=%s')
        args.append(language)
    return ' AND '.join(where), args


async def search_results(query, page=0, kind='all', quality='all', language='all'):
    clause,args = filters_sql(query,kind,quality,language)
    total = await db.fetchone(f'SELECT COUNT(*) AS n FROM files WHERE {clause}', args)
    rows = await db.fetchall(f'SELECT * FROM files WHERE {clause} ORDER BY title,season,episode,id LIMIT %s OFFSET %s', (*args,PAGE_SIZE,page*PAGE_SIZE))
    return rows,total['n']



# ===== DR_DOOM_SEARCH_V2 =====

def doom_size(value):
    try:
        size = int(value or 0)
    except (ValueError, TypeError):
        return "Unknown"

    if size >= 1073741824:
        return f"{size / 1073741824:.2f} GB"
    if size >= 1048576:
        return f"{size / 1048576:.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size} B" if size else "Unknown"


def doom_result_name(row):
    name = str(
        row.get("file_name")
        or row.get("title")
        or "Unknown File"
    )

    size = doom_size(row.get("file_size"))

    season = row.get("season")
    episode = row.get("episode")
    quality = row.get("quality")

    details = [size]

    if season is not None and episode is not None:
        details.append(
            f"S{int(season):02d}E{int(episode):02d}"
        )

    if quality:
        details.append(str(quality))

    prefix = " ".join(f"[{x}]" for x in details)

    # Telegram button text should remain readable.
    return f"{prefix} {name}"[:110]


def doom_search_text(query, total, page):
    pages = max(
        1,
        (total + PAGE_SIZE - 1) // PAGE_SIZE
    )

    return (
        "🎬 **DR. DOOM AUTO FILTER**\n\n"
        f"🔎 **Search:** {query}\n"
        f"📂 **Available files:** {total}\n"
        f"📄 **Page:** {page + 1}/{pages}\n\n"
        "✨ Select a file below to receive it "
        "in your private chat."
    )


def result_markup(rows, page, total, search_id):
    buttons = []

    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                doom_result_name(row),
                callback_data=f"get:{row['id']}"
            )
        ])

    pages = max(
        1,
        (total + PAGE_SIZE - 1) // PAGE_SIZE
    )

    if pages > 1:
        previous = (
            f"page:{search_id}:{page - 1}"
            if page > 0
            else "doom:noop"
        )

        following = (
            f"page:{search_id}:{page + 1}"
            if page + 1 < pages
            else "doom:noop"
        )

        buttons.append([
            InlineKeyboardButton(
                "◀️ BACK",
                callback_data=previous
            ),
            InlineKeyboardButton(
                f"📅 {page + 1}/{pages}",
                callback_data="doom:noop"
            ),
            InlineKeyboardButton(
                "NEXT ▶️",
                callback_data=following
            )
        ])

    return InlineKeyboardMarkup(buttons)


@bot.on_callback_query(
    filters.regex(r"^doom:noop$")
)
async def doom_noop(_, q):
    await q.answer()


# Search context is stored in MySQL so pagination works after restarts.
async def ensure_search_table():
    await db.execute('''CREATE TABLE IF NOT EXISTS searches (
      id BIGINT AUTO_INCREMENT PRIMARY KEY,
      query VARCHAR(255) NOT NULL,
      owner_id BIGINT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      KEY idx_created(created_at)
    )''')


async def search_and_reply(msg, query):
    query = query.strip()[:100]
    if len(query) < 2:
        return
    rows,total = await search_results(query)
    if not rows:
        if msg.chat.type.name.lower() == 'private':
            await msg.reply_text('No matching files found.')
        return
    sid = await db.insert_id('INSERT INTO searches(query,owner_id) VALUES(%s,%s)',(query,msg.from_user.id if msg.from_user else 0))
    await msg.reply_text(
        doom_search_text(query, total, 0),
        reply_markup=result_markup(rows, 0, total, sid)
    )


@bot.on_message(filters.channel)
async def channel_index(_, msg):
    if msg.chat.id in CHANNELS:
        try:
            await index_message(msg)
        except Exception:
            log.exception('Indexing failed for %s/%s',msg.chat.id,msg.id)
            slog.emit_background(f"❌ <b>Live indexing failed</b>\nChannel: <code>{msg.chat.id}</code>\nMessage: <code>{msg.id}</code>", key=f"live-index-failure:{msg.chat.id}", cooldown=60)



# ===== TEMARI WELCOME MENU =====

def base_welcome_keyboard():
    username = CFG["BOT_USERNAME"].lstrip("@")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠", callback_data="tm:home"),
            InlineKeyboardButton("🛡️", callback_data="tm:help"),
            InlineKeyboardButton("💳", callback_data="tm:premium"),
            InlineKeyboardButton("🚀", callback_data="tm:about"),
            InlineKeyboardButton("🖥️", callback_data="tm:stats")
        ],
        [
            InlineKeyboardButton(
                "🔎 MOVIE SEARCH GROUP",
                callback_data="tm:search"
            )
        ],
        [
            InlineKeyboardButton(
                "➕ ADD ME TO YOUR GROUP",
                url=f"https://t.me/{username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton("📜 COMMANDS", callback_data="tm:help"),
            InlineKeyboardButton("🔥 TOP SEARCHING", callback_data="tm:top")
        ],
        [
            InlineKeyboardButton("💎 PREMIUM", callback_data="tm:premium"),
            InlineKeyboardButton("ℹ️ ABOUT", callback_data="tm:about")
        ]
    ])


def default_welcome_text(user):
    name = user.first_name if user else "Friend"

    return (
        f"🌻 **HEY {name}, WELCOME TO TEMARI!**\n\n"
        "🎬 **I AM YOUR MOVIES & SERIES AUTO FILTER BOT**\n\n"
        "✨ Search movies and series instantly.\n"
        "📁 Browse indexed files.\n"
        "🔒 Receive files in private chat.\n"
        "⏳ Automatic file deletion.\n\n"
        "🚀 **ADD ME TO YOUR GROUP AND ENJOY!**\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💖 **POWERED BY TEMARI**"
    )



# ===== RANDOM START REACTIONS V1 =====

import random
from pyrogram.raw.functions.messages import SendReaction
from pyrogram.raw.types import ReactionEmoji


START_REACTIONS = [
    "⚡", "❤️", "🔥", "🥰", "😍",
    "🎉", "🤩", "😎", "👀", "🫡"
]



async def react_to_start(message):
    import asyncio
    import json
    import urllib.request
    import urllib.error

    emoji = random.choice(START_REACTIONS)

    token = CFG.get("BOT_TOKEN")

    if not token:
        log.warning("Reaction skipped: BOT_TOKEN missing")
        return

    url = (
        f"https://api.telegram.org/bot{token}/"
        "setMessageReaction"
    )

    payload = json.dumps({
        "chat_id": message.chat.id,
        "message_id": message.id,
        "reaction": [
            {
                "type": "emoji",
                "emoji": emoji
            }
        ]
    }).encode()

    def send_reaction():
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            request, timeout=10
        ) as response:
            return json.loads(response.read())

    try:
        result = await asyncio.to_thread(send_reaction)

        if not result.get("ok"):
            log.warning(
                "Reaction rejected: %s",
                result.get("description")
            )

    except urllib.error.HTTPError as exc:
        # Never log the request URL: it contains the bot token.
        try:
            detail = json.loads(exc.read()).get(
                "description", "HTTP error"
            )
        except Exception:
            detail = "HTTP error"

        log.warning("Reaction failed: %s", detail)

    except Exception as exc:
        log.warning(
            "Reaction request failed: %s",
            type(exc).__name__
        )



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


@bot.on_message(filters.command("start") & filters.private)
async def start(_, msg):
    slog.emit_background(f"👤 <b>Bot /start</b>\nUser: <code>{msg.from_user.id}</code>\nName: {slog._safe(msg.from_user.first_name)}\nUsername: {slog._safe(msg.from_user.username) if msg.from_user.username else 'Not set'}\n🕒 {slog._stamp()}", key=f"start:{msg.from_user.id}", cooldown=3600)
    await react_to_start(msg)
    # Preserve existing file-delivery deep links.
    if len(msg.command) > 1 and msg.command[1].startswith("file_"):
        try:
            file_id = int(msg.command[1][5:])
        except ValueError:
            return await msg.reply_text("Invalid file link.")

        return await deliver(msg.from_user.id, file_id, msg)

    if not await is_subscribed(msg.from_user.id):
        return await msg.reply_text(
            "🔒 **DR. DOOM — FORCE SUBSCRIPTION**\n\n"
            "Join all required channels below to access the bot.\n\n"
            "After joining, tap Verify Subscription.",
            reply_markup=doom_fsub_keyboard()
        )

    await send_start_welcome(msg)



# ===== TEMARI CALLBACK NAVIGATION V1 =====

from pyrogram.errors import MessageNotModified


def temari_nav_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Back", callback_data="tm:home"
            ),
            InlineKeyboardButton(
                "🏠 Home", callback_data="tm:home"
            )
        ]
    ])


async def temari_edit_page(q, text, keyboard):
    try:
        if q.message.photo:
            return await q.message.edit_caption(
                caption=text,
                reply_markup=keyboard
            )

        return await q.message.edit_text(
            text,
            reply_markup=keyboard
        )

    except MessageNotModified:
        return None


@bot.on_callback_query(filters.regex(r"^tm:"))
async def temari_menu(_, q):
    action = q.data.split(":", 1)[1]

    if action == "home":
        text = await welcome_text(q.from_user)
        keyboard = await welcome_keyboard()

    elif action in ("help", "search"):
        text = (
            "🎬 **TEMARI COMMANDS**\n\n"
            "🔎 /search name — Search all files\n"
            "🎥 /movies name — Search movies\n"
            "📺 /series name — Search series\n"
            "📜 /help — Show commands\n\n"
            "You can also send a movie or series "
            "name directly."
        )
        keyboard = temari_nav_keyboard()

    elif action == "top":
        rows = await db.fetchall(
            "SELECT title, COUNT(*) AS total "
            "FROM files "
            "WHERE title IS NOT NULL AND title != '' "
            "GROUP BY title "
            "ORDER BY total DESC LIMIT 10"
        )

        text = "🔥 **MOST INDEXED TITLES**\n\n"

        if rows:
            for i, row in enumerate(rows, 1):
                title = str(row["title"] or "Unknown")
                title = title.replace("\n", " ")[:55]
                text += (
                    f"{i}. {title} "
                    f"({row['total']})\n"
                )
        else:
            text += "No indexed titles yet."

        keyboard = temari_nav_keyboard()

    elif action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total FROM files"
        )

        total = row["total"] if row else 0

        text = (
            "📊 **TEMARI STATISTICS**\n\n"
            f"📁 Indexed files: {total}"
        )
        keyboard = temari_nav_keyboard()

    elif action == "premium":
        text = (
            "💎 **TEMARI PREMIUM**\n\n"
            "Premium features are coming soon!"
        )
        keyboard = temari_nav_keyboard()

    elif action == "about":
        text = (
            "🌻 **TEMARI AUTO FILTER**\n\n"
            "🎬 Movies & Series Search\n"
            "📁 MySQL File Indexing\n"
            "🔒 Private File Delivery\n"
            "⏳ Automatic File Deletion\n\n"
            "💖 Powered by Temari"
        )
        keyboard = temari_nav_keyboard()

    else:
        return await q.answer(
            "Unknown menu option.",
            show_alert=True
        )

    # Telegram photo captions have a 1024-character limit.
    if q.message.photo and len(text) > 1000:
        text = text[:990] + "\n..."

    await q.answer()
    text = await apply_bot_branding(text)
    await temari_edit_page(q, text, keyboard)


# ===== START PICTURE MANAGER =====

async def ensure_start_picture_table():
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT
        )
    """)


async def get_start_picture():
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings "
        "WHERE setting_key=%s",
        ("start_picture",)
    )
    return row["setting_value"] if row else None



# ===== TEMARI WELCOME MESSAGE EDITOR =====

async def welcome_text(user):
    row = await db.fetchone(
        "SELECT setting_value FROM bot_settings "
        "WHERE setting_key=%s",
        ("welcome_message",)
    )

    if row and row["setting_value"]:
        name = user.first_name if user else "Friend"

        return row["setting_value"].replace(
            "{name}", name
        )

    return default_welcome_text(user)


@bot.on_message(
    filters.command(["setwelcome", "editwelcome"])
    & filters.private
)
async def set_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    content = msg.text.partition(" ")[2].strip()

    if not content and msg.reply_to_message:
        content = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ""
        )

    if not content:
        return await msg.reply_text(
            "Reply to a text message with /setwelcome "
            "or send:\n"
            "/setwelcome Your welcome message\n\n"
            "Use {name} for the user's first name."
        )

    if len(content) > 1024:
        return await msg.reply_text(
            "Welcome message must be 1024 characters "
            "or fewer to support photo captions."
        )

    await db.execute(
        """
        INSERT INTO bot_settings
        (setting_key, setting_value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
        setting_value=VALUES(setting_value)
        """,
        ("welcome_message", content)
    )

    await msg.reply_text(
        "✅ Welcome message updated!\n"
        "Send /start to preview."
    )


@bot.on_message(
    filters.command("viewwelcome") & filters.private
)
async def view_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        await apply_bot_branding(await welcome_text(msg.from_user)),
        reply_markup=await welcome_keyboard()
    )


@bot.on_message(
    filters.command("resetwelcome") & filters.private
)
async def reset_welcome_message(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await db.execute(
        "DELETE FROM bot_settings WHERE setting_key=%s",
        ("welcome_message",)
    )

    await msg.reply_text(
        "✅ Default welcome message restored."
    )



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



# ===== DR_DOOM_WELCOME_EFFECT_V1 =====

import asyncio
import json
import os
import random
import urllib.request

WELCOME_EFFECTS = [
    "5159385139981059251",  # Heart
    "5104841245755180586",  # Fire
    "5046509860389126442",  # Celebration
]

async def send_welcome_with_effect(msg, picture, caption, keyboard):
    token = os.environ.get("BOT_TOKEN") or CFG.get("BOT_TOKEN")

    if not token:
        raise RuntimeError("BOT_TOKEN missing")

    buttons = []

    if keyboard:
        for row in keyboard.inline_keyboard:
            new_row = []
            for button in row:
                item = {"text": button.text}

                if button.url:
                    item["url"] = button.url
                elif button.callback_data:
                    item["callback_data"] = button.callback_data
                elif button.switch_inline_query is not None:
                    item["switch_inline_query"] = button.switch_inline_query
                elif button.switch_inline_query_current_chat is not None:
                    item["switch_inline_query_current_chat"] = (
                        button.switch_inline_query_current_chat
                    )
                else:
                    raise ValueError("Unsupported welcome button type")

                new_row.append(item)

            buttons.append(new_row)

    payload = {
        "chat_id": msg.chat.id,
        "message_effect_id": random.choice(WELCOME_EFFECTS),
        "reply_markup": {"inline_keyboard": buttons},
    }

    if picture:
        payload["photo"] = picture
        payload["caption"] = caption
        method = "sendPhoto"
    else:
        payload["text"] = caption
        method = "sendMessage"

    def request():
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            result = json.load(response)

        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))

        return result

    return await asyncio.to_thread(request)


async def send_start_welcome(msg):
    picture = await get_start_picture()
    caption = await apply_bot_branding(
        await welcome_text(msg.from_user)
    )
    keyboard = await welcome_keyboard()

    try:
        return await send_welcome_with_effect(
            msg, picture, caption, keyboard
        )
    except Exception:
        log.exception("Animated welcome failed; using original sender")

    if picture:
        try:
            return await msg.reply_photo(
                photo=picture,
                caption=caption,
                reply_markup=keyboard
            )
        except RPCError:
            log.exception("Failed to send welcome picture")

    return await msg.reply_text(
        caption,
        reply_markup=keyboard
    )


@bot.on_message(
    filters.command(["setstartpic", "editstartpic"])
    & filters.private
)
async def set_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    photo = None

    if msg.reply_to_message and msg.reply_to_message.photo:
        photo = msg.reply_to_message.photo

    if not photo:
        return await msg.reply_text(
            "📸 Reply to a photo with /setstartpic "
            "or /editstartpic."
        )

    await db.execute("""
        INSERT INTO bot_settings(setting_key, setting_value)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
        setting_value=VALUES(setting_value)
    """, ("start_picture", photo.file_id))

    await msg.reply_text(
        "✅ Temari welcome picture saved successfully!\n"
        "Send /start to see it."
    )


@bot.on_message(filters.command("delstartpic") & filters.private)
async def delete_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await db.execute(
        "DELETE FROM bot_settings WHERE setting_key=%s",
        ("start_picture",)
    )

    await msg.reply_text(
        "✅ Welcome picture removed. "
        "The /start menu will use text again."
    )


@bot.on_message(filters.command("viewstartpic") & filters.private)
async def view_start_picture(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    picture = await get_start_picture()

    if not picture:
        return await msg.reply_text(
            "No welcome picture is currently configured."
        )

    await msg.reply_photo(
        picture,
        caption="📸 Current Temari welcome picture"
    )



# ===== TEMARI ADMIN PANEL V1 =====


# ===== DR_DOOM_ADMIN_PANEL_V2 =====


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
        "\n".join(lines),
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
            "➕ **ADD FORCE SUB CHANNEL**\n\n"
            "Send the Telegram channel ID.\n\n"
            "Example: `-1004435370184`\n\n"
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
            "➖ **REMOVE CHANNEL**\n\n"
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
            "\n".join(lines),
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
            "🔗 **EDIT MAIN CHANNEL JOIN LINK**\n\n"
            "Send the public Telegram URL or private invite link.\n\n"
            "Example: `https://t.me/YourChannel`\n\n"
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
                "Send a channel name.\n"
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


def temari_admin_back():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "⬅️ Back to Settings",
            callback_data="ta:home"
        )
    ]])


@bot.on_message(
    filters.command("adminpanel") & filters.private
)
async def temari_admin_panel(_, msg):
    if not admin(None, None, msg):
        return await msg.reply_text("Admins only.")

    await msg.reply_text(
        "⚙️ **DR. DOOM ADMIN SETTINGS**\n\n"
        "Choose what you want to manage.",
        reply_markup=temari_admin_keyboard()
    )


@bot.on_callback_query(filters.regex(r"^ta:"))
async def temari_admin_callback(_, q):
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer(
            "Admins only.",
            show_alert=True
        )

    action = q.data.split(":", 1)[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            "⚙️ **DR. DOOM ADMIN SETTINGS**\n\n"
            "Choose what you want to manage.",
            reply_markup=temari_admin_keyboard()
        )


    if action == "admins":
        if q.from_user.id != OWNER_ID:
            return await q.answer(
                "Only the owner can manage admins.",
                show_alert=True
            )

        ids = sorted(DYNAMIC_ADMINS)

        text = (
            "👑 **DR. DOOM ADMIN MANAGEMENT**\n\n"
            "Current admins:\n"
            + "\n".join(f"• `{uid}`" for uid in ids)
            + "\n\n"
            "**Add admin:**\n"
            "`/addadmin 123456789`\n\n"
            "**Remove admin:**\n"
            "`/deladmin 123456789`\n\n"
            "**List admins:** /admins"
        )

        await q.answer()
        return await q.message.edit_text(
            text,
            reply_markup=temari_admin_back()
        )


    if action == "fsub":
        await q.answer()
        return await doom_show_fsub_panel(q.message)

    if action == "welcome":
        await q.answer()
        return await q.message.edit_text(
            "📝 **WELCOME MESSAGE SETTINGS**\n\n"
            "To change the message, reply to your "
            "new text with:\n"
            "`/setwelcome`\n\n"
            "Other commands:\n"
            "/viewwelcome — Preview\n"
            "/resetwelcome — Restore default",
            reply_markup=temari_admin_back()
        )

    if action == "picture":
        await q.answer()
        return await q.message.edit_text(
            "🖼️ **WELCOME PICTURE SETTINGS**\n\n"
            "Reply to a photo with:\n"
            "`/setstartpic`\n\n"
            "Other commands:\n"
            "/editstartpic — Replace picture\n"
            "/viewstartpic — View picture\n"
            "/delstartpic — Remove picture",
            reply_markup=temari_admin_back()
        )

    if action == "links":
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\n\\n"
            "Select a link to edit:",
            reply_markup=await menu_links_keyboard()
        )

    if action == "preview":
        await q.answer()
        picture = await get_start_picture()
        message = await welcome_text(q.from_user)

        if picture:
            return await bot.send_photo(
                q.from_user.id,
                picture,
                caption=message,
                reply_markup=await welcome_keyboard()
            )

        return await bot.send_message(
            q.from_user.id,
            message,
            reply_markup=await welcome_keyboard()
        )

    if action == "stats":
        row = await db.fetchone(
            "SELECT COUNT(*) AS total, "
            "COUNT(DISTINCT source_channel) AS channels "
            "FROM files"
        )
        await q.answer()
        return await q.message.edit_text(
            "📊 **TEMARI STATISTICS**\n\n"
            f"📁 Indexed files: {row['total']}\n"
            f"📡 Source channels: {row['channels']}",
            reply_markup=temari_admin_back()
        )

    if action == "reset":
        await q.answer()
        return await q.message.edit_text(
            "🔄 **RESET WELCOME MESSAGE**\n\n"
            "To restore the default welcome text, "
            "send /resetwelcome.\n\n"
            "This does not delete your welcome picture.",
            reply_markup=temari_admin_back()
        )

    await q.answer()




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
        f"⚙️ **EDIT MENU BUTTON**\\n\\n"
        f"Name: {name}\\n"
        f"URL: {url or 'Not set'}\\n"
        f"Visible: {'Yes' if visible else 'No'}\\n\\n"
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
    if not q.from_user or q.from_user.id not in DYNAMIC_ADMINS:
        return await q.answer("Admins only.", show_alert=True)

    parts = q.data.split(":")
    action = parts[1]

    if action == "list":
        pending_menu_links.pop(q.from_user.id, None)
        await q.answer()
        return await q.message.edit_text(
            "🔗 **TEMARI MENU LINKS**\\n\\nSelect a button:",
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
            "\\nSend /cancel to cancel."
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

    if user_id not in DYNAMIC_ADMINS:
        return

    pending = pending_menu_links.get(user_id)

    if not pending:
        return

    code, action = pending
    value = msg.text.strip()

    if action == "name":
        if not value or len(value) > 60 or "\\n" in value:
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
        "✅ **Button updated successfully!**\\n\\n" + text,
        reply_markup=keyboard
    )

    raise StopPropagation


@bot.on_message(filters.command('help'))
async def help_command(_,msg):
    await msg.reply_text('**Commands**\n/search <name> — Find files\n/movies <name> — Movies only\n/series <name> — Series only\n\n**Admin:** /stats, /index <channel_id>, /progress <channel_id>')


@bot.on_message(filters.command(['search','movies','series']))
async def command_search(_,msg):
    query = msg.text.partition(' ')[2].strip()
    if not query:
        return await msg.reply_text('Example: /search Stranger Things')
    kind = {'movies':'movie','series':'series'}.get(msg.command[0].lower(),'all')
    # Add kind to query lookup by using dedicated search context syntax.
    if kind == 'all':
        return await search_and_reply(msg,query)
    rows,total = await search_results(query,kind=kind)
    if not rows:
        return await msg.reply_text('No matching files found.')
    sid = await db.insert_id('INSERT INTO searches(query,owner_id) VALUES(%s,%s)',(f'{kind}|{query}',msg.from_user.id))
    await msg.reply_text(
        doom_search_text(query, total, 0),
        reply_markup=result_markup(rows, 0, total, sid)
    )


@bot.on_message(filters.text & ~filters.command(['start','help','search','movies','series','stats','index','progress']) & (filters.private | filters.group))
async def auto_search(_,msg):
    if msg.from_user and not msg.from_user.is_bot and msg.text and not msg.text.startswith('/'):
        await search_and_reply(msg,msg.text)


@bot.on_callback_query(filters.regex(r'^page:\d+:\d+$'))
async def paginate(_,q):
    _,sid,page = q.data.split(':')
    page = int(page)
    if page > 10000:
        return await q.answer('Page limit reached',show_alert=True)
    record = await db.fetchone('SELECT * FROM searches WHERE id=%s',(int(sid),))
    if not record:
        return await q.answer('Search expired',show_alert=True)
    raw = record['query']
    kind = 'all'
    if raw.startswith(('movie|','series|')):
        kind,raw = raw.split('|',1)
    rows,total = await search_results(raw,page,kind=kind)
    if not rows:
        return await q.answer('No results',show_alert=True)
    await q.message.edit_text(
        doom_search_text(raw, total, page),
        reply_markup=result_markup(
            rows, page, total, int(sid)
        )
    )
    await q.answer()


async def delete_later(chat_id,message_ids):
    try:
        await asyncio.sleep(DELETE_SECONDS)
        await bot.delete_messages(chat_id,message_ids)
    except RPCError as exc:
        log.warning('Auto-delete failed: %s',exc)


def schedule_delete(chat_id, ids):
    task = asyncio.create_task(delete_later(chat_id,ids))
    cleanup_tasks.add(task)
    task.add_done_callback(cleanup_tasks.discard)



# ===== DR_DOOM_CUSTOM_FILE_CAPTION_V1 =====

def doom_file_caption(row):
    import html

    def safe(value):
        return html.escape(str(value or "Unknown"))

    filename = (
        row.get("file_name")
        or row.get("filename")
        or "Telegram File"
    )

    size = row.get("file_size") or 0

    try:
        size = float(size)
        if size >= 1073741824:
            size_text = f"{size / 1073741824:.2f} GB"
        elif size >= 1048576:
            size_text = f"{size / 1048576:.2f} MB"
        elif size >= 1024:
            size_text = f"{size / 1024:.2f} KB"
        elif size:
            size_text = f"{int(size)} B"
        else:
            size_text = "Unknown"
    except (TypeError, ValueError):
        size_text = "Unknown"

    language = safe(row.get("language"))
    quality = safe(row.get("quality"))

    caption = (
        f"🎬 <b>{safe(filename)}</b>\n\n"
        "╭──── ⚡ DR. DOOM ⚡ ────╮\n"
        f"│ 📦 Size: {size_text}\n"
        f"│ 🌐 Language: {language}\n"
        f"│ 🎞 Quality: {quality}\n"
        "╰──────────────────────╯\n\n"
        "🔥 <b>POWERED BY DR. DOOM</b>"
    )

    return caption[:1024]


async def deliver(user_id,file_id,origin=None):
    if not await is_subscribed(user_id):
        if origin:
            await origin.reply_text(
                "Please join the required channel first.",
                reply_markup=join_keyboard(file_id)
            )
        else:
            await bot.send_message(
                user_id,
                "Please join the required channel first.",
                reply_markup=join_keyboard(file_id)
            )
        return

    row = await db.fetchone(
        "SELECT * FROM files WHERE id=%s",
        (file_id,)
    )

    if not row:
        return await bot.send_message(
            user_id,
            "File not found."
        )

    caption = doom_file_caption(row)

    try:
        sent = await bot.copy_message(
            user_id,
            row["source_channel"],
            row["source_message"],
            caption=caption,
            parse_mode=ParseMode.HTML
        )

    except RPCError:
        try:
            options = {
                "caption": caption,
                "parse_mode": ParseMode.HTML
            }

            media_type = row["media_type"]

            if media_type == "video":
                sent = await bot.send_video(
                    user_id, row["file_id"], **options
                )
            elif media_type == "audio":
                sent = await bot.send_audio(
                    user_id, row["file_id"], **options
                )
            elif media_type == "animation":
                sent = await bot.send_animation(
                    user_id, row["file_id"], **options
                )
            else:
                sent = await bot.send_document(
                    user_id, row["file_id"], **options
                )

        except RPCError as exc:
            log.warning("Delivery failed: %s", exc)
            slog.emit_background(f"❌ <b>Delivery failed</b>\nUser: <code>{user_id}</code>\nFile ID: <code>{file_id}</code>\nError: {type(exc).__name__}")
            return await bot.send_message(
                user_id,
                "File is temporarily unavailable. Contact an admin."
            )

    slog.emit_background(f"📤 <b>File delivered</b>\nUser: <code>{user_id}</code>\nFile ID: <code>{file_id}</code>")

    note = await bot.send_message(
        user_id,
        f"⏳ This file and notice will be deleted after "
        f"{DELETE_SECONDS//60} minute(s)."
    )

    schedule_delete(user_id, [sent.id, note.id])


@bot.on_callback_query(filters.regex(r'^get:\d+$'))
async def get_file(_,q):
    file_id = int(q.data.split(':')[1])
    if q.message.chat.type.name.lower() != 'private':
        username = CFG['BOT_USERNAME'].lstrip('@')
        await q.answer('Open the bot in private to receive your file.',url=f'https://t.me/{username}?start=file_{file_id}')
        return
    await q.answer('Sending file…')
    await deliver(q.from_user.id,file_id,q.message)


@bot.on_message(filters.command('stats') & filters.private)
async def stats(_,msg):
    if not admin(None,None,msg):
        return
    row = await db.fetchone('SELECT COUNT(*) total, COUNT(DISTINCT source_channel) channels, SUM(kind="series") episodes FROM files')
    await msg.reply_text(f"📊 Indexed files: {row['total']}\nChannels: {row['channels']}\nSeries entries: {row['episodes'] or 0}")



async def scan_channel(channel_id):
    slog.emit_background(f"📚 <b>Scan started</b>\nChannel: <code>{channel_id}</code>")
    try:
        # Populate the in-memory history reader's peer cache.
        found = False

        async for dialog in history.get_dialogs():
            if dialog.chat.id == channel_id:
                found = True
                break

        if not found:
            raise RuntimeError(
                f"History-reader account cannot discover channel {channel_id}"
            )

        await ags_indexer.scan_channel(
            history,
            channel_id,
            index_message
        )
        slog.emit_background(f"✅ <b>Scan completed</b>\nChannel: <code>{channel_id}</code>")
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("AGS indexing failed for %s", channel_id)
        slog.emit_background(f"❌ <b>Scan failed</b>\nChannel: <code>{channel_id}</code>")
    finally:
        scans.pop(channel_id, None)




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


# ===== TEMARI INTERACTIVE INDEX MANAGER =====

import time
from types import SimpleNamespace

index_started_at = {}


def index_admin(user):
    return bool(user) and admin(
        None, None, SimpleNamespace(from_user=user)
    )


def index_menu():
    buttons = [
        [InlineKeyboardButton(
            f"📁 Channel {channel}",
            callback_data=f"im:channel:{channel}"
        )]
        for channel in sorted(CHANNELS)
    ]
    return InlineKeyboardMarkup(buttons)


def index_channel_menu(channel):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "▶️ Start / Resume Scan",
            callback_data=f"im:start:{channel}"
        )],
        [InlineKeyboardButton(
            "📊 Detailed Report",
            callback_data=f"im:report:{channel}"
        )],
        [InlineKeyboardButton(
            "🔄 Refresh",
            callback_data=f"im:channel:{channel}"
        )],
        [InlineKeyboardButton(
            "⬅️ All Channels",
            callback_data="im:home"
        )]
    ])


async def index_report(channel):
    row = await db.fetchone(
        "SELECT * FROM ags_scan_state WHERE channel_id=%s",
        (channel,)
    )

    stored = await db.fetchone(
        "SELECT COUNT(*) AS total FROM files "
        "WHERE source_channel=%s",
        (channel,)
    )

    running = (
        channel in scans and not scans[channel].done()
    )

    if not row:
        return (
            f"📊 TEMARI INDEX REPORT\n\n"
            f"Channel: {channel}\n"
            f"Status: Not started\n"
            f"Stored files: {stored['total']}\n"
            f"Use Start / Resume Scan to begin."
        )

    elapsed = index_started_at.get(channel)
    if elapsed is not None and running:
        duration = int(time.monotonic() - elapsed)
        elapsed_text = f"{duration // 60}m {duration % 60}s"
    else:
        elapsed_text = "Not recorded"

    status = "running" if running else row["status"]

    return (
        f"📊 TEMARI — INDEX REPORT\n\n"
        f"📁 Channel: {channel}\n"
        f"📌 Status: {status}\n\n"
        f"🔎 Scanned: {row['scanned']}\n"
        f"✅ Indexed/updated: {row['indexed']}\n"
        f"⏭ Skipped: {row['skipped']}\n"
        f"📦 Stored files: {stored['total']}\n"
        f"📍 Checkpoint: {row['next_offset_id']}\n"
        f"⏱ Current run: {elapsed_text}\n"
        f"🔄 Active task: {running}\n\n"
        f"Duplicate and failure totals are not separately "
        f"tracked by the current indexer."
    )


async def index_completion_notice(channel, user_id, task):
    try:
        await task
    except asyncio.CancelledError:
        return
    except Exception:
        log.exception("Index task failed: %s", channel)
    finally:
        index_started_at.pop(channel, None)

    try:
        report = await index_report(channel)
        await bot.send_message(
            user_id,
            "🏁 Scan task finished\n\n" + report
        )
    except Exception:
        log.exception("Could not send scan report")


@bot.on_message(filters.command('index') & filters.private)
async def index_command(_, msg):
    if not index_admin(msg.from_user):
        return

    if len(msg.command) > 1:
        try:
            channel = int(msg.command[1])
        except ValueError:
            return await msg.reply_text(
                "Usage: /index or /index <channel_id>"
            )

        if channel not in CHANNELS:
            success, reason = await register_source_channel(channel)

            if not success:
                return await msg.reply_text(
                    f"❌ {reason}"
                )

            await msg.reply_text(
                "✅ New database channel registered!\\n"
                f"Channel: {channel}\\n"
                "Select Start / Resume Scan to begin."
            )

        return await msg.reply_text(
            f"📁 TEMARI INDEX MANAGER\n\n"
            f"Selected channel: {channel}",
            reply_markup=index_channel_menu(channel)
        )

    await msg.reply_text(
        "📁 TEMARI — INDEX MANAGER\n\n"
        "Select a database channel:",
        reply_markup=index_menu()
    )


@bot.on_callback_query(filters.regex(r'^im:'))
async def index_manager_callback(_, q):
    if not index_admin(q.from_user):
        return await q.answer(
            "Admins only", show_alert=True
        )

    parts = q.data.split(":")
    action = parts[1]

    if action == "home":
        await q.answer()
        return await q.message.edit_text(
            "📁 TEMARI — INDEX MANAGER\n\n"
            "Select a database channel:",
            reply_markup=index_menu()
        )

    try:
        channel = int(parts[2])
    except (IndexError, ValueError):
        return await q.answer("Invalid channel", show_alert=True)

    if channel not in CHANNELS:
        return await q.answer(
            "Channel not configured", show_alert=True
        )

    if action == "channel":
        await q.answer()
        return await q.message.edit_text(
            f"📁 TEMARI INDEX MANAGER\n\n"
            f"Selected channel: {channel}",
            reply_markup=index_channel_menu(channel)
        )

    if action == "report":
        await q.answer()
        return await q.message.edit_text(
            await index_report(channel),
            reply_markup=index_channel_menu(channel)
        )

    if action == "start":
        if not history:
            return await q.answer(
                "USER_SESSION is not configured",
                show_alert=True
            )

        if channel in scans and not scans[channel].done():
            return await q.answer(
                "Scan already running",
                show_alert=True
            )

        task = asyncio.create_task(scan_channel(channel))
        scans[channel] = task
        index_started_at[channel] = time.monotonic()

        asyncio.create_task(
            index_completion_notice(
                channel, q.from_user.id, task
            )
        )

        await q.answer("Scan started")
        await q.message.edit_text(
            f"✅ Scan started / resumed\n"
            f"Channel: {channel}\n\n"
            f"Use Detailed Report to monitor progress.",
            reply_markup=index_channel_menu(channel)
        )


@bot.on_message(filters.command('progress') & filters.private)
async def progress(_, msg):
    if not admin(None, None, msg):
        return

    try:
        channel = int(msg.command[1])
    except (IndexError, ValueError):
        return await msg.reply_text(
            "Usage: /progress -1001234567890"
        )

    row = await db.fetchone(
        "SELECT * FROM ags_scan_state WHERE channel_id=%s",
        (channel,)
    )

    if not row:
        return await msg.reply_text(
            "No AGS scan recorded for this channel."
        )

    running = (
        channel in scans
        and not scans[channel].done()
    )

    await msg.reply_text(
        f"📊 AGS Index Progress\n"
        f"Channel: {channel}\n"
        f"Status: {row['status']}\n"
        f"Scanned: {row['scanned']}\n"
        f"Indexed/updated: {row['indexed']}\n"
        f"Skipped: {row['skipped']}\n"
        f"Checkpoint: {row['next_offset_id']}\n"
        f"Running: {running}"
    )


async def main():
    global history
    await db.init_db()
    await ags_indexer.ensure_tables()
    await ensure_search_table()
    await load_doom_access()
    await group_tracker.ensure_table(db)
    group_tracker.register(bot, db, lambda user_id: user_id in DYNAMIC_ADMINS)
    await user_tracker.ensure_table(db)
    user_tracker.register(bot, db, lambda user_id: user_id in DYNAMIC_ADMINS)
    broadcast.register(bot, db, lambda user_id: user_id in DYNAMIC_ADMINS, lambda message: slog.emit_background(message))
    await ensure_start_picture_table()
    await bot.start()
    await slog.start(bot)
    if CFG['USER_SESSION']:
        history = Client('history_reader',api_id=int(CFG['API_ID']),api_hash=CFG['API_HASH'],session_string=CFG['USER_SESSION'],in_memory=True,no_updates=True)
        await history.start()
    log.info('Bot running, configured channels: %s',CHANNELS)
    try:
        await idle()
    finally:
        for task in scans.values():
            task.cancel()
        if scans:
            await asyncio.gather(*scans.values(),return_exceptions=True)
        for task in cleanup_tasks:
            task.cancel()
        if history:
            await history.stop()
        await slog.stop()
        await bot.stop()
        await db.close_db()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
