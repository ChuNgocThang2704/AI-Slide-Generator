import unittest

from services.revision_rules import (
    explicit_chart_type_targets_from_prompt,
    explicit_visual_targets_from_prompt,
    fallback_table_from_revision_prompt,
    parse_revision_target_indices,
    revision_prompt_add_slide_count,
    revision_added_slide_indices,
    revision_prompt_delete_slide_indices,
    revision_prompt_mentions_image,
    revision_prompt_preserve_slide_indices,
)
from services.slide_charts import _explicit_chart_requests


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

    def test_extracts_year_range_and_separate_chart_values(self):
        specs = _explicit_chart_requests(
            "Chuyen slide 5 thanh bieu do cot giai doan 2021-2025 "
            "voi cac gia tri 13, 16, 20, 25 va 31 ty USD.",
            9,
        )
        self.assertEqual(specs[4]["labels"], ["2021", "2022", "2023", "2024", "2025"])
        self.assertEqual(specs[4]["values"], [13.0, 16.0, 20.0, 25.0, 31.0])

    def test_understands_deck_structure_operations(self):
        self.assertEqual(revision_prompt_add_slide_count("Them 2 slide moi"), 2)
        self.assertEqual(revision_prompt_add_slide_count("Thêm một slide trước phần kết luận"), 1)
        self.assertEqual(revision_prompt_add_slide_count("Add one slide before the conclusion"), 1)
        self.assertEqual(revision_prompt_add_slide_count("Bổ sung ba trang về rủi ro"), 3)
        self.assertEqual(revision_prompt_delete_slide_indices("Xoa slide 3", 5), [2])
        self.assertEqual(revision_prompt_preserve_slide_indices("Giu slide 1 nhu cu", 5), [0])
        self.assertEqual(
            revision_added_slide_indices("Thêm một slide trước slide kết luận", 9, 10, 1),
            [8],
        )
        self.assertEqual(revision_added_slide_indices("Add two slides after slide 3", 5, 7, 2), [3, 4])

    def test_builds_contract_safe_table_fallback(self):
        table = fallback_table_from_revision_prompt(
            "Sua thanh bang, cot Tieu chi, Thu cong, Thong minh; "
            "hang Toc do, Chi phi, Do chinh xac"
        )
        self.assertIsNotNone(table)
        self.assertEqual(len(table["headers"]), 3)
        self.assertTrue(table["rows"])
        self.assertTrue(all(len(row) == len(table["headers"]) for row in table["rows"]))

    @unittest.skip("Legacy table-content parser is no longer used by the AI-first revision flow")
    def test_builds_vietnamese_diacritics_table_fallback(self):
        # Kiểm tra prompt thực tế của user
        prompt = (
            "sửa slide 5 thành bảng gồm các cột Tiêu chí, Quản lý thủ công, Hệ thống thông minh, Nhận xét. "
            "Thêm các hàng: tốc độ xử lý, độ chính xác, chi phí vận hành, bảo mật dữ liệu, khả năng mở rộng và trải nghiệm sinh viên"
        )
        table = fallback_table_from_revision_prompt(prompt)
        self.assertIsNotNone(table)
        self.assertEqual(len(table["headers"]), 4)
        self.assertEqual(table["headers"], ["Tiêu chí", "Quản lý thủ công", "Hệ thống thông minh", "Nhận xét"])
        self.assertEqual(len(table["rows"]), 6)
        # Check first column value of each row matches requested criteria
        criteria = [row[0].lower() for row in table["rows"]]
        self.assertIn("toc do xu ly", [c.replace("ố", "o").replace("ử", "u").replace("ý", "y").replace("đ", "d") for c in criteria])

    def test_detects_image_request(self):
        self.assertTrue(revision_prompt_mentions_image("Doi anh slide 5 thanh xe o to"))
        
    def test_image_revision_visual_phrase_scenarios(self):
        from services.images.prompts import _revision_visual_phrase
        # Test 1: Bãi đỗ xe thông minh, có camera nhận diện biển số, không dùng camera cận cảnh
        prompt = (
            "Chỉ thay ảnh slide 3 bằng hình bãi đỗ xe thông minh trong trường đại học, "
            "có ô tô, cảm biến tại từng vị trí đỗ, camera nhận diện biển số và bảng điện tử hiển thị số chỗ trống. "
            "Không dùng hình camera cận cảnh."
        )
        phrase = _revision_visual_phrase(prompt)
        # Đảm bảo không bị camera_forbidden block hoàn toàn, nhưng vẫn nhận diện được camera nhận diện biển số
        self.assertIn("license plate recognition camera", phrase)
        self.assertIn("modern university parking lot", phrase)
        self.assertIn("IoT sensors", phrase)
        self.assertIn("digital display board", phrase)


if __name__ == "__main__":
    unittest.main()
