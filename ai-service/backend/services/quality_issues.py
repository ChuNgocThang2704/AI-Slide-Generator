"""Canonical quality issue contract shared by deterministic and LLM validators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


class IssueSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


ALLOWED_ISSUE_TYPES = frozenset({
    "duplicate_content", "off_topic", "weak_progression", "missing_transition",
    "contradiction", "visual_mismatch", "missing_requirement", "factual_accuracy",
    "missing_example", "objective_mismatch", "unsupported_claim", "incomplete_coverage",
    "weak_support", "role_mismatch", "incomplete_example", "list_title_mismatch",
    "format_artifact", "weak_closing", "overloaded_slide", "unsupported_numeric_claim",
})

ISSUE_ALIASES = {
    "duplicate": "duplicate_content", "duplication": "duplicate_content",
    "redundancy": "duplicate_content", "redundant_content": "duplicate_content",
    "topic_drift": "off_topic", "poor_progression": "weak_progression",
    "weak_narrative": "weak_progression", "transition": "missing_transition",
    "inconsistency": "contradiction", "visual_inconsistency": "visual_mismatch",
    "missing_user_requirement": "missing_requirement",
    "missing_requested_content": "missing_requirement", "factual_error": "factual_accuracy",
    "incorrect_fact": "factual_accuracy", "inaccurate": "factual_accuracy",
    "weak_example": "missing_example", "missing_worked_example": "missing_example",
    "learning_objective_mismatch": "objective_mismatch",
    "unsupported_absolute": "unsupported_claim", "missing_component": "incomplete_coverage",
    "incomplete_list": "incomplete_coverage", "partial_framework": "incomplete_coverage",
    "insufficient_evidence": "weak_support", "weak_evidence": "weak_support",
    "pedagogical_role_mismatch": "role_mismatch",
    "incomplete_code_example": "incomplete_example",
    "incomplete_worked_example": "incomplete_example",
    "plural_title_mismatch": "list_title_mismatch", "markdown_artifact": "format_artifact",
    "weak_summary": "weak_closing", "excessive_density": "overloaded_slide",
}

ALLOWED_TARGET_FIELDS = frozenset({
    "title", "bullets", "notes", "pedagogical_role", "table", "chart", "layout",
    "source_pages",
})


@dataclass(frozen=True)
class QualityIssue:
    slide_index: int
    issue_type: str
    severity: IssueSeverity
    instruction: str
    target_fields: Tuple[str, ...] = ("title", "bullets", "notes")
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize with legacy keys while exposing the canonical field target."""
        result = {
            "index": self.slide_index,
            "slide_index": self.slide_index,
            "type": self.issue_type,
            "severity": self.severity.value,
            "instruction": self.instruction,
            "target_fields": list(self.target_fields),
        }
        if self.evidence:
            result["evidence"] = self.evidence
        return result


def normalize_quality_issue(
    value: Any,
    *,
    slide_count: int,
    allowed_indices: Optional[set[int]] = None,
    default_fields: Sequence[str] = ("title", "bullets", "notes"),
) -> Optional[QualityIssue]:
    if isinstance(value, QualityIssue):
        issue = value
    elif isinstance(value, Mapping):
        try:
            index = int(value.get("slide_index", value.get("index")))
        except (TypeError, ValueError):
            return None
        issue_type = str(value.get("type") or value.get("issue_type") or "").strip().lower()
        issue_type = ISSUE_ALIASES.get(issue_type, issue_type)
        severity_value = str(value.get("severity") or "low").strip().lower()
        instruction = str(value.get("instruction") or "").strip()[:500]
        inferred_fields = default_fields
        if issue_type in {"role_mismatch", "missing_example", "objective_mismatch"}:
            inferred_fields = (*default_fields, "pedagogical_role")
        elif issue_type in {"factual_accuracy", "unsupported_claim", "unsupported_numeric_claim", "incomplete_example"}:
            inferred_fields = ("bullets", "notes")
        elif issue_type in {"format_artifact", "list_title_mismatch"}:
            inferred_fields = ("title", "bullets")
        raw_fields = value.get("target_fields") or value.get("fields") or inferred_fields
        if isinstance(raw_fields, str):
            raw_fields = [raw_fields]
        fields = tuple(dict.fromkeys(
            str(field).strip().lower() for field in raw_fields
            if str(field).strip().lower() in ALLOWED_TARGET_FIELDS
        ))
        if issue_type not in ALLOWED_ISSUE_TYPES or severity_value not in {item.value for item in IssueSeverity}:
            return None
        if not instruction or not fields:
            return None
        issue = QualityIssue(
            slide_index=index,
            issue_type=issue_type,
            severity=IssueSeverity(severity_value),
            instruction=instruction,
            target_fields=fields,
            evidence=str(value.get("evidence") or "").strip()[:500],
        )
    else:
        return None
    if issue.slide_index < 0 or issue.slide_index >= slide_count:
        return None
    if allowed_indices is not None and issue.slide_index not in allowed_indices:
        return None
    return issue


def normalize_quality_issues(
    values: Iterable[Any], *, slide_count: int, allowed_indices: Optional[set[int]] = None
) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for value in values:
        issue = normalize_quality_issue(
            value, slide_count=slide_count, allowed_indices=allowed_indices
        )
        if issue is None:
            continue
        key = (issue.slide_index, issue.issue_type, issue.target_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue.to_dict())
    return result
