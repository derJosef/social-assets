"""Offline Buffer rate-limit regression tests, with no network or credentials."""

import unittest
from email.message import Message

from scripts.buffer_rate_limits import read_limits, report_limits, retry_after_seconds


class BufferRateLimitTests(unittest.TestCase):
    @staticmethod
    def repeated_headers():
        headers = Message()
        headers.add_header("RateLimit", '"150-in-15min"; r=15; t=897')
        headers.add_header("RateLimit", '"600-in-1day";r=598;t=86397')
        headers.add_header("RateLimit", '"3000-in-30days"; r=2969; t=696980')
        headers.add_header("RateLimit-Policy", '"150-in-15min";q=150;w=900;pk=:private:')
        headers.add_header("RateLimit-Policy", '"600-in-1day"; q=600; w=86400; pk=:private:')
        headers.add_header("RateLimit-Policy", '"3000-in-30days"; q=3000; w=2592000; pk=:private:')
        return headers

    def test_repeated_headers_and_10_percent_warning(self):
        headers = self.repeated_headers()
        output = []
        data = report_limits(headers, output=output.append)
        self.assertEqual(data["15m"]["remaining"], 15)
        self.assertEqual(data["24h"]["remaining"], 598)
        self.assertEqual(data["30d"]["quota"], 3000)
        self.assertIn("BUFFER_QUOTA WARN window=15m", output[0])
        self.assertEqual(len(output), 3)
        self.assertNotIn("private", repr(output))

    def test_combined_headers_and_policy_order(self):
        headers = {
            "RateLimit": '"8-in-15min";r=6;t=10, "20-in-1day"; r=1; t=90',
            "RateLimit-Policy": '"20-in-1day";q=20;w=86400, "8-in-15min";q=8;w=900',
        }
        data = read_limits(headers)
        self.assertEqual(data["15m"]["remaining"], 6)
        self.assertEqual(data["24h"]["remaining"], 1)
        self.assertEqual(data["24h"]["reset_seconds"], 90)

    def test_unknown_policy_and_missing_headers_safe(self):
        self.assertEqual(read_limits(None), {})
        self.assertEqual(read_limits({"RateLimit": '"3"; r=0; t=4'}), {})
        self.assertEqual(report_limits({}, output=lambda _: self.fail("Unexpected log")), {})

    def test_retry_after_parsing(self):
        self.assertEqual(retry_after_seconds({"Retry-After": "753"}), 753)
        self.assertEqual(retry_after_seconds({"Retry-After": "0"}), 0)
        self.assertIsNone(retry_after_seconds({"Retry-After": "soon"}))
        self.assertIsNone(retry_after_seconds({}))
        self.assertIsNone(retry_after_seconds({"Retry-After": "123456789123456"}))


if __name__ == "__main__":
    unittest.main()
