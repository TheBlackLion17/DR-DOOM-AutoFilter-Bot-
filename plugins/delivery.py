"""Samantha delivery handlers. Shared state and helpers live in core."""
from core import *


async def get_file(_,q):
    file_id = int(q.data.split(':')[1])
    if q.message.chat.type.name.lower() != 'private':
        username = CFG['BOT_USERNAME'].lstrip('@')
        await q.answer('Open the bot in private to receive your file.',url=f'https://t.me/{username}?start=file_{file_id}')
        return
    await q.answer('Sending file…')
    await deliver(q.from_user.id,file_id,q.message)


async def stats(_,msg):
    if not admin(None,None,msg):
        return
    row = await db.fetchone('SELECT COUNT(*) total, COUNT(DISTINCT source_channel) channels, SUM(kind="series") episodes FROM files')
    await msg.reply_text(f"📊 Indexed files: {row['total']}\nChannels: {row['channels']}\nSeries entries: {row['episodes'] or 0}")
