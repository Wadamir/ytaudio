import unittest

from bot.utils.inflight import (
	canonical_inflight_key,
	mark_inflight,
	pop_inflight_messages,
)


class InflightTests(unittest.IsolatedAsyncioTestCase):
	async def test_youtube_tracking_urls_share_one_inflight_entry(self):
		first_url = "https://youtu.be/abc123?si=tracking"
		second_url = "https://www.youtube.com/watch?v=abc123&t=42"

		first_key = canonical_inflight_key(first_url)
		second_key = canonical_inflight_key(second_url)

		self.assertEqual(first_key, second_key)
		self.assertTrue(await mark_inflight(123, first_key, 1))
		self.assertFalse(await mark_inflight(123, second_key, 2))
		self.assertEqual(
			await pop_inflight_messages(123, first_key),
			[1, 2],
		)

	def test_non_youtube_urls_are_preserved(self):
		url = "https://example.com/audio?id=1"

		self.assertEqual(canonical_inflight_key(url), url)


if __name__ == "__main__":
	unittest.main()
