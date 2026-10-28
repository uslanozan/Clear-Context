"""Offline checks for instruction-role separation."""

import unittest
from copy import deepcopy

from langextract_instructions import move_rules_to_system


class InstructionRoleTests(unittest.TestCase):
    def test_moves_exact_prefix_without_changing_remainder(self):
        rules = "Extract claims. Preserve dates."
        remainder = "\nContext: tr\nExample: A\nSource: Original source."
        before = [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": rules + remainder},
        ]
        original = deepcopy(before)
        after = move_rules_to_system(before, rules)
        self.assertEqual(after[0]["content"], "Return JSON.\n\n" + rules)
        self.assertEqual(after[1]["content"], remainder)
        self.assertEqual(before, original)

    def test_source_containing_rule_text_is_not_rewritten(self):
        rules = "Extract claims."
        remainder = "\nSource: The sign says Extract claims. exactly."
        after = move_rules_to_system(
            [{"role": "user", "content": rules + remainder}], rules
        )
        self.assertEqual(after[1]["content"], remainder)

    def test_mismatched_prefix_fails_before_inference(self):
        with self.assertRaisesRegex(ValueError, "expected prompt prefix"):
            move_rules_to_system(
                [{"role": "user", "content": "Unexpected prompt"}], "Rules"
            )

    def test_empty_rules_and_ambiguous_messages_are_rejected(self):
        for messages, rules in [
            ([], ""),
            ([], "Rules"),
            ([{"role": "user", "content": "Rules"}] * 2, "Rules"),
        ]:
            with self.assertRaises(ValueError):
                move_rules_to_system(messages, rules)


if __name__ == "__main__":
    unittest.main()
