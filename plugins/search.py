"""Samantha search handlers. Shared state and helpers live in core."""
from core import *


async def doom_noop(_, q):
    await q.answer()


# Search context is stored in MySQL so pagination works after restarts.


async def help_command(_,msg):
    await msg.reply_text('**Commands**\n/search <name> — Find files\n/movies <name> — Movies only\n/series <name> — Series only\n\n**Admin:** /stats, /index <channel_id>, /progress <channel_id>')


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


async def auto_search(_,msg):
    if msg.from_user and not msg.from_user.is_bot and msg.text and not msg.text.startswith('/'):
        await search_and_reply(msg,msg.text)


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
