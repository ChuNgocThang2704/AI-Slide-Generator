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

    async def test_model_failure_returns_original_deck(self):
        deck = sample_deck()
        extractor = FakeExtractor(error=RuntimeError("provider unavailable"))

        result = await improve_deck_coherence(extractor, deck)

        self.assertIs(result, deck)
        self.assertEqual(extractor.calls, 1)


if __name__ == "__main__":
    unittest.main()
