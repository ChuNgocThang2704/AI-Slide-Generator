import unittest

from services.slide_charts import (
    _inline_series_candidates, _retyped, drop_charted_series_bullets, named_chart_type, normalize_chart_spec,
    suggest_chart_type,
)
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


class ChartTypeTests(unittest.TestCase):
    def test_parts_of_a_whole_are_a_pie(self):
        self.assertEqual(suggest_chart_type(["Robusta", "Arabica", "Khác"], [93, 5, 2], True), "pie")
        self.assertEqual(suggest_chart_type(["A", "B"], [0.6, 0.4], True), "pie")

    def test_percentages_that_are_not_a_whole_stay_bars(self):
        self.assertEqual(suggest_chart_type(["Hà Nội", "Đà Nẵng", "TP.HCM"], [72, 65, 81], True), "bar")

    def test_points_along_time_are_a_line(self):
        self.assertEqual(suggest_chart_type(["2020", "2021", "2022", "2023"], [1.76, 1.74, 1.85, 1.78]), "line")
        self.assertEqual(suggest_chart_type(["Quý 1", "Quý 2", "Quý 3", "Quý 4"], [12, 15, 19, 24]), "line")
        self.assertEqual(suggest_chart_type(["Tháng 1", "Tháng 2", "Tháng 3"], [5, 7, 9], text="xu hướng doanh thu"), "line")

    def test_few_time_points_and_plain_categories_are_bars(self):
        self.assertEqual(suggest_chart_type(["2022", "2023"], [10, 14]), "bar")
        self.assertEqual(suggest_chart_type(["Táo", "Cam", "Xoài"], [12, 30, 21]), "bar")

    def test_many_or_long_categories_go_horizontal(self):
        labels = [f"Sản phẩm {i}" for i in range(9)]
        self.assertEqual(suggest_chart_type(labels, list(range(1, 10))), "bar_horizontal")

    def test_a_named_type_always_wins(self):
        self.assertEqual(named_chart_type("một slide biểu đồ cột sản lượng theo năm"), "bar")
        self.assertEqual(named_chart_type("vẽ biểu đồ tròn thị phần"), "pie")
        self.assertEqual(named_chart_type("add a line chart of revenue"), "line")
        self.assertIsNone(named_chart_type("cột mốc trên con đường phát triển, có biểu đồ"))
        spec = normalize_chart_spec({"title": "t", "chart_type": "bar", "labels": ["2020", "2021", "2022", "2023"], "values": [1, 2, 3, 4]})
        self.assertEqual(_retyped(spec, "biểu đồ cột doanh thu")["chart_type"], "bar")
        self.assertEqual(_retyped(spec, "doanh thu qua các năm")["chart_type"], "line")

    def test_request_without_a_named_type_reads_the_type_off_the_data(self):
        share = _inline_series_candidates("Có biểu đồ cơ cấu giống: Robusta là 93%, Arabica là 5%, Khác là 2%.")
        self.assertEqual(share[0]["spec"]["chart_type"], "pie")
        years = _inline_series_candidates("Thêm biểu đồ doanh thu: 2020 là 10, 2021 là 12, 2022 là 15, 2023 là 19.")
        self.assertEqual(years[0]["spec"]["chart_type"], "line")


if __name__ == "__main__":
    unittest.main()
