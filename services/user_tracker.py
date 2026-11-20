"""Record Telegram users who interact with Samantha, with admin-only statistics.

Only messages/callbacks delivered to the bot are visible. No group member scraping.
"""
import logging

from pyrogram import filters
from services import samantha_logs as slog
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

log = logging.getLogger(__name__)


async def ensure_table(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id BIGINT PRIMARY KEY,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            username VARCHAR(255),
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_requests INT DEFAULT 1,
            source VARCHAR(30) DEFAULT 'private',
            status VARCHAR(30) DEFAULT 'active',
            INDEX idx_first_seen (first_seen),
            INDEX idx_last_active (last_active)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)


def register(bot, db, is_admin):
    async def record(user, source):
        if not user or getattr(user, "is_bot", False):
            return
        inserted = await db.execute("""
            INSERT IGNORE INTO bot_users
                (user_id, first_name, last_name, username, source)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user.id,
            (user.first_name or "")[:255],
            (user.last_name or "")[:255],
            (user.username or "")[:255] or None,
            source,
        ))
        if inserted:
            try:
                row = await db.fetchone("SELECT COUNT(*) AS n FROM bot_users")
                slog.emit_background_new_user(user, row["n"] if row else None)
            except Exception:
                log.exception("Unable to log new Telegram user")
        else:
            await db.execute("""
                UPDATE bot_users SET first_name=%s, last_name=%s,
                    username=%s, last_active=CURRENT_TIMESTAMP,
                    total_requests=total_requests+1, source=%s
                WHERE user_id=%s
            """, ((user.first_name or "")[:255], (user.last_name or "")[:255],
                  (user.username or "")[:255] or None, source, user.id))

    async def observe_message(_, message):
        try:
            if message.chat.type.name.lower() == "private":
                await record(message.from_user, "private")
            elif message.text and message.text.startswith("/"):
                await record(message.from_user, "group")
        except Exception:
            log.exception("Unable to record Telegram message user")

    async def observe_callback(_, query):
        try:
            source = "private" if query.message and query.message.chat.type.name.lower() == "private" else "group"
            await record(query.from_user, source)
        except Exception:
            log.exception("Unable to record Telegram callback user")

    async def users_command(_, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        try:
            row = await db.fetchone("""
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(DATE(first_seen) = CURDATE()), 0) AS today,
                       COALESCE(SUM(first_seen >= NOW() - INTERVAL 7 DAY), 0) AS week,
                       COALESCE(SUM(last_active >= NOW() - INTERVAL 1 DAY), 0) AS active_day
                FROM bot_users
            """)
            await message.reply_text(
                f"👥 Samantha users\n"
                f"Total: {row['total']}\n"
                f"New today: {row['today']}\n"
                f"New in 7 days: {row['week']}\n"
                f"Active in 24h: {row['active_day']}\n\n"
                "Use /newusers to view recent users."
            )
        except Exception:
            log.exception("Unable to load user statistics")
            await message.reply_text("Could not load user statistics. Check service logs.")

    async def newusers_command(_, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        try:
            rows = await db.fetchall("""
                SELECT user_id, first_name, username, first_seen
                FROM bot_users ORDER BY first_seen DESC LIMIT 10
            """)
            if not rows:
                return await message.reply_text("No users recorded yet.")
            lines = ["👥 10 most recent Samantha users"]
            for row in rows:
                name = row["first_name"] or "Unknown"
                username = " @" + row["username"] if row["username"] else ""
                lines.append(f"{name}{username} | ID: {row['user_id']} | {row['first_seen']}")
            await message.reply_text("\n".join(lines), parse_mode=None)
        except Exception:
            log.exception("Unable to load recent users")
            await message.reply_text("Could not load recent users. Check service logs.")

    # Later handler groups observe activity without replacing search/start handlers.
    bot.add_handler(MessageHandler(observe_message, filters.private | filters.group), group=30)
    bot.add_handler(CallbackQueryHandler(observe_callback), group=30)
    bot.add_handler(MessageHandler(users_command, filters.private & filters.command(["users", "userstats"])), group=31)
    bot.add_handler(MessageHandler(newusers_command, filters.private & filters.command("newusers")), group=31)
