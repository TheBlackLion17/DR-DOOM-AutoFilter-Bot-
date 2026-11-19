# Movies & Series Telegram AutoFilter Bot

Python 3.12, Pyrogram, MySQL, Ubuntu 24.04. Only share media you have permission to distribute.

## Install

```bash
sudo mkdir -p /opt/autofilter_bot
# Upload/extract the ZIP contents into /opt/autofilter_bot first
cd /opt/autofilter_bot
sudo bash install.sh
```

## Create database and restricted user

```bash
sudo mysql
```

```sql
CREATE DATABASE autofilter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'autofilter'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON autofilter.* TO 'autofilter'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Set `DB_PASSWORD` to that password in `.env`. Edit other settings:

```bash
nano /opt/autofilter_bot/.env
chmod 600 /opt/autofilter_bot/.env
```

Get `API_ID` and `API_HASH` at my.telegram.org, and `BOT_TOKEN` from @BotFather. `BOT_USERNAME` is the bot's username without @. `ADMINS` is a comma-separated list of Telegram user IDs. `SOURCE_CHANNELS` is a comma-separated list of channel IDs. Make the bot an administrator in each source channel so it receives new channel posts and can copy source messages. For group search, add the bot to the group and disable BotFather privacy mode (or make it an admin). To enable force subscription, set `FORCE_SUB_CHANNEL` to a channel ID, set `FORCE_SUB_LINK` to its valid invite/public URL, and make the bot an administrator there so membership can be checked.

## Optional bulk history indexing

The Telegram bot API does not provide full old channel history. A separate authorized user session is needed for historical scanning. That user account must have access to the source channel. Keep the session secret.

```bash
cd /opt/autofilter_bot
./venv/bin/python generate_session.py
```

Paste the resulting `USER_SESSION` into `.env`, then restart. In the bot's private chat as an admin:

```
/index -1001234567890
/progress -1001234567890
/stats
```

Scans resume using saved message IDs. They read oldest unprocessed first within a batch and update progress per message. Note that bulk scanning may take a long time on large channels and can be rate-limited by Telegram.

## Run

```bash
cd /opt/autofilter_bot
./venv/bin/python bot.py
```

## Install service

```bash
sudo cp /opt/autofilter_bot/autofilter.service /etc/systemd/system/autofilter.service
sudo systemctl daemon-reload
sudo systemctl enable --now autofilter.service
sudo systemctl status autofilter.service --no-pager
sudo journalctl -u autofilter.service -f
```

## Notes and limitations

- The bot indexes documents, videos, audio and animations from configured channels. Telegram source channel posts must remain accessible to the bot for `copy_message` delivery; saved file IDs are the fallback.
- The filename parser uses heuristics; ambiguous filenames can be classified incorrectly. This version has search and type filtering, but no interactive season/language/quality filter menus.
- Auto-delete tasks run in memory and are not resumed after restart. Telegram may rate-limit deletion and delivery.
- MySQL data and scan progress persist across restarts.
- The bulk scanner's checkpoint is per message ID; it is not a transactional guarantee of complete history if individual message fetches fail. Review logs after large scans.
- Protect `.env` and the user session. Never publish bot tokens, API hashes, or session strings.
