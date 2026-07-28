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
