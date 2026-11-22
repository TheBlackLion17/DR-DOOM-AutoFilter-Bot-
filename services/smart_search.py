"""Smart catalog suggestions and missing-title request persistence."""
import re
from difflib import SequenceMatcher
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def normalize(value):
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))

async def ensure_tables(db):
    await db.execute("""CREATE TABLE IF NOT EXISTS movie_requests (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        query VARCHAR(255) NOT NULL,
        normalized_query VARCHAR(255) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_user_query (user_id, normalized_query),
        KEY idx_status (status)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""")


    await db.execute("""CREATE TABLE IF NOT EXISTS movie_request_settings (
        setting_key VARCHAR(64) PRIMARY KEY,
        setting_value VARCHAR(255) NOT NULL
    ) CHARACTER SET utf8mb4""")
    await db.execute("""CREATE TABLE IF NOT EXISTS movie_request_notifications (
        request_id BIGINT PRIMARY KEY,
        channel_id BIGINT NOT NULL,
        message_id BIGINT NOT NULL
    ) CHARACTER SET utf8mb4""")
    await db.execute("""CREATE TABLE IF NOT EXISTS movie_request_delivery (
        request_id BIGINT PRIMARY KEY,
        delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4""")

async def suggestions(db, query, kind='all', limit=5):
    query_norm = normalize(query)
    if len(query_norm) < 2:
        return []
    # Keep candidate selection bounded, then rank by similarity in Python.
    kind_sql = "AND kind=%s" if kind != 'all' else ""
    args = (kind,) if kind != 'all' else ()
    rows = await db.fetchall(
        f"SELECT DISTINCT title FROM files WHERE title <> '' {kind_sql} ORDER BY title LIMIT 3000", args
    )
    scored = []
    for row in rows:
        title = str(row['title'])
        candidate = normalize(title)
        if not candidate:
            continue
        ratio = SequenceMatcher(None, query_norm, candidate).ratio()
        if query_norm in candidate or candidate in query_norm:
            ratio = max(ratio, 0.82)
        if ratio >= 0.55:
            scored.append((ratio, title))
    scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return [title for _, title in scored[:limit]]

async def missing_reply(db, msg, query, kind='all', owner_id=None):
    user_id = owner_id if owner_id is not None else (msg.from_user.id if msg.from_user else 0)
    # Store the original search context in MySQL, not callback_data.
    search_id = await db.insert_id(
        "INSERT INTO searches(query,owner_id) VALUES(%s,%s)",
        ((kind + '|' if kind != 'all' else '') + query, user_id)
    )
    matches = await suggestions(db, query, kind)
    buttons = [
        [InlineKeyboardButton('🔎 ' + title[:48], callback_data=f'spell:{search_id}:{i}')]
        for i, title in enumerate(matches)
    ]
    buttons.append([InlineKeyboardButton('📩 Request Movie', callback_data=f'request:{search_id}')])
    buttons.append([InlineKeyboardButton('🔁 Search Again', callback_data='spell:retry')])
    message = (
        "❌ **Movie Not Found**\n\n"
        f"🔎 **Searched:** {query}\n\n"
        + ("💡 **Did you mean:**\nChoose a title below.\n\n" if matches else "")
        + "Check the spelling or request this title from our admins."
    )
    return await msg.reply_text(message, reply_markup=InlineKeyboardMarkup(buttons))

async def record_request(db, user_id, query):
    normalized = normalize(query)[:255]
    if not normalized:
        return False
    count = await db.execute(
        "INSERT IGNORE INTO movie_requests(user_id,query,normalized_query) VALUES(%s,%s,%s)",
        (user_id, query[:255], normalized)
    )
    return bool(count)

async def request_channel(db):
    row = await db.fetchone("SELECT setting_value FROM movie_request_settings WHERE setting_key='request_channel'")
    return int(row['setting_value']) if row else 0

async def set_request_channel(db, channel_id):
    await db.execute("""INSERT INTO movie_request_settings(setting_key,setting_value)
        VALUES('request_channel',%s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)""",
        (str(channel_id),))

async def find_indexed(db, title):
    normalized = normalize(title)
    if not normalized:
        return []
    rows = await db.fetchall(
        "SELECT id,title,file_name FROM files WHERE kind='movie' AND LOWER(title)=LOWER(%s) ORDER BY id DESC LIMIT 12",
        (title,))
    return [row for row in rows if normalize(row['title']) == normalized]

async def pending_matches(db, title):
    rows = await db.fetchall("SELECT id,user_id,query FROM movie_requests WHERE status='pending' ORDER BY id DESC LIMIT 2000")
    target = normalize(title)
    return [row for row in rows if normalize(row['query']) == target]
