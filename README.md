<div align="center">

![DR. DOOM — Telegram AutoFilter Bot](assets/17f4023b375b83f96bc811eac94e1e21%20(1).jpg)

# ⚡ DR. DOOM
### Telegram Movies & Series AutoFilter Bot

**Search • Index • Discover • Deliver**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![Pyrogram](https://img.shields.io/badge/Pyrogram-2.x-229ED9?logo=telegram&logoColor=white) ![MySQL](https://img.shields.io/badge/MySQL-8.x-4479A1?logo=mysql&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white)

*A self-hosted Telegram bot for indexing and searching media you have permission to distribute.*

</div>

---

## ✨ Features

| Category | Capabilities |
|---|---|
| 🔎 Search | Search indexed movie and series files; pagination and file metadata |
| 📥 Indexing | Index new posts from configured source channels; optional historical scan using an authorized user session |
| 🗃️ Storage | MySQL-backed metadata and indexing progress |
| 📬 Delivery | Private-chat file delivery with a timed deletion notice |
| 🛡️ Access | Main force-subscription channel, additional required channels, admin management |
| 🎛️ Admin panel | `/adminpanel` for welcome content, links, statistics, and channel controls |
| 🎨 Customization | Welcome text, start picture, menu links, and optional reaction/effect features |
| 🖥️ Deployment | Python virtual environment and systemd service for Ubuntu VPS |

> **Development note:** This repository includes iterative feature patches. The latest `bot.py` includes interactive force-subscription management, but not every feature has been verified end-to-end. Check logs and test with a non-admin account before production use.

## 🧭 How it works

```text
Source Telegram channel
          │
          ▼
  Auto / manual indexing
          │
          ▼
    MySQL media index
          │
          ▼
  User searches in bot/group
          │
          ▼
  Results and private delivery
          │
          ▼
   Subscription verification
```

## 📦 Requirements

- Ubuntu 24.04 VPS (or compatible Linux)
- Python 3.12 and `python3-venv`
- MySQL server
- Telegram API ID and hash from [my.telegram.org](https://my.telegram.org)
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Access and appropriate permissions for every source channel

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/TheBlackLion17/DR-DOOM-AutoFilter-Bot.git
cd DR-DOOM-AutoFilter-Bot
```

### 2. Install Python dependencies

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip mysql-server
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Create the database

```bash
sudo mysql
```

```sql
CREATE DATABASE autofilter CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'autofilter'@'localhost' IDENTIFIED BY 'CHANGE_THIS_TO_A_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON autofilter.* TO 'autofilter'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. Configure the bot

Create a `.env` file using the configuration expected by `config.py` and the original project documentation. Configure your API credentials, bot token, MySQL credentials, admin IDs, and source channels. Never commit `.env` or Telegram session files.

For force subscription, set the required channel ID and a **real** `https://t.me/...` public or invite link. A numeric channel ID is **not** a valid join URL. Add the bot as an administrator where it must check membership or read channel posts.

### 5. Run

```bash
./venv/bin/python bot.py
```

For a persistent VPS deployment, adapt the included `autofilter.service` to your cloned project path, then install it:

```bash
sudo cp autofilter.service /etc/systemd/system/autofilter.service
sudo systemctl daemon-reload
sudo systemctl enable --now autofilter.service
sudo systemctl status autofilter.service --no-pager
sudo journalctl -u autofilter.service -n 50 --no-pager
```

> The included service may reference `/opt/autofilter_bot`; adjust `WorkingDirectory` and `ExecStart` if you cloned elsewhere. Do not run a second instance with the same bot token.

## 🤖 Commands

| Command | Purpose |
|---|---|
| `/start` | Open the bot |
| `/help` | Show help |
| `/search` | Search indexed files |
| `/movies` | Search movies |
| `/series` | Search series |
| `/adminpanel` | Open admin controls |
| `/stats` | View statistics |
| `/index CHANNEL_ID` | Start an authorized channel history scan |
| `/progress CHANNEL_ID` | Check scan progress |
| `/addadmin USER_ID` | Add a dynamic admin (owner only) |
| `/deladmin USER_ID` | Remove a dynamic admin (owner only) |
| `/admins` | List admins |
| `/addfsub CHANNEL_ID TITLE LINK` | Add a required channel |
| `/delfsub CHANNEL_ID` | Remove an additional required channel |
| `/fsublist` | List additional required channels |

Some commands require admin privileges and a correctly configured source channel.

## 📁 Project structure

```text
├── bot.py                # Telegram handlers and user/admin flows
├── config.py             # Configuration loader
├── database.py           # MySQL database functions
├── parser.py             # Media filename metadata parser
├── ags_indexer.py        # Source-channel indexing
├── requirements.txt      # Python dependencies
├── autofilter.service    # Example systemd unit
├── install.sh            # Original installation helper
├── install_*.py          # Historical feature patch scripts
├── fix_*.py              # Historical repair scripts
└── assets/
    └── dr-doom-banner.png
```

## 🛠️ Troubleshooting

**Bot starts but cannot access a channel:** Verify the channel ID, permissions, membership, and that the bot/user session has resolved the Telegram peer. `Peer id invalid` errors need the full traceback and affected channel checked.

**Force-subscription button doesn't work:** Verify that the join link is a valid Telegram URL, the bot is an administrator, and the subscription-check flow is working for non-admin users.

**No search results:** Check source-channel permissions, indexing progress, filename parsing, and database connectivity.

**Check service logs:**

```bash
sudo journalctl -u autofilter.service -f
```

## 🔐 Security & responsible use

- Never publish `.env`, API hashes, bot tokens, passwords, or `.session` files.
- Keep the repository private until you have reviewed all source and helper scripts for embedded secrets.
- Only index and distribute content you own or are authorized to share.
- Telegram can rate-limit scanning, delivery, and deletion.
- Auto-delete jobs stored in memory may be lost on process restart.

---

<div align="center">

**DR. DOOM** · Built with Python, Pyrogram & MySQL

*Search smarter. Manage easier.*

</div>
