import unittest

from services.revision_rules import (
    explicit_chart_type_targets_from_prompt,
    explicit_visual_targets_from_prompt,
    fallback_table_from_revision_prompt,
    parse_revision_target_indices,
    revision_prompt_add_slide_count,
    revision_prompt_delete_slide_indices,
    revision_prompt_mentions_image,
    revision_prompt_preserve_slide_indices,
)


class RevisionRulesTest(unittest.TestCase):
    def test_resolves_prompt_and_structured_targets(self):
        targets = parse_revision_target_indices(
            revision_prompt="Sua slide 2 va trang cuoi",
            slide_count=5,
            slide_number=3,
        )
        self.assertEqual(targets, [1, 2, 4])

    def test_detects_visual_and_chart_type(self):
        prompt = "Doi slide 2 thanh bieu do duong, slide 4 thanh bang so sanh"
        self.assertEqual(explicit_visual_targets_from_prompt(prompt, 5), {1: "chart", 3: "table"})
        self.assertEqual(explicit_chart_type_targets_from_prompt(prompt, 5), {1: "line"})

    def test_understands_deck_structure_operations(self):
        self.assertEqual(revision_prompt_add_slide_count("Them 2 slide moi"), 2)
        self.assertEqual(revision_prompt_delete_slide_indices("Xoa slide 3", 5), [2])
        self.assertEqual(revision_prompt_preserve_slide_indices("Giu slide 1 nhu cu", 5), [0])

    def test_builds_contract_safe_table_fallback(self):
        table = fallback_table_from_revision_prompt(
            "Sua thanh bang, cot Tieu chi, Thu cong, Thong minh; "
            "hang Toc do, Chi phi, Do chinh xac"
        )
        self.assertIsNotNone(table)
        self.assertEqual(len(table["headers"]), 3)
        self.assertTrue(table["rows"])
        self.assertTrue(all(len(row) == len(table["headers"]) for row in table["rows"]))

    def test_detects_image_request(self):
        self.assertTrue(revision_prompt_mentions_image("Doi anh slide 5 thanh xe o to"))


if __name__ == "__main__":
    unittest.main()
