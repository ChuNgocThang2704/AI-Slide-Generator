import json
import unittest

from services.visual_data_review import _table_semantic_alignment, review_visual_data_specs


def test_table_alignment_rejects_neighbor_table_with_only_domain_overlap():
    spec = {
        "title": "Python Variable Naming Rules",
        "headers": ["Rule", "Description", "Example"],
        "rows": [["Keywords", "Cannot use reserved words", "class"]],
    }

    alignment = _table_semantic_alignment(
        spec,
        "Debugging: Understanding Error Types\nSyntax errors stop parsing.\n"
        "Runtime errors occur during execution.\nSemantic errors produce wrong results.",
    )

    assert alignment["hard_mismatch"] is True


def test_table_alignment_rejects_wrong_subject_even_when_body_shares_result_word():
    spec = {
        "title": "Python Operator Precedence (PEMDAS)",
        "headers": ["Operator Type", "Precedence", "Example", "Result"],
        "rows": [["Exponentiation", "High", "3 ** 2", "9"]],
    }

    alignment = _table_semantic_alignment(
        spec,
        "Types of Program Errors: Syntax, Runtime, and Semantic\n"
        "Semantic errors produce an unintended result.",
    )

    assert alignment["overlap"] == ["result"]
    assert alignment["title_overlap"] == []
    assert alignment["hard_mismatch"] is True


def test_table_alignment_rejects_variable_names_for_generic_syntax_error_title():
    spec = {
        "title": "Variable Naming Rules and Errors",
        "headers": ["Category", "Example", "Explanation"],
        "rows": [
            ["Legal Name", "message", "Meaningful variable name"],
            ["Illegal Name", "76trombones", "Cannot begin with a number"],
        ],
    }

    alignment = _table_semantic_alignment(
        spec,
        "Understanding Syntax Errors\n"
        "Syntax errors violate grammar before a program can execute.",
    )

    assert alignment["title_overlap"] == []
    assert alignment["hard_mismatch"] is True


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

    async def _llm_completion_plain_text(self, messages, **kwargs):
        return await self._gemini_completion_plain_text(messages, **kwargs)

    async def extract_table_spec(self, data):
        self.repair_calls += 1
        return self.repaired


class NoReviewerExtractor:
    pass


class VisualDataReviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_drops_later_identical_visual_spec(self):
        extractor = FakeExtractor(None, review_pass=True)
        spec = {
            "headers": ["Term", "Meaning"],
            "rows": [["Variable", "A name that refers to a value"]],
        }
        structured = {
            "slides": [
                {"title": "Variables", "bullets": ["A variable refers to a value."]},
                {"title": "Comments", "bullets": ["Comments explain code intent."]},
            ]
        }
        specs = {0: dict(spec), 1: dict(spec)}
        records = [
            {"slide_index": 0, "status": "created", "source": "llm", "spec": specs[0]},
            {"slide_index": 1, "status": "created", "source": "llm", "spec": specs[1]},
        ]

        reviewed, debug = await review_visual_data_specs(
            extractor, structured, specs, records, kind="table", raw_content=""
        )

        self.assertIn(0, reviewed)
        self.assertNotIn(1, reviewed)
        self.assertEqual(debug[1]["status"], "duplicate_rejected")
        self.assertEqual(debug[1]["duplicate_of_slide_index"], 0)

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

    async def test_repairs_complete_table_attached_to_wrong_slide_subject(self):
        extractor = FakeExtractor({
            "title": "Programming errors",
            "headers": ["Error type", "Description", "Example"],
            "rows": [
                ["Syntax error", "Invalid program grammar", "1 = x"],
                ["Runtime error", "Fails while executing", "10 / 0"],
                ["Semantic error", "Runs with the wrong result", "Wrong formula"],
            ],
        }, review_pass=True)
        structured = {"slides": [{
            "title": "Types of programming errors",
            "bullets": [
                "Syntax errors prevent parsing.",
                "Runtime errors fail during execution.",
                "Semantic errors produce an unintended result.",
            ],
        }]}
        specs = {0: {
            "title": "Operator precedence",
            "headers": ["Operator", "Priority", "Example"],
            "rows": [
                ["Parentheses", "Highest", "(1 + 1) * 3"],
                ["Exponentiation", "High", "2 ** 3"],
            ],
        }}
        records = [{"slide_index": 0, "status": "created", "source": "inline_json", "spec": specs[0]}]

        reviewed, debug = await review_visual_data_specs(
            extractor,
            structured,
            specs,
            records,
            kind="table",
            raw_content=(
                "The lesson covers operator precedence first, then syntax errors, "
                "runtime errors, and semantic errors."
            ),
        )

        self.assertEqual(reviewed[0]["headers"][0], "Error type")
        self.assertEqual(debug[0]["status"], "repaired_after_review")
        self.assertEqual(extractor.repair_calls, 1)

    async def test_drops_wrong_subject_table_when_reviewer_is_unavailable(self):
        structured = {"slides": [{
            "title": "Types of programming errors",
            "bullets": ["Syntax, runtime, and semantic errors have different causes."],
        }]}
        specs = {0: {
            "headers": ["Operator", "Priority"],
            "rows": [["Parentheses", "Highest"], ["Exponentiation", "High"]],
        }}
        records = [{"slide_index": 0, "status": "created", "source": "inline_json", "spec": specs[0]}]

        reviewed, debug = await review_visual_data_specs(
            NoReviewerExtractor(),
            structured,
            specs,
            records,
            kind="table",
            raw_content="",
        )

        self.assertNotIn(0, reviewed)
        self.assertEqual(debug[0]["status"], "semantic_mismatch_rejected")


if __name__ == "__main__":
    unittest.main()
