from pathlib import Path
from datetime import datetime
import py_compile

p = Path("/opt/autofilter_bot/bot.py")
original = p.read_text()
s = original

if "DR_DOOM_SEARCH_V2" in s:
    raise SystemExit("Already installed.")

start = s.find("def result_markup(rows, page, total, search_id):")
end = s.find("\n\n# Search context is stored", start)

if start == -1 or end == -1:
    raise SystemExit("Search markup section not found.")

replacement = '''
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
        "🎬 **DR. DOOM AUTO FILTER**\\n\\n"
        f"🔎 **Search:** {query}\\n"
        f"📂 **Available files:** {total}\\n"
        f"📄 **Page:** {page + 1}/{pages}\\n\\n"
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
'''

s = s[:start] + replacement + s[end:]

old = """await msg.reply_text(f'🔎 **{query}**\\nFound {total} matching files. Page 1/{(total+PAGE_SIZE-1)//PAGE_SIZE}', reply_markup=result_markup(rows,0,total,sid))"""

new = """await msg.reply_text(
        doom_search_text(query, total, 0),
        reply_markup=result_markup(rows, 0, total, sid)
    )"""

if old not in s:
    raise SystemExit("Standard search reply not found.")

s = s.replace(old, new, 1)

old = """await msg.reply_text(f'🔎 {kind.title()} results for **{query}** ({total})',reply_markup=result_markup(rows,0,total,sid))"""

new = """await msg.reply_text(
        doom_search_text(query, total, 0),
        reply_markup=result_markup(rows, 0, total, sid)
    )"""

if old not in s:
    raise SystemExit("Command search reply not found.")

s = s.replace(old, new, 1)

old = """await q.message.edit_text(f'🔎 **{raw}**\\nFound {total} matching files. Page {page+1}/{(total+PAGE_SIZE-1)//PAGE_SIZE}',reply_markup=result_markup(rows,page,total,int(sid)))"""

new = """await q.message.edit_text(
        doom_search_text(raw, total, page),
        reply_markup=result_markup(
            rows, page, total, int(sid)
        )
    )"""

if old not in s:
    raise SystemExit("Pagination reply not found.")

s = s.replace(old, new, 1)

backup = p.with_name(
    "bot.py.before-doom-search-v2-" +
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

print("Search upgrade installed.")
print("Python syntax verified.")
print("Backup:", backup)
