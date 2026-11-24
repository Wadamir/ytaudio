import unittest
from unittest.mock import AsyncMock, patch

from telegram.error import NetworkError

from bot.main import initialize_application_with_retries


class TelegramStartupTests(unittest.IsolatedAsyncioTestCase):
	async def test_retries_network_error_and_initializes(self):
		class FlakyApplication:
			def __init__(self):
				self.attempts = 0

			async def initialize(self):
				self.attempts += 1
				if self.attempts == 1:
					raise NetworkError("temporary connection failure")

		app = FlakyApplication()
		with patch("bot.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
			await initialize_application_with_retries(app)

		self.assertEqual(app.attempts, 2)
		sleep.assert_awaited_once_with(1)

	async def test_surfaces_network_error_after_retry_limit(self):
		class UnavailableApplication:
			def __init__(self):
				self.attempts = 0

			async def initialize(self):
				self.attempts += 1
				raise NetworkError("connection unavailable")

		app = UnavailableApplication()
		with patch("bot.main.asyncio.sleep", new_callable=AsyncMock) as sleep:
			with self.assertRaises(NetworkError):
				await initialize_application_with_retries(app)

		self.assertEqual(app.attempts, 3)
		self.assertEqual(sleep.await_count, 2)


if __name__ == "__main__":
	unittest.main()
