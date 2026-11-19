import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import GetAvailableEffectsRequest

load_dotenv(Path("/opt/autofilter_bot/.env"))

api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]
bot_token = os.environ["BOT_TOKEN"]

async def main():
    client = TelegramClient(
        "/opt/autofilter_bot/effects_checker",
        api_id,
        api_hash
    )

    try:
        await client.start(bot_token=bot_token)

        result = await client(GetAvailableEffectsRequest(hash=0))

        effects = getattr(result, "effects", [])

        print(f"\nAvailable effects: {len(effects)}\n")

        for effect in effects:
            print(
                "ID:", effect.id,
                "| Emoji:", effect.emoticon,
                "| Premium:", effect.premium_required
            )
    finally:
        await client.disconnect()

asyncio.run(main())
