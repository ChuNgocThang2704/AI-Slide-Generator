from services.duplicate_content import detect_duplicate_content


def _deck(*slides):
    return {"slides": list(slides)}


def _slide(title, bullet, *, layout="text_only", role="concept"):
    return {"title": title, "bullets": [bullet], "layout": layout, "pedagogical_role": role}


def test_exact_duplicate_is_detected_before_embedding_and_targets_later_slide():
    deck = _deck(
        _slide("Cover", "Overview", layout="intro"),
        _slide("AI benefits", "Automation reduces repetitive work."),
        _slide("AI benefits!", "Automation reduces repetitive work"),
        _slide("Closing", "Questions", layout="thankyou", role="summary"),
    )

    issues = detect_duplicate_content(
        deck, model_name="test", semantic_enabled=False
    )

    assert len(issues) == 1
    assert issues[0]["index"] == 2
    assert issues[0]["type"] == "duplicate_content"
    assert "method=exact" in issues[0]["evidence"]


def test_embedding_detects_semantic_duplicate_but_not_distinct_slide():
    vectors = {
        "Neural networks\nModels learn layered representations.": [1.0, 0.0],
        "Deep learning\nLayered models learn useful features.": [0.99, 0.01],
        "Deployment\nMonitoring detects production drift.": [0.0, 1.0],
    }

    def fake_embedder(texts):
        return [vectors[text] for text in texts]

    deck = _deck(
        _slide("Neural networks", "Models learn layered representations."),
        _slide("Deep learning", "Layered models learn useful features."),
        _slide("Deployment", "Monitoring detects production drift."),
    )
    issues = detect_duplicate_content(
        deck, model_name="test", embedder=fake_embedder, semantic_threshold=0.95
    )

    assert [issue["index"] for issue in issues] == [1]
    assert "method=embedding" in issues[0]["evidence"]


def test_embedding_failure_keeps_exact_results_and_does_not_block_generation():
    def unavailable(_texts):
        raise RuntimeError("model missing")

    deck = _deck(
        _slide("A repeated topic", "The same sufficiently long explanation appears here."),
        _slide("A repeated topic", "The same sufficiently long explanation appears here."),
    )
    issues = detect_duplicate_content(
        deck, model_name="test", embedder=unavailable
    )

    assert len(issues) == 1
    assert "method=exact" in issues[0]["evidence"]


def test_boundary_and_summary_slides_are_not_duplicate_candidates():
    deck = _deck(
        _slide("Same", "Repeated framing content for the presentation.", layout="intro"),
        _slide("Same", "Repeated framing content for the presentation.", layout="thankyou", role="summary"),
    )

    assert detect_duplicate_content(deck, model_name="test", semantic_enabled=False) == []


def test_semantically_close_concept_and_practice_are_not_treated_as_duplicates():
    def fake_embedder(_texts):
        return [[1.0, 0.0], [1.0, 0.0]]

    deck = _deck(
        _slide("Index lookup", "An index narrows records scanned for matching keys."),
        _slide(
            "Practice index lookup",
            "Compare records scanned with and without the index.",
            role="practice",
        ),
    )

    assert detect_duplicate_content(
        deck, model_name="test", embedder=fake_embedder
    ) == []
