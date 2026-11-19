"""Register handlers in the exact order used by the original monolith."""
import core
from core import bot, filters
from plugins import admin
from plugins import search
from plugins import indexing
from plugins import menus
from plugins import delivery

bot.on_message(filters.command("addadmin") & filters.private)(admin.doom_addadmin)
bot.on_message(filters.command("deladmin") & filters.private)(admin.doom_deladmin)
bot.on_message(filters.command("admins") & filters.private)(admin.doom_admin_list)
bot.on_message(filters.command("addfsub") & filters.private)(admin.doom_addfsub)
bot.on_message(filters.command("delfsub") & filters.private)(admin.doom_delfsub)
bot.on_message(filters.command("fsublist") & filters.private)(admin.doom_fsub_list)
bot.on_callback_query(
    filters.regex(r"^doom:noop$")
)(search.doom_noop)
bot.on_message(filters.channel)(indexing.channel_index)
bot.on_callback_query(filters.regex(r"^doom:verify_fsub$"))(admin.doom_verify_fsub)
bot.on_message(filters.command("start") & filters.private)(menus.start)
bot.on_callback_query(filters.regex(r"^tm:"))(menus.temari_menu)
bot.on_message(
    filters.command(["setwelcome", "editwelcome"])
    & filters.private
)(menus.set_welcome_message)
bot.on_message(
    filters.command("viewwelcome") & filters.private
)(menus.view_welcome_message)
bot.on_message(
    filters.command("resetwelcome") & filters.private
)(menus.reset_welcome_message)
bot.on_message(
    filters.command(["setstartpic", "editstartpic"])
    & filters.private
)(menus.set_start_picture)
bot.on_message(filters.command("delstartpic") & filters.private)(menus.delete_start_picture)
bot.on_message(filters.command("viewstartpic") & filters.private)(menus.view_start_picture)
bot.on_callback_query(filters.regex(r"^dfsub:"))(admin.doom_fsub_panel_callback)
bot.on_message(filters.private & filters.text, group=-5)(admin.doom_fsub_pending_handler)
bot.on_message(
    filters.command("adminpanel") & filters.private
)(admin.temari_admin_panel)
bot.on_callback_query(filters.regex(r"^ta:"))(admin.temari_admin_callback)
bot.on_callback_query(filters.regex(r"^tl2:"))(menus.temari_editor_callback)
bot.on_message(
    filters.command("cancel") & filters.private,
    group=-1
)(menus.cancel_menu_edit)
bot.on_message(
    filters.private & filters.text & ~filters.regex(r"^/"),
    group=-1
)(menus.capture_menu_link)
bot.on_message(filters.command('help'))(search.help_command)
bot.on_message(filters.command(['search','movies','series']))(search.command_search)
bot.on_message(filters.text & ~filters.command(['start','help','search','movies','series','stats','index','progress']) & (filters.private | filters.group))(search.auto_search)
bot.on_callback_query(filters.regex(r'^page:\d+:\d+$'))(search.paginate)
bot.on_callback_query(filters.regex(r'^get:\d+$'))(delivery.get_file)
bot.on_message(filters.command('stats') & filters.private)(delivery.stats)
bot.on_message(filters.command('index') & filters.private)(indexing.index_command)
bot.on_callback_query(filters.regex(r'^im:'))(indexing.index_manager_callback)
bot.on_message(filters.command('progress') & filters.private)(indexing.progress)

# Preserve references between handlers and core helpers after extraction.
for _module in (admin, search, indexing, menus, delivery):
    for _name, _value in vars(_module).items():
        if callable(_value) and getattr(_value, '__module__', None) == _module.__name__:
            setattr(core, _name, _value)
