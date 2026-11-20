"""Admin-only broadcasts to users who contacted the bot privately."""
import asyncio
import logging
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait, RPCError

log = logging.getLogger(__name__)

def register(bot, db, is_admin, report=None):
    state = {"task": None, "cancel": False, "sent": 0, "failed": 0, "total": 0}

    async def deliver(client, user_id, source):
        for attempt in range(5):
            try:
                await client.copy_message(user_id, source.chat.id, source.id)
                return True
            except FloodWait as exc:
                await asyncio.sleep(int(exc.value) + 1)
            except RPCError:
                return False
        return False

    async def run(client, source, actor):
        try:
            rows = await db.fetchall(
                "SELECT user_id FROM bot_users WHERE source='private' AND status='active' ORDER BY user_id"
            )
            state["total"] = len(rows)
            for row in rows:
                if state["cancel"]:
                    break
                if await deliver(client, int(row["user_id"]), source):
                    state["sent"] += 1
                else:
                    state["failed"] += 1
                await asyncio.sleep(0.08)
            result = ("🛑 Broadcast cancelled" if state["cancel"] else "✅ Broadcast completed")
            result += (f"\nTotal: {state['total']}\nSent: {state['sent']}"
                       f"\nFailed: {state['failed']}\nAdmin: {actor}")
            await client.send_message(actor, result)
            if report:
                report(result)
        except Exception:
            log.exception("Broadcast failed")
            await client.send_message(actor, "❌ Broadcast failed. Check service logs.")
        finally:
            state["task"] = None

    async def broadcast(client, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        if state["task"] is not None:
            return await message.reply_text("A broadcast is already running.")
        if not message.reply_to_message:
            return await message.reply_text("Reply to a message with /broadcast.")
        state.update(cancel=False, sent=0, failed=0, total=0)
        state["task"] = asyncio.create_task(run(client, message.reply_to_message, message.from_user.id))
        await message.reply_text("📣 Broadcast started. Use /broadcaststatus.")

    async def status(_, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        await message.reply_text(
            f"📣 Broadcast {'running' if state['task'] else 'idle'}\n"
            f"Total: {state['total']}\nSent: {state['sent']}\n"
            f"Failed: {state['failed']}\nCancelled: {state['cancel']}"
        )

    async def cancel(_, message):
        if not message.from_user or not is_admin(message.from_user.id):
            return await message.reply_text("Admins only.")
        if state["task"] is None:
            return await message.reply_text("No broadcast is running.")
        state["cancel"] = True
        await message.reply_text("🛑 Cancellation requested.")

    bot.add_handler(MessageHandler(broadcast, filters.private & filters.command("broadcast")), group=40)
    bot.add_handler(MessageHandler(status, filters.private & filters.command("broadcaststatus")), group=40)
    bot.add_handler(MessageHandler(cancel, filters.private & filters.command("cancelbroadcast")), group=40)
