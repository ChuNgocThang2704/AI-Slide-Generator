import copy
import json
import unittest

from services.deck_coherence import improve_deck_coherence


class FakeExtractor:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = 0

    async def _llm_completion_plain_text(self, messages, **kwargs):
        self.calls += 1
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
        ])

        result = await improve_deck_coherence(extractor, deck)

        self.assertEqual(result["slides"][0], original["slides"][0])
        self.assertEqual(result["slides"][1]["title"], "Tu van de den giai phap")
        self.assertEqual(result["slides"][1]["layout"], "text_table")
        self.assertEqual(result["slides"][1]["table"], original["slides"][1]["table"])
        self.assertEqual(deck, original)
        self.assertEqual(extractor.calls, 2)

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
