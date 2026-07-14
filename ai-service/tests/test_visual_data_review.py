import json
import unittest

from services.visual_data_review import review_visual_data_specs


class FakeExtractor:
    gemini_available = True

    def __init__(self, repaired, review_pass=False):
        self.repaired = repaired
        self.review_pass = review_pass
        self.repair_calls = 0

    async def _gemini_completion_plain_text(self, messages, **kwargs):
        return json.dumps({
            "decisions": [{
                "slide_index": 0,
                "pass": self.review_pass,
                "confidence": 0.95,
                "reason": "Requested column is missing and one cell is empty",
            }]
        })

    async def extract_table_spec(self, data):
        self.repair_calls += 1
        return self.repaired


class VisualDataReviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_enforces_explicit_schema_even_when_reviewer_passes(self):
        extractor = FakeExtractor({
            "headers": ["Criterion", "Manual", "Smart", "Comment"],
            "rows": [["Speed", "Slow", "Fast", "Improved"]],
        }, review_pass=True)
        structured = {"slides": [{"title": "Comparison", "bullets": ["Manual versus smart"]}]}
        specs = {0: {
            "headers": ["Criterion", "Manual", "Smart"],
            "rows": [["Speed", "Slow", "Fast"]],
        }}
        records = [{"slide_index": 0, "status": "created", "source": "llm", "spec": specs[0]}]

        reviewed, debug = await review_visual_data_specs(
            extractor,
            structured,
            specs,
            records,
            kind="table",
            raw_content="Use columns Criterion, Manual, Smart, Comment.",
        )

        self.assertEqual(reviewed[0]["headers"][-1], "Comment")
        self.assertEqual(debug[0]["status"], "repaired_to_requested_schema")

    async def test_repairs_rejected_table_instead_of_dropping_it(self):
        extractor = FakeExtractor({
            "title": "Comparison",
            "headers": ["Criterion", "Manual", "Smart", "Comment"],
            "rows": [["Speed", "Slow", "Fast", "Improved"]],
        })
        structured = {"slides": [{
            "title": "Comparison",
            "bullets": ["Compare manual and smart operation"],
        }]}
        specs = {0: {
            "title": "Comparison",
            "headers": ["Criterion", "Manual", "Smart"],
            "rows": [["Speed", "Slow", ""]],
        }}
        records = [{"slide_index": 0, "status": "created", "source": "llm", "spec": specs[0]}]

        reviewed, debug = await review_visual_data_specs(
            extractor,
            structured,
            specs,
            records,
            kind="table",
            raw_content="Create a table with Criterion, Manual, Smart, Comment columns.",
        )

        self.assertIn(0, reviewed)
        self.assertEqual(reviewed[0]["headers"][-1], "Comment")
        self.assertEqual(debug[0]["status"], "repaired_after_review")
        self.assertEqual(extractor.repair_calls, 1)

    async def test_drops_table_when_repair_is_still_incomplete(self):
        extractor = FakeExtractor({
            "headers": ["Criterion", "Manual"],
            "rows": [["Speed", ""]],
        })
        structured = {"slides": [{"title": "Comparison", "bullets": ["Comparison"]}]}
        specs = {0: {"headers": ["Criterion", "Manual"], "rows": [["Speed", ""]]}}
        records = [{"slide_index": 0, "status": "created", "source": "llm", "spec": specs[0]}]

        reviewed, debug = await review_visual_data_specs(
            extractor, structured, specs, records, kind="table", raw_content="Create a table."
        )

        self.assertNotIn(0, reviewed)
        self.assertEqual(debug[0]["status"], "gemini_rejected")


if __name__ == "__main__":
    unittest.main()
