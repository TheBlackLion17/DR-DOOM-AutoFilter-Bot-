import asyncio
from pyrogram import Client
from config import CFG

async def main():
    async with Client('history_login', api_id=int(CFG['API_ID']), api_hash=CFG['API_HASH'], in_memory=True) as app:
        session = await app.export_session_string()
        print('\nUSER_SESSION=' + session + '\n')
        print('Keep this session private: it grants access to your Telegram account.')

asyncio.run(main())
