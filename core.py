from pyrogram.enums import ParseMode
import asyncio
import logging
import re

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, UserNotParticipant, RPCError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import ags_indexer
import samantha_logs as slog
from config import CFG, ADMINS, CHANNELS, FORCE_CHANNEL, DELETE_SECONDS, PAGE_SIZE
from parser import parse_name

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


async def main():
    global history
    await db.init_db()
    await ags_indexer.ensure_tables()
    await ensure_search_table()
    await load_doom_access()
    await ensure_start_picture_table()
    await bot.start()
    await slog.start(bot)
    if CFG['USER_SESSION']:
        history = Client('history_reader',api_id=int(CFG['API_ID']),api_hash=CFG['API_HASH'],session_string=CFG['USER_SESSION'],in_memory=True)
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
