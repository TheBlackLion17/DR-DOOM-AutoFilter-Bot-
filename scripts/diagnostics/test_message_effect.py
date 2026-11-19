import json
import os
import urllib.request
import urllib.error

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path("/opt/autofilter_bot/.env"))

token = os.environ["BOT_TOKEN"]

chat_id = input("Enter your Telegram numeric user ID: ").strip()

effects = {
    "❤️": "5159385139981059251",
    "🔥": "5104841245755180586",
    "🎉": "5046509860389126442",
}

for emoji, effect_id in effects.items():
    payload = {
        "chat_id": chat_id,
        "text": f"{emoji} DR. DOOM animated effect test",
        "message_effect_id": effect_id
    }

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)

        print(emoji, "SUCCESS" if result.get("ok") else result)

    except urllib.error.HTTPError as error:
        details = error.read().decode()
        print(emoji, "FAILED:", details)

