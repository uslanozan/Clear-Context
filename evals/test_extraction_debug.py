"""Offline checks for the extraction QA harness; no network calls."""

import json
import unittest
from pathlib import Path
from uuid import uuid4

import httpx
from extraction_debug import CaptureTransport, Trace, inspect_content, quote_diagnostic


def content(quote):
    return json.dumps(
        {
            "extractions": [
                {
                    "claim": quote,
                    "claim_attributes": {
                        "statement": "A statement",
                        "group": "A group",
                    },
                }
            ]
        }
    )


class ExtractionDebugTests(unittest.TestCase):
    def test_escaped_json_decodes_before_quote_matching(self):
        source = 'He wrote "hello".\nA second line.'
        result = inspect_content(content(source), source)
        self.assertEqual(result["outcome"], "exact_quotes")

    def test_invisible_difference_is_not_reported_as_exact(self):
        result = quote_diagnostic("Marie Curie", "Marie\u200b\u200b Curie")
        self.assertEqual(result["classification"], "invisible_character_difference")
        self.assertFalse(result["exact"])
        self.assertEqual(result["original_source_candidate"], "Marie\u200b\u200b Curie")

    def test_apostrophe_difference_has_a_source_candidate(self):
        result = quote_diagnostic("axolotl’s genus", "axolotl's genus")
        self.assertEqual(result["classification"], "invisible_or_apostrophe_difference")
        self.assertFalse(result["exact"])

    def test_changed_number_is_not_formatting_difference(self):
        self.assertEqual(
            quote_diagnostic("She died at 45", "She died at 35")["classification"],
            "unmatched_source_quote",
        )

    def test_ambiguous_candidates_are_not_silently_selected(self):
        result = quote_diagnostic("a’b", "a'b and a'b")
        self.assertEqual(result["candidate_count"], 2)
        self.assertNotIn("candidate_span", result)

    def test_empty_result_does_not_become_overall_success(self):
        result = inspect_content('{"extractions": []}', "The Earth is spherical.")
        self.assertTrue(result["schema_valid"])
        self.assertEqual(result["outcome"], "empty_extraction")
        self.assertEqual(result["semantic_qa"], "not_evaluated")

    def test_duplicate_json_keys_are_rejected(self):
        self.assertEqual(
            inspect_content('{"extractions": [], "extractions": []}', "source")[
                "outcome"
            ],
            "invalid_json",
        )

    def test_wrong_types_and_extra_fields_are_rejected(self):
        self.assertEqual(
            inspect_content('{"extractions": [], "unexpected": 1}', "source")[
                "outcome"
            ],
            "invalid_schema",
        )
        self.assertEqual(
            inspect_content('{"extractions": "none"}', "source")["outcome"],
            "invalid_schema",
        )

    def test_trace_is_ordered_and_request_guard_prevents_network(self):
        local_root = Path.cwd() / ".local" / "qa-checks"
        directory = local_root / uuid4().hex
        self.assertTrue(directory.resolve().is_relative_to(local_root.resolve()))
        trace = Trace(directory)
        inspect_content(content("source"), "source", trace)
        events = [
            json.loads(line)
            for line in (trace.directory / "events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            [e["sequence"] for e in events], list(range(1, len(events) + 1))
        )
        transport = CaptureTransport(trace, "expected", "low")
        try:
            request = httpx.Request(
                "POST",
                "https://api.meta.ai/v1/chat/completions",
                json={
                    "model": "muse-spark-1.3",
                    "reasoning_effort": "low",
                    "messages": [{"role": "user", "content": "wrong source"}],
                },
            )
            with self.assertRaisesRegex(ValueError, "expected source"):
                transport.handle_request(request)
            self.assertEqual(transport.calls, 0)
        finally:
            transport.close()

    def test_transport_archives_payload_without_authorization_headers(self):
        directory = Path.cwd() / ".local" / "qa-checks" / uuid4().hex
        trace = Trace(directory)
        transport = CaptureTransport(trace, "source", "low")
        transport.inner.close()
        transport.inner = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": []})
        )
        payload = {
            "model": "muse-spark-1.3",
            "reasoning_effort": "low",
            "messages": [{"role": "user", "content": json.dumps({"source": "source"})}],
        }
        request = httpx.Request(
            "POST",
            "https://api.meta.ai/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer synthetic-test-secret"},
        )
        try:
            transport.handle_request(request)
            self.assertEqual(transport.calls, 1)
            self.assertEqual(
                json.loads((directory / "request.json").read_text()), payload
            )
            self.assertNotIn(
                "synthetic-test-secret",
                "".join(p.read_text() for p in directory.iterdir()),
            )
            with self.assertRaisesRegex(RuntimeError, "One-call"):
                transport.handle_request(request)
        finally:
            transport.close()


if __name__ == "__main__":
    unittest.main()
