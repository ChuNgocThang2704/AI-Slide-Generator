import unittest

from fastapi import HTTPException

from services.plan_limits import resolve_plan_image_limit, validate_plan_limits


class PlanLimitsTest(unittest.TestCase):
    def test_free_defaults_to_plan_slide_limit(self):
        target, resolved = validate_plan_limits("free", None, "short input")
        self.assertEqual((target, resolved), (10, 10))

    def test_detects_requested_slide_count_for_paid_plan(self):
        target, resolved = validate_plan_limits("pro", None, "Tao dung 12 slide ve AI")
        self.assertEqual((target, resolved), (12, 12))

    def test_rejects_character_limit_overflow(self):
        with self.assertRaises(HTTPException) as raised:
            validate_plan_limits("free", None, "x" * 10001)
        self.assertEqual(raised.exception.status_code, 400)

    def test_image_limit_respects_plan_and_deck_ratio(self):
        self.assertEqual(resolve_plan_image_limit("free", 10), 5)
        self.assertEqual(resolve_plan_image_limit("pro", 30), 15)
        self.assertEqual(resolve_plan_image_limit("ultra", 50), 35)


if __name__ == "__main__":
    unittest.main()
