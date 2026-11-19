"""Offline structural smoke tests for Samantha's modular import graph."""
import os
import unittest
import asyncio

# Pyrogram 2.0.106 resolves a current event loop during module import.
# This test imports the bot without starting Telegram or MySQL.
asyncio.set_event_loop(asyncio.new_event_loop())

os.environ.update({
    "API_ID": "12345",
    "API_HASH": "0123456789abcdef0123456789abcdef",
    "BOT_TOKEN": "123456:TEST_TOKEN",
    "BOT_USERNAME": "staging_example_bot",
    "ADMINS": "123456",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
})

class ModularSmokeTests(unittest.TestCase):
    def test_import_and_register_handlers_without_network(self):
        import bot
        import core
        from plugins import admin, search, indexing, menus, delivery, start, settings, filters
        from database import connection, models, queries
        from services import ags_indexer, parser, logging
        self.assertTrue(callable(bot.main))
        self.assertIs(bot.main, core.main)
        for handler in (admin.doom_addadmin, search.command_search,
                        indexing.channel_index, menus.temari_menu,
                        delivery.get_file, start.start,
                        settings.temari_editor_callback):
            self.assertTrue(callable(handler))
        self.assertTrue(callable(connection.init_db))
        self.assertTrue(callable(queries.fetchone))
        self.assertTrue(callable(ags_indexer.scan_channel))
        self.assertTrue(callable(parser.parse_name))
        self.assertTrue(callable(logging.emit))
        self.assertTrue(callable(filters.is_subscribed))
        self.assertTrue(core.bot.dispatcher.groups)

    def test_parser_classifies_series(self):
        from services.parser import parse_name
        parsed = parse_name("Example Show S01E02 1080p English.mkv")
        self.assertEqual(parsed["kind"], "series")
        self.assertEqual(parsed["season"], 1)
        self.assertEqual(parsed["episode"], 2)

if __name__ == "__main__":
    unittest.main()
