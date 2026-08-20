import html
import re
import unicodedata
from typing import Any, List


def plain_slide_text(value: Any) -> str:
    """Return user-visible slide text without markdown formatting markers."""
    t = unicodedata.normalize("NFKC", html.unescape(str(value or ""))).strip()
    if not t:
        return ""
    t = t.translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }))
    t = re.sub(r"<[^>\n]{1,80}>", " ", t)
    t = re.sub(r"[•◦▪▫■□●○◆◇★☆✓✔✗✘➜→←↑↓↔]", " ", t)
    cleaned_chars: List[str] = []
    symbol_keep = set("$€£¥₫%‰+-=<>±×÷°")
    for ch in t:
        if ch == "\ufffd":
            continue
        cat = unicodedata.category(ch)
        if cat[0] == "C":
            cleaned_chars.append(" ")
            continue
        if cat[0] == "S" and ch not in symbol_keep:
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(ch)
    t = "".join(cleaned_chars)
    t = re.sub(r"^\s*(?:[-+*]|•)\s+", "", t)
    # Strip only a leading list marker. Internal stars and underscores are
    # valid programming syntax and must survive API payload serialization.
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def plain_slide_block(value: Any) -> str:
    """Clean visible text while preserving code-block newlines and indentation."""
    raw = str(value or "")
    if "\n" not in raw and "\r" not in raw:
        return plain_slide_text(raw)
    lines: List[str] = []
    for source_line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not source_line.strip():
            if lines and lines[-1] != "":
                lines.append("")
            continue
        leading = len(source_line) - len(source_line.lstrip(" "))
        cleaned = plain_slide_text(source_line.strip())
        if cleaned:
            lines.append(f"{' ' * leading}{cleaned}")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
