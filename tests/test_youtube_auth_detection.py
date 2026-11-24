import unittest

from bot.downloaders.errors import FetchInfoFailed, is_browser_auth_required


class YouTubeAuthDetectionTests(unittest.TestCase):
	def test_explicit_login_challenge_requires_browser_auth(self):
		error = FetchInfoFailed("Sign in to confirm you're not a bot")

		self.assertTrue(is_browser_auth_required(error))

	def test_unsupported_youtube_post_is_not_an_auth_challenge(self):
		error = FetchInfoFailed(
			"This channel does not have a Ugkx123 tab"
		)

		self.assertFalse(is_browser_auth_required(error))


if __name__ == "__main__":
	unittest.main()
