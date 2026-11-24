import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.menu import handle_menu
from bot.keyboards.main import get_main_keyboard


class AdminKeyboardTests(unittest.TestCase):
	def setUp(self):
		self.admin_id_patcher = patch("bot.keyboards.main.ADMIN_USER_ID", 123)
		self.admin_id_patcher.start()

	def tearDown(self):
		self.admin_id_patcher.stop()

	def test_admin_defaults_to_user_keyboard_with_admin_button(self):
		with patch(
			"bot.i18n.keyboards.tr_user",
			side_effect=lambda user_id, key: key,
		):
			keyboard = get_main_keyboard(123)

		self.assertEqual(
			[[button.text for button in row] for row in keyboard.keyboard],
			[
				["btn_language", "btn_plan"],
				["btn_donate", "btn_help"],
				["btn_admin_mode"],
			],
		)

	def test_admin_mode_has_admin_actions_and_user_button(self):
		with patch(
			"bot.admin.keyboards.tr_user",
			side_effect=lambda user_id, key: key,
		):
			keyboard = get_main_keyboard(123, admin_mode=True)

		self.assertEqual(
			[[button.text for button in row] for row in keyboard.keyboard],
			[
				["📊 Stats", "👥 Users"],
				["📥 Downloads", "⚙️ System"],
				["btn_user_mode"],
			],
		)

	def test_regular_users_do_not_get_admin_button(self):
		with patch(
			"bot.i18n.keyboards.tr_user",
			side_effect=lambda user_id, key: key,
		):
			keyboard = get_main_keyboard(456)

		self.assertEqual(
			[[button.text for button in row] for row in keyboard.keyboard],
			[
				["btn_language", "btn_plan"],
				["btn_donate", "btn_help"],
			],
		)

	def test_admin_can_switch_between_user_and_admin_keyboards(self):
		async def run():
			context = SimpleNamespace(user_data={})
			message = SimpleNamespace(
				text="btn_admin_mode",
				reply_text=AsyncMock(),
			)
			update = SimpleNamespace(
				effective_user=SimpleNamespace(id=123),
				message=message,
			)

			with (
				patch("bot.handlers.menu.ADMIN_USER_ID", 123),
				patch(
					"bot.handlers.menu.tr_user",
					side_effect=lambda user_id, key: key,
				),
				patch(
					"bot.admin.keyboards.tr_user",
					side_effect=lambda user_id, key: key,
				),
				patch(
					"bot.i18n.keyboards.tr_user",
					side_effect=lambda user_id, key: key,
				),
			):
				self.assertTrue(await handle_menu(update, context))
				self.assertTrue(context.user_data["admin_keyboard_mode"])
				self.assertEqual(
					update.message.reply_text.await_args.kwargs[
						"reply_markup"
					].keyboard[-1][0].text,
					"btn_user_mode",
				)

				message.text = "btn_user_mode"
				self.assertTrue(await handle_menu(update, context))
				self.assertFalse(context.user_data["admin_keyboard_mode"])
				self.assertEqual(
					update.message.reply_text.await_args.kwargs[
						"reply_markup"
					].keyboard[-1][0].text,
					"btn_admin_mode",
				)

		import asyncio

		asyncio.run(run())


if __name__ == "__main__":
	unittest.main()
