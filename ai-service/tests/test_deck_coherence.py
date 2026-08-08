import copy
import json
import unittest

from services.deck_coherence import improve_deck_coherence


class FakeExtractor:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = 0
        self.messages = []
        self._source_content = ""
        self._user_instruction = ""

    async def _llm_completion_plain_text(self, messages, **kwargs):
        self.calls += 1
        self.messages.append(messages)
        if self.error:
            raise self.error
        return json.dumps(self.responses.pop(0), ensure_ascii=False)


def sample_deck():
    return {
        "title": "Smart parking",
        "slides": [
            {
                "title": "Tong quan",
                "bullets": ["Van de", "Muc tieu"],
                "notes": "Mo dau.",
                "layout": "text_only",
            },
            {
                "title": "So sanh",
                "bullets": ["Thu cong", "Thong minh"],
                "notes": "Trinh bay bang.",
                "layout": "text_table",
                "table": {"headers": ["Tieu chi", "Thu cong"], "rows": [["Toc do", "Cham"]]},
            },
        ],
    }


class DeckCoherenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_judge_receives_late_source_results(self):
        deck = sample_deck()
        extractor = FakeExtractor([{"score": 9.0, "issues": []}])
        extractor._source_content = "A" * 13000 + " LATE_PRIMARY_RESULT accuracy 95.76 percent"

        result = await improve_deck_coherence(extractor, deck)

        self.assertIs(result, deck)
        judge_payload = extractor.messages[0][1]["content"]
        self.assertIn("LATE_PRIMARY_RESULT", judge_payload)
        judge_prompt = extractor.messages[0][0]["content"]
        self.assertIn("indispensable findings", judge_prompt)
        self.assertIn("assumed current date", judge_prompt)

    async def test_explicit_missing_topic_replaces_redundant_body_slide(self):
        deck = {
            "title": "Python Chapter 2",
            "presentation_mode": "lecture",
            "slides": [
                {
                    "title": "Python Chapter 2",
                    "layout": "intro",
                    "bullets": ["Variables, expressions, and errors."],
                },
                {
                    "title": "Learning Objectives",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Distinguish syntax, runtime, and semantic errors."],
                },
                {
                    "title": "Operator Precedence",
                    "pedagogical_role": "concept",
                    "bullets": ["Parentheses are evaluated first."],
                },
                {
                    "title": "More PEMDAS Examples",
                    "pedagogical_role": "worked_example",
                    "bullets": ["Evaluate multiplication before addition."],
                },
                {
                    "title": "Summary",
                    "layout": "thankyou",
                    "pedagogical_role": "summary",
                    "bullets": ["Review errors and expressions."],
                },
            ],
        }
        extractor = FakeExtractor([
            {
                "requirements": [
                    {
                        "topic": "program error types",
                        "required_components": [
                            "syntax errors",
                            "runtime errors",
                            "semantic errors",
                        ],
                        "covered_components": ["syntax errors"],
                        "missing_components": ["runtime errors", "semantic errors"],
                        "covered_by": [3],
                        "target_index": 3,
                    },
                ],
                "issues": [],
            },
            {"score": 8.5, "issues": []},
            {
                "slides": [{
                    "index": 3,
                    "title": "Syntax, Runtime, and Semantic Errors",
                    "bullets": [
                        "Syntax errors violate Python grammar and stop parsing.",
                        "Runtime errors occur while otherwise valid code executes.",
                        "Semantic errors run but produce the wrong result.",
                    ],
                    "notes": "Contrast when and how each error is detected.",
                    "pedagogical_role": "concept",
                }],
            },
            {"score": 9.2, "issues": []},
        ])
        extractor._user_instruction = (
            "Cover variables, expressions, operator precedence, and syntax, runtime, "
            "and semantic errors."
        )

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(
            result["slides"][3]["title"],
            "Syntax, Runtime, and Semantic Errors",
        )
        self.assertEqual(len(result["slides"]), 5)
        audit_prompt = extractor.messages[0][0]["content"]
        self.assertIn("does NOT count as coverage", audit_prompt)
        self.assertEqual(extractor.calls, 4)

    async def test_missing_components_are_not_dropped_when_target_is_null(self):
        deck = {
            "title": "Python Chapter 2",
            "presentation_mode": "lecture",
            "slides": [
                {"title": "Python Chapter 2", "layout": "intro", "bullets": ["Overview."]},
                {
                    "title": "Learning Objectives",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Distinguish program error types."],
                },
                {"title": "Variables", "bullets": ["Variables refer to values."]},
                {"title": "Syntax Errors", "bullets": ["Syntax errors violate grammar rules."]},
                {
                    "title": "Summary",
                    "layout": "thankyou",
                    "pedagogical_role": "summary",
                    "bullets": ["Review the chapter."],
                },
            ],
        }
        extractor = FakeExtractor([
            {
                "requirements": [{
                    "topic": "program error types",
                    "required_components": ["syntax errors", "runtime errors", "semantic errors"],
                    "covered_components": ["syntax errors"],
                    "missing_components": ["runtime errors", "semantic errors"],
                    "covered_by": [3],
                    "target_index": None,
                }],
                "issues": [],
            },
            {"score": 7.0, "issues": []},
            {"slides": [{
                "index": 3,
                "title": "Syntax, Runtime, and Semantic Errors",
                "bullets": [
                    "Syntax errors violate grammar rules.",
                    "Runtime errors occur during execution.",
                    "Semantic errors produce unintended results.",
                ],
                "notes": "Compare when each category is detected.",
            }]},
            {"score": 9.0, "issues": []},
        ])
        extractor._user_instruction = "Cover syntax, runtime, and semantic errors."

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(result["slides"][3]["title"], "Syntax, Runtime, and Semantic Errors")
        self.assertEqual(extractor.calls, 4)

    async def test_refines_only_target_text_and_preserves_visual_data(self):
        deck = sample_deck()
        original = copy.deepcopy(deck)
        extractor = FakeExtractor([
            {
                "score": 6.5,
                "issues": [{
                    "index": 1,
                    "type": "redundancy",
                    "severity": "high",
                    "instruction": "Connect the comparison to the opening problem.",
                }],
            },
            {
                "slides": [{
                    "index": 1,
                    "title": "Tu van de den giai phap",
                    "bullets": ["Quy trinh thu cong gay cham tre", "He thong thong minh rut ngan thoi gian"],
                    "notes": "Lien ket van de voi bang so sanh.",
                }],
            },
            {"score": 9.0, "issues": []},
        ])

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(result["slides"][0], original["slides"][0])
        self.assertEqual(result["slides"][1]["title"], "Tu van de den giai phap")
        self.assertEqual(result["slides"][1]["layout"], "text_table")
        self.assertEqual(result["slides"][1]["table"], original["slides"][1]["table"])
        self.assertEqual(deck, original)
        self.assertEqual(extractor.calls, 3)

    async def test_lecture_review_uses_source_and_repairs_factual_issue_twice(self):
        deck = {
            "title": "Python Variables",
            "presentation_mode": "lecture",
            "learning_objectives": ["Explain valid Python variable names."],
            "slides": [
                {
                    "title": "Python Variables",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Explain valid Python variable names."],
                    "notes": "Introduce the lesson.",
                    "layout": "intro",
                },
                {
                    "title": "Variable names",
                    "pedagogical_role": "concept",
                    "bullets": ["Python variable names may only use lowercase letters."],
                    "notes": "Explain the naming rule.",
                    "layout": "text_only",
                }
            ],
        }
        extractor = FakeExtractor([
            {
                "score": 5,
                "issues": [{
                    "index": 1,
                    "type": "factual_error",
                    "severity": "high",
                    "instruction": "Correct the naming rule and include a supported example.",
                }],
            },
            {
                "slides": [{
                    "index": 1,
                    "title": "Valid Python variable names",
                    "bullets": [
                        "Names may contain letters, digits, and underscores, but cannot begin with a digit.",
                        "For example, user_2 is valid while 2_user is invalid.",
                    ],
                    "notes": "Contrast the two examples.",
                }],
            },
            {
                "score": 7,
                "issues": [{
                    "index": 1,
                    "type": "missing_example",
                    "severity": "medium",
                    "instruction": "Explain why the invalid example fails.",
                }],
            },
            {
                "slides": [{
                    "index": 1,
                    "title": "Valid Python variable names",
                    "bullets": [
                        "Names may contain letters, digits, and underscores, but cannot begin with a digit.",
                        "The name user_2 is valid; 2_user fails because its first character is a digit.",
                    ],
                    "notes": "Contrast the two examples and ask learners to classify another name.",
                }],
            },
        ])
        extractor._source_content = (
            "Variable names can contain letters, numbers and underscores, "
            "but cannot begin with a number. user_2 is valid and 2_user is invalid."
        )

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(extractor.calls, 4)
        self.assertIn("cannot begin with a digit", result["slides"][1]["bullets"][0])
        first_payload = extractor.messages[0][1]["content"]
        self.assertIn("user_2 is valid", first_payload)
        self.assertEqual(result["slides"][1]["pedagogical_role"], "concept")

    async def test_revision_scope_blocks_changes_to_other_slides(self):
        deck = sample_deck()
        extractor = FakeExtractor([{
            "score": 5,
            "issues": [{
                "index": 1,
                "type": "duplicate_content",
                "severity": "high",
                "instruction": "Remove repetition.",
            }],
        }])

        result = await improve_deck_coherence(extractor, deck, allowed_indices=[0])

        self.assertIs(result, deck)
        self.assertEqual(extractor.calls, 1)

    async def test_lecture_without_teaching_support_converts_middle_slide(self):
        deck = {
            "title": "Database Indexes",
            "presentation_mode": "lecture",
            "learning_objectives": ["Explain how an index changes lookup cost."],
            "slides": [
                {
                    "title": "Database Indexes",
                    "layout": "intro",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Explain how an index changes lookup cost."],
                },
                {
                    "title": "Index lookup",
                    "layout": "text_only",
                    "pedagogical_role": "concept",
                    "bullets": ["An index narrows the records scanned for a matching key."],
                },
                {
                    "title": "Summary",
                    "layout": "thankyou",
                    "pedagogical_role": "summary",
                    "bullets": ["Indexes trade write cost for faster lookup."],
                },
            ],
        }
        extractor = FakeExtractor([
            {
                "score": 7,
                "issues": [{
                    "index": 1,
                    "type": "missing_example",
                    "severity": "medium",
                    "instruction": "Convert this concept into a source-grounded knowledge check.",
                }],
            },
            {
                "slides": [{
                    "index": 1,
                    "title": "Check an index lookup",
                    "bullets": [
                        "Compare which records are scanned with and without the stated index.",
                        "Explain why narrowing the scanned records changes lookup cost.",
                    ],
                    "notes": "Ask learners to justify the comparison from the source.",
                    "pedagogical_role": "knowledge_check",
                }],
            },
            {"score": 9, "issues": []},
        ])
        extractor._source_content = (
            "An index narrows records scanned for a matching key, improving lookup "
            "while adding storage and write maintenance cost."
        )

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(result["slides"][1]["pedagogical_role"], "knowledge_check")
        profile_payload = json.loads(extractor.messages[0][1]["content"])
        self.assertEqual(profile_payload["deck_profile"]["teaching_support_count"], 0)
        self.assertEqual(extractor.calls, 3)

    async def test_presentation_repairs_weak_support_without_forcing_lecture_role(self):
        deck = {
            "title": "Cloud Migration",
            "presentation_mode": "presentation",
            "slides": [
                {
                    "title": "Migration proposal",
                    "layout": "intro",
                    "bullets": ["Move the service to managed infrastructure."],
                },
                {
                    "title": "Recommended approach",
                    "layout": "text_only",
                    "bullets": ["The managed platform is the best option."],
                },
            ],
        }
        extractor = FakeExtractor([
            {
                "score": 6,
                "issues": [{
                    "index": 1,
                    "type": "insufficient_evidence",
                    "severity": "high",
                    "instruction": "Support the recommendation with the source-backed operational rationale.",
                }],
            },
            {
                "slides": [{
                    "index": 1,
                    "title": "Managed platform recommendation",
                    "bullets": [
                        "Managed backups remove the manual recovery step required by the current deployment.",
                        "The recommendation addresses the documented recovery-time constraint without changing application scope.",
                    ],
                    "notes": "Connect the recommendation to the recovery requirement.",
                    "pedagogical_role": "practice",
                }],
            },
            {"score": 9, "issues": []},
        ])
        extractor._source_content = (
            "The current deployment requires manual backups. The target recovery-time "
            "requirement is supported by managed backups on the proposed platform."
        )

        result = await improve_deck_coherence(extractor, deck)

        self.assertNotIn("pedagogical_role", result["slides"][1])
        self.assertIn("Managed backups", result["slides"][1]["bullets"][0])
        self.assertEqual(extractor.calls, 3)

    async def test_model_failure_returns_original_deck(self):
        deck = sample_deck()
        extractor = FakeExtractor(error=RuntimeError("provider unavailable"))

        result = await improve_deck_coherence(extractor, deck)

        self.assertIs(result, deck)
        self.assertEqual(extractor.calls, 1)


if __name__ == "__main__":
    unittest.main()
