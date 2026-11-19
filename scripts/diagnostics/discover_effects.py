import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import GetAvailableEffectsRequest

load_dotenv(Path("/opt/autofilter_bot/.env"))

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

async def main():
    async with TelegramClient(
        "/opt/autofilter_bot/user_effects",
        API_ID,
        API_HASH
    ) as client:

        result = await client(
            GetAvailableEffectsRequest(hash=0)
        )

        effects = getattr(result, "effects", [])

        print(f"\nFound {len(effects)} effects\n")

        for effect in effects:
            print(
                "Emoji:", getattr(effect, "emoticon", "?"),
                "| ID:", effect.id,
                "| Premium:", getattr(
                    effect, "premium_required", False
                )
            )

asyncio.run(main())
