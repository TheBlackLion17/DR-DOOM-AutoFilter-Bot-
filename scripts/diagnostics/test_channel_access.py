import asyncio
from pyrogram import Client
from config import CFG

CHANNEL_ID = -1002518840015

async def main():
    async with Client(
        "temari_access_test",
        api_id=int(CFG["API_ID"]),
        api_hash=CFG["API_HASH"],
        session_string=CFG["USER_SESSION"],
        in_memory=True
    ) as app:

        me = await app.get_me()
        print("History reader user ID:", me.id)

        print("Searching accessible dialogs...")

        found = False

        async for dialog in app.get_dialogs():
            if dialog.chat.id == CHANNEL_ID:
                print("Channel found:", dialog.chat.title)
                found = True
                break

        if not found:
            print("Channel not found in accessible dialogs.")
            return

        chat = await app.get_chat(CHANNEL_ID)
        print("Channel resolved:", chat.title)

        async for message in app.get_chat_history(
            CHANNEL_ID,
            limit=1
        ):
            print("History accessible. Message ID:", message.id)
            break
        else:
            print("Channel resolved, but no messages returned.")

asyncio.run(main())
