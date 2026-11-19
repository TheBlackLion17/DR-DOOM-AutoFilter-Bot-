from pathlib import Path
from datetime import datetime
import shutil

p = Path("bot.py")
s = p.read_text()

start = s.index("async def react_to_start(message):")
end = s.index(
    '@bot.on_message(filters.command("start")',
    start
)

replacement = '''
async def react_to_start(message):
    import asyncio
    import json
    import urllib.request
    import urllib.error

    emoji = random.choice(START_REACTIONS)

    token = CFG.get("BOT_TOKEN")

    if not token:
        log.warning("Reaction skipped: BOT_TOKEN missing")
        return

    url = (
        f"https://api.telegram.org/bot{token}/"
        "setMessageReaction"
    )

    payload = json.dumps({
        "chat_id": message.chat.id,
        "message_id": message.id,
        "reaction": [
            {
                "type": "emoji",
                "emoji": emoji
            }
        ]
    }).encode()

    def send_reaction():
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            request, timeout=10
        ) as response:
            return json.loads(response.read())

    try:
        result = await asyncio.to_thread(send_reaction)

        if not result.get("ok"):
            log.warning(
                "Reaction rejected: %s",
                result.get("description")
            )

    except urllib.error.HTTPError as exc:
        # Never log the request URL: it contains the bot token.
        try:
            detail = json.loads(exc.read()).get(
                "description", "HTTP error"
            )
        except Exception:
            detail = "HTTP error"

        log.warning("Reaction failed: %s", detail)

    except Exception as exc:
        log.warning(
            "Reaction request failed: %s",
            type(exc).__name__
        )


'''

updated = s[:start] + replacement + s[end:]

compile(updated, str(p), "exec")

backup = Path(
    "bot.py.before-reaction-api-" +
    datetime.now().strftime("%Y%m%d-%H%M%S") +
    ".bak"
)

shutil.copy2(p, backup)
p.write_text(updated)

print("Reaction API patch installed.")
print("Backup:", backup)
