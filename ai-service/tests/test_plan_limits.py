import unittest

from fastapi import HTTPException

from services.plan_limits import (
    detect_requested_slide_count,
    enforce_plan_slide_limit,
    resolve_plan_image_limit,
    validate_plan_limits,
)


class PlanLimitsTest(unittest.TestCase):
    def test_slide_count_does_not_join_number_from_previous_line(self):
        prompt = (
            "Tao bai thuyet trinh 7 slide bang tieng Viet.\n"
            "De quan ly: 86\n\n"
            "Slide 7: Ket luan."
        )
        self.assertEqual(detect_requested_slide_count(prompt), 7)

    def test_free_without_count_uses_automatic_length(self):
        target, resolved = validate_plan_limits("free", None, "short input")
        self.assertEqual((target, resolved), (None, None))

    def test_free_honors_explicit_count(self):
        target, resolved = validate_plan_limits("free", None, "Tao dung 4 slide ve AI")
        self.assertEqual((target, resolved), (4, 4))

    def test_free_rejects_count_above_maximum(self):
        with self.assertRaises(HTTPException):
            validate_plan_limits("free", None, "Tao 11 slide ve AI")

    def test_detects_requested_slide_count_for_paid_plan(self):
        target, resolved = validate_plan_limits("pro", None, "Tao dung 12 slide ve AI")
        self.assertEqual((target, resolved), (12, 12))

    def test_rejects_character_limit_overflow(self):
        with self.assertRaises(HTTPException) as raised:
            validate_plan_limits("free", None, "x" * 10001)
        self.assertEqual(raised.exception.status_code, 400)

    def test_image_limit_respects_plan_and_deck_ratio(self):
        self.assertEqual(resolve_plan_image_limit("free", 10), 4)
        self.assertEqual(resolve_plan_image_limit("pro", 30), 15)
        self.assertEqual(resolve_plan_image_limit("ultra", 50), 35)

    def test_final_free_deck_is_capped_without_padding(self):
        short = {"slides": [{"title": str(i)} for i in range(4)]}
        long = {"slides": [{"title": str(i)} for i in range(12)]}
        self.assertEqual(len(enforce_plan_slide_limit(short, "free")["slides"]), 4)
        self.assertEqual(len(enforce_plan_slide_limit(long, "free")["slides"]), 10)


if __name__ == "__main__":
    unittest.main()
