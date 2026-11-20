"""Samantha AutoFilter message templates. Use Pyrogram HTML parse mode."""
from html import escape

class script(object):
    START_TXT = """<blockquote>👋🏻 Hᴇʟʟᴏ {}!</blockquote>

🤖 <b>Wᴇʟᴄᴏᴍᴇ ᴛᴏ Sᴀᴍᴀɴᴛʜᴀ AᴜᴛᴏFɪʟᴛᴇʀ</b>

🎬 Discover movies and series from our indexed collection.
📍 Add me to your Telegram group
⚡ Promote me as an admin if needed
🔎 Search using movie or series names

<blockquote>©️ Maintained by <a href="https://t.me/AgsModsOG">@AgsModsOG</a></blockquote>"""

    HELP_TXT = """🙋🏻‍♂️ Hᴇʟʟᴏ {}!

<blockquote>📌 Aᴠᴀɪʟᴀʙʟᴇ Cᴏᴍᴍᴀɴᴅs</blockquote>
🔹 /start – Open the bot
🔹 /help – Show help
🔹 /search – Search indexed titles
🔹 /movies – Browse movies
🔹 /series – Browse series

<blockquote>🛡️ Aᴅᴍɪɴ Cᴏᴍᴍᴀɴᴅs</blockquote>
🔹 /users – Registered user statistics
🔹 /newusers – Recent users
🔹 /groups – Tracked groups
🔹 /broadcast – Reply to broadcast
🔹 /broadcaststatus – Broadcast progress
🔹 /cancelbroadcast – Stop broadcast

⚠️ Some features depend on bot configuration and permissions.
<blockquote>©️ <a href="https://t.me/AgsModsOG">@AgsModsOG</a></blockquote>"""

    ABOUT_TXT = """<b><blockquote>🤖 Sᴀᴍᴀɴᴛʜᴀ AᴜᴛᴏFɪʟᴛᴇʀ</blockquote>
👨‍💻 Maintained by: <a href="https://t.me/AgsModsOG">@AgsModsOG</a>
💬 Language: Python 3
🗄️ Database: MySQL
🖥️ Hosting: Ubuntu VPS
⚙️ Framework: Pyrogram</b>"""

    SOURCE_TXT = """<b>📢 Sᴀᴍᴀɴᴛʜᴀ AᴜᴛᴏFɪʟᴛᴇʀ</b>
<blockquote>Project information and support</blockquote>
👨‍💻 Maintainer: <a href="https://t.me/AgsModsOG">@AgsModsOG</a>
🔗 For project support, contact the maintainer."""

    MANUELFILTER_TXT = """<b>❓ Hᴇʟᴘ: Mᴀɴᴜᴀʟ Fɪʟᴛᴇʀs</b>
Manual filters can reply to predefined keywords when enabled.
⚠️ Filter commands must be implemented separately.
🔒 Group admins should manage enabled filters."""

    PM_SUPPORT_TXT = """<b>👋 Hᴇʟʟᴏ {user}!</b>
🔎 Use the bot search menu to find movies and series.
<blockquote>©️ <a href="https://t.me/AgsModsOG">@AgsModsOG</a></blockquote>"""

    BUTTON_TXT = """<b>❓ Hᴇʟᴘ: Bᴜᴛᴛᴏɴs</b>
🔹 Telegram inline keyboards support navigation.
🔹 URL buttons open links.
🔹 Callback buttons navigate inside the bot.
⚠️ Button management depends on implemented handlers."""

    AUTOFILTER_TXT = """<b>🎬 Hᴇʟᴘ: AᴜᴛᴏFɪʟᴛᴇʀ</b>
1️⃣ Add the bot to your group.
2️⃣ Grant required permissions.
3️⃣ Configure an authorized source channel.
4️⃣ Index available media.
5️⃣ Search movie or series names.
⚠️ Only distribute content you are authorized to share."""

    CONNECTION_TXT = """<b>🔗 Hᴇʟᴘ: Cᴏɴɴᴇᴄᴛɪᴏɴs</b>
Connections may let admins manage groups from private chat.
⚠️ Connection commands require separate handlers."""

    EXTRAMOD_TXT = """<b>🧩 Hᴇʟᴘ: Exᴛʀᴀ Mᴏᴅᴜʟᴇs</b>
🔎 Movie and series search
📚 Indexed file browsing
👥 User and group statistics
📣 Admin broadcasting
Available features depend on the deployed version."""

    ADMIN_TXT = """<b>🛡️ Aᴅᴍɪɴ Mᴏᴅᴜʟᴇ</b>
<blockquote>Authorized admins only</blockquote>
• /users – User statistics
• /newusers – Recent users
• /groups – Tracked groups
• /broadcast – Broadcast a replied-to message
• /broadcaststatus – Delivery progress
• /cancelbroadcast – Cancel broadcast
🔒 Available to all authorized bot admins."""

    BROADCAST_TXT = """<b>📣 Bʀᴏᴀᴅᴄᴀsᴛ</b>
Reply to text, photo, video, or document with <code>/broadcast</code>.
📊 <code>/broadcaststatus</code>
🛑 <code>/cancelbroadcast</code>
⚠️ Only users Telegram permits the bot to contact can receive broadcasts."""

    BROADCAST_RESULT_TXT = """<b>📣 Bʀᴏᴀᴅᴄᴀsᴛ {status}</b>
👥 Total: <code>{total}</code>
✅ Sent: <code>{sent}</code>
❌ Failed: <code>{failed}</code>
🛡️ Admin: <code>{admin}</code>"""

    STATUS_TXT = """<b>📊 Sᴀᴍᴀɴᴛʜᴀ Sᴛᴀᴛᴜs</b>
📁 Total files: <code>{}</code>
👥 Total users: <code>{}</code>
💬 Total groups: <code>{}</code>
💾 Used storage: <code>{}</code>
📦 Free storage: <code>{}</code>"""

    LOG_TEXT_G = """<b>👥 #NewGroup</b>
💬 Group: {}
🆔 Group ID: <code>{}</code>
👤 Members: <code>{}</code>
➕ Added by: {}"""

    LOG_TEXT_P = """<b>🆕 #NewUser</b>
🆔 ID: <code>{}</code>
👤 Name: {}"""

    RESULT_TXT = """<b>🎉 Fɪʟᴇs Fᴏᴜɴᴅ!</b>
<blockquote>{}</blockquote>"""

    CUSTOM_FILE_CAPTION = """<b>📁 Fɪʟᴇ: <code>{file_name}</code>
📦 Sɪᴢᴇ: <code>{file_size}</code>
🔗 <a href="https://t.me/AgsModsOG">💥 AGS MODS 💥</a></b>"""

    RESTART_GC_TXT = """<b>🔄 Sᴀᴍᴀɴᴛʜᴀ Rᴇsᴛᴀʀᴛᴇᴅ!</b>
📅 Date: <code>{}</code>
⏰ Time: <code>{}</code>
🌐 Timezone: <code>Asia/Kolkata</code>
🖥️ Server: <code>Ubuntu VPS</code>"""

    RESTART_TXT = """<b>🟢 Sᴀᴍᴀɴᴛʜᴀ AᴜᴛᴏFɪʟᴛᴇʀ ɪs Oɴʟɪɴᴇ!</b>"""

    SPOLL_NOT_FND = """<blockquote>Oops! 🤖</blockquote>
No matching title found. Check spelling and try again."""

    ENG_SPELL = """📓 Please check spelling and use the correct movie or series title."""
    MAL_SPELL = """📓 ദയവായി സിനിമയുടെയോ സീരീസിന്റെയോ പേര് ശരിയായി ടൈപ്പ് ചെയ്യുക."""
    HIN_SPELL = """📓 कृपया फ़िल्म या सीरीज़ का सही नाम लिखें।"""
    TAM_SPELL = """📓 திரைப்படம் அல்லது தொடரின் சரியான பெயரை உள்ளிடவும்."""

    CHK_MOV_ALRT = "♻️ Cʜᴇᴄᴋɪɴɢ ᴍʏ ᴅᴀᴛᴀʙᴀsᴇ..."
    OLD_MES = "⚠️ This menu has expired. Please search again."

    MOV_NT_FND = """<b>🎬 Tɪᴛʟᴇ Nᴏᴛ Fᴏᴜɴᴅ</b>
<blockquote>This title is not yet available in the indexed database.</blockquote>
Contact <a href="https://t.me/AgsModsOG">@AgsModsOG</a>."""

    DMCA_TXT = """<b>📩 Content or copyright concern?</b>
Contact <a href="https://t.me/AgsModsOG">@AgsModsOG</a>."""

    DELIVERY_SUCCESS_TXT = """<b>✅ Fɪʟᴇ Dᴇʟɪᴠᴇʀᴇᴅ</b>
📁 File: <code>{file_name}</code>
⏳ This message may be automatically deleted after the configured retention period."""

    DELIVERY_FAILED_TXT = """<b>❌ Fɪʟᴇ Dᴇʟɪᴠᴇʀʏ Fᴀɪʟᴇᴅ</b>
Please try again later or contact <a href="https://t.me/AgsModsOG">@AgsModsOG</a>."""

def safe_format(template, *args, **kwargs):
    """Escape untrusted text before inserting it into Telegram HTML."""
    return template.format(
        *(escape(str(value)) for value in args),
        **{key: escape(str(value)) for key, value in kwargs.items()},
    )
