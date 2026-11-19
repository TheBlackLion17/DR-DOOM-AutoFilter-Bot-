import asyncio
import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path("/opt/autofilter_bot/.env"))

token = os.getenv("BOT_TOKEN")
if not token:
    raise SystemExit("BOT_TOKEN not found in .env")

def fetch():
    url = f"https://api.telegram.org/bot{token}/getAvailableEffects"
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)

result = asyncio.run(asyncio.to_thread(fetch))

if not result.get("ok"):
    print("Telegram returned:", result.get("description"))
else:
    for effect in result.get("result", []):
        print(
            "Emoji:", effect.get("emoji"),
            "| Effect ID:", effect.get("id"),
            "| Type:", effect.get("type")
        )
