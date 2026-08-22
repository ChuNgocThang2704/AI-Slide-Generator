"""Hybrid source retrieval for long, page-aware documents.

The retriever combines BM25 with an optional multilingual embedding model. It
is deliberately independent from the slide-generation pipeline so retrieval
can fail closed and leave the existing LLM/lexical fallbacks intact.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable, List, Optional, Sequence


_PAGE_RE = re.compile(r"\[\[SOURCE_PAGE:\s*(\d+)\s*\]\]", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "of", "on", "or", "that", "the", "this", "to", "with",
    "cac", "cho", "cua", "duoc", "la", "mot", "nhung", "slide", "tao",
    "theo", "trinh", "tu", "va", "ve",
}


@dataclass(frozen=True)
class SourceChunk:
    page: int
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    pages: List[int]
    confidence: float
    method: str


def _fold(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _tokens(text: str) -> List[str]:
    return [
        token
        for token in _TOKEN_RE.findall(_fold(text))
        if len(token) > 1 and token not in _STOPWORDS and not token.isdigit()
    ]


def _split_pages(source_text: str) -> List[tuple[int, str]]:
    source = str(source_text or "")
    matches = list(_PAGE_RE.finditer(source))
    pages: List[tuple[int, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        text = source[start:end].strip()
        if text:
            pages.append((int(match.group(1)), text))
    return pages


def _chunk_pages(
    source_text: str,
    *,
    target_words: int = 360,
    overlap_words: int = 60,
) -> List[SourceChunk]:
    chunks: List[SourceChunk] = []
    step = max(1, target_words - overlap_words)
    for page, page_text in _split_pages(source_text):
        words = re.findall(r"\S+", page_text)
        if not words:
            continue
        for start in range(0, len(words), step):
            part = words[start:start + target_words]
            if not part:
                break
            chunks.append(SourceChunk(page=page, text=" ".join(part)))
            if start + target_words >= len(words):
                break
    return chunks


def _bm25_scores(query: str, chunks: Sequence[SourceChunk]) -> List[float]:
    documents = [_tokens(chunk.text) for chunk in chunks]
    query_tokens = _tokens(query)
    if not documents or not query_tokens:
        return [0.0] * len(chunks)
    lengths = [len(document) for document in documents]
    avg_length = sum(lengths) / max(1, len(lengths))
    frequencies = Counter(token for document in documents for token in set(document))
    scores: List[float] = []
    k1, b = 1.5, 0.75
    for document, length in zip(documents, lengths):
        counts = Counter(document)
        score = 0.0
        for token in query_tokens:
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            doc_frequency = frequencies.get(token, 0)
            idf = math.log(1.0 + (len(documents) - doc_frequency + 0.5) / (doc_frequency + 0.5))
            denominator = frequency + k1 * (1.0 - b + b * length / max(1.0, avg_length))
            score += idf * frequency * (k1 + 1.0) / denominator
        scores.append(score)
    return scores


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


_MODEL_LOCK = threading.Lock()


@lru_cache(maxsize=2)
def _load_fastembed_model(model_name: str) -> Any:
    from fastembed import TextEmbedding

    with _MODEL_LOCK:
        cache_dir = os.getenv("SOURCE_EMBEDDING_CACHE_DIR", "").strip() or None
        return TextEmbedding(model_name=model_name, cache_dir=cache_dir)


def _default_embedder(model_name: str) -> Callable[[Sequence[str]], List[Sequence[float]]]:
    model = _load_fastembed_model(model_name)

    def embed(texts: Sequence[str]) -> List[Sequence[float]]:
        return list(model.embed(list(texts)))

    return embed


class HybridSourceRetriever:
    def __init__(
        self,
        *,
        model_name: str,
        semantic_enabled: bool = True,
        embedder: Optional[Callable[[Sequence[str]], Sequence[Sequence[float]]]] = None,
    ) -> None:
        self.model_name = model_name
        self.semantic_enabled = semantic_enabled
        self.embedder = embedder

    def retrieve(
        self,
        source_text: str,
        query: str,
        *,
        max_pages: int = 8,
    ) -> RetrievalResult:
        chunks = _chunk_pages(source_text)
        if not chunks or not str(query or "").strip():
            return RetrievalResult([], 0.0, "none")

        bm25 = _bm25_scores(query, chunks)
        semantic: Optional[List[float]] = None
        if self.semantic_enabled:
            try:
                embed = self.embedder or _default_embedder(self.model_name)
                if "e5" in self.model_name.lower() and self.embedder is None:
                    embedding_inputs = [f"query: {query}"] + [
                        f"passage: {chunk.text}" for chunk in chunks
                    ]
                else:
                    embedding_inputs = [query] + [chunk.text for chunk in chunks]
                vectors = list(embed(embedding_inputs))
                if len(vectors) == len(chunks) + 1:
                    semantic = [_cosine(vectors[0], vector) for vector in vectors[1:]]
            except Exception as exc:
                print(f"[source_retrieval] embedding unavailable; BM25 only: {exc}")

        ranks: defaultdict[int, float] = defaultdict(float)
        for position, index in enumerate(sorted(range(len(chunks)), key=lambda i: bm25[i], reverse=True)):
            if bm25[index] <= 0:
                break
            ranks[index] += 0.45 / (60 + position)
        if semantic is not None:
            for position, index in enumerate(
                sorted(range(len(chunks)), key=lambda i: semantic[i], reverse=True)
            ):
                if semantic[index] <= 0:
                    break
                ranks[index] += 0.55 / (60 + position)

        if not ranks:
            return RetrievalResult([], 0.0, "none")

        ordered = sorted(ranks, key=lambda index: ranks[index], reverse=True)
        page_scores: defaultdict[int, float] = defaultdict(float)
        for index in ordered[: max(12, max_pages * 3)]:
            page_scores[chunks[index].page] = max(page_scores[chunks[index].page], ranks[index])
        pages = [
            page
            for page, _score in sorted(page_scores.items(), key=lambda item: (-item[1], item[0]))[:max_pages]
        ]

        top = ranks[ordered[0]]
        runner_up = ranks[ordered[1]] if len(ordered) > 1 else 0.0
        separation = max(0.0, min(1.0, (top - runner_up) / max(top, 1e-9)))
        lexical_signal = min(1.0, max(bm25) / 4.0)
        semantic_signal = 0.0
        if semantic is not None and len(semantic) > 1:
            # E5 cosine values are often all high. Relevance is trustworthy only
            # when the query separates the best chunks from the rest.
            ordered_semantic = sorted(semantic, reverse=True)
            baseline = ordered_semantic[min(len(ordered_semantic) - 1, max(1, len(ordered_semantic) // 2))]
            semantic_spread = ordered_semantic[0] - baseline
            semantic_signal = max(0.0, min(1.0, (semantic_spread - 0.015) / 0.08))
        evidence = max(lexical_signal, semantic_signal)
        confidence = min(0.98, 0.35 + 0.25 * separation + 0.40 * evidence)
        method = "hybrid" if semantic is not None else "bm25"
        return RetrievalResult(pages, round(confidence, 4), method)


@lru_cache(maxsize=32)
def _cached_retrieve(
    source_digest: str,
    source_text: str,
    query: str,
    model_name: str,
    semantic_enabled: bool,
    max_pages: int,
) -> RetrievalResult:
    del source_digest
    return HybridSourceRetriever(
        model_name=model_name,
        semantic_enabled=semantic_enabled,
    ).retrieve(source_text, query, max_pages=max_pages)


def retrieve_source_pages(
    source_text: str,
    query: str,
    *,
    model_name: str,
    semantic_enabled: bool = True,
    max_pages: int = 8,
) -> RetrievalResult:
    digest = hashlib.sha256(str(source_text or "").encode("utf-8", errors="ignore")).hexdigest()
    return _cached_retrieve(
        digest,
        str(source_text or ""),
        str(query or ""),
        model_name,
        semantic_enabled,
        max_pages,
    )
