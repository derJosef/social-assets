"""Offline coverage for safe diagnostic categories from untrusted Buffer messages."""
import unittest

from scripts.buffer_error_diagnostics import safe_mutation_diagnosis


class BufferErrorDiagnosticsTests(unittest.TestCase):
    def test_known_api_example(self):
        self.assertEqual(
            safe_mutation_diagnosis({
                "__typename": "InvalidInputError", "message": "Text is required",
            }),
            ("InvalidInputError", "post_text"),
        )

    def test_only_predeclared_categories_are_returned(self):
        cases = {
            "Unable to determine image dimensions": "media_dimensions",
            "Image could not be downloaded": "media_access",
            "Media format is unsupported": "media_format",
            "Invalid dueAt for customScheduled": "posting_time",
            "Text is too long": "post_text",
            "Unknown channelId": "channel",
            "Invalid metadata for LinkedIn": "post_metadata",
            "Not authorized for this channel": "channel",  # category precedence
            "Rate limit exceeded": "limits",
            "An asset is invalid": "media_format",
            "Some unexpected failure": "unknown",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(
                    safe_mutation_diagnosis({
                        "__typename": "InvalidInputError", "message": message,
                    }),
                    ("InvalidInputError", expected),
                )

    def test_untrusted_identifiers_and_text_never_leak(self):
        secret_bits = (
            "Bearer PRIVATE_ACCESS_TOKEN_12345",
            "customer@example.invalid",
            "https://example.invalid/secret-path?token=private",
            "company customer confidential text",
        )
        for fragment in secret_bits:
            with self.subTest(secret=fragment):
                error = {
                    "__typename": "InvalidInputError",
                    "message": f"Image cannot be downloaded: {fragment}\n"
                               f"::error title=HACKED::{fragment}",
                }
                displayed = str(safe_mutation_diagnosis(error))
                self.assertIn("media_access", displayed)
                self.assertNotIn(fragment, displayed)
                self.assertNotIn("HACKED", displayed)
                self.assertNotIn("::error", displayed)
                self.assertNotIn("\n", displayed)

    def test_untrusted_typenames_never_enter_output(self):
        bad = '__typename PRIVATE_SESSION_KEY123\n::warning hacked'
        typ, category = safe_mutation_diagnosis({
            "__typename": bad, "message": "Text is required",
        })
        self.assertEqual((typ, category), ("OtherMutationError", "post_text"))
        self.assertNotIn("PRIVATE_", typ)

    def test_no_message_and_large_message_fail_closed(self):
        for response in (
            None, "invalid", [], {}, {"__typename": "InvalidInputError"},
            {"__typename": "InvalidInputError", "message": ["image", "cannot load"]},
            {"__typename": "InvalidInputError", "message": "Image " * 3000},
        ):
            with self.subTest(response_type=type(response).__name__):
                self.assertEqual(safe_mutation_diagnosis(response)[1], "unknown")

    def test_no_raw_message_on_known_other_error_types(self):
        for typename in ("MutationError", "VoidMutationError", "LimitReachedError"):
            with self.subTest(typename=typename):
                self.assertEqual(safe_mutation_diagnosis({
                    "__typename": typename,
                    "message": "Rate limit exceeded for SECRET_ACCOUNT",
                }), (typename, "limits"))


if __name__ == "__main__":
    unittest.main()
