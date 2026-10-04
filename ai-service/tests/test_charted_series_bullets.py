import unittest

from services.slide_charts import _inline_series_candidates, drop_charted_series_bullets
from services.slide_quality import _CHART_REQUEST


class ChartedSeriesBulletTests(unittest.TestCase):
    def test_bare_data_points_leave_when_real_bullets_remain(self):
        slide = {"bullets": ["2020: 1.76", "2021: 1.74", "2022: 1.85", "Sản lượng lập đỉnh năm 2022", "Năm 2023 giảm nhẹ do thời tiết"]}
        self.assertEqual(drop_charted_series_bullets(slide), 3)
        self.assertEqual(slide["bullets"], ["Sản lượng lập đỉnh năm 2022", "Năm 2023 giảm nhẹ do thời tiết"])

    def test_nothing_is_removed_when_too_little_text_would_stay(self):
        slide = {"bullets": ["2020: 1.76", "2021: 1.74", "2022: 1.85", "Một nhận xét"]}
        self.assertEqual(drop_charted_series_bullets(slide), 0)
        self.assertEqual(len(slide["bullets"]), 4)

    def test_a_point_with_an_explanation_is_kept(self):
        slide = {"bullets": ["2020: 1.76 triệu tấn nhờ thời tiết thuận lợi", "2021: 1.74", "2022: 1.85", "a b", "c d"]}
        self.assertEqual(drop_charted_series_bullets(slide), 0)

    def test_chart_request_is_recognised_in_both_languages(self):
        self.assertTrue(_CHART_REQUEST.search("Có một slide biểu đồ cột sản lượng"))
        self.assertTrue(_CHART_REQUEST.search("add a bar chart of revenue"))
        self.assertFalse(_CHART_REQUEST.search("một bảng so sánh Arabica và Robusta"))

    def test_series_dictated_in_the_request_becomes_a_chart_candidate(self):
        found = _inline_series_candidates(
            "Tạo 6 slide về cà phê. Có một slide biểu đồ cột sản lượng theo năm: 2020 là 1,76 triệu tấn, "
            "2021 là 1,74, 2022 là 1,85, 2023 là 1,78. Có một slide bảng so sánh Arabica và Robusta."
        )
        self.assertEqual(len(found), 1)
        spec = found[0]["spec"]
        self.assertEqual(spec["chart_type"], "bar")
        self.assertEqual(spec["labels"], ["2020", "2021", "2022", "2023"])
        self.assertEqual(spec["values"], [1.76, 1.74, 1.85, 1.78])
        self.assertIn("triệu tấn", spec["title"])

    def test_english_request_and_line_chart(self):
        found = _inline_series_candidates("Add a line chart of revenue: Q1 = 12, Q2 = 15, Q3 = 19 and Q4 = 24.")
        self.assertEqual(found[0]["spec"]["chart_type"], "line")
        self.assertEqual(found[0]["spec"]["values"], [12.0, 15.0, 19.0, 24.0])

    def test_a_chart_mention_without_data_gives_nothing(self):
        self.assertEqual(_inline_series_candidates("Thêm một biểu đồ minh hoạ cho slide 3."), [])


if __name__ == "__main__":
    unittest.main()
