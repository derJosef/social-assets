"""Offline API and batching regressions. No network requests or publications."""

import io
import json
import sys
import unittest
import urllib.error
from email.message import Message
from unittest import mock

from scripts import buffer_draft as m


class BufferApiSafetyTests(unittest.TestCase):
    def test_429_uses_retry_after_without_retry_or_body_leak(self):
        headers = Message()
        headers["Retry-After"] = "753"
        headers.add_header("RateLimit", '"150-in-15min";r=0;t=753')
        headers.add_header("RateLimit-Policy", '"150-in-15min";q=150;w=900;pk=:SECRET:')
        error = urllib.error.HTTPError(
            "https://api.buffer.com", 429, "Too many requests", headers, io.BytesIO(b"private body"))
        with mock.patch.object(m.urllib.request, "urlopen", side_effect=error) as urlopen, \
             mock.patch.object(m, "report_limits") as report:
            with self.assertRaisesRegex(RuntimeError, "Retry-After=753s") as raised:
                m.buffer_graphql("dummy-token", m.CREATE_DATED_DRAFT, {})
        self.assertNotIn("SECRET", str(raised.exception))
        self.assertNotIn("private body", str(raised.exception))
        self.assertEqual(urlopen.call_count, 1)
        report.assert_called_once()

    def test_channels_lookup_shared_only_within_batch(self):
        calls = []
        def fake_api(token, query, variables):
            calls.append(query)
            if query == m.GET_ORGANIZATIONS:
                return {"account": {"organizations": [{"id": "org"}]}}
            if query == m.GET_CHANNELS:
                return {"channels": [{"id": "li", "service": "linkedin"},
                                     {"id": "fb", "service": "facebook"},
                                     {"id": "ig", "service": "instagram"}]}
            self.fail("Unexpected query")
        cache = {}
        with mock.patch.object(m, "buffer_graphql", side_effect=fake_api):
            self.assertEqual(m.resolve_channel("dummy", "linkedin", channel_cache=cache), "li")
            self.assertEqual(m.resolve_channel("dummy", "facebook", channel_cache=cache), "fb")
            self.assertEqual(m.resolve_channel("dummy", "instagram", channel_cache=cache), "ig")
            with self.assertRaises(RuntimeError):
                m.resolve_channel("dummy", "facebook", "li", channel_cache=cache)
            self.assertEqual(len(calls), 2)
            self.assertEqual(m.resolve_channel("dummy", "linkedin"), "li")
            self.assertEqual(len(calls), 4)

    def test_batch_validates_all_before_first_write(self):
        def read_draft(path):
            if path.endswith("bad.json"):
                raise ValueError("Invalid final draft")
            return path, "text", b'{"target":"linkedin"}'
        with mock.patch.object(m, "read_draft", side_effect=read_draft), \
             mock.patch.object(m, "send_draft") as send, \
             mock.patch.object(sys, "argv", ["buffer_draft.py", "--draft", "drafts/good.json",
                                             "--draft", "drafts/bad.json", "--send"]):
            self.assertEqual(m.main(), 1)
            send.assert_not_called()

    def test_batch_uses_same_in_memory_cache(self):
        with mock.patch.object(m, "read_draft",
                               side_effect=lambda path: (path, "text", b'{"target":"linkedin"}')), \
             mock.patch.object(m, "send_draft") as send, \
             mock.patch.object(sys, "argv", ["buffer_draft.py", "--draft", "drafts/first.json",
                                             "--draft", "drafts/second.json", "--send"]):
            self.assertEqual(m.main(), 0)
            self.assertEqual(send.call_count, 2)
            self.assertIs(send.call_args_list[0].kwargs["channel_cache"],
                          send.call_args_list[1].kwargs["channel_cache"])


if __name__ == "__main__":
    unittest.main()
