import unittest

from routes.api import (
    _build_slide_spec_payload,
    _review_revised_spec_payload,
    _structured_content_from_spec_payload,
)
from services.deck_contract import (
    assert_deck_structure_locked,
    assign_stable_slide_ids,
    deck_structure_signature,
    paths_by_slide_id,
    specs_by_slide_id,
)


class DeckContractTests(unittest.TestCase):
    def _deck(self):
        return {
            "title": "Python Variables",
            "slides": [
                {"title": "Python Variables", "layout": "intro", "bullets": ["Overview."]},
                {
                    "title": "Operator Comparison",
                    "layout": "text_table",
                    "bullets": ["Compare arithmetic operators."],
                },
                {"title": "Summary and Q&A", "layout": "thankyou", "bullets": ["Review."]},
            ],
        }

    def test_assigns_unique_stable_slide_ids(self):
        deck = assign_stable_slide_ids(self._deck())
        first_signature = deck_structure_signature(deck)

        assign_stable_slide_ids(deck)

        self.assertEqual(deck_structure_signature(deck), first_signature)
        self.assertEqual(len(first_signature), len(set(first_signature)))

    def test_locked_signature_detects_reordering(self):
        deck = assign_stable_slide_ids(self._deck())
        signature = deck_structure_signature(deck)
        deck["_structure_signature"] = list(signature)

        deck["slides"][0], deck["slides"][1] = deck["slides"][1], deck["slides"][0]

        with self.assertRaises(RuntimeError):
            assert_deck_structure_locked(deck)

    def test_visual_maps_are_converted_to_slide_ids(self):
        deck = assign_stable_slide_ids(self._deck())
        table = {"headers": ["Operator", "Meaning"], "rows": [["+", "Addition"]]}
        table_map = specs_by_slide_id(deck, {1: table})
        image_map = paths_by_slide_id(deck, {1: "outputs/operator.png"})
        target_id = deck["slides"][1]["slide_id"]

        self.assertEqual(table_map, {target_id: table})
        self.assertEqual(image_map, {target_id: "outputs/operator.png"})

    def test_payload_and_revision_round_trip_preserve_slide_ids(self):
        deck = assign_stable_slide_ids(self._deck())
        target_id = deck["slides"][1]["slide_id"]
        table = {"headers": ["Operator", "Meaning"], "rows": [["+", "Addition"]]}

        payload = _build_slide_spec_payload(
            task_id="task-1",
            structured_content=deck,
            chart_specs={},
            table_specs={target_id: table},
            image_paths={target_id: "outputs/operator.png"},
        )
        restored = _structured_content_from_spec_payload(payload)

        self.assertEqual(payload["deck"]["slides"][1]["slide_id"], target_id)
        self.assertEqual(payload["deck"]["slides"][1]["table"], table)
        self.assertEqual(restored["slides"][1]["slide_id"], target_id)

    def test_revise_review_preserves_all_slide_ids(self):
        deck = assign_stable_slide_ids(self._deck())
        original_ids = [slide["slide_id"] for slide in deck["slides"]]
        payload = _build_slide_spec_payload(
            task_id="task-2",
            structured_content=deck,
            chart_specs={},
            table_specs={},
            image_paths={},
        )
        payload["deck"]["slides"][0].pop("slide_id")
        payload["deck"]["slides"][2]["title"] = "Unexpected change"

        reviewed = _review_revised_spec_payload(
            payload,
            previous_structured_content=deck,
            revision_prompt="Only rename slide 2",
            plan_targets=[1],
            wants_deck_restructure=False,
            forced_table_targets=set(),
            fallback_table=None,
            chart_type_targets={},
            wants_image_revision=False,
            image_instruction_targets=[],
        )

        reviewed_ids = [
            slide["slide_id"] for slide in reviewed["deck"]["slides"]
        ]
        self.assertEqual(reviewed_ids, original_ids)
        self.assertEqual(
            reviewed["deck"]["slides"][2]["title"],
            deck["slides"][2]["title"],
        )


if __name__ == "__main__":
    unittest.main()
