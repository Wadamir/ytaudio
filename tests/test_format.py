import unittest

from bot.utils.format import format_eta, format_size_bytes


class FormatTests(unittest.TestCase):
	def test_format_size_bytes(self):
		self.assertEqual(format_size_bytes(512), "512 B")
		self.assertEqual(format_size_bytes(1024 * 1.5), "1.5 KiB")
		self.assertIsNone(format_size_bytes(None))

	def test_format_eta(self):
		self.assertEqual(format_eta(12), "12 sec")
		self.assertEqual(format_eta(75), "1 min 15 sec")
		self.assertEqual(format_eta(3660), "1 h 1 min")
		self.assertIsNone(format_eta(None))


if __name__ == "__main__":
	unittest.main()
