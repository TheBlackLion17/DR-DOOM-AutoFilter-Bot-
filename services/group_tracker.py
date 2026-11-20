"""Track Telegram group activity and expose an admin-only /groups command.

Telegram bots cannot enumerate all existing group memberships; tracking begins
when group messages or membership updates reach this bot.
"""
import logging
from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler
from pyrogram.errors import RPCError

log = logging.getLogger(__name__)

async def ensure_table(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_groups (
            chat_id BIGINT PRIMARY KEY,
            title VARCHAR(255) NOT NULL DEFAULT '',
            username VARCHAR(255) NULL,
            chat_type VARCHAR(32) NOT NULL DEFAULT '',
            bot_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

def register(bot, db, is_admin):
    async def save(chat, status="unknown"):
        if not chat or not getattr(chat, "id", None):
            return
        await db.execute("""
            INSERT INTO bot_groups (chat_id,title,username,chat_type,bot_status)
            VALUES (%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                title=VALUES(title),username=VALUES(username),
                chat_type=VALUES(chat_type),
                bot_status=IF(VALUES(bot_status)='unknown',bot_status,VALUES(bot_status)),
                last_seen=CURRENT_TIMESTAMP
        """, (
            chat.id, (getattr(chat, "title", "") or "")[:255],
            getattr(chat, "username", None),
            str(getattr(chat, "type", "")).split(".")[-1].lower(), status,
        ))

    async def observe_message(_, message):
        try:
            await save(message.chat)
        except Exception:
            log.exception("Could not track group %s", message.chat.id)

    async def observe_membership(client, update):
        try:
            member = update.new_chat_member
            old = update.old_chat_member
            subject = member or old
            if not subject or not subject.user or subject.user.id != client.me.id:
                return
            status = str(member.status).split(".")[-1].lower() if member else "left"
            await save(update.chat, status)
        except Exception:
            log.exception("Could not track group membership update")

    async def groups_command(client, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        try:
            page = max(1, int(message.command[1])) if len(message.command) > 1 else 1
        except ValueError:
            return await message.reply_text("Usage: /groups or /groups 2")
        page_size = 10
        count = await db.fetchone("SELECT COUNT(*) AS n FROM bot_groups")
        total = int(count["n"])
        rows = await db.fetchall("""
            SELECT chat_id,title,username,bot_status,last_seen
            FROM bot_groups ORDER BY last_seen DESC
            LIMIT %s OFFSET %s
        """, (page_size, (page - 1) * page_size))
        if not rows:
            return await message.reply_text(
                "No tracked groups on this page. Group tracking starts when "
                "the bot receives group activity or its own membership updates."
            )
        lines = [f"📋 Samantha tracked groups — page {page} | Total: {total}"]
        for i, row in enumerate(rows, (page - 1) * page_size + 1):
            gid = int(row["chat_id"])
            title = row["title"] or "Unnamed group"
            status = row["bot_status"] or "unknown"
            members = "unavailable"
            try:
                member = await client.get_chat_member(gid, client.me.id)
                status = str(member.status).split(".")[-1].lower()
                if status not in ("left", "banned", "kicked"):
                    members = str(await client.get_chat_members_count(gid))
                await db.execute(
                    "UPDATE bot_groups SET bot_status=%s WHERE chat_id=%s",
                    (status, gid),
                )
            except RPCError:
                status = f"{status} (not verified)"
            lines.append(
                f"\n{i}. {title}\nID: {gid}\n"
                f"Members: {members}\nBot: {status}"
            )
        lines.append("\nUse /groups 2 for the next page. "
                     "Only observed groups are listed.")
        await message.reply_text("\n".join(lines), parse_mode=None)

    # Use separate handler groups so existing AutoFilter handlers keep working.
    bot.add_handler(MessageHandler(observe_message, filters.group), group=20)
    bot.add_handler(ChatMemberUpdatedHandler(observe_membership), group=20)
    bot.add_handler(
        MessageHandler(groups_command, filters.private & filters.command("groups")),
        group=20,
    )
