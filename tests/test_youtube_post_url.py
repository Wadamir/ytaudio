import unittest

from bot.utils.urls import is_youtube_post_url


class YouTubePostUrlTests(unittest.TestCase):
	def test_detects_youtube_post_links_with_tracking_parameters(self):
		self.assertTrue(
			is_youtube_post_url(
				"https://www.youtube.com/post/UgkxExample?si=tracking"
			)
		)

	def test_does_not_match_video_or_non_youtube_urls(self):
		self.assertFalse(
			is_youtube_post_url("https://youtube.com/watch?v=abc123")
		)
		self.assertFalse(
			is_youtube_post_url("https://youtube.com.evil.test/post/UgkxExample")
		)
		self.assertFalse(
			is_youtube_post_url("https://example.com/post/UgkxExample")
		)
		self.assertFalse(is_youtube_post_url("https://[::1/post/UgkxExample"))


if __name__ == "__main__":
	unittest.main()
