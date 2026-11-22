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

async def missing_reply(db, msg, query, kind='all'):
    user_id = msg.from_user.id if msg.from_user else 0
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
