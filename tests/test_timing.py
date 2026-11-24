import logging
import time
import unittest
from unittest.mock import patch

from bot.utils.timing import create_ytdlp_download_hook, log_duration


class TimingTests(unittest.TestCase):
	def test_logs_stage_duration_when_enabled(self):
		logger = logging.getLogger("test.timing")

		with patch("bot.utils.timing.LOG_TIME", True):
			with self.assertLogs(logger, level="INFO") as captured:
				log_duration(
					logger,
					"youtube_info",
					time.perf_counter() - 0.01,
					route="socks_primary",
				)

		self.assertRegex(
			captured.output[0],
			r"\[timing\] stage=youtube_info duration_ms=\d+ route=socks_primary",
		)

	def test_does_not_log_when_disabled(self):
		logger = logging.getLogger("test.timing")

		with patch("bot.utils.timing.LOG_TIME", False):
			with patch.object(logger, "info") as info:
				log_duration(logger, "postprocess", time.perf_counter())

		info.assert_not_called()

	def test_ytdlp_hook_logs_transfer_duration_and_bytes(self):
		logger = logging.getLogger("test.timing")

		with patch("bot.utils.timing.LOG_TIME", True):
			hook, state = create_ytdlp_download_hook(
				logger,
				route="socks_primary",
				mode="slow_mode",
			)
			with self.assertLogs(logger, level="INFO") as captured:
				hook({"status": "downloading"})
				time.sleep(0.01)
				hook({
					"status": "finished",
					"downloaded_bytes": 1024,
				})

		self.assertIsNotNone(state.get("finished_at"))
		self.assertRegex(
			captured.output[0],
			r"\[timing\] stage=youtube_transfer duration_ms=\d+ "
			r"route=socks_primary mode=slow_mode downloaded_bytes=1024 "
			r"average_bytes_per_second=\d+",
		)


if __name__ == "__main__":
	unittest.main()
