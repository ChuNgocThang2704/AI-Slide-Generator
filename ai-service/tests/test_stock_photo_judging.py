import asyncio
import unittest
from unittest import mock

from services import stock_photos


class StockPhotoJudgingTests(unittest.TestCase):
    def _run(self, verdicts, delays):
        metas = [{"image_url": f"u{i}"} for i in range(3)]

        async def search(client, query):
            return metas

        async def download(client, url):
            return {"bytes": url.encode(), "extension": ".jpg"}

        async def judge(img, meta):
            i = int(meta["image_url"][1:])
            await asyncio.sleep(delays[i])
            return verdicts[i]

        with mock.patch.object(stock_photos, "_search_wikimedia", search), \
                mock.patch.object(stock_photos, "_download_image", download):
            return asyncio.run(stock_photos.fetch_external_image(
                None, queries=["q"], providers=["wikimedia"], vlm_validate_fn=judge))

    def test_first_passing_photo_in_search_order_wins_even_if_a_later_one_judges_faster(self):
        result = self._run([False, True, True], [0.03, 0.02, 0.0])
        self.assertEqual(result["image_url"], "u1")

    def test_none_when_no_photo_passes(self):
        self.assertIsNone(self._run([False, False, False], [0, 0, 0]))

    def test_judging_runs_side_by_side(self):
        import time
        started = time.monotonic()
        self._run([False, False, False], [0.2, 0.2, 0.2])
        self.assertLess(time.monotonic() - started, 0.5)
