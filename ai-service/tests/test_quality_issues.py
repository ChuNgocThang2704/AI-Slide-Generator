import asyncio
import json

from services.deck_coherence import _refine
from services.quality_issues import (
    IssueSeverity,
    QualityIssue,
    normalize_quality_issue,
    normalize_quality_issues,
)


class RefiningExtractor:
    async def _llm_completion_plain_text(self, messages, **kwargs):
        return json.dumps({"slides": [{
            "index": 0,
            "title": "Model tried to replace title",
            "bullets": ["Correct value: 91%."],
            "notes": "Corrected from source.",
        }]})


def test_normalizes_legacy_issue_to_canonical_contract_and_alias():
    issue = normalize_quality_issue(
        {
            "index": 2,
            "type": "factual_error",
            "severity": "high",
            "instruction": "Correct the unsupported number.",
        },
        slide_count=4,
    )

    assert issue == QualityIssue(
        slide_index=2,
        issue_type="factual_accuracy",
        severity=IssueSeverity.HIGH,
        instruction="Correct the unsupported number.",
        target_fields=("bullets", "notes"),
    )
    assert issue.to_dict()["slide_index"] == 2


def test_rejects_invalid_slide_field_and_low_quality_payload():
    assert normalize_quality_issue(
        {"index": 8, "type": "off_topic", "severity": "high", "instruction": "Fix"},
        slide_count=2,
    ) is None
    assert normalize_quality_issue(
        {
            "index": 0,
            "type": "off_topic",
            "severity": "high",
            "instruction": "Fix",
            "target_fields": ["unknown_field"],
        },
        slide_count=2,
    ) is None


def test_deduplicates_same_slide_type_and_field_target():
    issues = normalize_quality_issues(
        [
            {"index": 0, "type": "weak_support", "severity": "medium", "instruction": "Add evidence"},
            {"slide_index": 0, "issue_type": "weak_support", "severity": "high", "instruction": "Ground it"},
        ],
        slide_count=1,
    )

    assert len(issues) == 1
    assert issues[0]["target_fields"] == ["title", "bullets", "notes"]


def test_targeted_refine_preserves_fields_outside_issue_contract():
    deck = {
        "title": "Report",
        "slides": [{
            "title": "Stable title",
            "bullets": ["Incorrect value: 99%."],
            "notes": "Old note.",
            "layout": "text_only",
        }],
    }
    issue = {
        "index": 0,
        "type": "unsupported_numeric_claim",
        "severity": "high",
        "instruction": "Use the source value.",
        "target_fields": ["bullets"],
    }

    repaired, changed = asyncio.run(_refine(RefiningExtractor(), deck, [issue]))

    assert changed == [0]
    assert repaired["slides"][0]["title"] == "Stable title"
    assert repaired["slides"][0]["bullets"] == ["Correct value: 91%."]
    assert repaired["slides"][0]["notes"] == "Old note."
