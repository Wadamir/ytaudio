import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.db import db
from bot.downloaders.youtube import YouTubeDownloader
from bot.transport import state, strategy
from bot.transport.exceptions import is_route_format_error
from bot.transport.routes import TransportRoute


class RouteAffinityTests(unittest.TestCase):
	def setUp(self):
		self.temp_dir = tempfile.TemporaryDirectory()
		self.db_path_patcher = patch.object(
			db,
			"DB_PATH",
			Path(self.temp_dir.name) / "bot.sqlite3",
		)
		self.db_path_patcher.start()
		self.reset_setting_patcher = patch.dict(
			os.environ,
			{"RESET_DB_ON_START": "false"},
		)
		self.reset_setting_patcher.start()
		db.init_db()

	def tearDown(self):
		self.reset_setting_patcher.stop()
		self.db_path_patcher.stop()
		self.temp_dir.cleanup()

	def test_route_preferences_are_persisted_per_service(self):
		db.set_last_successful_route("telegram", "http_secondary")
		db.set_last_successful_route("youtube", "socks_primary")

		self.assertEqual(
			db.get_last_successful_route("telegram"),
			"http_secondary",
		)
		self.assertEqual(
			db.get_last_successful_route("youtube"),
			"socks_primary",
		)

	def test_youtube_tries_saved_route_first_and_updates_it_on_success(self):
		routes = [
			TransportRoute("socks_primary", "socks5h://primary"),
			TransportRoute("http_secondary", "http://secondary"),
		]
		with patch.object(strategy, "ROUTES_IN_ORDER", routes):
			db.set_last_successful_route("youtube", "socks_primary")
			self.assertEqual(
				[route.key for route in strategy.iter_routes()],
				["socks_primary", "http_secondary"],
			)

			state.mark_success("http_secondary")
			self.assertEqual(
				[route.key for route in strategy.iter_routes()],
				["http_secondary", "socks_primary"],
			)

	def test_missing_formats_trigger_route_fallback(self):
		self.assertTrue(
			is_route_format_error(
				RuntimeError("Requested format is not available")
			)
		)
		self.assertTrue(
			is_route_format_error(
				RuntimeError("Only images are available for download")
			)
		)
		self.assertFalse(is_route_format_error(RuntimeError("Video unavailable")))

	def test_socks_protocol_mismatch_is_a_route_connection_error(self):
		self.assertTrue(
			YouTubeDownloader._is_route_connection_error(
				RuntimeError(
					"Invalid response version from server. Expected 05 got 00"
				)
			)
		)

	def test_image_only_info_is_not_usable_for_audio_download(self):
		self.assertFalse(
			YouTubeDownloader._has_audio_format(
				{"formats": [{"acodec": "none", "vcodec": "none"}]}
			)
		)
		self.assertTrue(
			YouTubeDownloader._has_audio_format(
				{"formats": [{"acodec": "opus", "vcodec": "none"}]}
			)
		)


if __name__ == "__main__":
	unittest.main()
