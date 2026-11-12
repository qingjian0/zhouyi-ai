import unittest

from benchmarks.benchmark_n010_ooc_rss import _ru_maxrss_kib


class TestN010OocRssBenchmark(unittest.TestCase):
    def test_linux_ru_maxrss_is_already_kib(self):
        self.assertEqual(_ru_maxrss_kib(12345, "linux"), 12345)

    def test_macos_ru_maxrss_bytes_are_converted_to_kib(self):
        self.assertEqual(_ru_maxrss_kib(1024 * 123, "darwin"), 123)
        self.assertEqual(_ru_maxrss_kib(1025, "darwin"), 2)


if __name__ == "__main__":
    unittest.main()
