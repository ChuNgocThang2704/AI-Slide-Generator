import unittest

from fastapi import HTTPException

from services.plan_limits import (
    detect_requested_slide_count,
    enforce_plan_slide_limit,
    resolve_plan_image_limit,
    validate_generation_instruction,
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

    def test_file_content_limit_is_not_bypassed_by_short_instruction(self):
        with self.assertRaises(HTTPException) as raised:
            validate_plan_limits(
                "free",
                None,
                raw_content="x" * 10001,
                count_detection_content="Tao 10 slide tu file",
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_slide_count_is_detected_from_instruction_not_file_body(self):
        target, resolved = validate_plan_limits(
            "pro",
            None,
            raw_content="Noi dung tai lieu khong ghi so slide.",
            count_detection_content="Tao dung 12 slide tu file",
        )
        self.assertEqual((target, resolved), (12, 12))

    def test_image_limit_respects_plan_and_deck_ratio(self):
        self.assertEqual(resolve_plan_image_limit("free", 10), 4)
        self.assertEqual(resolve_plan_image_limit("pro", 30), 15)
        self.assertEqual(resolve_plan_image_limit("ultra", 50), 35)

    def test_final_free_deck_is_capped_without_padding(self):
        short = {"slides": [{"title": str(i)} for i in range(4)]}
        long = {"slides": [{"title": str(i)} for i in range(12)]}
        self.assertEqual(len(enforce_plan_slide_limit(short, "free")["slides"]), 4)
        self.assertEqual(len(enforce_plan_slide_limit(long, "free")["slides"]), 10)

    def test_file_generation_requires_a_meaningful_instruction(self):
        with self.assertRaises(HTTPException) as raised:
            validate_generation_instruction("", has_file=True)
        self.assertEqual(raised.exception.status_code, 400)

        with self.assertRaises(HTTPException):
            validate_generation_instruction("Tao slide tu file", has_file=True)

    def test_file_generation_accepts_purpose_and_scope(self):
        prompt = "Tao bai giang tong quan toan bo tai lieu bang tieng Viet"
        self.assertEqual(
            validate_generation_instruction(prompt, has_file=True),
            prompt,
        )

    def test_topic_only_generation_remains_flexible(self):
        prompt = "Tri tue nhan tao tai Viet Nam"
        self.assertEqual(
            validate_generation_instruction(prompt, has_file=False),
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
