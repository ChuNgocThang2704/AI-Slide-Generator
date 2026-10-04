import asyncio
import json
import unittest

from services.visual_translate import restore_dropped_bullets, translate_deck_text


class _Extractor:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def _llm_completion_plain_text(self, messages, **_):
        self.calls += 1
        return self.reply(json.loads(messages[1]["content"])["items"])


def _run(deck, old, reply):
    extractor = _Extractor(reply)
    repaired = asyncio.run(restore_dropped_bullets(extractor, deck, old, "en"))
    return repaired, extractor.calls


class TranslationBulletTests(unittest.TestCase):
    def test_slide_with_fewer_bullets_gets_every_original_bullet_translated(self):
        old = [{"bullets": ["một", "hai", "ba"]}, {"bullets": ["bốn"]}]
        deck = {"slides": [{"bullets": ["one", "two"]}, {"bullets": ["four"]}]}
        repaired, calls = _run(deck, old, lambda items: json.dumps({"items": [f"EN {i}" for i in items]}))
        assert repaired == [0] and calls == 1
        assert deck["slides"][0]["bullets"] == ["EN một", "EN hai", "EN ba"]
        assert deck["slides"][1]["bullets"] == ["four"]


    def test_wrong_item_count_leaves_the_slide_as_it_was(self):
        old = [{"bullets": ["một", "hai", "ba"]}]
        deck = {"slides": [{"bullets": ["one", "two"]}]}
        repaired, _ = _run(deck, old, lambda items: json.dumps({"items": ["only one"]}))
        assert repaired == [] and deck["slides"][0]["bullets"] == ["one", "two"]


    def test_changed_slide_count_is_not_touched(self):
        deck = {"slides": [{"bullets": []}]}
        repaired, calls = _run(deck, [{"bullets": ["a"]}, {"bullets": ["b"]}], lambda items: "{}")
        assert repaired == [] and calls == 0


class TranslateDeckTextTests(unittest.TestCase):
    def _deck(self):
        return {"title": "Cà phê", "slides": [
            {"title": "Cà phê", "bullets": ["Tổng quan"], "layout": "intro"},
            {"title": "Sản lượng", "bullets": ["2020: 1,76", "Tăng nhẹ"], "notes": "Ghi chú", "chart": {"labels": ["2020"]}},
        ]}

    def test_every_string_is_translated_in_its_own_place(self):
        extractor = _Extractor(lambda items: json.dumps({"items": [f"EN:{i}" for i in items]}))
        deck = self._deck()
        out = asyncio.run(translate_deck_text(extractor, deck, "en"))
        self.assertEqual([s["title"] for s in out["slides"]], ["EN:Cà phê", "EN:Sản lượng"])
        self.assertEqual(out["slides"][1]["bullets"], ["2020: 1,76", "EN:Tăng nhẹ"])  # a bare number is not text
        self.assertEqual(out["slides"][1]["notes"], "EN:Ghi chú")
        self.assertEqual(out["slides"][1]["chart"], {"labels": ["2020"]})
        self.assertEqual(out["slides"][0]["layout"], "intro")
        self.assertEqual(deck["slides"][1]["bullets"], ["2020: 1,76", "Tăng nhẹ"])  # the source deck is untouched

    def test_only_the_named_slides_are_translated(self):
        extractor = _Extractor(lambda items: json.dumps({"items": [f"EN:{i}" for i in items]}))
        out = asyncio.run(translate_deck_text(extractor, self._deck(), "en", [1]))
        self.assertEqual(out["slides"][0]["title"], "Cà phê")
        self.assertEqual(out["slides"][1]["title"], "EN:Sản lượng")

    def test_a_wrong_item_count_gives_up_instead_of_shifting_text(self):
        extractor = _Extractor(lambda items: json.dumps({"items": items[:-1]}))
        self.assertIsNone(asyncio.run(translate_deck_text(extractor, self._deck(), "en")))
        self.assertEqual(extractor.calls, 2)


if __name__ == "__main__":
    unittest.main()
