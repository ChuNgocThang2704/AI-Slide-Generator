import asyncio
import unittest
from unittest.mock import patch

from services.content_extractor import ContentExtractor
from services.source_retrieval import HybridSourceRetriever, RetrievalResult


def _source(*pages):
    return "\n".join(
        f"[[SOURCE_PAGE:{number}]]\n{text}"
        for number, text in pages
    )


class SourceRetrievalTests(unittest.TestCase):
    def test_bm25_finds_exact_technical_evidence(self):
        source = _source(
            (1, "Cloud infrastructure deployment and network operations."),
            (2, "Fruitful functions return a computed value to the caller."),
            (3, "Local variables exist only during a function call."),
        )
        result = HybridSourceRetriever(
            model_name="unused",
            semantic_enabled=False,
        ).retrieve(source, "fruitful functions return value", max_pages=2)

        self.assertEqual(result.pages[0], 2)
        self.assertEqual(result.method, "bm25")
        self.assertGreaterEqual(result.confidence, 0.6)

    def test_embedding_handles_cross_language_request(self):
        source = _source(
            (1, "Cloud infrastructure deployment."),
            (2, "A function can return a computed value."),
            (3, "Local variables and function parameters."),
        )

        vectors = {
            "Chi trinh bay ham tra ve ket qua.": [1.0, 0.0],
            "Cloud infrastructure deployment.": [0.0, 1.0],
            "A function can return a computed value.": [0.98, 0.02],
            "Local variables and function parameters.": [0.2, 0.8],
        }

        def fake_embedder(texts):
            return [vectors[text] for text in texts]

        result = HybridSourceRetriever(
            model_name="unused",
            semantic_enabled=True,
            embedder=fake_embedder,
        ).retrieve(source, "Chi trinh bay ham tra ve ket qua.", max_pages=2)

        self.assertEqual(result.pages[0], 2)
        self.assertEqual(result.method, "hybrid")
        self.assertGreaterEqual(result.confidence, 0.6)

    def test_empty_query_returns_no_selection(self):
        result = HybridSourceRetriever(
            model_name="unused",
            semantic_enabled=False,
        ).retrieve(_source((1, "Some content.")), "")
        self.assertEqual(result.pages, [])
        self.assertEqual(result.method, "none")

    def test_llm_reranks_hybrid_candidates_before_materializing_source(self):
        source = _source(
            (1, "Assignment statements and interactive mode. " * 80),
            (3, "Script mode and expression evaluation. " * 80),
            (7, "General function composition. " * 80),
            (15, "Parameters are local variables inside a function. " * 80),
            (16, "Fruitful functions return results; void functions do not. " * 80),
        )
        extractor = ContentExtractor()
        extractor.vllm_available = True
        extractor.gemini_available = False
        seen_prompt = {}

        async def fake_completion(messages, **kwargs):
            seen_prompt["text"] = messages[-1]["content"]
            return '{"pages":[15,16],"confidence":0.94,"reason":"both requested concepts"}'

        extractor._llm_completion_plain_text = fake_completion
        retrieval = RetrievalResult([3, 7, 15, 16], 0.81, "hybrid")
        with patch(
            "services.content.extractor.retrieve_source_pages",
            return_value=retrieval,
        ):
            excerpt = asyncio.run(
                extractor._focus_document_scope(
                    source,
                    "Explain fruitful functions and variable scope.",
                    max_chars=900,
                )
            )

        self.assertIn("PAGE 15:", seen_prompt["text"])
        self.assertNotIn("PAGE 1:", seen_prompt["text"])
        self.assertIn("Parameters are local", excerpt)
        self.assertIn("Fruitful functions", excerpt)
        self.assertNotIn("Script mode", excerpt)


if __name__ == "__main__":
    unittest.main()
